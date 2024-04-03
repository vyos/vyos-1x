# Copyright 2023-2024 VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

import json
import os
import socket

from vyos.template import is_ipv6
from vyos.template import isc_static_route
from vyos.template import netmask_from_cidr
from vyos.utils.dict import dict_search_args
from vyos.utils.file import file_permissions
from vyos.utils.process import run

kea4_options = {
    'name_server': 'domain-name-servers',
    'domain_name': 'domain-name',
    'domain_search': 'domain-search',
    'ntp_server': 'ntp-servers',
    'pop_server': 'pop-server',
    'smtp_server': 'smtp-server',
    'time_server': 'time-servers',
    'wins_server': 'netbios-name-servers',
    'default_router': 'routers',
    'server_identifier': 'dhcp-server-identifier',
    'tftp_server_name': 'tftp-server-name',
    'bootfile_size': 'boot-size',
    'time_offset': 'time-offset',
    'wpad_url': 'wpad-url',
    'ipv6_only_preferred': 'v6-only-preferred',
    'captive_portal': 'v4-captive-portal'
}

kea6_options = {
    'info_refresh_time': 'information-refresh-time',
    'name_server': 'dns-servers',
    'domain_search': 'domain-search',
    'nis_domain': 'nis-domain-name',
    'nis_server': 'nis-servers',
    'nisplus_domain': 'nisp-domain-name',
    'nisplus_server': 'nisp-servers',
    'sntp_server': 'sntp-servers',
    'captive_portal': 'v6-captive-portal'
}

kea_ctrl_socket = '/run/kea/dhcp{inet}-ctrl-socket'

def kea_parse_options(config):
    options = []

    for node, option_name in kea4_options.items():
        if node not in config:
            continue

        value = ", ".join(config[node]) if isinstance(config[node], list) else config[node]
        options.append({'name': option_name, 'data': value})

    if 'client_prefix_length' in config:
        options.append({'name': 'subnet-mask', 'data': netmask_from_cidr('0.0.0.0/' + config['client_prefix_length'])})

    if 'ip_forwarding' in config:
        options.append({'name': 'ip-forwarding', 'data': "true"})

    if 'static_route' in config:
        default_route = ''

        if 'default_router' in config:
            default_route = isc_static_route('0.0.0.0/0', config['default_router'])

        routes = [isc_static_route(route, route_options['next_hop']) for route, route_options in config['static_route'].items()]

        options.append({'name': 'rfc3442-static-route', 'data': ", ".join(routes if not default_route else routes + [default_route])})
        options.append({'name': 'windows-static-route', 'data': ", ".join(routes)})

    if 'time_zone' in config:
        with open("/usr/share/zoneinfo/" + config['time_zone'], "rb") as f:
            tz_string = f.read().split(b"\n")[-2].decode("utf-8")

        options.append({'name': 'pcode', 'data': tz_string})
        options.append({'name': 'tcode', 'data': config['time_zone']})

    unifi_controller = dict_search_args(config, 'vendor_option', 'ubiquiti', 'unifi_controller')
    if unifi_controller:
        options.append({
            'name': 'unifi-controller',
            'data': unifi_controller,
            'space': 'ubnt'
        })

    return options

def kea_parse_subnet(subnet, config):
    out = {'subnet': subnet, 'id': int(config['subnet_id'])}
    options = []

    if 'option' in config:
        out['option-data'] = kea_parse_options(config['option'])

        if 'bootfile_name' in config['option']:
            out['boot-file-name'] = config['option']['bootfile_name']

        if 'bootfile_server' in config['option']:
            out['next-server'] = config['option']['bootfile_server']

    if 'ignore_client_id' in config:
        out['match-client-id'] = False

    if 'lease' in config:
        out['valid-lifetime'] = int(config['lease'])
        out['max-valid-lifetime'] = int(config['lease'])

    if 'range' in config:
        pools = []
        for num, range_config in config['range'].items():
            start, stop = range_config['start'], range_config['stop']
            pool = {
                'pool': f'{start} - {stop}'
            }

            if 'option' in range_config:
                pool['option-data'] = kea_parse_options(range_config['option'])

                if 'bootfile_name' in range_config['option']:
                    pool['boot-file-name'] = range_config['option']['bootfile_name']

                if 'bootfile_server' in range_config['option']:
                    pool['next-server'] = range_config['option']['bootfile_server']

            pools.append(pool)
        out['pools'] = pools

    if 'static_mapping' in config:
        reservations = []
        for host, host_config in config['static_mapping'].items():
            if 'disable' in host_config:
                continue

            reservation = {
                'hostname': host,
            }

            if 'mac' in host_config:
                reservation['hw-address'] = host_config['mac']

            if 'duid' in host_config:
                reservation['duid'] = host_config['duid']

            if 'ip_address' in host_config:
                reservation['ip-address'] = host_config['ip_address']

            if 'option' in host_config:
                reservation['option-data'] = kea_parse_options(host_config['option'])

                if 'bootfile_name' in host_config['option']:
                    reservation['boot-file-name'] = host_config['option']['bootfile_name']

                if 'bootfile_server' in host_config['option']:
                    reservation['next-server'] = host_config['option']['bootfile_server']

            reservations.append(reservation)
        out['reservations'] = reservations

    return out

def kea6_parse_options(config):
    options = []

    for node, option_name in kea6_options.items():
        if node not in config:
            continue

        value = ", ".join(config[node]) if isinstance(config[node], list) else config[node]
        options.append({'name': option_name, 'data': value})

    if 'sip_server' in config:
        sip_servers = config['sip_server']

        addrs = []
        hosts = []

        for server in sip_servers:
            if is_ipv6(server):
                addrs.append(server)
            else:
                hosts.append(server)

        if addrs:
            options.append({'name': 'sip-server-addr', 'data': ", ".join(addrs)})

        if hosts:
            options.append({'name': 'sip-server-dns', 'data': ", ".join(hosts)})

    cisco_tftp = dict_search_args(config, 'vendor_option', 'cisco', 'tftp-server')
    if cisco_tftp:
        options.append({'name': 'tftp-servers', 'code': 2, 'space': 'cisco', 'data': cisco_tftp})

    return options

def kea6_parse_subnet(subnet, config):
    out = {'subnet': subnet, 'id': int(config['subnet_id'])}

    if 'option' in config:
        out['option-data'] = kea6_parse_options(config['option'])

    if 'interface' in config:
        out['interface'] = config['interface']

    if 'range' in config:
        pools = []
        for num, range_config in config['range'].items():
            pool = {}

            if 'prefix' in range_config:
                pool['pool'] = range_config['prefix']

            if 'start' in range_config:
                start = range_config['start']
                stop = range_config['stop']
                pool['pool'] = f'{start} - {stop}'

            if 'option' in range_config:
                pool['option-data'] = kea6_parse_options(range_config['option'])

            pools.append(pool)

        out['pools'] = pools

    if 'prefix_delegation' in config:
        pd_pools = []

        if 'prefix' in config['prefix_delegation']:
            for prefix, pd_conf in config['prefix_delegation']['prefix'].items():
                pd_pool = {
                    'prefix': prefix,
                    'prefix-len': int(pd_conf['prefix_length']),
                    'delegated-len': int(pd_conf['delegated_length'])
                }

                if 'excluded_prefix' in pd_conf:
                    pd_pool['excluded-prefix'] = pd_conf['excluded_prefix']
                    pd_pool['excluded-prefix-len'] = int(pd_conf['excluded_prefix_length'])

                pd_pools.append(pd_pool)

        out['pd-pools'] = pd_pools

    if 'lease_time' in config:
        if 'default' in config['lease_time']:
            out['valid-lifetime'] = int(config['lease_time']['default'])
        if 'maximum' in config['lease_time']:
            out['max-valid-lifetime'] = int(config['lease_time']['maximum'])
        if 'minimum' in config['lease_time']:
            out['min-valid-lifetime'] = int(config['lease_time']['minimum'])

    if 'static_mapping' in config:
        reservations = []
        for host, host_config in config['static_mapping'].items():
            if 'disable' in host_config:
                continue

            reservation = {
                'hostname': host
            }

            if 'mac' in host_config:
                reservation['hw-address'] = host_config['mac']

            if 'duid' in host_config:
                reservation['duid'] = host_config['duid']

            if 'ipv6_address' in host_config:
                reservation['ip-addresses'] = [ host_config['ipv6_address'] ]

            if 'ipv6_prefix' in host_config:
                reservation['prefixes'] = [ host_config['ipv6_prefix'] ]

            if 'option' in host_config:
                reservation['option-data'] = kea6_parse_options(host_config['option'])

            reservations.append(reservation)

        out['reservations'] = reservations

    return out

def _ctrl_socket_command(inet, command, args=None):
    path = kea_ctrl_socket.format(inet=inet)

    if not os.path.exists(path):
        return None

    if file_permissions(path) != '0775':
        run(f'sudo chmod 775 {path}')

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(path)

        payload = {'command': command}
        if args:
            payload['arguments'] = args

        sock.send(bytes(json.dumps(payload), 'utf-8'))
        result = b''
        while True:
            data = sock.recv(4096)
            result += data
            if len(data) < 4096:
                break

        return json.loads(result.decode('utf-8'))

def kea_get_leases(inet):
    leases = _ctrl_socket_command(inet, f'lease{inet}-get-all')

    if not leases or 'result' not in leases or leases['result'] != 0:
        return []

    return leases['arguments']['leases']

def kea_delete_lease(inet, ip_address):
    args = {'ip-address': ip_address}

    result = _ctrl_socket_command(inet, f'lease{inet}-del', args)

    if result and 'result' in result:
        return result['result'] == 0

    return False

def kea_get_active_config(inet):
    config = _ctrl_socket_command(inet, 'config-get')

    if not config or 'result' not in config or config['result'] != 0:
        return None

    return config

def kea_get_pool_from_subnet_id(config, inet, subnet_id):
    shared_networks = dict_search_args(config, 'arguments', f'Dhcp{inet}', 'shared-networks')

    if not shared_networks:
        return None

    for network in shared_networks:
        if f'subnet{inet}' not in network:
            continue

        for subnet in network[f'subnet{inet}']:
            if 'id' in subnet and int(subnet['id']) == int(subnet_id):
                return network['name']

    return None
