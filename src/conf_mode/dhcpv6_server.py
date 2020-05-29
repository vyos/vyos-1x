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
import ipaddress

from sys import exit
from copy import deepcopy

from vyos.config import Config
from vyos.template import render
from vyos.util import call
from vyos.validate import is_subnet_connected, is_ipv6
from vyos import ConfigError

from vyos import airbag
airbag.enable()

config_file = r'/run/dhcp-server/dhcpdv6.conf'

default_config_data = {
    'preference': '',
    'disabled': False,
    'shared_network': []
}

def get_config():
    dhcpv6 = deepcopy(default_config_data)
    conf = Config()
    base = ['service', 'dhcpv6-server']
    if not conf.exists(base):
        return None
    else:
        conf.set_level(base)

    # Check for global disable of DHCPv6 service
    if conf.exists(['disable']):
        dhcpv6['disabled'] = True
        return dhcpv6

    # Preference of this DHCPv6 server compared with others
    if conf.exists(['preference']):
        dhcpv6['preference'] = conf.return_value(['preference'])

    # check for multiple, shared networks served with DHCPv6 addresses
    if conf.exists(['shared-network-name']):
        for network in conf.list_nodes(['shared-network-name']):
            conf.set_level(base + ['shared-network-name', network])
            config = {
                'name': network,
                'disabled': False,
                'subnet': []
            }

            # If disabled, the shared-network configuration becomes inactive
            if conf.exists(['disable']):
                config['disabled'] = True

            # check for multiple subnet configurations in a shared network
            if conf.exists(['subnet']):
                for net in conf.list_nodes(['subnet']):
                    conf.set_level(base + ['shared-network-name', network, 'subnet', net])
                    subnet = {
                        'network': net,
                        'range6_prefix': [],
                        'range6': [],
                        'default_router': '',
                        'dns_server': [],
                        'domain_name': '',
                        'domain_search': [],
                        'lease_def': '',
                        'lease_min': '',
                        'lease_max': '',
                        'nis_domain': '',
                        'nis_server': [],
                        'nisp_domain': '',
                        'nisp_server': [],
                        'prefix_delegation': [],
                        'sip_address': [],
                        'sip_hostname': [],
                        'sntp_server': [],
                        'static_mapping': []
                    }

                    # For any subnet on which addresses will be assigned dynamically, there must be at
                    # least one address range statement. The range statement gives the lowest and highest
                    # IP addresses in a range. All IP addresses in the range should be in the subnet in
                    # which the range statement is declared.
                    if conf.exists(['address-range', 'prefix']):
                        for prefix in conf.list_nodes(['address-range', 'prefix']):
                            range = {
                                'prefix': prefix,
                                'temporary': False
                            }

                            # Address range will be used for temporary addresses
                            if conf.exists(['address-range' 'prefix', prefix, 'temporary']):
                                range['temporary'] = True

                            # Append to subnet temporary range6 list
                            subnet['range6_prefix'].append(range)

                    if conf.exists(['address-range', 'start']):
                        for range in conf.list_nodes(['address-range', 'start']):
                            range = {
                                'start': range,
                                'stop': conf.return_value(['address-range', 'start', range, 'stop'])
                            }

                            # Append to subnet range6 list
                            subnet['range6'].append(range)

                    # The domain-search option specifies a 'search list' of Domain Names to be used
                    # by the client to locate not-fully-qualified domain names.
                    if conf.exists(['domain-search']):
                        subnet['domain_search'] = conf.return_values(['domain-search'])

                    # IPv6 address valid lifetime
                    #  (at the end the address is no longer usable by the client)
                    #  (set to 30 days, the usual IPv6 default)
                    if conf.exists(['lease-time', 'default']):
                        subnet['lease_def'] = conf.return_value(['lease-time', 'default'])

                    # Time should be the maximum length in seconds that will be assigned to a lease.
                    # The only exception to this is that Dynamic BOOTP lease lengths, which are not
                    # specified by the client, are not limited by this maximum.
                    if conf.exists(['lease-time', 'maximum']):
                        subnet['lease_max'] = conf.return_value(['lease-time', 'maximum'])

                    # Time should be the minimum length in seconds that will be assigned to a lease
                    if conf.exists(['lease-time', 'minimum']):
                        subnet['lease_min'] = conf.return_value(['lease-time', 'minimum'])

                    # Specifies a list of Domain Name System name servers available to the client.
                    # Servers should be listed in order of preference.
                    if conf.exists(['name-server']):
                        subnet['dns_server'] = conf.return_values(['name-server'])

                    # Ancient NIS (Network Information Service) domain name
                    if conf.exists(['nis-domain']):
                        subnet['nis_domain'] = conf.return_value(['nis-domain'])

                    # Ancient NIS (Network Information Service) servers
                    if conf.exists(['nis-server']):
                        subnet['nis_server'] = conf.return_values(['nis-server'])

                    # Ancient NIS+ (Network Information Service) domain name
                    if conf.exists(['nisplus-domain']):
                        subnet['nisp_domain'] = conf.return_value(['nisplus-domain'])

                    # Ancient NIS+ (Network Information Service) servers
                    if conf.exists(['nisplus-server']):
                        subnet['nisp_server'] = conf.return_values(['nisplus-server'])

                    # Local SIP server that is to be used for all outbound SIP requests - IPv6 address
                    if conf.exists(['sip-server']):
                        for value in conf.return_values(['sip-server']):
                            if is_ipv6(value):
                                subnet['sip_address'].append(value)
                            else:
                                subnet['sip_hostname'].append(value)

                    # List of local SNTP servers available for the client to synchronize their clocks
                    if conf.exists(['sntp-server']):
                        subnet['sntp_server'] = conf.return_values(['sntp-server'])

                    # Prefix Delegation (RFC 3633)
                    if conf.exists(['prefix-delegation', 'start']):
                        for address in conf.list_nodes(['prefix-delegation', 'start']):
                            conf.set_level(base + ['shared-network-name', network, 'subnet', net, 'prefix-delegation', 'start', address])
                            prefix = {
                                'start' : address,
                                'stop' : '',
                                'length' : ''
                            }

                            if conf.exists(['prefix-length']):
                                prefix['length'] = conf.return_value(['prefix-length'])

                            if conf.exists(['stop']):
                                prefix['stop'] = conf.return_value(['stop'])

                            subnet['prefix_delegation'].append(prefix)

                    #
                    # Static DHCP v6 leases
                    #
                    conf.set_level(base + ['shared-network-name', network, 'subnet', net])
                    if conf.exists(['static-mapping']):
                        for mapping in conf.list_nodes(['static-mapping']):
                            conf.set_level(base + ['shared-network-name', network, 'subnet', net, 'static-mapping', mapping])
                            mapping = {
                               'name': mapping,
                               'disabled': False,
                               'ipv6_address': '',
                               'client_identifier': '',
                            }

                            # This static lease is disabled
                            if conf.exists(['disable']):
                                mapping['disabled'] = True

                            # IPv6 address used for this DHCP client
                            if conf.exists(['ipv6-address']):
                                mapping['ipv6_address'] = conf.return_value(['ipv6-address'])

                            # This option specifies the client’s DUID identifier. DUIDs are similar but different from DHCPv4 client identifiers
                            if conf.exists(['identifier']):
                                mapping['client_identifier'] = conf.return_value(['identifier'])

                            # append static mapping configuration tu subnet list
                            subnet['static_mapping'].append(mapping)

                    # append subnet configuration to shared network subnet list
                    config['subnet'].append(subnet)

            # append shared network configuration to config dictionary
            dhcpv6['shared_network'].append(config)

    # If all shared-networks are disabled, there's nothing to do.
    if all(net['disabled'] for net in dhcpv6['shared_network']):
        return None

    return dhcpv6

def verify(dhcpv6):
    if not dhcpv6 or dhcpv6['disabled']:
        return None

    # If DHCP is enabled we need one share-network
    if len(dhcpv6['shared_network']) == 0:
        raise ConfigError('No DHCPv6 shared networks configured.\n' \
                          'At least one DHCPv6 shared network must be configured.')

    # Inspect shared-network/subnet
    subnets = []
    listen_ok = False

    for network in dhcpv6['shared_network']:
        # A shared-network requires a subnet definition
        if len(network['subnet']) == 0:
            raise ConfigError('No DHCPv6 lease subnets configured for {0}. At least one\n' \
                              'lease subnet must be configured for each shared network.'.format(network['name']))

        range6_start = []
        range6_stop = []
        for subnet in network['subnet']:
            # Ususal range declaration with a start and stop address
            for range6 in subnet['range6']:
                # shorten names
                start = range6['start']
                stop = range6['stop']

                # DHCPv6 stop address is required
                if start and not stop:
                    raise ConfigError('DHCPv6 range stop address for start {0} is not defined!'.format(start))

                # Start address must be inside network
                if not ipaddress.ip_address(start) in ipaddress.ip_network(subnet['network']):
                    raise ConfigError('DHCPv6 range start address {0} is not in subnet {1}\n' \
                                      'specified for shared network {2}!'.format(start, subnet['network'], network['name']))

                # Stop address must be inside network
                if not ipaddress.ip_address(stop) in ipaddress.ip_network(subnet['network']):
                     raise ConfigError('DHCPv6 range stop address {0} is not in subnet {1}\n' \
                                       'specified for shared network {2}!'.format(stop, subnet['network'], network['name']))

                # Stop address must be greater or equal to start address
                if not ipaddress.ip_address(stop) >= ipaddress.ip_address(start):
                    raise ConfigError('DHCPv6 range stop address {0} must be greater or equal\n' \
                                      'to the range start address {1}!'.format(stop, start))

                # DHCPv6 range start address must be unique - two ranges can't
                # start with the same address - makes no sense
                if start in range6_start:
                    raise ConfigError('Conflicting DHCPv6 lease range:\n' \
                                      'Pool start address {0} defined multipe times!'.format(start))
                else:
                    range6_start.append(start)

                # DHCPv6 range stop address must be unique - two ranges can't
                # end with the same address - makes no sense
                if stop in range6_stop:
                    raise ConfigError('Conflicting DHCPv6 lease range:\n' \
                                      'Pool stop address {0} defined multipe times!'.format(stop))
                else:
                    range6_stop.append(stop)

            # Prefix delegation sanity checks
            for prefix in subnet['prefix_delegation']:
                if not prefix['stop']:
                    raise ConfigError('Stop address of delegated IPv6 prefix range must be configured')

                if not prefix['length']:
                    raise ConfigError('Length of delegated IPv6 prefix must be configured')

            # We also have prefixes that require checking
            for prefix in subnet['range6_prefix']:
                # If configured prefix does not match our subnet, we have to check that it's inside
                if ipaddress.ip_network(prefix['prefix']) != ipaddress.ip_network(subnet['network']):
                    # Configured prefixes must be inside our network
                    if not ipaddress.ip_network(prefix['prefix']) in ipaddress.ip_network(subnet['network']):
                        raise ConfigError('DHCPv6 prefix {0} is not in subnet {1}\n' \
                                          'specified for shared network {2}!'.format(prefix['prefix'], subnet['network'], network['name']))

            # Static mappings don't require anything (but check if IP is in subnet if it's set)
            for mapping in subnet['static_mapping']:
                if mapping['ipv6_address']:
                    # Static address must be in subnet
                    if not ipaddress.ip_address(mapping['ipv6_address']) in ipaddress.ip_network(subnet['network']):
                        raise ConfigError('DHCPv6 static mapping IPv6 address {0} for static mapping {1}\n' \
                                          'in shared network {2} is outside subnet {3}!' \
                                          .format(mapping['ipv6_address'], mapping['name'], network['name'], subnet['network']))

            # Subnets must be unique
            if subnet['network'] in subnets:
                raise ConfigError('DHCPv6 subnets must be unique! Subnet {0} defined multiple times!'.format(subnet['network']))
            else:
                subnets.append(subnet['network'])

            # DHCPv6 requires at least one configured address range or one static mapping
            # (FIXME: is not actually checked right now?)

            # There must be one subnet connected to a listen interface if network is not disabled.
            if not network['disabled']:
                if is_subnet_connected(subnet['network']):
                    listen_ok = True

            # DHCPv6 subnet must not overlap. ISC DHCP also complains about overlapping
            # subnets: "Warning: subnet 2001:db8::/32 overlaps subnet 2001:db8:1::/32"
            net = ipaddress.ip_network(subnet['network'])
            for n in subnets:
                net2 = ipaddress.ip_network(n)
                if (net != net2):
                    if net.overlaps(net2):
                        raise ConfigError('DHCPv6 conflicting subnet ranges: {0} overlaps {1}'.format(net, net2))

    if not listen_ok:
        raise ConfigError('None of the DHCPv6 subnets are connected to a subnet6 on\n' \
                          'this machine. At least one subnet6 must be connected such that\n' \
                          'DHCPv6 listens on an interface!')


    return None

def generate(dhcpv6):
    if not dhcpv6 or dhcpv6['disabled']:
        return None

    render(config_file, 'dhcpv6-server/dhcpdv6.conf.tmpl', dhcpv6)
    return None

def apply(dhcpv6):
    if not dhcpv6 or dhcpv6['disabled']:
        # DHCP server is removed in the commit
        call('systemctl stop isc-dhcp-server6.service')
        if os.path.exists(config_file):
            os.unlink(config_file)

    else:
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
