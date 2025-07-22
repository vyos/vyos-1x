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
#
#

# N.B. only for use within testing framework; explicit invocation will leave
# system in inconsistent state.

import os
import sys
from argparse import ArgumentParser

from vyos.utils.backend import set_vyconf_backend

if os.getuid() != 0:
    sys.exit('Requires root privileges')

parser = ArgumentParser()
parser.add_argument('--disable', action='store_true',
                    help='enable/disable vyconf backend')
parser.add_argument('--no-prompt', action='store_true',
                    help='confirm without prompt')

args = parser.parse_args()

match args.disable:
    case False:
        set_vyconf_backend(True, no_prompt=args.no_prompt)
    case True:
        set_vyconf_backend(False, no_prompt=args.no_prompt)
