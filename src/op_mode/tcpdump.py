#! /usr/bin/env python3

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
    'dump': {
        'cmd': '{command} -A',
        'type': 'noarg',
        'help': 'Print each packet (minus its link level header) in ASCII.'
    },
    'hexdump': {
        'cmd': '{command} -X',
        'type': 'noarg',
        'help': 'Print each packet (minus its link level header) in both hex and ASCII.'
    },
    'filter': {
        'cmd': '{command} \'{value}\'',
        'type': '<pcap-filter>',
        'help': 'Match traffic for capture and display with a pcap-filter expression.'
    },
    'numeric': {
        'cmd': '{command} -nn',
        'type': 'noarg',
        'help': 'Do not attempt to resolve addresses, protocols or services to names.'
    },
    'save': {
        'cmd': '{command} -w {value}',
        'type': '<file>',
        'help': 'Write captured raw packets to <file> rather than parsing or printing them out.'
    },
    'verbose': {
        'cmd': '{command} -vvv -ne',
        'type': 'noarg',
        'help': 'Parse packets with increased detail output, including link-level headers and extended decoding protocol sanity checks.'
    },
}

tcpdump = 'sudo /usr/bin/tcpdump'

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
            sys.exit(f'monitor traffic: missing argument for {longname} option')
        else:
            command = options[longname]['cmd'].format(
                command=command, value=args.first())
    return command


if __name__ == '__main__':
    args = List(sys.argv[1:])
    ifname = args.first()

    # Slightly simplified & tweaked version of the code from mtr.py - it may be 
    # worthwhile to combine and centralise this in a common module. 
    if ifname == '--get-options-nested':
        args.first()  # pop monitor
        args.first()  # pop traffic
        args.first()  # pop interface
        args.first()  # pop <ifname>
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
                # Run helpfunction to get list of possible values
                if 'helpfunction' in options[matched[0]]:
                    result = options[matched[0]]['helpfunction']()
                    if result:
                        helplines = '\n' + ' '.join(result)
                sys.stdout.write(helplines)
                sys.exit(0)

    command = convert(tcpdump, args)
    call(f'{command} -i {ifname}')
