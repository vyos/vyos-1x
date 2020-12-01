#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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
from vyos.template import render
from vyos.util import call
from vyos.util import dict_search
from vyos import ConfigError
from vyos import airbag
from pprint import pprint
airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['vpn', 'nipsec']
    if not conf.exists(base):
        return None

    # retrieve common dictionary keys
    ipsec = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
    return ipsec

def verify(ipsec):
    if not ipsec:
        return None

def generate(ipsec):
    if not ipsec:
        return None

    return ipsec

def apply(ipsec):
    if not ipsec:
        return None

    pprint(ipsec)

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
