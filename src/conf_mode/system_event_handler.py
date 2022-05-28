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
import os

from vyos.config import Config
from vyos.configdict import node_changed
from vyos.util import cmd
from vyos.util import call
from vyos.template import render
from vyos import ConfigError
from vyos import airbag
airbag.enable()


systemd_dir = '/etc/systemd/system'
systemd_service = 'vyos-event-handler'
service_path = f'{systemd_dir}/{systemd_service}.service'
event_conf = '/run/vyos-event-handler.conf'


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['system', 'event-handler']
    event = conf.get_config_dict(base, get_first_key=True, no_tag_node_value_mangle=True)

    return event

def verify(event):
    # bail out early - looks like removal from running config
    if not event:
        return None

    for name, event_config in event.items():
        if 'pattern' not in event_config or 'script' not in event_config:
            raise ConfigError(f'Event-handler "pattern and script" are mandatory!')

def generate(event):
    if not event:
        return None

    conf_json = json.dumps(event, indent = 4)
    with open(event_conf, 'w') as f:
        f.write(conf_json)

    render(service_path, 'event-handler/systemd_event_handler_service.j2', event)

    return None

def apply(event):
    call('systemctl daemon-reload')
    if event:
        call(f'systemctl restart {systemd_service}.service')
    else:
        call(f'systemctl stop {systemd_service}.service')

        for f in [service_path, event_conf]:
            if os.path.isfile(f):
                os.unlink(f)

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
