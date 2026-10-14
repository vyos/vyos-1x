# Copyright (C) VyOS Inc.
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


from vyos.configtree import ConfigTree  # noqa: I001
from vyos.configtree import DiffTree
from vyos.configtree import subtree_values_of_path
from vyos.referencetree import ReferenceTree
from vyos.base import Warning as Warn


def removed_dependency_value_paths_of_kind(
    kind: str,
    reference_tree: ReferenceTree,
    session_tree: ConfigTree,
    diff_tree: DiffTree,
):
    paths = reference_tree.get_nodes_of_kind(kind)
    value_paths = []
    for path in paths:
        path_vals = subtree_values_of_path(diff_tree.sub, path, reference_tree)
        path_vals = [t for t in path_vals if t != ([], [])]
        for vlst, p in path_vals:
            vals = list(
                filter(
                    lambda v, cur_p=p: not session_tree.exists(cur_p + [v]),
                    vlst,
                )
            )
            if vals:
                value_paths.append((vals, p))

    return value_paths


def dependent_value_paths_of_kind(
    kind: str,
    reference_tree: ReferenceTree,
    session_tree: ConfigTree,
):
    dependent_data = reference_tree.get_rdeps_of_kind_data(kind)

    dependent_value_paths = {}
    for p, a in dependent_data:
        path_vals = subtree_values_of_path(session_tree, p, reference_tree)
        path_vals = [t for t in path_vals if t != ([], [])]
        if path_vals:
            lst = dependent_value_paths.setdefault(a, [])
            lst.extend(path_vals)

    return dependent_value_paths


vif_refpath = [
    ['interfaces', 'ethernet', 'vif'],
    ['interfaces', 'ethernet', 'vif-s'],
    ['interfaces', 'ethernet', 'vif-s', 'vif-c'],
    ['interfaces', 'bonding', 'vif'],
    ['interfaces', 'bonding', 'vif-s'],
    ['interfaces', 'bonding', 'vif-s', 'vif-c'],
    ['interfaces', 'bridge', 'vif'],
    ['interfaces', 'pseudo-ethernet', 'vif'],
    ['interfaces', 'pseudo-ethernet', 'vif-s'],
    ['interfaces', 'pseudo-ethernet', 'vif-s', 'vif-c'],
    ['interfaces', 'virtual-ethernet', 'vif'],
    ['interfaces', 'virtual-ethernet', 'vif-s'],
    ['interfaces', 'virtual-ethernet', 'vif-s', 'vif-c'],
    ['interfaces', 'wireless', 'vif'],
    ['interfaces', 'wireless', 'vif-s'],
    ['interfaces', 'wireless', 'vif-s', 'vif-c'],
]


def check_vif_path(reference_tree: ReferenceTree):
    for p in vif_refpath:
        if not reference_tree.exists(p):
            Warn(f'Out of date reference path: {p}')


def concatenate_vif(reference_tree: ReferenceTree, value_paths):
    check_vif_path(reference_tree)
    revised = []
    orig_value = {}
    for vp in value_paths:
        refpath = reference_tree.reference_path_from_config_path(vp[1])
        if refpath not in vif_refpath:
            revised.append(vp)
        else:
            p = vp[1]
            match p[-1]:
                case 'vif':
                    rev_vals = [p[2] + '.' + v for v in vp[0]]
                    orig_value |= dict(zip(rev_vals, vp[0]))
                    revised.append((rev_vals, vp[1]))
                case 'vif-s':
                    rev_vals = [p[2] + '.' + v for v in vp[0]]
                    orig_value |= dict(zip(rev_vals, vp[0]))
                    revised.append((rev_vals, vp[1]))
                case 'vif-c':
                    rev_vals = [p[2] + '.' + p[4] + '.' + v for v in vp[0]]
                    orig_value |= dict(zip(rev_vals, vp[0]))
                    revised.append((rev_vals, vp[1]))
    return revised, orig_value
