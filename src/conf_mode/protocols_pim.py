#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

from ipaddress import IPv4Address
from ipaddress import IPv4Network
from signal import SIGTERM
from sys import exit

from vyos.config import Config
from vyos.configverify import verify_interface_exists
from vyos.configverify import has_frr_protocol_in_dict
from vyos.frrender import FRRender
from vyos.frrender import get_frrender_dict
from vyos.frrender import pim_daemon
from vyos.utils.process import is_systemd_service_running
from vyos.utils.process import process_named_running
from vyos.utils.process import call
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    return get_frrender_dict(conf)

def verify(config_dict):
    if not has_frr_protocol_in_dict(config_dict, 'pim'):
        return None

    pim = config_dict['pim']

    if 'deleted' in pim:
        return None

    if 'igmp_proxy_enabled' in pim:
        raise ConfigError('IGMP proxy and PIM cannot be configured at the same time!')

    if 'interface' not in pim:
        raise ConfigError('PIM require defined interfaces!')

    RESERVED_MC_NET = '224.0.0.0/24'
    for interface, interface_config in pim['interface'].items():
        verify_interface_exists(pim, interface)

        # Check join group in reserved net
        if 'igmp' in interface_config and 'join' in interface_config['igmp']:
            for join_addr in interface_config['igmp']['join']:
                if IPv4Address(join_addr) in IPv4Network(RESERVED_MC_NET):
                    raise ConfigError(f'Groups within {RESERVED_MC_NET} are reserved and cannot be joined!')

    if 'rp' in pim:
        if 'address' not in pim['rp']:
            raise ConfigError('PIM rendezvous point needs to be defined!')

        # Check unique multicast groups
        unique = []
        pim_base_error = 'PIM rendezvous point group'
        for address, address_config in pim['rp']['address'].items():
            if 'group' not in address_config:
                raise ConfigError(f'{pim_base_error} should be defined for "{address}"!')

            # Check if it is a multicast group
            for gr_addr in address_config['group']:
                if not IPv4Network(gr_addr).is_multicast:
                    raise ConfigError(f'{pim_base_error} "{gr_addr}" is not a multicast group!')
                if gr_addr in unique:
                    raise ConfigError(f'{pim_base_error} must be unique!')
                unique.append(gr_addr)

def generate(config_dict):
    if config_dict and not is_systemd_service_running('vyos-configd.service'):
        FRRender().generate(config_dict)
    return None

def apply(config_dict):
    if not has_frr_protocol_in_dict(config_dict, 'pim'):
        return None

    pim_pid = process_named_running(pim_daemon)
    pim = config_dict['pim']
    if 'deleted' in pim:
        os.kill(int(pim_pid), SIGTERM)
        return None

    if not pim_pid:
        call('/usr/lib/frr/pimd -d -F traditional --daemon -A 127.0.0.1')

    if config_dict and not is_systemd_service_running('vyos-configd.service'):
        FRRender().apply()
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
