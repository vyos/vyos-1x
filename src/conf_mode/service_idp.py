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

# Directory where the SAML IDP configuration will be stored
CONFIG_DIR = "/lib/security/saml-auth"

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['service', 'idp']

    config_data = conf.get_config_dict(base, key_mangling=('-', '_'))
    return config_data

def verify(config_dict):
    pass

def generate(config_dict):
    config_json = json.dumps(config_dict, indent=4)

    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR, exist_ok=True)

    with open(f"{CONFIG_DIR}/idp_config.json", "w") as f:
        f.write(config_json)

def apply(config_dict):
    pass

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        exit(1)
