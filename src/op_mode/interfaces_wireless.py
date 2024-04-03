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

import re
import sys
import vyos.opmode

from copy import deepcopy
from tabulate import tabulate
from vyos.utils.process import popen
from vyos.configquery import ConfigTreeQuery

def _verify(func):
    """Decorator checks if Wireless LAN config exists"""
    from functools import wraps

    @wraps(func)
    def _wrapper(*args, **kwargs):
        config = ConfigTreeQuery()
        if not config.exists(['interfaces', 'wireless']):
            unconf_message = 'No Wireless interfaces configured'
            raise vyos.opmode.UnconfiguredSubsystem(unconf_message)
        return func(*args, **kwargs)
    return _wrapper

def _get_raw_info_data():
    output_data = []

    config = ConfigTreeQuery()
    raw = config.get_config_dict(['interfaces', 'wireless'], effective=True,
                                 get_first_key=True, key_mangling=('-', '_'))
    for interface, interface_config in raw.items():
        tmp = {'name' : interface}

        if 'type' in interface_config:
            tmp.update({'type' : interface_config['type']})
        else:
            tmp.update({'type' : '-'})

        if 'ssid' in interface_config:
            tmp.update({'ssid' : interface_config['ssid']})
        else:
            tmp.update({'ssid' : '-'})

        if 'channel' in interface_config:
            tmp.update({'channel' : interface_config['channel']})
        else:
            tmp.update({'channel' : '-'})

        output_data.append(tmp)

    return output_data

def _get_formatted_info_output(raw_data):
    output=[]
    for ssid in raw_data:
        output.append([ssid['name'], ssid['type'], ssid['ssid'], ssid['channel']])

    headers = ["Interface", "Type", "SSID", "Channel"]
    print(tabulate(output, headers, numalign="left"))

def _get_raw_scan_data(intf_name):
    # XXX: This ignores errors
    tmp, _ = popen(f'iw dev {intf_name} scan ap-force')
    networks = []
    data = {
        'ssid': '',
        'mac': '',
        'channel': '',
        'signal': ''
    }
    re_mac = re.compile(r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})')
    for line in tmp.splitlines():
        if line.startswith('BSS '):
            ssid = deepcopy(data)
            ssid['mac'] = re.search(re_mac, line).group()

        elif line.lstrip().startswith('SSID: '):
            # SSID can be "    SSID: WLAN-57 6405", thus strip all leading whitespaces
            ssid['ssid'] = line.lstrip().split(':')[-1].lstrip()

        elif line.lstrip().startswith('signal: '):
            # Siganl can be "   signal: -67.00 dBm", thus strip all leading whitespaces
            ssid['signal'] = line.lstrip().split(':')[-1].split()[0]

        elif line.lstrip().startswith('DS Parameter set: channel'):
            # Channel can be "        DS Parameter set: channel 6" , thus
            # strip all leading whitespaces
            ssid['channel'] = line.lstrip().split(':')[-1].split()[-1]
            networks.append(ssid)
            continue

    return networks

def _format_scan_data(raw_data):
    output=[]
    for ssid in raw_data:
        output.append([ssid['mac'], ssid['ssid'], ssid['channel'], ssid['signal']])
    headers = ["Address", "SSID", "Channel", "Signal (dbm)"]
    return tabulate(output, headers, numalign="left")

def _get_raw_station_data(intf_name):
    # XXX: This ignores errors
    tmp, _ = popen(f'iw dev {intf_name} station dump')
    clients = []
    data = {
        'mac': '',
        'signal': '',
        'rx_bytes': '',
        'rx_packets': '',
        'tx_bytes': '',
        'tx_packets': ''
    }
    re_mac = re.compile(r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})')
    for line in tmp.splitlines():
        if line.startswith('Station'):
            client = deepcopy(data)
            client['mac'] = re.search(re_mac, line).group()

        elif line.lstrip().startswith('signal avg:'):
            client['signal'] = line.lstrip().split(':')[-1].lstrip().split()[0]

        elif line.lstrip().startswith('rx bytes:'):
            client['rx_bytes'] = line.lstrip().split(':')[-1].lstrip()

        elif line.lstrip().startswith('rx packets:'):
            client['rx_packets'] = line.lstrip().split(':')[-1].lstrip()

        elif line.lstrip().startswith('tx bytes:'):
            client['tx_bytes'] = line.lstrip().split(':')[-1].lstrip()

        elif line.lstrip().startswith('tx packets:'):
            client['tx_packets'] = line.lstrip().split(':')[-1].lstrip()
            clients.append(client)
            continue

    return clients

def _format_station_data(raw_data):
    output=[]
    for ssid in raw_data:
        output.append([ssid['mac'], ssid['signal'], ssid['rx_bytes'], ssid['rx_packets'], ssid['tx_bytes'], ssid['tx_packets']])
    headers = ["Station", "Signal", "RX bytes", "RX packets", "TX bytes", "TX packets"]
    return tabulate(output, headers, numalign="left")

@_verify
def show_info(raw: bool):
    info_data = _get_raw_info_data()
    if raw:
        return info_data
    return _get_formatted_info_output(info_data)

def show_scan(raw: bool, intf_name: str):
    data = _get_raw_scan_data(intf_name)
    if raw:
        return data
    return _format_scan_data(data)

@_verify
def show_stations(raw: bool, intf_name: str):
    data = _get_raw_station_data(intf_name)
    if raw:
        return data
    return _format_station_data(data)

if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
