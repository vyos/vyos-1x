# Copyright 2020-2023 VyOS maintainers and contributors <maintainers@vyos.io>
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

def _mangle_dict_keys(data, regex, replacement, abs_path=[], no_tag_node_value_mangle=False, mod=0):
    """ Mangles dict keys according to a regex and replacement character.
    Some libraries like Jinja2 do not like certain characters in dict keys.
    This function can be used for replacing all offending characters
    with something acceptable.

    Args:
        data (dict): Original dict to mangle

    Returns: dict
    """
    import re
    from vyos.xml import is_tag

    new_dict = {}

    for key in data.keys():
        save_mod = mod
        save_path = abs_path[:]

        abs_path.append(key)

        if not is_tag(abs_path):
            new_key = re.sub(regex, replacement, key)
        else:
            if mod%2:
                new_key = key
            else:
                new_key = re.sub(regex, replacement, key)
            if no_tag_node_value_mangle:
                mod += 1

        value = data[key]

        if isinstance(value, dict):
            new_dict[new_key] = _mangle_dict_keys(value, regex, replacement, abs_path=abs_path, mod=mod, no_tag_node_value_mangle=no_tag_node_value_mangle)
        else:
            new_dict[new_key] = value

        mod = save_mod
        abs_path = save_path[:]

    return new_dict

def mangle_dict_keys(data, regex, replacement, abs_path=[], no_tag_node_value_mangle=False):
    return _mangle_dict_keys(data, regex, replacement, abs_path=abs_path, no_tag_node_value_mangle=no_tag_node_value_mangle, mod=0)
