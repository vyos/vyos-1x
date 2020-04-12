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

from ipaddress import ip_address, ip_network
from socket import inet_ntoa
from struct import pack
from sys import exit

from vyos.config import Config
from vyos.validate import is_subnet_connected
from vyos import ConfigError
from vyos.util import call
from vyos.template import render


config_file = r'/etc/dhcp/dhcpd.conf'
lease_file = r'/config/dhcpd.leases'
pid_file = r'/var/run/dhcpd.pid'
daemon_config_file = r'/etc/default/isc-dhcpv4-server'

default_config_data = {
    'lease_file': lease_file,
    'disabled': False,
    'ddns_enable': False,
    'global_parameters': [],
    'hostfile_update': False,
    'host_decl_name': False,
    'static_route': False,
    'wpad': False,
    'shared_network': [],
}

def dhcp_slice_range(exclude_list, range_list):
    """
    This function is intended to slice a DHCP range. What does it mean?

    Lets assume we have a DHCP range from '192.0.2.1' to '192.0.2.100'
    but want to exclude address '192.0.2.74' and '192.0.2.75'. We will
    pass an input 'range_list' in the format:
      [{'start' : '192.0.2.1', 'stop' : '192.0.2.100' }]
    and we will receive an output list of:
      [{'start' : '192.0.2.1' , 'stop' : '192.0.2.73'  },
       {'start' : '192.0.2.76', 'stop' : '192.0.2.100' }]
    The resulting list can then be used in turn to build the proper dhcpd
    configuration file.
    """
    output = []
    # exclude list must be sorted for this to work
    exclude_list = sorted(exclude_list)
    for ra in range_list:
        range_start = ra['start']
        range_stop = ra['stop']
        range_last_exclude = ''

        for e in exclude_list:
            if (ip_address(e) >= ip_address(range_start)) and \
               (ip_address(e) <= ip_address(range_stop)):
                range_last_exclude = e

        for e in exclude_list:
            if (ip_address(e) >= ip_address(range_start)) and \
               (ip_address(e) <= ip_address(range_stop)):

                # Build new IP address range ending one IP address before exclude address
                r = {
                    'start' : range_start,
                    'stop' : str(ip_address(e) -1)
                }
                # On the next run our IP address range will start one address after the exclude address
                range_start = str(ip_address(e) + 1)

                # on subsequent exclude addresses we can not
                # append them to our output
                if not (ip_address(r['start']) > ip_address(r['stop'])):
                    # Everything is fine, add range to result
                    output.append(r)

                # Take care of last IP address range spanning from the last exclude
                # address (+1) to the end of the initial configured range
                if ip_address(e) == ip_address(range_last_exclude):
                    r = {
                      'start': str(ip_address(e) + 1),
                      'stop': str(range_stop)
                    }
                    if not (ip_address(r['start']) > ip_address(r['stop'])):
                        output.append(r)
            else:
              # if we have no exclude in the whole range - we just take the range
              # as it is
              if not range_last_exclude:
                  if ra not in output:
                      output.append(ra)

    return output

def dhcp_static_route(static_subnet, static_router):
    # https://ercpe.de/blog/pushing-static-routes-with-isc-dhcp-server
    # Option format is:
    # <netmask>, <network-byte1>, <network-byte2>, <network-byte3>, <router-byte1>, <router-byte2>, <router-byte3>
    # where bytes with the value 0 are omitted.
    net = ip_network(static_subnet)
    # add netmask
    string = str(net.prefixlen) + ','
    # add network bytes
    if net.prefixlen:
        width = net.prefixlen // 8
        if net.prefixlen % 8:
            width += 1
        string += ','.join(map(str,tuple(net.network_address.packed)[:width])) + ','

    # add router bytes
    string += ','.join(static_router.split('.'))

    return string

def get_config():
    dhcp = default_config_data
    conf = Config()
    if not conf.exists('service dhcp-server'):
        return None
    else:
        conf.set_level('service dhcp-server')

    # check for global disable of DHCP service
    if conf.exists('disable'):
        dhcp['disabled'] = True

    # check for global dynamic DNS upste
    if conf.exists('dynamic-dns-update'):
        dhcp['ddns_enable'] = True

    # HACKS AND TRICKS
    #
    # check for global 'raw' ISC DHCP parameters configured by users
    # actually this is a bad idea in general to pass raw parameters from any user
    if conf.exists('global-parameters'):
        dhcp['global_parameters'] = conf.return_values('global-parameters')

    # check for global DHCP server updating /etc/host per lease
    if conf.exists('hostfile-update'):
        dhcp['hostfile_update'] = True

    # If enabled every host declaration within that scope, the name provided
    # for the host declaration will be supplied to the client as its hostname.
    if conf.exists('host-decl-name'):
        dhcp['host_decl_name'] = True

    # check for multiple, shared networks served with DHCP addresses
    if conf.exists('shared-network-name'):
        for network in conf.list_nodes('shared-network-name'):
            conf.set_level('service dhcp-server shared-network-name {0}'.format(network))
            config = {
                'name': network,
                'authoritative': False,
                'description': '',
                'disabled': False,
                'network_parameters': [],
                'subnet': []
            }
            # check if DHCP server should be authoritative on this network
            if conf.exists('authoritative'):
                config['authoritative'] = True

            # A description for this given network
            if conf.exists('description'):
                config['description'] = conf.return_value('description')

            # If disabled, the shared-network configuration becomes inactive in
            # the running DHCP server instance
            if conf.exists('disable'):
                config['disabled'] = True

            # HACKS AND TRICKS
            #
            # check for 'raw' ISC DHCP parameters configured by users
            # actually this is a bad idea in general to pass raw parameters
            # from any user
            #
            # deprecate this and issue a warning like we do for DNS forwarding?
            if conf.exists('shared-network-parameters'):
                config['network_parameters'] = conf.return_values('shared-network-parameters')

            # check for multiple subnet configurations in a shared network
            # config segment
            if conf.exists('subnet'):
                for net in conf.list_nodes('subnet'):
                    conf.set_level('service dhcp-server shared-network-name {0} subnet {1}'.format(network, net))
                    subnet = {
                        'network': net,
                        'address': str(ip_network(net).network_address),
                        'netmask': str(ip_network(net).netmask),
                        'bootfile_name': '',
                        'bootfile_server': '',
                        'client_prefix_length': '',
                        'default_router': '',
                        'rfc3442_default_router': '',
                        'dns_server': [],
                        'domain_name': '',
                        'domain_search': [],
                        'exclude': [],
                        'failover_local_addr': '',
                        'failover_name': '',
                        'failover_peer_addr': '',
                        'failover_status': '',
                        'ip_forwarding': False,
                        'lease': '86400',
                        'ntp_server': [],
                        'pop_server': [],
                        'server_identifier': '',
                        'smtp_server': [],
                        'range': [],
                        'static_mapping': [],
                        'static_subnet': '',
                        'static_router': '',
                        'static_route': '',
                        'subnet_parameters': [],
                        'tftp_server': '',
                        'time_offset': '',
                        'time_server': [],
                        'wins_server': [],
                        'wpad_url': ''
                    }

                    # Used to identify a bootstrap file
                    if conf.exists('bootfile-name'):
                        subnet['bootfile_name'] = conf.return_value('bootfile-name')

                    # Specify host address of the server from which the initial boot file
                    # (specified above) is to be loaded. Should be a numeric IP address or
                    # domain name.
                    if conf.exists('bootfile-server'):
                        subnet['bootfile_server'] = conf.return_value('bootfile-server')

                    # The subnet mask option specifies the client's subnet mask as per RFC 950. If no subnet
                    # mask option is provided anywhere in scope, as a last resort dhcpd will use the subnet
                    # mask from the subnet declaration for the network on which an address is being assigned.
                    if conf.exists('client-prefix-length'):
                        # snippet borrowed from https://stackoverflow.com/questions/33750233/convert-cidr-to-subnet-mask-in-python
                        host_bits = 32 - int(conf.return_value('client-prefix-length'))
                        subnet['client_prefix_length'] = inet_ntoa(pack('!I', (1 << 32) - (1 << host_bits)))

                    # Default router IP address on the client's subnet
                    if conf.exists('default-router'):
                        subnet['default_router'] = conf.return_value('default-router')
                        subnet['rfc3442_default_router'] = dhcp_static_route("0.0.0.0/0", subnet['default_router'])

                    # Specifies a list of Domain Name System (STD 13, RFC 1035) name servers available to
                    # the client. Servers should be listed in order of preference.
                    if conf.exists('dns-server'):
                        subnet['dns_server'] = conf.return_values('dns-server')

                    # Option specifies the domain name that client should use when resolving hostnames
                    # via the Domain Name System.
                    if conf.exists('domain-name'):
                        subnet['domain_name'] = conf.return_value('domain-name')

                    # The domain-search option specifies a 'search list' of Domain Names to be used
                    # by the client to locate not-fully-qualified domain names.
                    if conf.exists('domain-search'):
                        for domain in conf.return_values('domain-search'):
                            subnet['domain_search'].append('"' + domain + '"')

                    # IP address (local) for failover peer to connect
                    if conf.exists('failover local-address'):
                        subnet['failover_local_addr'] = conf.return_value('failover local-address')

                    # DHCP failover peer name
                    if conf.exists('failover name'):
                        subnet['failover_name'] = conf.return_value('failover name')

                    # IP address (remote) of failover peer
                    if conf.exists('failover peer-address'):
                        subnet['failover_peer_addr'] = conf.return_value('failover peer-address')

                    # DHCP failover peer status (primary|secondary)
                    if conf.exists('failover status'):
                        subnet['failover_status'] = conf.return_value('failover status')

                    # Option specifies whether the client should configure its IP layer for packet
                    # forwarding
                    if conf.exists('ip-forwarding'):
                        subnet['ip_forwarding'] = True

                    # Time should be the length in seconds that will be assigned to a lease if the
                    # client requesting the lease does not ask for a specific expiration time
                    if conf.exists('lease'):
                        subnet['lease'] = conf.return_value('lease')

                    # Specifies a list of IP addresses indicating NTP (RFC 5905) servers available
                    # to the client.
                    if conf.exists('ntp-server'):
                        subnet['ntp_server'] = conf.return_values('ntp-server')

                    # POP3 server option specifies a list of POP3 servers available to the client.
                    # Servers should be listed in order of preference.
                    if conf.exists('pop-server'):
                        subnet['pop_server'] = conf.return_values('pop-server')

                    # DHCP servers include this option in the DHCPOFFER in order to allow the client
                    # to distinguish between lease offers. DHCP clients use the contents of the
                    # 'server identifier' field as the destination address for any DHCP messages
                    # unicast to the DHCP server
                    if conf.exists('server-identifier'):
                        subnet['server_identifier'] = conf.return_value('server-identifier')

                    # SMTP server option specifies a list of SMTP servers available to the client.
                    # Servers should be listed in order of preference.
                    if conf.exists('smtp-server'):
                        subnet['smtp_server'] = conf.return_values('smtp-server')

                    # For any subnet on which addresses will be assigned dynamically, there must be at
                    # least one range statement. The range statement gives the lowest and highest IP
                    # addresses in a range. All IP addresses in the range should be in the subnet in
                    # which the range statement is declared.
                    if conf.exists('range'):
                        for range in conf.list_nodes('range'):
                            range = {
                                'start': conf.return_value('range {0} start'.format(range)),
                                'stop':  conf.return_value('range {0} stop'.format(range))
                            }
                            subnet['range'].append(range)

                    # IP address that needs to be excluded from DHCP lease range
                    if conf.exists('exclude'):
                        subnet['exclude'] = conf.return_values('exclude')
                        subnet['range'] = dhcp_slice_range(subnet['exclude'], subnet['range'])

                    # Static DHCP leases
                    if conf.exists('static-mapping'):
                        addresses_for_exclude = []
                        for mapping in conf.list_nodes('static-mapping'):
                            conf.set_level('service dhcp-server shared-network-name {0} subnet {1} static-mapping {2}'.format(network, net, mapping))
                            mapping = {
                                'name': mapping,
                                'disabled': False,
                                'ip_address': '',
                                'mac_address': '',
                                'static_parameters': []
                            }

                            # This static lease is disabled
                            if conf.exists('disable'):
                                mapping['disabled'] = True

                            # IP address used for this DHCP client
                            if conf.exists('ip-address'):
                                mapping['ip_address'] = conf.return_value('ip-address')
                                addresses_for_exclude.append(mapping['ip_address'])

                            # MAC address of requesting DHCP client
                            if conf.exists('mac-address'):
                                mapping['mac_address'] = conf.return_value('mac-address')

                            # HACKS AND TRICKS
                            #
                            # check for 'raw' ISC DHCP parameters configured by users
                            # actually this is a bad idea in general to pass raw parameters
                            # from any user
                            #
                            # deprecate this and issue a warning like we do for DNS forwarding?
                            if conf.exists('static-mapping-parameters'):
                                mapping['static_parameters'] = conf.return_values('static-mapping-parameters')

                            # append static-mapping configuration to subnet list
                            subnet['static_mapping'].append(mapping)

                        # Now we have all static DHCP leases - we also need to slice them
                        # out of our DHCP ranges to avoid ISC DHCPd warnings as:
                        #   dhcpd: Dynamic and static leases present for 192.0.2.51.
                        #   dhcpd: Remove host declaration DMZ_PC1 or remove 192.0.2.51
                        #   dhcpd: from the dynamic address pool for DMZ
                        subnet['range'] = dhcp_slice_range(addresses_for_exclude, subnet['range'])

                    # Reset config level to matching hirachy
                    conf.set_level('service dhcp-server shared-network-name {0} subnet {1}'.format(network, net))

                    # This option specifies a list of static routes that the client should install in its routing
                    # cache. If multiple routes to the same destination are specified, they are listed in descending
                    # order of priority.
                    if conf.exists('static-route destination-subnet'):
                        subnet['static_subnet'] = conf.return_value('static-route destination-subnet')
                        # Required for global config section
                        dhcp['static_route'] = True

                    if conf.exists('static-route router'):
                        subnet['static_router'] = conf.return_value('static-route router')

                    if subnet['static_router'] and subnet['static_subnet']:
                        subnet['static_route'] = dhcp_static_route(subnet['static_subnet'], subnet['static_router'])

                    # HACKS AND TRICKS
                    #
                    # check for 'raw' ISC DHCP parameters configured by users
                    # actually this is a bad idea in general to pass raw parameters
                    # from any user
                    #
                    # deprecate this and issue a warning like we do for DNS forwarding?
                    if conf.exists('subnet-parameters'):
                        subnet['subnet_parameters'] = conf.return_values('subnet-parameters')

                    # This option is used to identify a TFTP server and, if supported by the client, should have
                    # the same effect as the server-name declaration. BOOTP clients are unlikely to support this
                    # option. Some DHCP clients will support it, and others actually require it.
                    if conf.exists('tftp-server-name'):
                        subnet['tftp_server'] = conf.return_value('tftp-server-name')

                    # The time-offset option specifies the offset of the client’s subnet in seconds from
                    # Coordinated Universal Time (UTC).
                    if conf.exists('time-offset'):
                        subnet['time_offset'] = conf.return_value('time-offset')

                    # The time-server option specifies a list of RFC 868 time servers available to the client.
                    # Servers should be listed in order of preference.
                    if conf.exists('time-server'):
                        subnet['time_server'] = conf.return_values('time-server')

                    # The NetBIOS name server (NBNS) option specifies a list of RFC 1001/1002 NBNS name servers
                    # listed in order of preference. NetBIOS Name Service is currently more commonly referred to
                    # as WINS. WINS servers can be specified using the netbios-name-servers option.
                    if conf.exists('wins-server'):
                        subnet['wins_server'] = conf.return_values('wins-server')

                    # URL for Web Proxy Autodiscovery Protocol
                    if conf.exists('wpad-url'):
                        subnet['wpad_url'] = conf.return_value('wpad-url')
                        # Required for global config section
                        dhcp['wpad'] = True

                    # append subnet configuration to shared network subnet list
                    config['subnet'].append(subnet)

            # append shared network configuration to config dictionary
            dhcp['shared_network'].append(config)

    return dhcp

def verify(dhcp):
    if (dhcp is None) or (dhcp['disabled'] is True):
        return None

    # If DHCP is enabled we need one share-network
    if len(dhcp['shared_network']) == 0:
        raise ConfigError('No DHCP shared networks configured.\n' \
                          'At least one DHCP shared network must be configured.')

    # Inspect shared-network/subnet
    failover_names = []
    listen_ok = False
    subnets = []

    # A shared-network requires a subnet definition
    for network in dhcp['shared_network']:
        if len(network['subnet']) == 0:
            raise ConfigError('No DHCP lease subnets configured for {0}. At least one\n' \
                              'lease subnet must be configured for each shared network.'.format(network['name']))

        for subnet in network['subnet']:
            # Subnet static route declaration requires destination and router
            if subnet['static_subnet'] or subnet['static_router']:
                if not (subnet['static_subnet'] and subnet['static_router']):
                    raise ConfigError('Please specify missing DHCP static-route parameter(s):\n' \
                                      'destination-subnet | router')

            # Failover requires all 4 parameters set
            if subnet['failover_local_addr'] or subnet['failover_peer_addr'] or subnet['failover_name'] or subnet['failover_status']:
                if not (subnet['failover_local_addr'] and subnet['failover_peer_addr'] and subnet['failover_name'] and subnet['failover_status']):
                    raise ConfigError('Please specify missing DHCP failover parameter(s):\n' \
                                      'local-address | peer-address | name | status')

                # Failover names must be uniquie
                if subnet['failover_name'] in failover_names:
                    raise ConfigError('Failover names must be unique:\n' \
                                      '{0} has already been configured!'.format(subnet['failover_name']))
                else:
                    failover_names.append(subnet['failover_name'])

                # Failover requires start/stop ranges for pool
                if (len(subnet['range']) == 0):
                    raise ConfigError('At least one start-stop range must be configured for {0}\n' \
                                      'to set up DHCP failover!'.format(subnet['network']))

            # Check if DHCP address range is inside configured subnet declaration
            range_start = []
            range_stop = []
            for range in subnet['range']:
                start = range['start']
                stop = range['stop']
                # DHCP stop IP required after start IP
                if start and not stop:
                    raise ConfigError('DHCP range stop address for start {0} is not defined!'.format(start))

                # Start address must be inside network
                if not ip_address(start) in ip_network(subnet['network']):
                    raise ConfigError('DHCP range start address {0} is not in subnet {1}\n' \
                                      'specified for shared network {2}!'.format(start, subnet['network'], network['name']))

                # Stop address must be inside network
                if not ip_address(stop) in ip_network(subnet['network']):
                    raise ConfigError('DHCP range stop address {0} is not in subnet {1}\n' \
                                      'specified for shared network {2}!'.format(stop, subnet['network'], network['name']))

                # Stop address must be greater or equal to start address
                if not ip_address(stop) >= ip_address(start):
                    raise ConfigError('DHCP range stop address {0} must be greater or equal\n' \
                                      'to the range start address {1}!'.format(stop, start))

                # Range start address must be unique
                if start in range_start:
                    raise ConfigError('Conflicting DHCP lease range:\n' \
                                      'Pool start address {0} defined multipe times!'.format(start))
                else:
                    range_start.append(start)

                # Range stop address must be unique
                if stop in range_stop:
                    raise ConfigError('Conflicting DHCP lease range:\n' \
                                      'Pool stop address {0} defined multipe times!'.format(stop))
                else:
                    range_stop.append(stop)

            # Exclude addresses must be in bound
            for exclude in subnet['exclude']:
                if not ip_address(exclude) in ip_network(subnet['network']):
                    raise ConfigError('Exclude IP address {0} is outside of the DHCP lease network {1}\n' \
                                      'under shared network {2}!'.format(exclude, subnet['network'], network['name']))

            # At least one DHCP address range or static-mapping required
            active_mapping = False
            if (len(subnet['range']) == 0):
                for mapping in subnet['static_mapping']:
                    # we need at least one active mapping
                    if (not active_mapping) and (not mapping['disabled']):
                        active_mapping = True
            else:
                active_mapping = True

            if not active_mapping:
                raise ConfigError('No DHCP address range or active static-mapping set\n' \
                                  'for subnet {0}!'.format(subnet['network']))

            # Static mappings require just a MAC address (will use an IP from the dynamic pool if IP is not set)
            for mapping in subnet['static_mapping']:

                if mapping['ip_address']:
                    # Static IP address must be in bound
                    if not ip_address(mapping['ip_address']) in ip_network(subnet['network']):
                        raise ConfigError('DHCP static lease IP address {0} for static mapping {1}\n' \
                                          'in shared network {2} is outside DHCP lease subnet {3}!' \
                                          .format(mapping['ip_address'], mapping['name'], network['name'], subnet['network']))

                # Static mapping requires MAC address
                if not mapping['mac_address']:
                    raise ConfigError('DHCP static lease MAC address not specified for static mapping\n' \
                                       '{0} under shared network name {1}!'.format(mapping['name'], network['name']))

            # There must be one subnet connected to a listen interface.
            # This only counts if the network itself is not disabled!
            if not network['disabled']:
                if is_subnet_connected(subnet['network'], primary=True):
                    listen_ok = True

            # Subnets must be non overlapping
            if subnet['network'] in subnets:
                raise ConfigError('DHCP subnets must be unique! Subnet {0} defined multiple times!'.format(subnet['network']))
            else:
                subnets.append(subnet['network'])

            # Check for overlapping subnets
            net = ip_network(subnet['network'])
            for n in subnets:
                net2 = ip_network(n)
                if (net != net2):
                    if net.overlaps(net2):
                        raise ConfigError('DHCP conflicting subnet ranges: {0} overlaps {1}'.format(net, net2))

    if not listen_ok:
        raise ConfigError('DHCP server configuration error!\n' \
                          'None of configured DHCP subnets does not have appropriate\n' \
                          'primary IP address on any broadcast interface.')

    return None

def generate(dhcp):
    if dhcp is None:
        return None

    if dhcp['disabled'] is True:
        print('Warning: DHCP server will be deactivated because it is disabled')
        return None

    # Please see: https://phabricator.vyos.net/T1129 for quoting of the raw parameters
    # we can pass to ISC DHCPd
    render(config_file, 'dhcp-server/dhcpd.conf.tmpl', dhcp,
           formater=lambda _: _.replace("&quot;", '"'))
    render(daemon_config_file, 'dhcp-server/daemon.tmpl', dhcp)
    return None

def apply(dhcp):
    if (dhcp is None) or dhcp['disabled']:
        # DHCP server is removed in the commit
        call('sudo systemctl stop isc-dhcpv4-server.service')
        if os.path.exists(config_file):
            os.unlink(config_file)
        if os.path.exists(daemon_config_file):
            os.unlink(daemon_config_file)
    else:
        # If our file holding DHCP leases does yet not exist - create it
        if not os.path.exists(lease_file):
            os.mknod(lease_file)

        call('sudo systemctl restart isc-dhcpv4-server.service')

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
