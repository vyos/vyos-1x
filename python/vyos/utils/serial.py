# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

import os
import re
import json
import socket
from typing import List
from pathlib import Path

from vyos.base import Warning
from vyos.utils.io import ask_yes_no
from vyos.utils.process import cmd
from vyos.utils.file import read_file
from vyos.utils.process import is_systemd_service_running

GLOB_GETTY_UNITS = 'serial-getty@*.service'
RE_GETTY_DEVICES = re.compile(r'.+@(.+).service$')

SD_UNIT_PATH = '/run/systemd/system'
UTMP_PATH = '/run/utmp'

SOCKET_PATH = '/tmp/iol_perleinit'
SERIAL_SERVICE = 'iolan-monitor.service'

SERIAL_DEV_PREFIX = 'ttyS'
SERIAL_CONFIG_PATH = Path('/run/serial')
SERINFO_PATH = Path('/tmp/serinfo')

def send_command_to_iolan(action, name):
    msg = {
        'action': action,  # 'restart' | 'stop' | 'delete' | 'relaunch'
        'name': name,
    }

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)

    # Send message as JSON
    try:
        if not os.path.exists(SOCKET_PATH) and is_systemd_service_running(SERIAL_SERVICE):
            cmd(f'systemctl restart {SERIAL_SERVICE}')
            cmd(f'systemctl is-active --wait {SERIAL_SERVICE}')

        sock.sendto(json.dumps(msg).encode(), SOCKET_PATH)
        # print(f'Sent to {SOCKET_PATH}:\n{json.dumps(msg, indent=4)}')
    except Exception as e:
        print(f'Error sending message: {e}')
    finally:
        sock.close()

def print_global_change_warning():
    Warning('Global configuration changes have been made. To activate the new settings, run the "restart serial ..." command to restart the serial port!')

def find_enabled_consoles():
    consoles_file = Path('/proc/consoles')
    consoles = []

    if not consoles_file.exists():
        return consoles

    for line in consoles_file.read_text().splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue

        dev_name = parts[0]
        if SERIAL_DEV_PREFIX not in dev_name:
            continue

        flags = parts[2].strip('()')
        if 'E' in flags:
            consoles.append(f'{dev_name}')

    return consoles

def find_all_ttyS_devices():
    '''
    Device files /dev/ttySx could exist without hardware
    Use proc file to get real 8250 serial ports
    Save sudo cat output in /tmp because of 'driver' dir permission issue
    '''
    tty_devices = []
    if not SERINFO_PATH.exists():
        serinfo = read_file('/proc/tty/driver/serial', defaultonfailure='', sudo=True)
        if not serinfo:
            return tty_devices
        SERINFO_PATH.write_text(serinfo)

    if not SERINFO_PATH.exists():
        print('Error: Failed to get ttyS info')
        return tty_devices

    for line in SERINFO_PATH.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        index, driver = line.split(':', 1)
        index = index.strip()
        driver = driver.strip()

        if 'unknown' in driver:
            continue

        tty_path = Path(f'/dev/{SERIAL_DEV_PREFIX}{index}')
        if tty_path.exists():
            tty_devices.append(f'{SERIAL_DEV_PREFIX}{index}')

    return tty_devices

def find_all_ttyS_devices_without_console():
    console_set = set(find_enabled_consoles())
    return [tty for tty in find_all_ttyS_devices() if tty not in console_set]

def find_active_ttyS_devices():
    tty_devices = []
    if not SERIAL_CONFIG_PATH.exists():
        return tty_devices

    for path in SERIAL_CONFIG_PATH.iterdir():
        if not path.name.startswith(SERIAL_DEV_PREFIX) or path.suffix != '.json':
            continue
        try:
            with path.open('r') as f:
                data = json.load(f)
            if 'disable' in data:
                continue
            tty_devices.append(path.stem)
        except Exception as e:
            print(f'Error processing {path}: {e}')

    return sorted(tty_devices)

def find_active_ttyS_devices_with_auth_on():
    tty_devices = []
    if not SERIAL_CONFIG_PATH.exists():
        return tty_devices

    for path in SERIAL_CONFIG_PATH.iterdir():
        auth = 0
        if not path.name.startswith(SERIAL_DEV_PREFIX) or path.suffix != '.json':
            continue
        try:
            with path.open('r') as f:
                data = json.load(f)
            if 'disable' in data:
                continue

            if 'ssh-reverse' in data['service']:
                auth = 1
            if 'telnet-reverse' in data['service'] or 'tcp-reverse' in data['service']:
                if 'service_setting' in data:
                    if 'reverse' in data['service_setting']:
                        if 'auth_user' in data['service_setting']['reverse']:
                            auth = 1

            if auth == 0:
                continue

            tty_devices.append(path.stem)
        except Exception as e:
            print(f'Error processing {path}: {e}')

    return sorted(tty_devices)

def find_active_ttyS_devices_running_service(service):
    tty_devices = []
    if not SERIAL_CONFIG_PATH.exists():
        return tty_devices

    for path in SERIAL_CONFIG_PATH.iterdir():
        if not path.name.startswith(SERIAL_DEV_PREFIX) or path.suffix != '.json':
            continue
        try:
            with path.open('r') as f:
                data = json.load(f)
            if 'disable' in data:
                continue
            if service == 'console-management' and ('ssh-reverse' in data['service'] or 'telnet-reverse' in data['service']):
                tty_devices.append(path.stem)
            elif service == 'modbus-master' and 'modbus-master' in data['service']:
                tty_devices.append(path.stem)
            elif service == 'modbus-slave' and 'modbus-slave' in data['service']:
                tty_devices.append(path.stem)
            elif service == 'ppp' and 'ppp' in data['service']:
                tty_devices.append(path.stem)
            elif service == 'slip' and 'slip' in data['service']:
                tty_devices.append(path.stem)

        except Exception as e:
            print(f'Error processing {path}: {e}')

    return sorted(tty_devices)

def is_ttyS(tty_name, skip_tty_err_msg=False):
    consoles = set(find_enabled_consoles())
    tty_devices = set(find_all_ttyS_devices_without_console())

    if tty_name in consoles:
        print(f'Error: {tty_name} is system console')
        return False
    if tty_name not in tty_devices:
        if not skip_tty_err_msg:
            print(f'Error: {tty_name} is not a valid tty')
        return False

    return True

def is_valid_ttyS_range(tty_range=None, tty_start=None, tty_end=None):
    if not tty_range:
        if not tty_start:
            return False
        if not tty_end:
            if not is_ttyS(tty_start):
                return False

    tty_max_num = int(find_all_ttyS_devices_without_console()[-1][4:])

    tty_range_str = ''
    if not tty_range:
        tty_range = f'{tty_start}-{tty_end}'
        tty_range_str = f'{tty_start} to {tty_end}'
    else:
        tty_range_str = tty_range

    match = re.match(r'^ttyS(\d{1,})(?:-ttyS(\d{1,}))?$', tty_range)

    if not match:
        print(f'Error: {tty_range_str} is not a valid tty or tty range')
        return False

    tty_start_num = int(match.group(1))
    tty_end_num = int(match.group(2)) if match.group(2) else tty_start_num

    if tty_start_num > tty_end_num or tty_end_num > tty_max_num:
        print(f'Error: {tty_range_str} is not a valid tty or tty range')
        return False

    for i in range(tty_start_num, tty_end_num + 1):
        if not is_ttyS(f'ttyS{i}', skip_tty_err_msg=True):
            print(f'Error: {tty_range_str} is not a valid tty or tty range')
            return False
    return True

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
                      '"restart serial" command to apply new configuration!')
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

def is_tty(name: str, warning=False) -> bool:
    """ Check if a given device file (e.g. /dev/ttyS0) is a TTY (teletypewriter)
    device in Linux
    """
    import os
    path_tty = f'/dev/{name}'
    if os.path.exists(path_tty):
        with open(path_tty, 'rb') as f:
            fd = f.fileno()
            # True if filename is a TTY
            return os.isatty(fd)
    elif warning:
        from vyos.base import Warning
        Warning(f'Device "{name}" does not exist!')
    return False
