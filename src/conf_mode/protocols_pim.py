#!/usr/bin/env python3
#
# Copyright (C) 2020-2024 VyOS maintainers and contributors
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

from ipaddress import IPv4Address
from ipaddress import IPv4Network
from signal import SIGTERM
from sys import exit

from vyos.config import Config
from vyos.config import config_dict_merge
from vyos.configdict import node_changed
from vyos.configverify import verify_interface_exists
from vyos.utils.process import process_named_running
from vyos.utils.process import call
from vyos.template import render_to_string
from vyos import ConfigError
from vyos import frr
from vyos import airbag
airbag.enable()

RESERVED_MC_NET = '224.0.0.0/24'


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['protocols', 'pim']

    pim = conf.get_config_dict(base, key_mangling=('-', '_'),
                               get_first_key=True, no_tag_node_value_mangle=True)

    # We can not run both IGMP proxy and PIM at the same time - get IGMP
    # proxy status
    if conf.exists(['protocols', 'igmp-proxy']):
        pim.update({'igmp_proxy_enabled' : {}})

    # FRR has VRF support for different routing daemons. As interfaces belong
    # to VRFs - or the global VRF, we need to check for changed interfaces so
    # that they will be properly rendered for the FRR config. Also this eases
    # removal of interfaces from the running configuration.
    interfaces_removed = node_changed(conf, base + ['interface'])
    if interfaces_removed:
        pim['interface_removed'] = list(interfaces_removed)

    # Bail out early if configuration tree does no longer exist. this must
    # be done after retrieving the list of interfaces to be removed.
    if not conf.exists(base):
        pim.update({'deleted' : ''})
        return pim

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_values = conf.get_config_defaults(**pim.kwargs, recursive=True)

    # We have to cleanup the default dict, as default values could enable features
    # which are not explicitly enabled on the CLI. Example: default-information
    # originate comes with a default metric-type of 2, which will enable the
    # entire default-information originate tree, even when not set via CLI so we
    # need to check this first and probably drop that key.
    for interface in pim.get('interface', []):
        # We need to reload the defaults on every pass b/c of
        # hello-multiplier dependency on dead-interval
        # If hello-multiplier is set, we need to remove the default from
        # dead-interval.
        if 'igmp' not in pim['interface'][interface]:
            del default_values['interface'][interface]['igmp']

    pim = config_dict_merge(default_values, pim)
    return pim

def verify(pim):
    if not pim or 'deleted' in pim:
        return None

    if 'igmp_proxy_enabled' in pim:
        raise ConfigError('IGMP proxy and PIM cannot be configured at the same time!')

    if 'interface' not in pim:
        raise ConfigError('PIM require defined interfaces!')

    for interface, interface_config in pim['interface'].items():
        verify_interface_exists(pim, interface)

        # Check join group in reserved net
        if 'igmp' in interface_config and 'join' in interface_config['igmp']:
            for join_addr in interface_config['igmp']['join']:
                if IPv4Address(join_addr) in IPv4Network(RESERVED_MC_NET):
                    raise ConfigError(f'Groups within {RESERVED_MC_NET} are reserved and cannot be joined!')

    if 'rp' in pim:
        if 'address' not in pim['rp']:
            raise ConfigError('PIM rendezvous point needs to be defined!')

        # Check unique multicast groups
        unique = []
        pim_base_error = 'PIM rendezvous point group'
        for address, address_config in pim['rp']['address'].items():
            if 'group' not in address_config:
                raise ConfigError(f'{pim_base_error} should be defined for "{address}"!')

            # Check if it is a multicast group
            for gr_addr in address_config['group']:
                if not IPv4Network(gr_addr).is_multicast:
                    raise ConfigError(f'{pim_base_error} "{gr_addr}" is not a multicast group!')
                if gr_addr in unique:
                    raise ConfigError(f'{pim_base_error} must be unique!')
                unique.append(gr_addr)

def generate(pim):
    if not pim or 'deleted' in pim:
        return None
    pim['frr_pimd_config']  = render_to_string('frr/pimd.frr.j2', pim)
    return None

def apply(pim):
    pim_daemon = 'pimd'
    pim_pid = process_named_running(pim_daemon)

    if not pim or 'deleted' in pim:
        if 'deleted' in pim:
            os.kill(int(pim_pid), SIGTERM)

        return None

    if not pim_pid:
        call('/usr/lib/frr/pimd -d -F traditional --daemon -A 127.0.0.1')

    # Save original configuration prior to starting any commit actions
    frr_cfg = frr.FRRConfig()

    frr_cfg.load_configuration(pim_daemon)
    frr_cfg.modify_section(f'^ip pim')
    frr_cfg.modify_section(f'^ip igmp')

    for key in ['interface', 'interface_removed']:
        if key not in pim:
            continue
        for interface in pim[key]:
            frr_cfg.modify_section(f'^interface {interface}', stop_pattern='^exit', remove_stop_mark=True)

    if 'frr_pimd_config' in pim:
        frr_cfg.add_before(frr.default_add_before, pim['frr_pimd_config'])
    frr_cfg.commit_configuration(pim_daemon)
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
