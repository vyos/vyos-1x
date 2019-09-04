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
#
#

import sys
import os
import subprocess
import json

import vyos.defaults
from vyos.config import Config
from vyos import ConfigError

config_file = '/etc/vyos/http-api.conf'

vyos_conf_scripts_dir=vyos.defaults.directories['conf_mode']

# XXX: this model will need to be extended for tag nodes
dependencies = [
    'https.py',
]

def get_config():
    http_api = vyos.defaults.api_data

    conf = Config()
    if not conf.exists('service https api'):
        return None
    else:
        conf.set_level('service https api')

    if conf.exists('strict'):
        http_api['strict'] = 'true'

    if conf.exists('debug'):
        http_api['debug'] = 'true'

    if conf.exists('port'):
        port = conf.return_value('port')
        http_api['port'] = port

    if conf.exists('keys'):
        for name in conf.list_nodes('keys id'):
            if conf.exists('keys id {0} key'.format(name)):
                key = conf.return_value('keys id {0} key'.format(name))
                new_key = { 'id': name, 'key': key }
                http_api['api_keys'].append(new_key)

    return http_api

def verify(http_api):
    return None

def generate(http_api):
    if http_api is None:
        return None

    if not os.path.exists('/etc/vyos'):
        os.mkdir('/etc/vyos')

    with open(config_file, 'w') as f:
        json.dump(http_api, f, indent=2)

    return None

def apply(http_api):
    if http_api is not None:
        os.system('sudo systemctl restart vyos-http-api.service')
    else:
        os.system('sudo systemctl stop vyos-http-api.service')

    for dep in dependencies:
        cmd = '{0}/{1}'.format(vyos_conf_scripts_dir, dep)
        try:
            subprocess.check_call(cmd, shell=True)
        except subprocess.CalledProcessError as err:
            raise ConfigError("{}.".format(err))

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
