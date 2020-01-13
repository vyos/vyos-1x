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

import os
import re
import sys
import json

import vyos.defaults

def get_system_versions():
    """
    Get component versions from running system: read vyatta directory
    structure for versions, then read vyos JSON file. It is a critical
    error if either migration directory or JSON file is unreadable.
    """
    system_versions = {}

    try:
        version_info = os.listdir(vyos.defaults.directories['current'])
    except OSError as err:
        print("OS error: {}".format(err))
        sys.exit(1)

    for info in version_info:
        if re.match(r'[\w,-]+@\d+', info):
            pair = info.split('@')
            system_versions[pair[0]] = int(pair[1])

    version_dict = {}
    path = vyos.defaults.version_file

    if os.path.isfile(path):
        with open(path, 'r') as f:
            try:
                version_dict = json.load(f)
            except ValueError as err:
                print(f"\nValue error in {path}: {err}")
                sys.exit(1)

        for k, v in version_dict.items():
            if not isinstance(v, int):
                print(f"\nType error in {path}; expecting Dict[str, int]")
                sys.exit(1)
            existing = system_versions.get(k)
            if existing is None:
                system_versions[k] = v
            elif v > existing:
                system_versions[k] = v

    return system_versions
