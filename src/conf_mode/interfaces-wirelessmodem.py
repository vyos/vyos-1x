#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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

from vyos.config import Config
from vyos.configdict import get_interface_dict
from vyos.configverify import verify_vrf
from vyos.template import render
from vyos.util import call
from vyos.util import check_kmod
from vyos.util import find_device_file
from vyos import ConfigError
from vyos import airbag
airbag.enable()

k_mod = ['option', 'usb_wwan', 'usbserial']

def get_config(config=None):
    """
    Retrive CLI config as dictionary. Dictionary can never be empty, as at least the
    interface name will be added or a deleted flag
    """
    if config:
        conf = config
    else:
        conf = Config()
    base = ['interfaces', 'wirelessmodem']
    wwan = get_interface_dict(conf, base)

    return wwan

def verify(wwan):
    if 'deleted' in wwan:
        return None

    if not 'apn' in wwan:
        raise ConfigError('No APN configured for "{ifname}"'.format(**wwan))

    if not 'device' in wwan:
        raise ConfigError('Physical "device" must be configured')

    # we can not use isfile() here as Linux device files are no regular files
    # thus the check will return False
    dev_path = find_device_file(wwan['device'])
    if dev_path is None or not os.path.exists(dev_path):
        raise ConfigError('Device "{device}" does not exist'.format(**wwan))

    verify_vrf(wwan)

    return None

def generate(wwan):
    # set up configuration file path variables where our templates will be
    # rendered into
    ifname = wwan['ifname']
    config_wwan = f'/etc/ppp/peers/{ifname}'
    config_wwan_chat = f'/etc/ppp/peers/chat.{ifname}'
    script_wwan_pre_up = f'/etc/ppp/ip-pre-up.d/1010-vyos-wwan-{ifname}'
    script_wwan_ip_up = f'/etc/ppp/ip-up.d/1010-vyos-wwan-{ifname}'
    script_wwan_ip_down = f'/etc/ppp/ip-down.d/1010-vyos-wwan-{ifname}'

    config_files = [config_wwan, config_wwan_chat, script_wwan_pre_up,
                    script_wwan_ip_up, script_wwan_ip_down]

    # Always hang-up WWAN connection prior generating new configuration file
    call(f'systemctl stop ppp@{ifname}.service')

    if 'deleted' in wwan:
        # Delete PPP configuration files
        for file in config_files:
            if os.path.exists(file):
                os.unlink(file)

    else:
        wwan['device'] = find_device_file(wwan['device'])

        # Create PPP configuration files
        render(config_wwan, 'wwan/peer.tmpl', wwan, trim_blocks=True)
        # Create PPP chat script
        render(config_wwan_chat, 'wwan/chat.tmpl', wwan, trim_blocks=True)

        # generated script file must be executable

        # Create script for ip-pre-up.d
        render(script_wwan_pre_up, 'wwan/ip-pre-up.script.tmpl',
               wwan, trim_blocks=True, permission=0o755)
        # Create script for ip-up.d
        render(script_wwan_ip_up, 'wwan/ip-up.script.tmpl',
               wwan, trim_blocks=True, permission=0o755)
        # Create script for ip-down.d
        render(script_wwan_ip_down, 'wwan/ip-down.script.tmpl',
               wwan, trim_blocks=True, permission=0o755)

    return None

def apply(wwan):
    if 'deleted' in wwan:
        # bail out early
        return None

    if not 'disable' in wwan:
        # "dial" WWAN connection
        call('systemctl start ppp@{ifname}.service'.format(**wwan))

    return None

if __name__ == '__main__':
    try:
        check_kmod(k_mod)
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
