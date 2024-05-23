#!/usr/bin/env python3
#
# Copyright (C) 2018-2023 VyOS maintainers and contributors
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

from glob import glob
from ipaddress import ip_address
from ipaddress import ip_network
from sys import exit

from vyos.config import Config
from vyos.template import render
from vyos.utils.process import call
from vyos.utils.file import chmod_775
from vyos.utils.file import chown
from vyos.utils.file import makedir
from vyos.utils.file import write_file
from vyos.utils.dict import dict_search
from vyos.utils.network import is_subnet_connected
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_file = '/run/kea/kea-dhcp6.conf'
ctrl_socket = '/run/kea/dhcp6-ctrl-socket'
lease_file = '/config/dhcp/dhcp6-leases.csv'
lease_file_glob = '/config/dhcp/dhcp6-leases*'
user_group = '_kea'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'dhcpv6-server']
    if not conf.exists(base):
        return None

    dhcpv6 = conf.get_config_dict(base, key_mangling=('-', '_'),
                                  get_first_key=True,
                                  no_tag_node_value_mangle=True)
    return dhcpv6

def verify(dhcpv6):
    # bail out early - looks like removal from running config
    if not dhcpv6 or 'disable' in dhcpv6:
        return None

    # If DHCP is enabled we need one share-network
    if 'shared_network_name' not in dhcpv6:
        raise ConfigError('No DHCPv6 shared networks configured. At least '\
                          'one DHCPv6 shared network must be configured.')

    # Inspect shared-network/subnet
    subnets = []
    subnet_ids = []
    listen_ok = False
    for network, network_config in dhcpv6['shared_network_name'].items():
        # A shared-network requires a subnet definition
        if 'subnet' not in network_config:
            raise ConfigError(f'No DHCPv6 lease subnets configured for "{network}". '\
                              'At least one lease subnet must be configured for '\
                              'each shared network!')

        for subnet, subnet_config in network_config['subnet'].items():
            if 'subnet_id' not in subnet_config:
                raise ConfigError(f'Unique subnet ID not specified for subnet "{subnet}"')

            if subnet_config['subnet_id'] in subnet_ids:
                raise ConfigError(f'Subnet ID for subnet "{subnet}" is not unique')

            subnet_ids.append(subnet_config['subnet_id'])

            if 'range' in subnet_config:
                range6_start = []
                range6_stop = []

                for num, range_config in subnet_config['range'].items():
                    if 'start' in range_config:
                        start = range_config['start']

                        if 'stop' not in range_config:
                            raise ConfigError(f'Range stop address for start "{start}" is not defined!')
                        stop = range_config['stop']

                        # Start address must be inside network
                        if not ip_address(start) in ip_network(subnet):
                            raise ConfigError(f'Range start address "{start}" is not in subnet "{subnet}"!')

                        # Stop address must be inside network
                        if not ip_address(stop) in ip_network(subnet):
                             raise ConfigError(f'Range stop address "{stop}" is not in subnet "{subnet}"!')

                        # Stop address must be greater or equal to start address
                        if not ip_address(stop) >= ip_address(start):
                            raise ConfigError(f'Range stop address "{stop}" must be greater than or equal ' \
                                              f'to the range start address "{start}"!')

                        # DHCPv6 range start address must be unique - two ranges can't
                        # start with the same address - makes no sense
                        if start in range6_start:
                            raise ConfigError(f'Conflicting DHCPv6 lease range: '\
                                              f'Pool start address "{start}" defined multiple times!')

                        range6_start.append(start)

                        # DHCPv6 range stop address must be unique - two ranges can't
                        # end with the same address - makes no sense
                        if stop in range6_stop:
                            raise ConfigError(f'Conflicting DHCPv6 lease range: '\
                                              f'Pool stop address "{stop}" defined multiple times!')

                        range6_stop.append(stop)

                    if 'prefix' in range_config:
                        prefix = range_config['prefix']

                        if not ip_network(prefix).subnet_of(ip_network(subnet)):
                            raise ConfigError(f'Range prefix "{prefix}" is not in subnet "{subnet}"')

            # Prefix delegation sanity checks
            if 'prefix_delegation' in subnet_config:
                if 'prefix' not in subnet_config['prefix_delegation']:
                    raise ConfigError('prefix-delegation prefix not defined!')

                for prefix, prefix_config in subnet_config['prefix_delegation']['prefix'].items():
                    if 'delegated_length' not in prefix_config:
                        raise ConfigError(f'Delegated IPv6 prefix length for "{prefix}" '\
                                          f'must be configured')

                    if 'prefix_length' not in prefix_config:
                        raise ConfigError('Length of delegated IPv6 prefix must be configured')

                    if prefix_config['prefix_length'] > prefix_config['delegated_length']:
                        raise ConfigError('Length of delegated IPv6 prefix must be within parent prefix')

                    if 'excluded_prefix' in prefix_config:
                        if 'excluded_prefix_length' not in prefix_config:
                            raise ConfigError('Length of excluded IPv6 prefix must be configured')

                        prefix_len = prefix_config['prefix_length']
                        prefix_obj = ip_network(f'{prefix}/{prefix_len}')

                        excluded_prefix = prefix_config['excluded_prefix']
                        excluded_len = prefix_config['excluded_prefix_length']
                        excluded_obj = ip_network(f'{excluded_prefix}/{excluded_len}')

                        if excluded_len <= prefix_config['delegated_length']:
                            raise ConfigError('Excluded IPv6 prefix must be smaller than delegated prefix')

                        if not excluded_obj.subnet_of(prefix_obj):
                            raise ConfigError(f'Excluded prefix "{excluded_prefix}" does not exist in the prefix')

            # Static mappings don't require anything (but check if IP is in subnet if it's set)
            if 'static_mapping' in subnet_config:
                for mapping, mapping_config in subnet_config['static_mapping'].items():
                    if 'ipv6_address' in mapping_config:
                        # Static address must be in subnet
                        if ip_address(mapping_config['ipv6_address']) not in ip_network(subnet):
                            raise ConfigError(f'static-mapping address for mapping "{mapping}" is not in subnet "{subnet}"!')

                        if ('mac' not in mapping_config and 'duid' not in mapping_config) or \
                            ('mac' in mapping_config and 'duid' in mapping_config):
                            raise ConfigError(f'Either MAC address or Client identifier (DUID) is required for '
                                              f'static mapping "{mapping}" within shared-network "{network}, {subnet}"!')

            if 'option' in subnet_config:
                if 'vendor_option' in subnet_config['option']:
                    if len(dict_search('option.vendor_option.cisco.tftp_server', subnet_config)) > 2:
                        raise ConfigError(f'No more than two Cisco tftp-servers should be defined for subnet "{subnet}"!')

            # Subnets must be unique
            if subnet in subnets:
                raise ConfigError(f'DHCPv6 subnets must be unique! Subnet {subnet} defined multiple times!')

            subnets.append(subnet)

        # DHCPv6 requires at least one configured address range or one static mapping
        # (FIXME: is not actually checked right now?)

        # There must be one subnet connected to a listen interface if network is not disabled.
        if 'disable' not in network_config:
            if is_subnet_connected(subnet):
                listen_ok = True

            # DHCPv6 subnet must not overlap. ISC DHCP also complains about overlapping
            # subnets: "Warning: subnet 2001:db8::/32 overlaps subnet 2001:db8:1::/32"
            net = ip_network(subnet)
            for n in subnets:
                net2 = ip_network(n)
                if (net != net2):
                    if net.overlaps(net2):
                        raise ConfigError('DHCPv6 conflicting subnet ranges: {0} overlaps {1}'.format(net, net2))

    if not listen_ok:
        raise ConfigError('None of the DHCPv6 subnets are connected to a subnet6 on '\
                          'this machine. At least one subnet6 must be connected such that '\
                          'DHCPv6 listens on an interface!')


    return None

def generate(dhcpv6):
    # bail out early - looks like removal from running config
    if not dhcpv6 or 'disable' in dhcpv6:
        return None

    dhcpv6['lease_file'] = lease_file
    dhcpv6['machine'] = os.uname().machine

    # Create directory for lease file if necessary
    lease_dir = os.path.dirname(lease_file)
    if not os.path.isdir(lease_dir):
        makedir(lease_dir, group='vyattacfg')
        chmod_775(lease_dir)

    # Ensure correct permissions on lease files + backups
    for file in glob(lease_file_glob):
        chown(file, user=user_group, group='vyattacfg')

    # Create lease file if necessary and let kea own it - 'kea-lfc' expects it that way
    if not os.path.exists(lease_file):
        write_file(lease_file, '', user=user_group, group=user_group, mode=0o644)

    render(config_file, 'dhcp-server/kea-dhcp6.conf.j2', dhcpv6, user=user_group, group=user_group)
    return None

def apply(dhcpv6):
    # bail out early - looks like removal from running config
    service_name = 'kea-dhcp6-server.service'
    if not dhcpv6 or 'disable' in dhcpv6:
        # DHCP server is removed in the commit
        call(f'systemctl stop {service_name}')
        if os.path.exists(config_file):
            os.unlink(config_file)
        return None

    call(f'systemctl restart {service_name}')

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
