#!/usr/bin/env python3
#
# Copyright (C) 2018-2021 VyOS maintainers and contributors
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
from ipaddress import IPv4Address

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.configdict import get_interface_dict
from vyos.configdict import node_changed
from vyos.configdict import leaf_node_changed
from vyos.configverify import verify_address
from vyos.configverify import verify_bridge_delete
from vyos.configverify import verify_interface_exists
from vyos.configverify import verify_mtu_ipv6
from vyos.configverify import verify_vrf
from vyos.configverify import verify_tunnel
from vyos.ifconfig import Interface
from vyos.ifconfig import Section
from vyos.ifconfig import TunnelIf
from vyos.template import is_ipv4
from vyos.template import is_ipv6
from vyos.util import get_interface_config
from vyos.util import dict_search
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
    base = ['interfaces', 'tunnel']
    tunnel = get_interface_dict(conf, base)

    tmp = leaf_node_changed(conf, ['encapsulation'])
    if tmp: tunnel.update({'encapsulation_changed': {}})

    # We must check if our interface is configured to be a DMVPN member
    nhrp_base = ['protocols', 'nhrp', 'tunnel']
    conf.set_level(nhrp_base)
    nhrp = conf.get_config_dict([], key_mangling=('-', '_'), get_first_key=True)
    if nhrp: tunnel.update({'nhrp' : list(nhrp.keys())})

    return tunnel

def verify(tunnel):
    if 'deleted' in tunnel:
        verify_bridge_delete(tunnel)

        if 'nhrp' in tunnel and tunnel['ifname'] in tunnel['nhrp']:
            raise ConfigError('Tunnel used for NHRP, it can not be deleted!')

        return None

    verify_tunnel(tunnel)

    # If tunnel source address any and key not set
    if tunnel['encapsulation'] in ['gre'] and \
       dict_search('source_address', tunnel) == '0.0.0.0' and \
       dict_search('parameters.ip.key', tunnel) == None:
        raise ConfigError('Tunnel parameters ip key must be set!')

    if tunnel['encapsulation'] in ['gre', 'gretap']:
        if dict_search('parameters.ip.key', tunnel) != None:
            # Check pairs tunnel source-address/encapsulation/key with exists tunnels.
            # Prevent the same key for 2 tunnels with same source-address/encap. T2920
            for tunnel_if in Section.interfaces('tunnel'):
                # It makes no sense to run the test for re-used GRE keys on our
                # own interface we are currently working on
                if tunnel['ifname'] == tunnel_if:
                    continue
                tunnel_cfg = get_interface_config(tunnel_if)
                # no match on encapsulation - bail out
                if dict_search('linkinfo.info_kind', tunnel_cfg) != tunnel['encapsulation']:
                    continue
                new_source_address = dict_search('source_address', tunnel)
                # Convert tunnel key to ip key, format "ip -j link show"
                # 1 => 0.0.0.1, 999 => 0.0.3.231
                orig_new_key = dict_search('parameters.ip.key', tunnel)
                new_key = IPv4Address(int(orig_new_key))
                new_key = str(new_key)
                if dict_search('address', tunnel_cfg) == new_source_address and \
                   dict_search('linkinfo.info_data.ikey', tunnel_cfg) == new_key:
                    raise ConfigError(f'Key "{orig_new_key}" for source-address "{new_source_address}" ' \
                                      f'is already used for tunnel "{tunnel_if}"!')

    # Keys are not allowed with ipip and sit tunnels
    if tunnel['encapsulation'] in ['ipip', 'sit']:
        if dict_search('parameters.ip.key', tunnel) != None:
            raise ConfigError('Keys are not allowed with ipip and sit tunnels!')

    verify_mtu_ipv6(tunnel)
    verify_address(tunnel)
    verify_vrf(tunnel)

    if 'source_interface' in tunnel:
        verify_interface_exists(tunnel['source_interface'])

    # TTL != 0 and nopmtudisc are incompatible, parameters and ip use default
    # values, thus the keys are always present.
    if dict_search('parameters.ip.no_pmtu_discovery', tunnel) != None:
        if dict_search('parameters.ip.ttl', tunnel) != '0':
            raise ConfigError('Disabled PMTU requires TTL set to "0"!')
        if tunnel['encapsulation'] in ['ipip6', 'ip6ip6', 'ip6gre']:
            raise ConfigError('Can not disable PMTU discovery for given encapsulation')

    if dict_search('parameters.ip.ignore_df', tunnel) != None:
        if tunnel['encapsulation'] not in ['gretap']:
            raise ConfigError('Option ignore-df can only be used on GRETAP tunnels!')

        if dict_search('parameters.ip.no_pmtu_discovery', tunnel) == None:
            raise ConfigError('Option ignore-df requires path MTU discovery to be disabled!')


def generate(tunnel):
    return None

def apply(tunnel):
    interface = tunnel['ifname']
    # If a gretap tunnel is already existing we can not "simply" change local or
    # remote addresses. This returns "Operation not supported" by the Kernel.
    # There is no other solution to destroy and recreate the tunnel.
    encap = ''
    remote = ''
    tmp = get_interface_config(interface)
    if tmp:
        encap = dict_search('linkinfo.info_kind', tmp)
        remote = dict_search('linkinfo.info_data.remote', tmp)

    if ('deleted' in tunnel or 'encapsulation_changed' in tunnel or encap in
        ['gretap', 'ip6gretap'] or remote in ['any']):
        if interface in interfaces():
            tmp = Interface(interface)
            tmp.remove()
        if 'deleted' in tunnel:
            return None

    tun = TunnelIf(**tunnel)
    tun.update(tunnel)

    return None

if __name__ == '__main__':
    try:
        c = get_config()
        generate(c)
        verify(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
