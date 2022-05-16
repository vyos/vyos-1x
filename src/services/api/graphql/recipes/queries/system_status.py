#!/usr/bin/env python3
#
# Copyright (C) 2022 VyOS maintainers and contributors
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
import json
import importlib.util

from vyos.defaults import directories

OP_PATH = directories['op_mode']

def load_as_module(name: str):
    path = os.path.join(OP_PATH, name)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def get_system_version() -> dict:
    show_version = load_as_module('show_version.py')
    return show_version.get_raw_data()

def get_system_uptime() -> dict:
    show_uptime = load_as_module('show_uptime.py')
    return show_uptime.get_raw_data()

def get_system_ram_usage() -> dict:
    show_ram = load_as_module('show_ram.py')
    return show_ram.get_raw_data()
