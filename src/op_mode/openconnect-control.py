#!/usr/bin/env python3
#
# Copyright (C) 2020-2023 VyOS maintainers and contributors
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
import json

from tabulate import tabulate

from vyos.config import Config
from vyos.utils.process import popen
from vyos.utils.process import run
from vyos.utils.process import DEVNULL

occtl        = '/usr/bin/occtl'
occtl_socket = '/run/ocserv/occtl.socket'

def show_sessions():
    out, code = popen("sudo {0} -j -s {1} show users".format(occtl, occtl_socket),stderr=DEVNULL)
    if code:
        sys.exit('Cannot get openconnect users information')
    else:
        headers = ["interface", "username", "ip", "remote IP", "RX", "TX", "state", "uptime"]
        sessions = json.loads(out)
        ses_list = []
        for ses in sessions:
            ses_list.append([ses["Device"], ses["Username"], ses["IPv4"], ses["Remote IP"], ses["_RX"], ses["_TX"], ses["State"], ses["_Connected at"]])
        if len(ses_list) > 0:
            print(tabulate(ses_list, headers))
        else:
            print("No active openconnect sessions")

def is_ocserv_configured():
    if not Config().exists_effective('vpn openconnect'):
        print("vpn openconnect server is not configured")
        sys.exit(1)

def main():
    #parese args
    parser = argparse.ArgumentParser()
    parser.add_argument('--action', help='Control action', required=True)
    parser.add_argument('--selector', help='Selector username|ifname|sid', required=False)
    parser.add_argument('--target', help='Target must contain username|ifname|sid', required=False)
    args = parser.parse_args()


    # Check is Openconnect server configured
    is_ocserv_configured()

    if args.action == "restart":
        run("sudo systemctl restart ocserv.service")
        sys.exit(0)
    elif args.action == "show_sessions":
        show_sessions()

if __name__ == '__main__':
    main()
