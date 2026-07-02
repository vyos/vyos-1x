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

import os

from glob import glob
from sys import exit

from vyos.config import Config
from vyos.configdict import get_interface_dict
from vyos.configdict import is_node_changed
from vyos.configdict import is_vrf_changed
from vyos.configdict import is_source_interface
from vyos.configdep import set_dependents
from vyos.configdep import call_dependents
from vyos.configverify import verify_vrf
from vyos.configverify import verify_address
from vyos.configverify import verify_bridge_delete
from vyos.configverify import verify_mtu_ipv6
from vyos.configverify import verify_mirror_redirect
from vyos.configverify import verify_bond_bridge_member
from vyos.defaults import wireguard_fwmark_pref
from vyos.ifconfig import WireGuardIf
from vyos.utils.kernel import check_kmod
from vyos.utils.network import check_port_availability
from vyos.utils.network import get_vrf_tableid
from vyos.utils.network import is_wireguard_key_pair
from vyos.utils.process import call
from vyos import ConfigError
from vyos import airbag
airbag.enable()


def get_config(config=None):
    """
    Retrieve CLI config as dictionary. Dictionary can never be empty, as at least the
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

    wireguard['peers_need_resolve'] = []
    if 'peer' in wireguard:
        for peer, peer_config in wireguard['peer'].items():
            if 'disable' not in peer_config and 'host_name' in peer_config:
                wireguard['peers_need_resolve'].append(peer)

    # Check if interface is used as source-interface on VXLAN interface
    tmp = is_source_interface(conf, ifname, 'vxlan')
    if tmp:
        if 'deleted' not in wireguard:
            set_dependents('vxlan', conf, tmp)
        else:
            wireguard['is_source_interface'] = tmp

    if is_node_changed(conf, base + [ifname, 'fwmark']) or is_node_changed(
        conf, base + [ifname, 'vrf']
    ):
        wireguard['fwmark_vrf_changed'] = {}
        prev = conf.get_config_dict(
            base + [ifname], effective=True, key_mangling=('-', '_'), get_first_key=True
        )
        wireguard['prev_fwmark'] = prev.get('fwmark')
        wireguard['prev_vrf'] = prev.get('vrf')

    # Check vrf membership, to ensure firewall is updated
    if is_vrf_changed(conf, ifname):
        set_dependents('firewall', conf)

    return wireguard


def verify(wireguard):
    if 'deleted' in wireguard:
        verify_bridge_delete(wireguard)
        if 'is_source_interface' in wireguard:
            raise ConfigError(
                f'Interface "{wireguard["ifname"]}" cannot be deleted as it is used '
                f'as source interface for "{wireguard["is_source_interface"]}"!'
            )
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
        if check_port_availability(None, listen_port, protocol='udp') is not True:
            raise ConfigError(f'UDP port {listen_port} is busy or unavailable and '
                               'cannot be used for the interface!')

    # run checks on individual configured WireGuard peer
    if 'peer' in wireguard:
        public_keys = []
        for tmp in wireguard['peer']:
            peer = wireguard['peer'][tmp]

            base_error = f'WireGuard peer "{tmp}":'

            if 'host_name' in peer and 'address' in peer:
                raise ConfigError(f'{base_error} address/host-name are mutually exclusive!')

            if 'allowed_ips' not in peer:
                raise ConfigError(f'{base_error} missing mandatory allowed-ips!')

            if 'public_key' not in peer:
                raise ConfigError(f'{base_error} missing mandatory public-key!')

            if peer['public_key'] in public_keys:
                raise ConfigError(f'{base_error} duplicate public-key!')

            if 'disable' not in peer:
                if is_wireguard_key_pair(wireguard['private_key'], peer['public_key']):
                    tmp = wireguard["ifname"]
                    raise ConfigError(f'{base_error} identical public key as interface "{tmp}"!')

            port_addr_error = f'{base_error} both port and address/host-name must '\
                              'be defined if either one of them is set!'
            if 'port' not in peer:
                if 'host_name' in peer or 'address' in peer:
                    raise ConfigError(port_addr_error)
            else:
                if 'host_name' not in peer and 'address' not in peer:
                    raise ConfigError(port_addr_error)

            public_keys.append(peer['public_key'])


def generate(wireguard):
    return None


def apply(wireguard):
    check_kmod('wireguard')

    wg = WireGuardIf(**wireguard)

    if 'deleted' in wireguard:
        wg.remove()
    else:
        wg.update(wireguard)

    # delete old fwmark-based ip rule if fwmark or VRF was changed
    if 'fwmark_vrf_changed' in wireguard or 'deleted' in wireguard:
        prev_fwmark = wireguard.get('prev_fwmark')
        prev_vrf = wireguard.get('prev_vrf')
        if prev_fwmark is not None and prev_vrf is not None:
            table_id = get_vrf_tableid(prev_vrf)
            if table_id is not None:
                for afi in ['-4', '-6']:
                    call(
                        f'ip {afi} rule del pref {wireguard_fwmark_pref} fwmark {prev_fwmark} table {table_id}'
                    )

    # Add ip rule to route fwmark-marked WireGuard tunnel packets into the
    # correct VRF routing table. This is required for VRF-bound WireGuard
    # interfaces with fwmark set, so that outgoing encapsulated packets use the
    # proper VRF routes (otherwise, they may be unroutable or use the main table).
    if wireguard.get('fwmark', '0') != '0' and 'vrf' in wireguard:
        table_id = get_vrf_tableid(wireguard['vrf'])
        for afi in ['-4', '-6']:
            call(
                f'ip {afi} rule add pref {wireguard_fwmark_pref} fwmark {wireguard["fwmark"]} table {table_id}'
            )

    domain_resolver_usage = '/run/use-vyos-domain-resolver-interfaces-wireguard-' + wireguard['ifname']

    ## DOMAIN RESOLVER
    domain_action = 'restart'
    if 'peers_need_resolve' in wireguard and len(wireguard['peers_need_resolve']) > 0 and 'disable' not in wireguard:
        from vyos.utils.file import write_file

        text = f'# Automatically generated by interfaces_wireguard.py\nThis file indicates that vyos-domain-resolver service is used by the interfaces_wireguard.\n'
        text += "interfaces:\n" + "".join([f"  - {peer}\n" for peer in wireguard['peers_need_resolve']])
        write_file(domain_resolver_usage, text)
    else:
        if os.path.exists(domain_resolver_usage):
            os.unlink(domain_resolver_usage)
        if not glob('/run/use-vyos-domain-resolver*'):
            domain_action = 'stop'
    call(f'systemctl {domain_action} vyos-domain-resolver.service')

    # run the dependents
    call_dependents()

    return None


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
