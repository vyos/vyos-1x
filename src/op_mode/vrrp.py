#!/usr/bin/env python3
#
# Copyright (C) 2018-2024 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import json
import sys

import vyos.opmode

from vyos.configquery import ConfigTreeQuery
from vyos.ifconfig.vrrp import VRRP
from vyos.ifconfig.vrrp import VRRPError


def _is_configured():
    """Check if VRRP is configured"""
    return ConfigTreeQuery().exists(['high-availability', 'vrrp', 'group'])

def show(raw: bool):
    if raw:
        return json.loads(VRRP.collect('json'))
    else:
        raise vyos.opmode.UnsupportedOperation\
            ('VRRP show supports only raw output.')

def show_summary(raw: bool) -> str:
    if not raw:
        return VRRP.format(VRRP.collect('json'))
    else:
        raise vyos.opmode.UnsupportedOperation\
            ('VRRP summary does not support raw output.')

def show_statistics(raw: bool) -> str:
    if not raw:
        return VRRP.collect('stats')
    else:
        raise vyos.opmode.UnsupportedOperation\
            ('VRRP statistics does not support raw output.')

def show_state(raw: bool) -> str:
    if not raw:
        return VRRP.collect('state')
    else:
        raise vyos.opmode.UnsupportedOperation\
            ('VRRP detailed state does not support raw output.')


if __name__ == "__main__":
    try:
        if not _is_configured():
            raise vyos.opmode.UnconfiguredSubsystem('VRRP is not configured.')
        if not VRRP.is_running():
            raise vyos.opmode.UnconfiguredSubsystem('VRRP is not running.')
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (vyos.opmode.Error, VRRPError) as e:
        print(e, file=sys.stdout)
        sys.exit(1)
