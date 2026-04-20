#!/usr/bin/env python3
#
# Copyright (C) VyOS Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import re
import json
from pathlib import Path


def filter_key(s: Path):
    s = s.stem
    return re.match(r'\d+\-.+', s)


def sort_key(s: Path):
    s = s.stem
    pre, rem = re.match(r'(\d+)(?:-)(.+)', s).groups()
    return int(pre), rem


activation_dir = 'src/activation-scripts'
activation_list = 'data/activation-list'
activation_list_init = 'data/activation-init'

activation_scripts = Path(activation_dir).glob('*.py')

filtered = filter(filter_key, activation_scripts)
script_list = sorted(filtered, key=sort_key)

# default on system update
script_dict = dict.fromkeys(map(lambda s: s.stem, script_list), 'enabled')
# exceptions:
# only enabled for script_dict_init
script_dict['00-first-installed-boot'] = 'never'
# for backward compatibility on system update
script_dict['20-ethernet-offload'] = 'off'

# installed on image creation
script_dict_init = dict.fromkeys(map(lambda s: s.stem, script_list), 'enabled')

Path(activation_list).write_text(json.dumps(script_dict))
Path(activation_list_init).write_text(json.dumps(script_dict_init))
