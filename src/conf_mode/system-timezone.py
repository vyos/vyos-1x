#!/usr/bin/env python3
#
# Copyright (C) 2019 VyOS maintainers and contributors
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

import sys
import os

from copy import deepcopy
from vyos.config import Config
from vyos import ConfigError
from vyos.util import run


default_config_data = {
    'name': 'UTC'
}

def get_config():
    tz = deepcopy(default_config_data)
    conf = Config()
    if conf.exists('system time-zone'):
        tz['name'] = conf.return_value('system time-zone')

    return tz

def verify(tz):
    pass

def generate(tz):
    pass

def apply(tz):
    run('/usr/bin/timedatectl set-timezone {}'.format(tz['name']))

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
