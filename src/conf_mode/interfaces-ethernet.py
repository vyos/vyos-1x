#!/usr/bin/env python3
#
# Copyright (C) 2019-2020 VyOS maintainers and contributors
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
from vyos.configdict import dict_merge
from vyos.configdict import T2665_default_dict_cleanup
from vyos.configverify import verify_interface_exists
from vyos.configverify import verify_dhcpv6
from vyos.configverify import verify_address
from vyos.configverify import verify_vrf
from vyos.configverify import verify_vlan_config
from vyos.ifconfig import EthernetIf
from vyos.ifconfig_vlan import get_removed_vlans
from vyos.validate import is_member
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()


def get_config():
    """ Retrive CLI config as dictionary. Dictionary can never be empty,
    as at least the interface name will be added or a deleted flag """
    conf = Config()

    # determine tagNode instance
    if 'VYOS_TAGNODE_VALUE' not in os.environ:
        raise ConfigError('Interface (VYOS_TAGNODE_VALUE) not specified')

    # retrieve interface default values
    base = ['interfaces', 'ethernet']
    default_values = defaults(base)

    ifname = os.environ['VYOS_TAGNODE_VALUE']
    base = base + [ifname]
    # setup config level which is extracted in get_removed_vlans()
    conf.set_level(base)
    ethernet = conf.get_config_dict([], key_mangling=('-', '_'), get_first_key=True)

    # Check if interface has been removed
    if ethernet == {}:
        ethernet.update({'deleted' : ''})

    # We have gathered the dict representation of the CLI, but there are
    # default options which we need to update into the dictionary
    # retrived.
    ethernet = dict_merge(default_values, ethernet)

    # Add interface instance name into dictionary
    ethernet.update({'ifname': ifname})

    # Check if we are a member of a bridge device
    bridge = is_member(conf, ifname, 'bridge')
    if bridge:
        tmp = {'is_bridge_member' : bridge}
        ethernet.update(tmp)

    # Check if we are a member of a bond device
    bond = is_member(conf, ifname, 'bonding')
    if bond:
        tmp = {'is_bond_member' : bond}
        ethernet.update(tmp)

    ethernet = T2665_default_dict_cleanup( ethernet )
    # Check vif, vif-s/vif-c VLAN interfaces for removal
    ethernet = get_removed_vlans( conf, ethernet )
    return ethernet

def verify(ethernet):
    if 'deleted' in ethernet.keys():
        return None

    verify_interface_exists(ethernet)

    if ethernet.get('speed', None) == 'auto':
        if ethernet.get('duplex', None) != 'auto':
            raise ConfigError('If speed is hardcoded, duplex must be hardcoded, too')

    if ethernet.get('duplex', None) == 'auto':
        if ethernet.get('speed', None) != 'auto':
            raise ConfigError('If duplex is hardcoded, speed must be hardcoded, too')

    verify_dhcpv6(ethernet)
    verify_address(ethernet)
    verify_vrf(ethernet)

    if {'is_bond_member', 'mac'} <= set(ethernet):
        print(f'WARNING: changing mac address "{mac}" will be ignored as "{ifname}" '
              f'is a member of bond "{is_bond_member}"'.format(**ethernet))

    # use common function to verify VLAN configuration
    verify_vlan_config(ethernet)
    return None

def generate(ethernet):
    return None

def apply(ethernet):
    e = EthernetIf(ethernet['ifname'])
    if 'deleted' in ethernet.keys():
        # delete interface
        e.remove()
    else:
        e.update(ethernet)


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
