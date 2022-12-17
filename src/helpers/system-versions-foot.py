#!/usr/bin/python3

# Copyright 2019, 2022 VyOS maintainers and contributors <maintainers@vyos.io>
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

import sys
import vyos.defaults
from vyos.component_version import write_system_footer

sys.stdout.write("\n\n")
if vyos.defaults.cfg_vintage == 'vyos':
    write_system_footer(None, vintage='vyos')
elif vyos.defaults.cfg_vintage == 'vyatta':
    write_system_footer(None, vintage='vyatta')
else:
    write_system_footer(None, vintage='vyos')
