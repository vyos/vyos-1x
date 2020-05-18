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
from vyos.command import cmd

#
# NOTE: Do not import full classes here, move your import to the function
# where it is used so it is as local as possible to the execution
#


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

    if not os.path.exists(path):
        return False
	
    uid = getpwnam(user).pw_uid
    gid = getgrnam(group).gr_gid
    os.chown(path, uid, gid)
    return True


def chmod(path, bitmask):
    if not os.path.exists(path):
        return
    if bitmask is None:
        return
    os.chmod(path, bitmask)


def chmod_600(path):
    """ make file only read/writable by owner """
    from stat import S_IRUSR, S_IWUSR

    if os.path.exists(path):
        bitmask = S_IRUSR | S_IWUSR
        os.chmod(path, bitmask)


def chmod_750(path):
    """ make file/directory only executable to user and group """
    from stat import S_IRUSR, S_IWUSR, S_IXUSR, S_IRGRP, S_IXGRP

    if os.path.exists(path):
        bitmask = S_IRUSR | S_IWUSR | S_IXUSR | S_IRGRP | S_IXGRP
        os.chmod(path, bitmask)


def chmod_755(path):
    """ make file executable by all """
    from stat import S_IRUSR, S_IWUSR, S_IXUSR, S_IRGRP, S_IXGRP, S_IROTH, S_IXOTH

    if os.path.exists(path):
        bitmask = S_IRUSR | S_IWUSR | S_IXUSR | S_IRGRP | S_IXGRP | \
                  S_IROTH | S_IXOTH
        os.chmod(path, bitmask)


def makedir(path, user=None, group=None):
    if os.path.exists(path):
        return
    os.mkdir(path)
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

def ifname_from_config(conf):
    """
    Gets interface name with VLANs from current config level.
    Level must be at the interface whose name we want.

    Example:
    >>> from vyos.util import ifname_from_config
    >>> from vyos.config import Config
    >>> conf = Config()
    >>> conf.set_level('interfaces ethernet eth0 vif-s 1 vif-c 2')
    >>> ifname_from_config(conf)
    'eth0.1.2'
    """
    level = conf.get_level()

    # vlans
    if level[-2] == 'vif' or level[-2] == 'vif-s':
        return level[-3] + '.' + level[-1]
    if level[-2] == 'vif-c':
        return level[-5] + '.' + level[-3] + '.' + level[-1]

    # no vlans
    return level[-1]

def get_bridge_member_config(conf, br, intf):
    """
    Gets bridge port (member) configuration

    Arguments:
    conf: Config
    br: bridge name
    intf: interface name

    Returns:
    dict with the configuration
    False if bridge or bridge port doesn't exist
    """
    old_level = conf.get_level()
    conf.set_level([])

    bridge = f'interfaces bridge {br}'
    member = f'{bridge} member interface {intf}'
    if not ( conf.exists(bridge) and conf.exists(member) ):
        return False

    # default bridge port configuration
    # cost and priority initialized with linux defaults
    # by reading /sys/devices/virtual/net/br0/brif/eth2/{path_cost,priority}
    # after adding interface to bridge after reboot
    memberconf = {
        'cost': 100,
        'priority': 32,
        'arp_cache_tmo': 30,
        'disable_link_detect': 1,
    }

    if conf.exists(f'{member} cost'):
        memberconf['cost'] = int(conf.return_value(f'{member} cost'))

    if conf.exists(f'{member} priority'):
        memberconf['priority'] = int(conf.return_value(f'{member} priority'))

    if conf.exists(f'{bridge} ip arp-cache-timeout'):
        memberconf['arp_cache_tmo'] = int(conf.return_value(f'{bridge} ip arp-cache-timeout'))

    if conf.exists(f'{bridge} disable-link-detect'):
        memberconf['disable_link_detect'] = 2

    conf.set_level(old_level)
    return memberconf
