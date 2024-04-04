#!/usr/bin/env python3
#
# Copyright (C) 2022-2024 VyOS maintainers and contributors
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

import json

from pathlib import Path
from sys import exit

from vyos.config import Config
from vyos.utils.process import call
from vyos import ConfigError
from vyos import airbag
airbag.enable()

base = ['system', 'update-check']
service_name = 'vyos-system-update'
service_conf = Path(f'/run/{service_name}.conf')
motd_file = Path('/run/motd.d/10-vyos-update')


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    if not conf.exists(base):
        return None

    config = conf.get_config_dict(base, key_mangling=('-', '_'),
                                  get_first_key=True, no_tag_node_value_mangle=True)

    return config


def verify(config):
    # bail out early - looks like removal from running config
    if config is None:
        return

    if 'url' not in config:
        raise ConfigError('URL is required!')


def generate(config):
    # bail out early - looks like removal from running config
    if config is None:
        # Remove old config and return
        service_conf.unlink(missing_ok=True)
        # MOTD used in /run/motd.d/10-update
        motd_file.unlink(missing_ok=True)
        return None

    # Write configuration file
    conf_json = json.dumps(config, indent=4)
    service_conf.write_text(conf_json)

    return None


def apply(config):
    if config:
        if 'auto_check' in config:
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
