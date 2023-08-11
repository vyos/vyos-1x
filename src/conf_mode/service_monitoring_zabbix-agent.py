#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
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

from vyos.config import Config
from vyos.template import render
from vyos.utils.process import call
from vyos import ConfigError
from vyos import airbag
airbag.enable()


service_name = 'zabbix-agent2'
service_conf = f'/run/zabbix/{service_name}.conf'
systemd_override = r'/run/systemd/system/zabbix-agent2.service.d/10-override.conf'


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['service', 'monitoring', 'zabbix-agent']

    if not conf.exists(base):
        return None

    config = conf.get_config_dict(base, key_mangling=('-', '_'),
                                  get_first_key=True,
                                  no_tag_node_value_mangle=True,
                                  with_recursive_defaults=True)

    # Cut the / from the end, /tmp/ => /tmp
    if 'directory' in config and config['directory'].endswith('/'):
        config['directory'] = config['directory'][:-1]

    return config


def verify(config):
    # bail out early - looks like removal from running config
    if config is None:
        return

    if 'server' not in config:
        raise ConfigError('Server is required!')


def generate(config):
    # bail out early - looks like removal from running config
    if config is None:
        # Remove old config and return
        config_files = [service_conf, systemd_override]
        for file in config_files:
            if os.path.isfile(file):
                os.unlink(file)

        return None

    # Write configuration file
    render(service_conf, 'zabbix-agent/zabbix-agent.conf.j2', config)
    render(systemd_override, 'zabbix-agent/10-override.conf.j2', config)

    return None


def apply(config):
    call('systemctl daemon-reload')
    if config:
        call(f'systemctl restart {service_name}.service')
    else:
        call(f'systemctl stop {service_name}.service')


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
