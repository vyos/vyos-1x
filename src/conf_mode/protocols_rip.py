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
from vyos.configdict import node_changed
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
    base = ['protocols', 'rip']
    rip = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)

    # FRR has VRF support for different routing daemons. As interfaces belong
    # to VRFs - or the global VRF, we need to check for changed interfaces so
    # that they will be properly rendered for the FRR config. Also this eases
    # removal of interfaces from the running configuration.
    interfaces_removed = node_changed(conf, base + ['interface'])
    if interfaces_removed:
        rip['interface_removed'] = list(interfaces_removed)

    # Bail out early if configuration tree does not exist
    if not conf.exists(base):
        rip.update({'deleted' : ''})
        return rip

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    rip = conf.merge_defaults(rip, recursive=True)

    # We also need some additional information from the config, prefix-lists
    # and route-maps for instance. They will be used in verify().
    #
    # XXX: one MUST always call this without the key_mangling() option! See
    # vyos.configverify.verify_common_route_maps() for more information.
    tmp = conf.get_config_dict(['policy'])
    # Merge policy dict into "regular" config dict
    rip = dict_merge(tmp, rip)

    return rip

def verify(rip):
    if not rip:
        return None

    verify_common_route_maps(rip)

    acl_in = dict_search('distribute_list.access_list.in', rip)
    if acl_in: verify_access_list(acl_in, rip)

    acl_out = dict_search('distribute_list.access_list.out', rip)
    if acl_out: verify_access_list(acl_out, rip)

    prefix_list_in = dict_search('distribute_list.prefix-list.in', rip)
    if prefix_list_in: verify_prefix_list(prefix_list_in, rip)

    prefix_list_out = dict_search('distribute_list.prefix_list.out', rip)
    if prefix_list_out: verify_prefix_list(prefix_list_out, rip)

    if 'interface' in rip:
        for interface, interface_options in rip['interface'].items():
            if 'authentication' in interface_options:
                if {'md5', 'plaintext_password'} <= set(interface_options['authentication']):
                    raise ConfigError('Can not use both md5 and plaintext-password at the same time!')
            if 'split_horizon' in interface_options:
                if {'disable', 'poison_reverse'} <= set(interface_options['split_horizon']):
                    raise ConfigError(f'You can not have "split-horizon poison-reverse" enabled ' \
                                      f'with "split-horizon disable" for "{interface}"!')

def generate(rip):
    if not rip or 'deleted' in rip:
        return None

    rip['new_frr_config'] = render_to_string('frr/ripd.frr.j2', rip)
    return None

def apply(rip):
    rip_daemon = 'ripd'
    zebra_daemon = 'zebra'

    # Save original configuration prior to starting any commit actions
    frr_cfg = frr.FRRConfig()

    # The route-map used for the FIB (zebra) is part of the zebra daemon
    frr_cfg.load_configuration(zebra_daemon)
    frr_cfg.modify_section('^ip protocol rip route-map [-a-zA-Z0-9.]+', stop_pattern='(\s|!)')
    frr_cfg.commit_configuration(zebra_daemon)

    frr_cfg.load_configuration(rip_daemon)
    frr_cfg.modify_section('^key chain \S+', stop_pattern='^exit', remove_stop_mark=True)
    frr_cfg.modify_section('^router rip', stop_pattern='^exit', remove_stop_mark=True)

    for key in ['interface', 'interface_removed']:
        if key not in rip:
            continue
        for interface in rip[key]:
            frr_cfg.modify_section(f'^interface {interface}', stop_pattern='^exit', remove_stop_mark=True)

    if 'new_frr_config' in rip:
        frr_cfg.add_before(frr.default_add_before, rip['new_frr_config'])
    frr_cfg.commit_configuration(rip_daemon)

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
