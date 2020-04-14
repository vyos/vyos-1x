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

import sys
import argparse

from vyos.config import Config
from vyos.util import popen, run

cmd_dict = {
    'cmd_base'   : '/usr/bin/accel-cmd -p 2002 ',
    'selector'   : ['if', 'username', 'sid'],
    'actions'     : {
        'show_sessions'  : 'show sessions',
        'show_stat'      : 'show stat',
        'terminate'      : 'teminate'
    }
}

def is_ipoe_configured():
    if not Config().exists_effective('service ipoe-server'):
        print("Service IPoE is not configured")
        sys.exit(1)

def main():
    #parese args
    parser = argparse.ArgumentParser()
    parser.add_argument('--action', help='Control action', required=True)
    parser.add_argument('--selector', help='Selector username|ifname|sid', required=False)
    parser.add_argument('--target', help='Target must contain username|ifname|sid', required=False)
    args = parser.parse_args()


    # Check is IPoE configured
    is_ipoe_configured()

    if args.action == "restart":
        run(cmd_dict['cmd_base'] + "restart")
        sys.exit(0)

    if args.action in cmd_dict['actions']:
        if args.selector in cmd_dict['selector'] and args.target:
            run(cmd_dict['cmd_base'] + "{0} {1} {2}".format(args.action, args.selector, args.target))
        else:
            output, err = popen(cmd_dict['cmd_base'] + cmd_dict['actions'][args.action], decode='utf-8')
            if not err:
                print(output)
            else:
                print("IPoE server is not running")

if __name__ == '__main__':
    main()
