#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
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

from vyos.configquery import VbashOpRun
from vyos.configquery import ConfigTreeQuery

from vyos.utils.network import is_wwan_connected

conf = ConfigTreeQuery()
dict = conf.get_config_dict(['interfaces', 'wwan'], key_mangling=('-', '_'),
                            get_first_key=True)

for interface, interface_config in dict.items():
    if not is_wwan_connected(interface):
        if 'disable' in interface_config:
            # do not restart this interface as it's disabled by the user
            continue

        op = VbashOpRun()
        op.run(['connect', 'interface', interface])

exit(0)
