# Copyright 2023 VyOS maintainers and contributors <maintainers@vyos.io>
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

from typing import Optional, Union, TYPE_CHECKING
from vyos.xml_ref import definition

if TYPE_CHECKING:
    from vyos.config import ConfigDict

def load_reference(cache=[]):
    if cache:
        return cache[0]

    xml = definition.Xml()

    try:
        from vyos.xml_ref.cache import reference
    except Exception:
        raise ImportError('no xml reference cache !!')

    if not reference:
        raise ValueError('empty xml reference cache !!')

    xml.define(reference)
    cache.append(xml)

    return xml

def is_tag(path: list) -> bool:
    return load_reference().is_tag(path)

def is_tag_value(path: list) -> bool:
    return load_reference().is_tag_value(path)

def is_multi(path: list) -> bool:
    return load_reference().is_multi(path)

def is_valueless(path: list) -> bool:
    return load_reference().is_valueless(path)

def is_leaf(path: list) -> bool:
    return load_reference().is_leaf(path)

def owner(path: list) -> str:
    return load_reference().owner(path)

def priority(path: list) -> str:
    return load_reference().priority(path)

def cli_defined(path: list, node: str, non_local=False) -> bool:
    return load_reference().cli_defined(path, node, non_local=non_local)

def component_version() -> dict:
    return load_reference().component_version()

def default_value(path: list) -> Optional[Union[str, list]]:
    return load_reference().default_value(path)

def multi_to_list(rpath: list, conf: dict) -> dict:
    return load_reference().multi_to_list(rpath, conf)

def get_defaults(path: list, get_first_key=False, recursive=False) -> dict:
    return load_reference().get_defaults(path, get_first_key=get_first_key,
                                         recursive=recursive)

def relative_defaults(rpath: list, conf: dict, get_first_key=False,
                      recursive=False) -> dict:

    return load_reference().relative_defaults(rpath, conf,
                                              get_first_key=get_first_key,
                                              recursive=recursive)

def from_source(d: dict, path: list) -> bool:
    return definition.from_source(d, path)

def ext_dict_merge(source: dict, destination: Union[dict, 'ConfigDict']):
    return definition.ext_dict_merge(source, destination)
