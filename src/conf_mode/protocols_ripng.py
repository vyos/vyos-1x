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

from sys import exit

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.configverify import verify_common_route_maps
from vyos.configverify import verify_access_list
from vyos.configverify import verify_prefix_list
from vyos.utils.dict import dict_search
from vyos.template import render_to_string
from vyos import ConfigError
from vyos import frr
from vyos import airbag
airbag.enable()

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
    ripng = conf.merge_defaults(ripng, recursive=True)

    # We also need some additional information from the config, prefix-lists
    # and route-maps for instance. They will be used in verify().
    #
    # XXX: one MUST always call this without the key_mangling() option! See
    # vyos.configverify.verify_common_route_maps() for more information.
    tmp = conf.get_config_dict(['policy'])
    # Merge policy dict into "regular" config dict
    ripng = dict_merge(tmp, ripng)

    return ripng

def verify(ripng):
    if not ripng:
        return None

    verify_common_route_maps(ripng)

    acl_in = dict_search('distribute_list.access_list.in', ripng)
    if acl_in: verify_access_list(acl_in, ripng, version='6')

    acl_out = dict_search('distribute_list.access_list.out', ripng)
    if acl_out: verify_access_list(acl_out, ripng, version='6')

    prefix_list_in = dict_search('distribute_list.prefix_list.in', ripng)
    if prefix_list_in: verify_prefix_list(prefix_list_in, ripng, version='6')

    prefix_list_out = dict_search('distribute_list.prefix_list.out', ripng)
    if prefix_list_out: verify_prefix_list(prefix_list_out, ripng, version='6')

    if 'interface' in ripng:
        for interface, interface_options in ripng['interface'].items():
            if 'authentication' in interface_options:
                if {'md5', 'plaintext_password'} <= set(interface_options['authentication']):
                    raise ConfigError('Can not use both md5 and plaintext-password at the same time!')
            if 'split_horizon' in interface_options:
                if {'disable', 'poison_reverse'} <= set(interface_options['split_horizon']):
                    raise ConfigError(f'You can not have "split-horizon poison-reverse" enabled ' \
                                      f'with "split-horizon disable" for "{interface}"!')

def generate(ripng):
    if not ripng:
        ripng['new_frr_config'] = ''
        return None

    ripng['new_frr_config'] = render_to_string('frr/ripngd.frr.j2', ripng)
    return None

def apply(ripng):
    ripng_daemon = 'ripngd'
    zebra_daemon = 'zebra'

    # Save original configuration prior to starting any commit actions
    frr_cfg = frr.FRRConfig()

    # The route-map used for the FIB (zebra) is part of the zebra daemon
    frr_cfg.load_configuration(zebra_daemon)
    frr_cfg.modify_section('^ipv6 protocol ripng route-map [-a-zA-Z0-9.]+', stop_pattern='(\s|!)')
    frr_cfg.commit_configuration(zebra_daemon)

    frr_cfg.load_configuration(ripng_daemon)
    frr_cfg.modify_section('key chain \S+', stop_pattern='^exit', remove_stop_mark=True)
    frr_cfg.modify_section('interface \S+', stop_pattern='^exit', remove_stop_mark=True)
    frr_cfg.modify_section('^router ripng', stop_pattern='^exit', remove_stop_mark=True)
    if 'new_frr_config' in ripng:
        frr_cfg.add_before(frr.default_add_before, ripng['new_frr_config'])
    frr_cfg.commit_configuration(ripng_daemon)

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
