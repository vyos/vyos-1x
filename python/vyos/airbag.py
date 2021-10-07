# Copyright 2019-2020 VyOS maintainers and contributors <maintainers@vyos.io>
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

import sys
from datetime import datetime

from vyos import debug
from vyos.logger import syslog
from vyos.version import get_full_version_data


def enable(log=True):
    if log:
        _intercepting_logger()
    _intercepting_exceptions()


_noteworthy = []


def noteworthy(msg):
    """
    noteworthy can be use to take note things which we may not want to
    report to the user may but be worth including in bug report
    if something goes wrong later on
    """
    _noteworthy.append(msg)


# emulate a file object
class _IO(object):
    def __init__(self, std, log):
        self.std = std
        self.log = log

    def write(self, message):
        self.std.write(message)
        for line in message.split('\n'):
            s = line.rstrip()
            if s:
                self.log(s)

    def flush(self):
        self.std.flush()

    def close(self):
        pass


# The function which will be used to report information
# to users when an exception is unhandled
def bug_report(dtype, value, trace):
    from traceback import format_exception

    sys.stdout.flush()
    sys.stderr.flush()

    information = get_full_version_data()
    trace = '\n'.join(format_exception(dtype, value, trace)).replace('\n\n','\n')
    note = ''
    if _noteworthy:
        note = 'noteworthy:\n'
        note += '\n'.join(_noteworthy)

    information.update({
        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'trace': trace,
        'instructions': INSTRUCTIONS,
        'note': note,
    })

    sys.stdout.write(INTRO.format(**information))
    sys.stdout.flush()

    sys.stderr.write(FAULT.format(**information))
    sys.stderr.flush()


# define an exception handler to be run when an exception
# reach the end of __main__ and was not intercepted
def _intercepter(dtype, value, trace):
    bug_report(dtype, value, trace)
    if debug.enabled('developer'):
        import pdb
        pdb.pm()


def _intercepting_logger(_singleton=[False]):
    skip = _singleton.pop()
    _singleton.append(True)
    if skip:
        return

    # log to syslog any message sent to stderr
    sys.stderr = _IO(sys.stderr, syslog.critical)


# lists as default arguments in function is normally dangerous
# as they will keep any modification performed, unless this is
# what you want to do (in that case to only run the code once)
def _intercepting_exceptions(_singleton=[False]):
    skip = _singleton.pop()
    _singleton.append(True)
    if skip:
        return

    # install the handler to replace the default behaviour
    # which just prints the exception trace on screen
    sys.excepthook = _intercepter


# Messages to print
# if the key before the value has not time, syslog takes that as the source of the message

FAULT = """\
Report time:      {date}
Image version:    VyOS {version}
Release train:    {release_train}

Built by:         {built_by}
Built on:         {built_on}
Build UUID:       {build_uuid}
Build commit ID:  {build_git}

Architecture:     {system_arch}
Boot via:         {boot_via}
System type:      {system_type}

Hardware vendor:  {hardware_vendor}
Hardware model:   {hardware_model}
Hardware S/N:     {hardware_serial}
Hardware UUID:    {hardware_uuid}

{trace}
{note}
"""

INTRO = """\
VyOS had an issue completing a command.

We are sorry that you encountered a problem while using VyOS.
There are a few things you can do to help us (and yourself):
{instructions}

When reporting problems, please include as much information as possible:
- do not obfuscate any data (feel free to contact us privately if your 
  business policy requires it)
- and include all the information presented below

"""

INSTRUCTIONS = """\
- Contact us using the online help desk if you have a subscription:
  https://support.vyos.io/
- Make sure you are running the latest version of VyOS available at:
  https://vyos.net/get/
- Consult the community forum to see how to handle this issue:
  https://forum.vyos.io
- Join us on Slack where our users exchange help and advice:
  https://vyos.slack.com
""".strip()
