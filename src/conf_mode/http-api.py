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

from time import sleep

import vyos.defaults

from vyos.config import Config
from vyos.configdep import set_dependents, call_dependents
from vyos.template import render
from vyos.utils.process import call
from vyos.utils.process import is_systemd_service_running
from vyos import ConfigError
from vyos import airbag
airbag.enable()

systemd_service = '/run/systemd/system/vyos-http-api.service'

vyos_conf_scripts_dir=vyos.defaults.directories['conf_mode']

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    # reset on creation/deletion of 'api' node
    https_base = ['service', 'https']
    if conf.exists(https_base):
        set_dependents("https", conf)

    base = ['service', 'https', 'api']
    if not conf.exists(base):
        return None

    http_api = conf.get_config_dict(base, key_mangling=('-', '_'),
                                    no_tag_node_value_mangle=True,
                                    get_first_key=True,
                                    with_recursive_defaults=True)

    # Do we run inside a VRF context?
    vrf_path = ['service', 'https', 'vrf']
    if conf.exists(vrf_path):
        http_api['vrf'] = conf.return_value(vrf_path)

    if http_api.from_defaults(['graphql']):
        del http_api['graphql']

    return http_api

def verify(http_api):
    return None

def generate(http_api):
    if http_api is None:
        if os.path.exists(systemd_service):
            os.unlink(systemd_service)
        return

    render(systemd_service, 'https/vyos-http-api.service.j2', http_api)

def apply(http_api):
    # Reload systemd manager configuration
    call('systemctl daemon-reload')
    service_name = 'vyos-http-api.service'

    if http_api is not None:
        if is_systemd_service_running(f'{service_name}'):
            call(f'systemctl reload {service_name}')
        else:
            call(f'systemctl restart {service_name}')
    else:
        call(f'systemctl stop {service_name}')

    # Let uvicorn settle before restarting Nginx
    sleep(1)

    call_dependents()

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
