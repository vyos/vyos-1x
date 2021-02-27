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
from vyos.ifconfig import TunnelIf
from vyos.template import is_ipv4
from vyos.template import is_ipv6
from vyos.util import cmd
from vyos.util import dict_search
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_tunnel_encapsulation(interface):
    """ Returns the used encapsulation protocol for given interface.
        If interface does not exist, None is returned.
    """
    if not os.path.exists(f'/sys/class/net/{interface}'):
        return None
    from json import loads
    tmp = loads(cmd(f'ip -d -j link show {interface}'))[0]
    return tmp['linkinfo']['info_kind']

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

    if 'encapsulation' not in tunnel:
        error = 'Must configure encapsulation for "{ifname}"!'
        raise ConfigError(error.format(**tunnel))

    verify_mtu_ipv6(tunnel)
    verify_address(tunnel)
    verify_vrf(tunnel)
    verify_tunnel(tunnel)

    if 'source_interface' in tunnel:
        verify_interface_exists(tunnel['source_interface'])

    # TTL != 0 and nopmtudisc are incompatible, parameters and ip use default
    # values, thus the keys are always present.
    if dict_search('parameters.ip.no_pmtu_discovery', tunnel) != None:
        if dict_search('parameters.ip.ttl', tunnel) != '0':
            raise ConfigError('Disabled PMTU requires TTL set to "0"!')
        if tunnel['encapsulation'] in ['ipip6', 'ip6ip6', 'ip6gre']:
            raise ConfigError('Can not disable PMTU discovery for given encapsulation')


def generate(tunnel):
    return None

def apply(tunnel):
    interface = tunnel['ifname']
    # If a gretap tunnel is already existing we can not "simply" change local or
    # remote addresses. This returns "Operation not supported" by the Kernel.
    # There is no other solution to destroy and recreate the tunnel.
    encap = get_tunnel_encapsulation(interface)

    if 'deleted' in tunnel or 'encapsulation_changed' in tunnel or encap == 'gretap':
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
