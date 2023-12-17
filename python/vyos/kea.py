# Copyright 2023 VyOS maintainers and contributors <maintainers@vyos.io>
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

from datetime import datetime

from vyos.template import is_ipv6
from vyos.template import isc_static_route
from vyos.template import netmask_from_cidr
from vyos.utils.dict import dict_search_args
from vyos.utils.file import file_permissions
from vyos.utils.file import read_file
from vyos.utils.process import cmd

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

    return options

def kea_parse_subnet(subnet, config):
    out = {'subnet': subnet}
    options = kea_parse_options(config)

    if 'bootfile_name' in config:
        out['boot-file-name'] = config['bootfile_name']

    if 'bootfile_server' in config:
        out['next-server'] = config['bootfile_server']

    if 'lease' in config:
        out['valid-lifetime'] = int(config['lease'])
        out['max-valid-lifetime'] = int(config['lease'])

    if 'range' in config:
        pools = []
        for num, range_config in config['range'].items():
            start, stop = range_config['start'], range_config['stop']
            pools.append({'pool': f'{start} - {stop}'})
        out['pools'] = pools

    if 'static_mapping' in config:
        reservations = []
        for host, host_config in config['static_mapping'].items():
            if 'disable' in host_config:
                continue

            obj = {
                'hw-address': host_config['mac_address']
            }

            if 'ip_address' in host_config:
                obj['ip-address'] = host_config['ip_address']

            reservations.append(obj)
        out['reservations'] = reservations

    unifi_controller = dict_search_args(config, 'vendor_option', 'ubiquiti', 'unifi_controller')
    if unifi_controller:
        options.append({
            'name': 'unifi-controller',
            'data': unifi_controller,
            'space': 'ubnt'
        })

    if options:
        out['option-data'] = options

    return out

def kea6_parse_options(config):
    options = []

    if 'common_options' in config:
        common_opt = config['common_options']

        for node, option_name in kea6_options.items():
            if node not in common_opt:
                continue

            value = ", ".join(common_opt[node]) if isinstance(common_opt[node], list) else common_opt[node]
            options.append({'name': option_name, 'data': value})

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
    out = {'subnet': subnet}
    options = kea6_parse_options(config)

    if 'address_range' in config:
        addr_range = config['address_range']
        pools = []

        if 'prefix' in addr_range:
            for prefix in addr_range['prefix']:
                pools.append({'pool': prefix})

        if 'start' in addr_range:
            for start, range_conf in addr_range['start'].items():
                stop = range_conf['stop']
                pools.append({'pool': f'{start} - {stop}'})

        out['pools'] = pools

    if 'prefix_delegation' in config:
        pd_pools = []

        if 'prefix' in config['prefix_delegation']:
            for prefix, pd_conf in config['prefix_delegation']['prefix'].items():
                pd_pools.append({
                    'prefix': prefix,
                    'prefix-len': int(pd_conf['prefix_length']),
                    'delegated-len': int(pd_conf['delegated_length'])
                })

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

            reservation = {}

            if 'identifier' in host_config:
                reservation['duid'] = host_config['identifier']

            if 'ipv6_address' in host_config:
                reservation['ip-addresses'] = [ host_config['ipv6_address'] ]

            if 'ipv6_prefix' in host_config:
                reservation['prefixes'] = [ host_config['ipv6_prefix'] ]

            reservations.append(reservation)

        out['reservations'] = reservations

    if options:
        out['option-data'] = options

    return out

def kea_parse_leases(lease_path):
    contents = read_file(lease_path)
    lines = contents.split("\n")
    output = []

    if len(lines) < 2:
        return output

    headers = lines[0].split(",")

    for line in lines[1:]:
        line_out = dict(zip(headers, line.split(",")))

        lifetime = int(line_out['valid_lifetime'])
        expiry = int(line_out['expire'])

        line_out['start_timestamp'] = datetime.utcfromtimestamp(expiry - lifetime)
        line_out['expire_timestamp'] = datetime.utcfromtimestamp(expiry) if expiry else None

        output.append(line_out)

    return output

def _ctrl_socket_command(path, command, args=None):
    if not os.path.exists(path):
        return None

    if file_permissions(path) != '0775':
        cmd(f'sudo chmod 775 {path}')

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

def kea_get_active_config(inet):
    ctrl_socket = f'/run/kea/dhcp{inet}-ctrl-socket'

    config = _ctrl_socket_command(ctrl_socket, 'config-get')
    
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
