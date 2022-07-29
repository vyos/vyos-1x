#!/usr/bin/env python3
#
# Copyright (C) 2019-2022 VyOS maintainers and contributors
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

from vyos.base import Warning
from vyos.config import Config
from vyos.configdict import get_interface_dict
from vyos.configdict import leaf_node_changed
from vyos.configdict import is_node_changed
from vyos.configverify import verify_address
from vyos.configverify import verify_bridge_delete
from vyos.configverify import verify_mtu_ipv6
from vyos.configverify import verify_mirror_redirect
from vyos.configverify import verify_source_interface
from vyos.configverify import verify_bond_bridge_member
from vyos.ifconfig import Interface
from vyos.ifconfig import VXLANIf
from vyos.template import is_ipv6
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config(config=None):
    """
    Retrive CLI config as dictionary. Dictionary can never be empty, as at least
    the interface name will be added or a deleted flag
    """
    if config:
        conf = config
    else:
        conf = Config()
    base = ['interfaces', 'vxlan']
    ifname, vxlan = get_interface_dict(conf, base)

    # VXLAN interfaces are picky and require recreation if certain parameters
    # change. But a VXLAN interface should - of course - not be re-created if
    # it's description or IP address is adjusted. Feels somehow logic doesn't it?
    for cli_option in ['external', 'gpe', 'group', 'port', 'remote',
                       'source-address', 'source-interface', 'vni']:
        if leaf_node_changed(conf, base + [ifname, cli_option]):
            vxlan.update({'rebuild_required': {}})

    if is_node_changed(conf, base + [ifname, 'parameters']):
        vxlan.update({'rebuild_required': {}})

    # We need to verify that no other VXLAN tunnel is configured when external
    # mode is in use - Linux Kernel limitation
    conf.set_level(base)
    vxlan['other_tunnels'] = conf.get_config_dict([], key_mangling=('-', '_'),
                                                  get_first_key=True,
                                                  no_tag_node_value_mangle=True)

    # This if-clause is just to be sure - it will always evaluate to true
    ifname = vxlan['ifname']
    if ifname in vxlan['other_tunnels']:
        del vxlan['other_tunnels'][ifname]
    if len(vxlan['other_tunnels']) == 0:
        del vxlan['other_tunnels']

    return vxlan

def verify(vxlan):
    if 'deleted' in vxlan:
        verify_bridge_delete(vxlan)
        return None

    if int(vxlan['mtu']) < 1500:
        Warning('RFC7348 recommends VXLAN tunnels preserve a 1500 byte MTU')

    if 'group' in vxlan:
        if 'source_interface' not in vxlan:
            raise ConfigError('Multicast VXLAN requires an underlaying interface')
        verify_source_interface(vxlan)

    if not any(tmp in ['group', 'remote', 'source_address'] for tmp in vxlan):
        raise ConfigError('Group, remote or source-address must be configured')

    if 'vni' not in vxlan and 'external' not in vxlan:
        raise ConfigError(
            'Must either configure VXLAN "vni" or use "external" CLI option!')

    if {'external', 'vni'} <= set(vxlan):
        raise ConfigError('Can not specify both "external" and "VNI"!')

    if {'external', 'other_tunnels'} <= set(vxlan):
        other_tunnels = ', '.join(vxlan['other_tunnels'])
        raise ConfigError(f'Only one VXLAN tunnel is supported when "external" '\
                          f'CLI option is used. Additional tunnels: {other_tunnels}')

    if 'gpe' in vxlan and 'external' not in vxlan:
        raise ConfigError(f'VXLAN-GPE is only supported when "external" '\
                          f'CLI option is used.')

    if 'source_interface' in vxlan:
        # VXLAN adds at least an overhead of 50 byte - we need to check the
        # underlaying device if our VXLAN package is not going to be fragmented!
        vxlan_overhead = 50
        if 'source_address' in vxlan and is_ipv6(vxlan['source_address']):
            # IPv6 adds an extra 20 bytes overhead because the IPv6 header is 20
            # bytes larger than the IPv4 header - assuming no extra options are
            # in use.
            vxlan_overhead += 20

        # If source_address is not used - check IPv6 'remote' list
        elif 'remote' in vxlan:
            if any(is_ipv6(a) for a in vxlan['remote']):
                vxlan_overhead += 20

        lower_mtu = Interface(vxlan['source_interface']).get_mtu()
        if lower_mtu < (int(vxlan['mtu']) + vxlan_overhead):
            raise ConfigError(f'Underlaying device MTU is to small ({lower_mtu} '\
                              f'bytes) for VXLAN overhead ({vxlan_overhead} bytes!)')

    # Check for mixed IPv4 and IPv6 addresses
    protocol = None
    if 'source_address' in vxlan:
        if is_ipv6(vxlan['source_address']):
            protocol = 'ipv6'
        else:
            protocol = 'ipv4'

    if 'remote' in vxlan:
        error_msg = 'Can not mix both IPv4 and IPv6 for VXLAN underlay'
        for remote in vxlan['remote']:
            if is_ipv6(remote):
                if protocol == 'ipv4':
                    raise ConfigError(error_msg)
                protocol = 'ipv6'
            else:
                if protocol == 'ipv6':
                    raise ConfigError(error_msg)
                protocol = 'ipv4'

    verify_mtu_ipv6(vxlan)
    verify_address(vxlan)
    verify_bond_bridge_member(vxlan)
    verify_mirror_redirect(vxlan)
    return None

def generate(vxlan):
    return None

def apply(vxlan):
    # Check if the VXLAN interface already exists
    if 'rebuild_required' in vxlan or 'delete' in vxlan:
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
