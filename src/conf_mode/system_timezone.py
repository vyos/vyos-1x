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

import sys

from copy import deepcopy
from vyos.config import Config
from vyos import ConfigError
from vyos.utils.process import call

from vyos import airbag
airbag.enable()

default_config_data = {
    'name': 'UTC'
}

def get_config(config=None):
    tz = deepcopy(default_config_data)
    if config:
        conf = config
    else:
        conf = Config()
    if conf.exists('system time-zone'):
        tz['name'] = conf.return_value('system time-zone')

    return tz

def verify(tz):
    pass

def generate(tz):
    pass

def apply(tz):
    call('/usr/bin/timedatectl set-timezone {}'.format(tz['name']))
    call('systemctl restart rsyslog')

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
