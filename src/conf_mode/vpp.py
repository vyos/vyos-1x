#!/usr/bin/env python3
#
# Copyright (C) VyOS Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

from pathlib import Path

from pyroute2.iproute import IPRoute

try:
    from vpp_papi import VPPIOError, VPPValueError
except ImportError:  # pylint: disable=import-error
    VPPIOError = VPPValueError = None

from vyos import ConfigError
from vyos import airbag
from vyos.base import Warning
from vyos.config import Config, config_dict_merge
from vyos.configdep import set_dependents
from vyos.configdep import call_dependents
from vyos.configdict import node_changed, is_member
from vyos.configverify import verify_interface_exists
from vyos.configverify import verify_virtual_interface_exists
from vyos.ifconfig import Section
from vyos.logger import getLogger
from vyos.template import render
from vyos.utils.boot import boot_configuration_complete
from vyos.utils.cpu import get_available_cpus
from vyos.utils.dict import dict_search
from vyos.utils.kernel import check_kmod
from vyos.utils.kernel import unload_kmod
from vyos.utils.kernel import list_loaded_modules
from vyos.utils.process import call
from vyos.utils.process import is_systemd_service_active

from vyos.vpp import VPPControl
from vyos.vpp import control_host
from vyos.vpp import VppNotRunningError
from vyos.vpp.config_verify import (
    verify_vpp_remove_interface,
    verify_vpp_minimum_cpus,
    verify_vpp_minimum_memory,
    verify_vpp_cpu_cores,
    verify_vpp_memory,
    verify_vpp_statseg_size,
    verify_vpp_interfaces_dpdk_num_queues,
    verify_routes_count,
    verify_vpp_main_heap_size,
    verify_vpp_buffers,
)
from vyos.vpp.config_resource_checks import memory
from vyos.vpp.config_resource_checks.resource_defaults import default_resource_map
from vyos.vpp.config_filter import iface_filter_eth
from vyos.vpp.utils import EthtoolGDrvinfo
from vyos.vpp.utils import cli_ethernet_with_vifs_ifaces
from vyos.vpp.configdb import JSONStorage

airbag.enable()

service_name = 'vpp'
service_conf = Path(f'/run/vpp/{service_name}.conf')
systemd_override = '/run/systemd/system/vpp.service.d/10-override.conf'

vpp_log = getLogger(
    service_name, format='%(filename)s[%(process)d]: %(message)s', address='/dev/log'
)

dependency_interface_type_map = {
    'vpp_interfaces_bonding': 'bonding',
    'vpp_interfaces_bridge': 'bridge',
    'vpp_interfaces_gre': 'gre',
    'vpp_interfaces_ipip': 'ipip',
    'vpp_interfaces_loopback': 'loopback',
    'vpp_interfaces_vxlan': 'vxlan',
    'vpp_interfaces_xconnect': 'xconnect',
}

# dict of drivers that needs to be overridden
override_drivers: dict[str, str] = {
    'hv_netvsc': 'uio_hv_generic',
}

# drivers that does not use PCIe addresses
not_pci_drv: list[str] = ['hv_netvsc']

# drivers that support interrupt RX mode for DPDK and XDP
drivers_support_interrupt: dict[str, list] = {
    'atlantic': ['dpdk', 'xdp'],
    'bnx2x': ['dpdk'],
    'e1000': ['dpdk'],
    'ena': ['dpdk', 'xdp'],
    'i40e': ['dpdk', 'xdp'],
    'ice': ['dpdk', 'xdp'],
    'igb': ['xdp'],
    'igc': ['dpdk', 'xdp'],
    'ixgbe': ['dpdk', 'xdp'],
    'qede': ['dpdk', 'xdp'],
    'vmxnet3': ['xdp'],
    'virtio_net': ['xdp'],
}

# drivers that require changing channels (half the maximum number of RX/TX queues)
ethtool_channels_change_drv: list[str] = ['ena', 'gve']

# List of NICs where VPP activation is supported
SUPPORTED_PCI_IDS = (
    '15b3:1019',  # Mellanox Technologies MT28800 Family [ConnectX-5 Ex]
    '15b3:101d',  # Mellanox Technologies MT2892 Family [ConnectX-6 Dx]
    '15b3:101e',  # Mellanox Technologies ConnectX Family mlx5Gen Virtual Function
    '8086:1592',  # Intel Corporation Ethernet Controller E810-C for QSFP
    '1ae0:0042',  # Google, Inc. Compute Engine Virtual Ethernet [gVNIC]
    '1af4:1000',  # Red Hat, Inc. Virtio network device (legacy ID)
    '1af4:1041',  # Red Hat, Inc. Virtio network device (modern ID)
    '1d0f:ec20',  # Amazon.com, Inc. Elastic Network Adapter (ENA)
)
SUPPORTED_DRIVERS = (
    'hv_netvsc',  # Microsoft Hyper-V network interface card
)


def _load_module(module_name: str):
    """
    Load a kernel module

    Args:
        module_name (str): Name of the module to load.
    """
    if module_name in list_loaded_modules():
        vpp_log.info(f"Module '{module_name}' is already loaded")
        return
    try:
        check_kmod(module_name)
        vpp_log.info(f"Module '{module_name}' loaded successfully")
    except Exception as e:
        vpp_log.error(f"Failed to load module '{module_name}': {e}")
        raise


def _unload_module(module_name: str):
    """
    Unload a kernel module

    Args:
        module_name (str): Name of the module to unload.
    """
    if module_name not in list_loaded_modules():
        vpp_log.info(f"Module '{module_name}' is not loaded")
        return
    try:
        unload_kmod(module_name)
        vpp_log.info(f"Module '{module_name}' unloaded successfully")
    except Exception as e:
        vpp_log.error(f"Failed to unload module '{module_name}': {e}")
        raise


def _configure_vpp_cpu_settings(config: dict):
    """Configure VPP CPU settings: main-core, workers and skip-cores based on 'cpu-cores'"""
    cpu_cores = int(config['settings']['resource_allocation']['cpu_cores'])
    reserved_cpus = default_resource_map.get('reserved_cpu_cores')

    # Get sorted list of available CPU IDs
    available = sorted({cpu['cpu'] for cpu in get_available_cpus()})

    if reserved_cpus < len(available):
        main_core = available[reserved_cpus]  # first non-reserved CPU
        config['settings']['cpu'] = {
            'main_core': str(main_core),
            'skip_cores': str(reserved_cpus),
        }
        if cpu_cores > 1:
            config['settings']['cpu']['workers'] = str(cpu_cores - 1)


def _normalize_buffers(config: dict):
    """Replace 'auto' buffers_per_numa with calculated value"""
    if (
        config['settings']['resource_allocation']['buffers']['buffers_per_numa']
        == 'auto'
    ):
        buffers = memory.buffers_required(config['settings'])
        config['settings']['resource_allocation']['buffers']['buffers_per_numa'] = str(
            buffers
        )


def _get_max_xdp_rx_queues(config: dict):
    """
    Count max number of RX queues for XDP driver
    - If the interface driver is in `ethtool_channels_change_drv`
      only half of the available queues are used (to avoid NIC issues)
    - For other interface drivers the full number of queues is returned.
    - If neither `rx` nor `combined` is set, return 1.
    """
    for key in ('rx', 'combined'):
        value = config['channels'].get(key)
        if value:
            if config['original_driver'] in ethtool_channels_change_drv:
                return max(1, int(value) // 2)
            else:
                return int(value)

    return 1


def _is_device_allowed(config: dict, iface: str):
    """
    Determines if a network interface device is allowed to be used
    with VPP based on its PCI ID or driver.
    """
    if 'allow_unsupported_nics' in config['settings']:
        return True

    persist_config = dict_search(f'persist_config.{iface}', config, default={})

    pci_id = persist_config.get('pci_id')
    # PCI ID is sufficient by itself, if presented
    if pci_id is not None and pci_id in SUPPORTED_PCI_IDS:
        return True

    # If the PCI ID did not match or does not exist, fall back to a driver
    original_driver = persist_config.get('original_driver')
    if original_driver is not None and original_driver in SUPPORTED_DRIVERS:
        return True

    return False


def get_config(config=None):
    # use persistent config to store interfaces data between executions
    # this is required because some interfaces after they are connected
    # to VPP is really hard or impossible to restore without knowing
    # their original parameters (like IDs)
    with JSONStorage('vpp_conf') as persist_config:
        eth_ifaces_persist: dict[str, dict[str, str]] = persist_config.read(
            'eth_ifaces', {}
        )

    if config:
        conf = config
    else:
        conf = Config()

    base = ['vpp']
    base_settings = ['vpp', 'settings']

    # find interfaces removed from VPP
    effective_config = conf.get_config_dict(
        base,
        key_mangling=('-', '_'),
        effective=True,
        get_first_key=True,
        no_tag_node_value_mangle=True,
    )

    removed_ifaces = []
    tmp = node_changed(conf, base_settings + ['interface'])
    if tmp:
        for removed_iface in tmp:
            to_append = {
                'iface_name': removed_iface,
                'driver': 'dpdk',
            }
            removed_ifaces.append(to_append)
            # add an interface to a list of interfaces that need
            # to be reinitialized after the commit
            set_dependents('ethernet', conf, removed_iface)

    # Get interfaces that should be used in PPPoE for control-plane integration
    pppoe_ifaces = conf.get_config_dict(
        ['service', 'pppoe-server', 'interface'],
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
    )
    changed_pppoe_ifaces = [
        iface for iface in pppoe_ifaces if iface.split('.')[0] in tmp
    ]

    interfaces_config = conf.get_config_dict(
        ['interfaces', 'vpp'],
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
        with_defaults=True,
        with_recursive_defaults=True,
    )

    if not conf.exists(base):
        if changed_pppoe_ifaces:
            set_dependents('pppoe_server', conf)
        return {
            'removed_ifaces': removed_ifaces,
            'persist_config': eth_ifaces_persist,
            'interfaces_vpp': interfaces_config,
            'pppoe_ifaces': pppoe_ifaces,
            'remove': {},
        }

    config = conf.get_config_dict(
        base,
        get_first_key=True,
        key_mangling=('-', '_'),
        no_tag_node_value_mangle=True,
    )

    # Get default values which we need to conditionally update into the
    # dictionary retrieved.
    default_values = conf.get_config_defaults(**config.kwargs, recursive=True)

    # Since XDP is no longer configurable via the CLI (T8202),
    # this code is kept commented out to simplify reintroducing XDP in the future.
    #
    # # delete driver-incompatible defaults
    # for iface, iface_config in config.get('settings', {}).get('interface', {}).items():
    #     if iface_config.get('driver') == 'dpdk':
    #         del default_values['settings']['interface'][iface]['xdp_options']
    #     elif iface_config.get('driver') == 'xdp':
    #         del default_values['settings']['interface'][iface]['dpdk_options']

    config = config_dict_merge(default_values, config)

    # add running config
    if effective_config:
        default_values_effective = conf.get_config_defaults(
            **effective_config.kwargs, recursive=True
        )
        effective_config = config_dict_merge(default_values_effective, effective_config)
        # Buffer normalization (auto → computed)
        _normalize_buffers(effective_config)
        for iface_config in effective_config['settings']['interface'].values():
            iface_config['driver'] = 'dpdk'
        config['effective'] = effective_config

    # Save important info about all interfaces that cannot be retrieved later
    # Add new interfaces (only if they are first time seen in a config)
    for iface, iface_config in config.get('settings', {}).get('interface', {}).items():
        if iface not in effective_config.get('settings', {}).get('interface', {}):
            eth_ifaces_persist[iface] = {
                'original_driver': EthtoolGDrvinfo(iface).driver,
            }
            eth_ifaces_persist[iface]['bus_id'] = control_host.get_bus_name(iface)
            eth_ifaces_persist[iface]['dev_id'] = control_host.get_dev_id(iface)
            eth_ifaces_persist[iface]['pci_id'] = control_host.get_pci_id(iface)
            eth_ifaces_persist[iface]['channels'] = control_host.get_eth_channels(iface)

    # Return to config dictionary
    config['persist_config'] = eth_ifaces_persist

    # list of all Ethernet interfaces with vifs
    ifaces_with_vifs = cli_ethernet_with_vifs_ifaces(conf, include_nested_vifs=True)

    if 'settings' in config:
        if 'interface' in config['settings']:
            interface_rx_mode = config['settings'].get('interface_rx_mode')

            for iface, iface_config in config['settings']['interface'].items():
                iface_config['driver'] = 'dpdk'

                # old_driver = leaf_node_changed(
                #     conf, base_settings + ['interface', iface, 'driver']
                # )
                #
                # if old_driver:
                #     config['settings']['interface'][iface]['driver_changed'] = {}

                # Get current kernel module, required for extra verification and
                # logic for VMBus interfaces
                config['settings']['interface'][iface]['kernel_module'] = (
                    EthtoolGDrvinfo(iface).driver
                )

                # filter unsupported config nodes
                iface_filter_eth(conf, iface)
                set_dependents('ethernet', conf, iface)
                # Interfaces with changed driver should be removed/readded
                # if old_driver and old_driver[0] == 'dpdk':
                #     removed_ifaces.append(
                #         {
                #             'iface_name': iface,
                #             'driver': 'dpdk',
                #         }
                #     )

                # Collect memberships as sets for uniqueness
                bond_member = is_member(conf, iface, 'bonding')
                bridge_member = is_member(conf, iface, 'bridge')

                # Look for VLAN interfaces of this parent
                vlans = [
                    vlan_iface
                    for vlan_iface in ifaces_with_vifs
                    if vlan_iface.startswith(f'{iface}.')
                ]
                for vlan_iface in vlans:
                    bond_member.update(is_member(conf, vlan_iface, 'bonding'))
                    bridge_member.update(is_member(conf, vlan_iface, 'bridge'))

                # Store as lists
                if bond_member:
                    iface_config['bond_member'] = list(bond_member)
                if bridge_member:
                    iface_config['bridge_member'] = list(bridge_member)

                # Get PCI address or device ID
                if iface_config['driver'] == 'dpdk':
                    if 'dpdk_options' not in iface_config:
                        iface_config['dpdk_options'] = {}
                    # Check in a persistent config first
                    id_from_persistent_conf = eth_ifaces_persist.get(iface, {}).get(
                        'dev_id'
                    )
                    if id_from_persistent_conf:
                        iface_config['dpdk_options']['dev_id'] = id_from_persistent_conf
                    else:
                        try:
                            iface_to_search = iface
                            # if old_driver and old_driver[0] == 'xdp':
                            #     iface_to_search = f'defunct_{iface}'
                            iface_config['dpdk_options']['dev_id'] = (
                                control_host.get_dev_id(iface_to_search)
                            )
                        except Exception:
                            # Return empty address if all attempts failed
                            # We will catch this in verify()
                            iface_config['dpdk_options']['dev_id'] = ''
                # prepare XDP interface parameters
                if iface_config['driver'] == 'xdp':
                    xdp_api_params = {
                        'rxq_size': int(iface_config['xdp_options']['rx_queue_size']),
                        'txq_size': int(iface_config['xdp_options']['tx_queue_size']),
                    }
                    if iface_config['xdp_options']['num_rx_queues'] == 'all':
                        # 65535 is used as special value to request all available queues
                        xdp_api_params['rxq_num'] = 65535
                    else:
                        xdp_api_params['rxq_num'] = int(
                            iface_config['xdp_options']['num_rx_queues']
                        )
                    if 'zero-copy' in iface_config['xdp_options']:
                        xdp_api_params['mode'] = 'zero-copy'
                    if (
                        interface_rx_mode in ('interrupt', 'adaptive')
                        and int(config['settings']['resource_allocation']['cpu_cores'])
                        > 1
                    ):
                        xdp_api_params['flags'] = 'no_syscall_lock'
                    iface_config['xdp_api_params'] = xdp_api_params

        # Buffer normalization (auto → computed)
        _normalize_buffers(config)
        # Configure VPP main-core and workers 'cpu-cores' settings
        _configure_vpp_cpu_settings(config)

    if removed_ifaces:
        config['removed_ifaces'] = removed_ifaces

    config['interfaces_vpp'] = interfaces_config

    # Dependencies
    for dependency, interface_type in dependency_interface_type_map.items():
        if conf.exists(['interfaces', 'vpp', interface_type]):
            for iface, iface_config in interfaces_config.get(
                interface_type, {}
            ).items():
                set_dependents(dependency, conf, iface)

    config['ipoe_conf'] = conf.get_config_dict(
        ['service', 'ipoe-server'],
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
    )

    # NAT dependency
    if conf.exists(['vpp', 'nat', 'nat44']):
        set_dependents('vpp_nat_nat44', conf)
    if conf.exists(['vpp', 'nat', 'cgnat']):
        set_dependents('vpp_nat_cgnat', conf)

    # sFlow dependency
    if conf.exists(['vpp', 'sflow']):
        set_dependents('vpp_sflow', conf)

    # ACL dependency
    if conf.exists(['vpp', 'acl']):
        set_dependents('vpp_acl', conf)

    # IPFIX dependency
    if conf.exists(['vpp', 'ipfix']):
        set_dependents('vpp_ipfix', conf)

    # PPPoE dependency
    added_pppoe_ifaces = [
        iface
        for iface in pppoe_ifaces
        if iface.split('.')[0] in config.get('settings', {}).get('interface', {})
    ]
    changed_pppoe_ifaces.extend(added_pppoe_ifaces)
    if changed_pppoe_ifaces:
        set_dependents('pppoe_server', conf)
    config['changed_pppoe_ifaces'] = changed_pppoe_ifaces

    return config


def verify(config):
    if config.get('interfaces_vpp') and 'remove' in config:
        raise ConfigError(
            'VPP cannot be removed while VPP interfaces exist. Remove all "interfaces vpp" first!'
        )

    # Find PPPoE ifaces where the base matches any VPP interface (base or VLAN)
    pppoe_vpp_ifaces = [
        iface for iface in config.get('pppoe_ifaces', {}) if iface.startswith('vpp')
    ]
    if 'remove' in config and pppoe_vpp_ifaces:
        raise ConfigError(
            f'Cannot remove VPP: PPPoE server still uses VPP interface(s): {", ".join(pppoe_vpp_ifaces)}'
        )

    # bail out early - looks like removal from running config
    if not config or 'remove' in config:
        return None

    # Check removed interfaces (and their VLANs) against all VPP features
    for removed_iface in config.get('removed_ifaces', []):
        verify_vpp_remove_interface(
            removed_iface['iface_name'], config, match_vlans=True
        )

    if 'settings' not in config:
        raise ConfigError('"settings interface" is required but not set!')

    if 'interface' not in config['settings']:
        raise ConfigError('"settings interface" is required but not set!')

    ipoe_ifaces = list(
        {
            iface
            for iface in config['settings']['interface']
            for ipoe_iface in config.get('ipoe_conf', {}).get('interface', {})
            if iface == ipoe_iface or ipoe_iface.startswith(f'{iface}.')
        }
    )
    if ipoe_ifaces:
        raise ConfigError(
            f'Interface(s) {", ".join(ipoe_ifaces)} cannot be added to VPP because '
            'IPoE is already configured. An interface cannot be used by both VPP and IPoE!'
        )

    # check if the system meets minimal requirements
    verify_vpp_minimum_memory()

    # check if Ethernet interfaces exist
    ethernet_ifaces = Section.interfaces('ethernet')
    for iface in config['settings']['interface'].keys():
        if iface not in ethernet_ifaces:
            raise ConfigError(f'Interface {iface} does not exist or is not Ethernet!')

    # Resource usage checks
    cpu_cores = int(config['settings']['resource_allocation']['cpu_cores'])
    verify_vpp_minimum_cpus()
    verify_vpp_cpu_cores(cpu_cores)

    verify_vpp_main_heap_size(config['settings'])
    verify_vpp_statseg_size(config['settings'])

    # Check buffers
    verify_vpp_buffers(config['settings'])

    # Check if available memory is enough for current VPP config
    verify_vpp_memory(config)

    interface_rx_mode = config['settings'].get('interface_rx_mode')

    # ensure DPDK/XDP settings are properly configured
    for iface, iface_config in config['settings']['interface'].items():
        if not _is_device_allowed(config, iface):
            raise ConfigError(
                f'NIC used by "{iface}" is not validated for VPP on VyOS. '
                'Using it is unsafe and unsupported and will void support for the entire system. '
                'To proceed at your own risk, enable: "set vpp settings allow-unsupported-nics".'
            )

        err_message = f'Cannot add {iface} to VPP - '
        if 'bond_member' in iface_config:
            raise ConfigError(
                err_message
                + f'interface (or its VLAN) is a member of bond(s): {", ".join(iface_config["bond_member"])}'
            )
        if 'bridge_member' in iface_config:
            raise ConfigError(
                err_message
                + f'interface (or its VLAN) is a member of bridge(s): {", ".join(iface_config["bridge_member"])}'
            )

        if iface_config['driver'] == 'xdp' and 'xdp_options' in iface_config:
            if iface_config['xdp_options']['num_rx_queues'] != 'all':
                rx_queues = iface_config['xdp_api_params']['rxq_num']
                max_rx_queues = _get_max_xdp_rx_queues(config['persist_config'][iface])
                if rx_queues > max_rx_queues:
                    raise ConfigError(
                        f'Maximum supported number of RX queues for interface {iface} is {max_rx_queues}. '
                        f'Please set "xdp-options num-rx-queues" to {max_rx_queues} or fewer'
                    )

                Warning(f'Not all RX queues will be connected to VPP for {iface}!')

        if iface_config['driver'] == 'dpdk':
            if 'num_rx_queues' in iface_config:
                rx_queues = int(iface_config['num_rx_queues'])
                verify_vpp_interfaces_dpdk_num_queues(
                    qtype='receive', num_queues=rx_queues, workers=cpu_cores
                )

            if 'num_tx_queues' in iface_config:
                tx_queues = int(iface_config['num_tx_queues'])
                verify_vpp_interfaces_dpdk_num_queues(
                    qtype='transmit', num_queues=tx_queues, workers=cpu_cores
                )

        # RX-mode verification
        rx_mode = interface_rx_mode
        if rx_mode and rx_mode != 'polling':
            # By default drivers operate in polling mode. Not all NIC drivers support
            # RX mode interrupt and adaptive
            driver = config.get('persist_config').get(iface).get('original_driver')
            if (
                driver not in drivers_support_interrupt
                or iface_config['driver'] not in drivers_support_interrupt[driver]
            ):
                raise ConfigError(
                    f'RX mode {rx_mode} is not supported for interface {iface}'
                )

    verify_routes_count(config['settings'])

    for pppoe_iface in config.get('changed_pppoe_ifaces', []):
        if '.' in pppoe_iface:
            verify_virtual_interface_exists(config, pppoe_iface)
        else:
            verify_interface_exists(config, pppoe_iface)


def generate(config):
    if not config or 'remove' in config:
        # Remove old config and return
        service_conf.unlink(missing_ok=True)
        return None

    render(service_conf, 'vpp/startup.conf.j2', config['settings'])
    render(systemd_override, 'vpp/override.conf.j2', config)

    return None


def initialize_interface(iface, driver, iface_config) -> None:
    # DPDK - rescan PCI to use a proper driver
    if driver == 'dpdk' and iface_config['original_driver'] not in not_pci_drv:
        # 'gve' devices require a specific unbind/bind process instead of a standard PCI rescan.
        if iface_config['original_driver'] == 'gve':
            control_host.rebind_gve_driver(
                iface, iface_config['bus_id'], iface_config['dev_id']
            )
        else:
            control_host.pci_rescan(iface_config['dev_id'])
        # rename to the proper name
        iface_new_name: str = control_host.get_eth_name(iface_config['dev_id'])
        control_host.rename_iface(iface_new_name, iface)

    # XDP - rename an interface, disable promisc and XDP, set original channels
    if driver == 'xdp':
        control_host.set_promisc(f'defunct_{iface}', 'off')
        control_host.rename_iface(f'defunct_{iface}', iface)
        control_host.xdp_remove(iface)
        if iface_config['original_driver'] in ethtool_channels_change_drv:
            control_host.set_eth_channels(iface, iface_config['channels'])

    # Rename Mellanox NIC to a normal name
    try:
        if control_host.get_eth_driver(f'defunct_{iface}') == 'mlx5_core':
            control_host.rename_iface(f'defunct_{iface}', iface)
    except Exception:
        pass

    # Replace a driver with original for VMBus interfaces and rename it
    if driver == 'dpdk' and iface_config['original_driver'] in override_drivers:
        control_host.override_driver(iface_config['bus_id'], iface_config['dev_id'])
        iface_new_name: str = control_host.get_eth_name(iface_config['dev_id'])
        control_host.rename_iface(iface_new_name, iface)


def apply(config):
    # modrpobe modules
    modules = ('vfio_iommu_type1', 'vfio_pci', 'vfio_pci_core', 'vfio')
    # Open persistent config
    # It is required for operations with interfaces
    if not config or 'remove' in config:
        # Cleanup persistent config
        with JSONStorage('vpp_conf') as persist_config:
            persist_config.delete()
        # And stop the service
        call(f'systemctl stop {service_name}.service')
        # Unlod modules (modprobe -r)
        for module in modules:
            _unload_module(module)
    else:
        # Some interfaces required extra preparation before VPP can be started
        if 'settings' in config and 'interface' in config.get('settings'):
            # modprobe vfio
            if any(
                iface_config.get('driver') == 'dpdk'
                for iface_config in config['settings']['interface'].values()
            ):
                for module in modules:
                    _load_module(module)

            for iface, iface_config in config['settings']['interface'].items():
                if iface_config['driver'] == 'dpdk':
                    # ena interfaces require noiommu mode
                    if iface_config['kernel_module'] == 'ena':
                        control_host.unsafe_noiommu_mode(True)

                    original_driver = config['persist_config'][iface]['original_driver']
                    effective_ifaces = (
                        config.get('effective', {})
                        .get('settings', {})
                        .get('interface', {})
                    )
                    # Check if the driver needs to be overridden:
                    # either the kernel module requires it, or the interface is being switched
                    # from XDP (hv_netvsc) to DPDK (T7797)
                    override_xdp_to_dpdk = (
                        effective_ifaces.get(iface, {}).get('driver') == 'xdp'
                        and original_driver == 'hv_netvsc'
                    )
                    k_module = (
                        original_driver
                        if override_xdp_to_dpdk
                        else iface_config['kernel_module']
                    )
                    if (
                        iface_config['kernel_module'] in override_drivers
                        or override_xdp_to_dpdk
                    ):
                        control_host.override_driver(
                            config['persist_config'][iface]['bus_id'],
                            config['persist_config'][iface]['dev_id'],
                            override_drivers[k_module],
                        )

        call('systemctl daemon-reload')
        call(f'systemctl restart {service_name}.service')

    # Initialize interfaces removed from VPP
    for iface in config.get('removed_ifaces', []):
        initialize_interface(
            iface['iface_name'],
            iface['driver'],
            config['persist_config'][iface['iface_name']],
        )

        # Remove what is not in the config anymore
        if iface['iface_name'] not in config.get('settings', {}).get('interface', {}):
            del config['persist_config'][iface['iface_name']]

    if 'settings' in config and 'interface' in config.get('settings'):
        interface_rx_mode = config['settings'].get('interface_rx_mode')

        # connect to VPP
        try:
            # Bail out early if VPP service is not running
            if not is_systemd_service_active(f'{service_name}.service'):
                raise VppNotRunningError(
                    'VPP service is not running or failed to start'
                )

            vpp_control = VPPControl()

            # preconfigure LCP plugin
            if 'ignore_kernel_routes' in config['settings']:
                vpp_control.cli_cmd('lcp param route-no-paths off')
            else:
                vpp_control.cli_cmd('lcp param route-no-paths on')
            # add interfaces
            iproute = IPRoute()
            for iface, iface_config in config['settings']['interface'].items():
                # add XDP interfaces
                if iface_config['driver'] == 'xdp':
                    control_host.rename_iface(iface, f'defunct_{iface}')

                    # Some cloud NICs fail to load XDP if all RX queues are configured. To avoid this,
                    # we limit the number of queues to half of the maximum supported by the driver.
                    if (
                        config['persist_config'][iface]['original_driver']
                        in ethtool_channels_change_drv
                    ):
                        max_rx_queues = _get_max_xdp_rx_queues(
                            config['persist_config'][iface]
                        )
                        channels_orig = config['persist_config'][iface]['channels']
                        channels = {}
                        if channels_orig.get('rx'):
                            channels = {'rx': max_rx_queues, 'tx': max_rx_queues}
                        if channels_orig.get('combined'):
                            channels['combined'] = max_rx_queues
                        if channels:
                            control_host.set_eth_channels(f'defunct_{iface}', channels)

                    vpp_control.xdp_iface_create(
                        host_if=f'defunct_{iface}',
                        name=iface,
                        **iface_config['xdp_api_params'],
                    )
                    # replicate MAC address of a real interface
                    real_mac = control_host.get_eth_mac(f'defunct_{iface}')
                    vpp_control.set_iface_mac(iface, real_mac)
                    if 'promisc' in iface_config['xdp_options']:
                        control_host.set_promisc(f'defunct_{iface}', 'on')
                    control_host.set_status(f'defunct_{iface}', 'up')
                    control_host.flush_ip(f'defunct_{iface}')
                # Rename Mellanox interfaces to hide them and create LCP properly
                if (
                    iface in Section.interfaces()
                    and control_host.get_eth_driver(iface) == 'mlx5_core'
                ):
                    control_host.rename_iface(iface, f'defunct_{iface}')
                    control_host.set_status(f'defunct_{iface}', 'up')
                    control_host.flush_ip(f'defunct_{iface}')
                # Create lcp
                if iface not in Section.interfaces():
                    vpp_control.lcp_pair_add(iface, iface)

                # For unknown reasons, if multiple interfaces later try to be
                # initialized by configuration scripts, some of them may stuck
                # in an endless UP/DOWN loop
                # We found two workarounds - pause initialization (requires
                # main code modifications).
                # And this one
                dev_index = iproute.link_lookup(ifname=iface)[0]
                iproute.link('set', index=dev_index, state='up')

                # Set rx-mode. Should be configured after interface state set to UP
                rx_mode = interface_rx_mode
                if rx_mode:
                    # to hardware side
                    vpp_control.iface_rxmode(iface, rx_mode)
                    # to kernel side
                    lcp_name = vpp_control.lcp_pair_find(vpp_name_hw=iface).get(
                        'vpp_name_kernel'
                    )
                    vpp_control.iface_rxmode(lcp_name, rx_mode)

            # Synchronize routes via LCP
            vpp_control.lcp_resync()

        except (VPPIOError, VPPValueError, VppNotRunningError) as e:
            # if cannot connect to VPP or an error occurred then
            # we need to stop vpp service and initialize interfaces
            call(f'systemctl stop {service_name}.service')
            for iface, iface_config in config['settings']['interface'].items():
                initialize_interface(
                    iface, iface_config['driver'], config['persist_config'][iface]
                )

            raise ConfigError(
                f'An error occurred: {e}. '
                'VPP service will be restarted with the previous configuration'
            )

    # Save persistent config
    if 'persist_config' in config and config['persist_config']:
        with JSONStorage('vpp_conf') as persist_config:
            persist_config.write('eth_ifaces', config['persist_config'])

    # reinitialize interfaces, but not during the first boot
    if boot_configuration_complete():
        call_dependents()


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
