#!/usr/bin/env python3
#
# Copyright (C) 2023-2024 VyOS maintainers and contributors
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
from vyos.configverify import verify_vrf
from vyos.template import render
from vyos.utils.process import call
from vyos.utils.network import is_addr_assigned
from vyos import ConfigError
from vyos import airbag
airbag.enable()

hsflowd_conf_path = '/run/sflow/hsflowd.conf'
systemd_service = 'hsflowd.service'
systemd_override = f'/run/systemd/system/{systemd_service}.d/override.conf'


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['system', 'sflow']
    if not conf.exists(base):
        return None

    sflow = conf.get_config_dict(base, key_mangling=('-', '_'),
                                 get_first_key=True,
                                 with_recursive_defaults=True)

    return sflow

def verify(sflow):
    if not sflow:
        return None

    # Check if configured sflow agent-address exist in the system
    if 'agent_address' in sflow:
        tmp = sflow['agent_address']
        if not is_addr_assigned(tmp):
            raise ConfigError(
                f'Configured "sflow agent-address {tmp}" does not exist in the system!'
            )

    # Check if at least one interface is configured
    if 'interface' not in sflow:
        raise ConfigError(
            'sFlow requires at least one interface to be configured!')

    # Check if at least one server is configured
    if 'server' not in sflow:
        raise ConfigError('You need to configure at least one sFlow server!')

    verify_vrf(sflow)
    return None

def generate(sflow):
    if not sflow:
        return None

    render(hsflowd_conf_path, 'sflow/hsflowd.conf.j2', sflow)
    render(systemd_override, 'sflow/override.conf.j2', sflow)
    # Reload systemd manager configuration
    call('systemctl daemon-reload')

def apply(sflow):
    if not sflow:
        # Stop flow-accounting daemon and remove configuration file
        call(f'systemctl stop {systemd_service}')
        if os.path.exists(hsflowd_conf_path):
            os.unlink(hsflowd_conf_path)
        return

    # Start/reload flow-accounting daemon
    call(f'systemctl restart {systemd_service}')

if __name__ == '__main__':
    try:
        config = get_config()
        verify(config)
        generate(config)
        apply(config)
    except ConfigError as e:
        print(e)
        exit(1)
