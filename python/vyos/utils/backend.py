# Copyright 2025 VyOS maintainers and contributors <maintainers@vyos.io>
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
# You should have received a copy of the GNU Lesser General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>.

# N.B. the following is a temporary addition for running smoketests under
# vyconf and is not to be called explicitly, at the risk of catastophe.

# pylint: disable=wrong-import-position

from pathlib import Path

from vyos.utils.io import ask_yes_no
from vyos.utils.process import call

VYCONF_SENTINEL = '/run/vyconf_backend'

MSG_ENABLE_VYCONF = 'This will enable the vyconf backend for testing. Proceed?'
MSG_DISABLE_VYCONF = (
    'This will restore the legacy backend; it requires a reboot. Proceed?'
)

# read/set immutable file attribute without popen:
# https://www.geeklab.info/2021/04/chattr-and-lsattr-in-python/
import fcntl  # pylint: disable=C0411 # noqa: E402
from array import array  # pylint: disable=C0411 # noqa: E402

# FS constants - see /uapi/linux/fs.h in kernel source
# or <elixir.free-electrons.com/linux/latest/source/include/uapi/linux/fs.h>
FS_IOC_GETFLAGS = 0x80086601
FS_IOC_SETFLAGS = 0x40086602
FS_IMMUTABLE_FL = 0x010


def chattri(filename: str, value: bool):
    with open(filename, 'r') as f:
        arg = array('L', [0])
        fcntl.ioctl(f.fileno(), FS_IOC_GETFLAGS, arg, True)
        if value:
            arg[0] = arg[0] | FS_IMMUTABLE_FL
        else:
            arg[0] = arg[0] & ~FS_IMMUTABLE_FL
        fcntl.ioctl(f.fileno(), FS_IOC_SETFLAGS, arg, True)


def lsattri(filename: str) -> bool:
    with open(filename, 'r') as f:
        arg = array('L', [0])
        fcntl.ioctl(f.fileno(), FS_IOC_GETFLAGS, arg, True)
    return bool(arg[0] & FS_IMMUTABLE_FL)


# End: read/set immutable file attribute without popen


def vyconf_backend() -> bool:
    return Path(VYCONF_SENTINEL).exists() and lsattri(VYCONF_SENTINEL)


def set_vyconf_backend(value: bool, no_prompt: bool = False):
    vyconfd_service = 'vyconfd.service'
    match value:
        case True:
            if vyconf_backend():
                return
            if not no_prompt and not ask_yes_no(MSG_ENABLE_VYCONF):
                return
            Path(VYCONF_SENTINEL).touch()
            chattri(VYCONF_SENTINEL, True)
            call(f'systemctl restart {vyconfd_service}')
        case False:
            if not vyconf_backend():
                return
            if not no_prompt and not ask_yes_no(MSG_DISABLE_VYCONF):
                return
            chattri(VYCONF_SENTINEL, False)
            Path(VYCONF_SENTINEL).unlink()
            call('/sbin/shutdown -r now')
