# Copyright 2024 VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

import os, re, json
from typing import List

from vyos.base import Warning
from vyos.utils.io import ask_yes_no
from vyos.utils.process import cmd

GLOB_GETTY_UNITS = 'serial-getty@*.service'
RE_GETTY_DEVICES = re.compile(r'.+@(.+).service$')

SD_UNIT_PATH = '/run/systemd/system'
UTMP_PATH = '/run/utmp'

def get_serial_units(include_devices=[]):
    # Since we cannot depend on the current config for decommissioned ports,
    # we just grab everything that systemd knows about.
    tmp = cmd(f'systemctl list-units {GLOB_GETTY_UNITS} --all --output json --no-pager')
    getty_units = json.loads(tmp)
    for sdunit in getty_units:
        m = RE_GETTY_DEVICES.search(sdunit['unit'])
        if m is None:
            Warning(f'Serial console unit name "{sdunit["unit"]}" is malformed and cannot be checked for activity!')
            continue

        getty_device = m.group(1)
        if include_devices and getty_device not in include_devices:
            continue

        sdunit['device'] = getty_device

    return getty_units

def get_authenticated_ports(units):
    connected = []
    ports = [ x['device'] for x in units if 'device' in x ]
    #
    # utmpdump just gives us an easily parseable dump of currently logged-in sessions, for eg:
    # $ utmpdump /run/utmp
    # Utmp dump of /run/utmp
    # [2] [00000] [~~  ] [reboot  ] [~           ] [6.6.31-amd64-vyos   ] [0.0.0.0        ] [2024-06-18T13:56:53,958484+00:00]
    # [1] [00051] [~~  ] [runlevel] [~           ] [6.6.31-amd64-vyos   ] [0.0.0.0        ] [2024-06-18T13:57:01,790808+00:00]
    # [6] [03178] [tty1] [LOGIN   ] [tty1        ] [                    ] [0.0.0.0        ] [2024-06-18T13:57:31,015392+00:00]
    # [7] [37151] [ts/0] [vyos    ] [pts/0       ] [10.9.8.7            ] [10.9.8.7       ] [2024-07-04T13:42:08,760892+00:00]
    # [8] [24812] [ts/1] [        ] [pts/1       ] [10.9.8.7            ] [10.9.8.7       ] [2024-06-20T18:10:07,309365+00:00]
    #
    # We can safely skip blank or LOGIN sessions with valid device names.
    #
    for line in cmd(f'utmpdump {UTMP_PATH}').splitlines():
        row = line.split('] [')
        user_name = row[3].strip()
        user_term = row[4].strip()
        if user_name and user_name != 'LOGIN' and user_term in ports:
            connected.append(user_term)

    return connected

def restart_login_consoles(prompt_user=False, quiet=True, devices: List[str]=[]):
    # restart_login_consoles() is called from both conf- and op-mode scripts, including
    # the warning messages and user prompts common to both.
    #
    # The default case, called with no arguments, is a simple serial-getty restart &
    # cleanup wrapper with no output or prompts that can be used from anywhere.
    #
    # quiet and prompt_user args have been split from an original "no_prompt", in
    # order to support the completely silent default use case. "no_prompt" would
    # only suppress the user interactive prompt.
    #
    # quiet intentionally does not suppress a vyos.base.Warning() for malformed
    # device names in _get_serial_units().
    #
    cmd('systemctl daemon-reload')

    units = get_serial_units(devices)
    connected = get_authenticated_ports(units)

    if connected:
        if not quiet:
            Warning('There are user sessions connected via serial console that '\
                    'will be terminated when serial console settings are changed!')
            if not prompt_user:
                # This flag is used by conf_mode/system_console.py to reset things, if there's
                # a problem, the user should issue a manual restart for serial-getty.
                Warning('Please ensure all settings are committed and saved before issuing a ' \
                      '"restart serial console" command to apply new configuration!')
        if not prompt_user:
            return False
        if not ask_yes_no('Any uncommitted changes from these sessions will be lost\n' \
                          'and in-progress actions may be left in an inconsistent state.\n'\
                          '\nContinue?'):
            return False

    for unit in units:
        if 'device' not in unit:
            continue # malformed or filtered.
        unit_name = unit['unit']
        unit_device = unit['device']
        if os.path.exists(os.path.join(SD_UNIT_PATH, unit_name)):
            cmd(f'systemctl restart {unit_name}')
        else:
            # Deleted stubs don't need to be restarted, just shut them down.
            cmd(f'systemctl stop {unit_name}')

    return True
