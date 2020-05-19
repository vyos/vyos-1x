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
import re

from sys import exit
from copy import deepcopy
from netifaces import interfaces

from vyos.config import Config
from vyos.configdict import list_diff
from vyos.ifconfig import WireGuardIf
from vyos.util import chown, chmod_750, call
from vyos.validate import is_member, is_ipv6
from vyos import ConfigError

kdir = r'/config/auth/wireguard'

default_config_data = {
    'intfc': '',
    'address': [],
    'address_remove': [],
    'description': '',
    'listen_port': '',
    'deleted': False,
    'disable': False,
    'fwmark': 0,
    'is_bridge_member': False,
    'mtu': 1420,
    'peer': [],
    'peer_remove': [], # stores public keys of peers to remove
    'pk': f'{kdir}/default/private.key',
    'vrf': ''
}

def _check_kmod():
    modules = ['wireguard']
    for module in modules:
        if not os.path.exists(f'/sys/module/{module}'):
            if call(f'modprobe {module}') != 0:
                raise ConfigError(f'Loading Kernel module {module} failed')


def _migrate_default_keys():
    if os.path.exists(f'{kdir}/private.key') and not os.path.exists(f'{kdir}/default/private.key'):
        location = f'{kdir}/default'
        if not os.path.exists(location):
            os.makedirs(location)

        chown(location, 'root', 'vyattacfg')
        chmod_750(location)
        os.rename(f'{kdir}/private.key', f'{location}/private.key')
        os.rename(f'{kdir}/public.key', f'{location}/public.key')


def get_config():
    conf = Config()
    base = ['interfaces', 'wireguard']

    # determine tagNode instance
    if 'VYOS_TAGNODE_VALUE' not in os.environ:
        raise ConfigError('Interface (VYOS_TAGNODE_VALUE) not specified')

    wg = deepcopy(default_config_data)
    wg['intf'] = os.environ['VYOS_TAGNODE_VALUE']

    # check if interface is member if a bridge
    wg['is_bridge_member'] = is_member(conf, wg['intf'], 'bridge')

    # Check if interface has been removed
    if not conf.exists(base + [wg['intf']]):
        wg['deleted'] = True
        return wg

    conf.set_level(base + [wg['intf']])

    # retrieve configured interface addresses
    if conf.exists(['address']):
        wg['address'] = conf.return_values(['address'])

    # get interface addresses (currently effective) - to determine which
    # address is no longer valid and needs to be removed
    eff_addr = conf.return_effective_values(['address'])
    wg['address_remove'] = list_diff(eff_addr, wg['address'])

    # retrieve interface description
    if conf.exists(['description']):
        wg['description'] = conf.return_value(['description'])

    # disable interface
    if conf.exists(['disable']):
        wg['disable'] = True

    # local port to listen on
    if conf.exists(['port']):
        wg['listen_port'] = conf.return_value(['port'])

    # fwmark value
    if conf.exists(['fwmark']):
        wg['fwmark'] = int(conf.return_value(['fwmark']))

    # Maximum Transmission Unit (MTU)
    if conf.exists('mtu'):
        wg['mtu'] = int(conf.return_value(['mtu']))

    # retrieve VRF instance
    if conf.exists('vrf'):
        wg['vrf'] = conf.return_value('vrf')

    # private key
    if conf.exists(['private-key']):
        wg['pk'] = "{0}/{1}/private.key".format(
            kdir, conf.return_value(['private-key']))

    # peer removal, wg identifies peers by its pubkey
    peer_eff = conf.list_effective_nodes(['peer'])
    peer_rem = list_diff(peer_eff, conf.list_nodes(['peer']))
    for peer in peer_rem:
        wg['peer_remove'].append(
            conf.return_effective_value(['peer', peer, 'pubkey']))

    # peer settings
    if conf.exists(['peer']):
        for p in conf.list_nodes(['peer']):
            # set new config level for this peer
            conf.set_level(base + [wg['intf'], 'peer', p])
            peer = {
                'allowed-ips': [],
                'address': '',
                'name': p,
                'persistent_keepalive': '',
                'port': '',
                'psk': '',
                'pubkey': ''
            }

            # peer allowed-ips
            if conf.exists(['allowed-ips']):
                peer['allowed-ips'] = conf.return_values(['allowed-ips'])

            # peer address
            if conf.exists(['address']):
                peer['address'] = conf.return_value(['address'])

            # peer port
            if conf.exists(['port']):
                peer['port'] = conf.return_value(['port'])

            # persistent-keepalive
            if conf.exists(['persistent-keepalive']):
                peer['persistent_keepalive'] = conf.return_value(['persistent-keepalive'])

            # preshared-key
            if conf.exists(['preshared-key']):
                peer['psk'] = conf.return_value(['preshared-key'])

            # peer pubkeys
            if conf.exists(['pubkey']):
                key_eff = conf.return_effective_value(['pubkey'])
                key_cfg = conf.return_value(['pubkey'])
                peer['pubkey'] = key_cfg

                # on a pubkey change we need to remove the pubkey first
                # peers are identified by pubkey, so key update means
                # peer removal and re-add
                if key_eff != key_cfg and key_eff != None:
                    wg['peer_remove'].append(key_cfg)

            # if a peer is disabled, we have to exec a remove for it's pubkey
            if conf.exists(['disable']):
                wg['peer_remove'].append(peer['pubkey'])
            else:
                wg['peer'].append(peer)

    return wg


def verify(wg):
    if wg['deleted']:
        if wg['is_bridge_member']:
            raise ConfigError((
                f'Cannot delete interface "{wg["intf"]}" as it is a member '
                f'of bridge "{wg["is_bridge_member"]}"!'))

        return None

    if wg['is_bridge_member'] and wg['address']:
        raise ConfigError((
            f'Cannot assign address to interface "{wg["intf"]}" '
            f'as it is a member of bridge "{wg["is_bridge_member"]}"!'))

    if wg['vrf']:
        if wg['vrf'] not in interfaces():
            raise ConfigError(f'VRF "{wg["vrf"]}" does not exist')

        if wg['is_bridge_member']:
            raise ConfigError((
                f'Interface "{wg["intf"]}" cannot be member of VRF '
                f'"{wg["vrf"]}" and bridge {wg["is_bridge_member"]} '
                f'at the same time!'))

    if not os.path.exists(wg['pk']):
        raise ConfigError('No keys found, generate them by executing:\n' \
                          '"run generate wireguard [keypair|named-keypairs]"')

    if not wg['address']:
        raise ConfigError(f'IP address required for interface "{wg["intf"]}"!')

    if not wg['peer']:
        raise ConfigError(f'Peer required for interface "{wg["intf"]}"!')

    # run checks on individual configured WireGuard peer
    for peer in wg['peer']:
        if not peer['allowed-ips']:
            raise ConfigError(f'Peer allowed-ips required for peer "{peer["name"]}"!')

        if not peer['pubkey']:
            raise ConfigError(f'Peer public-key required for peer "{peer["name"]}"!')

        if peer['address'] and not peer['port']:
            raise ConfigError(f'Peer "{peer["name"]}" port must be defined if address is defined!')

        if not peer['address'] and peer['port']:
           raise ConfigError(f'Peer "{peer["name"]}" address must be defined if port is defined!')


def apply(wg):
    # init wg class
    w = WireGuardIf(wg['intf'])

    # single interface removal
    if wg['deleted']:
        w.remove()
        return None

    # Configure interface address(es)
    # - not longer required addresses get removed first
    # - newly addresses will be added second
    for addr in wg['address_remove']:
        w.del_addr(addr)
    for addr in wg['address']:
        w.add_addr(addr)

    # Maximum Transmission Unit (MTU)
    w.set_mtu(wg['mtu'])

    # update interface description used e.g. within SNMP
    w.set_alias(wg['description'])

    # assign/remove VRF (ONLY when not a member of a bridge,
    # otherwise 'nomaster' removes it from it)
    if not wg['is_bridge_member']:
        w.set_vrf(wg['vrf'])

    # remove peers
    for pub_key in wg['peer_remove']:
        w.remove_peer(pub_key)

    # peer pubkey
    # setting up the wg interface
    w.config['private-key'] = c['pk']

    for peer in wg['peer']:
        # peer pubkey
        w.config['pubkey'] = peer['pubkey']
        # peer allowed-ips
        w.config['allowed-ips'] = peer['allowed-ips']
        # local listen port
        if wg['listen_port']:
            w.config['port'] = wg['listen_port']
        # fwmark
        if c['fwmark']:
            w.config['fwmark'] = wg['fwmark']

        # endpoint
        if peer['address'] and peer['port']:
            if is_ipv6(peer['address']):
                w.config['endpoint'] = '[{}]:{}'.format(peer['address'], peer['port'])
            else:
                w.config['endpoint'] = '{}:{}'.format(peer['address'], peer['port'])

        # persistent-keepalive
        if peer['persistent_keepalive']:
            w.config['keepalive'] = peer['persistent_keepalive']

        # maybe move it into ifconfig.py
        # preshared-key - needs to be read from a file
        if peer['psk']:
            psk_file = '/config/auth/wireguard/psk'
            with open(psk_file, 'w') as f:
                f.write(peer['psk'])
            w.config['psk'] = psk_file

        w.update()

    # Enable/Disable interface
    if wg['disable']:
        w.set_admin_state('down')
    else:
        w.set_admin_state('up')

    return None

if __name__ == '__main__':
    try:
        _check_kmod()
        _migrate_default_keys()
        c = get_config()
        verify(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
