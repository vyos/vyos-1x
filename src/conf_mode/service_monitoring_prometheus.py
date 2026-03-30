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

from time import sleep
from sys import exit

from vyos.config import Config
from vyos.configdict import is_node_changed
from vyos.configverify import verify_vrf
from vyos.template import render
from vyos.utils.process import call
from vyos.utils.process import is_systemd_service_active
from vyos.utils.process import is_systemd_service_running
from vyos.utils.network import check_port_availability
from vyos.utils.network import is_listen_port_bind_service
from vyos.base import Warning
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

vpp_exporter_service_file = '/etc/systemd/system/vpp_exporter.service'
vpp_exporter_systemd_service = 'vpp_exporter.service'
vpp_exporter_process_name = 'vpp_prometheus_export'

vpp_stat_group_patterns = {
    'interfaces': '^/interfaces',
    'err': '^/err',
    'buffer-pools': '^/buffer-pools',
    'sys': '^/sys',
    'workers': '^/workers',
    'nodes': '^/nodes',
    'mem': '^/mem',
}
vpp_default_stat_groups = ['interfaces', 'err', 'buffer-pools', 'sys', 'workers', 'mem']


def get_node_values(node):
    if node is None:
        return []
    if isinstance(node, dict):
        return list(node.keys())
    if isinstance(node, list):
        return node
    return [node]


def build_vpp_stat_patterns(vpp_exporter):
    selected_groups = get_node_values(vpp_exporter.get('stat_group'))
    custom_patterns = get_node_values(vpp_exporter.get('stat_pattern'))

    if not selected_groups and not custom_patterns:
        selected_groups = vpp_default_stat_groups

    patterns = []
    selected_groups_set = set(selected_groups)
    for group_name, pattern in vpp_stat_group_patterns.items():
        if group_name in selected_groups_set:
            patterns.append(pattern)

    for pattern in custom_patterns:
        if pattern not in patterns:
            patterns.append(pattern)

    return patterns


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
        'vpp_exporter': base + ['vpp-exporter'],
    }

    for exporter_name, exporter_base in exporters.items():
        if conf.exists(exporter_base):
            monitoring[exporter_name] = conf.get_config_dict(
                exporter_base,
                key_mangling=('-', '_'),
                get_first_key=True,
                with_recursive_defaults=True,
            )
            if exporter_name == 'vpp_exporter':
                monitoring[exporter_name]['patterns'] = build_vpp_stat_patterns(
                    monitoring[exporter_name]
                )
                monitoring[exporter_name]['vpp_per_node_counters_enabled'] = (
                    conf.exists(
                        [
                            'vpp',
                            'settings',
                            'resource-allocation',
                            'memory',
                            'stats',
                            'per-node-counters',
                        ]
                    )
                )
                monitoring[exporter_name]['vpp_configured'] = conf.exists(['vpp'])

                configured_groups = conf.return_values(exporter_base + ['stat-group'])
                configured_patterns = conf.return_values(
                    exporter_base + ['stat-pattern']
                )

                effective_groups = conf.return_effective_values(
                    exporter_base + ['stat-group']
                )
                effective_patterns = conf.return_effective_values(
                    exporter_base + ['stat-pattern']
                )

                nodes_requested = 'nodes' in configured_groups or any(
                    pattern.startswith('^/nodes') for pattern in configured_patterns
                )
                nodes_requested_effective = 'nodes' in effective_groups or any(
                    pattern.startswith('^/nodes') for pattern in effective_patterns
                )

                monitoring[exporter_name]['nodes_selection_newly_enabled'] = (
                    nodes_requested and not nodes_requested_effective
                )
            if is_node_changed(conf, exporter_base):
                monitoring.update({f'{exporter_name}_restart_required': {}})

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

    if 'vpp_exporter' in monitoring:
        verify_vrf(monitoring['vpp_exporter'])

        port = int(monitoring['vpp_exporter']['port'])
        if check_port_availability(
            None, port, 'tcp'
        ) is not True and not is_listen_port_bind_service(
            port, vpp_exporter_process_name
        ):
            raise ConfigError(f'TCP port "{port}" is used by another service!')

        if not monitoring['vpp_exporter'].get('vpp_configured'):
            raise ConfigError(
                'No VPP configuration exists. Configure VPP before configuring VPP-exporter.'
            )

        if 'stat_group' in monitoring['vpp_exporter']:
            for group_name in get_node_values(monitoring['vpp_exporter']['stat_group']):
                if group_name not in vpp_stat_group_patterns:
                    raise ConfigError(f'Invalid stat-group "{group_name}"')

        if 'stat_pattern' in monitoring['vpp_exporter']:
            for pattern in get_node_values(monitoring['vpp_exporter']['stat_pattern']):
                if not pattern or not pattern.startswith('^/'):
                    raise ConfigError(
                        f'Invalid stat-pattern "{pattern}". Pattern must start with "^/"'
                    )

        if monitoring['vpp_exporter'].get(
            'nodes_selection_newly_enabled'
        ) and not monitoring['vpp_exporter'].get('vpp_per_node_counters_enabled'):
            Warning(
                'VPP node metrics requested but per-node-counters setting is not enabled.'
                'Enable it using below cmd for "nodes" metrics to be available:\n'
                '"set vpp settings resource-allocation memory stats per-node-counters".'
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

    if not monitoring or 'vpp_exporter' not in monitoring:
        # Delete systemd files
        if os.path.isfile(vpp_exporter_service_file):
            os.unlink(vpp_exporter_service_file)

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

    if 'vpp_exporter' in monitoring:
        # Render vpp_exporter service_file
        render(
            vpp_exporter_service_file,
            'prometheus/vpp_exporter.service.j2',
            monitoring['vpp_exporter'],
        )

    return None


def apply(monitoring):
    def run_systemctl(action, service=None, verify_running=False):
        command = f'systemctl {action}'
        if service:
            command = f'{command} {service}'

        rc = call(command)
        if rc != 0:
            if service:
                raise ConfigError(
                    f'Failed to {action} {service}. Check "journalctl -xe" for details.'
                )
            raise ConfigError(
                f'Failed to run "systemctl {action}". Check "journalctl -xe" for details.'
            )

        if verify_running and service:
            for _ in range(6):
                if is_systemd_service_running(service):
                    return
                sleep(0.5)
            raise ConfigError(
                f'{service} failed to reach running state after {action}. Check "journalctl -xe" for details.'
            )

    # Reload systemd manager configuration
    run_systemctl('daemon-reload')
    if not monitoring or 'node_exporter' not in monitoring:
        if is_systemd_service_active(node_exporter_systemd_service):
            run_systemctl('stop', node_exporter_systemd_service)
    if not monitoring or 'frr_exporter' not in monitoring:
        if is_systemd_service_active(frr_exporter_systemd_service):
            run_systemctl('stop', frr_exporter_systemd_service)
    if not monitoring or 'blackbox_exporter' not in monitoring:
        if is_systemd_service_active(blackbox_exporter_systemd_service):
            run_systemctl('stop', blackbox_exporter_systemd_service)
    if not monitoring or 'vpp_exporter' not in monitoring:
        if is_systemd_service_active(vpp_exporter_systemd_service):
            run_systemctl('stop', vpp_exporter_systemd_service)
        if os.path.isfile(vpp_exporter_service_file):
            run_systemctl('disable', vpp_exporter_systemd_service)

    if not monitoring:
        return

    if 'node_exporter' in monitoring:
        if (
            'node_exporter_restart_required' in monitoring
            or not is_systemd_service_active(node_exporter_systemd_service)
        ):
            run_systemctl('restart', node_exporter_systemd_service, verify_running=True)

    if 'frr_exporter' in monitoring:
        if (
            'frr_exporter_restart_required' in monitoring
            or not is_systemd_service_active(frr_exporter_systemd_service)
        ):
            run_systemctl('restart', frr_exporter_systemd_service, verify_running=True)

    if 'blackbox_exporter' in monitoring:
        if (
            'blackbox_exporter_restart_required' in monitoring
            or not is_systemd_service_active(blackbox_exporter_systemd_service)
        ):
            run_systemctl(
                'restart', blackbox_exporter_systemd_service, verify_running=True
            )

    if 'vpp_exporter' in monitoring:
        run_systemctl('enable', vpp_exporter_systemd_service)
        if (
            'vpp_exporter_restart_required' in monitoring
            or not is_systemd_service_active(vpp_exporter_systemd_service)
        ):
            run_systemctl('restart', vpp_exporter_systemd_service, verify_running=True)


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
