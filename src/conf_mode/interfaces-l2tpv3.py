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
from copy import deepcopy
from netifaces import interfaces

from vyos.config import Config
from vyos.configdict import get_interface_dict
from vyos.configdict import leaf_node_changed
from vyos.configverify import verify_address
from vyos.configverify import verify_bridge_delete
from vyos.ifconfig import L2TPv3If
from vyos.util import check_kmod
from vyos.validate import is_addr_assigned
from vyos import ConfigError
from vyos import airbag
airbag.enable()

k_mod = ['l2tp_eth', 'l2tp_netlink', 'l2tp_ip', 'l2tp_ip6']


def get_config(config=None):
    """
    Retrive CLI config as dictionary. Dictionary can never be empty, as at least the
    interface name will be added or a deleted flag
    """
    if config:
        conf = config
    else:
        conf = Config()
    base = ['interfaces', 'l2tpv3']
    l2tpv3 = get_interface_dict(conf, base)

    # L2TPv3 is "special" the default MTU is 1488 - update accordingly
    # as the config_level is already st in get_interface_dict() - we can use []
    tmp = conf.get_config_dict([], key_mangling=('-', '_'), get_first_key=True)
    if 'mtu' not in tmp:
        l2tpv3['mtu'] = '1488'

    # To delete an l2tpv3 interface we need the current tunnel and session-id
    if 'deleted' in l2tpv3:
        tmp = leaf_node_changed(conf, ['tunnel-id'])
        # leaf_node_changed() returns a list
        l2tpv3.update({'tunnel_id': tmp[0]})

        tmp = leaf_node_changed(conf, ['session-id'])
        l2tpv3.update({'session_id': tmp[0]})

    return l2tpv3

def verify(l2tpv3):
    if 'deleted' in l2tpv3:
        verify_bridge_delete(l2tpv3)
        return None

    interface = l2tpv3['ifname']

    for key in ['local_ip', 'remote_ip', 'tunnel_id', 'peer_tunnel_id',
                'session_id', 'peer_session_id']:
        if key not in l2tpv3:
            tmp = key.replace('_', '-')
            raise ConfigError(f'L2TPv3 {tmp} must be configured!')

    if not is_addr_assigned(l2tpv3['local_ip']):
        raise ConfigError('L2TPv3 local-ip address '
                          '"{local_ip}" is not configured!'.format(**l2tpv3))

    verify_address(l2tpv3)
    return None

def generate(l2tpv3):
    return None

def apply(l2tpv3):
    # L2TPv3 interface needs to be created/deleted on-block, instead of
    # passing a ton of arguments, I just use a dict that is managed by
    # vyos.ifconfig
    conf = deepcopy(L2TPv3If.get_config())

    # Check if L2TPv3 interface already exists
    if l2tpv3['ifname'] in interfaces():
        # L2TPv3 is picky when changing tunnels/sessions, thus we can simply
        # always delete it first.
        conf['session_id'] = l2tpv3['session_id']
        conf['tunnel_id'] = l2tpv3['tunnel_id']
        l = L2TPv3If(l2tpv3['ifname'], **conf)
        l.remove()

    if 'deleted' not in l2tpv3:
        conf['peer_tunnel_id'] = l2tpv3['peer_tunnel_id']
        conf['local_port'] = l2tpv3['source_port']
        conf['remote_port'] = l2tpv3['destination_port']
        conf['encapsulation'] = l2tpv3['encapsulation']
        conf['local_address'] = l2tpv3['local_ip']
        conf['remote_address'] = l2tpv3['remote_ip']
        conf['session_id'] = l2tpv3['session_id']
        conf['tunnel_id'] = l2tpv3['tunnel_id']
        conf['peer_session_id'] = l2tpv3['peer_session_id']

        # Finally create the new interface
        l = L2TPv3If(l2tpv3['ifname'], **conf)
        l.update(l2tpv3)

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
