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
import argparse
#import re

from vyos.util import run, DEVNULL

pptp_base = '/usr/bin/accel-cmd -p 2003 terminate {} {}'
l2tp_base = '/usr/bin/accel-cmd -p 2004 terminate {} {}'

def terminate_sessions(username='', interface='', protocol=''):
    if username:
        if username == "all_users":
            if protocol == "pptp":
                pptp_cmd = pptp_base.format('all','')
                run(pptp_cmd, stdout=DEVNULL, stderr=DEVNULL)
                return
            elif protocol == "l2tp":
                l2tp_cmd = l2tp_base.format('all', '')
                run(l2tp_cmd, stdout=DEVNULL, stderr=DEVNULL)
                return
            else:
                pptp_cmd = pptp_base.format('all', '')
                run(pptp_cmd, stdout=DEVNULL, stderr=DEVNULL)
                l2tp_cmd = l2tp_base.format('all', '')
                run(l2tp_cmd, stdout=DEVNULL, stderr=DEVNULL)
                return

        if protocol == "pptp":
            pptp_cmd = pptp_base.format('username', username)
            run(pptp_cmd, stdout=DEVNULL, stderr=DEVNULL)
            return
        elif protocol == "l2tp":
            l2tp_cmd = l2tp_base.format('username', username)
            run(l2tp_cmd, stdout=DEVNULL, stderr=DEVNULL)
            return
        else:
            pptp_cmd = pptp_base.format('username', username)
            run(pptp_cmd, stdout=DEVNULL, stderr=DEVNULL)
            l2tp_cmd.append("terminate username {0}".format(username))
            run(l2tp_cmd, stdout=DEVNULL, stderr=DEVNULL)
            return

    # rewrite `terminate by interface` if pptp will have pptp%d interface naming
    if interface:
        pptp_cmd = pptp_base.format('if', interface)
        run(pptp_cmd, stdout=DEVNULL, stderr=DEVNULL)
        l2tp_cmd = l2tp_base.format('if', interface)
        run(l2tp_cmd, stdout=DEVNULL, stderr=DEVNULL)
       

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
