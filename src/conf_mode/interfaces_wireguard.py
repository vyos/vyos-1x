#!/usr/bin/env python3
#
# Copyright (C) 2018-2024 VyOS maintainers and contributors
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
from vyos.configdict import is_node_changed
from vyos.configverify import verify_vrf
from vyos.configverify import verify_address
from vyos.configverify import verify_bridge_delete
from vyos.configverify import verify_mtu_ipv6
from vyos.configverify import verify_mirror_redirect
from vyos.configverify import verify_bond_bridge_member
from vyos.ifconfig import WireGuardIf
from vyos.utils.kernel import check_kmod
from vyos.utils.network import check_port_availability
from vyos.utils.network import is_wireguard_key_pair
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
    ifname, wireguard = get_interface_dict(conf, base)

    # Check if a port was changed
    tmp = is_node_changed(conf, base + [ifname, 'port'])
    if tmp: wireguard['port_changed'] = {}

    # T4702: If anything on a peer changes we remove the peer first and re-add it
    if is_node_changed(conf, base + [ifname, 'peer']):
        wireguard.update({'rebuild_required': {}})

    return wireguard

def verify(wireguard):
    if 'deleted' in wireguard:
        verify_bridge_delete(wireguard)
        return None

    verify_mtu_ipv6(wireguard)
    verify_address(wireguard)
    verify_vrf(wireguard)
    verify_bond_bridge_member(wireguard)
    verify_mirror_redirect(wireguard)

    if 'private_key' not in wireguard:
        raise ConfigError('Wireguard private-key not defined')

    if 'port' in wireguard and 'port_changed' in wireguard:
        listen_port = int(wireguard['port'])
        if check_port_availability('0.0.0.0', listen_port, 'udp') is not True:
            raise ConfigError(f'UDP port {listen_port} is busy or unavailable and '
                               'cannot be used for the interface!')

    # run checks on individual configured WireGuard peer
    if 'peer' in wireguard:
        public_keys = []
        for tmp in wireguard['peer']:
            peer = wireguard['peer'][tmp]

            if 'allowed_ips' not in peer:
                raise ConfigError(f'Wireguard allowed-ips required for peer "{tmp}"!')

            if 'public_key' not in peer:
                raise ConfigError(f'Wireguard public-key required for peer "{tmp}"!')

            if ('address' in peer and 'port' not in peer) or ('port' in peer and 'address' not in peer):
                raise ConfigError('Both Wireguard port and address must be defined '
                                  f'for peer "{tmp}" if either one of them is set!')

            if peer['public_key'] in public_keys:
                raise ConfigError(f'Duplicate public-key defined on peer "{tmp}"')

            if 'disable' not in peer:
                if is_wireguard_key_pair(wireguard['private_key'], peer['public_key']):
                    raise ConfigError(f'Peer "{tmp}" has the same public key as the interface "{wireguard["ifname"]}"')

            public_keys.append(peer['public_key'])

def generate(wireguard):
    return None

def apply(wireguard):
    check_kmod('wireguard')

    if 'rebuild_required' in wireguard or 'deleted' in wireguard:
        wg = WireGuardIf(**wireguard)
        # WireGuard only supports peer removal based on the configured public-key,
        # by deleting the entire interface this is the shortcut instead of parsing
        # out all peers and removing them one by one.
        #
        # Peer reconfiguration will always come with a short downtime while the
        # WireGuard interface is recreated (see below)
        wg.remove()

    # Create the new interface if required
    if 'deleted' not in wireguard:
        wg = WireGuardIf(**wireguard)
        wg.update(wireguard)

    return None

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
