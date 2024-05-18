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

from tabulate import tabulate

import vyos.opmode

from vyos.configquery import ConfigTreeQuery
from vyos.utils.process import cmd

CGNAT_TABLE = 'cgnat'


def _get_raw_data():
    """ Get CGNAT dictionary
    """
    cmd_output = cmd(f'nft --json list table ip {CGNAT_TABLE}')
    data = json.loads(cmd_output)
    return data


def _get_formatted_output(data):
    elements = data['nftables'][2]['map']['elem']
    allocations = []
    for elem in elements:
        internal = elem[0]  # internal
        external = elem[1]['concat'][0]  # external
        start_port = elem[1]['concat'][1]['range'][0]
        end_port = elem[1]['concat'][1]['range'][1]
        port_range = f'{start_port}-{end_port}'
        allocations.append((internal, external, port_range))

    headers = ['Internal IP', 'External IP', 'Port range']
    output = tabulate(allocations, headers, numalign="left")
    return output


def show_allocation(raw: bool):
    config = ConfigTreeQuery()
    if not config.exists('nat cgnat'):
        raise vyos.opmode.UnconfiguredSubsystem('CGNAT is not configured')

    if raw:
        return _get_raw_data()

    else:
        raw_data = _get_raw_data()
        return _get_formatted_output(raw_data)


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
