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

from sys import exit

from vyos.config import Config
from vyos.configdict import get_interface_dict
from vyos.configdict import leaf_node_changed
from vyos.configverify import verify_address
from vyos.configverify import verify_bridge_delete
from vyos.configverify import verify_mtu_ipv6
from vyos.configverify import verify_mirror_redirect
from vyos.configverify import verify_bond_bridge_member
from vyos.configverify import verify_vrf
from vyos.ifconfig import L2TPv3If
from vyos.utils.kernel import check_kmod
from vyos.utils.network import is_addr_assigned
from vyos.utils.network import interface_exists
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
    ifname, l2tpv3 = get_interface_dict(conf, base)

    # To delete an l2tpv3 interface we need the current tunnel and session-id
    if 'deleted' in l2tpv3:
        tmp = leaf_node_changed(conf, base + [ifname, 'tunnel-id'])
        # leaf_node_changed() returns a list
        l2tpv3.update({'tunnel_id': tmp[0]})

        tmp = leaf_node_changed(conf, base + [ifname, 'session-id'])
        l2tpv3.update({'session_id': tmp[0]})

    return l2tpv3

def verify(l2tpv3):
    if 'deleted' in l2tpv3:
        verify_bridge_delete(l2tpv3)
        return None

    interface = l2tpv3['ifname']

    for key in ['source_address', 'remote', 'tunnel_id', 'peer_tunnel_id',
                'session_id', 'peer_session_id']:
        if key not in l2tpv3:
            tmp = key.replace('_', '-')
            raise ConfigError(f'Missing mandatory L2TPv3 option: "{tmp}"!')

    if not is_addr_assigned(l2tpv3['source_address']):
        raise ConfigError('L2TPv3 source-address address "{source_address}" '
                          'not configured on any interface!'.format(**l2tpv3))

    verify_mtu_ipv6(l2tpv3)
    verify_address(l2tpv3)
    verify_vrf(l2tpv3)
    verify_bond_bridge_member(l2tpv3)
    verify_mirror_redirect(l2tpv3)
    return None

def generate(l2tpv3):
    return None

def apply(l2tpv3):
    check_kmod(k_mod)

    # Check if L2TPv3 interface already exists
    if interface_exists(l2tpv3['ifname']):
        # L2TPv3 is picky when changing tunnels/sessions, thus we can simply
        # always delete it first.
        l = L2TPv3If(**l2tpv3)
        l.remove()

    if 'deleted' not in l2tpv3:
        # Finally create the new interface
        l = L2TPv3If(**l2tpv3)
        l.update(l2tpv3)

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
