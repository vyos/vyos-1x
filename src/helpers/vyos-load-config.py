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

import os
import sys
import argparse
import tempfile

from vyos.remote import get_config_file
from vyos.config import Config
from vyos.migrate import ConfigMigrate
from vyos.migrate import ConfigMigrateError
from vyos.load_config import load as load_config
from vyos.defaults import directories


default_config_file = os.path.join(directories['config'], 'config.boot')

parser = argparse.ArgumentParser()
parser.add_argument('config_file', nargs='?', help='config file to load')
parser.add_argument(
    '--migrate', action='store_true', help='migrate config file before merge'
)

args = parser.parse_args()

file_name = args.config_file if args.config_file else default_config_file

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

config = Config()

if config.vyconf_session is not None:
    out, err = config.vyconf_session.load_config(file_path)
    if err:
        os.remove(file_path)
        sys.exit(out)
    print(out)
else:
    load_config(file_path)

os.remove(file_path)

if config.session_changed():
    print("Load complete. Use 'commit' to make changes effective.")
else:
    print('No configuration changes to commit.')
