#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
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

from json import loads
from sys import exit

from vyos.config import Config
from vyos.template import render
from vyos.util import cmd
from vyos.util import dict_search_args
from vyos.util import run
from vyos import ConfigError
from vyos import airbag
airbag.enable()

nftables_conf = '/run/nftables_zone.conf'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['zone-policy']
    zone_policy = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True,
                                    no_tag_node_value_mangle=True)

    if zone_policy:
        zone_policy['firewall'] = conf.get_config_dict(['firewall'], key_mangling=('-', '_'), get_first_key=True,
                                    no_tag_node_value_mangle=True)

    return zone_policy

def verify(zone_policy):
    # bail out early - looks like removal from running config
    if not zone_policy:
        return None

    local_zone = False
    interfaces = []

    if 'zone' in zone_policy:
        for zone, zone_conf in zone_policy['zone'].items():
            if 'local_zone' not in zone_conf and 'interface' not in zone_conf:
                raise ConfigError(f'Zone "{zone}" has no interfaces and is not the local zone')

            if 'local_zone' in zone_conf:
                if local_zone:
                    raise ConfigError('There cannot be multiple local zones')
                if 'interface' in zone_conf:
                    raise ConfigError('Local zone cannot have interfaces assigned')
                if 'intra_zone_filtering' in zone_conf:
                    raise ConfigError('Local zone cannot use intra-zone-filtering')
                local_zone = True

            if 'interface' in zone_conf:
                found_duplicates = [intf for intf in zone_conf['interface'] if intf in interfaces]

                if found_duplicates:
                    raise ConfigError(f'Interfaces cannot be assigned to multiple zones')

                interfaces += zone_conf['interface']

            if 'intra_zone_filtering' in zone_conf:
                intra_zone = zone_conf['intra_zone_filtering']

                if len(intra_zone) > 1:
                    raise ConfigError('Only one intra-zone-filtering action must be specified')

                if 'firewall' in intra_zone:
                    v4_name = dict_search_args(intra_zone, 'firewall', 'name')
                    if v4_name and not dict_search_args(zone_policy, 'firewall', 'name', v4_name):
                        raise ConfigError(f'Firewall name "{v4_name}" does not exist')

                    v6_name = dict_search_args(intra_zone, 'firewall', 'ipv6-name')
                    if v6_name and not dict_search_args(zone_policy, 'firewall', 'ipv6-name', v6_name):
                        raise ConfigError(f'Firewall ipv6-name "{v6_name}" does not exist')

                    if not v4_name and not v6_name:
                        raise ConfigError('No firewall names specified for intra-zone-filtering')

            if 'from' in zone_conf:
                for from_zone, from_conf in zone_conf['from'].items():
                    v4_name = dict_search_args(from_conf, 'firewall', 'name')
                    if v4_name:
                        if 'name' not in zone_policy['firewall']:
                            raise ConfigError(f'Firewall name "{v4_name}" does not exist')

                        if not dict_search_args(zone_policy, 'firewall', 'name', v4_name):
                            raise ConfigError(f'Firewall name "{v4_name}" does not exist')

                    v6_name = dict_search_args(from_conf, 'firewall', 'v6_name')
                    if v6_name:
                        if 'ipv6_name' not in zone_policy['firewall']:
                            raise ConfigError(f'Firewall ipv6-name "{v6_name}" does not exist')

                        if not dict_search_args(zone_policy, 'firewall', 'ipv6_name', v6_name):
                            raise ConfigError(f'Firewall ipv6-name "{v6_name}" does not exist')

    return None

def has_ipv4_fw(zone_conf):
    if 'from' not in zone_conf:
        return False
    zone_from = zone_conf['from']
    return any([True for fz in zone_from if dict_search_args(zone_from, fz, 'firewall', 'name')])

def has_ipv6_fw(zone_conf):
    if 'from' not in zone_conf:
        return False
    zone_from = zone_conf['from']
    return any([True for fz in zone_from if dict_search_args(zone_from, fz, 'firewall', 'ipv6_name')])

def get_local_from(zone_policy, local_zone_name):
    # Get all zone firewall names from the local zone
    out = {}
    for zone, zone_conf in zone_policy['zone'].items():
        if zone == local_zone_name:
            continue
        if 'from' not in zone_conf:
            continue
        if local_zone_name in zone_conf['from']:
            out[zone] = zone_conf['from'][local_zone_name]
    return out

def cleanup_commands():
    commands = []
    for table in ['ip filter', 'ip6 filter']:
        json_str = cmd(f'nft -j list table {table}')
        obj = loads(json_str)
        if 'nftables' not in obj:
            continue
        for item in obj['nftables']:
            if 'rule' in item:
                chain = item['rule']['chain']
                handle = item['rule']['handle']
                if 'expr' not in item['rule']:
                    continue
                for expr in item['rule']['expr']:
                    target = dict_search_args(expr, 'jump', 'target')
                    if target and target.startswith("VZONE"):
                        commands.append(f'delete rule {table} {chain} handle {handle}')
        for item in obj['nftables']:
            if 'chain' in item:
                if item['chain']['name'].startswith("VZONE"):
                    chain = item['chain']['name']
                    commands.append(f'delete chain {table} {chain}')
    return commands

def generate(zone_policy):
    data = zone_policy or {}

    if os.path.exists(nftables_conf): # Check to see if we've run before
        data['cleanup_commands'] = cleanup_commands()

    if 'zone' in data:
        for zone, zone_conf in data['zone'].items():
            zone_conf['ipv4'] = has_ipv4_fw(zone_conf)
            zone_conf['ipv6'] = has_ipv6_fw(zone_conf)

            if 'local_zone' in zone_conf:
                zone_conf['from_local'] = get_local_from(data, zone)

    render(nftables_conf, 'zone_policy/nftables.tmpl', data)
    return None

def apply(zone_policy):
    install_result = run(f'nft -f {nftables_conf}')
    if install_result == 1:
        raise ConfigError('Failed to apply zone-policy')

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
