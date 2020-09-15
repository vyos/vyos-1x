#!/usr/bin/env python3
#
# Copyright (C) 2019-2020 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import argparse
from vyos.ifconfig import Section

def matching(feature):
    for section in Section.feature(feature):
        for intf in Section.interfaces(section):
            yield intf

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group()
group.add_argument("-t", "--type", type=str, help="List interfaces of specific type")
group.add_argument("-b", "--broadcast", action="store_true", help="List all broadcast interfaces")
group.add_argument("-br", "--bridgeable", action="store_true", help="List all bridgeable interfaces")
group.add_argument("-bo", "--bondable", action="store_true", help="List all bondable interfaces")

args = parser.parse_args()

if args.type:
    try:
        interfaces = Section.interfaces(args.type)
        print(" ".join(interfaces))
    except ValueError as e:
        print(e, file=sys.stderr)
        print("")

elif args.broadcast:
    print(" ".join(matching("broadcast")))

elif args.bridgeable:
    print(" ".join(matching("bridgeable")))

elif args.bondable:
    # we need to filter out VLAN interfaces identified by a dot (.) in their name
    print(" ".join([intf for intf in matching("bondable") if '.' not in intf]))

else:
    print(" ".join(Section.interfaces()))
