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
from copy import deepcopy

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.configdict import get_interface_dict
from vyos.configdict import node_changed
from vyos.configdict import leaf_node_changed
from vyos.configverify import verify_vrf
from vyos.configverify import verify_address
from vyos.configverify import verify_bridge_delete
from vyos.configverify import verify_mtu_ipv6
from vyos.ifconfig import Interface
from vyos.ifconfig import GREIf
from vyos.ifconfig import GRETapIf
from vyos.ifconfig import IPIPIf
from vyos.ifconfig import IP6GREIf
from vyos.ifconfig import IPIP6If
from vyos.ifconfig import IP6IP6If
from vyos.ifconfig import SitIf
from vyos.ifconfig import Sit6RDIf
from vyos.template import is_ipv4
from vyos.template import is_ipv6
from vyos.util import dict_search
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
    base = ['interfaces', 'tunnel']
    tunnel = get_interface_dict(conf, base)

    # Wireguard is "special" the default MTU is 1420 - update accordingly
    # as the config_level is already st in get_interface_dict() - we can use []
    tmp = conf.get_config_dict([], key_mangling=('-', '_'), get_first_key=True)
    if 'mtu' not in tmp:
        tunnel['mtu'] = '1476'

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

    if 'encapsulation' not in tunnel:
        raise ConfigError('Must configure the tunnel encapsulation for '\
                          '{ifname}!'.format(**tunnel))

    verify_mtu_ipv6(tunnel)
    verify_address(tunnel)
    verify_vrf(tunnel)

    if 'local_ip' not in tunnel and 'dhcp_interface' not in tunnel:
        raise ConfigError('local-ip is mandatory for tunnel')

    if 'remote_ip' not in tunnel and tunnel['encapsulation'] != 'gre':
        raise ConfigError('remote-ip is mandatory for tunnel')

    if {'local_ip', 'dhcp_interface'} <= set(tunnel):
        raise ConfigError('Can not use both local-ip and dhcp-interface')

    if tunnel['encapsulation'] in ['ipip6', 'ip6ip6', 'ip6gre']:
        error_ipv6 = 'Encapsulation mode requires IPv6'
        if 'local_ip' in tunnel and not is_ipv6(tunnel['local_ip']):
            raise ConfigError(f'{error_ipv6} local-ip')

        if 'remote_ip' in tunnel and not is_ipv6(tunnel['remote_ip']):
            raise ConfigError(f'{error_ipv6} remote-ip')
    else:
        error_ipv4 = 'Encapsulation mode requires IPv4'
        if 'local_ip' in tunnel and not is_ipv4(tunnel['local_ip']):
            raise ConfigError(f'{error_ipv4} local-ip')

        if 'remote_ip' in tunnel and not is_ipv4(tunnel['remote_ip']):
            raise ConfigError(f'{error_ipv4} remote-ip')

    if tunnel['encapsulation'] in ['sit', 'gre-bridge']:
        if 'source_interface' in tunnel:
            raise ConfigError('Option source-interface can not be used with ' \
                              'encapsulation "sit" or "gre-bridge"')
    elif tunnel['encapsulation'] == 'gre':
        if is_ipv6(tunnel['local_ip']):
            raise ConfigError('Can not use local IPv6 address is for mGRE tunnels')

def generate(tunnel):
    return None

def apply(tunnel):
    if 'deleted' in tunnel:
        tmp = Interface(tunnel['ifname'])
        tmp.remove()
        return None

    dispatch = {
        'gre': GREIf,
        'gre-bridge': GRETapIf,
        'ipip': IPIPIf,
        'ipip6': IPIP6If,
        'ip6ip6': IP6IP6If,
        'ip6gre': IP6GREIf,
        'sit': SitIf,
    }

    # We need to re-map the tunnel encapsulation proto to a valid interface class
    encap = tunnel['encapsulation']
    klass = dispatch[encap]

    # This is a special type of interface which needs additional parameters
    # when created using iproute2. Instead of passing a ton of arguments,
    # use a dictionary provided by the interface class which holds all the
    # options necessary.
    conf = klass.get_config()

    # Copy/re-assign our dictionary values to values understood by the
    # derived _Tunnel classes
    mapping = {
        # this                       :  get_config()
        'local_ip'                   : 'local',
        'remote_ip'                  : 'remote',
        'source_interface'           : 'dev',
        'parameters.ip.ttl'          : 'ttl',
        'parameters.ip.tos'          : 'tos',
        'parameters.ip.key'          : 'key',
        'parameters.ipv6.encaplimit' : 'encaplimit'
    }

    # Add additional IPv6 options if tunnel is IPv6 aware
    if tunnel['encapsulation'] in ['ipip6', 'ip6ip6', 'ip6gre']:
        mappingv6 = {
            # this                       :  get_config()
            'parameters.ipv6.encaplimit' : 'encaplimit'
        }
        mapping.update(mappingv6)

    for our_key, their_key in mapping.items():
        if dict_search(our_key, tunnel) and their_key in conf:
            conf[their_key] = dict_search(our_key, tunnel)

    # TODO: support encapsulation change per tunnel

    tun = klass(tunnel['ifname'], **conf)
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
