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
import time
from argparse import ArgumentParser
from shutil import copyfile

from vyos.migrate import ConfigMigrate
from vyos.migrate import ConfigMigrateError

parser = ArgumentParser()
parser.add_argument('config_file', type=str,
                    help="configuration file to migrate")
parser.add_argument('--test-script', type=str,
                    help="test named script")
parser.add_argument('--output-file', type=str,
                    help="write to named output file instead of config file")
parser.add_argument('--force', action='store_true',
                    help="force run of all migration scripts")

args = parser.parse_args()

config_file = args.config_file
out_file = args.output_file
test_script = args.test_script
force = args.force

if not os.access(config_file, os.R_OK):
    print(f"Config file '{config_file}' not readable")
    sys.exit(1)

if out_file is None:
    if not os.access(config_file, os.W_OK):
        print(f"Config file '{config_file}' not writeable")
        sys.exit(1)
else:
    try:
        open(out_file, 'w').close()
    except OSError:
        print(f"Output file '{out_file}' not writeable")
        sys.exit(1)

config_migrate = ConfigMigrate(config_file, force=force, output_file=out_file)

if test_script:
    # run_script and exit
    config_migrate.run_script(test_script)
    sys.exit(0)

backup = None
if out_file is None:
    timestr = time.strftime("%Y%m%d-%H%M%S")
    backup = f'{config_file}.{timestr}.pre-migration'
    copyfile(config_file, backup)

try:
    config_migrate.run()
except ConfigMigrateError as e:
    print(f'Error: {e}')
    sys.exit(1)

if backup is not None and not config_migrate.config_modified:
    os.unlink(backup)
