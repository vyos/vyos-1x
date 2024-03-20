# Copyright 2024 VyOS maintainers and contributors <maintainers@vyos.io>
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

from pathlib import Path
from typing import List

from vyos.xml_ref import load_reference
from vyos.base import Warning as Warn

def priority_data(d: dict) -> list:
    def func(d, path, res, hier):
        for k,v in d.items():
            if not 'node_data' in v:
                continue
            subpath = path + [k]
            hier_prio = hier
            data = v.get('node_data')
            o = data.get('owner')
            p = data.get('priority')
            # a few interface-definitions have priority preceding owner
            # attribute, instead of within properties; pass in descent
            if p is not None and o is None:
                hier_prio = p
            if o is not None and p is None:
                p = hier_prio
            if o is not None and p is not None:
                o = Path(o.split()[0]).name
                p = int(p)
                res.append((subpath, o, p))
            if isinstance(v, dict):
                func(v, subpath, res, hier_prio)
        return res
    ret = func(d, [], [], 0)
    ret = sorted(ret, key=lambda x: x[0])
    ret = sorted(ret, key=lambda x: x[2])
    return ret

def get_priority_data() -> list:
    xml = load_reference()
    return priority_data(xml.ref)

def priority_sort(sections: List[list[str]] = None,
                  owners: List[str] = None,
                  reverse=False) -> List:
    if sections is not None:
        index = 0
        collection: List = sections
    elif owners is not None:
        index = 1
        collection = owners
    else:
        raise ValueError('one of sections or owners is required')

    l = get_priority_data()
    m = [item for item in l if item[index] in collection]
    n = sorted(m, key=lambda x: x[2], reverse=reverse)
    o = [item[index] for item in n]
    # sections are unhashable; use comprehension
    missed = [j for j in collection if j not in o]
    if missed:
        Warn(f'No priority available for elements {missed}')

    return o
