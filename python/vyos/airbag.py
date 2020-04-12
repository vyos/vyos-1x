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

import os
import sys
import logging
import logging.handlers
from datetime import datetime

from vyos import debug
from vyos.config import Config
from vyos.version import get_version
from vyos.util import run


# we allow to disable the extra logging
DISABLE = False


# emulate a file object
class _IO(object):
    def __init__(self, std, log):
        self.std = std
        self.log = log

    def write(self, message):
        self.std.write(message)
        if DISABLE:
            return
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

    information = {
        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'version': get_version(),
        'trace': format_exception(dtype, value, trace),
        'instructions': COMMUNITY if 'rolling' in get_version() else SUPPORTED,
    }

    sys.stdout.write(INTRO.format(**information))
    sys.stdout.flush()

    sys.stderr.write(FAULT.format(**information))
    sys.stderr.flush()


# define an exception handler to be run when an exception
# reach the end of __main__ and was not intercepted
def intercepter(dtype, value, trace):
    bug_report(dtype, value, trace)
    if debug.enabled('developer'):
        import pdb
        pdb.pm()


def InterceptingLogger(address, _singleton=[False]):
    skip = _singleton.pop()
    _singleton.append(True)
    if skip:
        return

    logger = logging.getLogger('VyOS')
    logger.setLevel(logging.DEBUG)
    handler = logging.handlers.SysLogHandler(address='/dev/log', facility='syslog')
    logger.addHandler(handler)

    # log to syslog any message sent to stderr
    sys.stderr = _IO(sys.stderr, logger.critical)


# lists as default arguments in function is normally dangerous
# as they will keep any modification performed, unless this is
# what you want to do (in that case to only run the code once)
def InterceptingException(excepthook,_singleton=[False]):
    skip = _singleton.pop()
    _singleton.append(True)
    if skip:
        return

    # install the handler to replace the default behaviour
    # which just prints the exception trace on screen
    sys.excepthook = excepthook


# Do not attempt the extra logging for operational commands
try:
    # This fails during boot
    insession = Config().in_session()
except:
    # we save info on boot to help debugging
    insession = True


# Installing the interception, it currently does not work when
# running testing so we are checking that we are on the router
# as otherwise it prevents dpkg-buildpackage to work
if get_version() and insession:
    InterceptingLogger('/run/systemd/journal/dev-log')
    InterceptingException(intercepter)


# Messages to print

FAULT = """\
Date:       {date}
VyOS image: {version}

{trace}
"""

INTRO = """\
VyOS had an issue completing a command.

We are sorry that you encountered a problem with VyOS.
There are a few things you can do to help us (and yourself):
{instructions}

PLEASE, when reporting, do include as much information as you can:
- do not obfuscate any data (feel free to send us a private communication with
  the extra information if your business policy is strict on information sharing)
- and include all the information presented below

"""

COMMUNITY = """\
- Make sure you are running the latest version of the code available at
  https://downloads.vyos.io/rolling/current/amd64/vyos-rolling-latest.iso
- Consult the forum to see how to handle this issue
  https://forum.vyos.io
- Join our community on slack where our users exchange help and advice
  https://vyos.slack.com
""".strip()

SUPPORTED = """\
- Make sure you are running the latest stable version of VyOS
  the code is available at https://downloads.vyos.io/?dir=release/current
- Contact us on our online help desk
  https://support.vyos.io/
""".strip()
