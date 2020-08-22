#!/usr/bin/env python3
#
# Copyright 2020 VyOS maintainers and contributors <maintainers@vyos.io>
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
import vyos.defaults

from jinja2 import FileSystemLoader, Environment
from sys import exit

from vyos.config import Config
from vyos import ConfigError

lcdd_conf = '/run/LCDd/LCDd.conf'
lcdproc_conf = '/run/lcdproc/lcdproc.conf'

def get_config():
    base = 'system lcd'
    conf = Config()
    lcd = {}
    if conf.exists(base):
        conf.set_level(base)

        if conf.exists('device'):
            tmp = conf.return_value('device')
            lcd.update({'device' : tmp})

        if conf.exists('model'):
            tmp = conf.return_value('model')
            lcd.update({'model' : tmp})

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
        lcd['device'] = '/dev/' + lcd['device']

    tmpl_path = os.path.join(vyos.defaults.directories['data'], 'templates')
    fs_loader = FileSystemLoader(tmpl_path)
    env = Environment(loader=fs_loader)

    # create configuration directories
    for file in [lcdd_conf, lcdproc_conf]:
        path = os.path.dirname(file)
        if not os.path.isdir(path):
            os.mkdir(path, mode=0o755)

    lcdd_conf_tmpl = env.get_template('lcd/LCDd.conf.tmpl')
    tmp = lcdd_conf_tmpl.render(lcd)
    with open(lcdd_conf, 'w') as f:
        f.write(tmp)

    lcdproc_conf_tmpl = env.get_template('lcd/lcdproc.conf.tmpl')
    tmp = lcdproc_conf_tmpl.render(lcd)
    with open(lcdproc_conf, 'w') as f:
        f.write(tmp)

    return None

def apply(lcd):
    if not lcd:
        os.system('sudo systemctl stop lcdproc.service LCDd.service')

        for file in [lcdd_conf, lcdproc_conf]:
            if os.path.exists(file):
                os.remove(file)
    else:
        # Restart server
        os.system('sudo systemctl restart LCDd.service lcdproc.service')

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
