#!/usr/bin/env python3
#
# Copyright (C) 2022 VyOS maintainers and contributors
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
#

import os
import sys
import copy

import vyos.util

from vyos.config import Config
from vyos.ifconfig import Section
from vyos.util import call
from vyos.util import cmd

from vyos import ConfigError
from vyos import airbag
from pprint import pprint
airbag.enable()

nftables_conf = '/run/nftables.conf'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    # Full firewall dict
    firewall = conf.get_config_dict(
                 ['firewall'], key_mangling=('-', '_'),
                 get_first_key=True,
                 no_tag_node_value_mangle=True)

    policy_dict = vyos.util.get_sub_dict(firewall, ['policy', 'bridge', 'forward'])
    if not policy_dict:
        return None


    pprint(firewall)
    config = {}
    config["policy"] = firewall["policy"]
    if 'group' in firewall:
        config["group"] = firewall["group"]
    config["ipv4_ruleset"] = firewall["name"][firewall["policy"]["bridge"]["forward"]["ipv4"]]

    return config


def verify(firewall):
    # bail out early - looks like removal from running config
    if not firewall:
        return None

def generate(firewall):
    if not firewall:
        return None

    vyos.template.render(nftables_conf, 'firewall/nftables-bridge.tmpl', firewall)
    return None


def apply(firewall):
    if not firewall:
        call('nft flush ruleset bridge')
        return None
    install_result = vyos.util.run(f'nft -f {nftables_conf}')
    if install_result == 1:
        raise ConfigError('Failed to apply bridge firewall')
    return None


if __name__ == '__main__':

    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
