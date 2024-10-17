#!/usr/bin/env python3
#
# Copyright (C) 2024 VyOS maintainers and contributors
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

import ipaddress
import socket
import sys
import typing

from json import loads

from vyos.utils.network import interface_list
from vyos.utils.network import vrf_list
from vyos.utils.process import cmd
from vyos.utils.process import call

import vyos.opmode

ArgProtocol = typing.Literal['tcp', 'udp', 'sctp']
noargs_list = [
    'report_mode',
    'json',
    'report_wide',
    'split',
    'raw',
    'no_dns',
    'aslookup',
]


def vrf_list_default():
    return vrf_list() + ['default']


options = {
    'report_mode': {
        'mtr': '{command} --report',
    },
    'protocol': {
        'mtr': '{command} --{value}',
    },
    'json': {
        'mtr': '{command} --json',
    },
    'report_wide': {
        'mtr': '{command} --report-wide',
    },
    'raw': {
        'mtr': '{command} --raw',
    },
    'split': {
        'mtr': '{command} --split',
    },
    'no_dns': {
        'mtr': '{command} --no-dns',
    },
    'show_ips': {
        'mtr': '{command} --show-ips {value}',
    },
    'ipinfo': {
        'mtr': '{command} --ipinfo {value}',
    },
    'aslookup': {
        'mtr': '{command} --aslookup',
    },
    'interval': {
        'mtr': '{command} --interval {value}',
    },
    'report_cycles': {
        'mtr': '{command} --report-cycles {value}',
    },
    'psize': {
        'mtr': '{command} --psize {value}',
    },
    'bitpattern': {
        'mtr': '{command} --bitpattern {value}',
    },
    'gracetime': {
        'mtr': '{command} --gracetime {value}',
    },
    'tos': {
        'mtr': '{command} --tos {value}',
    },
    'mpls': {
        'mtr': '{command} --mpls {value}',
    },
    'interface': {
        'mtr': '{command} --interface {value}',
        'helpfunction': interface_list,
    },
    'address': {
        'mtr': '{command} --address {value}',
    },
    'first_ttl': {
        'mtr': '{command} --first-ttl {value}',
    },
    'max_ttl': {
        'mtr': '{command} --max-ttl {value}',
    },
    'max_unknown': {
        'mtr': '{command} --max-unknown {value}',
    },
    'port': {
        'mtr': '{command} --port {value}',
    },
    'localport': {
        'mtr': '{command} --localport {value}',
    },
    'timeout': {
        'mtr': '{command} --timeout {value}',
    },
    'mark': {
        'mtr': '{command} --mark {value}',
    },
    'vrf': {
        'mtr': 'sudo ip vrf exec {value} {command}',
        'helpfunction': vrf_list_default,
        'dflt': 'default',
    },
}

mtr_command = {
    4: '/bin/mtr -4',
    6: '/bin/mtr -6',
}


def mtr(
    host: str,
    for_api: typing.Optional[bool],
    report_mode: typing.Optional[bool],
    protocol: typing.Optional[ArgProtocol],
    report_wide: typing.Optional[bool],
    raw: typing.Optional[bool],
    json: typing.Optional[bool],
    split: typing.Optional[bool],
    no_dns: typing.Optional[bool],
    show_ips: typing.Optional[str],
    ipinfo: typing.Optional[str],
    aslookup: typing.Optional[bool],
    interval: typing.Optional[str],
    report_cycles: typing.Optional[str],
    psize: typing.Optional[str],
    bitpattern: typing.Optional[str],
    gracetime: typing.Optional[str],
    tos: typing.Optional[str],
    mpl: typing.Optional[bool],
    interface: typing.Optional[str],
    address: typing.Optional[str],
    first_ttl: typing.Optional[str],
    max_ttl: typing.Optional[str],
    max_unknown: typing.Optional[str],
    port: typing.Optional[str],
    localport: typing.Optional[str],
    timeout: typing.Optional[str],
    mark: typing.Optional[str],
    vrf: typing.Optional[str],
):
    args = locals()
    for name, option in options.items():
        if 'dflt' in option and not args[name]:
            args[name] = option['dflt']

    try:
        ip = socket.gethostbyname(host)
    except UnicodeError:
        raise vyos.opmode.InternalError(f'Unknown host: {host}')
    except socket.gaierror:
        ip = host

    try:
        version = ipaddress.ip_address(ip).version
    except ValueError:
        raise vyos.opmode.InternalError(f'Unknown host: {host}')

    command = mtr_command[version]

    for key, val in args.items():
        if key in options and val:
            if 'helpfunction' in options[key]:
                allowed_values = options[key]['helpfunction']()
                if val not in allowed_values:
                    raise vyos.opmode.InternalError(
                        f'Invalid argument for option {key} - {val}'
                    )
            value = '' if key in noargs_list else val
            command = options[key]['mtr'].format(command=command, value=val)

    if json:
        output = cmd(f'{command} {host}')
        if for_api:
            output = loads(output)
        print(output)
    else:
        call(f'{command} --curses --displaymode 0 {host}')


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
