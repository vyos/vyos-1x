#!/usr/bin/env python3
#
# Copyright (C) 2018-2020 VyOS maintainers and contributors
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

from ipaddress import ip_address
from ipaddress import ip_network
from sys import exit

from vyos.config import Config
from vyos.template import render
from vyos.template import is_ipv6
from vyos.util import call
from vyos.util import dict_search
from vyos.validate import is_subnet_connected
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_file = '/run/dhcp-server/dhcpdv6.conf'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'dhcpv6-server']
    if not conf.exists(base):
        return None

    dhcpv6 = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
    return dhcpv6

def verify(dhcpv6):
    # bail out early - looks like removal from running config
    if not dhcpv6 or 'disable' in dhcpv6:
        return None

    # If DHCP is enabled we need one share-network
    if 'shared_network_name' not in dhcpv6:
        raise ConfigError('No DHCPv6 shared networks configured. At least\n' \
                          'one DHCPv6 shared network must be configured.')

    # Inspect shared-network/subnet
    subnets = []
    listen_ok = False
    for network, network_config in dhcpv6['shared_network_name'].items():
        # A shared-network requires a subnet definition
        if 'subnet' not in network_config:
            raise ConfigError(f'No DHCPv6 lease subnets configured for "{network}". At least one\n' \
                              'lease subnet must be configured for each shared network!')

        for subnet, subnet_config in network_config['subnet'].items():
            if 'address_range' in subnet_config:
                if 'start' in subnet_config['address_range']:
                    range6_start = []
                    range6_stop = []
                    for start, start_config in subnet_config['address_range']['start'].items():
                        if 'stop' not in start_config:
                            raise ConfigError(f'address-range stop address for start "{start}" is not defined!')
                        stop = start_config['stop']

                        # Start address must be inside network
                        if not ip_address(start) in ip_network(subnet):
                            raise ConfigError(f'address-range start address "{start}" is not in subnet "{subnet}"!')

                        # Stop address must be inside network
                        if not ip_address(stop) in ip_network(subnet):
                             raise ConfigError(f'address-range stop address "{stop}" is not in subnet "{subnet}"!')

                        # Stop address must be greater or equal to start address
                        if not ip_address(stop) >= ip_address(start):
                            raise ConfigError(f'address-range stop address "{stop}" must be greater or equal\n' \
                                              f'to the range start address "{start}"!')

                        # DHCPv6 range start address must be unique - two ranges can't
                        # start with the same address - makes no sense
                        if start in range6_start:
                            raise ConfigError(f'Conflicting DHCPv6 lease range:\n' \
                                              f'Pool start address "{start}" defined multipe times!')
                        range6_start.append(start)

                        # DHCPv6 range stop address must be unique - two ranges can't
                        # end with the same address - makes no sense
                        if stop in range6_stop:
                            raise ConfigError(f'Conflicting DHCPv6 lease range:\n' \
                                              f'Pool stop address "{stop}" defined multipe times!')
                        range6_stop.append(stop)

                if 'prefix' in subnet_config:
                    for prefix in subnet_config['prefix']:
                        if ip_network(prefix) not in ip_network(subnet):
                            raise ConfigError(f'address-range prefix "{prefix}" is not in subnet "{subnet}""')

            # Prefix delegation sanity checks
            if 'prefix_delegation' in subnet_config:
                if 'start' not in subnet_config['prefix_delegation']:
                    raise ConfigError('prefix-delegation start address not defined!')

                for prefix, prefix_config in subnet_config['prefix_delegation']['start'].items():
                    if 'stop' not in prefix_config:
                        raise ConfigError(f'Stop address of delegated IPv6 prefix range "{prefix}"\n'
                                          f'must be configured')

                    if 'prefix_length' not in prefix_config:
                        raise ConfigError('Length of delegated IPv6 prefix must be configured')

            # Static mappings don't require anything (but check if IP is in subnet if it's set)
            if 'static_mapping' in subnet_config:
                for mapping, mapping_config in subnet_config['static_mapping'].items():
                    if 'ipv6_address' in mapping_config:
                        # Static address must be in subnet
                        if ip_address(mapping_config['ipv6_address']) not in ip_network(subnet):
                            raise ConfigError(f'static-mapping address for mapping "{mapping}" is not in subnet "{subnet}"!')

            # Subnets must be unique
            if subnet in subnets:
                raise ConfigError('DHCPv6 subnets must be unique! Subnet {0} defined multiple times!'.format(subnet['network']))
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
        raise ConfigError('None of the DHCPv6 subnets are connected to a subnet6 on\n' \
                          'this machine. At least one subnet6 must be connected such that\n' \
                          'DHCPv6 listens on an interface!')


    return None

def generate(dhcpv6):
    # bail out early - looks like removal from running config
    if not dhcpv6 or 'disable' in dhcpv6:
        return None

    render(config_file, 'dhcp-server/dhcpdv6.conf.tmpl', dhcpv6)
    return None

def apply(dhcpv6):
    # bail out early - looks like removal from running config
    if not dhcpv6 or 'disable' in dhcpv6:
        # DHCP server is removed in the commit
        call('systemctl stop isc-dhcp-server6.service')
        if os.path.exists(config_file):
            os.unlink(config_file)

        return None

    call('systemctl restart isc-dhcp-server6.service')
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
