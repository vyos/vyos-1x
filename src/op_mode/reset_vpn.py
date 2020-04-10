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

import sys
import argparse

from vyos.util import run

cmd_dict = {
    'cmd_base'  : '/usr/bin/accel-cmd -p {} terminate {} {}',
    'vpn_types' : {
        'pptp' : 2003,
        'l2tp' : 2004,
        'sstp' : 2005
    }
}

def terminate_sessions(username='', interface='', protocol=''):

    # Reset vpn connections by username
    if protocol in cmd_dict['vpn_types']:
        if username == "all_users":
            run(cmd_dict['cmd_base'].format(cmd_dict['vpn_types'][protocol], 'all', ''))
        else:
            run(cmd_dict['cmd_base'].format(cmd_dict['vpn_types'][protocol], 'username', username))

    # Reset vpn connections by ifname
    elif interface:
        for proto in cmd_dict['vpn_types']:
            run(cmd_dict['cmd_base'].format(cmd_dict['vpn_types'][proto], 'if', interface))

    elif username:
        # Reset all vpn connections
        if username == "all_users":
            for proto in cmd_dict['vpn_types']:
                run(cmd_dict['cmd_base'].format(cmd_dict['vpn_types'][proto], 'all', ''))
        else:
            for proto in cmd_dict['vpn_types']:
                run(cmd_dict['cmd_base'].format(cmd_dict['vpn_types'][proto], 'username', username))

def main():
    #parese args
    parser = argparse.ArgumentParser()
    parser.add_argument('--username', help='Terminate by username (all_users used for disconnect all users)', required=False)
    parser.add_argument('--interface', help='Terminate by interface', required=False)
    parser.add_argument('--protocol', help='Set protocol (pptp|l2tp|sstp)', required=False)
    args = parser.parse_args()

    if args.username or args.interface:
        terminate_sessions(username=args.username, interface=args.interface, protocol=args.protocol)
    else:
        print("Param --username or --interface required")
        sys.exit(1)

    terminate_sessions()


if __name__ == '__main__':
    main()
