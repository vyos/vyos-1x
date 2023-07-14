#!/usr/bin/env python3
#
# Copyright (C) 2019-2023 VyOS maintainers and contributors
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

from vyos.config import Config
from vyos.utils.process import popen
from vyos.utils.process import DEVNULL

cmd_dict = {
    'cmd_base'  : '/usr/bin/accel-cmd -p {} ',
    'vpn_types' : {
        'pppoe' : 2001,
        'pptp'  : 2003,
        'l2tp'  : 2004,
        'sstp'  : 2005
    },
    'conf_proto' : {
        'pppoe' : 'service pppoe-server',
        'pptp'  : 'vpn pptp remote-access',
        'l2tp'  : 'vpn l2tp remote-access',
        'sstp'  : 'vpn sstp'
    }
}

def is_service_configured(proto):
    if not Config().exists_effective(cmd_dict['conf_proto'][proto]):
        print("Service {} is not configured".format(proto))
        sys.exit(1)

def main():
    #parese args
    parser = argparse.ArgumentParser()
    parser.add_argument('--proto', help='Possible protocols pppoe|pptp|l2tp|sstp', required=True)
    parser.add_argument('--action', help='Action command', required=True)
    args = parser.parse_args()

    if args.proto in cmd_dict['vpn_types'] and args.action:
        # Check is service configured
        is_service_configured(args.proto)

        if args.action == "show sessions":
            ses_pattern = " ifname,username,ip,ip6,ip6-dp,calling-sid,rate-limit,state,uptime,rx-bytes,tx-bytes"
        else:
            ses_pattern = ""

        output, err = popen(cmd_dict['cmd_base'].format(cmd_dict['vpn_types'][args.proto]) + args.action + ses_pattern, stderr=DEVNULL, decode='utf-8')
        if not err:
            try:
                print(f' {output}')
            except:
                sys.exit(0)
        else:
            print("{} server is not running".format(args.proto))

    else:
        print("Param --proto and --action required")
        sys.exit(1)

if __name__ == '__main__':
    main()
