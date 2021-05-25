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
from vyos.configdict import node_changed
from vyos.configdict import leaf_node_changed
from vyos.template import render
from vyos.util import call
from vyos import ConfigError
from vyos import airbag
from pprint import pprint
airbag.enable()


def get_config(config=None):

    if config:
        conf = config
    else:
        conf = Config()
    base = ['nfirewall']
    firewall = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True,
                                    no_tag_node_value_mangle=True)

    pprint(firewall)
    return firewall

def verify(firewall):
    # bail out early - looks like removal from running config
    if not firewall:
        return None

    return None

def generate(firewall):
    if not firewall:
        return None

    return None

def apply(firewall):
    if not firewall:
        return None

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
