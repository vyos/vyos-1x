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
import sys
from datetime import datetime

def message(message, flag='', destination=sys.stdout):
    """
    print a debug message line on stdout if debugging is enabled for the flag
    also log it to a file if the flag 'log' is enabled

    message: the message to print
    flag: which flag must be set for it to print
    destination: which file like object to write to (default: sys.stdout)

    returns if any message was logged or not
    """
    enable = enabled(flag)
    if enable:
        destination.write(_format(flag,message))

    # the log flag is special as it logs all the commands
    # executed to a log
    logfile = _logfile('log', '/tmp/developer-log')
    if not logfile:
        return enable

    try:
        # at boot the file is created as root:vyattacfg
        # at runtime the file is created as user:vyattacfg
        # but the helper scripts are not run as this so it
        # need the default permission to be 666 (an not 660)
        mask = os.umask(0o111)

        with open(logfile, 'a') as f:
            f.write(_timed(_format('log', message)))
    finally:
        os.umask(mask)

    return enable


def enabled(flag):
    """
    a flag can be set by touching the file in /tmp or /config

    The current flags are:
     - developer: the code will drop into PBD on un-handled exception
     - log: the code will log all command to a file
     - ifconfig: when modifying an interface,
       prints command with result and sysfs access on stdout for interface
     - command: print command run with result

    Having the flag setup on the filesystem is required to have
    debuging at boot time, however, setting the flag via environment
    does not require a seek to the filesystem and is more efficient
    it can be done on the shell on via .bashrc for the user

    The function returns an empty string if the flag was not set otherwise
    the function returns either the file or environment name used to set it up
    """

    # this is to force all new flags to be registered here to be
    # documented both here and a reminder to update readthedocs :-)
    if flag not in ['developer', 'log', 'ifconfig', 'command']:
        return ''

    return _fromenv(flag) or _fromfile(flag)


def _timed(message):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return f'{now} {message}'


def _remove_invisible(string):
    for char in ('\0', '\a', '\b', '\f', '\v'):
        string = string.replace(char, '')
    return string


def _format(flag, message):
    """
    format a log message
    """
    message = _remove_invisible(message)
    return f'DEBUG/{flag.upper():<7} {message}\n'


def _fromenv(flag):
    """
    check if debugging is set for this flag via environment

    For a given debug flag named "test"
    The presence of the environment VYOS_TEST_DEBUG (uppercase) enables it

    return empty string if not
    return content of env value it is
    """

    flagname = f'VYOS_{flag.upper()}_DEBUG'
    flagenv = os.environ.get(flagname, None)

    if flagenv is None:
        return ''
    return flagenv


def _fromfile(flag):
    """
    Check if debug exist for a given debug flag name

    Check is a debug flag was set by the user. the flag can be set either:
     - in /tmp for a non-persistent presence between reboot
     - in /config for always on (an existence at boot time)

    For a given debug flag named "test"
    The presence of the file vyos.test.debug (all lowercase) enables it

    The function returns an empty string if the flag was not set otherwise
    the function returns the full flagname
    """

    for folder in ('/tmp', '/config'):
        flagfile = f'{folder}/vyos.{flag}.debug'
        if os.path.isfile(flagfile):
            return flagfile

    return ''


def _contentenv(flag):
    return os.environ.get(f'VYOS_{flag.upper()}_DEBUG', '').strip()


def _contentfile(flag, default=''):
    """
    Check if debug exist for a given debug flag name

    Check is a debug flag was set by the user. the flag can be set either:
     - in /tmp for a non-persistent presence between reboot
     - in /config for always on (an existence at boot time)

    For a given debug flag named "test"
    The presence of the file vyos.test.debug (all lowercase) enables it

    The function returns an empty string if the flag was not set otherwise
    the function returns the full flagname
    """

    for folder in ('/tmp', '/config'):
        flagfile = f'{folder}/vyos.{flag}.debug'
        if not os.path.isfile(flagfile):
            continue
        with open(flagfile) as f:
            content = f.readline().strip()
        return content or default

    return ''


def _logfile(flag, default):
    """
    return the name of the file to use for logging when the flag 'log' is set
    if it could not be established or the location is invalid it returns
    an empty string
    """

    # For log we return the location of the log file
    log_location = _contentenv(flag) or _contentfile(flag, default)

    # it was not set
    if not log_location:
        return ''

    # Make sure that the logs can only be in /tmp, /var/log, or /tmp
    if not log_location.startswith('/tmp/') and \
       not log_location.startswith('/config/') and \
       not log_location.startswith('/var/log/'):
        return default
    # Do not allow to escape the folders
    if '..' in log_location:
        return default

    if not os.path.exists(log_location):
        return log_location

    # this permission is unique the the config and var folder
    stat = os.stat(log_location).st_mode
    if stat != 0o100666:
        return default
    return log_location
