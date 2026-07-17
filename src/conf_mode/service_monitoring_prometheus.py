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

from sys import exit

from vyos.base import Warning
from vyos.config import Config
from vyos.configdict import is_node_changed
from vyos.configdict import node_changed
from vyos.configdiff import Diff
from vyos.configverify import verify_vrf
from vyos.template import render
from vyos.utils.network import check_port_availability
from vyos.utils.network import is_listen_port_bind_service
from vyos.utils.process import call
from vyos.utils.process import is_systemd_service_active
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
vpp_exporter_enable_link = '/etc/systemd/system/vpp.service.wants/vpp_exporter.service'
vpp_exporter_process_name = 'vpp_prometheus_export'

vpp_stat_group_patterns = {
    'interfaces': '^/interfaces',
    'err': '^/err',
    'buffer-pools': '^/buffer-pools',
    'system': '^/sys',
    'workers': '^/workers',
    'nodes': '^/nodes',
    'memory': '^/mem',
}
vpp_default_stat_groups = [
    'interfaces',
    'err',
    'buffer-pools',
    'system',
    'workers',
    'memory',
]


def build_vpp_stat_patterns(vpp_exporter):
    selected_groups = vpp_exporter.get('stat_group', [])
    custom_patterns = vpp_exporter.get('stat_pattern', [])

    if not selected_groups and not custom_patterns:
        selected_groups = vpp_default_stat_groups

    selected_groups = set(selected_groups)
    patterns = [
        pattern
        for group_name, pattern in vpp_stat_group_patterns.items()
        if group_name in selected_groups
    ]

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

    if 'frr_exporter' in monitoring:
        # Optional collectors to enable, translated from the CLI node name
        # to the upstream frr_exporter collector flag
        collector_flags = {'bgp_l2_vpn': 'bgpl2vpn', 'pim': 'pim'}
        collector = monitoring['frr_exporter'].get('collector', {})
        monitoring['frr_exporter']['optional_collectors'] = [
            flag for node, flag in collector_flags.items() if node in collector
        ]
        # peer-description carries a default value (json) which is merged into
        # the config dict by with_recursive_defaults - the BGP peer description
        # collector option is opt-in, so drop the default if it was never set
        if not conf.exists(
            base + ['frr-exporter', 'collector', 'bgp', 'peer-description']
        ):
            collector.get('bgp', {}).pop('peer_description', None)
    if 'vpp_exporter' in monitoring:
        vpp_exporter = monitoring['vpp_exporter']
        vpp_exporter['patterns'] = build_vpp_stat_patterns(vpp_exporter)
        vpp_exporter['vpp_per_node_counters_enabled'] = conf.exists(
            [
                'vpp',
                'settings',
                'resource-allocation',
                'memory',
                'stats',
                'per-node-counters',
            ]
        )
        vpp_exporter['vpp_configured'] = conf.exists(['vpp'])

        configured_groups = conf.return_values(base + ['vpp-exporter', 'stat-group'])
        configured_patterns = conf.return_values(
            base + ['vpp-exporter', 'stat-pattern']
        )
        effective_groups = conf.return_effective_values(
            base + ['vpp-exporter', 'stat-group']
        )
        effective_patterns = conf.return_effective_values(
            base + ['vpp-exporter', 'stat-pattern']
        )

        nodes_requested = 'nodes' in configured_groups or any(
            pattern.startswith('^/nodes') for pattern in configured_patterns
        )
        nodes_requested_effective = 'nodes' in effective_groups or any(
            pattern.startswith('^/nodes') for pattern in effective_patterns
        )
        vpp_exporter['nodes_selection_newly_enabled'] = (
            nodes_requested and not nodes_requested_effective
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
    modules_changed = node_changed(
        conf,
        base + ['blackbox-exporter', 'modules'],
        expand_nodes=Diff.ADD | Diff.DELETE,
    )
    tmp = tmp or 'icmp' in modules_changed
    if tmp:
        monitoring.update({'blackbox_exporter_restart_required': {}})

    if is_node_changed(conf, base + ['vpp-exporter']):
        monitoring.update({'vpp_exporter_restart_required': {}})

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
        vpp_exporter = monitoring['vpp_exporter']
        verify_vrf(vpp_exporter)

        if not vpp_exporter.get('vpp_configured'):
            raise ConfigError(
                'No VPP configuration exists. Configure VPP before configuring '
                'VPP-exporter.'
            )

        port = int(vpp_exporter['port'])
        if not check_port_availability(
            None, port, 'tcp', vrf=vpp_exporter.get('vrf')
        ) and not is_listen_port_bind_service(port, vpp_exporter_process_name):
            raise ConfigError(f'TCP port "{port}" is used by another service!')

        for group_name in vpp_exporter.get('stat_group', []):
            if group_name not in vpp_stat_group_patterns:
                raise ConfigError(f'Invalid stat-group "{group_name}"')

        for pattern in vpp_exporter.get('stat_pattern', []):
            if not pattern.startswith('^/'):
                raise ConfigError(
                    f'Invalid stat-pattern "{pattern}". Pattern must start with "^/"'
                )

        if vpp_exporter.get('nodes_selection_newly_enabled') and not vpp_exporter.get(
            'vpp_per_node_counters_enabled'
        ):
            Warning(
                'VPP node metrics requested but per-node-counters setting is not '
                'enabled. Enable it using the following command for "nodes" metrics '
                'to be available:\n'
                '"set vpp settings resource-allocation memory stats '
                'per-node-counters".'
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
        if os.path.islink(vpp_exporter_enable_link):
            os.unlink(vpp_exporter_enable_link)

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
    # Reload systemd manager configuration
    call('systemctl daemon-reload')
    if not monitoring or 'node_exporter' not in monitoring:
        if is_systemd_service_active(node_exporter_systemd_service):
            call(f'systemctl stop {node_exporter_systemd_service}')
    if not monitoring or 'frr_exporter' not in monitoring:
        if is_systemd_service_active(frr_exporter_systemd_service):
            call(f'systemctl stop {frr_exporter_systemd_service}')
    if not monitoring or 'blackbox_exporter' not in monitoring:
        if is_systemd_service_active(blackbox_exporter_systemd_service):
            call(f'systemctl stop {blackbox_exporter_systemd_service}')
    if not monitoring or 'vpp_exporter' not in monitoring:
        if is_systemd_service_active(vpp_exporter_systemd_service):
            call(f'systemctl stop {vpp_exporter_systemd_service}')

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

    if 'vpp_exporter' in monitoring:
        call(f'systemctl enable {vpp_exporter_systemd_service}')

        systemd_action = 'reload-or-restart'
        if 'vpp_exporter_restart_required' in monitoring:
            systemd_action = 'restart'

        call(f'systemctl {systemd_action} {vpp_exporter_systemd_service}')


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
