# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

def is_list_equal(first: list, second: list) -> bool:
    """ Check if 2 lists are equal and list not empty """
    if len(first) != len(second) or len(first) == 0:
        return False
    return sorted(first) == sorted(second)


def list_strip(lst: list, sub: list, right: bool = False) -> list:
    """Remove list 'sub' from beginning (right=False), resp., end of list 'lst'"""

    if not right:
        while sub:
            if lst[:1] == sub[:1]:
                lst = lst[1:]
                sub = sub[1:]
            else:
                lst = []
                sub = []
    else:
        while sub:
            if lst[-1:] == sub[-1:]:
                lst = lst[:-1]
                sub = sub[:-1]
            else:
                lst = []
                sub = []

    return lst
