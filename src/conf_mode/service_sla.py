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

import os

from sys import exit

from vyos.config import Config
from vyos.template import render
from vyos.utils.process import call
from vyos import ConfigError
from vyos import airbag
airbag.enable()

owamp_config_dir = '/etc/owamp-server'
owamp_config_file = f'{owamp_config_dir}/owamp-server.conf'
systemd_override_owamp = r'/run/systemd/system/owamp-server.d/20-override.conf'

twamp_config_dir = '/etc/twamp-server'
twamp_config_file = f'{twamp_config_dir}/twamp-server.conf'
systemd_override_twamp = r'/run/systemd/system/twamp-server.d/20-override.conf'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'sla']
    if not conf.exists(base):
        return None

    sla = conf.get_config_dict(base, key_mangling=('-', '_'),
                               get_first_key=True,
                               with_recursive_defaults=True)

    # Ignore default XML values if config doesn't exists
    # Delete key from dict
    if not conf.exists(base + ['owamp-server']):
        del sla['owamp_server']
    if not conf.exists(base + ['twamp-server']):
        del sla['twamp_server']

    return sla

def verify(sla):
    if not sla:
        return None

def generate(sla):
    if not sla:
        return None

    render(owamp_config_file, 'sla/owamp-server.conf.j2', sla)
    render(systemd_override_owamp, 'sla/owamp-override.conf.j2', sla)

    render(twamp_config_file, 'sla/twamp-server.conf.j2', sla)
    render(systemd_override_twamp, 'sla/twamp-override.conf.j2', sla)

    return None

def apply(sla):
    owamp_service = 'owamp-server.service'
    twamp_service = 'twamp-server.service'

    call('systemctl daemon-reload')

    if not sla or 'owamp_server' not in sla:
        call(f'systemctl stop {owamp_service}')

        if os.path.exists(owamp_config_file):
            os.unlink(owamp_config_file)

    if not sla or 'twamp_server' not in sla:
        call(f'systemctl stop {twamp_service}')
        if os.path.exists(twamp_config_file):
            os.unlink(twamp_config_file)

    if sla and 'owamp_server' in sla:
        call(f'systemctl reload-or-restart {owamp_service}')

    if sla and 'twamp_server' in sla:
        call(f'systemctl reload-or-restart {twamp_service}')

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
