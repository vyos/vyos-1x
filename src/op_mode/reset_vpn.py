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

# import os
import sys
import subprocess
import argparse
#import re

pptp_cmd = ["/usr/bin/accel-cmd", "-p 2003"]
l2tp_cmd = ["/usr/bin/accel-cmd", "-p 2004"]

def terminate_sessions(username='', interface='', protocol=''):
    if username:
        if username == "all_users":
            if protocol == "pptp":
                pptp_cmd.append("terminate all")
                subprocess.call(pptp_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            elif protocol == "l2tp":
                l2tp_cmd.append("terminate all")
                subprocess.call(l2tp_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            else:
                pptp_cmd.append("terminate all")
                subprocess.call(pptp_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                l2tp_cmd.append("terminate all")
                subprocess.call(l2tp_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return

        if protocol == "pptp":
            pptp_cmd.append("terminate username {0}".format(username))
            subprocess.call(pptp_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        elif protocol == "l2tp":
            l2tp_cmd.append("terminate username {0}".format(username))
            subprocess.call(l2tp_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        else:
            pptp_cmd.append("terminate username {0}".format(username))
            subprocess.call(pptp_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            l2tp_cmd.append("terminate username {0}".format(username))
            subprocess.call(l2tp_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return

    # rewrite `terminate by interface` if pptp will have pptp%d interface naming
    if interface:
        pptp_cmd.append("terminate if {0}".format(interface))
        subprocess.call(pptp_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        l2tp_cmd.append("terminate if {0}".format(interface))
        subprocess.call(l2tp_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
       

def main():
    #parese args
    parser = argparse.ArgumentParser()
    parser.add_argument('--username', help='Terminate by username (all_users used for disconnect all users)', required=False)
    parser.add_argument('--interface', help='Terminate by interface', required=False)
    parser.add_argument('--protocol', help='Set protocol (pptp|l2tp)', required=False)
    args = parser.parse_args()

    if args.username or args.interface:
        terminate_sessions(username=args.username, interface=args.interface, protocol=args.protocol)
    else:
        print("Param --username or --interface required")
        sys.exit(1)

    terminate_sessions()


if __name__ == '__main__':
    main()
