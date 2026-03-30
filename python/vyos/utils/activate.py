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


import json
import typing
from pathlib import Path

from vyos.defaults import activation_list
from vyos.defaults import activation_init
from vyos.defaults import activation_hint
from vyos.defaults import directories


ActiveOpt = typing.Literal['enabled', 'once', 'off', 'never']


def get_activation_scripts() -> dict:
    list_path = Path(activation_list)
    return json.loads(list_path.read_text())


def set_activation(file_name: str, value: ActiveOpt):
    script_dict = get_activation_scripts()
    file_key = Path(file_name).stem
    script_dict[file_key] = value
    list_path = Path(activation_list)
    list_path.write_text(json.dumps(script_dict))


def get_activation(file_name: str) -> ActiveOpt:
    script_dict = get_activation_scripts()
    file_key = Path(file_name).stem
    return script_dict[file_key]


def is_active(file_name: str) -> bool:
    script_dict = get_activation_scripts()
    file_key = Path(file_name).stem
    if script_dict[file_key] in ('enabled', 'once'):
        return True
    return False


def stable_update(new: dict, old: dict):
    res = {}
    for key in new.keys():
        res[key] = old[key] if key in old.keys() else new[key]
    return res


def init_activation_list() -> bool:
    """Init if activation_hint exists, left on install_image or if image was
    built as raw_image"""

    init_hint = Path(activation_hint)
    if not init_hint.exists():
        return False

    init_hint.unlink()
    init_list = Path(activation_init)
    data_list = Path(activation_list)
    data_obj = json.loads(init_list.read_text())
    data_list.write_text(json.dumps(data_obj))

    return True


def refresh_activation_list():
    """Refresh activation list, as will be needed after image update"""

    if init_activation_list():
        return

    new_list_path = Path(directories['data']).joinpath(Path(activation_list).name)
    if not new_list_path.exists():
        return

    new_obj = json.loads(new_list_path.read_text())

    orig_list_path = Path(activation_list)
    if orig_list_path.exists():
        orig_obj = json.loads(orig_list_path.read_text())
        if orig_obj == new_obj:
            return

        obj = stable_update(new_obj, orig_obj)
    else:
        obj = new_obj

    orig_list_path.write_text(json.dumps(obj))
