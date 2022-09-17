#!/usr/bin/env python3
#
# Copyright (C) 2018-2020 VyOS maintainers and contributors
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
from vyos.configdict import get_interface_dict
from vyos.configdict import is_node_changed
from vyos.configverify import verify_vrf
from vyos.configverify import verify_address
from vyos.configverify import verify_bridge_delete
from vyos.configverify import verify_mtu_ipv6
from vyos.configverify import verify_bond_bridge_member
from vyos.ifconfig import WireGuardIf
from vyos.util import check_kmod
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
    base = ['interfaces', 'wireguard']
    wireguard = get_interface_dict(conf, base)

    # Mangle private key - it has a default so its always valid
    wireguard['private_key'] = '/config/auth/wireguard/{private_key}/private.key'.format(**wireguard)

    # Determine which Wireguard peer has been removed.
    # Peers can only be removed with their public key!
    if 'peer' in wireguard:
        ifname = wireguard['ifname']
        peer_remove = {}
        for peer, peer_config in wireguard['peer'].items():
            # T4702: If anything on a peer changes we remove the peer first and re-add it
            if is_node_changed(conf, ['peer', peer]):
                if 'pubkey' in peer_config:
                    peer_remove = dict_merge({'peer_remove' : {peer : peer_config['pubkey']}}, peer_remove)
        if peer_remove:
            wireguard.update(peer_remove)

    return wireguard

def verify(wireguard):
    if 'deleted' in wireguard:
        verify_bridge_delete(wireguard)
        return None

    verify_mtu_ipv6(wireguard)
    verify_address(wireguard)
    verify_vrf(wireguard)
    verify_bond_bridge_member(wireguard)

    if not os.path.exists(wireguard['private_key']):
        raise ConfigError('Wireguard private-key not found! Execute: ' \
                          '"run generate wireguard [default-keypair|named-keypairs]"')

    if 'peer' not in wireguard:
        raise ConfigError('At least one Wireguard peer is required!')

    # run checks on individual configured WireGuard peer
    for tmp in wireguard['peer']:
        peer = wireguard['peer'][tmp]

        if 'allowed_ips' not in peer:
            raise ConfigError(f'Wireguard allowed-ips required for peer "{tmp}"!')

        if 'pubkey' not in peer:
            raise ConfigError(f'Wireguard public-key required for peer "{tmp}"!')

        if ('address' in peer and 'port' not in peer) or ('port' in peer and 'address' not in peer):
            raise ConfigError('Both Wireguard port and address must be defined '
                              f'for peer "{tmp}" if either one of them is set!')

def apply(wireguard):
    tmp = WireGuardIf(wireguard['ifname'])
    if 'deleted' in wireguard:
        tmp.remove()
        return None

    tmp.update(wireguard)
    return None

if __name__ == '__main__':
    try:
        check_kmod('wireguard')
        c = get_config()
        verify(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
