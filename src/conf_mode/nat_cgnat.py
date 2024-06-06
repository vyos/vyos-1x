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

import ipaddress
import jmespath
import os

from sys import exit

from vyos.config import Config
from vyos.template import render
from vyos.utils.process import cmd
from vyos.utils.process import run
from vyos import ConfigError
from vyos import airbag

airbag.enable()


nftables_cgnat_config = '/run/nftables-cgnat.nft'


class IPOperations:
    def __init__(self, ip_prefix: str):
        self.ip_prefix = ip_prefix
        self.ip_network = ipaddress.ip_network(ip_prefix) if '/' in ip_prefix else None

    def get_ips_count(self) -> int:
        """Returns the number of IPs in a prefix or range.

        Example:
        % ip = IPOperations('192.0.2.0/30')
        % ip.get_ips_count()
        4
        % ip = IPOperations('192.0.2.0-192.0.2.2')
        % ip.get_ips_count()
        3
        """
        if '-' in self.ip_prefix:
            start_ip, end_ip = self.ip_prefix.split('-')
            start_ip = ipaddress.ip_address(start_ip)
            end_ip = ipaddress.ip_address(end_ip)
            return int(end_ip) - int(start_ip) + 1
        elif '/31' in self.ip_prefix:
            return 2
        elif '/32' in self.ip_prefix:
            return 1
        else:
            return sum(
                1
                for _ in [self.ip_network.network_address]
                + list(self.ip_network.hosts())
                + [self.ip_network.broadcast_address]
            )

    def convert_prefix_to_list_ips(self) -> list:
        """Converts a prefix or IP range to a list of IPs including the network and broadcast addresses.

        Example:
        % ip = IPOperations('192.0.2.0/30')
        % ip.convert_prefix_to_list_ips()
        ['192.0.2.0', '192.0.2.1', '192.0.2.2', '192.0.2.3']
        %
        % ip = IPOperations('192.0.0.1-192.0.2.5')
        % ip.convert_prefix_to_list_ips()
        ['192.0.2.1', '192.0.2.2', '192.0.2.3', '192.0.2.4', '192.0.2.5']
        """
        if '-' in self.ip_prefix:
            start_ip, end_ip = self.ip_prefix.split('-')
            start_ip = ipaddress.ip_address(start_ip)
            end_ip = ipaddress.ip_address(end_ip)
            return [
                str(ipaddress.ip_address(ip))
                for ip in range(int(start_ip), int(end_ip) + 1)
            ]
        elif '/31' in self.ip_prefix:
            return [
                str(ip)
                for ip in [
                    self.ip_network.network_address,
                    self.ip_network.broadcast_address,
                ]
            ]
        elif '/32' in self.ip_prefix:
            return [str(self.ip_network.network_address)]
        else:
            return [
                str(ip)
                for ip in [self.ip_network.network_address]
                + list(self.ip_network.hosts())
                + [self.ip_network.broadcast_address]
            ]


def generate_port_rules(
    external_hosts: list,
    internal_hosts: list,
    port_count: int,
    global_port_range: str = '1024-65535',
) -> list:
    """Generates a list of nftables option rules for the batch file.

    Args:
        external_hosts (list): A list of external host IPs.
        internal_hosts (list): A list of internal host IPs.
        port_count (int): The number of ports required per host.
        global_port_range (str): The global port range to be used. Default is '1024-65535'.

    Returns:
        list: A list containing two elements:
            - proto_map_elements (list): A list of proto map elements.
            - other_map_elements (list): A list of other map elements.
    """
    rules = []
    proto_map_elements = []
    other_map_elements = []
    start_port, end_port = map(int, global_port_range.split('-'))
    total_possible_ports = (end_port - start_port) + 1

    # Calculate the required number of ports per host
    required_ports_per_host = port_count
    current_port = start_port
    current_external_index = 0

    for internal_host in internal_hosts:
        external_host = external_hosts[current_external_index]
        next_end_port = current_port + required_ports_per_host - 1

        # If the port range exceeds the end_port, move to the next external host
        while next_end_port > end_port:
            current_external_index = (current_external_index + 1) % len(external_hosts)
            external_host = external_hosts[current_external_index]
            current_port = start_port
            next_end_port = current_port + required_ports_per_host - 1

        proto_map_elements.append(
            f'{internal_host} : {external_host} . {current_port}-{next_end_port}'
        )
        other_map_elements.append(f'{internal_host} : {external_host}')

        current_port = next_end_port + 1
        if current_port > end_port:
            current_port = start_port
            current_external_index += 1  # Move to the next external host

    return [proto_map_elements, other_map_elements]


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['nat', 'cgnat']
    config = conf.get_config_dict(
        base,
        get_first_key=True,
        key_mangling=('-', '_'),
        no_tag_node_value_mangle=True,
        with_recursive_defaults=True,
    )

    return config


def verify(config):
    # bail out early - looks like removal from running config
    if not config:
        return None

    if 'pool' not in config:
        raise ConfigError(f'Pool must be defined!')
    if 'rule' not in config:
        raise ConfigError(f'Rule must be defined!')

    for pool in ('external', 'internal'):
        if pool not in config['pool']:
            raise ConfigError(f'{pool} pool must be defined!')
        for pool_name, pool_config in config['pool'][pool].items():
            if 'range' not in pool_config:
                raise ConfigError(
                    f'Range for "{pool} pool {pool_name}" must be defined!'
                )

    external_pools_query = "keys(pool.external)"
    external_pools: list = jmespath.search(external_pools_query, config)
    internal_pools_query = "keys(pool.internal)"
    internal_pools: list = jmespath.search(internal_pools_query, config)

    used_external_pools = {}
    used_internal_pools = {}
    for rule, rule_config in config['rule'].items():
        if 'source' not in rule_config:
            raise ConfigError(f'Rule "{rule}" source pool must be defined!')
        if 'pool' not in rule_config['source']:
            raise ConfigError(f'Rule "{rule}" source pool must be defined!')

        if 'translation' not in rule_config:
            raise ConfigError(f'Rule "{rule}" translation pool must be defined!')

        # Check if pool exists
        internal_pool = rule_config['source']['pool']
        if internal_pool not in internal_pools:
            raise ConfigError(f'Internal pool "{internal_pool}" does not exist!')
        external_pool = rule_config['translation']['pool']
        if external_pool not in external_pools:
            raise ConfigError(f'External pool "{external_pool}" does not exist!')

        # Check pool duplication in different rules
        if external_pool in used_external_pools:
            raise ConfigError(
                f'External pool "{external_pool}" is already used in rule '
                f'{used_external_pools[external_pool]} and cannot be used in '
                f'rule {rule}!'
            )

        if internal_pool in used_internal_pools:
            raise ConfigError(
                f'Internal pool "{internal_pool}" is already used in rule '
                f'{used_internal_pools[internal_pool]} and cannot be used in '
                f'rule {rule}!'
            )

        used_external_pools[external_pool] = rule
        used_internal_pools[internal_pool] = rule

        # Check calculation for allocation
        external_port_range: str = config['pool']['external'][external_pool]['external_port_range']

        external_ip_ranges: list = list(
            config['pool']['external'][external_pool]['range']
        )
        internal_ip_ranges: list = config['pool']['internal'][internal_pool]['range']
        start_port, end_port = map(int, external_port_range.split('-'))
        ports_per_range_count: int = (end_port - start_port) + 1

        external_list_hosts_count = []
        external_list_hosts = []
        internal_list_hosts_count = []
        internal_list_hosts = []
        for ext_range in external_ip_ranges:
            # External hosts count
            e_count = IPOperations(ext_range).get_ips_count()
            external_list_hosts_count.append(e_count)
            # External hosts list
            e_hosts = IPOperations(ext_range).convert_prefix_to_list_ips()
            external_list_hosts.extend(e_hosts)
        for int_range in internal_ip_ranges:
            # Internal hosts count
            i_count = IPOperations(int_range).get_ips_count()
            internal_list_hosts_count.append(i_count)
            # Internal hosts list
            i_hosts = IPOperations(int_range).convert_prefix_to_list_ips()
            internal_list_hosts.extend(i_hosts)

        external_host_count = sum(external_list_hosts_count)
        internal_host_count = sum(internal_list_hosts_count)
        ports_per_user: int = int(
            config['pool']['external'][external_pool]['per_user_limit']['port']
        )
        users_per_extip = ports_per_range_count // ports_per_user
        max_users = users_per_extip * external_host_count

        if internal_host_count > max_users:
            raise ConfigError(
                f'Rule "{rule}" does not have enough ports available for the '
                f'specified parameters'
            )


def generate(config):
    if not config:
        return None

    proto_maps = []
    other_maps = []

    for rule, rule_config in config['rule'].items():
        ext_pool_name: str = rule_config['translation']['pool']
        int_pool_name: str = rule_config['source']['pool']

        # Sort the external ranges by sequence
        external_ranges: list = sorted(
            config['pool']['external'][ext_pool_name]['range'],
            key=lambda r: int(config['pool']['external'][ext_pool_name]['range'][r].get('seq', 999999))
        )
        internal_ranges: list = [range for range in config['pool']['internal'][int_pool_name]['range']]
        external_list_hosts_count = []
        external_list_hosts = []
        internal_list_hosts_count = []
        internal_list_hosts = []

        for ext_range in external_ranges:
            # External hosts count
            e_count = IPOperations(ext_range).get_ips_count()
            external_list_hosts_count.append(e_count)
            # External hosts list
            e_hosts = IPOperations(ext_range).convert_prefix_to_list_ips()
            external_list_hosts.extend(e_hosts)

        for int_range in internal_ranges:
            # Internal hosts count
            i_count = IPOperations(int_range).get_ips_count()
            internal_list_hosts_count.append(i_count)
            # Internal hosts list
            i_hosts = IPOperations(int_range).convert_prefix_to_list_ips()
            internal_list_hosts.extend(i_hosts)

        external_host_count = sum(external_list_hosts_count)
        internal_host_count = sum(internal_list_hosts_count)
        ports_per_user = int(
            jmespath.search(f'pool.external."{ext_pool_name}".per_user_limit.port', config)
        )
        external_port_range: str = jmespath.search(
            f'pool.external."{ext_pool_name}".external_port_range', config
        )

        rule_proto_maps, rule_other_maps = generate_port_rules(
            external_list_hosts, internal_list_hosts, ports_per_user, external_port_range
        )

        proto_maps.extend(rule_proto_maps)
        other_maps.extend(rule_other_maps)

    config['proto_map_elements'] = ', '.join(proto_maps)
    config['other_map_elements'] = ', '.join(other_maps)

    render(nftables_cgnat_config, 'firewall/nftables-cgnat.j2', config)

    # dry-run newly generated configuration
    tmp = run(f'nft --check --file {nftables_cgnat_config}')
    if tmp > 0:
        raise ConfigError('Configuration file errors encountered!')


def apply(config):
    if not config:
        # Cleanup cgnat
        cmd('nft delete table ip cgnat')
        if os.path.isfile(nftables_cgnat_config):
            os.unlink(nftables_cgnat_config)
        return None
    cmd(f'nft --file {nftables_cgnat_config}')


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
