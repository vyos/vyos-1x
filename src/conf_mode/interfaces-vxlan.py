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
from vyos.ifconfig import VXLANIf, Interface
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

    # VXLAN is "special" the default MTU is 1492 - update accordingly
    # as the config_level is already st in get_interface_dict() - we can use []
    tmp = conf.get_config_dict([], key_mangling=('-', '_'), get_first_key=True)
    if 'mtu' not in tmp:
        vxlan['mtu'] = '1450'

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

    if 'vni' not in vxlan:
        raise ConfigError('Must configure VNI for VXLAN')

    if 'source_interface' in vxlan:
        # VXLAN adds a 50 byte overhead - we need to check the underlaying MTU
        # if our configured MTU is at least 50 bytes less
        lower_mtu = Interface(vxlan['source_interface']).get_mtu()
        if lower_mtu < (int(vxlan['mtu']) + 50):
            raise ConfigError('VXLAN has a 50 byte overhead, underlaying device ' \
                              f'MTU is to small ({underlay_mtu} bytes)')

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
        # This is a special type of interface which needs additional parameters
        # when created using iproute2. Instead of passing a ton of arguments,
        # use a dictionary provided by the interface class which holds all the
        # options necessary.
        conf = VXLANIf.get_config()

        # Assign VXLAN instance configuration parameters to config dict
        for tmp in ['vni', 'group', 'source_address', 'source_interface', 'remote', 'port']:
            if tmp in vxlan:
                conf[tmp] = vxlan[tmp]

        # Finally create the new interface
        v = VXLANIf(vxlan['ifname'], **conf)
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
