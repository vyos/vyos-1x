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

import ipaddress

from vyos import ConfigError

from vyos.configdiff import Diff
from vyos.configdict import node_changed
from vyos.config import Config
from vyos.utils.network import get_interface_address

from vyos.vpp.utils import cli_ifaces_list
from vyos.vpp.utils import vpp_iface_name_transform
from vyos.vpp.nat.nat44 import Nat44
from vyos.vpp.control_vpp import VPPControl


protocol_map = {
    'all': 0,
    'icmp': 1,
    'tcp': 6,
    'udp': 17,
}


def get_config(config=None) -> dict:
    if config:
        conf = config
    else:
        conf = Config()

    base = ['vpp', 'nat44']

    # Get config_dict with default values
    config = conf.get_config_dict(
        base,
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
        with_defaults=True,
        with_recursive_defaults=True,
    )

    if not conf.exists(['vpp']):
        config['remove_vpp'] = True
        return config

    # Get effective config as we need full dictionary for deletion
    effective_config = conf.get_config_dict(
        base,
        key_mangling=('-', '_'),
        effective=True,
        get_first_key=True,
        no_tag_node_value_mangle=True,
    )

    if not config:
        config['remove'] = True
        return config

    config_changed = node_changed(
        conf,
        base,
        key_mangling=('-', '_'),
        recursive=True,
        expand_nodes=Diff.DELETE | Diff.ADD,
    )

    changed_static_rules = node_changed(
        conf,
        base + ['static', 'rule'],
        key_mangling=('-', '_'),
        recursive=True,
        expand_nodes=Diff.DELETE | Diff.ADD,
    )

    changed_exclude_rules = node_changed(
        conf,
        base + ['exclude', 'rule'],
        key_mangling=('-', '_'),
        recursive=True,
        expand_nodes=Diff.DELETE | Diff.ADD,
    )

    if not config_changed:
        changed_static_rules = list(config.get('static', {}).get('rule', {}).keys())
        changed_exclude_rules = list(config.get('exclude', {}).get('rule', {}).keys())

    config.update(
        {
            'changed_static_rules': changed_static_rules,
            'changed_exclude_rules': changed_exclude_rules,
            'vpp_ifaces': cli_ifaces_list(conf),
        }
    )

    settings = conf.get_config_dict(
        ['vpp', 'settings', 'nat44'],
        key_mangling=('-', '_'),
        with_recursive_defaults=True,
    )
    config.update(settings.get('nat44'))

    if effective_config:
        config.update({'effective': effective_config})

    return config


def convert_range_to_list_ips(address_range) -> list:
    """Converts IP range to a list of IPs .

    Example:
    % ip = IPOperations('192.0.0.1-192.0.2.5')
    % ip.convert_prefix_to_list_ips()
    ['192.0.2.1', '192.0.2.2', '192.0.2.3', '192.0.2.4', '192.0.2.5']
    """
    if '-' in address_range:
        start_ip, end_ip = address_range.split('-')
        start_ip = ipaddress.ip_address(start_ip)
        end_ip = ipaddress.ip_address(end_ip)
        return [
            str(ipaddress.ip_address(ip))
            for ip in range(int(start_ip), int(end_ip) + 1)
        ]
    else:
        return [address_range]


def verify(config):
    if 'remove' in config or 'remove_vpp' in config:
        return None

    if 'interface' not in config:
        raise ConfigError('Interfaces must be configured for NAT44')

    required_keys = {'inside', 'outside'}
    missing_keys = required_keys - set(config['interface'].keys())
    if missing_keys:
        raise ConfigError(
            f'Both inside and outside interfaces must be configured. Please add: {", ".join(missing_keys)}'
        )

    vpp = VPPControl()
    for direction in ['inside', 'outside']:
        for interface in config['interface'][direction]:
            vpp_iface_name = vpp_iface_name_transform(interface)
            if vpp.get_sw_if_index(vpp_iface_name) is None:
                raise ConfigError(
                    f'{interface} must be a VPP interface for {direction} NAT interface'
                )

    if not config.get('address_pool', {}).get('translation') and not config.get(
        'static', {}
    ).get('rule'):
        raise ConfigError('"address-pool translation" or "static rule" is required')

    addresses_translation = []
    addresses_twice_nat = []
    if 'address_pool' in config:
        address_pool = config.get('address_pool')
        if 'translation' in address_pool:
            if not address_pool['translation'].get('address') and not address_pool[
                'translation'
            ].get('interface'):
                raise ConfigError(
                    '"address-pool translation" requires address or interface'
                )

            for address_range in address_pool['translation'].get('address', []):
                addresses = convert_range_to_list_ips(address_range)
                for address in addresses:
                    if address in addresses_translation:
                        raise ConfigError(
                            f'Address {address} is already in use in "address-pool translation address"'
                        )
                    addresses_translation.append(address)

            for interface in address_pool['translation'].get('interface', []):
                if interface not in config['vpp_ifaces']:
                    raise ConfigError(
                        f'{interface} must be a VPP interface for "address-pool translation interface"'
                    )
                address_info = get_interface_address(interface).get('addr_info')
                if not address_info:
                    raise ConfigError(
                        f'{interface} should have an address to be used for "address-pool translation interface"'
                    )
                iface_address = address_info[0].get('local')
                addresses_translation.append(iface_address)

        if 'twice_nat' in address_pool:
            if not address_pool['twice_nat'].get('address') and not address_pool[
                'twice_nat'
            ].get('interface'):
                raise ConfigError(
                    '"address-pool twice-nat" requires address or interface'
                )

            for address_range in address_pool['twice_nat'].get('address', []):
                addresses = convert_range_to_list_ips(address_range)
                for address in addresses:
                    if address in addresses_twice_nat:
                        raise ConfigError(
                            f'Address {address} is already in use in "address-pool twice-nat address"'
                        )
                    addresses_twice_nat.append(address)

            for interface in address_pool['twice_nat'].get('interface', []):
                if interface not in config['vpp_ifaces']:
                    raise ConfigError(
                        f'{interface} must be a VPP interface for "address-pool twice-nat interface"'
                    )
                address_info = get_interface_address(interface).get('addr_info')
                if not address_info:
                    raise ConfigError(
                        f'{interface} should have an address to be used for "address-pool twice-nat interface"'
                    )
                iface_address = address_info[0].get('local')
                addresses_twice_nat.append(iface_address)

    if 'static' in config:
        addresses_with_ports = set()
        addresses_without_ports = set()
        local_addresses = set()

        for rule, rule_config in config['static']['rule'].items():
            error_msg = f'Configuration error in static rule {rule}:'

            if not rule_config.get('local', {}).get('address'):
                raise ConfigError(f'{error_msg} local settings require address')

            if not rule_config.get('external', {}).get('address'):
                raise ConfigError(f'{error_msg} external settings require address')

            has_local_port = 'port' in rule_config.get('local', {})
            has_external_port = 'port' in rule_config.get('external', {})

            if not has_external_port == has_local_port:
                raise ConfigError(
                    f'{error_msg} source and destination ports must either '
                    'both be specified, or neither must be specified'
                )

            # Either both protocol and ports are set, or both no protocol and no ports
            if (rule_config['protocol'] != 'all') != has_local_port:
                raise ConfigError(
                    f'{error_msg} protocol and ports must either both be specified or both omitted'
                )

            ext_address = rule_config['external']['address']
            port = rule_config['external'].get('port')
            local_address = rule_config['local']['address']

            if port:
                pair = (ext_address, port)
                if (
                    pair in addresses_with_ports
                    or ext_address in addresses_without_ports
                ):
                    raise ConfigError(
                        f'{error_msg} external address/port is already in use!'
                    )
                addresses_with_ports.add(pair)

            else:
                if ext_address in addresses_without_ports or any(
                    addr == ext_address for addr, _ in addresses_with_ports
                ):
                    raise ConfigError(
                        f'{error_msg} external address is already in use!'
                    )
                addresses_without_ports.add(ext_address)

                if local_address in local_addresses:
                    raise ConfigError(
                        f'{error_msg} local address {local_address} is already in use'
                    )
                local_addresses.add(local_address)

            options = rule_config.get('options', {})

            if 'self_twice_nat' in options and ext_address not in addresses_translation:
                raise ConfigError(
                    f'{error_msg} external address {ext_address} must be part of '
                    '"address-pool translation" when using self-twice-nat'
                )

            if all(key in options for key in ('twice_nat', 'self_twice_nat')):
                raise ConfigError(
                    f'{error_msg} cannot set both options "twice-nat" and "self-twice-nat"'
                )
            if any(key in options for key in ('twice_nat', 'self_twice_nat')):
                if not has_local_port or rule_config['protocol'] == 'all':
                    raise ConfigError(
                        f'{error_msg} twice-nat/self-twice-nat options require port and protocol to be set'
                    )
                if not config.get('address_pool', {}).get('twice_nat'):
                    raise ConfigError(
                        f'{error_msg} twice-nat/self-twice-nat options require "address-pool twice-nat" to be set'
                    )
            if 'twice_nat_address' in options:
                if not any(key in options for key in ('twice_nat', 'self_twice_nat')):
                    raise ConfigError(
                        f'{error_msg} twice-nat/self-twice-nat option required when twice-nat-address is set'
                    )
                tn_address = options['twice_nat_address']
                if tn_address not in addresses_twice_nat:
                    raise ConfigError(
                        f'{error_msg} twice-nat-address {tn_address} is not in "address-pool twice-nat"'
                    )

    if 'exclude' in config:
        for rule, rule_config in config['exclude']['rule'].items():
            keys = {'local_address', 'external_interface'}
            if not any(key in rule_config for key in keys):
                raise ConfigError(
                    f'Local-address or external-interface must be specified for exclude rule {rule}'
                )
            if all(key in rule_config for key in keys):
                raise ConfigError(
                    f'Cannot set both address and interface for exclude rule {rule}'
                )
            if (
                'external_interface' in rule_config
                and rule_config.get('external_interface') not in config['vpp_ifaces']
            ):
                raise ConfigError(
                    f'{rule_config["external_interface"]} must be a VPP interface for exclude rule {rule}'
                )

            # Either both protocol and local-port are set, or both no protocol and no port
            if (rule_config['protocol'] != 'all') != ('local_port' in rule_config):
                raise ConfigError(
                    f'Protocol and local-port must either both be specified or both omitted for exclude rule {rule}'
                )


def generate(config):
    pass


def apply(config):
    if 'remove_vpp' in config:
        return None

    n = Nat44()

    if 'remove' in config:
        n.disable_nat44_ed()
        return None

    if 'effective' in config:
        remove_config = config.get('effective')
        # Delete inside interfaces
        for interface in remove_config['interface']['inside']:
            if interface not in config.get('interface', {}).get('inside', []):
                vpp_iface_name = vpp_iface_name_transform(interface)
                n.delete_nat44_interface_inside(vpp_iface_name)
        # Delete outside interfaces
        for interface in remove_config['interface']['outside']:
            if interface not in config.get('interface', {}).get('outside', []):
                vpp_iface_name = vpp_iface_name_transform(interface)
                n.delete_nat44_interface_outside(vpp_iface_name)
        # Delete address pool
        address_pool = config.get('address_pool', {})
        for address in (
            remove_config.get('address_pool', {})
            .get('translation', {})
            .get('address', [])
        ):
            if address not in address_pool.get('translation', {}).get('address', []):
                n.delete_nat44_address_range(address, twice_nat=False)
        for interface in (
            remove_config.get('address_pool', {})
            .get('translation', {})
            .get('interface', [])
        ):
            if interface not in address_pool.get('translation', {}).get(
                'interface', []
            ):
                n.delete_nat44_interface_address(interface, twice_nat=False)
        for address in (
            remove_config.get('address_pool', {})
            .get('twice_nat', {})
            .get('address', [])
        ):
            if address not in address_pool.get('twice_nat', {}).get('address', []):
                n.delete_nat44_address_range(address, twice_nat=True)
        for interface in (
            remove_config.get('address_pool', {})
            .get('twice_nat', {})
            .get('interface', [])
        ):
            if interface not in address_pool.get('twice_nat', {}).get('interface', []):
                n.delete_nat44_interface_address(interface, twice_nat=True)
        # Delete NAT static mapping rules
        for rule in config['changed_static_rules']:
            if rule in remove_config.get('static', {}).get('rule', {}):
                rule_config = remove_config['static']['rule'][rule]
                n.delete_nat44_static_mapping(
                    local_ip=rule_config.get('local').get('address'),
                    external_ip=rule_config.get('external', {}).get('address', ''),
                    local_port=int(rule_config.get('local', {}).get('port', 0)),
                    external_port=int(rule_config.get('external', {}).get('port', 0)),
                    protocol=protocol_map[rule_config.get('protocol', 'all')],
                    twice_nat='twice_nat' in rule_config.get('options', {}),
                    self_twice_nat='self_twice_nat' in rule_config.get('options', {}),
                    out2in='out_to_in_only' in rule_config.get('options', {}),
                    pool_ip=rule_config.get('options', {}).get('twice_nat_address'),
                )
        # Delete NAT exclude rules
        for rule in config['changed_exclude_rules']:
            if rule in remove_config.get('exclude', {}).get('rule', {}):
                rule_config = remove_config['exclude']['rule'][rule]
                n.delete_nat44_identity_mapping(
                    ip_address=rule_config.get('local_address'),
                    protocol=protocol_map[rule_config.get('protocol', 'all')],
                    port=int(rule_config.get('local_port', 0)),
                    interface=rule_config.get('external_interface'),
                )

    # Add NAT44
    n.enable_nat44_ed()

    # Enable/disable forwarding
    enable_forwarding = True
    if 'no_forwarding' in config:
        enable_forwarding = False
    n.enable_disable_nat44_forwarding(enable_forwarding)

    # Add inside interfaces
    for interface in config['interface']['inside']:
        vpp_iface_name = vpp_iface_name_transform(interface)
        n.add_nat44_interface_inside(vpp_iface_name)
    # Add outside interfaces
    for interface in config['interface']['outside']:
        vpp_iface_name = vpp_iface_name_transform(interface)
        n.add_nat44_interface_outside(vpp_iface_name)
    # Add translation pool
    for address in (
        config.get('address_pool', {}).get('translation', {}).get('address', [])
    ):
        n.add_nat44_address_range(address, twice_nat=False)
    for interface in (
        config.get('address_pool', {}).get('translation', {}).get('interface', [])
    ):
        n.add_nat44_interface_address(interface, twice_nat=False)
    for address in (
        config.get('address_pool', {}).get('twice_nat', {}).get('address', [])
    ):
        n.add_nat44_address_range(address, twice_nat=True)
    for interface in (
        config.get('address_pool', {}).get('twice_nat', {}).get('interface', [])
    ):
        n.add_nat44_interface_address(interface, twice_nat=True)
    # Add NAT static mapping rules
    for rule in config['changed_static_rules']:
        if rule in config.get('static', {}).get('rule', {}):
            rule_config = config['static']['rule'][rule]
            n.add_nat44_static_mapping(
                local_ip=rule_config.get('local').get('address'),
                external_ip=rule_config.get('external', {}).get('address', ''),
                local_port=int(rule_config.get('local', {}).get('port', 0)),
                external_port=int(rule_config.get('external', {}).get('port', 0)),
                protocol=protocol_map[rule_config.get('protocol', 'all')],
                twice_nat='twice_nat' in rule_config.get('options', {}),
                self_twice_nat='self_twice_nat' in rule_config.get('options', {}),
                out2in='out_to_in_only' in rule_config.get('options', {}),
                pool_ip=rule_config.get('options', {}).get('twice_nat_address'),
            )
    # Add NAT exclude rules
    for rule in config['changed_exclude_rules']:
        if rule in config.get('exclude', {}).get('rule', {}):
            rule_config = config['exclude']['rule'][rule]
            n.add_nat44_identity_mapping(
                ip_address=rule_config.get('local_address'),
                protocol=protocol_map[rule_config.get('protocol', 'all')],
                port=int(rule_config.get('local_port', 0)),
                interface=rule_config.get('external_interface'),
            )
    if 'timeout' in config:
        n.set_nat_timeouts(
            icmp=int(config.get('timeout').get('icmp')),
            udp=int(config.get('timeout').get('udp')),
            tcp_established=int(config.get('timeout').get('tcp_established')),
            tcp_transitory=int(config.get('timeout').get('tcp_transitory')),
        )


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
