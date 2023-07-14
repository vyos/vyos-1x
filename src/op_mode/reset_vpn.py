#!/usr/bin/env python3
#
# Copyright (C) 2022-2023 VyOS maintainers and contributors
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
import typing

from vyos.utils.process import run

import vyos.opmode

cmd_dict = {
    'cmd_base': '/usr/bin/accel-cmd -p {} terminate {} {}',
    'vpn_types': {
        'pptp': 2003,
        'l2tp': 2004,
        'sstp': 2005
    }
}

def reset_conn(protocol: str, username: typing.Optional[str] = None,
               interface: typing.Optional[str] = None):
    if protocol in cmd_dict['vpn_types']:
        # Reset by Interface
        if interface:
            run(cmd_dict['cmd_base'].format(cmd_dict['vpn_types'][protocol],
                                            'if', interface))
            return
            # Reset by username
        if username:
            run(cmd_dict['cmd_base'].format(cmd_dict['vpn_types'][protocol],
                                            'username', username))
        # Reset all
        else:
            run(cmd_dict['cmd_base'].format(cmd_dict['vpn_types'][protocol],
                                            'all',
                                            ''))
    else:
        vyos.opmode.IncorrectValue('Unknown VPN Protocol, aborting')


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
