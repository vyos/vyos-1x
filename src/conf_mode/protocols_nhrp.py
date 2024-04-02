#!/usr/bin/env python3
#
# Copyright (C) 2021-2024 VyOS maintainers and contributors
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

from vyos.config import Config
from vyos.configdict import node_changed
from vyos.template import render
from vyos.utils.process import run
from vyos import ConfigError
from vyos import airbag
airbag.enable()

opennhrp_conf = '/run/opennhrp/opennhrp.conf'
nhrp_nftables_conf = '/run/nftables_nhrp.conf'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['protocols', 'nhrp']

    nhrp = conf.get_config_dict(base, key_mangling=('-', '_'),
                                get_first_key=True, no_tag_node_value_mangle=True)
    nhrp['del_tunnels'] = node_changed(conf, base + ['tunnel'])

    if not conf.exists(base):
        return nhrp

    nhrp['if_tunnel'] = conf.get_config_dict(['interfaces', 'tunnel'], key_mangling=('-', '_'),
                                get_first_key=True, no_tag_node_value_mangle=True)

    nhrp['profile_map'] = {}
    profile = conf.get_config_dict(['vpn', 'ipsec', 'profile'], key_mangling=('-', '_'),
                                get_first_key=True, no_tag_node_value_mangle=True)

    for name, profile_conf in profile.items():
        if 'bind' in profile_conf and 'tunnel' in profile_conf['bind']:
            interfaces = profile_conf['bind']['tunnel']
            if isinstance(interfaces, str):
                interfaces = [interfaces]
            for interface in interfaces:
                nhrp['profile_map'][interface] = name

    return nhrp

def verify(nhrp):
    if 'tunnel' in nhrp:
        for name, nhrp_conf in nhrp['tunnel'].items():
            if not nhrp['if_tunnel'] or name not in nhrp['if_tunnel']:
                raise ConfigError(f'Tunnel interface "{name}" does not exist')

            tunnel_conf = nhrp['if_tunnel'][name]

            if 'encapsulation' not in tunnel_conf or tunnel_conf['encapsulation'] != 'gre':
                raise ConfigError(f'Tunnel "{name}" is not an mGRE tunnel')

            if 'remote' in tunnel_conf:
                raise ConfigError(f'Tunnel "{name}" cannot have a remote address defined')

            if 'map' in nhrp_conf:
                for map_name, map_conf in nhrp_conf['map'].items():
                    if 'nbma_address' not in map_conf:
                        raise ConfigError(f'nbma-address missing on map {map_name} on tunnel {name}')

            if 'dynamic_map' in nhrp_conf:
                for map_name, map_conf in nhrp_conf['dynamic_map'].items():
                    if 'nbma_domain_name' not in map_conf:
                        raise ConfigError(f'nbma-domain-name missing on dynamic-map {map_name} on tunnel {name}')
    return None

def generate(nhrp):
    if not os.path.exists(nhrp_nftables_conf):
        nhrp['first_install'] = True

    render(opennhrp_conf, 'nhrp/opennhrp.conf.j2', nhrp)
    render(nhrp_nftables_conf, 'nhrp/nftables.conf.j2', nhrp)
    return None

def apply(nhrp):
    nft_rc = run(f'nft --file {nhrp_nftables_conf}')
    if nft_rc != 0:
        raise ConfigError('Failed to apply NHRP tunnel firewall rules')

    action = 'restart' if nhrp and 'tunnel' in nhrp else 'stop'
    service_rc = run(f'systemctl {action} opennhrp.service')
    if service_rc != 0:
        raise ConfigError(f'Failed to {action} the NHRP service')

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
