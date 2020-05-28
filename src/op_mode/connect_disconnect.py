#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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

from sys import exit
from psutil import process_iter
from time import strftime, localtime, time

from vyos.util import call

def check_interface(interface):
    if not os.path.isfile(f'/etc/ppp/peers/{interface}'):
        print(f'Interface {interface}: invalid!')
        exit(1)

def check_ppp_running(interface):
    """
    Check if ppp process is running in the interface in question
    """
    for p in process_iter():
        if "pppd" in p.name():
            if interface in p.cmdline():
                return True

    return False

def connect(interface):
    """
    Connect PPP interface
    """
    check_interface(interface)

    # Check if interface is already dialed
    if os.path.isdir(f'/sys/class/net/{interface}'):
        print(f'Interface {interface}: already connected!')
    elif check_ppp_running(interface):
        print(f'Interface {interface}: connection is beeing established!')
    else:
        print(f'Interface {interface}: connecting...')
        call(f'systemctl restart ppp@{interface}.service')

def disconnect(interface):
    """
    Disconnect PPP interface
    """
    check_interface(interface)

    # Check if interface is already down
    if not check_ppp_running(interface):
        print(f'Interface {interface}: connection is already down')
    else:
        print(f'Interface {interface}: disconnecting...')
        call(f'systemctl stop ppp@{interface}.service')

def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--connect", help="Bring up a connection-oriented network interface", action="store")
    group.add_argument("--disconnect", help="Take down connection-oriented network interface", action="store")
    args = parser.parse_args()

    if args.connect:
        connect(args.connect)
    elif args.disconnect:
        disconnect(args.disconnect)
    else:
        parser.print_help()

    exit(0)

if __name__ == '__main__':
     main()
