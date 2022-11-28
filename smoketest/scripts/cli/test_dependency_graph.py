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

import json
import unittest
from graphlib import TopologicalSorter, CycleError

DEP_FILE = '/usr/share/vyos/config-mode-dependencies.json'

def graph_from_dict(d):
    g = {}
    for k in list(d):
        g[k] = set()
        # add the dependencies for every sub-case; should there be cases
        # that are mutally exclusive in the future, the graphs will be
        # distinguished
        for el in list(d[k]):
            g[k] |= set(d[k][el])
    return g

class TestDependencyGraph(unittest.TestCase):
    def setUp(self):
        with open(DEP_FILE) as f:
            dd = json.load(f)
            self.dependency_graph = graph_from_dict(dd)

    def test_cycles(self):
        ts = TopologicalSorter(self.dependency_graph)
        out = None
        try:
            # get node iterator
            order = ts.static_order()
            # try iteration
            _ = [*order]
        except CycleError as e:
            out = e.args

        self.assertIsNone(out)

if __name__ == '__main__':
    unittest.main(verbosity=2)
