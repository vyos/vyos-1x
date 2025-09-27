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

import sys
import time

from pathlib import Path

from vyos import ConfigError
from vyos.base import Warning
from vyos.config import Config
from vyos.configdiff import Diff
from vyos.configdiff import get_config_diff
from vyos.template import render
from vyos.utils.process import call
from vyos.utils.process import cmd
from vyos.utils.process import rc_cmd
from vyos.utils.dict import dict_search
from vyos.utils.dict import dict_search_recursive
from vyos.utils.dict import dict_set_nested
from vyos.configdict import node_changed
from vyos.utils.network import get_bridge_master
from vyos.utils.network import interface_exists

zerotier_config = Path('/config/vyos-generated-zerotier')
systemd_unit_path = Path('/run/systemd/system')
controller_api_key = Path('/config/vyos-zerotier/zt_controller_api_key.secret')

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['interfaces','zerotier']
    zerotier = {
        'interfaces': conf.get_config_dict(
            base,
            key_mangling=('-', '_'),
            no_tag_node_value_mangle=True,
            get_first_key=True,
            with_recursive_defaults=True,
        )
    }

    # If the base node changed, an interface was deleted
    tmp = node_changed(conf, base)
    if tmp:
        zerotier['interface_remove'] = tmp

    # Check if an interface config changed at all
    expand_nodes = Diff.ADD | Diff.DELETE
    tmp = node_changed(conf, base, recursive=True, expand_nodes=expand_nodes)
    if tmp:
        zerotier['interface_changed'] = tmp

    # Get all children that may have changed for an interface
    diff = get_config_diff(conf, key_mangling=('-', '_'))
    tmp = diff.get_child_nodes_diff(base, expand_nodes=expand_nodes, recursive=True)
    diff_dict = {}

    # Restart is only required when a listening port//ip or network id is changed
    for section in ("delete", "add"):
        for iface, changes in tmp.get(section, {}).items():
            network_config = dict_search('network_config', changes)
            peer_config = dict_search('peer_config', changes)
            if network_config:
                for _, search_result in dict_search_recursive(network_config, 'blacklist'):
                    if search_result:
                        diff_dict.setdefault(iface, set()).update(changes.keys())
            elif peer_config:
                for _, search_result in dict_search_recursive(peer_config, 'blacklist'):
                    if search_result:
                        diff_dict.setdefault(iface, set()).update(changes.keys())
            else:
                diff_dict.setdefault(iface, set()).update(changes.keys())

            # Track which network-ids were removed.
            if section == 'delete' and 'network_id' in changes:
                netids = changes['network_id']
                if isinstance(netids, list):
                    dict_set_nested(f'networks_removed.{iface}', netids, zerotier)
                else:
                    dict_set_nested(f'networks_removed.{iface}', [netids], zerotier)

    for interface, interface_config in zerotier['interfaces'].items():
        # If an interface is disabled, treat it as a removal.
        if 'disable' in interface_config:
            zerotier.setdefault('interface_remove', []).append(interface)

        # Restart is only required when a listening port//ip or network id is changed
        if interface in diff_dict:
            restart_keys = {
                'network_id', 'primary', 'secondary', 'tertiary', 'interface_blacklist',
                'disable_secondary_port', 'listen_address', 'network_config', 'peer_config'
            }
            if diff_dict[interface] & restart_keys:
                zerotier.setdefault('restart_required', set()).update([interface])
            elif 'disable' in diff_dict[interface]:
                pass
            else:
                zerotier.setdefault('no_restart_required', set()).update([interface])

    return zerotier


def verify(config):
    ports = {}

    for interface, interface_config in config['interfaces'].items():
        # Define ports (if configured; otherwise None)
        primary_port = dict_search('primary.port', interface_config)
        secondary_port = dict_search('secondary.port', interface_config)
        tertiary_port = dict_search('tertiary.port', interface_config)

        # Primary port is required
        if not primary_port:
            raise ConfigError("Primary Port must be configured")

        # Network ID must be configured
        if not dict_search('network_id', interface_config):
            raise ConfigError("Network ID must be configured")

        # Check for secondary port when allow-secondary-port is false
        if secondary_port and dict_search('disable_secondary_port', interface_config) is not None:
            raise ConfigError("Secondary port cannot be set when disable-secondary-port is configured")

        # Multicore must be enabled when cpu-pinning or core-count is configured
        multicore_enabled = dict_search('multicore_options.enabled', interface_config)
        if any([dict_search('multicore_options.core_count', interface_config),
                dict_search('multicore_options.cpu_pinning', interface_config) is not None]):
            if multicore_enabled is None:
                raise ConfigError("Multicore must be enabled when cpu-pinning or core-count is configured")

        # controller-api-key must be configured if controller-api-url is set
        api_key = dict_search('controller_api_key', interface_config)
        api_url = dict_search('controller_api_url', interface_config)
        if api_url and not api_key:
            raise ConfigError("controller-api-key must be configured if controller-api-url is set")

        # Check for duplicate ports
        for port in filter(None, (primary_port, secondary_port, tertiary_port)):
            if port in ports:
                raise ConfigError(f"Port {port} already assigned to interface {dict_search(port, ports)}")
            ports[port] = interface

        # Check if user defined bonding policy is configured
        pre_defined_policies = ('active-backup', 'broadcast', 'balance-rr', 'balance-xor', 'balance-aware')
        bonding_policy = dict_search('bonding_policy', interface_config, '')
        custom_policies = dict_search('custom_policy', interface_config)
        if bonding_policy and bonding_policy not in pre_defined_policies:
            if custom_policies:
                if bonding_policy not in custom_policies:
                    raise ConfigError(f"Custom bonding policy {bonding_policy} is not configured")
            else:
                raise ConfigError(f"Custom bonding policy {bonding_policy} is not configured")

        # Check if user defined bonding policy is configured
        peer_specific_data = dict_search('peer_specific_bonds', interface_config, {})
        for node, node_config in peer_specific_data.items():
            peer_specific_bonding_policy = dict_search('bonding_policy', node_config)
            if peer_specific_bonding_policy not in pre_defined_policies:
                if custom_policies and peer_specific_bonding_policy not in custom_policies:
                    raise ConfigError(f"Custom bonding policy {peer_specific_bonding_policy} is not configured")

        if custom_policies:
            for policy_name, policy_config in custom_policies.items():
                # policy name cannot have the name of a base policy
                if policy_name in pre_defined_policies:
                    raise ConfigError(f"Policy name cannot be the same as a predefined policy")

                base_policy = dict_search('base_policy', policy_config)

                # Base policy must be set for custom bonding policy
                if not base_policy:
                    raise ConfigError(f"Base policy must be set for custom bonding policy {policy_name}")

                # link-select-method is only valid for active-backup
                if dict_search('link_select_method', policy_config) and "active-backup" not in base_policy:
                    raise ConfigError("link-select-method is only valid for active-backup bonding policy")

                links = dict_search('links', policy_config)
                if links:
                    primary_count = 0
                    for link, link_config in links.items():
                        # Check if link exists
                        if not interface_exists(link):
                            Warning(f"Interface {link} does not exist")

                        # capacity is only valid for balance-aware
                        if dict_search('capacity', link_config) and "balance-aware" not in base_policy:
                            raise ConfigError("capacity is only valid for balance-aware bonding policy")

                        # mode has no effect for broadcast bonding policy
                        if dict_search('mode', link_config) and "broadcast" in base_policy:
                            raise ConfigError("mode is not valid for broadcast bonding policy")

                        failover_to = dict_search('failover_to', link_config)
                        if failover_to:
                            # Make sure not failing over to self
                            if failover_to == link:
                                raise ConfigError("Cannot fail over to the same link")

                            # Check if the interface to failover-to exists
                            if not interface_exists(failover_to):
                                Warning(f"Interface {failover_to} does not exist")

                        # active-backup bonding policy may only have one primary link
                        if "active-backup" in base_policy:
                            if dict_search('mode', link_config) == 'primary':
                                primary_count += 1
                                if primary_count > 1:
                                    raise ConfigError("active-backup bonding policy must have only one primary link")

                link_quality = dict_search('link_quality', policy_config)
                if link_quality:
                    # link-quality is only valid for balance-aware
                    if "balance-aware" not in base_policy:
                        raise ConfigError("link-quality is only valid for balance-aware bonding policy")

                    lat_weight = dict_search('link_quality.latency_weight', policy_config)
                    pdv_weight = dict_search('link_quality.variance_weight', policy_config)

                    # Check if latency-weight or variance-weight is set, both must be set
                    if any([lat_weight, pdv_weight]) and not all([lat_weight, pdv_weight]):
                        raise ConfigError("If latency-weight or variance-weight is set, both must be set")

                    # Check if latency-weight and variance-weight add up to 1
                    if float(lat_weight) + float(pdv_weight) != 1:
                        raise ConfigError("Latency-weight and variance-weight must equal 1")


def generate(config):
    for interface, interface_config in config['interfaces'].items():
        # If an interface wasn't changed, don't generate anything new.
        if interface not in config['interface_changed']:
            continue

        network_id = dict_search('network_id', interface_config)

        # Generate systemd unit file
        unit_path = systemd_unit_path / f'vyos-zerotier-{interface}.service'
        if not unit_path.exists(): # <- don't create if it already exists
            render(str(unit_path), 'zerotier/systemd-unit.j2', {"name": interface})

        # Create interface directory
        iface_dir = zerotier_config / interface
        if not iface_dir.exists():  # <- don't create if it already exists
            iface_dir.mkdir(parents=True, exist_ok=True)

        # Generate local.conf file
        local_conf_path = iface_dir / 'local.conf'
        render(str(local_conf_path), 'zerotier/local.conf.j2', config['interfaces'][interface], rm_trail_comma=True) # <- always create

        # Create networks.d directory if it doesn't exist
        network_conf_dir = iface_dir /'networks.d'
        if not network_conf_dir.exists():  # <- don't create if it already exists
            network_conf_dir.mkdir(parents=True, exist_ok=True)

        # Generate network.conf file
        for network in network_id:
            network_conf_path = network_conf_dir / f'{network}.conf'
            if not network_conf_path.exists():
                network_conf_path.touch(exist_ok=True)

        # Generate devicemap (maps network-ids to interfaces)
        device_map_path = iface_dir / 'devicemap'
        render(str(device_map_path), 'zerotier/devicemap.j2', {"interface": interface, "network_id": network_id}) # <- always create

    return config


def apply(config):
    removed_interfaces = dict_search('interface_remove', config)
    networks_removed = dict_search('networks_removed', config)
    restart_required = dict_search('restart_required', config, [])
    no_restart_required = dict_search('no_restart_required', config, [])

    # Stop and disable interfaces that were removed.
    if removed_interfaces:
        for interface in removed_interfaces:
            unit_path = systemd_unit_path / f'vyos-zerotier-{interface}.service'
            if unit_path.exists():
                call(f'systemctl --no-block --quiet stop vyos-zerotier-{interface}.service')
                call(f'systemctl --no-block --quiet disable vyos-zerotier-{interface}.service')
                unit_path.unlink(missing_ok=True)

    # Remove network.conf files that were removed.
    if networks_removed:
        for interface, networks in networks_removed.items():
            for network in networks:
                network_conf_path = zerotier_config / interface / 'networks.d' / f'{network}.conf'
                network_local_conf_path = zerotier_config / interface / f'{network}.local.conf'
                network_conf_path.unlink(missing_ok=True)
                network_local_conf_path.unlink(missing_ok=True)

    call('systemctl daemon-reload')
    interfaces_changed = {}
    for interface, interface_config in config['interfaces'].items():
        # If an interface was removed, this was handled above.
        if removed_interfaces and interface in removed_interfaces:
            continue

        # If an interface wasn't changed, don't restart it.
        if interface not in config['interface_changed']:
            continue

        interfaces_changed[interface] = {}

        # Check if the interface is a bridge member
        for network in interface_config['network_id']:
            interfaces_changed[interface][f'{interface}.{network[:5]}'] = get_bridge_master(f'{interface}.{network[:5]}')

        # Restart the interface if a restart is required. Enable and start
        # the interface if it's a new interface or was disabled.
        if restart_required and interface in restart_required:
            call(f'systemctl --no-block --quiet restart vyos-zerotier-{interface}.service')
        # If an interface wasn't changed, don't restart it.
        elif no_restart_required and interface in no_restart_required:
            continue
        else:
            call(f'systemctl --quiet enable vyos-zerotier-{interface}.service')
            call(f'systemctl --no-block --quiet start vyos-zerotier-{interface}.service')

    # Give the interfaces time to start
    timeout = 10
    interval = 1
    for _, int_config in interfaces_changed.items():
        for interface, is_member in int_config.items():
            end = time.monotonic() + timeout
            while time.monotonic() < end:
                rc, output = rc_cmd(f'ip link show dev {interface}')
                if rc != 0:
                    time.sleep(interval)
                    continue
                break

            # After a restart, the interface would be removed as a bridge member.
            # Re-add the interface as a bridge member
            if is_member:
                cmd(f'ip link set {interface} master {is_member}')

try:
    c = get_config()
    verify(c)
    generate(c)
    apply(c)
except ConfigError as e:
    print(e)
    sys.exit(1)
