# Copyright 2023-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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
from vyos.defaults import directories

config_file = os.path.join(directories['config'], 'config.boot')

def read_saved_value(path: list):
    if not isinstance(path, list) or not path:
        return ''
    from vyos.configtree import ConfigTree
    try:
        with open(config_file) as f:
            config_string = f.read()
        ct = ConfigTree(config_string)
    except Exception:
        return ''
    if not ct.exists(path):
        return ''
    res = ct.return_values(path)
    if len(res) == 1:
        return res[0]
    res = ct.list_nodes(path)
    if len(res) == 1:
        return ' '.join(res)
    return res
