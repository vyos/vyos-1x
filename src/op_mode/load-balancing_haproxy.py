#!/usr/bin/env python3
#
# Copyright (C) 2023-2024 VyOS maintainers and contributors
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

import json
import socket
import sys

from tabulate import tabulate
from vyos.configquery import ConfigTreeQuery

import vyos.opmode

socket_path = '/run/haproxy/admin.sock'
timeout = 5


def _execute_haproxy_command(command):
    """Execute a command on the HAProxy UNIX socket and retrieve the response.

    Args:
        command (str): The command to be executed.

    Returns:
        str: The response received from the HAProxy UNIX socket.

    Raises:
        socket.error: If there is an error while connecting or communicating with the socket.

    Finally:
        Closes the socket connection.

    Notes:
        - HAProxy expects a newline character at the end of the command.
        - The socket connection is established using the HAProxy UNIX socket.
        - The response from the socket is received and decoded.

    Example:
        response = _execute_haproxy_command('show stat')
        print(response)
    """
    try:
        # HAProxy expects new line for command
        command = f'{command}\n'

        # Connect to the HAProxy UNIX socket
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(socket_path)

        # Set the socket timeout
        sock.settimeout(timeout)

        # Send the command
        sock.sendall(command.encode())

        # Receive and decode the response
        response = b''
        while True:
            data = sock.recv(4096)
            if not data:
                break
            response += data
        response = response.decode()

        return (response)

    except socket.error as e:
        print(f"Error: {e}")

    finally:
        # Close the socket
        sock.close()


def _convert_seconds(seconds):
    """Convert seconds to days, hours, minutes, and seconds.

    Args:
        seconds (int): The number of seconds to convert.

    Returns:
        tuple: A tuple containing the number of days, hours, minutes, and seconds.
    """
    minutes = seconds // 60
    hours = minutes // 60
    days = hours // 24

    return days, hours % 24, minutes % 60, seconds % 60


def _last_change_format(seconds):
    """Format the time components into a string representation.

    Args:
        seconds (int): The total number of seconds.

    Returns:
        str: The formatted time string with days, hours, minutes, and seconds.

    Examples:
        >>> _last_change_format(1434)
        '23m54s'
        >>> _last_change_format(93734)
        '1d0h23m54s'
        >>> _last_change_format(85434)
        '23h23m54s'
    """
    days, hours, minutes, seconds = _convert_seconds(seconds)
    time_format = ""

    if days:
        time_format += f"{days}d"
    if hours:
        time_format += f"{hours}h"
    if minutes:
        time_format += f"{minutes}m"
    if seconds:
        time_format += f"{seconds}s"

    return time_format


def _get_json_data():
    """Get haproxy data format JSON"""
    return _execute_haproxy_command('show stat json')


def _get_raw_data():
    """Retrieve raw data from JSON and organize it into a dictionary.

    Returns:
        dict: A dictionary containing the organized data categorized
              into frontend, backend, and server.
    """

    data = json.loads(_get_json_data())
    lb_dict = {'frontend': [], 'backend': [], 'server': []}

    for key in data:
        frontend = []
        backend = []
        server = []
        for entry in key:
            obj_type = entry['objType'].lower()
            position = entry['field']['pos']
            name = entry['field']['name']
            value = entry['value']['value']

            dict_entry = {'pos': position, 'name': {name: value}}

            if obj_type == 'frontend':
                frontend.append(dict_entry)
            elif obj_type == 'backend':
                backend.append(dict_entry)
            elif obj_type == 'server':
                server.append(dict_entry)

        if len(frontend) > 0:
            lb_dict['frontend'].append(frontend)
        if len(backend) > 0:
            lb_dict['backend'].append(backend)
        if len(server) > 0:
            lb_dict['server'].append(server)

    return lb_dict


def _get_formatted_output(data):
    """
    Format the data into a tabulated output.

    Args:
        data (dict): The data to be formatted.

    Returns:
        str: The tabulated output representing the formatted data.
    """
    table = []
    headers = [
        "Proxy name", "Role", "Status", "Req rate", "Resp time", "Last change"
    ]

    for key in data:
        for item in data[key]:
            row = [None] * len(headers)

            for element in item:
                if 'pxname' in element['name']:
                    row[0] = element['name']['pxname']
                elif 'svname' in element['name']:
                    row[1] = element['name']['svname']
                elif 'status' in element['name']:
                    row[2] = element['name']['status']
                elif 'req_rate' in element['name']:
                    row[3] = element['name']['req_rate']
                elif 'rtime' in element['name']:
                    row[4] = f"{element['name']['rtime']} ms"
                elif 'lastchg' in element['name']:
                    row[5] = _last_change_format(element['name']['lastchg'])
            table.append(row)

    out = tabulate(table, headers, numalign="left")
    return out


def show(raw: bool):
    config = ConfigTreeQuery()
    if not config.exists('load-balancing haproxy'):
        raise vyos.opmode.UnconfiguredSubsystem('Haproxy is not configured')

    data = _get_raw_data()
    if raw:
        return data
    else:
        return _get_formatted_output(data)


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
