# Copyright 2017 VyOS maintainers and contributors <maintainers@vyos.io>
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
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.


import os
import json

import vyos.defaults

version_file = os.path.join(vyos.defaults.directories['data'], 'version.json')
  
def get_version_data(file=version_file):
    with open(file, 'r') as f:
        version_data = json.load(f)
    return version_data

def get_version(file=None):
    version_data = None
    if file:
        version_data = get_version_data(file=file)
    else:
        version_data = get_version_data()
    return version_data["version"]
