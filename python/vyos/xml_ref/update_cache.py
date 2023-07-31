#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
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
from copy import deepcopy
from generate_cache import pkg_cache
from generate_cache import ref_cache

def dict_merge(source, destination):
    dest = deepcopy(destination)

    for key, value in source.items():
        if key not in dest:
            dest[key] = value
        elif isinstance(source[key], dict):
            dest[key] = dict_merge(source[key], dest[key])

    return dest

def main():
    res = {}
    cache_dir = os.path.basename(pkg_cache)
    for mod in os.listdir(pkg_cache):
        mod = os.path.splitext(mod)[0]
        if not mod.endswith('_cache'):
            continue
        d = getattr(__import__(f'{cache_dir}.{mod}', fromlist=[mod]), 'reference')
        if mod == 'vyos_1x_cache':
            res = dict_merge(res, d)
        else:
            res = dict_merge(d, res)

    with open(ref_cache, 'w') as f:
        f.write(f'reference = {str(res)}')

if __name__ == '__main__':
    main()
