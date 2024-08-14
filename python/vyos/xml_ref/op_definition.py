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

from typing import TypedDict
from typing import TypeAlias
from typing import Optional
from typing import Union


class NodeData(TypedDict):
    node_type: Optional[str]
    help_text: Optional[str]
    comp_help: Optional[dict[str, list]]
    command: Optional[str]
    path: Optional[list[str]]


PathData: TypeAlias = dict[str, Union[NodeData|list['PathData']]]


class OpXml:
    def __init__(self):
        self.op_ref = {}

    def define(self, op_ref: list[PathData]) -> None:
        self.op_ref = op_ref

    def _get_op_ref_path(self, path: list[str]) -> list[PathData]:
        def _get_path_list(path: list[str], l: list[PathData]) -> list[PathData]:
            if not path:
                return l
            for d in l:
                if path[0] in list(d):
                    return _get_path_list(path[1:], d[path[0]])
            return []
        l = self.op_ref
        return _get_path_list(path, l)
