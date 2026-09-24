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
