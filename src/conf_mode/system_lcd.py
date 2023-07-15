#!/usr/bin/env python3
#
# Copyright 2020-2022 VyOS maintainers and contributors <maintainers@vyos.io>
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
from vyos.utils.process import call
from vyos.utils.system import find_device_file
from vyos.template import render
from vyos import ConfigError
from vyos import airbag
airbag.enable()

lcdd_conf = '/run/LCDd/LCDd.conf'
lcdproc_conf = '/run/lcdproc/lcdproc.conf'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['system', 'lcd']
    lcd = conf.get_config_dict(base, key_mangling=('-', '_'),
                               get_first_key=True)
    # Return (possibly empty) dictionary
    return lcd

def verify(lcd):
    if not lcd:
        return None

    if 'model' in lcd and lcd['model'] in ['sdec']:
        # This is a fixed LCD display, no device needed - bail out early
        return None

    if not {'device', 'model'} <= set(lcd):
        raise ConfigError('Both device and driver must be set!')

    return None

def generate(lcd):
    if not lcd:
        return None

    if 'device' in lcd:
        lcd['device'] = find_device_file(lcd['device'])

    # Render config file for daemon LCDd
    render(lcdd_conf, 'lcd/LCDd.conf.j2', lcd)
    # Render config file for client lcdproc
    render(lcdproc_conf, 'lcd/lcdproc.conf.j2', lcd)

    return None

def apply(lcd):
    if not lcd:
        call('systemctl stop lcdproc.service LCDd.service')

        for file in [lcdd_conf, lcdproc_conf]:
            if os.path.exists(file):
                os.remove(file)
    else:
        # Restart server
        call('systemctl restart LCDd.service lcdproc.service')

    return None

if __name__ == '__main__':
    try:
        config_dict = get_config()
        verify(config_dict)
        generate(config_dict)
        apply(config_dict)
    except ConfigError as e:
        print(e)
        exit(1)
