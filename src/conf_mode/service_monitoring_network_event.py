#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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
import json

from sys import exit

from vyos.config import Config
from vyos.utils.file import write_file
from vyos.utils.process import call
from vyos import ConfigError
from vyos import airbag
airbag.enable()

vyos_network_event_logger_config = r'/run/vyos-network-event-logger.conf'


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'monitoring', 'network-event']
    if not conf.exists(base):
        return None

    monitoring = conf.get_config_dict(base, key_mangling=('-', '_'),
                                      get_first_key=True,
                                      no_tag_node_value_mangle=True)

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    monitoring = conf.merge_defaults(monitoring, recursive=True)

    return monitoring


def verify(monitoring):
    if not monitoring:
        return None

    return None


def generate(monitoring):
    if not monitoring:
        # Delete config
        if os.path.exists(vyos_network_event_logger_config):
            os.unlink(vyos_network_event_logger_config)

        return None

    # Create config
    log_conf_json = json.dumps(monitoring, indent=4)
    write_file(vyos_network_event_logger_config, log_conf_json)

    return None


def apply(monitoring):
    # Reload systemd manager configuration
    systemd_service = 'vyos-network-event-logger.service'

    if not monitoring:
        call(f'systemctl stop {systemd_service}')
        return

    call(f'systemctl restart {systemd_service}')


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
