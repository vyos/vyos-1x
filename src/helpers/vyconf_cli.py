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

import os
import sys

from vyos.vyconf_session import VyconfSession


pid = os.getppid()

vs = VyconfSession(pid=pid)

script_path = sys.argv[0]
script_name = os.path.basename(script_path)
# drop prefix 'vy_' if present
if script_name.startswith('vy_'):
    func_name = script_name[3:]
else:
    func_name = script_name

if hasattr(vs, func_name):
    func = getattr(vs, func_name)
else:
    sys.exit(f'Call unimplemented: {func_name}')

res = func()
if isinstance(res, bool):
    # for use in shell scripts
    sys.exit(int(not res))

if isinstance(res, tuple):
    out, err = res
    print(out)
    sys.exit(err)
