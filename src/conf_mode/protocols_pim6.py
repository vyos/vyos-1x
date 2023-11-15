#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
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

from ipaddress import IPv6Address
from ipaddress import IPv6Network
from sys import exit

from vyos.config import Config
from vyos.config import config_dict_merge
from vyos.configdict import node_changed
from vyos.configverify import verify_interface_exists
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
    base = ['protocols', 'pim6']
    pim6 = conf.get_config_dict(base, key_mangling=('-', '_'),
                                 get_first_key=True, with_recursive_defaults=True)

    # FRR has VRF support for different routing daemons. As interfaces belong
    # to VRFs - or the global VRF, we need to check for changed interfaces so
    # that they will be properly rendered for the FRR config. Also this eases
    # removal of interfaces from the running configuration.
    interfaces_removed = node_changed(conf, base + ['interface'])
    if interfaces_removed:
        pim6['interface_removed'] = list(interfaces_removed)

    # Bail out early if configuration tree does no longer exist. this must
    # be done after retrieving the list of interfaces to be removed.
    if not conf.exists(base):
        pim6.update({'deleted' : ''})
        return pim6

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_values = conf.get_config_defaults(**pim6.kwargs, recursive=True)

    pim6 = config_dict_merge(default_values, pim6)
    return pim6

def verify(pim6):
    if not pim6 or 'deleted' in pim6:
        return

    for interface, interface_config in pim6.get('interface', {}).items():
        verify_interface_exists(interface)
        if 'mld' in interface_config:
            mld = interface_config['mld']
            for group in mld.get('join', {}).keys():
                # Validate multicast group address
                if not IPv6Address(group).is_multicast:
                    raise ConfigError(f"{group} is not a multicast group")

    if 'rp' in pim6:
        if 'address' not in pim6['rp']:
            raise ConfigError('PIM6 rendezvous point needs to be defined!')

        # Check unique multicast groups
        unique = []
        pim_base_error = 'PIM6 rendezvous point group'

        if {'address', 'prefix-list6'} <= set(pim6['rp']):
            raise ConfigError(f'{pim_base_error} supports either address or a prefix-list!')

        for address, address_config in pim6['rp']['address'].items():
            if 'group' not in address_config:
                raise ConfigError(f'{pim_base_error} should be defined for "{address}"!')

            # Check if it is a multicast group
            for gr_addr in address_config['group']:
                if not IPv6Network(gr_addr).is_multicast:
                    raise ConfigError(f'{pim_base_error} "{gr_addr}" is not a multicast group!')
                if gr_addr in unique:
                    raise ConfigError(f'{pim_base_error} must be unique!')
                unique.append(gr_addr)

def generate(pim6):
    if not pim6 or 'deleted' in pim6:
        return
    pim6['new_frr_config'] = render_to_string('frr/pim6d.frr.j2', pim6)
    return None

def apply(pim6):
    if pim6 is None:
        return

    pim6_daemon = 'pim6d'

    # Save original configuration prior to starting any commit actions
    frr_cfg = frr.FRRConfig()

    frr_cfg.load_configuration(pim6_daemon)

    for key in ['interface', 'interface_removed']:
        if key not in pim6:
            continue
        for interface in pim6[key]:
            frr_cfg.modify_section(f'^interface {interface}', stop_pattern='^exit', remove_stop_mark=True)

    if 'new_frr_config' in pim6:
        frr_cfg.add_before(frr.default_add_before, pim6['new_frr_config'])
    frr_cfg.commit_configuration(pim6_daemon)
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
