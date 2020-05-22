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

'''
show nat translations
'''

import os
import sys
import ipaddress
import argparse
import xmltodict

from vyos.util import popen
from vyos.util import DEVNULL

conntrack = '/usr/sbin/conntrack'

verbose_format = "%-20s %-18s %-20s %-18s"
normal_format = "%-20s %-20s %-4s  %-8s %s"


def headers(verbose, pipe):
    if verbose:
        return verbose_format % ('Pre-NAT src', 'Pre-NAT dst', 'Post-NAT src', 'Post-NAT dst')
    return normal_format % ('Pre-NAT', 'Post-NAT', 'Prot', 'Timeout', 'Type' if pipe else '')


def command(srcdest, proto, ipaddr):
    command = f'{conntrack} -o xml -L'

    if proto:
        command += f' -p {proto}'

    if srcdest == 'source':
        command += ' -n'
        if ipaddr:
            command += f' --orig-src {ipaddr}'
    if srcdest == 'destination':
        command += ' -g'

    return command


def run(command):
    xml, code = popen(command,stderr=DEVNULL)
    if code:
        sys.exit('conntrack failed')
    return xml


def content(xmlfile):
    xml = ''
    with open(xmlfile,'r') as r:
        xml += r.read()
    return xml


def pipe():
    xml = ''
    while True:
        line = sys.stdin.readline()
        xml += line
        if '</conntrack>' in line:
            break

    sys.stdin = open('/dev/tty')
    return xml


def process(data, stats, protocol, pipe, verbose, flowtype=''):
    if not data:
        return

    parsed = xmltodict.parse(data)

    print(headers(verbose, pipe))

    # to help the linter to detect typos
    ORIGINAL = 'original'
    REPLY = 'reply'
    INDEPENDANT = 'independent'
    SPORT = 'sport'
    DPORT = 'dport'
    SRC = 'src'
    DST = 'dst'

    for rule in parsed['conntrack']['flow']:
        src, dst, sport, dport, proto = {}, {}, {}, {}, {}
        packet_count, byte_count = {}, {}
        timeout, use = 0, 0

        rule_type = rule.get('type', '')

        for meta in rule['meta']:
            # print(meta)
            direction = meta['@direction']

            if direction in (ORIGINAL, REPLY):
                if 'layer3' in meta:
                    l3 = meta['layer3']
                    src[direction] = l3[SRC]
                    dst[direction] = l3[DST]

                if 'layer4' in meta:
                    l4 = meta['layer4']
                    sport[direction] = l4[SPORT]
                    dport[direction] = l4[DPORT]
                    proto[direction] = l4.get('@protoname','')

                if stats and 'counters' in meta:
                    packet_count[direction] = meta['packets']
                    byte_count[direction] = meta['bytes']
                continue

            if direction == INDEPENDANT:
                timeout = meta['timeout']
                use = meta['use']
                continue

        in_src = '%s:%s' % (src[ORIGINAL], sport[ORIGINAL]) if ORIGINAL in sport else src[ORIGINAL]
        in_dst = '%s:%s' % (dst[ORIGINAL], dport[ORIGINAL]) if ORIGINAL in dport else dst[ORIGINAL]

        # inverted the the perl code !!?
        out_dst = '%s:%s' % (dst[REPLY], dport[REPLY]) if REPLY in dport else dst[REPLY]
        out_src = '%s:%s' % (src[REPLY], sport[REPLY]) if REPLY in sport else src[REPLY]

        if flowtype == 'source':
            v = ORIGINAL in sport and REPLY in dport
            f = '%s:%s' % (src[ORIGINAL], sport[ORIGINAL]) if v else src[ORIGINAL]
            t = '%s:%s' % (dst[REPLY], dport[REPLY]) if v else dst[REPLY]
        else:
            v = ORIGINAL in dport and REPLY in sport
            f = '%s:%s' % (dst[ORIGINAL], dport[ORIGINAL]) if v else dst[ORIGINAL]
            t = '%s:%s' % (src[REPLY], sport[REPLY]) if v else src[REPLY]

        # Thomas: I do not believe proto should be an option
        p = proto.get('original', '')
        if protocol and p != protocol:
            continue

        if verbose:
            msg = verbose_format % (in_src, in_dst, out_dst, out_src)
            p = f'{p}: ' if p else ''
            msg += f'\n  {p}{f} ==> {t}'
            msg += f' timeout: {timeout}' if timeout else ''
            msg += f' use: {use} ' if use else ''
            msg += f' type: {rule_type}' if rule_type else ''
            print(msg)
        else:
            print(normal_format % (f, t, p, timeout, rule_type if rule_type else ''))

        if stats:
            for direction in ('original', 'reply'):
                if direction in packet_count:
                    print('  %-8s: packets %s, bytes %s' % direction, packet_count[direction], byte_count[direction])


def main():
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    parser.add_argument('--verbose', help='provide more details about the flows', action='store_true')
    parser.add_argument('--proto', help='filter by protocol', default='', type=str)
    parser.add_argument('--file', help='read the conntrack xml from a file', type=str)
    parser.add_argument('--stats', help='add usage statistics', action='store_true')
    parser.add_argument('--type', help='NAT type (source, destination)', required=True, type=str)
    parser.add_argument('--ipaddr', help='source ip address to filter on', type=ipaddress.ip_address)
    parser.add_argument('--pipe', help='read conntrack xml data from stdin', action='store_true')

    arg = parser.parse_args()

    if arg.type not in ('source', 'destination'):
        sys.exit('Unknown NAT type!')

    if arg.pipe:
        process(pipe(), arg.stats, arg.proto, arg.pipe, arg.verbose, arg.type)
    elif arg.file:
        process(content(arg.file), arg.stats, arg.proto, arg.pipe, arg.verbose, arg.type)
    else:
        process(run(command(arg.type, arg.proto, arg.ipaddr)), arg.stats, arg.proto, arg.pipe, arg.verbose, arg.type)


if __name__ == '__main__':
    main()
