#!/usr/bin/env python3
#
# Copyright (C) 2018 VyOS maintainers and contributors
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

# File: restart_dhcp_relay.py
# Purpose:
#    Restart IPv4 and IPv6 DHCP relay instances of dhcrelay service

import sys
import argparse
import os

import vyos.config
from vyos.util import call


parser = argparse.ArgumentParser()
parser.add_argument("--ipv4", action="store_true", help="Restart IPv4 DHCP relay")
parser.add_argument("--ipv6", action="store_true", help="Restart IPv6 DHCP relay")

if __name__ == '__main__':
    args = parser.parse_args()
    c = vyos.config.Config()

    if args.ipv4:
        # Do nothing if service is not configured
        if not c.exists_effective('service dhcp-relay'):
            print("DHCP relay service not configured")
        else:
            call('sudo systemctl restart isc-dhcp-relay.service')

        sys.exit(0)
    elif args.ipv6:
        # Do nothing if service is not configured
        if not c.exists_effective('service dhcpv6-relay'):
            print("DHCPv6 relay service not configured")
        else:
            call('sudo systemctl restart isc-dhcpv6-relay.service')

        sys.exit(0)
    else:
        parser.print_help()
        sys.exit(1)
