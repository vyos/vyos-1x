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

from sys import exit

from vyos.config import Config
from vyos import ConfigError
from vyos.util import run
from vyos.template import render

from vyos import airbag
airbag.enable()

def get_config():
    # Return a (possibly empty) configuration dictionary
    return Config().get_config_dict(['system', 'display'])

def generate(config_dict):
    if not config_dict:
        return None
    # Render config file for daemon LCDd
    render('/run/LCDd/LCDd.lo.conf', 'system-display/LCDd.conf.tmpl', config_dict)
    # Render config file for client lcdproc
    render('/run/lcdproc/lcdproc.lo.conf', 'system-display/lcdproc.conf.tmpl', config_dict)

    return None

def verify(config_dict):
    if not config_dict:
        return None

    if 'model' not in config_dict:
        raise ConfigError('Display model is [REQUIRED]')

    if (           'show' not in config_dict
        or (      'clock' not in config_dict['show']
            and 'network' not in config_dict['show']
            and    'host' not in config_dict['show']
           )
       ):
        raise ConfigError('Display show must have a clock, host or network')

    if (      'network'     in config_dict['show']
        and 'interface' not in config_dict['show']['network']
       ):
        raise ConfigError('Display show network must have an interface')

    if (      'network' in config_dict['show']
        and 'interface' in config_dict['show']['network']
        and len(config_dict['show']['network']['interface']) > 3
       ):
        raise ConfigError('Display show network cannot have > 3 interfaces')

    return None

def apply(config_dict):
    # Stop client
    run('systemctl stop lcdproc@lo.service')

    if not config_dict or 'disabled' in config_dict:
        # Stop server
        run('systemctl stop LCDd@lo.service')
        return None

    # Restart server
    run('systemctl restart LCDd@lo.service')
    # Start client
    run('systemctl start lcdproc@lo.service')

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
