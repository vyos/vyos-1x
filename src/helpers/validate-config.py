#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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


import sys
import argparse

from vyos.configtree import ConfigTree
from vyos.configtree import validate_tree_filter
from vyos.component_version import add_system_version


parser = argparse.ArgumentParser()
parser.add_argument('config_file', help='config file to validate')
parser.add_argument('--filtered-config', help='write valid subset of config file')

args = parser.parse_args()

config_file = args.config_file
filtered_config = args.filtered_config

with open(config_file) as f:
    config_str = f.read()

config_tree = ConfigTree(config_str)

valid_tree, out = validate_tree_filter(config_tree)

if filtered_config:
    add_system_version(valid_tree.to_string(), filtered_config)

if out:
    print(out)

sys.exit(int(bool(out)))
