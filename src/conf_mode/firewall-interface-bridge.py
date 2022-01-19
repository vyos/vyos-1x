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
import copy
from sys import argv
from sys import exit

from vyos.config import Config
from vyos.ifconfig import Section
from vyos.util import call
from vyos.util import cmd

from vyos import ConfigError
from vyos import airbag
from pprint import pprint
airbag.enable()


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    iface = argv[1]
    # print(f"IFACE : {iface}")
    iface_path = Section.get_config_path(iface)
    # print(f'IFACE_PATH: {iface_path}')
    iface_firewall_path = f'interfaces {iface_path} firewall bridge'

    br_firewall = conf.get_config_dict(
                    iface_firewall_path, key_mangling=('-', '_'),
                    get_first_key=True, no_tag_node_value_mangle=True)

    br_firewall['br_iface'] = iface
    # Full firewall dict
    br_firewall['full_firewall'] = conf.get_config_dict(
                                ['firewall'], key_mangling=('-', '_'),
                                get_first_key=True,
                                no_tag_node_value_mangle=True)

    if 'forward' not in br_firewall:
        return None

    if 'name' in br_firewall['forward']:
        # show interfaces bridge br1 firewall bridge forward name  => FOO
        br_firewall['br_firewall_name'] = br_firewall['forward']['name']
        # Firewall FOO rules
        # show firewall name FOO
        br_firewall['br_iface_firewall'] = conf.get_config_dict(
                         ['firewall', 'name', br_firewall['br_firewall_name']],
                         key_mangling=('-', '_'), get_first_key=True,
                         no_tag_node_value_mangle=True)

    pprint(br_firewall)
    """
    Example:

    set firewall name FOO rule 10 action 'accept'
    set firewall name FOO rule 10 destination address '203.0.113.1'
    set interfaces bridge br1 firewall bridge forward name 'FOO'

    vyos@r4# commit
    [ interfaces bridge br1 firewall bridge ]
    {'br_firewall_name': 'FOO',
     'br_iface': 'br1',
     'br_iface_firewall': {'default_action': 'drop',
                           'rule': {'10': {'action': 'accept',
                                           'destination': {'address': '203.0.113.1'}}}},
     'forward': {'name': 'FOO'},
     'full_firewall': {'all_ping': 'enable',
                       'broadcast_ping': 'disable',
                       'config_trap': 'disable',
                       'ip_src_route': 'disable',
                       'ipv6_receive_redirects': 'disable',
                       'ipv6_src_route': 'disable',
                       'log_martians': 'enable',
                       'name': {'FOO': {'default_action': 'drop',
                                        'rule': {'10': {'action': 'accept',
                                                        'destination': {'address': '203.0.113.1'}}}}},
                       'receive_redirects': 'disable',
                       'send_redirects': 'enable',
                       'source_validation': 'disable',
                       'syn_cookies': 'enable',
                       'twa_hazards_protection': 'disable'}}

    """
    return br_firewall


def verify(br_firewall):
    # bail out early - looks like removal from running config
    if not br_firewall:
        return None


def generate(br_firewall):
    return None


def apply(br_firewall):
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
