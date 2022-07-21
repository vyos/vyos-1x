#!/usr/bin/env python3
#
# Copyright (C) 2018-2022 VyOS maintainers and contributors
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
from vyos.configdict import dict_merge
from vyos.template import render
from vyos.util import call
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_file = r'/etc/fastnetmon.conf'
networks_list = r'/etc/networks_list'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'ids', 'ddos-protection']
    fastnetmon = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_values = defaults(base)
    fastnetmon = dict_merge(default_values, fastnetmon)

    return fastnetmon

def verify(fastnetmon):
    if not fastnetmon:
        return None

    if 'mode' not in fastnetmon:
        raise ConfigError('Specify operating mode!')

    if 'listen_interface' not in fastnetmon:
        raise ConfigError('Specify interface(s) for traffic capture')

    if 'alert_script' in fastnetmon:
        if os.path.isfile(fastnetmon['alert_script']):
            # Check script permissions
            if not os.access(fastnetmon['alert_script'], os.X_OK):
                raise ConfigError('Script "{alert_script}" is not executable!'.format(fastnetmon['alert_script']))
        else:
           raise ConfigError('File "{alert_script}" does not exists!'.format(fastnetmon))

def generate(fastnetmon):
    if not fastnetmon:
        if os.path.isfile(config_file):
            os.unlink(config_file)
        if os.path.isfile(networks_list):
            os.unlink(networks_list)

        return

    render(config_file, 'ids/fastnetmon.j2', fastnetmon)
    render(networks_list, 'ids/fastnetmon_networks_list.j2', fastnetmon)

    return None

def apply(fastnetmon):
    if not fastnetmon:
        # Stop fastnetmon service if removed
        call('systemctl stop fastnetmon.service')
    else:
        call('systemctl restart fastnetmon.service')

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
