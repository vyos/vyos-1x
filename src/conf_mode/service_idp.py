#!/usr/bin/env python3
#
# Copyright (C) 2019-2024 VyOS maintainers and contributors
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

import os
import sys
import json
from vyos.config import Config
from vyos import ConfigError

CONFIG_DIR = "/etc/idp-providers"

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['system', 'idp']

    config_data = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
    return config_data

def verify(config_dict):
    if not isinstance(config_dict, dict):
        raise ConfigError("IDP config is not a dict")

    for idp_name, data in config_dict.items():
        if not idp_name:
            raise ConfigError("IDP name cannot be empty")

        if 'metadata-url' not in data or not data['metadata-url']:
            raise ConfigError(f"IDP '{idp_name}' requires a metadat URL")
    
        url = data['metadata-url']
        if not (url.startswith('http://') or url.startswith('https://')):
            raise ConfigError(f"IDP '{idp_name}' URL must start with http:// or https://")

def generate(config_dict):
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR, exists_ok=True)
    
    path = os.path.join(CONFIG_DIR, 'idps.json')
    with open(path, "w") as f:
        json.dump(config_dict, f, indent=2)

def apply(config_dict):
    pass

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
