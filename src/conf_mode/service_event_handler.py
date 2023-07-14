#!/usr/bin/env python3
#
# Copyright (C) 2022 VyOS maintainers and contributors
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

from vyos.config import Config
from vyos.utils.dict import dict_search
from vyos.utils.process import call
from vyos import ConfigError
from vyos import airbag

airbag.enable()

service_name = 'vyos-event-handler'
service_conf = Path(f'/run/{service_name}.conf')


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['service', 'event-handler', 'event']
    config = conf.get_config_dict(base,
                                  get_first_key=True,
                                  no_tag_node_value_mangle=True)

    return config


def verify(config):
    # bail out early - looks like removal from running config
    if not config:
        return None

    for name, event_config in config.items():
        if not dict_search('filter.pattern', event_config) or not dict_search(
                'script.path', event_config):
            raise ConfigError(
                'Event-handler: both pattern and script path items are mandatory'
            )

        if dict_search('script.environment.message', event_config):
            raise ConfigError(
                'Event-handler: "message" environment variable is reserved for log message text'
            )


def generate(config):
    if not config:
        # Remove old config and return
        service_conf.unlink(missing_ok=True)
        return None

    # Write configuration file
    conf_json = json.dumps(config, indent=4)
    service_conf.write_text(conf_json)

    return None


def apply(config):
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
