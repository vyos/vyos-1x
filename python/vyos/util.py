# Copyright 2018 VyOS maintainers and contributors <maintainers@vyos.io>
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

import re
import grp
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
