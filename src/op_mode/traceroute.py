#! /usr/bin/env python3

# Copyright (C) 2022 VyOS maintainers and contributors
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
import socket
import ipaddress

from vyos.utils.network import interface_list
from vyos.utils.network import vrf_list
from vyos.utils.process import call

options = {
    'backward-hops': {
        'traceroute': '{command} --back',
        'type': 'noarg',
        'help': 'Display number of backward hops when they different from the forwarded path'
    },
    'bypass': {
        'traceroute': '{command} -r',
        'type': 'noarg',
        'help': 'Bypass the normal routing tables and send directly to a host on an attached network'
    },
    'do-not-fragment': {
        'traceroute': '{command} -F',
        'type': 'noarg',
        'help': 'Do not fragment probe packets.'
    },
    'first-ttl': {
        'traceroute': '{command} -f {value}',
        'type': '<ttl>',
        'help': 'Specifies with what TTL to start. Defaults to 1.'
    },
    'icmp': {
        'traceroute': '{command} -I',
        'type': 'noarg',
        'help': 'Use ICMP ECHO for tracerouting'
    },
    'interface': {
        'traceroute': '{command} -i {value}',
        'type': '<interface>',
        'helpfunction': interface_list,
        'help': 'Source interface'
    },
    'lookup-as': {
        'traceroute': '{command} -A',
        'type': 'noarg',
        'help': 'Perform AS path lookups'
    },
    'mark': {
        'traceroute': '{command} --fwmark={value}',
        'type': '<fwmark>',
        'help': 'Set the firewall mark for outgoing packets'
    },
    'no-resolve': {
        'traceroute': '{command} -n',
        'type': 'noarg',
        'help': 'Do not resolve hostnames'
    },
    'port': {
        'traceroute': '{command} -p {value}',
        'type': '<port>',
        'help': 'Destination port'
    },
    'source-address': {
        'traceroute': '{command} -s {value}',
        'type': '<x.x.x.x> <h:h:h:h:h:h:h:h>',
        'help': 'Specify source IP v4/v6 address'
    },
    'tcp': {
        'traceroute': '{command} -T',
        'type': 'noarg',
        'help': 'Use TCP SYN for tracerouting (default port is 80)'
    },
    'tos': {
        'traceroute': '{commad} -t {value}',
        'type': '<tos>',
        'help': 'Mark packets with specified TOS'
    },
    'ttl': {
        'traceroute': '{command} -m {value}',
        'type': '<ttl>',
        'help': 'Maximum number of hops'
    },
    'udp': {
        'traceroute': '{command} -U',
        'type': 'noarg',
        'help': 'Use UDP to particular port for tracerouting (default port is 53)'
    },
    'vrf': {
        'traceroute': 'sudo ip vrf exec {value} {command}',
        'type': '<vrf>',
        'help': 'Use specified VRF table',
        'helpfunction': vrf_list,
        'dflt': 'default'}
}

traceroute = {
    4: '/bin/traceroute -4',
    6: '/bin/traceroute -6',
}


class List(list):
    def first(self):
        return self.pop(0) if self else ''

    def last(self):
        return self.pop() if self else ''

    def prepend(self, value):
        self.insert(0, value)


def completion_failure(option: str) -> None:
    """
    Shows failure message after TAB when option is wrong
    :param option: failure option
    :type str:
    """
    sys.stderr.write('\n\n Invalid option: {}\n\n'.format(option))
    sys.stdout.write('<nocomps>')
    sys.exit(1)


def expension_failure(option, completions):
    reason = 'Ambiguous' if completions else 'Invalid'
    sys.stderr.write(
        '\n\n  {} command: {} [{}]\n\n'.format(reason, ' '.join(sys.argv),
                                               option))
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
            command = options[longname]['traceroute'].format(
                command=command, value='')
        elif not args:
            sys.exit(f'traceroute: missing argument for {longname} option')
        else:
            command = options[longname]['traceroute'].format(
                command=command, value=args.first())
    return command


if __name__ == '__main__':
    args = List(sys.argv[1:])
    host = args.first()

    if not host:
        sys.exit("traceroute: Missing host")

    if host == '--get-options':
        args.first()  # pop ping
        args.first()  # pop IP
        usedoptionslist = []
        while args:
            option = args.first()  # pop option
            matched = complete(option)  # get option parameters
            usedoptionslist.append(option)  # list of used options
            # Select options
            if not args:
                # remove from Possible completions used options
                for o in usedoptionslist:
                    if o in matched:
                        matched.remove(o)
                sys.stdout.write(' '.join(matched))
                sys.exit(0)

            if len(matched) > 1:
                sys.stdout.write(' '.join(matched))
                sys.exit(0)
            # If option doesn't have value
            if matched:
                if options[matched[0]]['type'] == 'noarg':
                    continue
            else:
                # Unexpected option
                completion_failure(option)

            value = args.first()  # pop option's value
            if not args:
                matched = complete(option)
                helplines = options[matched[0]]['type']
                # Run helpfunction to get list of possible values
                if 'helpfunction' in options[matched[0]]:
                    result = options[matched[0]]['helpfunction']()
                    if result:
                        helplines = '\n' + ' '.join(result)
                sys.stdout.write(helplines)
                sys.exit(0)

    for name, option in options.items():
        if 'dflt' in option and name not in args:
            args.append(name)
            args.append(option['dflt'])

    try:
        ip = socket.gethostbyname(host)
    except UnicodeError:
        sys.exit(f'tracroute: Unknown host: {host}')
    except socket.gaierror:
        ip = host

    try:
        version = ipaddress.ip_address(ip).version
    except ValueError:
        sys.exit(f'traceroute: Unknown host: {host}')

    command = convert(traceroute[version], args)
    call(f'{command} {host}')
