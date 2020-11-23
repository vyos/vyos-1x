#!/usr/bin/env python3
#
# Copyright (C) 2019 VyOS maintainers and contributors
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

import argparse
import re

from sys import exit
from copy import deepcopy

from vyos.config import Config
from vyos.util import popen

parser = argparse.ArgumentParser()
parser.add_argument("-s", "--scan", help="Scan for Wireless APs on given interface, e.g. 'wlan0'")
parser.add_argument("-b", "--brief", action="store_true", help="Show wireless configuration")
parser.add_argument("-c", "--stations", help="Show wireless clients connected on interface, e.g. 'wlan0'")

def show_brief():
    config = Config()
    if len(config.list_effective_nodes('interfaces wireless')) == 0:
        print("No Wireless interfaces configured")
        exit(0)

    interfaces = []
    for intf in config.list_effective_nodes('interfaces wireless'):
        config.set_level(f'interfaces wireless {intf}')
        data = { 'name': intf }
        data['type'] = config.return_effective_value('type') or '-'
        data['ssid'] = config.return_effective_value('ssid') or '-'
        data['channel'] = config.return_effective_value('channel') or '-'
        interfaces.append(data)

    return interfaces

def ssid_scan(intf):
    # XXX: This ignores errors
    tmp, _ = popen(f'/sbin/iw dev {intf} scan ap-force')
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

def show_clients(intf):
    # XXX: This ignores errors
    tmp, _ = popen(f'/sbin/iw dev {intf} station dump')
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

if __name__ == '__main__':
    args = parser.parse_args()

    if args.scan:
        print("Address            SSID                          Channel  Signal (dbm)")
        for network in ssid_scan(args.scan):
            print("{:<17}  {:<32}  {:>3}  {}".format(network['mac'],
                                                     network['ssid'],
                                                     network['channel'],
                                                     network['signal']))
        exit(0)

    elif args.brief:
        print("Interface  Type          SSID                         Channel")
        for intf in show_brief():
            print("{:<9}  {:<12}  {:<32} {:>3}".format(intf['name'],
                                                      intf['type'],
                                                      intf['ssid'],
                                                      intf['channel']))
        exit(0)

    elif args.stations:
        print("Station            Signal     RX: bytes    packets        TX: bytes     packets")
        for client in show_clients(args.stations):
            print("{:<17}  {:>3}  {:>15}  {:>9}  {:>15}  {:>10} ".format(client['mac'],
                                                 client['signal'], client['rx_bytes'], client['rx_packets'], client['tx_bytes'], client['tx_packets']))

        exit(0)

    else:
        parser.print_help()
        exit(1)
