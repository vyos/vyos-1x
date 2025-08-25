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
from sys import argv

from glob import glob
from ipaddress import ip_address
from ipaddress import ip_network
from netaddr import IPRange

from vyos.config import Config
from vyos.pki import wrap_certificate
from vyos.pki import wrap_private_key
from vyos.template import render
from vyos.utils.dict import dict_search
from vyos.utils.dict import dict_search_args
from vyos.utils.file import chmod_775
from vyos.utils.file import makedir
from vyos.utils.file import write_file
from vyos.utils.permission import chown
from vyos.utils.process import call
from vyos.utils.network import interface_exists
from vyos.utils.network import is_subnet_connected
from vyos.utils.network import is_addr_assigned
from vyos import ConfigError
from vyos import airbag

airbag.enable()

ctrl_socket = ''
config_file = ''
config_file_d2 = ''
lease_file = ''
lease_file_glob = ''

ca_cert_file = ''
cert_file = ''
cert_key_file = ''

user_group = '_kea'


def _override_for_vrf(vrf_name):
    """
    This function is intended to override global vars when vrf is enabled
    """
    global ctrl_socket, config_file, config_file_d2, lease_file, lease_file_glob
    global ca_cert_file, cert_file, cert_key_file

    ctrl_socket = f'/run/kea/dhcp4-{vrf_name}-ctrl-socket'
    config_file = f'/run/kea/kea-{vrf_name}-dhcp4.conf'
    config_file_d2 = f'/run/kea/kea-{vrf_name}-dhcp-ddns.conf'
    lease_file = f'/config/dhcp/dhcp4-{vrf_name}-leases.csv'
    lease_file_glob = f'/config/dhcp/dhcp4-{vrf_name}-leases*'

    ca_cert_file = f'/run/kea/kea-{vrf_name}-failover-ca.pem'
    cert_file = f'/run/kea/kea-{vrf_name}-failover.pem'
    cert_key_file = f'/run/kea/kea-{vrf_name}-failover-key.pem'


def _reset_vars():
    """
    This function is intended to reset global vars when vrf is not enabled
    """
    global ctrl_socket, config_file, config_file_d2, lease_file, lease_file_glob
    global ca_cert_file, cert_file, cert_key_file

    ctrl_socket = '/run/kea/dhcp4-ctrl-socket'
    config_file = '/run/kea/kea-dhcp4.conf'
    config_file_d2 = '/run/kea/kea-dhcp-ddns.conf'
    lease_file = '/config/dhcp/dhcp4-leases.csv'
    lease_file_glob = '/config/dhcp/dhcp4-leases*'

    ca_cert_file = '/run/kea/kea-failover-ca.pem'
    cert_file = '/run/kea/kea-failover.pem'
    cert_key_file = '/run/kea/kea-failover-key.pem'


def dhcp_slice_range(exclude_list, range_dict):
    """
    This function is intended to slice a DHCP range. What does it mean?

    Lets assume we have a DHCP range from '192.0.2.1' to '192.0.2.100'
    but want to exclude address '192.0.2.74' and '192.0.2.75'. We will
    pass an input 'range_dict' in the format:
      {'start' : '192.0.2.1', 'stop' : '192.0.2.100' }
    and we will receive an output list of:
      [{'start' : '192.0.2.1' , 'stop' : '192.0.2.73'  },
       {'start' : '192.0.2.76', 'stop' : '192.0.2.100' }]
    The resulting list can then be used in turn to build the proper dhcpd
    configuration file.
    """
    output = []
    # exclude list must be sorted for this to work
    exclude_list = sorted(exclude_list)
    range_start = range_dict['start']
    range_stop = range_dict['stop']
    range_last_exclude = ''

    for e in exclude_list:
        if (ip_address(e) >= ip_address(range_start)) and (
            ip_address(e) <= ip_address(range_stop)
        ):
            range_last_exclude = e

    for e in exclude_list:
        if (ip_address(e) >= ip_address(range_start)) and (
            ip_address(e) <= ip_address(range_stop)
        ):
            # Build new address range ending one address before exclude address
            r = {'start': range_start, 'stop': str(ip_address(e) - 1)}

            if 'option' in range_dict:
                r['option'] = range_dict['option']

            # On the next run our address range will start one address after
            # the exclude address
            range_start = str(ip_address(e) + 1)

            # on subsequent exclude addresses we can not
            # append them to our output
            if not (ip_address(r['start']) > ip_address(r['stop'])):
                # Everything is fine, add range to result
                output.append(r)

            # Take care of last IP address range spanning from the last exclude
            # address (+1) to the end of the initial configured range
            if ip_address(e) == ip_address(range_last_exclude):
                r = {'start': str(ip_address(e) + 1), 'stop': str(range_stop)}

                if 'option' in range_dict:
                    r['option'] = range_dict['option']

                if not (ip_address(r['start']) > ip_address(r['stop'])):
                    output.append(r)
        else:
            # if the excluded address was not part of the range, we simply return
            # the entire ranga again
            if not range_last_exclude:
                if range_dict not in output:
                    output.append(range_dict)

    return output


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    # if running in vrf, set base diffrently
    if argv and len(argv) > 1:
        vrf_name = argv[1]
        base = ['vrf', 'name', vrf_name, 'service', 'dhcp-server']

        # vrf is defined, override other vars aswell
        _override_for_vrf(vrf_name)
    else:
        base = ['service', 'dhcp-server']

        # vrf is not defined reset vars
        _reset_vars()
    if not conf.exists(base):
        return None

    dhcp = conf.get_config_dict(
        base,
        key_mangling=('-', '_'),
        no_tag_node_value_mangle=True,
        get_first_key=True,
        with_recursive_defaults=True,
    )

    # add vrf context if present
    if argv and len(argv) > 1:
        dhcp['vrf_context'] = argv[1]

    if 'shared_network_name' in dhcp:
        for network, network_config in dhcp['shared_network_name'].items():
            if 'subnet' in network_config:
                for subnet, subnet_config in network_config['subnet'].items():
                    # If exclude IP addresses are defined we need to slice them out of
                    # the defined ranges
                    if {'exclude', 'range'} <= set(subnet_config):
                        new_range_id = 0
                        new_range_dict = {}
                        for r, r_config in subnet_config['range'].items():
                            for slice in dhcp_slice_range(
                                subnet_config['exclude'], r_config
                            ):
                                new_range_dict.update({new_range_id: slice})
                                new_range_id += 1

                        dhcp['shared_network_name'][network]['subnet'][subnet].update(
                            {'range': new_range_dict}
                        )

    if len(dhcp['high_availability']) == 1:
        ## only default value for mode is set, need to remove ha node
        del dhcp['high_availability']
    else:
        if dict_search('high_availability.certificate', dhcp):
            dhcp['pki'] = conf.get_config_dict(
                ['pki'],
                key_mangling=('-', '_'),
                get_first_key=True,
                no_tag_node_value_mangle=True,
            )

    return dhcp

def verify_ddns_domain_servers(domain_type, domain):
    if 'dns_server' in domain:
        invalid_servers = []
        for server_no, server_config in domain['dns_server'].items():
            if 'address' not in server_config:
                invalid_servers.append(server_no)
        if len(invalid_servers) > 0:
            raise ConfigError(f'{domain_type} DNS servers {", ".join(invalid_servers)} in DDNS configuration need to have an IP address')
    return None

def verify(dhcp):
    # bail out early - looks like removal from running config
    if not dhcp or 'disable' in dhcp:
        return None

    # If DHCP is enabled we need one share-network
    if 'shared_network_name' not in dhcp:
        raise ConfigError(
            'No DHCP shared networks configured.\n'
            'At least one DHCP shared network must be configured.'
        )

    # Inspect shared-network/subnet
    listen_ok = False
    subnets = []
    shared_networks = len(dhcp['shared_network_name'])
    disabled_shared_networks = 0

    subnet_ids = []

    # A shared-network requires a subnet definition
    for network, network_config in dhcp['shared_network_name'].items():
        if 'disable' in network_config:
            disabled_shared_networks += 1

        if 'subnet' not in network_config:
            raise ConfigError(
                f'No subnets defined for {network}. At least one\n'
                'lease subnet must be configured.'
            )

        for subnet, subnet_config in network_config['subnet'].items():
            if 'subnet_id' not in subnet_config:
                raise ConfigError(
                    f'Unique subnet ID not specified for subnet "{subnet}"'
                )

            if subnet_config['subnet_id'] in subnet_ids:
                raise ConfigError(f'Subnet ID for subnet "{subnet}" is not unique')

            subnet_ids.append(subnet_config['subnet_id'])

            # All delivered static routes require a next-hop to be set
            if 'static_route' in subnet_config:
                for route, route_option in subnet_config['static_route'].items():
                    if 'next_hop' not in route_option:
                        raise ConfigError(
                            f'DHCP static-route "{route}" requires router to be defined!'
                        )

            # Check if DHCP address range is inside configured subnet declaration
            if 'range' in subnet_config:
                networks = []
                for range, range_config in subnet_config['range'].items():
                    if not {'start', 'stop'} <= set(range_config):
                        raise ConfigError(
                            f'DHCP range "{range}" start and stop address must be defined!'
                        )

                    # Start/Stop address must be inside network
                    for key in ['start', 'stop']:
                        if ip_address(range_config[key]) not in ip_network(subnet):
                            raise ConfigError(
                                f'DHCP range "{range}" {key} address not within shared-network "{network}, {subnet}"!'
                            )

                    # Stop address must be greater or equal to start address
                    if ip_address(range_config['stop']) < ip_address(
                        range_config['start']
                    ):
                        raise ConfigError(
                            f'DHCP range "{range}" stop address must be greater or equal\n'
                            'to the ranges start address!'
                        )

                    for network in networks:
                        start = range_config['start']
                        stop = range_config['stop']
                        if start in network:
                            raise ConfigError(
                                f'Range "{range}" start address "{start}" already part of another range!'
                            )
                        if stop in network:
                            raise ConfigError(
                                f'Range "{range}" stop address "{stop}" already part of another range!'
                            )

                    tmp = IPRange(range_config['start'], range_config['stop'])
                    networks.append(tmp)

            # Exclude addresses must be in bound
            if 'exclude' in subnet_config:
                for exclude in subnet_config['exclude']:
                    if ip_address(exclude) not in ip_network(subnet):
                        raise ConfigError(
                            f'Excluded IP address "{exclude}" not within shared-network "{network}, {subnet}"!'
                        )

            # At least one DHCP address range or static-mapping required
            if 'range' not in subnet_config and 'static_mapping' not in subnet_config:
                raise ConfigError(
                    f'No DHCP address range or active static-mapping configured\n'
                    f'within shared-network "{network}, {subnet}"!'
                )

            if 'static_mapping' in subnet_config:
                # Static mappings require just a MAC address (will use an IP from the dynamic pool if IP is not set)
                used_ips = []
                used_mac = []
                used_duid = []
                for mapping, mapping_config in subnet_config['static_mapping'].items():
                    if 'ip_address' in mapping_config:
                        if ip_address(mapping_config['ip_address']) not in ip_network(
                            subnet
                        ):
                            raise ConfigError(
                                f'Configured static lease address for mapping "{mapping}" is\n'
                                f'not within shared-network "{network}, {subnet}"!'
                            )

                        if (
                            'mac' not in mapping_config and 'duid' not in mapping_config
                        ) or ('mac' in mapping_config and 'duid' in mapping_config):
                            raise ConfigError(
                                f'Either MAC address or Client identifier (DUID) is required for '
                                f'static mapping "{mapping}" within shared-network "{network}, {subnet}"!'
                            )

                        if 'disable' not in mapping_config:
                            if mapping_config['ip_address'] in used_ips:
                                raise ConfigError(
                                    f'Configured IP address for static mapping "{mapping}" already exists on another static mapping'
                                )
                            used_ips.append(mapping_config['ip_address'])

                    if 'disable' not in mapping_config:
                        if 'mac' in mapping_config:
                            if mapping_config['mac'] in used_mac:
                                raise ConfigError(
                                    f'Configured MAC address for static mapping "{mapping}" already exists on another static mapping'
                                )
                            used_mac.append(mapping_config['mac'])

                        if 'duid' in mapping_config:
                            if mapping_config['duid'] in used_duid:
                                raise ConfigError(
                                    f'Configured DUID for static mapping "{mapping}" already exists on another static mapping'
                                )
                            used_duid.append(mapping_config['duid'])

            # There must be one subnet connected to a listen interface.
            # This only counts if the network itself is not disabled!
            if 'disable' not in network_config:
                if is_subnet_connected(subnet, primary=False):
                    listen_ok = True

            # Subnets must be non overlapping
            if subnet in subnets:
                raise ConfigError(
                    f'Configured subnets must be unique! Subnet "{subnet}"\n'
                    'defined multiple times!'
                )
            subnets.append(subnet)

            # Check for overlapping subnets
            net = ip_network(subnet)
            for n in subnets:
                net2 = ip_network(n)
                if net != net2:
                    if net.overlaps(net2):
                        raise ConfigError(
                            f'Conflicting subnet ranges: "{net}" overlaps "{net2}"!'
                        )

    # Prevent 'disable' for shared-network if only one network is configured
    if (shared_networks - disabled_shared_networks) < 1:
        raise ConfigError('At least one shared network must be active!')

    if 'high_availability' in dhcp:
        for key in ['name', 'remote', 'source_address', 'status']:
            if key not in dhcp['high_availability']:
                tmp = key.replace('_', '-')
                raise ConfigError(
                    f'DHCP high-availability requires "{tmp}" to be specified!'
                )

        if len({'certificate', 'ca_certificate'} & set(dhcp['high_availability'])) == 1:
            raise ConfigError(
                'DHCP secured high-availability requires both certificate and CA certificate'
            )

        if 'certificate' in dhcp['high_availability']:
            cert_name = dhcp['high_availability']['certificate']

            if cert_name not in dhcp['pki']['certificate']:
                raise ConfigError(
                    'Invalid certificate specified for DHCP high-availability'
                )

            if not dict_search_args(
                dhcp['pki']['certificate'], cert_name, 'certificate'
            ):
                raise ConfigError(
                    'Invalid certificate specified for DHCP high-availability'
                )

            if not dict_search_args(
                dhcp['pki']['certificate'], cert_name, 'private', 'key'
            ):
                raise ConfigError(
                    'Missing private key on certificate specified for DHCP high-availability'
                )

        if 'ca_certificate' in dhcp['high_availability']:
            ca_cert_name = dhcp['high_availability']['ca_certificate']
            if ca_cert_name not in dhcp['pki']['ca']:
                raise ConfigError(
                    'Invalid CA certificate specified for DHCP high-availability'
                )

            if not dict_search_args(dhcp['pki']['ca'], ca_cert_name, 'certificate'):
                raise ConfigError(
                    'Invalid CA certificate specified for DHCP high-availability'
                )

    for address in dict_search('listen_address', dhcp) or []:
        if is_addr_assigned(address, include_vrf=True):
            listen_ok = True
            # no need to probe further networks, we have one that is valid
            continue
        else:
            raise ConfigError(
                f'listen-address "{address}" not configured on any interface'
            )

    if not listen_ok:
        raise ConfigError(
            'None of the configured subnets have an appropriate primary IP address on any\n'
            'broadcast interface configured, nor was there an explicit listen-address\n'
            'configured for serving DHCP relay packets!'
        )

    if 'listen_address' in dhcp and 'listen_interface' in dhcp:
        raise ConfigError(
            'Cannot define listen-address and listen-interface at the same time'
        )

    for interface in dict_search('listen_interface', dhcp) or []:
        if not interface_exists(interface):
            raise ConfigError(f'listen-interface "{interface}" does not exist')

    if 'dynamic_dns_update' in dhcp:
        ddns = dhcp['dynamic_dns_update']
        if 'tsig_key' in ddns:
            invalid_keys = []
            for tsig_key_name, tsig_key_config in ddns['tsig_key'].items():
                if not ('algorithm' in tsig_key_config and 'secret' in tsig_key_config):
                    invalid_keys.append(tsig_key_name)
            if len(invalid_keys) > 0:
                raise ConfigError(f'Both algorithm and secret need to be set for TSIG keys: {", ".join(invalid_keys)}')

        if 'forward_domain' in ddns:
            verify_ddns_domain_servers('Forward', ddns['forward_domain'])

        if 'reverse_domain' in ddns:
            verify_ddns_domain_servers('Reverse', ddns['reverse_domain'])

    return None


def generate(dhcp):
    # bail out early - looks like removal from running config
    if not dhcp or 'disable' in dhcp:
        return None

    dhcp['lease_file'] = lease_file
    dhcp['machine'] = os.uname().machine

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

    for f in [cert_file, cert_key_file, ca_cert_file]:
        if os.path.exists(f):
            os.unlink(f)

    if 'high_availability' in dhcp:
        if 'certificate' in dhcp['high_availability']:
            cert_name = dhcp['high_availability']['certificate']
            cert_data = dhcp['pki']['certificate'][cert_name]['certificate']
            key_data = dhcp['pki']['certificate'][cert_name]['private']['key']
            write_file(
                cert_file, wrap_certificate(cert_data), user=user_group, mode=0o600
            )
            write_file(
                cert_key_file, wrap_private_key(key_data), user=user_group, mode=0o600
            )

            dhcp['high_availability']['cert_file'] = cert_file
            dhcp['high_availability']['cert_key_file'] = cert_key_file

        if 'ca_certificate' in dhcp['high_availability']:
            ca_cert_name = dhcp['high_availability']['ca_certificate']
            ca_cert_data = dhcp['pki']['ca'][ca_cert_name]['certificate']
            write_file(
                ca_cert_file,
                wrap_certificate(ca_cert_data),
                user=user_group,
                mode=0o600,
            )

            dhcp['high_availability']['ca_cert_file'] = ca_cert_file

    render(
        config_file,
        'dhcp-server/kea-dhcp4.conf.j2',
        dhcp,
        user=user_group,
        group=user_group,
    )
    if 'dynamic_dns_update' in dhcp:
        render(
            config_file_d2,
            'dhcp-server/kea-dhcp-ddns.conf.j2',
            dhcp,
            user=user_group,
            group=user_group
        )

    return None


def apply(dhcp):
    # if running in vrf, set base diffrently
    if argv and len(argv) > 1:
        vrf_name = argv[1]
        services = [f'kea-dhcp4-server@{vrf_name}', f'kea-dhcp-ddns-server@{vrf_name}']
    else:
        services = ['kea-dhcp4-server', 'kea-dhcp-ddns-server']

    if not dhcp or 'disable' in dhcp:
        for service in services:
            call(f'systemctl stop {service}.service')

        if os.path.exists(config_file):
            os.unlink(config_file)

        return None

    for service in services:
        action = 'restart'

        if 'kea-dhcp-ddns-server' in service and 'dynamic_dns_update' not in dhcp:
            action = 'stop'

        call(f'systemctl {action} {service}.service')

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
