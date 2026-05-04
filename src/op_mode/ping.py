#! /usr/bin/env python3

# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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
import re
import socket
import ipaddress
import subprocess

from vyos.utils.network import interface_list
from vyos.utils.network import vrf_list
from vyos.utils.process import call

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
    'do-not-fragment': {
        'ping': '{command} -M do',
        'type': 'noarg',
        'help': 'Set DF-bit flag to 1 for no fragmentation'
    },
    'flood': {
        'ping': 'sudo {command} -f',
        'type': 'noarg',
        'help': 'Send 100 requests per second'
    },
    'interface': {
        'ping': '{command} -I {value}',
        'type': '<interface>',
        'helpfunction': interface_list,
        'help': 'Source interface'
    },
    'interval': {
        'ping': '{command} -i {value}',
        'type': '<seconds>',
        'help': 'Number of seconds to wait between requests'
    },
    'ipv4': {
        'ping': '{command} -4',
        'type': 'noarg',
        'help': 'Use IPv4 only'
    },
    'ipv6': {
        'ping': '{command} -6',
        'type': 'noarg',
        'help': 'Use IPv6 only'
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
        'help': 'Suppress loopback of multicast pings'
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
    'source-address': {
        'ping': '{command} -I {value}',
        'type': '<x.x.x.x> <h:h:h:h:h:h:h:h>',
    },
    'ttl': {
        'ping': '{command} -t {value}',
        'type': '<ttl>',
        'help': 'Maximum packet lifetime'
    },
    'vrf': {
        'ping': 'sudo ip vrf exec {value} {command}',
        'type': '<vrf>',
        'help': 'Use specified VRF table',
        'helpfunction': vrf_list,
        'dflt': 'default',
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

tcp_options = {
    'count': {'type': '<requests>', 'help': 'Number of requests to send'},
    'interface': {
        'type': '<interface>',
        'helpfunction': interface_list,
        'help': 'Source interface',
    },
    'port': {'type': '<port>', 'help': 'Destination port'},
    'source-address': {'type': '<x.x.x.x> <h:h:h:h:h:h:h:h>', 'help': 'Source address'},
    'vrf': {
        'type': '<vrf>',
        'help': 'Use specified VRF table',
        'helpfunction': vrf_list,
        'dflt': 'default',
    },
}

ping_options = options | {
    'tcp': {'type': 'noarg', 'help': 'Use TCP connect probe'},
}

tcp_completion_options = {'tcp': ping_options['tcp']} | tcp_options

NPING = '/usr/bin/nping'
TCP_DELAY = '1s'
SUCCESSFUL_CONNECTIONS_RE = re.compile(r'Successful connections:\s+(\d+)')


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


def expansion_failure(option, completions):
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


def complete(prefix, available_options=options):
    return [o for o in available_options if o.startswith(prefix)]


class UsageError(Exception):
    pass


def convert(command, args):
    while args:
        shortname = args.first()
        longnames = complete(shortname)
        if len(longnames) != 1:
            expansion_failure(shortname, longnames)
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


def option_value_help(option, available_options):
    helplines = available_options[option]['type']
    if 'helpfunction' in available_options[option]:
        result = available_options[option]['helpfunction']()
        if result:
            helplines = '\n' + ' '.join(result)

    return helplines


def get_option_completion(args, available_options):
    args.first()  # pop ping
    args.first()  # pop IP
    usedoptionslist = []
    while args:
        option = args.first()  # pop option
        matched = complete(option, available_options)  # get option parameters
        usedoptionslist.append(option)  # list of used options
        # Select options
        if not args:
            # remove from Possible completions used options
            for o in usedoptionslist:
                if o in matched:
                    matched.remove(o)
            return ' '.join(matched)

        if len(matched) > 1:
            return ' '.join(matched)
        # If option doesn't have value
        if matched:
            if available_options[matched[0]]['type'] == 'noarg':
                continue
        else:
            # Unexpected option
            completion_failure(option)

        args.first()  # pop option's value
        if not args:
            matched = complete(option, available_options)
            return option_value_help(matched[0], available_options)

    return ''


def get_icmp_completion(args):
    return get_option_completion(args, ping_options)


def get_tcp_completion(args):
    return get_option_completion(args, tcp_completion_options)


def has_tcp_option(args):
    args = List(args[:])
    args.first()  # pop ping
    args.first()  # pop IP

    while args:
        shortname = args.first()
        longnames = complete(shortname, ping_options)
        if len(longnames) != 1:
            continue

        longname = longnames[0]
        if longname == 'tcp':
            return True

        if ping_options[longname]['type'] != 'noarg':
            args.first()

    return False


def get_completion(args):
    if has_tcp_option(args):
        return get_tcp_completion(args)

    return get_icmp_completion(args)


def tcp_usage(message):
    sys.stderr.write(f'{message}\n')
    return 2


def parse_positive_int(value, option):
    try:
        number = int(value)
    except ValueError:
        raise UsageError(f'ping tcp: invalid {option}: {value}')

    if number < 1:
        raise UsageError(f'ping tcp: invalid {option}: {value}')

    return number


def parse_tcp_port(value):
    port = parse_positive_int(value, 'port')
    if port > 65535:
        raise UsageError(f'ping tcp: invalid port: {value}')

    return port


def parse_tcp_args(argv):
    args = List(argv)
    host = args.first()
    if not host:
        raise UsageError('ping tcp: Missing host')

    result = {
        'host': host,
        'port': None,
        'count': None,
        'interface': None,
        'source_address': None,
        'vrf': 'default',
    }

    while args:
        shortname = args.first()
        longnames = complete(shortname, tcp_completion_options)
        if len(longnames) > 1:
            raise UsageError(f'ping tcp: ambiguous option: {shortname}')
        if not longnames:
            raise UsageError(f'ping tcp: invalid option: {shortname}')

        longname = longnames[0]
        if longname == 'tcp':
            continue

        if not args:
            raise UsageError(f'ping tcp: missing argument for {longname} option')

        value = args.first()
        if longname == 'port':
            result['port'] = parse_tcp_port(value)
        elif longname == 'count':
            result['count'] = parse_positive_int(value, 'count')
        elif longname == 'source-address':
            try:
                ipaddress.ip_address(value)
            except ValueError:
                raise UsageError(f'ping tcp: invalid source-address: {value}')
            result['source_address'] = value
        elif longname == 'interface':
            result['interface'] = value
        elif longname == 'vrf':
            result['vrf'] = value

    if result['port'] is None:
        raise UsageError('ping tcp: missing port option')

    return result


def tcp_uses_ipv6(config):
    addresses = [config['host'], config['source_address']]
    for address in addresses:
        if not address:
            continue
        try:
            if ipaddress.ip_address(address).version == 6:
                return True
        except ValueError:
            continue

    return False


def build_tcp_nping_command(config):
    command = [
        NPING,
        '--tcp-connect',
        '--dest-port',
        str(config['port']),
        '--count',
        str(config['count'] if config['count'] is not None else 0),
        '--delay',
        TCP_DELAY,
    ]

    if tcp_uses_ipv6(config):
        command.insert(1, '-6')

    if config['interface']:
        command.extend(['--interface', config['interface']])

    if config['source_address']:
        command.extend(['--source-ip', config['source_address']])

    command.append(config['host'])

    if config['vrf'] != 'default':
        return ['sudo', '/bin/ip', 'vrf', 'exec', config['vrf']] + command

    if config['interface'] or config['source_address']:
        return ['sudo'] + command

    return command


def run_tcp_nping(command, popen=subprocess.Popen):
    successful_connections = None
    process = None

    try:
        process = popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in process.stdout:
            print(line, end='')
            match = SUCCESSFUL_CONNECTIONS_RE.search(line)
            if match:
                successful_connections = int(match.group(1))
        returncode = process.wait()
    except FileNotFoundError:
        raise UsageError('ping tcp: nping is not installed')
    except KeyboardInterrupt:
        if process:
            process.terminate()
            process.wait()
        print()
        return 130

    if successful_connections is not None:
        return 0 if successful_connections > 0 else 1

    return returncode if returncode else 1


def run_tcp_ping(argv):
    try:
        config = parse_tcp_args(argv)
        return run_tcp_nping(build_tcp_nping_command(config))
    except UsageError as err:
        return tcp_usage(str(err))


if __name__ == '__main__':
    args = List(sys.argv[1:])
    host = args.first()

    if not host:
        sys.exit("ping: Missing host")

    if host == '--get-options':
        sys.stdout.write(get_completion(args))
        sys.exit(0)

    if has_tcp_option(['ping', host] + args):
        sys.exit(run_tcp_ping([host] + args))

    for name, option in options.items():
        if 'dflt' in option and name not in args:
            args.append(name)
            args.append(option['dflt'])

    try:
        ip = socket.gethostbyname(host)
    except UnicodeError:
        sys.exit(f'ping: Unknown host: {host}')
    except socket.gaierror:
        ip = host

    try:
        version = ipaddress.ip_address(ip).version
    except ValueError:
        sys.exit(f'ping: Unknown host: {host}')

    command = convert(ping[version], args)
    call(f'{command} {host}')
