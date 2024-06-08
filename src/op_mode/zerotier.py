#!/usr/bin/env python3
#
# Copyright (C) 2016-2024 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# This script is will output various information related to ZeroTier

import json
import os
import re
import requests
import sys
import typing
import zipfile

from tabulate import tabulate

import vyos.opmode
from vyos.utils.process import cmd
from vyos.configquery import ConfigTreeQuery

conf = ConfigTreeQuery()

def show_interfaces(raw: bool, interface: typing.Optional[str]):
    # Get list of interfaces
    zt_int_dict = conf.get_config_dict(['interfaces', 'zerotier'], key_mangling=('-', '_'),
                            get_first_key=True)

    if interface:
        # Check if interface that was specified exists
        if interface not in zt_int_dict.keys():
            raise vyos.opmode.Error(f'ZeroTier interface not configured')
        if_list = [interface]
    else:
        if_list = zt_int_dict.keys()

    if not if_list:
        raise vyos.opmode.Error(f'No ZeroTier interfaces configured')

    output_list = []
    raw_dict = {}
    for interface in if_list:
        zt_dict = zt_int_dict.get(interface)
        raw_dict[interface] = {}

        if zt_dict:
            interface_name = interface

            # Get Network ID
            network_id = zt_dict.get('network_id')

            description = zt_dict.get('description')

            # Get Node ID and Version
            cli_dict = json.loads(cmd(f"podman exec vyos_created_{interface_name} zerotier-cli info -j"))
            node_id = cli_dict.get('address')
            version = cli_dict.get('version')

            # Get IP address(es) on interface
            tmp = json.loads(cmd(f"ip -j addr show dev {interface_name}"))[0].get('addr_info')

            ip_list = []
            for address in tmp:
                ip_list.append(f"{address.get('local')}/{address.get('prefixlen')}")

            # Generate list for tabulate output
            output_list.append([interface_name,
                                node_id,
                                '\n'.join(ip_list),
                                network_id,
                                version,
                                description]
                               )

            # Generate dict for raw output
            raw_dict[interface]['node_id'] = node_id
            raw_dict[interface]['ip_address'] = ip_list
            raw_dict[interface]['network_id'] = network_id
            raw_dict[interface]['version'] = version
            raw_dict[interface]['description'] = description

    if raw:
        return {'zerotier': raw_dict}
    else:
        # Tabulate print information
        headers = ["Interface", "Node ID", "IP Address", "Network", "Version", "Description"]
        print(tabulate(output_list, headers))

def zt_api(url, api_token, api_type):
    # Create the headers for API calls
    if api_type == "service":
        headers = {
            "X-ZT1-Auth": api_token
        }
    elif api_type == "central":
        headers = {
            'Authorization': f'token {api_token}'
        }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raises HTTPError for bad responses (4xx and 5xx)
        return response
    except requests.exceptions.HTTPError as http_err:
        raise vyos.opmode.Error(f'HTTP error occurred: {http_err}')
    except Exception as err:
        raise vyos.opmode.Error(f'Other error occurred: {err}')

def show_peers_detail(raw: bool, interface: typing.Optional[str]):
    localNodeList = []
    controllerNodeList = []
    controllerNetworkList = []

    headers = ['Name', 'NodeID', 'Description', 'ZeroTier IP', 'Public IP', 'Network', 'Version']
    peer_dict = conf.get_config_dict(['interfaces', 'zerotier', interface], key_mangling=('-', '_'),
                            get_first_key=True)

    primary_port = peer_dict.get('primary_port')

    # peers-all and peers-detail does API calls to ZeroTier Central and requires API key to be configured
    api_token = peer_dict.get('api_key')
    if not api_token:
        raise vyos.opmode.Error("This command requires a ZeroTier Central API key to be configured")

    # peers-detail does a local API call to get local peers and requires an authtoken
    try:
        with open(f'/config/vyos-zerotier/{interface}/authtoken.secret', 'r') as file:
            authtoken = file.read()
    except FileNotFoundError:
        raise vyos.opmode.Error(f'authtoken.secret not found! This should have been created when creating an interface. Does {interface} exist')

    # Get local list of nodes
    network_data = zt_api(f'http://127.0.0.1:{primary_port}/peer', authtoken, 'service').json()
    for peers in network_data:
        localNodeList.append(peers['address'])

    # Get list of all networks in a ZeroTier controller
    network_data = zt_api('https://api.zerotier.com/api/v1/network', api_token, 'central').json()
    for networks in network_data:
        controllerNetworkList.append(networks['id'])

    raw_dict = {}
    for controllerNode in controllerNetworkList:
        raw_dict[controllerNode] = []
        network_data = zt_api(f'https://api.zerotier.com/api/v1/network/{controllerNode}/member', api_token, 'central').json()
        for i in network_data:
            if i['nodeId'] in localNodeList:
                controllerNodeList.append([i['name'], i['nodeId'], i['description'], '\n'.join(i['config']['ipAssignments']), i['physicalAddress'], i['networkId'], i['clientVersion']])
                raw_dict[controllerNode].append(i)

    if raw:
        return {'zerotier': raw_dict}
    else:
        sorted_list = sorted(controllerNodeList, key=lambda x: x[0].lower())
        print(tabulate(sorted_list, headers))

def show_peers_all(raw: bool, interface: typing.Optional[str]):
    controllerNodeList = []
    controllerNetworkList = []

    headers = ['Name', 'NodeID', 'Description', 'ZeroTier IP', 'Network', 'Version']
    peer_dict = conf.get_config_dict(['interfaces', 'zerotier', interface], key_mangling=('-', '_'),
                            get_first_key=True)

    # peers-all and peers-detail does API calls to ZeroTier Central and requires API key to be configured
    api_token = peer_dict.get('api_key')
    if not api_token:
        raise vyos.opmode.Error("This command requires a ZeroTier Central API key to be configured")

    # Get list of all networks in a ZeroTier controller
    network_data = zt_api('https://api.zerotier.com/api/v1/network', api_token, 'central').json()
    for networks in network_data:
        controllerNetworkList.append(networks['id'])

    raw_dict = {}
    for controllerNode in controllerNetworkList:
        network_data = zt_api(f'https://api.zerotier.com/api/v1/network/{controllerNode}/member', api_token, 'central').json()
        for i in network_data:
            controllerNodeList.append([i['name'], i['nodeId'], i['description'], '\n'.join(i['config']['ipAssignments']), i['networkId'], i['clientVersion']])
        raw_dict[controllerNode] = network_data

    if raw:
        return {'zerotier': raw_dict}
    else:
        sorted_list = sorted(controllerNodeList, key=lambda x: x[0].lower())
        print(tabulate(sorted_list, headers))

def show_metrics(raw: bool, metric: typing.Optional[str], interface: typing.Optional[str]):
    def format_counts(value_list):
        aggregated_counts = {}

        for direction, value_type, count in value_list:
            count = int(count)

            if value_type not in aggregated_counts:
                aggregated_counts[value_type] = {'rx': 0, 'tx': 0}

            aggregated_counts[value_type][direction] += count
        sorted_list = sorted([[tmp, counts['rx'], counts['tx']] for tmp, counts in aggregated_counts.items()], key=lambda x: x[0])

        return sorted_list

    def output_parse(pattern, line):
        match = re.search(pattern, line)

        if match:
            # Join the matched groups into a single comma-separated string
            result = ','.join(match.groups())
            return result

    primary_port = conf.get_config_dict(['interfaces', 'zerotier', interface], key_mangling=('-', '_'),
                            get_first_key=True).get('primary_port')

    accepted_packets_list, errors_list, latency_list, peer_packet_list, packet_type_list, protocol_list, peer_error_list = [], [], [], [], [], [], []

    try:
        with open(f'/config/vyos-zerotier/{interface}/metricstoken.secret', 'r') as file:
            authtoken = file.read()
    except FileNotFoundError:
        raise vyos.opmode.Error(f'metricstoken.secret not found! This should have been created when when creating an interface. Does {interface} exist?')

    network_data = zt_api(f'http://127.0.0.1:{primary_port}/metrics', authtoken, 'service')

    for i in network_data.text.split('\n'):
        # Skip comments
        if i.startswith('# '):
            continue

        if 'packettype' == metric:
            if 'packet_type=' in i:
                pattern = r'zt_packet\{direction="(tx|rx)",packet_type="([^"]+)"\}\s(\d+)'
                packet_type_list.append(output_parse(pattern, i).split(','))
        elif 'errors' == metric:
            if 'error_type=' in i:
                pattern = r'zt_packet_error\{direction="(tx|rx)",error_type="([^"]+)"\}\s(\d+)'
                errors_list.append(output_parse(pattern, i).split(','))
        elif 'acceptedpackets' == metric:
            if 'zt_network_packets{' in i:
                pattern = r'zt_network_packets\{accepted="(yes|no)",direction="(tx|rx)",network_id="([^"]+)"\}\s(\d+)'
                accepted_packets_list.append(output_parse(pattern, i).split(','))
        elif 'protocols' == metric:
            if 'protocol="' in i:
                pattern = r'zt_data\{direction="(tx|rx)",protocol="([^"]+)"\}\s(\d+)'
                protocol_list.append(output_parse(pattern, i).split(','))
        elif 'peerpackets' == metric:
            if 'zt_peer_packets{' in i:
                pattern = r'zt_peer_packets\{direction="(tx|rx)",node_id="([^"]+)"\}\s(\d+)'
                peer_packet_list.append(output_parse(pattern, i).split(','))
        elif 'peerpacketerrors' == metric:
            if 'zt_peer_packet_errors{' in i:
                pattern = r'node_id="([^"]+)"\} (\d+)'
                peer_error_list.append(output_parse(pattern, i).split(','))
        elif 'latency' == metric:
            if 'zt_peer_latency_bucket{' in i:
                latency_list.append(i.replace('zt_peer_latency_bucket{','').replace('"', '').replace('node_id=', '').replace('} ', ',').split(','))

    if 'peerpackets' == metric:
        sorted_list = format_counts(peer_packet_list)
        headers = ["Peer", "RX Count", "TX Count"]
    elif 'protocols' == metric:
        sorted_list = format_counts(protocol_list)
        headers = ["Protocol", "RX Count", "TX Count"]
    elif 'packettype' == metric:
        sorted_list = format_counts(packet_type_list)
        headers = ["Packet Type", "RX Count", "TX Count"]
    elif 'errors' == metric:
        sorted_list = format_counts(errors_list)
        headers = ["Error Type", "RX Count", "TX Count"]
    elif 'acceptedpackets' == metric:
        sorted_list = sorted(accepted_packets_list, key=lambda x: (x[2], x[0]))
        headers = ["Allowed", "Direction", "NetworkID", "Count"]
    elif 'peerpacketerrors' == metric:
        sorted_list = sorted(peer_error_list, key=lambda x: (x[1], x[0]))
        headers = ["Peer Node ID", "Error Count"]
    elif 'latency' == metric:
        node_data = {}

        for node_id, le_value, count in latency_list:
            if node_id not in node_data:
                node_data[node_id] = {}
            node_data[node_id][le_value] = int(count)

        headers = ["NodeID", "le=1", "le=3", "le=6", "le=10", "le=30", "le=60", "le=100", "le=300", "le=600", "le=1000", "le=+Inf"]

        table_data = []

        for node_id, counts in sorted(node_data.items()):
            row = [node_id] + [counts.get(le, 0) for le in headers[1:]]
            table_data.append(row)

        sorted_list = sorted(table_data, key=lambda x: (x[2], x[0]))

    print(tabulate(sorted_list, headers))

def show_command(raw: bool, command: typing.Optional[str], interface: typing.Optional[str]):
    # Validate commands
    def is_10_digit_hex(value):
        pattern = re.compile(r'^[0-9a-fA-F]{10}$')
        return bool(pattern.match(value))

    # Valdiate that provide Node-ID is a 10-digit hexadecimal value
    if 'bond' in command and 'show' in command:
        tmp = is_10_digit_hex(command.split()[1])
        if not tmp:
            raise vyos.opmode.Error(f"'{command.split()[1]}' must be a 10-digit hex value")

    if 'listnetworks' == command or 'peers' == command or ('bond' in command and 'list' in command):
        error_msg = f"Command could not be executed. Is {interface} up?"

    try:
        if raw:
            return {'zerotier': json.loads(cmd(f"podman exec vyos_created_{interface} zerotier-cli {command} -j"))}
        else:
            print(cmd(f"podman exec vyos_created_{interface} zerotier-cli {command}"))
    except:
        raise vyos.opmode.DataUnavailable(error_msg)

def set_allowed(raw: bool, allowed: typing.Optional[str], interface: typing.Optional[str], state: typing.Optional[str]):
    allow_dict = conf.get_config_dict(['interfaces', 'zerotier', interface], key_mangling=('-', '_'),
                            get_first_key=True)

    network_id = allow_dict.get('network_id')

    if not network_id:
        raise vyos.opmode.DataUnavailable(f"Command could not be executed. Is {interface} up?")

    cmd(f"podman exec vyos_created_{interface} zerotier-cli set {network_id} {allowed}={state}")

def reset_node(raw: bool, file: typing.Optional[str]):
    # Since elements in the config directory are important to node identities and secrets,
    # a backup is created when deleting a node. This can be used to recover the config
    interface_name = file.split('_')[0]
    directory = f"/config/vyos-zerotier/{interface_name}"

    # Check if the directory exists
    if os.path.exists(directory) and os.path.isdir(directory):
        raise vyos.opmode.Error(f"A directory for {interface_name} already exists, unable to restore")
    else:
        try:
            with zipfile.ZipFile(f"/config/vyos-zerotier/backup/{file}", 'r') as zip_ref:
                zip_ref.extractall("/")
        except Exception as e:
            print(f"An error occurred: {e}")
            raise vyos.opmode.Error(f"Unable to restore backup {file}")

if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
