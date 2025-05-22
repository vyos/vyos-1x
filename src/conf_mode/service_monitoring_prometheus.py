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

node_exporter_service_file = '/etc/systemd/system/node_exporter.service'
node_exporter_systemd_service = 'node_exporter.service'
node_exporter_collector_path = '/run/node_exporter/collector'

frr_exporter_service_file = '/etc/systemd/system/frr_exporter.service'
frr_exporter_systemd_service = 'frr_exporter.service'

blackbox_exporter_service_file = '/etc/systemd/system/blackbox_exporter.service'
blackbox_exporter_systemd_service = 'blackbox_exporter.service'


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'monitoring', 'prometheus']
    if not conf.exists(base):
        return None

    monitoring = {}
    exporters = {
        'node_exporter': base + ['node-exporter'],
        'frr_exporter': base + ['frr-exporter'],
        'blackbox_exporter': base + ['blackbox-exporter'],
    }

    for exporter_name, exporter_base in exporters.items():
        if conf.exists(exporter_base):
            monitoring[exporter_name] = conf.get_config_dict(
                exporter_base,
                key_mangling=('-', '_'),
                get_first_key=True,
                with_recursive_defaults=True,
            )

    tmp = is_node_changed(conf, base + ['node-exporter', 'vrf'])
    if tmp:
        monitoring.update({'node_exporter_restart_required': {}})

    tmp = is_node_changed(conf, base + ['frr-exporter', 'vrf'])
    if tmp:
        monitoring.update({'frr_exporter_restart_required': {}})

    tmp = False
    for node in ['vrf', 'config-file']:
        tmp = tmp or is_node_changed(conf, base + ['blackbox-exporter', node])
    if tmp:
        monitoring.update({'blackbox_exporter_restart_required': {}})

    return monitoring


def verify(monitoring):
    if not monitoring:
        return None

    if 'node_exporter' in monitoring:
        verify_vrf(monitoring['node_exporter'])

    if 'frr_exporter' in monitoring:
        verify_vrf(monitoring['frr_exporter'])

    if 'blackbox_exporter' in monitoring:
        verify_vrf(monitoring['blackbox_exporter'])

        if (
            'modules' in monitoring['blackbox_exporter']
            and 'dns' in monitoring['blackbox_exporter']['modules']
            and 'name' in monitoring['blackbox_exporter']['modules']['dns']
        ):
            for mod_name, mod_config in monitoring['blackbox_exporter']['modules'][
                'dns'
            ]['name'].items():
                if 'query_name' not in mod_config:
                    raise ConfigError(
                        f'query name not specified in dns module {mod_name}'
                    )

    return None


def generate(monitoring):
    if not monitoring or 'node_exporter' not in monitoring:
        # Delete systemd files
        if os.path.isfile(node_exporter_service_file):
            os.unlink(node_exporter_service_file)

    if not monitoring or 'frr_exporter' not in monitoring:
        # Delete systemd files
        if os.path.isfile(frr_exporter_service_file):
            os.unlink(frr_exporter_service_file)

    if not monitoring or 'blackbox_exporter' not in monitoring:
        # Delete systemd files
        if os.path.isfile(blackbox_exporter_service_file):
            os.unlink(blackbox_exporter_service_file)

    if not monitoring:
        return None

    if 'node_exporter' in monitoring:
        # Render node_exporter node_exporter_service_file
        render(
            node_exporter_service_file,
            'prometheus/node_exporter.service.j2',
            monitoring['node_exporter'],
        )
        if (
            'collectors' in monitoring['node_exporter']
            and 'textfile' in monitoring['node_exporter']['collectors']
        ):
            # Create textcollector folder
            if not os.path.isdir(node_exporter_collector_path):
                os.makedirs(node_exporter_collector_path)

    if 'frr_exporter' in monitoring:
        # Render frr_exporter service_file
        render(
            frr_exporter_service_file,
            'prometheus/frr_exporter.service.j2',
            monitoring['frr_exporter'],
        )

    if 'blackbox_exporter' in monitoring:
        # Render blackbox_exporter service_file
        render(
            blackbox_exporter_service_file,
            'prometheus/blackbox_exporter.service.j2',
            monitoring['blackbox_exporter'],
        )
        # Render blackbox_exporter config file
        render(
            '/run/blackbox_exporter/config.yml',
            'prometheus/blackbox_exporter.yml.j2',
            monitoring['blackbox_exporter'],
        )

    return None


def apply(monitoring):
    # Reload systemd manager configuration
    call('systemctl daemon-reload')
    if not monitoring or 'node_exporter' not in monitoring:
        call(f'systemctl stop {node_exporter_systemd_service}')
    if not monitoring or 'frr_exporter' not in monitoring:
        call(f'systemctl stop {frr_exporter_systemd_service}')
    if not monitoring or 'blackbox_exporter' not in monitoring:
        call(f'systemctl stop {blackbox_exporter_systemd_service}')

    if not monitoring:
        return

    if 'node_exporter' in monitoring:
        # we need to restart the service if e.g. the VRF name changed
        systemd_action = 'reload-or-restart'
        if 'node_exporter_restart_required' in monitoring:
            systemd_action = 'restart'

        call(f'systemctl {systemd_action} {node_exporter_systemd_service}')

    if 'frr_exporter' in monitoring:
        # we need to restart the service if e.g. the VRF name changed
        systemd_action = 'reload-or-restart'
        if 'frr_exporter_restart_required' in monitoring:
            systemd_action = 'restart'

        call(f'systemctl {systemd_action} {frr_exporter_systemd_service}')

    if 'blackbox_exporter' in monitoring:
        # we need to restart the service if e.g. the VRF name changed
        systemd_action = 'reload-or-restart'
        if 'blackbox_exporter_restart_required' in monitoring:
            systemd_action = 'restart'

        call(f'systemctl {systemd_action} {blackbox_exporter_systemd_service}')


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
