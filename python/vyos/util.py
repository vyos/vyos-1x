# Copyright 2019 VyOS maintainers and contributors <maintainers@vyos.io>
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
import getpass
import grp
import time
import subprocess
import sys

import psutil

import vyos.defaults


def read_file(path):
    """ Read a file to string """
    with open(path, 'r') as f:
        data = f.read().strip()
    return data

def colon_separated_to_dict(data_string, uniquekeys=False):
    """ Converts a string containing newline-separated entries
        of colon-separated key-value pairs into a dict.

        Such files are common in Linux /proc filesystem

    Args:
        data_string (str): data string
        uniquekeys (bool): whether to insist that keys are unique or not

    Returns: dict

    Raises:
        ValueError: if uniquekeys=True and the data string has
            duplicate keys.

    Note:
        If uniquekeys=True, then dict entries are always strings,
        otherwise they are always lists of strings.
    """
    key_value_re = re.compile('([^:]+)\s*\:\s*(.*)')

    data_raw = re.split('\n', data_string)

    data = {}

    for l in data_raw:
        l = l.strip()
        if l:
            match = re.match(key_value_re, l)
            if match:
                key = match.groups()[0].strip()
                value = match.groups()[1].strip()
            if key in data.keys():
                if uniquekeys:
                    raise ValueError("Data string has duplicate keys: {0}".format(key))
                else:
                    data[key].append(value)
            else:
                if uniquekeys:
                    data[key] = value
                else:
                    data[key] = [value]
        else:
            pass

    return data

def process_running(pid_file):
    """ Checks if a process with PID in pid_file is running """
    with open(pid_file, 'r') as f:
        pid = f.read().strip()
    return psutil.pid_exists(int(pid))

def seconds_to_human(s, separator=""):
    """ Converts number of seconds passed to a human-readable
    interval such as 1w4d18h35m59s
    """
    s = int(s)

    week = 60 * 60 * 24 * 7
    day = 60 * 60 * 24
    hour = 60 * 60

    remainder = 0
    result = ""

    weeks = s // week
    if weeks > 0:
        result = "{0}w".format(weeks)
        s = s % week

    days = s // day
    if days > 0:
        result = "{0}{1}{2}d".format(result, separator, days)
        s = s % day

    hours = s // hour
    if hours > 0:
        result = "{0}{1}{2}h".format(result, separator, hours)
        s = s % hour

    minutes = s // 60
    if minutes > 0:
        result = "{0}{1}{2}m".format(result, separator, minutes)
        s = s % 60

    seconds = s
    if seconds > 0:
        result = "{0}{1}{2}s".format(result, separator, seconds)

    return result

def get_cfg_group_id():
    group_data = grp.getgrnam(vyos.defaults.cfg_group)
    return group_data.gr_gid

def file_is_persistent(path):
    if not re.match(r'^(/config|/opt/vyatta/etc/config)', os.path.dirname(path)):
        warning = "Warning: file {0} is outside the /config directory\n".format(path)
        warning += "It will not be automatically migrated to a new image on system update"
        return (False, warning)
    else:
        return (True, None)

def commit_in_progress():
    """ Not to be used in normal op mode scripts! """

    # The CStore backend locks the config by opening a file
    # The file is not removed after commit, so just checking
    # if it exists is insufficient, we need to know if it's open by anyone

    # There are two ways to check if any other process keeps a file open.
    # The first one is to try opening it and see if the OS objects.
    # That's faster but prone to race conditions and can be intrusive.
    # The other one is to actually check if any process keeps it open.
    # It's non-intrusive but needs root permissions, else you can't check
    # processes of other users.
    #
    # Since this will be used in scripts that modify the config outside of the CLI
    # framework, those knowingly have root permissions.
    # For everything else, we add a safeguard.
    id = subprocess.check_output(['/usr/bin/id', '-u']).decode().strip()
    if id != '0':
        raise OSError("This functions needs root permissions to return correct results")

    for proc in psutil.process_iter():
        try:
            files = proc.open_files()
            if files:
                for f in files:
                    if f.path == vyos.defaults.commit_lock:
                        return True
        except psutil.NoSuchProcess as err:
            # Process died before we could examine it
            pass
    # Default case
    return False

def wait_for_commit_lock():
    """ Not to be used in normal op mode scripts! """

    # Very synchronous approach to multiprocessing
    while commit_in_progress():
        time.sleep(1)

def ask_yes_no(question, default=False) -> bool:
    """Ask a yes/no question via input() and return their answer."""
    default_msg = "[Y/n]" if default else "[y/N]"
    while True:
        sys.stdout.write("%s %s " % (question, default_msg))
        c = input().lower()
        if c == '':
            return default
        elif c in ("y", "ye", "yes"):
            return True
        elif c in ("n", "no"):
            return False
        else:
            sys.stdout.write("Please respond with yes/y or no/n\n")


def is_admin() -> bool:
    """Look if current user is in sudo group"""
    current_user = getpass.getuser()
    (_, _, _, admin_group_members) = grp.getgrnam('sudo')
    return current_user in admin_group_members

def escape_backslash(string: str) -> str:
    """Escape single backslashes in string that are not in escape sequence"""
    p = re.compile(r'(?<!\\)[\\](?!b|f|n|r|t|\\)')
    result = p.sub(r'\\\\', string)
    return result
