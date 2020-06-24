#!/usr/bin/env python3
#
# Copyright (C) 2020 Francois Mertz fireboxled at gmail.com
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
import re

from sys import exit

from vyos.config import Config
from vyos import ConfigError
from vyos.util import run
from vyos.template import render

from vyos import airbag
airbag.enable()

def get_config():
    c = Config()

    if not c.exists('system display'):
        return None

    c.set_level('system display')

    return c.get_config_dict([])

def generate(c):
    if c == None:
        return None
    # Render config file for daemon LCDd
    render('/etc/LCDd.conf', 'system-display/LCDd.conf.tmpl', c)
    # Render config file for client lcdproc
    render('/etc/lcdproc.conf', 'system-display/lcdproc.conf.tmpl', c)

    return None

def verify(c):
    if c == None:
        return None

    if c.get('model') == None:
        raise ConfigError('For system display, a model is [REQUIRED]')

    if c.get('show') == None:
        raise ConfigError('For system display, show cannot be empty')

    if 'network' in c['show'] and 'interface' not in c['show']['network']:
        raise ConfigError('system display show network must have at least one interface')

    if 'network' in c['show'] and 'interface' in c['show']['network'] and len(c['show']['network']['interface']) > 3:
        raise ConfigError('system display show network interface cannot have more than 3 entries')

    return None

def apply(c):
    if not c or c['config'] == 'disabled':
        # Stop client first
        run('systemctl stop lcdproc.service')
        # Stop server next
        return run('systemctl stop LCDd.service')

    # Stop client first
    run('systemctl stop lcdproc.service')
    # Restart server next
    run('systemctl restart LCDd.service')
    # Start client
    run('systemctl start lcdproc.service')

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
