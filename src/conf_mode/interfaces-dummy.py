#!/usr/bin/env python3
#
# Copyright (C) 2019-2020 VyOS maintainers and contributors
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
from vyos.configdict import get_interface_dict
from vyos.configverify import verify_vrf
from vyos.configverify import verify_address
from vyos.configverify import verify_bridge_delete
from vyos.ifconfig import DummyIf
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config():
    """
    Retrive CLI config as dictionary. Dictionary can never be empty, as at least the
    interface name will be added or a deleted flag
    """
    conf = Config()
    base = ['interfaces', 'dummy']
    dummy = get_interface_dict(conf, base)
    return dummy

def verify(dummy):
    if 'deleted' in dummy.keys():
        verify_bridge_delete(dummy)
        return None

    verify_vrf(dummy)
    verify_address(dummy)

    return None

def generate(dummy):
    return None

def apply(dummy):
    d = DummyIf(dummy['ifname'])

    # Remove dummy interface
    if 'deleted' in dummy.keys():
        d.remove()
    else:
        d.update(dummy)

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
