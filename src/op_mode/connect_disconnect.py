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


PPP_LOGFILE = '/var/log/vyatta/ppp_{}.log'

def check_interface(interface):
    if not os.path.isfile('/etc/ppp/peers/{}'.format(interface)):
        print('Interface {}: invalid!'.format(interface))
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
    if os.path.isdir('/sys/class/net/{}'.format(interface)):
        print('Interface {}: already connected!'.format(interface))
    elif check_ppp_running(interface):
        print('Interface {}: connection is beeing established!'.format(interface))
    else:
        print('Interface {}: connecting...'.format(interface))
        user = os.environ['SUDO_USER']
        tm = strftime("%a %d %b %Y %I:%M:%S %p %Z", localtime(time()))
        with open(PPP_LOGFILE.format(interface), 'a') as f:
            f.write('{}: user {} started PPP daemon for {} by connect command\n'.format(tm, user, interface))
            call('umask 0; setsid sh -c "nohup /usr/sbin/pppd call {0} > /tmp/{0}.log 2>&1 &"'.format(interface))


def disconnect(interface):
    """
    Disconnect PPP interface
    """
    check_interface(interface)

    # Check if interface is already down
    if not check_ppp_running(interface):
        print('Interface {}: connection is already down'.format(interface))
    else:
        print('Interface {}: disconnecting...'.format(interface))
        user = os.environ['SUDO_USER']
        tm = strftime("%a %d %b %Y %I:%M:%S %p %Z", localtime(time()))
        with open(PPP_LOGFILE.format(interface), 'a') as f:
            f.write('{}: user {} stopped PPP daemon for {} by disconnect command\n'.format(tm, user, interface))
            call('/usr/bin/poff "{}"'.format(interface))

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
