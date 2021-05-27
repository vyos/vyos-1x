# Copyright 2020-2021 VyOS maintainers and contributors <maintainers@vyos.io>
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

from subprocess import Popen
from subprocess import PIPE
from subprocess import STDOUT
from subprocess import DEVNULL

def popen(command, flag='', shell=None, input=None, timeout=None, env=None,
          stdout=PIPE, stderr=PIPE, decode='utf-8'):
    """
    popen is a wrapper helper aound subprocess.Popen
    with it default setting it will return a tuple (out, err)
    out: the output of the program run
    err: the error code returned by the program

    it can be affected by the following flags:
    shell:   do not try to auto-detect if a shell is required
             for example if a pipe (|) or redirection (>, >>) is used
    input:   data to sent to the child process via STDIN
             the data should be bytes but string will be converted
    timeout: time after which the command will be considered to have failed
    env:     mapping that defines the environment variables for the new process
    stdout:  define how the output of the program should be handled
              - PIPE (default), sends stdout to the output
              - DEVNULL, discard the output
    stderr:  define how the output of the program should be handled
              - None (default), send/merge the data to/with stderr
              - PIPE, popen will append it to output
              - STDOUT, send the data to be merged with stdout
              - DEVNULL, discard the output
    decode:  specify the expected text encoding (utf-8, ascii, ...)
             the default is explicitely utf-8 which is python's own default

    usage:
    get both stdout and stderr: popen('command', stdout=PIPE, stderr=STDOUT)
    discard stdout and get stderr: popen('command', stdout=DEVNUL, stderr=PIPE)
    """

    # airbag must be left as an import in the function as otherwise we have a
    # a circual import dependency
    from vyos import debug
    from vyos import airbag

    # log if the flag is set, otherwise log if command is set
    if not debug.enabled(flag):
        flag = 'command'

    cmd_msg = f"cmd '{command}'"
    debug.message(cmd_msg, flag)

    use_shell = shell
    stdin = None
    if shell is None:
        use_shell = False
        if ' ' in command:
            use_shell = True
        if env:
            use_shell = True

    if input:
        stdin = PIPE
        input = input.encode() if type(input) is str else input

    p = Popen(command, stdin=stdin, stdout=stdout, stderr=stderr,
              env=env, shell=use_shell)

    pipe = p.communicate(input, timeout)

    pipe_out = b''
    if stdout == PIPE:
        pipe_out = pipe[0]

    pipe_err = b''
    if stderr == PIPE:
        pipe_err = pipe[1]

    str_out = pipe_out.decode(decode).replace('\r\n', '\n').strip()
    str_err = pipe_err.decode(decode).replace('\r\n', '\n').strip()

    out_msg = f"returned (out):\n{str_out}"
    if str_out:
        debug.message(out_msg, flag)

    if str_err:
        err_msg = f"returned (err):\n{str_err}"
        # this message will also be send to syslog via airbag
        debug.message(err_msg, flag, destination=sys.stderr)

        # should something go wrong, report this too via airbag
        airbag.noteworthy(cmd_msg)
        airbag.noteworthy(out_msg)
        airbag.noteworthy(err_msg)

    return str_out, p.returncode


def run(command, flag='', shell=None, input=None, timeout=None, env=None,
        stdout=DEVNULL, stderr=PIPE, decode='utf-8'):
    """
    A wrapper around popen, which discard the stdout and
    will return the error code of a command
    """
    _, code = popen(
        command, flag,
        stdout=stdout, stderr=stderr,
        input=input, timeout=timeout,
        env=env, shell=shell,
        decode=decode,
    )
    return code


def cmd(command, flag='', shell=None, input=None, timeout=None, env=None,
        stdout=PIPE, stderr=PIPE, decode='utf-8', raising=None, message='',
        expect=[0]):
    """
    A wrapper around popen, which returns the stdout and
    will raise the error code of a command

    raising: specify which call should be used when raising
             the class should only require a string as parameter
             (default is OSError) with the error code
    expect:  a list of error codes to consider as normal
    """
    decoded, code = popen(
        command, flag,
        stdout=stdout, stderr=stderr,
        input=input, timeout=timeout,
        env=env, shell=shell,
        decode=decode,
    )
    if code not in expect:
        feedback = message + '\n' if message else ''
        feedback += f'failed to run command: {command}\n'
        feedback += f'returned: {decoded}\n'
        feedback += f'exit code: {code}'
        if raising is None:
            # error code can be recovered with .errno
            raise OSError(code, feedback)
        else:
            raise raising(feedback)
    return decoded


def call(command, flag='', shell=None, input=None, timeout=None, env=None,
         stdout=PIPE, stderr=PIPE, decode='utf-8'):
    """
    A wrapper around popen, which print the stdout and
    will return the error code of a command
    """
    out, code = popen(
        command, flag,
        stdout=stdout, stderr=stderr,
        input=input, timeout=timeout,
        env=env, shell=shell,
        decode=decode,
    )
    if out:
        print(out)
    return code


def read_file(fname, defaultonfailure=None):
    """
    read the content of a file, stripping any end characters (space, newlines)
    should defaultonfailure be not None, it is returned on failure to read
    """
    try:
        """ Read a file to string """
        with open(fname, 'r') as f:
            data = f.read().strip()
        return data
    except Exception as e:
        if defaultonfailure is not None:
            return defaultonfailure
        raise e

def write_file(fname, data, defaultonfailure=None, user=None, group=None):
    """
    Write content of data to given fname, should defaultonfailure be not None,
    it is returned on failure to read.

    If directory of file is not present, it is auto-created.
    """
    dirname = os.path.dirname(fname)
    if not os.path.isdir(dirname):
        os.makedirs(dirname, mode=0o755, exist_ok=False)
        chown(dirname, user, group)

    try:
        """ Write a file to string """
        bytes = 0
        with open(fname, 'w') as f:
            bytes = f.write(data)
        chown(fname, user, group)
        return bytes
    except Exception as e:
        if defaultonfailure is not None:
            return defaultonfailure
        raise e


def read_json(fname, defaultonfailure=None):
    """
    read and json decode the content of a file
    should defaultonfailure be not None, it is returned on failure to read
    """
    import json
    try:
        with open(fname, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        if defaultonfailure is not None:
            return defaultonfailure
        raise e


def chown(path, user, group):
    """ change file/directory owner """
    from pwd import getpwnam
    from grp import getgrnam

    if user is None or group is None:
        return False

    # path may also be an open file descriptor
    if not isinstance(path, int) and not os.path.exists(path):
        return False

    uid = getpwnam(user).pw_uid
    gid = getgrnam(group).gr_gid
    os.chown(path, uid, gid)
    return True


def chmod(path, bitmask):
    # path may also be an open file descriptor
    if not isinstance(path, int) and not os.path.exists(path):
        return
    if bitmask is None:
        return
    os.chmod(path, bitmask)


def chmod_600(path):
    """ make file only read/writable by owner """
    from stat import S_IRUSR, S_IWUSR

    bitmask = S_IRUSR | S_IWUSR
    chmod(path, bitmask)


def chmod_750(path):
    """ make file/directory only executable to user and group """
    from stat import S_IRUSR, S_IWUSR, S_IXUSR, S_IRGRP, S_IXGRP

    bitmask = S_IRUSR | S_IWUSR | S_IXUSR | S_IRGRP | S_IXGRP
    chmod(path, bitmask)


def chmod_755(path):
    """ make file executable by all """
    from stat import S_IRUSR, S_IWUSR, S_IXUSR, S_IRGRP, S_IXGRP, S_IROTH, S_IXOTH

    bitmask = S_IRUSR | S_IWUSR | S_IXUSR | S_IRGRP | S_IXGRP | \
              S_IROTH | S_IXOTH
    chmod(path, bitmask)


def makedir(path, user=None, group=None):
    if os.path.exists(path):
        return
    os.makedirs(path, mode=0o755)
    chown(path, user, group)


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
    import re
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

def _get_sub_dict(d, lpath):
    k = lpath[0]
    if k not in d.keys():
        return {}
    c = {k: d[k]}
    lpath = lpath[1:]
    if not lpath:
        return c
    elif not isinstance(c[k], dict):
        return {}
    return _get_sub_dict(c[k], lpath)

def get_sub_dict(source, lpath, get_first_key=False):
    """ Returns the sub-dict of a nested dict, defined by path of keys.

    Args:
        source (dict): Source dict to extract from
        lpath (list[str]): sequence of keys

    Returns: source, if lpath is empty, else
             {key : source[..]..[key]} for key the last element of lpath, if exists
             {} otherwise
    """
    if not isinstance(source, dict):
        raise TypeError("source must be of type dict")
    if not isinstance(lpath, list):
        raise TypeError("path must be of type list")
    if not lpath:
        return source

    ret =  _get_sub_dict(source, lpath)

    if get_first_key and lpath and ret:
        tmp = next(iter(ret.values()))
        if not isinstance(tmp, dict):
            raise TypeError("Data under node is not of type dict")
        ret = tmp

    return ret

def process_running(pid_file):
    """ Checks if a process with PID in pid_file is running """
    from psutil import pid_exists
    if not os.path.isfile(pid_file):
        return False
    with open(pid_file, 'r') as f:
        pid = f.read().strip()
    return pid_exists(int(pid))


def process_named_running(name):
    """ Checks if process with given name is running and returns its PID.
    If Process is not running, return None
    """
    from psutil import process_iter
    for p in process_iter():
        if name in p.name():
            return p.pid
    return None


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
    from grp import getgrnam
    from vyos.defaults import cfg_group

    group_data = getgrnam(cfg_group)
    return group_data.gr_gid


def file_is_persistent(path):
    import re
    location = r'^(/config|/opt/vyatta/etc/config)'
    absolute = os.path.abspath(os.path.dirname(path))
    return re.match(location,absolute)


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
    from psutil import process_iter, NoSuchProcess
    from vyos.defaults import commit_lock

    idu = cmd('/usr/bin/id -u')
    if idu != '0':
        raise OSError("This functions needs root permissions to return correct results")

    for proc in process_iter():
        try:
            files = proc.open_files()
            if files:
                for f in files:
                    if f.path == commit_lock:
                        return True
        except NoSuchProcess as err:
            # Process died before we could examine it
            pass
    # Default case
    return False


def wait_for_commit_lock():
    """ Not to be used in normal op mode scripts! """
    from time import sleep
    # Very synchronous approach to multiprocessing
    while commit_in_progress():
        sleep(1)


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

def dict_search(path, my_dict):
    """ Traverse Python dictionary (my_dict) delimited by dot (.).
    Return value of key if found, None otherwise.

    This is faster implementation then jmespath.search('foo.bar', my_dict)"""
    if not isinstance(my_dict, dict) or not path:
        return None

    parts = path.split('.')
    inside = parts[:-1]
    if not inside:
        if path not in my_dict:
            return None
        return my_dict[path]
    c = my_dict
    for p in parts[:-1]:
        c = c.get(p, {})
    return c.get(parts[-1], None)

def get_interface_config(interface):
    """ Returns the used encapsulation protocol for given interface.
        If interface does not exist, None is returned.
    """
    if not os.path.exists(f'/sys/class/net/{interface}'):
        return None
    from json import loads
    tmp = loads(cmd(f'ip -d -j link show {interface}'))[0]
    return tmp

def get_interface_address(interface):
    """ Returns the used encapsulation protocol for given interface.
        If interface does not exist, None is returned.
    """
    if not os.path.exists(f'/sys/class/net/{interface}'):
        return None
    from json import loads
    tmp = loads(cmd(f'ip -d -j addr show {interface}'))[0]
    return tmp

def get_all_vrfs():
    """ Return a dictionary of all system wide known VRF instances """
    from json import loads
    tmp = loads(cmd('ip -j vrf list'))
    # Result is of type [{"name":"red","table":1000},{"name":"blue","table":2000}]
    # so we will re-arrange it to a more nicer representation:
    # {'red': {'table': 1000}, 'blue': {'table': 2000}}
    data = {}
    for entry in tmp:
        name = entry.pop('name')
        data[name] = entry
    return data

def cidr_fit(cidr_a, cidr_b, both_directions = False):
    """
    Does CIDR A fit inside of CIDR B?

    Credit: https://gist.github.com/magnetikonline/686fde8ee0bce4d4930ce8738908a009
    """
    def split_cidr(cidr):
        part_list = cidr.split("/")
        if len(part_list) == 1:
            # if just an IP address, assume /32
            part_list.append("32")

        # return address and prefix size
        return part_list[0].strip(), int(part_list[1])
    def address_to_bits(address):
        # convert each octet of IP address to binary
        bit_list = [bin(int(part)) for part in address.split(".")]

        # join binary parts together
        # note: part[2:] to slice off the leading "0b" from bin() results
        return "".join([part[2:].zfill(8) for part in bit_list])
    def binary_network_prefix(cidr):
        # return CIDR as bits, to the length of the prefix size only (drop the rest)
        address, prefix_size = split_cidr(cidr)
        return address_to_bits(address)[:prefix_size]

    prefix_a = binary_network_prefix(cidr_a)
    prefix_b = binary_network_prefix(cidr_b)
    if both_directions:
        return prefix_a.startswith(prefix_b) or prefix_b.startswith(prefix_a)
    return prefix_a.startswith(prefix_b)
