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
#
#
# This script is used to show the commit data of the configuration

import sys
from pathlib import Path
from argparse import ArgumentParser

from vyos.config_mgmt import ConfigMgmt
from vyos.configtree import ConfigTree
from vyos.configtree import show_commit_data

cm = ConfigMgmt()

parser = ArgumentParser(
    description='Show commit priority queue; no options compares the last two commits'
)
parser.add_argument('--active-config', help='Path to the active configuration file')
parser.add_argument('--proposed-config', help='Path to the proposed configuration file')
args = parser.parse_args()

active_arg = args.active_config
proposed_arg = args.proposed_config

if active_arg and not proposed_arg:
    print('--proposed-config is required when --active-config is specified')
    sys.exit(1)

if not active_arg and not proposed_arg:
    active = cm.get_config_tree_revision(1)
    proposed = cm.get_config_tree_revision(0)
else:
    if active_arg:
        active = ConfigTree(Path(active_arg).read_text())
    else:
        active = cm.get_config_tree_revision(0)

    proposed = ConfigTree(Path(proposed_arg).read_text())

ret = show_commit_data(active, proposed)
print(ret)
