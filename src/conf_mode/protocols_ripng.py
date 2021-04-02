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
from vyos.configverify import verify_route_maps
from vyos.util import call
from vyos.util import dict_search
from vyos.xml import defaults
from vyos.template import render_to_string
from vyos import ConfigError
from vyos import frr
from vyos import airbag
airbag.enable()

frr_daemon = 'ripngd'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['protocols', 'ripng']
    ripng = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)

    # Bail out early if configuration tree does not exist
    if not conf.exists(base):
        return ripng

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_values = defaults(base)
    # merge in remaining default values
    ripng = dict_merge(default_values, ripng)

    # We also need some additional information from the config, prefix-lists
    # and route-maps for instance. They will be used in verify()
    base = ['policy']
    tmp = conf.get_config_dict(base, key_mangling=('-', '_'))
    # Merge policy dict into OSPF dict
    ripng = dict_merge(tmp, ripng)

    return ripng

def verify(ripng):
    if not ripng:
        return None

    acl_in = dict_search('distribute_list.access_list.in', ripng)
    if acl_in and acl_in not in  (dict_search('policy.access_list6', ripng) or []):
        raise ConfigError(f'Inbound access-list6 "{acl_in}" does not exist!')

    acl_out = dict_search('distribute_list.access_list.out', ripng)
    if acl_out and acl_out not in (dict_search('policy.access_list6', ripng) or []):
        raise ConfigError(f'Outbound access-list6 "{acl_out}" does not exist!')

    prefix_list_in = dict_search('distribute_list.prefix_list.in', ripng)
    if prefix_list_in and prefix_list_in.replace('-','_') not in (dict_search('policy.prefix_list6', ripng) or []):
        raise ConfigError(f'Inbound prefix-list6 "{prefix_list_in}" does not exist!')

    prefix_list_out = dict_search('distribute_list.prefix_list.out', ripng)
    if prefix_list_out and prefix_list_out.replace('-','_') not in (dict_search('policy.prefix_list6', ripng) or []):
        raise ConfigError(f'Outbound prefix-list6 "{prefix_list_out}" does not exist!')

    if 'interface' in ripng:
        for interface, interface_options in ripng['interface'].items():
            if 'authentication' in interface_options:
                if {'md5', 'plaintext_password'} <= set(interface_options['authentication']):
                    raise ConfigError('Can not use both md5 and plaintext-password at the same time!')
            if 'split_horizon' in interface_options:
                if {'disable', 'poison_reverse'} <= set(interface_options['split_horizon']):
                    raise ConfigError(f'You can not have "split-horizon poison-reverse" enabled ' \
                                      f'with "split-horizon disable" for "{interface}"!')

    verify_route_maps(ripng)

def generate(ripng):
    if not ripng:
        ripng['new_frr_config'] = ''
        return None

    ripng['new_frr_config'] = render_to_string('frr/ripng.frr.tmpl', ripng)
    return None

def apply(ripng):
    # Save original configuration prior to starting any commit actions
    frr_cfg = frr.FRRConfig()
    frr_cfg.load_configuration(frr_daemon)
    frr_cfg.modify_section(r'key chain \S+', '')
    frr_cfg.modify_section(r'interface \S+', '')
    frr_cfg.modify_section('router ripng', '')
    frr_cfg.add_before(r'(ip prefix-list .*|route-map .*|line vty)', ripng['new_frr_config'])
    frr_cfg.commit_configuration(frr_daemon)

    # If FRR config is blank, rerun the blank commit x times due to frr-reload
    # behavior/bug not properly clearing out on one commit.
    if ripng['new_frr_config'] == '':
        for a in range(5):
            frr_cfg.commit_configuration(frr_daemon)

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
