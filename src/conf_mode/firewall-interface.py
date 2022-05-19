#!/usr/bin/env python3
#
# Copyright (C) 2021-2022 VyOS maintainers and contributors
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

from sys import argv
from sys import exit

from vyos.config import Config
from vyos.configdict import leaf_node_changed
from vyos.ifconfig import Section
from vyos.template import render
from vyos.util import cmd
from vyos.util import dict_search_args
from vyos.util import run
from vyos import ConfigError
from vyos import airbag
airbag.enable()

NAME_PREFIX = 'NAME_'
NAME6_PREFIX = 'NAME6_'

NFT_CHAINS = {
    'in': 'VYOS_FW_FORWARD',
    'out': 'VYOS_FW_FORWARD',
    'local': 'VYOS_FW_LOCAL'
}
NFT6_CHAINS = {
    'in': 'VYOS_FW6_FORWARD',
    'out': 'VYOS_FW6_FORWARD',
    'local': 'VYOS_FW6_LOCAL'
}


def get_vrf(iface):
    """
    Get VRF name by interface name
    If VRF not found return original interface name
    Ex:
        >>> get_vrf('eth0')
        'MGMT'
        >>> get_vrf('eth1')
        'eth1'
        >>>
    """
    from vyos.util import get_interface_config
    if "linkinfo" in get_interface_config(iface):
        kind = get_interface_config(iface).get('linkinfo').get('info_slave_kind')
        if kind == "vrf":
            iface = get_interface_config(iface).get('master')
    return iface

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    ifname = argv[1]
    ifpath = Section.get_config_path(ifname)
    if_firewall_path = f'interfaces {ifpath} firewall'

    if_firewall = conf.get_config_dict(if_firewall_path, key_mangling=('-', '_'), get_first_key=True,
                                    no_tag_node_value_mangle=True)

    # T3933 replace interface name => vrf name
    # Only for forward-in and local directions
    # For deleting also firewall return vrf name
    if not if_firewall:
        ifname = get_vrf(ifname)
    for direction in if_firewall:
        if 'in' in direction or 'local' in direction:
            ifname = get_vrf(ifname)
    if_firewall['ifname'] = ifname
    if_firewall['firewall'] = conf.get_config_dict(['firewall'], key_mangling=('-', '_'), get_first_key=True,
                                    no_tag_node_value_mangle=True)

    return if_firewall

def verify(if_firewall):
    # bail out early - looks like removal from running config
    if not if_firewall:
        return None

    for direction in ['in', 'out', 'local']:
        if direction in if_firewall:
            if 'name' in if_firewall[direction]:
                name = if_firewall[direction]['name']

                if 'name' not in if_firewall['firewall']:
                    raise ConfigError('Firewall name not configured')

                if name not in if_firewall['firewall']['name']:
                    raise ConfigError(f'Invalid firewall name "{name}"')

            if 'ipv6_name' in if_firewall[direction]:
                name = if_firewall[direction]['ipv6_name']

                if 'ipv6_name' not in if_firewall['firewall']:
                    raise ConfigError('Firewall ipv6-name not configured')

                if name not in if_firewall['firewall']['ipv6_name']:
                    raise ConfigError(f'Invalid firewall ipv6-name "{name}"')

    return None

def generate(if_firewall):
    return None

def cleanup_rule(table, chain, prefix, ifname, new_name=None):
    results = cmd(f'nft -a list chain {table} {chain}').split("\n")
    retval = None
    for line in results:
        if f'{prefix}ifname "{ifname}"' in line:
            if new_name and f'jump {new_name}' in line:
                # new_name is used to clear rules for any previously referenced chains
                # returns true when rule exists and doesn't need to be created
                retval = True
                continue

            handle_search = re.search('handle (\d+)', line)
            if handle_search:
                run(f'nft delete rule {table} {chain} handle {handle_search[1]}')
    return retval

def state_policy_handle(table, chain):
    # Find any state-policy rule to ensure interface rules are only inserted afterwards
    results = cmd(f'nft -a list chain {table} {chain}').split("\n")
    for line in results:
        if 'jump VYOS_STATE_POLICY' in line:
            handle_search = re.search('handle (\d+)', line)
            if handle_search:
                return handle_search[1]
    return None

def apply(if_firewall):
    ifname = if_firewall['ifname']

    for direction in ['in', 'out', 'local']:
        chain = NFT_CHAINS[direction]
        ipv6_chain = NFT6_CHAINS[direction]
        if_prefix = 'i' if direction in ['in', 'local'] else 'o'

        name = dict_search_args(if_firewall, direction, 'name')
        if name:
            rule_exists = cleanup_rule('ip filter', chain, if_prefix, ifname, f'{NAME_PREFIX}{name}')

            if not rule_exists:
                rule_action = 'insert'
                rule_prefix = ''

                handle = state_policy_handle('ip filter', chain)
                if handle:
                    rule_action = 'add'
                    rule_prefix = f'position {handle}'

                run(f'nft {rule_action} rule ip filter {chain} {rule_prefix} {if_prefix}ifname {ifname} counter jump {NAME_PREFIX}{name}')
        else:
            cleanup_rule('ip filter', chain, if_prefix, ifname)

        ipv6_name = dict_search_args(if_firewall, direction, 'ipv6_name')
        if ipv6_name:
            rule_exists = cleanup_rule('ip6 filter', ipv6_chain, if_prefix, ifname, f'{NAME6_PREFIX}{ipv6_name}')

            if not rule_exists:
                rule_action = 'insert'
                rule_prefix = ''

                handle = state_policy_handle('ip6 filter', ipv6_chain)
                if handle:
                    rule_action = 'add'
                    rule_prefix = f'position {handle}'

                run(f'nft {rule_action} rule ip6 filter {ipv6_chain} {rule_prefix} {if_prefix}ifname {ifname} counter jump {NAME6_PREFIX}{ipv6_name}')
        else:
            cleanup_rule('ip6 filter', ipv6_chain, if_prefix, ifname)

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
