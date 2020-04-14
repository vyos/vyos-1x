#!/usr/bin/env python3

# Copyright 2017, 2019 VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

import os
import re
import sys
import datetime
import argparse
from subprocess import Popen, PIPE, STDOUT
import netifaces

from vyos.ifconfig import Section
from vyos.ifconfig import Interface
from vyos.ifconfig import VRRP
from vyos.util import cmd


# interfaces = Sections.reserved()
interfaces = ['eno', 'ens', 'enp', 'enx', 'eth', 'vmnet', 'lo', 'tun', 'wan', 'pppoe', 'pppoa', 'adsl']
glob_ifnames = '/sys/class/net/({})*'.format('|'.join(interfaces))


actions = {}
def register (name):
    """
    decorator to register a function into actions with a name
    it allows to use actions[name] to call the registered function
    """
    def _register(function):
        actions[name] = function
        return function
    return _register


def filtered_interfaces(ifnames, iftypes, vif, vrrp):
    """
    get all the interfaces from the OS and returns them
    ifnames can be used to filter which interfaces should be considered

    ifnames: a list of interfaces names to consider, empty do not filter
    return an instance of the interface class
    """
    allnames = Section.interfaces()
    allnames.sort()

    vrrp_interfaces = VRRP.active_interfaces() if vrrp else []

    for ifname in allnames:
        if ifnames and ifname not in ifnames:
            continue

        # return the class which can handle this interface name
        klass = Section.klass(ifname)
        # connect to the interface
        interface = klass(ifname, create=False, debug=False)

        if iftypes and interface.definition['section'] not in iftypes:
            continue

        if vif and not '.' in ifname:
            continue

        if vrrp and ifname not in vrrp_interfaces:
            continue

        yield interface


def split_text(text, used=0):
    """
    take a string and attempt to split it to fit with the width of the screen

    text: the string to split
    used: number of characted already used in the screen
    """
    returned = Popen('stty size', stdout=PIPE, stderr=STDOUT, shell=True).communicate()[0].strip().split()
    if len(returned) == 2:
        rows, columns = [int(_) for _ in returned]
    else:
        rows, columns = (40, 80)

    desc_len = columns - used

    line = ''
    for word in text.split():
        if len(line) + len(word) >= desc_len:
            yield f'{line} {word}'[1:]
            line = ''
        line = f'{line} {word}'
    yield line[1:]


def get_vrrp_intf():
    return [intf for intf in Section.interfaces() if intf.is_vrrp()]


def get_counter_val(clear, now):
    """
    attempt to correct a counter if it wrapped, copied from perl

    clear: previous counter
    now:   the current counter
    """
    # This function has to deal with both 32 and 64 bit counters
    if clear == 0:
        return now

    # device is using 64 bit values assume they never wrap
    value = now - clear
    if (now >> 32) != 0:
        return value

    # The counter has rolled.  If the counter has rolled
    # multiple times since the clear value, then this math
    # is meaningless.
    if (value < 0):
        value = (4294967296 - clear) + now

    return value


@register('help')
def usage(*args):
    print(f"Usage: {sys.argv[0]} [intf=NAME|intf-type=TYPE|vif|vrrp] action=ACTION")
    print(f"  NAME = " + ' | '.join(Section.interfaces()))
    print(f"  TYPE = " + ' | '.join(Section.sections()))
    print(f"  ACTION = " + ' | '.join(actions))
    sys.exit(1)


@register('allowed')
def run_allowed(**kwarg):
    sys.stdout.write(' '.join(Section.interfaces()))


@register('show')
def run_show_intf(ifnames, iftypes, vif, vrrp):
    for interface in filtered_interfaces(ifnames, iftypes, vif, vrrp):
        cache = interface.operational.load_counters()

        out = cmd(f'ip addr show {interface.ifname}')
        out = re.sub(f'^\d+:\s+','',out)
        if re.search("link/tunnel6", out):
            tunnel = cmd(f'ip -6 tun show {interface.ifname}')
            # tun0: ip/ipv6 remote ::2 local ::1 encaplimit 4 hoplimit 64 tclass inherit flowlabel inherit (flowinfo 0x00000000)
            tunnel = re.sub('.*encap', 'encap', tunnel)
            out = re.sub('(\n\s+)(link/tunnel6)', f'\g<1>{tunnel}\g<1>\g<2>', out)

        print(out)

        timestamp = int(cache.get('timestamp', 0))
        if timestamp:
            when = interface.operational.strtime(timestamp)
            print(f'    Last clear: {when}')

        description = interface.get_alias()
        if description:
            print(f'    Description: {description}')

        print()
        print(interface.operational.formated_stats())


@register('show-brief')
def run_show_intf_brief(ifnames, iftypes, vif, vrrp):
    format1 = '%-16s %-33s %-4s %s'
    format2 = '%-16s %s'

    print('Codes: S - State, L - Link, u - Up, D - Down, A - Admin Down')
    print(format1 % ("Interface", "IP Address", "S/L", "Description"))
    print(format1 % ("---------", "----------", "---", "-----------"))

    for interface in filtered_interfaces(ifnames, iftypes, vif, vrrp):
        oper_state = interface.operational.get_state()
        admin_state = interface.get_admin_state()

        intf = [interface.ifname,]
        oper = ['u', ] if oper_state in ('up', 'unknown') else ['A', ]
        admin = ['u', ] if oper_state in ('up', 'unknown') else ['D', ]
        addrs = [_ for _ in interface.get_addr() if not _.startswith('fe80::')] or ['-', ]
        # do not ask me why 56, it was the number in the perl code ...
        descs = list(split_text(interface.get_alias(),56))

        while intf or oper or admin or addrs or descs:
            i = intf.pop(0) if intf else ''
            a = addrs.pop(0) if addrs else ''
            d = descs.pop(0) if descs else ''
            s = [oper.pop(0)] if oper else []
            l = [admin.pop(0)] if admin else []
            if len(a) < 33:
                print(format1 % (i, a, '/'.join(s+l), d))
            else:
                print(format2 % (i, a))
                print(format1 % ('', '', '/'.join(s+l), d))


@register('show-count')
def run_show_counters(ifnames, iftypes, vif, vrrp):
    formating = '%-12s %10s %10s     %10s %10s'
    print(formating % ('Interface', 'Rx Packets', 'Rx Bytes', 'Tx Packets', 'Tx Bytes'))

    for interface in filtered_interfaces(ifnames, iftypes, vif, vrrp):
        oper = interface.operational.get_state()

        if oper not in ('up','unknown'):
            continue

        stats = interface.operational.get_stats()
        cache = interface.operational.load_counters()
        print(formating % (
            interface.ifname,
            get_counter_val(cache['rx_packets'], stats['rx_packets']),
            get_counter_val(cache['rx_bytes'],   stats['rx_bytes']),
            get_counter_val(cache['tx_packets'], stats['tx_packets']),
            get_counter_val(cache['tx_bytes'],   stats['tx_bytes']),
        ))


@register('clear')
def run_clear_intf(intf, iftypes, vif, vrrp):
    for interface in filtered_interfaces(ifnames, iftypes, vif, vrrp):
        print(f'Clearing {interface.ifname}')
        interface = Interface(ifname, create=False, debug=False)
        interface.operational.clear_counters()


@register('reset')
def run_reset_intf(intf, iftypes, vif, vrrp):
    os.remove()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False, description='Show interface information')
    parser.add_argument('--intf', action="store", type=str, default='', help='only show the specified interface(s)')
    parser.add_argument('--intf-type', action="store", type=str, default='', help='only show the specified interface type')
    parser.add_argument('--action', action="store", type=str, default='show', help='action to perform')
    parser.add_argument('--vif', action='store_true', default=False, help="only show vif interfaces")
    parser.add_argument('--vrrp', action='store_true', default=False, help="only show vrrp interfaces")
    parser.add_argument('--help', action='store_true', default=False, help="show help")

    args = parser.parse_args()

    def missing(*args):
        print('Invalid action [{args.action}]')
        usage()

    actions.get(args.action, missing)(
        [_ for _ in args.intf.split(' ') if _],
        [_ for _ in args.intf_type.split(' ') if _],
        args.vif,
        args.vrrp
    )
