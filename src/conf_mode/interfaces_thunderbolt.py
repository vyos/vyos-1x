#!/usr/bin/env python3
#
# Copyright (C) 2019-2024 VyOS maintainers and contributors
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
from vyos.configdict import get_interface_dict
from vyos.configverify import verify_vrf
from vyos.configverify import verify_address
from vyos.configverify import verify_bridge_delete
from vyos.configverify import verify_mirror_redirect
from vyos.ifconfig import ThunderboltIf
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config(config=None):
    """
    Retrive CLI config as dictionary. Dictionary can never be empty, as at least the
    interface name will be added or a deleted flag
    """
    if config:
        conf = config
    else:
        conf = Config()
    base = ['interfaces', 'thunderbolt']
    _, thunderbolt = get_interface_dict(conf, base)
    return thunderbolt

def verify(thunderbolt):
    if 'deleted' in thunderbolt:
        verify_bridge_delete(thunderbolt)
        return None

    verify_vrf(thunderbolt)
    verify_address(thunderbolt)
    verify_mirror_redirect(thunderbolt)
    # TODO: Verify a lot more here

    return None

def generate(thunderbolt):
    return None

def apply(thunderbolt):
    t = ThunderboltIf(**thunderbolt)

    # Remove thunderbolt interface
    if 'deleted' in thunderbolt:
        t.remove()
    else:
        t.update(thunderbolt)

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
