#!/usr/bin/env python3
#
# Copyright (C) 2025 VyOS maintainers and contributors
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
# This script is used to test execution of the commit algorithm by vyos-commitd

from pathlib import Path
from argparse import ArgumentParser
from datetime import datetime

from vyos.configtree import ConfigTree
from vyos.configtree import test_commit


parser = ArgumentParser(
    description='Execute commit priority queue'
)
parser.add_argument(
    '--active-config', help='Path to the active configuration file', required=True
)
parser.add_argument(
    '--proposed-config', help='Path to the proposed configuration file', required=True
)
args = parser.parse_args()

active_arg = args.active_config
proposed_arg = args.proposed_config

active = ConfigTree(Path(active_arg).read_text())
proposed = ConfigTree(Path(proposed_arg).read_text())


time_begin_commit = datetime.now()
test_commit(active, proposed)
time_end_commit = datetime.now()
print(f'commit time: {time_end_commit - time_begin_commit}')
