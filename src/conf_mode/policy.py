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

from sys import exit

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.template import render_to_string
from vyos.util import dict_search
from vyos import ConfigError
from vyos import frr
from vyos import airbag
airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['policy']
    policy = conf.get_config_dict(base, key_mangling=('-', '_'),
                                  no_tag_node_value_mangle=True)
    return policy

def verify(policy):
    if not policy:
        return None

    if 'access-list' in policy:
        for acl, acl_config in policy['access-list'].items():
            if 'rule' not in acl_config:
                continue

            for rule, rule_config in acl_config['rule'].items():
                if 'source' not in rule_config:
                    raise ConfigError(f'Source must be specified for rule {rule} '\
                                      f'for access-list {acl}!')
                if 'action' not in rule_config:
                    raise ConfigError(f'Action must be specified for rule {rule} '\
                                      f'for access-list {acl}!')

                if int(acl) not in range(100, 200) or int(acl) not in range(2000, 2700):
                    if 'destination' not in rule_config:
                        raise ConfigError(f'Destination must be specified for rule {rule} '\
                                          f'for access-list {acl}!')

    return None

def generate(policy):
    if not policy:
        policy['new_frr_config'] = ''
        return None

    policy['new_frr_config'] = render_to_string('frr/policy.frr.tmpl', policy)
    return None

def apply(policy):
    bgp_daemon = 'bgpd'
    zebra_daemon = 'zebra'

    # Save original configuration prior to starting any commit actions
    frr_cfg = frr.FRRConfig()

    # The route-map used for the FIB (zebra) is part of the zebra daemon
    frr_cfg.load_configuration(bgp_daemon)
    frr_cfg.modify_section(r'^bgp as-path access-list .*')
    frr_cfg.modify_section(r'^bgp community-list .*')
    frr_cfg.modify_section(r'^bgp extcommunity-list .*')
    frr_cfg.modify_section(r'^bgp large-community-list .*')
    frr_cfg.add_before('^line vty', policy['new_frr_config'])
    frr_cfg.commit_configuration(bgp_daemon)

    # The route-map used for the FIB (zebra) is part of the zebra daemon
    frr_cfg.load_configuration(zebra_daemon)
    frr_cfg.modify_section(r'^access-list .*')
    frr_cfg.modify_section(r'^ipv6 access-list .*')
    frr_cfg.modify_section(r'^ip prefix-list .*')
    frr_cfg.modify_section(r'^ipv6 prefix-list .*')
    frr_cfg.add_before('^line vty', policy['new_frr_config'])
    frr_cfg.commit_configuration(zebra_daemon)

    # If FRR config is blank, rerun the blank commit x times due to frr-reload
    # behavior/bug not properly clearing out on one commit.
    if policy['new_frr_config'] == '':
        for a in range(5):
            frr_cfg.commit_configuration(zebra_daemon)

    # Save configuration to /run/frr/config/frr.conf
    frr.save_configuration()

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
