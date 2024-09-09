#! /usr/bin/env python3
#
# Copyright (C) 2024 VyOS maintainers and contributors
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

from vyos.utils.process import call


options = {
    'port': {
        'cmd': '{command} -p {value}',
        'type': '<1-65535> <list>',
        'help': 'Scan specified ports.'
    },
    'tcp': {
        'cmd': '{command} -sT',
        'type': 'noarg',
        'help': 'Use TCP scan.'
    },
    'udp': {
        'cmd': '{command} -sU',
        'type': 'noarg',
        'help': 'Use UDP scan.'
    },
    'skip-ping': {
        'cmd': '{command} -Pn',
        'type': 'noarg',
        'help': 'Skip the Nmap discovery stage altogether.'
    },
    'ipv6': {
        'cmd': '{command} -6',
        'type': 'noarg',
        'help': 'Enable IPv6 scanning.'
    },
}

nmap = 'sudo /usr/bin/nmap'


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


def complete(prefix):
    return [o for o in options if o.startswith(prefix)]


def convert(command, args):
    while args:
        shortname = args.first()
        longnames = complete(shortname)
        if len(longnames) != 1:
            expansion_failure(shortname, longnames)
        longname = longnames[0]
        if options[longname]['type'] == 'noarg':
            command = options[longname]['cmd'].format(
                command=command, value='')
        elif not args:
            sys.exit(f'port-scan: missing argument for {longname} option')
        else:
            command = options[longname]['cmd'].format(
                command=command, value=args.first())
    return command


if __name__ == '__main__':
    args = List(sys.argv[1:])
    host = args.first()

    if host == '--get-options-nested':
        args.first()  # pop execute
        args.first()  # pop port-scan
        args.first()  # pop host
        args.first()  # pop <host>
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
                if not matched:
                    sys.stdout.write('<nocomps>')
                else:
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
                sys.stdout.write(helplines)
                sys.exit(0)

    command = convert(nmap, args)
    call(f'{command} -T4 {host}')
