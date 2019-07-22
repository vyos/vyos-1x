#!/usr/bin/python3

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
# You should have received a copy of the GNU Lesser General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>.

import sys
import vyos.formatversions as formatversions
import vyos.systemversions as systemversions
import vyos.defaults
import vyos.version

sys_versions = systemversions.get_system_versions()

component_string = formatversions.format_versions_string(sys_versions)

os_version_string = vyos.version.get_version()

sys.stdout.write("\n\n")
if vyos.defaults.cfg_vintage == 'vyos':
    formatversions.write_vyos_versions_foot(None, component_string,
                                            os_version_string)
elif vyos.defaults.cfg_vintage == 'vyatta':
    formatversions.write_vyatta_versions_foot(None, component_string,
                                              os_version_string)
else:
    formatversions.write_vyatta_versions_foot(None, component_string,
                                              os_version_string)
