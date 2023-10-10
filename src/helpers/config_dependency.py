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
import sys
import json
from argparse import ArgumentParser
from argparse import ArgumentTypeError
from graphlib import TopologicalSorter, CycleError

# addon packages will need to specify the dependency directory
data_dir = '/usr/share/vyos/'
dependency_dir = os.path.join(data_dir, 'config-mode-dependencies')

def dict_merge(source, destination):
    from copy import deepcopy
    tmp = deepcopy(destination)

    for key, value in source.items():
        if key not in tmp:
            tmp[key] = value
        elif isinstance(source[key], dict):
            tmp[key] = dict_merge(source[key], tmp[key])

    return tmp

def read_dependency_dict(dependency_dir: str = dependency_dir) -> dict:
    res = {}
    for dep_file in os.listdir(dependency_dir):
        if not dep_file.endswith('.json'):
            continue
        path = os.path.join(dependency_dir, dep_file)
        with open(path) as f:
            d = json.load(f)
        if dep_file == 'vyos-1x.json':
            res = dict_merge(res, d)
        else:
            res = dict_merge(d, res)

    return res

def graph_from_dependency_dict(d: dict) -> dict:
    g = {}
    for k in list(d):
        g[k] = set()
        # add the dependencies for every sub-case; should there be cases
        # that are mutally exclusive in the future, the graphs will be
        # distinguished
        for el in list(d[k]):
            g[k] |= set(d[k][el])

    return g

def is_acyclic(d: dict) -> bool:
    g = graph_from_dependency_dict(d)
    ts = TopologicalSorter(g)
    try:
        # get node iterator
        order = ts.static_order()
        # try iteration
        _ = [*order]
    except CycleError:
        return False

    return True

def check_dependency_graph(dependency_dir: str = dependency_dir,
                           supplement: str = None) -> bool:
    d = read_dependency_dict(dependency_dir=dependency_dir)
    if supplement is not None:
        with open(supplement) as f:
            d = dict_merge(json.load(f), d)

    return is_acyclic(d)

def path_exists(s):
    if not os.path.exists(s):
        raise ArgumentTypeError("Must specify a valid vyos-1x dependency directory")
    return s

def main():
    parser = ArgumentParser(description='generate and save dict from xml defintions')
    parser.add_argument('--dependency-dir', type=path_exists,
                        default=dependency_dir,
                        help='location of vyos-1x dependency directory')
    parser.add_argument('--supplement', type=str,
                        help='supplemental dependency file')
    args = vars(parser.parse_args())

    if not check_dependency_graph(**args):
        print("dependency error: cycle exists")
        sys.exit(1)

    print("dependency graph acyclic")
    sys.exit(0)

if __name__ == '__main__':
    main()
