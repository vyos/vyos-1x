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

from vyos.xml_ref import definition

def load_reference(cache=[]):
    if cache:
        return cache[0]

    xml = definition.Xml()

    try:
        from vyos.xml_ref.cache import reference
        xml.define(reference)
        cache.append(xml)
    except Exception:
        raise ImportError('no xml reference cache !!')

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

def component_version() -> dict:
    return load_reference().component_version()

def multi_to_list(rpath: list, conf: dict) -> dict:
    return load_reference().multi_to_list(rpath, conf)

def get_defaults(path: list, get_first_key=False, recursive=False) -> dict:
    return load_reference().get_defaults(path, get_first_key=get_first_key,
                                         recursive=recursive)

def get_config_defaults(rpath: list, conf: dict, get_first_key=False,
                        recursive=False) -> dict:

    return load_reference().relative_defaults(rpath, conf=conf,
                                              get_first_key=get_first_key,
                                              recursive=recursive)

def merge_defaults(path: list, conf: dict) -> dict:
    return load_reference().merge_defaults(path, conf)
