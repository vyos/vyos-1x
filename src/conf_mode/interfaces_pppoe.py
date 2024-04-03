#!/usr/bin/env python3
#
# Copyright (C) 2019-2024 VyOS maintainers and contributors
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
from vyos.configdict import is_node_changed
from vyos.configverify import verify_authentication
from vyos.configverify import verify_source_interface
from vyos.configverify import verify_vrf
from vyos.configverify import verify_mtu_ipv6
from vyos.configverify import verify_mirror_redirect
from vyos.ifconfig import PPPoEIf
from vyos.template import render
from vyos.utils.process import call
from vyos.utils.process import is_systemd_service_running
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config(config=None):
    """
    Retrive CLI config as dictionary. Dictionary can never be empty, as at least the
    interface name will be added or a deleted flag
    """
    if config:
        conf = config
    else:
        conf = Config()
    base = ['interfaces', 'pppoe']
    ifname, pppoe = get_interface_dict(conf, base)

    # We should only terminate the PPPoE session if critical parameters change.
    # All parameters that can be changed on-the-fly (like interface description)
    # should not lead to a reconnect!
    for options in ['access-concentrator', 'connect-on-demand', 'service-name',
                    'source-interface', 'vrf', 'no-default-route',
                    'authentication', 'host_uniq']:
        if is_node_changed(conf, base + [ifname, options]):
            pppoe.update({'shutdown_required': {}})
            # bail out early - no need to further process other nodes
            break

    if 'deleted' not in pppoe:
        # We always set the MRU value to the MTU size. This code path only re-creates
        # the old behavior if MRU is not set on the CLI.
        if 'mru' not in pppoe:
            pppoe['mru'] = pppoe['mtu']

    return pppoe

def verify(pppoe):
    if 'deleted' in pppoe:
        # bail out early
        return None

    verify_source_interface(pppoe)
    verify_authentication(pppoe)
    verify_vrf(pppoe)
    verify_mtu_ipv6(pppoe)
    verify_mirror_redirect(pppoe)

    if {'connect_on_demand', 'vrf'} <= set(pppoe):
        raise ConfigError('On-demand dialing and VRF can not be used at the same time')

    # both MTU and MRU have default values, thus we do not need to check
    # if the key exists
    if int(pppoe['mru']) > int(pppoe['mtu']):
        raise ConfigError('PPPoE MRU needs to be lower then MTU!')

    return None

def generate(pppoe):
    # set up configuration file path variables where our templates will be
    # rendered into
    ifname = pppoe['ifname']
    config_pppoe = f'/etc/ppp/peers/{ifname}'

    if 'deleted' in pppoe or 'disable' in pppoe:
        if os.path.exists(config_pppoe):
            os.unlink(config_pppoe)

        return None

    # Create PPP configuration files
    render(config_pppoe, 'pppoe/peer.j2', pppoe, permission=0o640)

    return None

def apply(pppoe):
    ifname = pppoe['ifname']
    if 'deleted' in pppoe or 'disable' in pppoe:
        if os.path.isdir(f'/sys/class/net/{ifname}'):
            p = PPPoEIf(ifname)
            p.remove()
        call(f'systemctl stop ppp@{ifname}.service')
        return None

    # reconnect should only be necessary when certain config options change,
    # like ACS name, authentication ... (see get_config() for details)
    if ((not is_systemd_service_running(f'ppp@{ifname}.service')) or
        'shutdown_required' in pppoe):

        # cleanup system (e.g. FRR routes first)
        if os.path.isdir(f'/sys/class/net/{ifname}'):
            p = PPPoEIf(ifname)
            p.remove()

        call(f'systemctl restart ppp@{ifname}.service')
        # When interface comes "live" a hook is called:
        # /etc/ppp/ip-up.d/99-vyos-pppoe-callback
        # which triggers PPPoEIf.update()
    else:
        if os.path.isdir(f'/sys/class/net/{ifname}'):
            p = PPPoEIf(ifname)
            p.update(pppoe)

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
