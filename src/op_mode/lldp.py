#!/usr/bin/env python3
#
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

import jmespath
import json
import sys
import typing

from tabulate import tabulate

from vyos.configquery import ConfigTreeQuery
from vyos.utils.process import cmd
from vyos.utils.dict import dict_search

import vyos.opmode
unconf_message = 'LLDP is not configured'
capability_codes = """Capability Codes: R - Router, B - Bridge, W - Wlan r - Repeater, S - Station
                  D - Docsis, T - Telephone, O - Other

"""

def _verify(func):
    """Decorator checks if LLDP config exists"""
    from functools import wraps

    @wraps(func)
    def _wrapper(*args, **kwargs):
        config = ConfigTreeQuery()
        if not config.exists(['service', 'lldp']):
            raise vyos.opmode.UnconfiguredSubsystem(unconf_message)
        return func(*args, **kwargs)
    return _wrapper

def _get_raw_data(interface=None, detail=False):
    """
    If interface name is not set - get all interfaces
    """
    tmp = 'lldpcli -f json show neighbors'
    if detail:
        tmp += f' details'
    if interface:
        tmp += f' ports {interface}'
    output = cmd(tmp)
    data = json.loads(output)
    if not data:
        return []
    return data

def _get_formatted_output(raw_data):
    data_entries = []
    tmp = dict_search('lldp.interface', raw_data)
    if not tmp:
        return None
    # One can not always ensure that "interface" is of type list, add safeguard.
    # E.G. Juniper Networks, Inc. ex2300-c-12t only has a dict, not a list of dicts
    if isinstance(tmp, dict):
        tmp = [tmp]
    for neighbor in tmp:
        for local_if, values in neighbor.items():
            tmp = []

            # Device field
            if 'chassis' in values:
                tmp.append(next(iter(values['chassis'])))
            else:
                tmp.append('')

            # Local Port field
            tmp.append(local_if)

            # Protocol field
            tmp.append(values['via'])

            # Capabilities
            cap = ''
            capabilities = jmespath.search('chassis.[*][0][0].capability', values)
            # One can not always ensure that "capability" is of type list, add
            # safeguard. E.G. Unify US-24-250W only has a dict, not a list of dicts
            if isinstance(capabilities, dict):
                capabilities = [capabilities]
            if capabilities:
                for capability in capabilities:
                    if capability['enabled']:
                        if capability['type'] == 'Router':
                            cap += 'R'
                        if capability['type'] == 'Bridge':
                            cap += 'B'
                        if capability['type'] == 'Wlan':
                            cap += 'W'
                        if capability['type'] == 'Station':
                            cap += 'S'
                        if capability['type'] == 'Repeater':
                            cap += 'r'
                        if capability['type'] == 'Telephone':
                            cap += 'T'
                        if capability['type'] == 'Docsis':
                            cap += 'D'
                        if capability['type'] == 'Other':
                            cap += 'O'
            tmp.append(cap)

            # Remote software platform
            platform = jmespath.search('chassis.[*][0][0].descr', values)
            if platform:
                tmp.append(platform[:37])
            else:
                tmp.append('')

            # Remote interface
            interface = jmespath.search('port.descr', values)
            if not interface:
                interface = jmespath.search('port.id.value', values)
            if not interface:
                interface = 'Unknown'
            tmp.append(interface)

            # Add individual neighbor to output list
            data_entries.append(tmp)

    headers = ["Device", "Local Port", "Protocol", "Capability", "Platform", "Remote Port"]
    output = tabulate(data_entries, headers, numalign="left")
    return capability_codes + output

@_verify
def show_neighbors(raw: bool, interface: typing.Optional[str], detail: typing.Optional[bool]):
    lldp_data = _get_raw_data(interface=interface, detail=detail)
    if raw:
        return lldp_data
    else:
        return _get_formatted_output(lldp_data)

if __name__ == "__main__":
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
