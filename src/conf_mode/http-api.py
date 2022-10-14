#!/usr/bin/env python3
#
# Copyright (C) 2019-2021 VyOS maintainers and contributors
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
import json

from time import sleep
from copy import deepcopy

import vyos.defaults

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.template import render
from vyos.util import cmd
from vyos.util import call
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

api_conf_file = '/etc/vyos/http-api.conf'
systemd_service = '/run/systemd/system/vyos-http-api.service'

vyos_conf_scripts_dir=vyos.defaults.directories['conf_mode']

def _translate_values_to_boolean(d: dict) -> dict:
    for k in list(d):
        if d[k] == {}:
            d[k] = True
        elif isinstance(d[k], dict):
            _translate_values_to_boolean(d[k])
        else:
            pass

def get_config(config=None):
    http_api = deepcopy(vyos.defaults.api_data)
    x = http_api.get('api_keys')
    if x is None:
        default_key = None
    else:
        default_key = x[0]
    keys_added = False

    if config:
        conf = config
    else:
        conf = Config()

    base = ['service', 'https', 'api']
    if not conf.exists(base):
        return None

    api_dict = conf.get_config_dict(base, key_mangling=('-', '_'),
                                          no_tag_node_value_mangle=True,
                                          get_first_key=True)

    # One needs to 'flatten' the keys dict from the config into the
    # http-api.conf format for api_keys:
    if 'keys' in api_dict:
        api_dict['api_keys'] = []
        for el in list(api_dict['keys']['id']):
            key = api_dict['keys']['id'][el]['key']
            api_dict['api_keys'].append({'id': el, 'key': key})
        del api_dict['keys']

    # Do we run inside a VRF context?
    vrf_path = ['service', 'https', 'vrf']
    if conf.exists(vrf_path):
        http_api['vrf'] = conf.return_value(vrf_path)

    if 'api_keys' in api_dict:
        keys_added = True

    if 'gql' in api_dict:
        api_dict = dict_merge(defaults(base), api_dict)

    http_api.update(api_dict)

    if keys_added and default_key:
        if default_key in http_api['api_keys']:
            http_api['api_keys'].remove(default_key)

    # Finally, translate entries in http_api into boolean settings for
    # backwards compatability of JSON http-api.conf file
    _translate_values_to_boolean(http_api)

    return http_api

def verify(http_api):
    return None

def generate(http_api):
    if http_api is None:
        if os.path.exists(systemd_service):
            os.unlink(systemd_service)
        return None

    if not os.path.exists('/etc/vyos'):
        os.mkdir('/etc/vyos')

    with open(api_conf_file, 'w') as f:
        json.dump(http_api, f, indent=2)

    render(systemd_service, 'https/vyos-http-api.service.j2', http_api)
    return None

def apply(http_api):
    # Reload systemd manager configuration
    call('systemctl daemon-reload')
    service_name = 'vyos-http-api.service'

    if http_api is not None:
        call(f'systemctl restart {service_name}')
    else:
        call(f'systemctl stop {service_name}')

    # Let uvicorn settle before restarting Nginx
    sleep(1)

    cmd(f'{vyos_conf_scripts_dir}/https.py', raising=ConfigError)

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
