#!/usr/bin/env python3
#
# Copyright (C) 2018-2024 VyOS maintainers and contributors
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

from vyos.configquery import ConfigTreeQuery
from vyos.ifconfig.vrrp import VRRP
from vyos.ifconfig.vrrp import VRRPNoData

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group()
group.add_argument("-s", "--summary", action="store_true", help="Print VRRP summary")
group.add_argument("-t", "--statistics", action="store_true", help="Print VRRP statistics")
group.add_argument("-d", "--data", action="store_true", help="Print detailed VRRP data")

args = parser.parse_args()

def is_configured():
    """ Check if VRRP is configured """
    config = ConfigTreeQuery()
    if not config.exists(['high-availability', 'vrrp', 'group']):
        return False
    return True

# Exit early if VRRP is dead or not configured
if is_configured() == False:
    print('VRRP not configured!')
    exit(0)
if not VRRP.is_running():
    print('VRRP is not running')
    sys.exit(0)

try:
    if args.summary:
        print(VRRP.format(VRRP.collect('json')))
    elif args.statistics:
        print(VRRP.collect('stats'))
    elif args.data:
        print(VRRP.collect('state'))
    else:
        parser.print_help()
        sys.exit(1)
except VRRPNoData as e:
    print(e)
    sys.exit(1)
