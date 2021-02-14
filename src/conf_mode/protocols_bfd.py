#!/usr/bin/env python3
#
# Copyright (C) 2019-2021 VyOS maintainers and contributors
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
from vyos.template import is_ipv6
from vyos.template import render_to_string
from vyos.util import call
from vyos.validate import is_ipv6_link_local
from vyos.xml import defaults
from vyos import ConfigError
from vyos import frr
from vyos import airbag
airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['protocols', 'bfd']
    bfd = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)

    # Bail out early if configuration tree does not exist
    if not conf.exists(base):
        return bfd

    if 'peer' in bfd:
        # We have gathered the dict representation of the CLI, but there are
        # default options which we need to update into the dictionary retrived.
        # XXX: T2665: we currently have no nice way for defaults under tag
        # nodes, thus we load the defaults "by hand"
        default_values = defaults(base + ['peer'])
        for peer in bfd['peer']:
            bfd['peer'][peer] = dict_merge(default_values, bfd['peer'][peer])

    return bfd

def verify(bfd):
    if not bfd or 'peer' not in bfd:
        return None

    for peer, peer_config in bfd['peer'].items():
        # IPv6 link local peers require an explicit local address/interface
        if is_ipv6_link_local(peer):
            if 'source' not in peer_config or len(peer_config['source'] < 2):
                raise ConfigError('BFD IPv6 link-local peers require explicit local address and interface setting')

        # IPv6 peers require an explicit local address
        if is_ipv6(peer):
            if 'source' not in peer_config or 'address' not in peer_config['source']:
                raise ConfigError('BFD IPv6 peers require explicit local address setting')

        if 'multihop' in peer_config:
            # multihop require source address
            if 'source' not in peer_config or 'address' not in peer_config['source']:
                raise ConfigError('BFD multihop require source address')

            # multihop and echo-mode cannot be used together
            if 'echo_mode' in peer_config:
                raise ConfigError('Multihop and echo-mode cannot be used together')

            # multihop doesn't accept interface names
            if 'source' in peer_config and 'interface' in peer_config['source']:
                raise ConfigError('Multihop and source interface cannot be used together')

        # echo interval can be configured only with enabled echo-mode
        if 'interval' in peer_config and 'echo_interval' in peer_config['interval'] and 'echo_mode' not in peer_config:
            raise ConfigError('echo-interval can be configured only with enabled echo-mode')

    return None

def generate(bfd):
    if not bfd:
        bfd['new_frr_config'] = ''
        return None

    bfd['new_frr_config'] = render_to_string('frr/bfd.frr.tmpl', bfd)

def apply(bfd):
    # Save original configuration prior to starting any commit actions
    frr_cfg = frr.FRRConfig()
    frr_cfg.load_configuration()
    frr_cfg.modify_section('bfd', '')
    frr_cfg.add_before(r'(ip prefix-list .*|route-map .*|line vty)', bfd['new_frr_config'])
    frr_cfg.commit_configuration()

    # If FRR config is blank, rerun the blank commit x times due to frr-reload
    # behavior/bug not properly clearing out on one commit.
    if bfd['new_frr_config'] == '':
        for a in range(5):
            frr_cfg.commit_configuration()

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
