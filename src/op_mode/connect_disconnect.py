#!/usr/bin/env python3
#
# Copyright (C) 2020-2024 VyOS maintainers and contributors
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

import os
import argparse

from psutil import process_iter

from vyos.configquery import ConfigTreeQuery
from vyos.utils.process import call
from vyos.utils.commit import commit_in_progress
from vyos.utils.network import is_wwan_connected
from vyos.utils.process import DEVNULL

def check_ppp_interface(interface):
    if not os.path.isfile(f'/etc/ppp/peers/{interface}'):
        print(f'Interface {interface} does not exist!')
        exit(1)

def check_ppp_running(interface):
    """ Check if PPP process is running in the interface in question """
    for p in process_iter():
        if "pppd" in p.name():
            if interface in p.cmdline():
                return True

    return False

def connect(interface):
    """ Connect dialer interface """

    if interface.startswith('pppoe') or interface.startswith('sstpc'):
        check_ppp_interface(interface)
        # Check if interface is already dialed
        if os.path.isdir(f'/sys/class/net/{interface}'):
            print(f'Interface {interface}: already connected!')
        elif check_ppp_running(interface):
            print(f'Interface {interface}: connection is being established!')
        else:
            print(f'Interface {interface}: connecting...')
            call(f'systemctl restart ppp@{interface}.service')
    elif interface.startswith('wwan'):
        if is_wwan_connected(interface):
            print(f'Interface {interface}: already connected!')
        else:
            call(f'VYOS_TAGNODE_VALUE={interface} /usr/libexec/vyos/conf_mode/interfaces_wwan.py')
    else:
        print(f'Unknown interface {interface}, cannot connect. Aborting!')

    # Reaply QoS configuration
    config = ConfigTreeQuery()
    if config.exists(f'qos interface {interface}'):
        count = 1
        while commit_in_progress():
            if ( count % 60 == 0 ):
                print(f'Commit still in progress after {count}s - waiting')
            count += 1
            time.sleep(1)
        call('/usr/libexec/vyos/conf_mode/qos.py')

def disconnect(interface):
    """ Disconnect dialer interface """

    if interface.startswith('pppoe') or interface.startswith('sstpc'):
        check_ppp_interface(interface)

        # Check if interface is already down
        if not check_ppp_running(interface):
            print(f'Interface {interface}: connection is already down')
        else:
            print(f'Interface {interface}: disconnecting...')
            call(f'systemctl stop ppp@{interface}.service')
    elif interface.startswith('wwan'):
        if not is_wwan_connected(interface):
            print(f'Interface {interface}: connection is already down')
        else:
            modem = interface.lstrip('wwan')
            call(f'mmcli --modem {modem} --simple-disconnect', stdout=DEVNULL)
    else:
        print(f'Unknown interface {interface}, cannot disconnect. Aborting!')

def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--connect", help="Bring up a connection-oriented network interface", action="store_true")
    group.add_argument("--disconnect", help="Take down connection-oriented network interface", action="store_true")
    parser.add_argument("--interface", help="Interface name", action="store", required=True)
    args = parser.parse_args()

    if args.connect or args.disconnect:
        if args.disconnect:
            disconnect(args.interface)

        if args.connect:
            if commit_in_progress():
                print('Cannot connect while a commit is in progress')
                exit(1)
            connect(args.interface)

    else:
        parser.print_help()

    exit(0)

if __name__ == '__main__':
     main()
