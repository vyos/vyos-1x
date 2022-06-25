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
import re

from sys import argv
from sys import exit

from vyos.config import Config
from vyos.ifconfig import Section
from vyos.template import render
from vyos.util import cmd
from vyos.util import run
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    ifname = argv[1]
    ifpath = Section.get_config_path(ifname)
    if_policy_path = f'interfaces {ifpath} policy'

    if_policy = conf.get_config_dict(if_policy_path, key_mangling=('-', '_'), get_first_key=True,
                                    no_tag_node_value_mangle=True)

    if_policy['ifname'] = ifname
    if_policy['policy'] = conf.get_config_dict(['policy'], key_mangling=('-', '_'), get_first_key=True,
                                    no_tag_node_value_mangle=True)

    return if_policy

def verify_chain(table, chain):
    # Verify policy route applied
    code = run(f'nft list chain {table} {chain}')
    return code == 0

def verify(if_policy):
    # bail out early - looks like removal from running config
    if not if_policy:
        return None

    for route in ['route', 'route6']:
        if route in if_policy:
            if route not in if_policy['policy']:
                raise ConfigError('Policy route not configured')

            route_name = if_policy[route]

            if route_name not in if_policy['policy'][route]:
                raise ConfigError(f'Invalid policy route name "{name}"')

            nft_prefix = 'VYOS_PBR6_' if route == 'route6' else 'VYOS_PBR_'
            nft_table = 'ip6 mangle' if route == 'route6' else 'ip mangle'

            if not verify_chain(nft_table, nft_prefix + route_name):
                raise ConfigError('Policy route did not apply')

    return None

def generate(if_policy):
    return None

def cleanup_rule(table, chain, ifname, new_name=None):
    results = cmd(f'nft -a list chain {table} {chain}').split("\n")
    retval = None
    for line in results:
        if f'ifname "{ifname}"' in line:
            if new_name and f'jump {new_name}' in line:
                # new_name is used to clear rules for any previously referenced chains
                # returns true when rule exists and doesn't need to be created
                retval = True
                continue

            handle_search = re.search('handle (\d+)', line)
            if handle_search:
                cmd(f'nft delete rule {table} {chain} handle {handle_search[1]}')
    return retval

def apply(if_policy):
    ifname = if_policy['ifname']

    route_chain = 'VYOS_PBR_PREROUTING'
    ipv6_route_chain = 'VYOS_PBR6_PREROUTING'

    if 'route' in if_policy:
        name = 'VYOS_PBR_' + if_policy['route']
        rule_exists = cleanup_rule('ip mangle', route_chain, ifname, name)

        if not rule_exists:
            cmd(f'nft insert rule ip mangle {route_chain} iifname {ifname} counter jump {name}')
    else:
        cleanup_rule('ip mangle', route_chain, ifname)

    if 'route6' in if_policy:
        name = 'VYOS_PBR6_' + if_policy['route6']
        rule_exists = cleanup_rule('ip6 mangle', ipv6_route_chain, ifname, name)

        if not rule_exists:
            cmd(f'nft insert rule ip6 mangle {ipv6_route_chain} iifname {ifname} counter jump {name}')
    else:
        cleanup_rule('ip6 mangle', ipv6_route_chain, ifname)

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
