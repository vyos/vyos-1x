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
import sys
from subprocess import Popen
from subprocess import PIPE
from subprocess import STDOUT
from subprocess import DEVNULL


def debug(flag):
    """
    Check is a debug flag was set by the user. 
    a flag can be set by touching the file /tmp/vyos.flag.debug
    with flag being the flag name, the current flags are:
     - developer: the code will drop into PBD on un-handled exception
     - ifconfig: prints command and sysfs access on stdout for interface
    The function returns an empty string if the flag was not set,
    """

    # this is to force all new flags to be registered here to be documented:
    if flag not in ['developer', 'ifconfig']:
        return ''
    return flag if os.path.isfile(f'/tmp/vyos.{flag}.debug') else ''


def debug_msg(message, flag=''):
    """
    print a debug message line on stdout if debugging is enabled for the flag
    """

    if debug(flag):
        print(f'DEBUG/{flag:<6} {message}')


# There is many (too many) ways to run command with python
# os.system, subprocess.Popen, subproces.{run,call,check_output}
# which all have slighty different behaviour


def popen(command, flag='', shell=None, input=None, timeout=None, env=None,
          stdout=PIPE, stderr=None, decode=None):
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

    usage:
    to get both stdout, and stderr: popen('command', stdout=PIPE, stderr=STDOUT)
    to discard stdout and get stderr: popen('command', stdout=DEVNUL, stderr=PIPE)
    """
    debug_msg(f"cmd '{command}'", flag)
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
    p = Popen(
        command,
        stdin=stdin, stdout=stdout, stderr=stderr,
        env=env, shell=use_shell,
    )
    tmp = p.communicate(input, timeout)
    out1 = b''
    out2 = b''
    if stdout == PIPE:
        out1 = tmp[0]
    if stderr == PIPE:
        out2 += tmp[1]
    decoded1 = out1.decode(decode) if decode else out1.decode()
    decoded2 = out2.decode(decode) if decode else out2.decode()
    decoded1 = decoded1.replace('\r\n', '\n').strip()
    decoded2 = decoded2.replace('\r\n', '\n').strip()
    nl = '\n' if decoded1 and decoded2 else ''
    decoded = decoded1 + nl + decoded2
    if decoded:
        debug_msg(f"returned:\n{decoded}", flag)
    return decoded, p.returncode


def run(command, flag='', shell=None, input=None, timeout=None, env=None,
        stdout=DEVNULL, stderr=None, decode=None):
    """
    A wrapper around vyos.util.popen, which discard the stdout and
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
        stdout=PIPE, stderr=None, decode=None,
        raising=None, message=''):
    """
    A wrapper around vyos.util.popen, which returns the stdout and
    will raise the error code of a command

    raising: specify which call should be used when raising (default is OSError)
             the class should only require a string as parameter
    """
    decoded, code = popen(
        command, flag,
        stdout=stdout, stderr=stderr,
        input=input, timeout=timeout,
        env=env, shell=shell,
        decode=decode,
    )
    if code != 0:
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
         stdout=PIPE, stderr=None, decode=None):
    """
    A wrapper around vyos.util.popen, which print the stdout and
    will return the error code of a command
    """
    out, code = popen(
        command, flag,
        stdout=stdout, stderr=stderr,
        input=input, timeout=timeout,
        env=env, shell=shell,
        decode=decode,
    )
    print(out)
    return code


def read_file(path):
    """ Read a file to string """
    with open(path, 'r') as f:
        data = f.read().strip()
    return data


def chown(path, user, group):
    """ change file/directory owner """
    from pwd import getpwnam
    from grp import getgrnam

    if os.path.exists(path):
        uid = getpwnam(user).pw_uid
        gid = getgrnam(group).gr_gid
        os.chown(path, uid, gid)

def chmod_750(path):
    """ make file/directory only executable to user and group """
    from stat import S_IRUSR, S_IWUSR, S_IXUSR, S_IRGRP, S_IXGRP

    if os.path.exists(path):
        bitmask = S_IRUSR | S_IWUSR | S_IXUSR | S_IRGRP | S_IXGRP
        os.chmod(path, bitmask)


def chmod_x(path):
    """ make file executable """
    from stat import S_IRUSR, S_IWUSR, S_IXUSR, S_IRGRP, S_IXGRP, S_IROTH, S_IXOTH

    if os.path.exists(path):
        bitmask = S_IRUSR | S_IWUSR | S_IXUSR | S_IRGRP | S_IXGRP | \
                  S_IROTH | S_IXOTH
        os.chmod(path, bitmask)


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
    from psutil import pid_exists
    if not os.path.isfile(pid_file):
        return False
    with open(pid_file, 'r') as f:
        pid = f.read().strip()
    return pid_exists(int(pid))


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

def is_bridge_member(interface):
    """
    Checks if passed interfaces is part of a bridge device or not.

    Returns a tuple:
    False, None -> Not part of a bridge
    True, bridge-name -> If it is assigned to a bridge
    """
    from vyos.config import Config
    c = Config()
    base = ['interfaces', 'bridge']
    for bridge in c.list_nodes(base):
        members = c.list_nodes(base + [bridge, 'member', 'interface'])
        if interface in members:
            return (True, bridge)

    return False, None

