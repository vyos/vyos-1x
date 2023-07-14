# Copyright 2020-2023 VyOS maintainers and contributors <maintainers@vyos.io>
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
import sys

#
# NOTE: Do not import full classes here, move your import to the function
# where it is used so it is as local as possible to the execution
#


def _mangle_dict_keys(data, regex, replacement, abs_path=[], no_tag_node_value_mangle=False, mod=0):
    """ Mangles dict keys according to a regex and replacement character.
    Some libraries like Jinja2 do not like certain characters in dict keys.
    This function can be used for replacing all offending characters
    with something acceptable.

    Args:
        data (dict): Original dict to mangle

    Returns: dict
    """
    from vyos.xml import is_tag

    new_dict = {}

    for key in data.keys():
        save_mod = mod
        save_path = abs_path[:]

        abs_path.append(key)

        if not is_tag(abs_path):
            new_key = re.sub(regex, replacement, key)
        else:
            if mod%2:
                new_key = key
            else:
                new_key = re.sub(regex, replacement, key)
            if no_tag_node_value_mangle:
                mod += 1

        value = data[key]

        if isinstance(value, dict):
            new_dict[new_key] = _mangle_dict_keys(value, regex, replacement, abs_path=abs_path, mod=mod, no_tag_node_value_mangle=no_tag_node_value_mangle)
        else:
            new_dict[new_key] = value

        mod = save_mod
        abs_path = save_path[:]

    return new_dict

def mangle_dict_keys(data, regex, replacement, abs_path=[], no_tag_node_value_mangle=False):
    return _mangle_dict_keys(data, regex, replacement, abs_path=abs_path, no_tag_node_value_mangle=no_tag_node_value_mangle, mod=0)

def is_list_equal(first: list, second: list) -> bool:
    """ Check if 2 lists are equal and list not empty """
    if len(first) != len(second) or len(first) == 0:
        return False
    return sorted(first) == sorted(second)

def is_listen_port_bind_service(port: int, service: str) -> bool:
    """Check if listen port bound to expected program name
    :param port: Bind port
    :param service: Program name
    :return: bool

    Example:
        % is_listen_port_bind_service(443, 'nginx')
        True
        % is_listen_port_bind_service(443, 'ocserv-main')
        False
    """
    from psutil import net_connections as connections
    from psutil import Process as process
    for connection in connections():
        addr = connection.laddr
        pid = connection.pid
        pid_name = process(pid).name()
        pid_port = addr.port
        if service == pid_name and port == pid_port:
            return True
    return False

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

def bytes_to_human(bytes, initial_exponent=0, precision=2):
    """ Converts a value in bytes to a human-readable size string like 640 KB

    The initial_exponent parameter is the exponent of 2,
    e.g. 10 (1024) for kilobytes, 20 (1024 * 1024) for megabytes.
    """

    if bytes == 0:
        return "0 B"

    from math import log2

    bytes = bytes * (2**initial_exponent)

    # log2 is a float, while range checking requires an int
    exponent = int(log2(bytes))

    if exponent < 10:
        value = bytes
        suffix = "B"
    elif exponent in range(10, 20):
        value = bytes / 1024
        suffix = "KB"
    elif exponent in range(20, 30):
        value = bytes / 1024**2
        suffix = "MB"
    elif exponent in range(30, 40):
        value = bytes / 1024**3
        suffix = "GB"
    else:
        value = bytes / 1024**4
        suffix = "TB"
    # Add a new case when the first machine with petabyte RAM
    # hits the market.

    size_string = "{0:.{1}f} {2}".format(value, precision, suffix)
    return size_string

def human_to_bytes(value):
    """ Converts a data amount with a unit suffix to bytes, like 2K to 2048 """

    from re import match as re_match

    res = re_match(r'^\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)\s*$', value)

    if not res:
        raise ValueError(f"'{value}' is not a valid data amount")
    else:
        amount = float(res.group(1))
        unit = res.group(2).lower()

        if unit == 'b':
            res = amount
        elif (unit == 'k') or (unit == 'kb'):
            res = amount * 1024
        elif (unit == 'm') or (unit == 'mb'):
            res = amount * 1024**2
        elif (unit == 'g') or (unit == 'gb'):
            res = amount * 1024**3
        elif (unit == 't') or (unit == 'tb'):
            res = amount * 1024**4
        else:
            raise ValueError(f"Unsupported data unit '{unit}'")

    # There cannot be fractional bytes, so we convert them to integer.
    # However, truncating causes problems with conversion back to human unit,
    # so we round instead -- that seems to work well enough.
    return round(res)

def get_cfg_group_id():
    from grp import getgrnam
    from vyos.defaults import cfg_group

    group_data = getgrnam(cfg_group)
    return group_data.gr_gid

def wait_for_inotify(file_path, pre_hook=None, event_type=None, timeout=None, sleep_interval=0.1):
    """ Waits for an inotify event to occur """
    if not os.path.dirname(file_path):
        raise ValueError(
          "File path {} does not have a directory part (required for inotify watching)".format(file_path))
    if not os.path.basename(file_path):
        raise ValueError(
          "File path {} does not have a file part, do not know what to watch for".format(file_path))

    from inotify.adapters import Inotify
    from time import time
    from time import sleep

    time_start = time()

    i = Inotify()
    i.add_watch(os.path.dirname(file_path))

    if pre_hook:
        pre_hook()

    for event in i.event_gen(yield_nones=True):
        if (timeout is not None) and ((time() - time_start) > timeout):
            # If the function didn't return until this point,
            # the file failed to have been written to and closed within the timeout
            raise OSError("Waiting for file {} to be written has failed".format(file_path))

        # Most such events don't take much time, so it's better to check right away
        # and sleep later.
        if event is not None:
            (_, type_names, path, filename) = event
            if filename == os.path.basename(file_path):
                if event_type in type_names:
                    return
        sleep(sleep_interval)

def wait_for_file_write_complete(file_path, pre_hook=None, timeout=None, sleep_interval=0.1):
    """ Waits for a process to close a file after opening it in write mode. """
    wait_for_inotify(file_path,
      event_type='IN_CLOSE_WRITE', pre_hook=pre_hook, timeout=timeout, sleep_interval=sleep_interval)

def ask_input(question, default='', numeric_only=False, valid_responses=[]):
    question_out = question
    if default:
        question_out += f' (Default: {default})'
    response = ''
    while True:
        response = input(question_out + ' ').strip()
        if not response and default:
            return default
        if numeric_only:
            if not response.isnumeric():
                print("Invalid value, try again.")
                continue
            response = int(response)
        if valid_responses and response not in valid_responses:
            print("Invalid value, try again.")
            continue
        break
    return response

def ask_yes_no(question, default=False) -> bool:
    """Ask a yes/no question via input() and return their answer."""
    from sys import stdout
    default_msg = "[Y/n]" if default else "[y/N]"
    while True:
        try:
            stdout.write("%s %s " % (question, default_msg))
            c = input().lower()
            if c == '':
                return default
            elif c in ("y", "ye", "yes"):
                return True
            elif c in ("n", "no"):
                return False
            else:
                stdout.write("Please respond with yes/y or no/n\n")
        except EOFError:
            stdout.write("\nPlease respond with yes/y or no/n\n")

def is_admin() -> bool:
    """Look if current user is in sudo group"""
    from getpass import getuser
    from grp import getgrnam
    current_user = getuser()
    (_, _, _, admin_group_members) = getgrnam('sudo')
    return current_user in admin_group_members

def mac2eui64(mac, prefix=None):
    """
    Convert a MAC address to a EUI64 address or, with prefix provided, a full
    IPv6 address.
    Thankfully copied from https://gist.github.com/wido/f5e32576bb57b5cc6f934e177a37a0d3
    """
    import re
    from ipaddress import ip_network
    # http://tools.ietf.org/html/rfc4291#section-2.5.1
    eui64 = re.sub(r'[.:-]', '', mac).lower()
    eui64 = eui64[0:6] + 'fffe' + eui64[6:]
    eui64 = hex(int(eui64[0:2], 16) ^ 2)[2:].zfill(2) + eui64[2:]

    if prefix is None:
        return ':'.join(re.findall(r'.{4}', eui64))
    else:
        try:
            net = ip_network(prefix, strict=False)
            euil = int('0x{0}'.format(eui64), 16)
            return str(net[euil])
        except:  # pylint: disable=bare-except
            return

def get_half_cpus():
    """ return 1/2 of the numbers of available CPUs """
    cpu = os.cpu_count()
    if cpu > 1:
        cpu /= 2
    return int(cpu)

def check_kmod(k_mod):
    """ Common utility function to load required kernel modules on demand """
    from vyos import ConfigError
    from vyos.utils.process import call
    if isinstance(k_mod, str):
        k_mod = k_mod.split()
    for module in k_mod:
        if not os.path.exists(f'/sys/module/{module}'):
            if call(f'modprobe {module}') != 0:
                raise ConfigError(f'Loading Kernel module {module} failed')

def find_device_file(device):
    """ Recurively search /dev for the given device file and return its full path.
        If no device file was found 'None' is returned """
    from fnmatch import fnmatch

    for root, dirs, files in os.walk('/dev'):
        for basename in files:
            if fnmatch(basename, device):
                return os.path.join(root, basename)

    return None

def convert_data(data):
    """Convert multiple types of data to types usable in CLI

    Args:
        data (str | bytes | list | OrderedDict): input data

    Returns:
        str | list | dict: converted data
    """
    from base64 import b64encode
    from collections import OrderedDict

    if isinstance(data, str):
        return data
    if isinstance(data, bytes):
        try:
            return data.decode()
        except UnicodeDecodeError:
            return b64encode(data).decode()
    if isinstance(data, list):
        list_tmp = []
        for item in data:
            list_tmp.append(convert_data(item))
        return list_tmp
    if isinstance(data, OrderedDict):
        dict_tmp = {}
        for key, value in data.items():
            dict_tmp[key] = convert_data(value)
        return dict_tmp

def print_error(str='', end='\n'):
    """
    Print `str` to stderr, terminated with `end`.
    Used for warnings and out-of-band messages to avoid mangling precious
     stdout output.
    """
    sys.stderr.write(str)
    sys.stderr.write(end)
    sys.stderr.flush()

def make_progressbar():
    """
    Make a procedure that takes two arguments `done` and `total` and prints a
     progressbar based on the ratio thereof, whose length is determined by the
     width of the terminal.
    """
    import shutil, math
    col, _ = shutil.get_terminal_size()
    col = max(col - 15, 20)
    def print_progressbar(done, total):
        if done <= total:
            increment = total / col
            length = math.ceil(done / increment)
            percentage = str(math.ceil(100 * done / total)).rjust(3)
            print_error(f'[{length * "#"}{(col - length) * "_"}] {percentage}%', '\r')
            # Print a newline so that the subsequent prints don't overwrite the full bar.
        if done == total:
            print_error()
    return print_progressbar

def make_incremental_progressbar(increment: float):
    """
    Make a generator that displays a progressbar that grows monotonically with
     every iteration.
    First call displays it at 0% and every subsequent iteration displays it
     at `increment` increments where 0.0 < `increment` < 1.0.
    Intended for FTP and HTTP transfers with stateless callbacks.
    """
    print_progressbar = make_progressbar()
    total = 0.0
    while total < 1.0:
        print_progressbar(total, 1.0)
        yield
        total += increment
    print_progressbar(1, 1)
    # Ignore further calls.
    while True:
        yield

def begin(*args):
    """
    Evaluate arguments in order and return the result of the *last* argument.
    For combining multiple expressions in one statement. Useful for lambdas.
    """
    return args[-1]

def begin0(*args):
    """
    Evaluate arguments in order and return the result of the *first* argument.
    For combining multiple expressions in one statement. Useful for lambdas.
    """
    return args[0]

def install_into_config(conf, config_paths, override_prompt=True):
    # Allows op-mode scripts to install values if called from an active config session
    # config_paths: dict of config paths
    # override_prompt: if True, user will be prompted before existing nodes are overwritten

    if not config_paths:
        return None

    from vyos.config import Config
    if not Config().in_session():
        print('You are not in configure mode, commands to install manually from configure mode:')
        for path in config_paths:
            print(f'set {path}')
        return None

    from vyos.utils.process import cmd

    count = 0
    failed = []

    for path in config_paths:
        if override_prompt and conf.exists(path) and not conf.is_multi(path):
            if not ask_yes_no(f'Config node "{node}" already exists. Do you want to overwrite it?'):
                continue

        try:
            cmd(f'/opt/vyatta/sbin/my_set {path}')
            count += 1
        except:
            failed.append(path)

    if failed:
        print(f'Failed to install {len(failed)} value(s). Commands to manually install:')
        for path in failed:
            print(f'set {path}')

    if count > 0:
        print(f'{count} value(s) installed. Use "compare" to see the pending changes, and "commit" to apply.')

def load_as_module(name: str, path: str):
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
