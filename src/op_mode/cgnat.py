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

import json
import sys
import typing

from tabulate import tabulate

import vyos.opmode

from vyos.configquery import ConfigTreeQuery
from vyos.utils.process import cmd

CGNAT_TABLE = 'cgnat'


def _get_raw_data(external_address: str = '', internal_address: str = '') -> list[dict]:
    """Get CGNAT dictionary and filter by external or internal address if provided."""
    cmd_output = cmd(f'nft --json list table ip {CGNAT_TABLE}')
    data = json.loads(cmd_output)

    elements = data['nftables'][2]['map']['elem']
    allocations = []
    for elem in elements:
        internal = elem[0]  # internal
        external = elem[1]['concat'][0]  # external
        start_port = elem[1]['concat'][1]['range'][0]
        end_port = elem[1]['concat'][1]['range'][1]
        port_range = f'{start_port}-{end_port}'

        if (internal_address and internal != internal_address) or (
            external_address and external != external_address
        ):
            continue

        allocations.append(
            {
                'internal_address': internal,
                'external_address': external,
                'port_range': port_range,
            }
        )

    return allocations


def _get_formatted_output(allocations: list[dict]) -> str:
    # Convert the list of dictionaries to a list of tuples for tabulate
    headers = ['Internal IP', 'External IP', 'Port range']
    data = [
        (alloc['internal_address'], alloc['external_address'], alloc['port_range'])
        for alloc in allocations
    ]
    output = tabulate(data, headers, numalign="left")
    return output


def show_allocation(
    raw: bool,
    external_address: typing.Optional[str],
    internal_address: typing.Optional[str],
) -> str:
    config = ConfigTreeQuery()
    if not config.exists('nat cgnat'):
        raise vyos.opmode.UnconfiguredSubsystem('CGNAT is not configured')

    if raw:
        return _get_raw_data(external_address, internal_address)

    else:
        raw_data = _get_raw_data(external_address, internal_address)
        return _get_formatted_output(raw_data)


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
