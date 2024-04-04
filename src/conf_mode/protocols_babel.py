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
from vyos.config import config_dict_merge
from vyos.configdict import dict_merge
from vyos.configdict import node_changed
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
    base = ['protocols', 'babel']
    babel = conf.get_config_dict(base, key_mangling=('-', '_'),
                                 get_first_key=True)

    # FRR has VRF support for different routing daemons. As interfaces belong
    # to VRFs - or the global VRF, we need to check for changed interfaces so
    # that they will be properly rendered for the FRR config. Also this eases
    # removal of interfaces from the running configuration.
    interfaces_removed = node_changed(conf, base + ['interface'])
    if interfaces_removed:
        babel['interface_removed'] = list(interfaces_removed)

    # Bail out early if configuration tree does not exist
    if not conf.exists(base):
        babel.update({'deleted' : ''})
        return babel

    # We have gathered the dict representation of the CLI, but there are default
    # values which we need to update into the dictionary retrieved.
    default_values = conf.get_config_defaults(base, key_mangling=('-', '_'),
                                              get_first_key=True,
                                              recursive=True)

    # merge in default values
    babel = config_dict_merge(default_values, babel)

    # We also need some additional information from the config, prefix-lists
    # and route-maps for instance. They will be used in verify().
    #
    # XXX: one MUST always call this without the key_mangling() option! See
    # vyos.configverify.verify_common_route_maps() for more information.
    tmp = conf.get_config_dict(['policy'])
    # Merge policy dict into "regular" config dict
    babel = dict_merge(tmp, babel)
    return babel

def verify(babel):
    if not babel:
        return None

    # verify distribute_list
    if "distribute_list" in babel:
        acl_keys = {
            "ipv4": [
                "distribute_list.ipv4.access_list.in",
                "distribute_list.ipv4.access_list.out",
            ],
            "ipv6": [
                "distribute_list.ipv6.access_list.in",
                "distribute_list.ipv6.access_list.out",
            ]
        }
        prefix_list_keys = {
            "ipv4": [
                "distribute_list.ipv4.prefix_list.in",
                "distribute_list.ipv4.prefix_list.out",
            ],
            "ipv6":[
                "distribute_list.ipv6.prefix_list.in",
                "distribute_list.ipv6.prefix_list.out",
            ]
        }
        for address_family in ["ipv4", "ipv6"]:
            for iface_key in babel["distribute_list"].get(address_family, {}).get("interface", {}).keys():
                acl_keys[address_family].extend([
                    f"distribute_list.{address_family}.interface.{iface_key}.access_list.in",
                    f"distribute_list.{address_family}.interface.{iface_key}.access_list.out"
                ])
                prefix_list_keys[address_family].extend([
                    f"distribute_list.{address_family}.interface.{iface_key}.prefix_list.in",
                    f"distribute_list.{address_family}.interface.{iface_key}.prefix_list.out"
                ])

        for address_family, keys in acl_keys.items():
            for key in keys:
                acl = dict_search(key, babel)
                if acl:
                    verify_access_list(acl, babel, version='6' if address_family == 'ipv6' else '')

        for address_family, keys in prefix_list_keys.items():
            for key in keys:
                prefix_list = dict_search(key, babel)
                if prefix_list:
                    verify_prefix_list(prefix_list, babel, version='6' if address_family == 'ipv6' else '')


def generate(babel):
    if not babel or 'deleted' in babel:
        return None

    babel['new_frr_config'] = render_to_string('frr/babeld.frr.j2', babel)
    return None

def apply(babel):
    babel_daemon = 'babeld'

    # Save original configuration prior to starting any commit actions
    frr_cfg = frr.FRRConfig()

    frr_cfg.load_configuration(babel_daemon)
    frr_cfg.modify_section('^router babel', stop_pattern='^exit', remove_stop_mark=True)

    for key in ['interface', 'interface_removed']:
        if key not in babel:
            continue
        for interface in babel[key]:
            frr_cfg.modify_section(f'^interface {interface}', stop_pattern='^exit', remove_stop_mark=True)

    if 'new_frr_config' in babel:
        frr_cfg.add_before(frr.default_add_before, babel['new_frr_config'])
    frr_cfg.commit_configuration(babel_daemon)

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
