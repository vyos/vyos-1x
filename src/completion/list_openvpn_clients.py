#!/usr/bin/env python3
#
# Copyright (C) 2019-2024 VyOS maintainers and contributors
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

import argparse

from vyos.ifconfig import Section

def get_client_from_interface(interface):
    clients = []
    try:
        with open('/run/openvpn/' + interface + '.status', 'r') as f:
            dump = False
            for line in f:
                if line.startswith("Common Name,"):
                    dump = True
                    continue
                if line.startswith("ROUTING TABLE"):
                    dump = False
                    continue
                if dump:
                    # client entry in this file looks like
                    # client1,172.18.202.10:47495,2957,2851,Sat Aug 17 00:07:11 2019
                    # we are only interested in the client name 'client1'
                    clients.append(line.split(',')[0])
    except:
        pass

    return clients

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--interface", type=str, help="List connected clients per interface")
    parser.add_argument("-a", "--all", action='store_true', help="List all connected OpenVPN clients")
    args = parser.parse_args()

    clients = []

    if args.interface:
        clients = get_client_from_interface(args.interface)
    elif args.all:
        for interface in Section.interfaces("openvpn"):
            clients += get_client_from_interface(interface)

    print(" ".join(clients))
