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

from vyos.ifconfig import LoopbackIf
from vyos.config import Config
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
    base = ['interfaces', 'loopback', ifname]

    loopback = conf.get_config_dict(base, key_mangling=('-', '_'))
    # store interface instance name in dictionary
    loopback.update({'ifname': ifname})

    # Check if interface has been removed
    tmp = {'deleted' : not conf.exists(base)}
    loopback.update(tmp)

    return loopback

def verify(loopback):
    return None

def generate(loopback):
    return None

def apply(loopback):
    l = LoopbackIf(loopback['ifname'])
    if loopback['deleted']:
        l.remove()
    else:
        l.update(loopback)

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
