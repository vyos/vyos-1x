#!/usr/bin/env python3
#
# Copyright (C) 2020-2022 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os

from sys import exit
from time import sleep

from vyos.config import Config
from vyos.configdict import get_interface_dict
from vyos.configdict import is_node_changed
from vyos.configverify import verify_authentication
from vyos.configverify import verify_interface_exists
from vyos.configverify import verify_mirror_redirect
from vyos.configverify import verify_vrf
from vyos.ifconfig import WWANIf
from vyos.utils.dict import dict_search
from vyos.utils.process import cmd
from vyos.utils.process import call
from vyos.utils.process import DEVNULL
from vyos.utils.process import is_systemd_service_active
from vyos.utils.file import write_file
from vyos import ConfigError
from vyos import airbag
airbag.enable()

service_name = 'ModemManager.service'
cron_script = '/etc/cron.d/vyos-wwan'

def get_config(config=None):
    """
    Retrive CLI config as dictionary. Dictionary can never be empty, as at least the
    interface name will be added or a deleted flag
    """
    if config:
        conf = config
    else:
        conf = Config()
    base = ['interfaces', 'wwan']
    ifname, wwan = get_interface_dict(conf, base)

    # We should only terminate the WWAN session if critical parameters change.
    # All parameters that can be changed on-the-fly (like interface description)
    # should not lead to a reconnect!
    tmp = is_node_changed(conf, base + [ifname, 'address'])
    if tmp: wwan.update({'shutdown_required': {}})

    tmp = is_node_changed(conf, base + [ifname, 'apn'])
    if tmp: wwan.update({'shutdown_required': {}})

    tmp = is_node_changed(conf, base + [ifname, 'disable'])
    if tmp: wwan.update({'shutdown_required': {}})

    tmp = is_node_changed(conf, base + [ifname, 'vrf'])
    if tmp: wwan.update({'shutdown_required': {}})

    tmp = is_node_changed(conf, base + [ifname, 'authentication'])
    if tmp: wwan.update({'shutdown_required': {}})

    tmp = is_node_changed(conf, base + [ifname, 'ipv6', 'address', 'autoconf'])
    if tmp: wwan.update({'shutdown_required': {}})

    # We need to know the amount of other WWAN interfaces as ModemManager needs
    # to be started or stopped.
    wwan['other_interfaces'] = conf.get_config_dict([], key_mangling=('-', '_'),
                                                       get_first_key=True,
                                                       no_tag_node_value_mangle=True)

    # This if-clause is just to be sure - it will always evaluate to true
    if ifname in wwan['other_interfaces']:
        del wwan['other_interfaces'][ifname]
    if len(wwan['other_interfaces']) == 0:
        del wwan['other_interfaces']

    return wwan

def verify(wwan):
    if 'deleted' in wwan:
        return None

    ifname = wwan['ifname']
    if not 'apn' in wwan:
        raise ConfigError(f'No APN configured for "{ifname}"!')

    verify_interface_exists(ifname)
    verify_authentication(wwan)
    verify_vrf(wwan)
    verify_mirror_redirect(wwan)

    return None

def generate(wwan):
    if 'deleted' in wwan:
        # We are the last WWAN interface - there are no other ones remaining
        # thus the cronjob needs to go away, too
        if 'other_interfaces' not in wwan:
            if os.path.exists(cron_script):
                os.unlink(cron_script)
        return None

    # Install cron triggered helper script to re-dial WWAN interfaces on
    # disconnect - e.g. happens during RF signal loss. The script watches every
    # WWAN interface - so there is only one instance.
    if not os.path.exists(cron_script):
        write_file(cron_script, '*/5 * * * * root /usr/libexec/vyos/vyos-check-wwan.py\n')

    return None

def apply(wwan):
    # ModemManager is required to dial WWAN connections - one instance is
    # required to serve all modems. Activate ModemManager on first invocation
    # of any WWAN interface.
    if not is_systemd_service_active(service_name):
        cmd(f'systemctl start {service_name}')

        counter = 100
        # Wait until a modem is detected and then we can continue
        while counter > 0:
            counter -= 1
            tmp = cmd('mmcli -L')
            if tmp != 'No modems were found':
                break
            sleep(0.250)

    if 'shutdown_required' in wwan:
        # we only need the modem number. wwan0 -> 0, wwan1 -> 1
        modem = wwan['ifname'].lstrip('wwan')
        base_cmd = f'mmcli --modem {modem}'
        # Number of bearers is limited - always disconnect first
        cmd(f'{base_cmd} --simple-disconnect')

    w = WWANIf(wwan['ifname'])
    if 'deleted' in wwan or 'disable' in wwan:
        w.remove()

        # We are the last WWAN interface - there are no other WWAN interfaces
        # remaining, thus we can stop ModemManager and free resources.
        if 'other_interfaces' not in wwan:
            cmd(f'systemctl stop {service_name}')
            # Clean CRON helper script which is used for to re-connect when
            # RF signal is lost
            if os.path.exists(cron_script):
                os.unlink(cron_script)

        return None

    if 'shutdown_required' in wwan:
        ip_type = 'ipv4'
        slaac = dict_search('ipv6.address.autoconf', wwan) != None
        if 'address' in wwan:
            if 'dhcp' in wwan['address'] and ('dhcpv6' in wwan['address'] or slaac):
                ip_type = 'ipv4v6'
            elif 'dhcpv6' in wwan['address'] or slaac:
                ip_type = 'ipv6'
            elif 'dhcp' in wwan['address']:
                ip_type = 'ipv4'

        options = f'ip-type={ip_type},apn=' + wwan['apn']
        if 'authentication' in wwan:
            options += ',user={username},password={password}'.format(**wwan['authentication'])

        command = f'{base_cmd} --simple-connect="{options}"'
        call(command, stdout=DEVNULL)

    w.update(wwan)
    return None

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
