#!/usr/bin/python3

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

import os
import sys
import shlex
import argparse
import tempfile

from vyos.remote import get_config_file
from vyos.config import Config
from vyos.configtree import ConfigTree
from vyos.configtree import mask_inclusive
from vyos.configtree import merge
from vyos.migrate import ConfigMigrate
from vyos.migrate import ConfigMigrateError
from vyos.load_config import load_explicit


parser = argparse.ArgumentParser()
parser.add_argument('config_file', help='config file to merge from')
parser.add_argument(
    '--destructive', action='store_true', help='replace values with those of merge file'
)
parser.add_argument('--paths', nargs='+', help='only merge from listed paths')
parser.add_argument(
    '--migrate', action='store_true', help='migrate config file before merge'
)

args = parser.parse_args()

file_name = args.config_file
paths = [shlex.split(s) for s in args.paths] if args.paths else []

# pylint: disable=consider-using-with
file_path = tempfile.NamedTemporaryFile(delete=False).name
err = get_config_file(file_name, file_path)
if err:
    os.remove(file_path)
    sys.exit(err)

if args.migrate:
    migrate = ConfigMigrate(file_path)
    try:
        migrate.run()
    except ConfigMigrateError as e:
        os.remove(file_path)
        sys.exit(e)

with open(file_path) as f:
    merge_str = f.read()

merge_ct = ConfigTree(merge_str)

if paths:
    mask = ConfigTree('')
    for p in paths:
        mask.set(p)

    merge_ct = mask_inclusive(merge_ct, mask)

with open(file_path, 'w') as f:
    f.write(merge_ct.to_string())

config = Config()

if config.vyconf_session is not None:
    out, err = config.vyconf_session.merge_config(
        file_path, destructive=args.destructive
    )
    if err:
        os.remove(file_path)
        sys.exit(out)
    print(out)
else:
    session_ct = config.get_config_tree()
    merge_res = merge(session_ct, merge_ct, destructive=args.destructive)

    load_explicit(merge_res)

os.remove(file_path)

if config.session_changed():
    print("Merge complete. Use 'commit' to make changes effective.")
else:
    print('No configuration changes to commit.')
