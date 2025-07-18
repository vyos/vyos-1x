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

from sys import exit
from sys import argv

import ipaddress
from vyos.config import Config
from vyos.template import render
from vyos.configverify import has_frr_protocol_in_dict
from vyos.utils.process import run
from vyos.utils.dict import dict_search
from vyos import ConfigError
from vyos import airbag
from vyos.frrender import FRRender
from vyos.frrender import get_frrender_dict
from vyos.utils.process import is_systemd_service_running

airbag.enable()

nflog_redirect = 1
nflog_multicast = 2
nhrp_nftables_conf = '/run/nftables_nhrp.conf'


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    return get_frrender_dict(conf, argv)


def verify(config_dict):
    if not config_dict or 'deleted' in config_dict:
        return None
    if 'tunnel' in config_dict:
        for name, nhrp_conf in config_dict['tunnel'].items():
            if not config_dict['if_tunnel'] or name not in config_dict['if_tunnel']:
                raise ConfigError(f'Tunnel interface "{name}" does not exist')

            tunnel_conf = config_dict['if_tunnel'][name]
            if 'address' in tunnel_conf:
                address_list = dict_search('address', tunnel_conf)
                for tunip in address_list:
                    if ipaddress.ip_network(tunip,
                                            strict=False).prefixlen != 32:
                        raise ConfigError(
                            f'Tunnel {name} is used for NHRP, Netmask should be /32!')

            if 'encapsulation' not in tunnel_conf or tunnel_conf['encapsulation'] != 'gre':
                raise ConfigError(f'Tunnel "{name}" is not an mGRE tunnel')

            if 'network_id' not in nhrp_conf:
                raise ConfigError(f'network-id is not specified in tunnel "{name}"')

            if 'remote' in tunnel_conf:
                raise ConfigError(f'Tunnel "{name}" cannot have a remote address defined')

            map_tunnelip = dict_search('map.tunnel_ip', nhrp_conf)
            if map_tunnelip:
                for map_name, map_conf in map_tunnelip.items():
                    if 'nbma' not in map_conf:
                        raise ConfigError(f'nbma-address missing on map {map_name} on tunnel {name}')

            nhs_tunnelip = dict_search('nhs.tunnel_ip', nhrp_conf)
            nbma_list = []
            if nhs_tunnelip:
                for nhs_name, nhs_conf in nhs_tunnelip.items():
                    if 'nbma' not in nhs_conf:
                        raise ConfigError(f'nbma-address missing on map nhs {nhs_name} on tunnel {name}')
                    if nhs_name != 'dynamic':
                        if len(list(dict_search('nbma', nhs_conf))) > 1:
                            raise ConfigError(
                                f'Static nhs tunnel-ip {nhs_name} cannot contain multiple nbma-addresses')
                    for nbma_ip in dict_search('nbma', nhs_conf):
                        if nbma_ip not in nbma_list:
                            nbma_list.append(nbma_ip)
                        else:
                            raise ConfigError(
                                f'Nbma address {nbma_ip} cannot be maped to several tunnel-ip')
    return None


def generate(config_dict):
    if not has_frr_protocol_in_dict(config_dict, 'nhrp'):
        return None

    if 'deleted' in config_dict['nhrp']:
        return None
    render(nhrp_nftables_conf, 'frr/nhrpd_nftables.conf.j2', config_dict['nhrp'])

    if config_dict and not is_systemd_service_running('vyos-configd.service'):
        FRRender().generate(config_dict)
    return None


def apply(config_dict):

    nft_rc = run(f'nft --file {nhrp_nftables_conf}')
    if nft_rc != 0:
        raise ConfigError('Failed to apply NHRP tunnel firewall rules')

    if config_dict and not is_systemd_service_running('vyos-configd.service'):
        FRRender().apply()
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

