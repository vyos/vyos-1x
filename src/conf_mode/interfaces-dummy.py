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

from netifaces import interfaces
from sys import exit

from vyos.config import Config
from vyos.ifconfig import DummyIf
from vyos.validate import is_member
from vyos import ConfigError, airbag
airbag.enable()

def get_config():
    """ Retrive CLI config as dictionary. Dictionary can never be empty,
        as at least the interface name will be added or a deleted flag """
    conf = Config()

    # determine tagNode instance
    if 'VYOS_TAGNODE_VALUE' not in os.environ:
        raise ConfigError('Interface (VYOS_TAGNODE_VALUE) not specified')

    ifname = os.environ['VYOS_TAGNODE_VALUE']
    base = ['interfaces', 'dummy', ifname]

    dummy = conf.get_config_dict(base, key_mangling=('-', '_'))
    # store interface instance name in dictionary
    dummy.update({'ifname': ifname})

    # check if we are a member of any bridge
    bridge = is_member(conf, ifname, 'bridge')
    if bridge:
        tmp = {'is_bridge_member' : bridge}
        dummy.update(tmp)

    # Check if interface has been removed
    tmp = {'deleted' : not conf.exists(base)}
    dummy.update(tmp)

    return dummy

def verify(dummy):
    if dummy['deleted']:
        if 'is_bridge_member' in dummy.keys():
            raise ConfigError(
                'Interface "{ifname}" cannot be deleted as it is a '
                'member of bridge "{is_bridge_member}"!'.format(**dummy))

        return None

    if 'vrf' in dummy.keys():
        if dummy['vrf'] not in interfaces():
            raise ConfigError('VRF "{vrf}" does not exist'.format(**dummy))

        if 'is_bridge_member' in dummy.keys():
            raise ConfigError(
                'Interface "{ifname}" cannot be both a member of VRF "{vrf}" '
                'and bridge "{is_bridge_member}"!'.format(**dummy))

    # check if both keys are part of the dictionary
    if {'is_bridge_member', 'address'} <= set(dummy):
        raise ConfigError(
            f'Cannot assign address to interface "{ifname}" as it is a '
            f'member of bridge "{is_bridge_member}"!'.format(**dummy))

    return None

def generate(dummy):
    return None

def apply(dummy):
    d = DummyIf(dummy['ifname'])

    # Remove dummy interface
    if dummy['deleted']:
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
