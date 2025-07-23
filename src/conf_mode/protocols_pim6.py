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

from ipaddress import IPv6Address
from ipaddress import IPv6Network
from sys import exit

from vyos.config import Config
from vyos.configverify import has_frr_protocol_in_dict
from vyos.configverify import verify_interface_exists
from vyos.utils.process import is_systemd_service_running
from vyos.frrender import FRRender
from vyos.frrender import get_frrender_dict
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
    if not has_frr_protocol_in_dict(config_dict, 'pim6'):
        return None

    pim6 = config_dict['pim6']
    if 'deleted' in pim6:
        return None

    for interface, interface_config in pim6.get('interface', {}).items():
        verify_interface_exists(pim6, interface)
        if 'mld' in interface_config:
            mld = interface_config['mld']
            for group in mld.get('join', {}).keys():
                # Validate multicast group address
                if not IPv6Address(group).is_multicast:
                    raise ConfigError(f"{group} is not a multicast group")

    if 'rp' in pim6:
        if 'address' not in pim6['rp']:
            raise ConfigError('PIM6 rendezvous point needs to be defined!')

        # Check unique multicast groups
        unique = []
        pim_base_error = 'PIM6 rendezvous point group'

        if {'address', 'prefix-list6'} <= set(pim6['rp']):
            raise ConfigError(f'{pim_base_error} supports either address or a prefix-list!')

        for address, address_config in pim6['rp']['address'].items():
            if 'group' not in address_config:
                raise ConfigError(f'{pim_base_error} should be defined for "{address}"!')

            # Check if it is a multicast group
            for gr_addr in address_config['group']:
                if not IPv6Network(gr_addr).is_multicast:
                    raise ConfigError(f'{pim_base_error} "{gr_addr}" is not a multicast group!')
                if gr_addr in unique:
                    raise ConfigError(f'{pim_base_error} must be unique!')
                unique.append(gr_addr)

def generate(config_dict):
    if config_dict and not is_systemd_service_running('vyos-configd.service'):
        FRRender().generate(config_dict)
    return None

def apply(config_dict):
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
