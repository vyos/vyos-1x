#! /usr/bin/env python3

# Copyright (C) 2023 VyOS maintainers and contributors
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
    'report': {
        'mtr': '{command} --report',
        'type': 'noarg',
        'help': 'This option puts mtr into report mode. When in this mode, mtr will run for the number of cycles specified by the -c option, and then print statistics and exit.'
    },
    'report-wide': {
        'mtr': '{command} --report-wide',
        'type': 'noarg',
        'help': 'This option puts mtr into wide report mode. When in this mode, mtr will not cut hostnames in the report.'
    },
    'raw': {
        'mtr': '{command} --raw',
        'type': 'noarg',
        'help': 'Use the raw output format. This format is better suited for archival of the measurement results.'
    },
    'json': {
        'mtr': '{command} --json',
        'type': 'noarg',
        'help': 'Use this option to tell mtr to use the JSON output format.'
    },
    'split': {
        'mtr': '{command} --split',
        'type': 'noarg',
        'help': 'Use this option to set mtr to spit out a format that is suitable for a split-user interface.'
    },
    'no-dns': {
        'mtr': '{command} --no-dns',
        'type': 'noarg',
        'help': 'Use this option to force mtr to display numeric IP numbers and not try to resolve the host names.'
    },
    'show-ips': {
        'mtr': '{command} --show-ips {value}',
        'type': '<num>',
        'help': 'Use this option to tell mtr to display both the host names and numeric IP numbers.'
    },
    'ipinfo': {
        'mtr': '{command} --ipinfo {value}',
        'type': '<num>',
        'help': 'Displays information about each IP hop.'
    },
    'aslookup': {
        'mtr': '{command} --aslookup',
        'type': 'noarg',
        'help': 'Displays the Autonomous System (AS) number alongside each hop. Equivalent to --ipinfo 0.'
    },
    'interval': {
        'mtr': '{command} --interval {value}',
        'type': '<num>',
        'help': 'Use this option to specify the positive number of seconds between ICMP ECHO requests. The default value for this parameter is one second. The root user may choose values between zero and one.'
    },
    'report-cycles': {
        'mtr': '{command} --report-cycles {value}',
        'type': '<num>',
        'help': 'Use this option to set the number of pings sent to determine both the machines on the network and the reliability of those machines.  Each cycle lasts one second.'
    },
    'psize': {
        'mtr': '{command} --psize {value}',
        'type': '<num>',
        'help': 'This option sets the packet size used for probing. It is in bytes, inclusive IP and ICMP headers. If set to a negative number, every iteration will use a different, random packet size up to that number.'
    },
    'bitpattern': {
        'mtr': '{command} --bitpattern {value}',
        'type': '<num>',
        'help': 'Specifies bit pattern to use in payload. Should be within range 0 - 255. If NUM is greater than 255, a random pattern is used.'
    },
    'gracetime': {
        'mtr': '{command} --gracetime {value}',
        'type': '<num>',
        'help': 'Use this option to specify the positive number of seconds to wait for responses after the final request. The default value is five seconds.'
    },
    'tos': {
        'mtr': '{command} --tos {value}',
        'type': '<tos>',
        'help': 'Specifies value for type of service field in IP header. Should be within range 0 - 255.'
    },
    'mpls': {
        'mtr': '{command} --mpls {value}',
        'type': 'noarg',
        'help': 'Use this option to tell mtr to display information from ICMP extensions for MPLS (RFC 4950) that are encoded in the response packets.'
    },
    'interface': {
        'mtr': '{command} --interface {value}',
        'type': '<interface>',
        'helpfunction': interface_list,
        'help': 'Use the network interface with a specific name for sending network probes. This can be useful when you have multiple network interfaces with routes to your destination, for example both wired Ethernet and WiFi, and wish to test a particular interface.'
    },
    'address': {
        'mtr': '{command} --address {value}',
        'type': '<x.x.x.x> <h:h:h:h:h:h:h:h>',
        'help': 'Use this option to bind the outgoing socket to ADDRESS, so that all packets will be sent with ADDRESS as source address.'
    },
    'first-ttl': {
        'mtr': '{command} --first-ttl {value}',
        'type': '<num>',
        'help': 'Specifies with what TTL to start. Defaults to 1.'
    },
    'max-ttl': {
        'mtr': '{command} --max-ttl {value}',
        'type': '<num>',
        'help': 'Specifies the maximum number of hops or max time-to-live value mtr will probe. Default is 30.'
    },
    'max-unknown': {
        'mtr': '{command} --max-unknown {value}',
        'type': '<num>',
        'help': 'Specifies the maximum unknown host. Default is 5.'
    },
    'udp': {
        'mtr': '{command} --udp',
        'type': 'noarg',
        'help': 'Use UDP datagrams instead of ICMP ECHO.'
    },
    'tcp': {
        'mtr': '{command} --tcp',
        'type': 'noarg',
        'help': ' Use TCP SYN packets instead of ICMP ECHO. PACKETSIZE is ignored, since SYN packets can not contain data.'
    },
    'sctp': {
        'mtr': '{command} --sctp',
        'type': 'noarg',
        'help': 'Use Stream Control Transmission Protocol packets instead of ICMP ECHO.'
    },
    'port': {
        'mtr': '{command} --port {value}',
        'type': '<port>',
        'help': 'The target port number for TCP/SCTP/UDP traces.'
    },
    'localport': {
        'mtr': '{command} --localport {value}',
        'type': '<port>',
        'help': 'The source port number for UDP traces.'
    },
    'timeout': {
        'mtr': '{command} --timeout {value}',
        'type': '<num>',
        'help': ' The number of seconds to keep probe sockets open before giving up on the connection.'
    },
    'mark': {
        'mtr': '{command} --mark {value}',
        'type': '<num>',
        'help': ' Set the mark for each packet sent through this socket similar to the netfilter MARK target but socket-based. MARK is 32 unsigned integer.'
    },
    'vrf': {
        'mtr': 'sudo ip vrf exec {value} {command}',
        'type': '<vrf>',
        'help': 'Use specified VRF table',
        'helpfunction': vrf_list,
        'dflt': 'default'
        }
    }

mtr = {
    4: '/bin/mtr -4',
    6: '/bin/mtr -6',
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
            command = options[longname]['mtr'].format(
                command=command, value='')
        elif not args:
            sys.exit(f'mtr: missing argument for {longname} option')
        else:
            command = options[longname]['mtr'].format(
                command=command, value=args.first())
    return command


if __name__ == '__main__':
    args = List(sys.argv[1:])
    host = args.first()

    if not host:
        sys.exit("mtr: Missing host")


    if host == '--get-options' or host == '--get-options-nested':
        if host == '--get-options-nested':
            args.first()  # pop monitor
        args.first()  # pop mtr | traceroute
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
        sys.exit(f'mtr: Unknown host: {host}')
    except socket.gaierror:
        ip = host

    try:
        version = ipaddress.ip_address(ip).version
    except ValueError:
        sys.exit(f'mtr: Unknown host: {host}')

    command = convert(mtr[version], args)
    call(f'{command} --curses --displaymode 0 {host}')
