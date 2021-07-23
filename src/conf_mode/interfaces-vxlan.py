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
from netifaces import interfaces

from vyos.config import Config
from vyos.configdict import get_interface_dict
from vyos.configverify import verify_address
from vyos.configverify import verify_bridge_delete
from vyos.configverify import verify_mtu_ipv6
from vyos.configverify import verify_source_interface
from vyos.ifconfig import Interface
from vyos.ifconfig import VXLANIf
from vyos.template import is_ipv6
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
    base = ['interfaces', 'vxlan']
    vxlan = get_interface_dict(conf, base)
    
    if 'port' not in vxlan:
        vxlan['port'] = '8472'

    return vxlan

def verify(vxlan):
    if 'deleted' in vxlan:
        verify_bridge_delete(vxlan)
        return None

    if int(vxlan['mtu']) < 1500:
        print('WARNING: RFC7348 recommends VXLAN tunnels preserve a 1500 byte MTU')

    if 'group' in vxlan:
        if 'source_interface' not in vxlan:
            raise ConfigError('Multicast VXLAN requires an underlaying interface ')

        verify_source_interface(vxlan)

    if not any(tmp in ['group', 'remote', 'source_address'] for tmp in vxlan):
        raise ConfigError('Group, remote or source-address must be configured')

    if 'external' not in vxlan and 'vni' not in vxlan:
        raise ConfigError('VNI must be configured for vxlan or the external flag must be turned on')
    
    if 'external' in vxlan and 'vni' in vxlan:
        raise ConfigError('You can only turn on the external flag or configure VNI for vxlan. The two options cannot exist at the same time')

    if 'source_interface' in vxlan:
        # VXLAN adds at least an overhead of 50 byte - we need to check the
        # underlaying device if our VXLAN package is not going to be fragmented!
        vxlan_overhead = 50
        if 'source_address' in vxlan and is_ipv6(vxlan['source_address']):
            # IPv6 adds an extra 20 bytes overhead because the IPv6 header is 20
            # bytes larger than the IPv4 header - assuming no extra options are
            # in use.
            vxlan_overhead += 20

        lower_mtu = Interface(vxlan['source_interface']).get_mtu()
        if lower_mtu < (int(vxlan['mtu']) + vxlan_overhead):
            raise ConfigError(f'Underlaying device MTU is to small ({lower_mtu} '\
                              f'bytes) for VXLAN overhead ({vxlan_overhead} bytes!)')

    verify_mtu_ipv6(vxlan)
    verify_address(vxlan)
    return None


def generate(vxlan):
    return None


def apply(vxlan):
    # Check if the VXLAN interface already exists
    if vxlan['ifname'] in interfaces():
        v = VXLANIf(vxlan['ifname'])
        # VXLAN is super picky and the tunnel always needs to be recreated,
        # thus we can simply always delete it first.
        v.remove()

    if 'deleted' not in vxlan:
        # Finally create the new interface
        v = VXLANIf(**vxlan)
        v.update(vxlan)

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
