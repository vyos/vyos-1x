#! /usr/bin/env python3

# Copyright (C) 2020 VyOS maintainers and contributors
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

import os
import sys
import socket
import ipaddress

options = {
    'audible': {
        'ping': '{command} -a',
        'type': 'noarg',
        'help': 'Make a noise on ping'
    },
    'adaptive': {
        'ping': '{command} -A',
        'type': 'noarg',
        'help': 'Adativly set interpacket interval'
    },
    'allow-broadcast': {
        'ping': '{command} -b',
        'type': 'noarg',
        'help': 'Ping broadcast address'
    },
    'bypass-route': {
        'ping': '{command} -r',
        'type': 'noarg',
        'help': 'Bypass normal routing tables'
    },
    'count': {
        'ping': '{command} -c {value}',
        'type': '<requests>',
        'help': 'Number of requests to send'
    },
    'deadline': {
        'ping': '{command} -w {value}',
        'type': '<seconds>',
        'help': 'Number of seconds before ping exits'
    },
    'flood': {
        'ping': 'sudo {command} -f',
        'type': 'noarg',
        'help': 'Send 100 requests per second'
    },
    'interface': {
        'ping': '{command} -I {value}',
        'type': '<interface> <X.X.X.X> <h:h:h:h:h:h:h:h>',
        'help': 'Interface to use as source for ping'
    },
    'interval': {
        'ping': '{command} -i {value}',
        'type': '<seconds>',
        'help': 'Number of seconds to wait between requests'
    },
    'mark': {
        'ping': '{command} -m {value}',
        'type': '<fwmark>',
        'help': 'Mark request for special processing'
    },
    'numeric': {
        'ping': '{command} -n',
        'type': 'noarg',
        'help': 'Do not resolve DNS names'
    },
    'no-loopback': {
        'ping': '{command} -L',
        'type': 'noarg',
        'help': 'Supress loopback of multicast pings'
    },
    'pattern': {
        'ping': '{command} -p {value}',
        'type': '<pattern>',
        'help': 'Pattern to fill out the packet'
    },
    'timestamp': {
        'ping': '{command} -D',
        'type': 'noarg',
        'help': 'Print timestamp of output'
    },
    'tos': {
        'ping': '{command} -Q {value}',
        'type': '<tos>',
        'help': 'Mark packets with specified TOS'
    },
    'quiet': {
        'ping': '{command} -q',
        'type': 'noarg',
        'help': 'Only print summary lines'
    },
    'record-route': {
        'ping': '{command} -R',
        'type': 'noarg',
        'help': 'Record route the packet takes'
    },
    'size': {
        'ping': '{command} -s {value}',
        'type': '<bytes>',
        'help': 'Number of bytes to send'
    },
    'ttl': {
        'ping': '{command} -t {value}',
        'type': '<ttl>',
        'help': 'Maximum packet lifetime'
    },
    'vrf': {
        'ping': 'sudo ip vrf exec {value} {command}',
        'type': '<vrf>',
        'help': 'Use specified VRF table'
    },
    'verbose': {
        'ping': '{command} -v',
        'type': 'noarg',
        'help': 'Verbose output'}
}

ping = {
    4: '/bin/ping',
    6: '/bin/ping6',
}


class List (list):
    def first (self):
        return self.pop(0) if self else ''

    def last(self):
        return self.pop() if self else ''

    def prepend(self,value):
        self.insert(0,value)


def expension_failure(option, completions):
    reason = 'Ambiguous' if completions else 'Invalid'
    sys.stderr.write('\n\n  {} command: {} [{}]\n\n'.format(reason,' '.join(sys.argv), option))
    if completions:
        sys.stderr.write('  Possible completions:\n   ')
        sys.stderr.write('\n   '.join(completions))
        sys.stderr.write('\n')
    sys.stdout.write('<nocomps>')
    sys.exit(1)


def complete(prefix):
    return [o for o in options if o.startswith(prefix)]


def convert(command, args):
    while args:
        shortname = args.first()
        longnames = complete(shortname)
        if len(longnames) != 1:
            expension_failure(shortname, longnames)
        longname = longnames[0]
        if options[longname]['type'] == 'noarg':
            command = options[longname]['ping'].format(
                command=command, value='')
        elif not args:
            sys.exit(f'ping: missing argument for {longname} option')
        else:
            command = options[longname]['ping'].format(
                command=command, value=args.first())
    return command


if __name__ == '__main__':
    args = List(sys.argv[1:])
    host = args.first()

    if not host:
        sys.exit("ping: Missing host")

    if host == '--get-options':
        args.first()  # pop ping
        args.first()  # pop IP
        while args:
            option = args.first()

            matched = complete(option)
            if not args:
                sys.stdout.write(' '.join(matched))
                sys.exit(0)

            if len(matched) > 1 :
                sys.stdout.write(' '.join(matched))
                sys.exit(0)

            if options[matched[0]]['type'] == 'noarg':
                continue

            value = args.first()
            if not args:
                matched = complete(option)
                sys.stdout.write(options[matched[0]]['type'])
                sys.exit(0)

    try:
        ip = socket.gethostbyname(host)
    except socket.gaierror:
        sys.exit(f'ping: Unknown host: {host}')

    try:
        version = ipaddress.ip_address(ip).version
    except ValueError:
        sys.exit(f'ping: Unknown host: {host}')

    command = convert(ping[version],args)

    # print(f'{command} {host}')
    os.system(f'{command} {host}')

