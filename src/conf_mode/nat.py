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

from copy import deepcopy
from sys import exit

from vyos.config import Config
from vyos import ConfigError

default_config_data = {
    'source': [],
    'destination': []
}

def get_config():
    nat = deepcopy(default_config_data)
    conf = Config()
    base = ['nat']
    if not conf.exists(base):
        return None
    else:
        conf.set_level(base)

    return nat

def verify(nat):
    if not nat:
        return None

    return None

def generate(nat):
    if not nat:
        return None

    return None

def apply(nat):

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
