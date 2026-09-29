#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Render the FRR configuration and reload FRR without vyos-configd.

Only vyos-configd renders FRR, and only at the end of a commit it handled
itself. Two paths need a render without it: a DHCP lease event, which changes
the rendered configuration without any CLI change, and a commit which fell back
to running the conf-mode scripts directly.

Instances are serialized by a lock file. Use "--if-idle" for the lease event
case, where a commit may win the race - it renders FRR from the current lease
itself."""

import argparse
import fcntl
import os
import sys

from vyos.config import Config
from vyos.frrender import FRRender
from vyos.frrender import frr_config_file
from vyos.frrender import get_frrender_dict
from vyos.utils.commit import commit_in_progress
from vyos.utils.commit import wait_for_commit_lock
from vyos.utils.file import read_file
from vyos import ConfigError

LOCK_FILE = '/run/vyos-frr-render.lock'


def render(if_idle: bool = False) -> None:
    """Reload FRR if the rendered configuration changed.

    A fresh instance has no cached configuration, thus its own change detection
    can not be used here - compare the rendered file instead."""
    if if_idle and commit_in_progress():
        return

    previous = read_file(frr_config_file) if os.path.exists(frr_config_file) else None

    frr = FRRender()
    frr.generate(get_frrender_dict(Config()))

    if read_file(frr_config_file) == previous:
        return

    # A commit which started in the meantime renders FRR itself - never run
    # two reloads at once
    if if_idle and commit_in_progress():
        return

    frr.apply()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--if-idle', action='store_true', help='skip the render while a commit is in progress')
    args = parser.parse_args()

    # A burst of lease events must not result in concurrent renders
    with open(LOCK_FILE, 'w') as lock_file:
        fcntl.lockf(lock_file, fcntl.LOCK_EX)

        if args.if_idle:
            wait_for_commit_lock()

        try:
            render(if_idle=args.if_idle)
        except ConfigError as e:
            print(e)
            sys.exit(1)
