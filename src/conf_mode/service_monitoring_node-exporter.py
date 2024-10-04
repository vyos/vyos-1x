#!/usr/bin/env python3
#
# Copyright (C) 2024 VyOS maintainers and contributors
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
from vyos.configdict import is_node_changed
from vyos.configverify import verify_vrf
from vyos.template import render
from vyos.utils.process import call
from vyos import ConfigError
from vyos import airbag


airbag.enable()

service_file = '/etc/systemd/system/node_exporter.service'
systemd_service = 'node_exporter.service'


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'monitoring', 'node-exporter']
    if not conf.exists(base):
        return None

    config_data = conf.get_config_dict(
        base, key_mangling=('-', '_'), get_first_key=True
    )
    config_data = conf.merge_defaults(config_data, recursive=True)

    tmp = is_node_changed(conf, base + ['vrf'])
    if tmp:
        config_data.update({'restart_required': {}})

    return config_data


def verify(config_data):
    # bail out early - looks like removal from running config
    if not config_data:
        return None

    verify_vrf(config_data)
    return None


def generate(config_data):
    if not config_data:
        # Delete systemd files
        if os.path.isfile(service_file):
            os.unlink(service_file)
        return None

    # Render node_exporter service_file
    render(service_file, 'node_exporter/node_exporter.service.j2', config_data)
    return None


def apply(config_data):
    # Reload systemd manager configuration
    call('systemctl daemon-reload')
    if not config_data:
        call(f'systemctl stop {systemd_service}')
        return

    # we need to restart the service if e.g. the VRF name changed
    systemd_action = 'reload-or-restart'
    if 'restart_required' in config_data:
        systemd_action = 'restart'

    call(f'systemctl {systemd_action} {systemd_service}')


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
