# Copyright 2022-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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

import os
import re
import typing

from typing import Union
from typing import Optional
from humps import decamelize

from vyos.defaults import directories
from vyos.utils.system import load_as_module
from vyos.opmode import _normalize_field_names
from vyos.opmode import _is_literal_type, _get_literal_values

def load_op_mode_as_module(name: str):
    path = os.path.join(directories['op_mode'], name)
    name = os.path.splitext(name)[0].replace('-', '_')
    return load_as_module(name, path)

def is_show_function_name(name):
    if re.match(r"^show", name):
        return True
    return False

def _nth_split(delim: str, n: int, s: str):
    groups = s.split(delim)
    l = len(groups)
    if n > l-1 or n < 1:
        return (s, '')
    return (delim.join(groups[:n]), delim.join(groups[n:]))

def _nth_rsplit(delim: str, n: int, s: str):
    groups = s.split(delim)
    l = len(groups)
    if n > l-1 or n < 1:
        return (s, '')
    return (delim.join(groups[:l-n]), delim.join(groups[l-n:]))

# Since we have mangled possible hyphens in the file name while constructing
# the snake case of the query/mutation name, we will need to recover the
# file name by searching with mangling:
def _filter_on_mangled(test):
    def func(elem):
        mangle = os.path.splitext(elem)[0].replace('-', '_')
        return test == mangle
    return func

# Find longest name in concatenated string that matches the basename of an
# op-mode script. Should one prefer to concatenate in the reverse order
# (script_name + '_' + function_name), use _nth_rsplit.
def split_compound_op_mode_name(name: str, files: list):
    for i in range(1, name.count('_') + 1):
        pair = _nth_split('_', i, name)
        f = list(filter(_filter_on_mangled(pair[1]), files))
        if f:
            pair = (pair[0], f[0])
            return pair
    return (name, '')

def snake_to_pascal_case(name: str) -> str:
    res = ''.join(map(str.title, name.split('_')))
    return res

def map_type_name(type_name: type, enums: Optional[dict] = None, optional: bool = False) -> str:
    if type_name == str:
        return 'String!' if not optional else 'String = null'
    if type_name == int:
        return 'Int!' if not optional else 'Int = null'
    if type_name == bool:
        return 'Boolean = false'
    if typing.get_origin(type_name) == list:
        if not optional:
            return f'[{map_type_name(typing.get_args(type_name)[0], enums=enums)}]!'
        return f'[{map_type_name(typing.get_args(type_name)[0], enums=enums)}]'
    if _is_literal_type(type_name):
        mapped = enums.get(_get_literal_values(type_name), '')
        if not mapped:
            raise ValueError(typing.get_args(type_name))
        return f'{mapped}!' if not optional else mapped
    # typing.Optional is typing.Union[_, NoneType]
    if (typing.get_origin(type_name) is typing.Union and
            typing.get_args(type_name)[1] == type(None)):
        return f'{map_type_name(typing.get_args(type_name)[0], enums=enums, optional=True)}'

    # scalar 'Generic' is defined in schema.graphql
    return 'Generic'

def normalize_output(result: Union[dict, list]) -> Union[dict, list]:
    return _normalize_field_names(decamelize(result))
