#!/usr/bin/env python3
#
# Copyright (C) 2022-2024 VyOS maintainers and contributors
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

from api.graphql.libs.op_mode import load_op_mode_as_module

def get_system_version() -> dict:
    show_version = load_op_mode_as_module('version.py')
    return show_version.show(raw=True, funny=False)

def get_system_uptime() -> dict:
    show_uptime = load_op_mode_as_module('uptime.py')
    return show_uptime._get_raw_data()

def get_system_ram_usage() -> dict:
    show_ram = load_op_mode_as_module('memory.py')
    return show_ram.show(raw=True)
