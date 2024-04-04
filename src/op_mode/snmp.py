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

from vyos.config import Config
from vyos.utils.process import call

config_file_daemon = r'/etc/snmp/snmpd.conf'

parser = argparse.ArgumentParser(description='Retrieve infomration from running SNMP daemon')
parser.add_argument('--allowed', action="store_true", help='Show available SNMP communities')
parser.add_argument('--community', action="store", help='Show status of given SNMP community', type=str)
parser.add_argument('--host', action="store", help='SNMP host to connect to', type=str, default='localhost')

config = {
    'communities': [],
}

def read_config():
    with open(config_file_daemon, 'r') as f:
        for line in f:
             # Only get configured SNMP communitie
             if line.startswith('rocommunity') or line.startswith('rwcommunity'):
                 string = line.split(' ')
                 # append community to the output list only once
                 c = string[1]
                 if c not in config['communities']:
                     config['communities'].append(c)

def show_all():
    if len(config['communities']) > 0:
        print(' '.join(config['communities']))

def show_community(c, h):
    print('Status of SNMP community {0} on {1}'.format(c, h), flush=True)
    call('/usr/bin/snmpstatus -t1 -v1 -c {0} {1}'.format(c, h))

if __name__ == '__main__':
    args = parser.parse_args()

    # Do nothing if service is not configured
    c = Config()
    if not c.exists_effective('service snmp'):
        print("SNMP service is not configured")
        sys.exit(0)

    read_config()

    if args.allowed:
        show_all()
        sys.exit(1)
    elif args.community:
        show_community(args.community, args.host)
        sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)
