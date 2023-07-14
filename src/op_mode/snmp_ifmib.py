#!/usr/bin/env python3
#
# Copyright (C) 2018-2023 VyOS maintainers and contributors
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
#
# File: snmp_ifmib.py
# Purpose:
#    Show SNMP MIB information
#    Used by the "run show snmp mib" commands.

import sys
import argparse
import netifaces

from vyos.config import Config
from vyos.utils.process import popen

parser = argparse.ArgumentParser(description='Retrieve SNMP interfaces information')
parser.add_argument('--ifindex', action='store', nargs='?', const='all', help='Show interface index')
parser.add_argument('--ifalias', action='store', nargs='?', const='all', help='Show interface aliase')
parser.add_argument('--ifdescr', action='store', nargs='?', const='all', help='Show interface description')

def show_ifindex(intf):
    out, err = popen(f'/bin/ip link show {intf}', decode='utf-8')
    index = 'ifIndex = ' + out.split(':')[0]
    return index.replace('\n', '')

def show_ifalias(intf):
    out, err = popen(f'/bin/ip link show {intf}', decode='utf-8')
    alias = out.split('alias')[1].lstrip() if 'alias' in out else intf
    return 'ifAlias = ' + alias.replace('\n', '')

def show_ifdescr(i):
    ven_id = ''
    dev_id = ''

    try:
        with open(r'/sys/class/net/' + i + '/device/vendor', 'r') as f:
            ven_id = f.read().replace('\n', '')
    except FileNotFoundError:
        pass

    try:
        with open(r'/sys/class/net/' + i + '/device/device', 'r') as f:
            dev_id = f.read().replace('\n', '')
    except FileNotFoundError:
         pass

    if ven_id == '' and dev_id == '':
        ret = 'ifDescr = {0}'.format(i)
        return ret

    device = str(ven_id) + ':' + str(dev_id)
    out, err = popen(f'/usr/bin/lspci -mm -d {device}', decode='utf-8')

    vendor = ""
    device = ""

    # convert output to string
    string = out.split('"')
    if len(string) > 3:
      vendor = string[3]

    if len(string) > 5:
      device = string[5]

    ret = 'ifDescr = {0} {1}'.format(vendor, device)
    return ret.replace('\n', '')

if __name__ == '__main__':
    args = parser.parse_args()

    # Do nothing if service is not configured
    c = Config()
    if not c.exists_effective('service snmp'):
        print("SNMP service is not configured")
        sys.exit(0)

    if args.ifindex:
        if args.ifindex == 'all':
            for i in netifaces.interfaces():
                print('{0}: {1}'.format(i, show_ifindex(i)))
        else:
            print('{0}: {1}'.format(args.ifindex, show_ifindex(args.ifindex)))

    elif args.ifalias:
        if args.ifalias == 'all':
            for i in netifaces.interfaces():
                print('{0}: {1}'.format(i, show_ifalias(i)))
        else:
            print('{0}: {1}'.format(args.ifalias, show_ifalias(args.ifalias)))

    elif args.ifdescr:
        if args.ifdescr == 'all':
            for i in netifaces.interfaces():
                print('{0}: {1}'.format(i, show_ifdescr(i)))
        else:
                print('{0}: {1}'.format(args.ifdescr, show_ifdescr(args.ifdescr)))

    else:
        #eth0: ifIndex = 2
        #      ifAlias = NET-MYBLL-MUCI-BACKBONE
        #      ifDescr = VMware VMXNET3 Ethernet Controller
        #lo: ifIndex = 1
        for i in netifaces.interfaces():
            print('{0}:\t{1}'.format(i, show_ifindex(i)))
            print('\t{0}'.format(show_ifalias(i)))
            print('\t{0}'.format(show_ifdescr(i)))

    sys.exit(1)
