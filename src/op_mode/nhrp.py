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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import tabulate
import vyos.opmode

from vyos.utils.process import cmd
from vyos.utils.process import process_named_running
from vyos.utils.dict import colon_separated_to_dict


def _get_formatted_output(output_dict: dict) -> str:
    """
    Create formatted table for CLI output
    :param output_dict: dictionary for API
    :type output_dict: dict
    :return: tabulate string
    :rtype: str
    """
    print(f"Status: {output_dict['Status']}")
    output: str = tabulate.tabulate(output_dict['routes'], headers='keys',
                                    numalign="left")
    return output


def _get_formatted_dict(output_string: str) -> dict:
    """
    Format string returned from CMD to API list
    :param output_string: String received by CMD
    :type output_string: str
    :return: dictionary for API
    :rtype: dict
    """
    formatted_dict: dict = {
        'Status': '',
        'routes': []
    }
    output_list: list = output_string.split('\n\n')
    for list_a in output_list:
        output_dict = colon_separated_to_dict(list_a, True)
        if 'Status' in output_dict:
            formatted_dict['Status'] = output_dict['Status']
        else:
            formatted_dict['routes'].append(output_dict)
    return formatted_dict


def show_interface(raw: bool):
    """
    Command 'show nhrp interface'
    :param raw: if API
    :type raw: bool
    """
    if not process_named_running('opennhrp'):
        raise vyos.opmode.UnconfiguredSubsystem('OpenNHRP is not running.')
    interface_string: str = cmd('sudo opennhrpctl interface show')
    interface_dict: dict = _get_formatted_dict(interface_string)
    if raw:
        return interface_dict
    else:
        return _get_formatted_output(interface_dict)


def show_tunnel(raw: bool):
    """
    Command 'show nhrp tunnel'
    :param raw: if API
    :type raw: bool
    """
    if not process_named_running('opennhrp'):
        raise vyos.opmode.UnconfiguredSubsystem('OpenNHRP is not running.')
    tunnel_string: str = cmd('sudo opennhrpctl show')
    tunnel_dict: list = _get_formatted_dict(tunnel_string)
    if raw:
        return tunnel_dict
    else:
        return _get_formatted_output(tunnel_dict)


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
