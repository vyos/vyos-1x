#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
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
#
#
import os
import re
import sys
from tempfile import NamedTemporaryFile
from argparse import ArgumentParser

from vyos.config import Config
from vyos.remote import urlc
from vyos.component_version import add_system_version
from vyos.defaults import directories

DEFAULT_CONFIG_PATH = os.path.join(directories['config'], 'config.boot')
remote_save = None

parser = ArgumentParser(description='Save configuration')
parser.add_argument('file', type=str, nargs='?', help='Save configuration to file')
parser.add_argument('--write-json-file', type=str, help='Save JSON of configuration to file')
args = parser.parse_args()
file = args.file
json_file = args.write_json_file

if file is not None:
    save_file = file
else:
    save_file = DEFAULT_CONFIG_PATH

if re.match(r'\w+:/', save_file):
    try:
        remote_save = urlc(save_file)
    except ValueError as e:
        sys.exit(e)

config = Config()
ct = config.get_config_tree(effective=True)

# pylint: disable=consider-using-with
write_file = save_file if remote_save is None else NamedTemporaryFile(delete=False).name

# config_tree is None before boot configuration is complete;
# automated saves should check boot_configuration_complete
config_str = None if ct is None else ct.to_string()
add_system_version(config_str, write_file)

if json_file is not None and ct is not None:
    try:
        with open(json_file, 'w') as f:
            f.write(ct.to_json())
    except OSError as e:
        print(f'failed to write JSON file: {e}')

if remote_save is not None:
    try:
        remote_save.upload(write_file)
    finally:
        os.remove(write_file)
