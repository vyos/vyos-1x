#!/usr/bin/env python3
#
# Copyright (C) 2019 VyOS maintainers and contributors
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

"""Load config file from within config session.
Config file specified by URI or path (without scheme prefix).
Example: load https://somewhere.net/some.config
        or
         load /tmp/some.config
"""

import sys
import tempfile
import vyos.defaults
import vyos.remote
from vyos.config import Config, VyOSError
from vyos.migrator import Migrator, MigratorError

system_config_file = 'config.boot'

class LoadConfig(Config):
    """A subclass for calling 'loadFile'.
    This does not belong in config.py, and only has a single caller.
    """
    def load_config(self, file_path):
        cmd = [self._cli_shell_api, 'loadFile', file_path]
        self._run(cmd)

if len(sys.argv) > 1:
    file_name = sys.argv[1]
else:
    file_name = system_config_file

configdir = vyos.defaults.directories['config']

protocols = ['scp', 'sftp', 'http', 'https', 'ftp', 'tftp']

if any(x in file_name for x in protocols):
    config_file = vyos.remote.get_remote_config(file_name)
    if not config_file:
        sys.exit("No config file by that name.")
else:
    canonical_path = '{0}/{1}'.format(configdir, file_name)
    try:
        with open(canonical_path, 'r') as f:
            config_file = f.read()
    except OSError as err1:
        try:
            with open(file_name, 'r') as f:
                config_file = f.read()
        except OSError as err2:
            sys.exit('{0}\n{1}'.format(err1, err2))

config = LoadConfig()

print("Loading configuration from '{}'".format(file_name))

with tempfile.NamedTemporaryFile() as fp:
    with open(fp.name, 'w') as fd:
        fd.write(config_file)

    migration = Migrator(fp.name)
    try:
        migration.run()
    except MigratorError as err:
        sys.exit('{}'.format(err))

    try:
        config.load_config(fp.name)
    except VyOSError as err:
        sys.exit('{}'.format(err))

if config.session_changed():
    print("Load complete. Use 'commit' to make changes effective.")
else:
    print("No configuration changes to commit.")
