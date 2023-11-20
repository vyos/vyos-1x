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

import os
import sys
import gzip
import tempfile
import vyos.defaults
import vyos.remote
from vyos.configsource import ConfigSourceSession, VyOSError
from vyos.migrator import Migrator, VirtualMigrator, MigratorError

class LoadConfig(ConfigSourceSession):
    """A subclass for calling 'loadFile'.
    This does not belong in configsource.py, and only has a single caller.
    """
    def load_config(self, path):
        return self._run(['/bin/cli-shell-api','loadFile',path])

file_name = sys.argv[1] if len(sys.argv) > 1 else 'config.boot'
configdir = vyos.defaults.directories['config']
protocols = ['scp', 'sftp', 'http', 'https', 'ftp', 'tftp']

def get_local_config(filename):
    if os.path.isfile(filename):
        fname = filename
    elif os.path.isfile(os.path.join(configdir, filename)):
        fname = os.path.join(configdir, filename)
    else:
        sys.exit(f"No such file '{filename}'")

    if fname.endswith('.gz'):
        with gzip.open(fname, 'rb') as f:
            try:
                config_str = f.read().decode()
            except OSError as e:
                sys.exit(e)
    else:
        with open(fname, 'r') as f:
            try:
                config_str = f.read()
            except OSError as e:
                sys.exit(e)

    return config_str

if any(file_name.startswith(f'{x}://') for x in protocols):
    config_string = vyos.remote.get_remote_config(file_name)
    if not config_string:
        sys.exit(f"No such config file at '{file_name}'")
else:
    config_string = get_local_config(file_name)

config = LoadConfig()

print(f"Loading configuration from '{file_name}'")

with tempfile.NamedTemporaryFile() as fp:
    with open(fp.name, 'w') as fd:
        fd.write(config_string)

    virtual_migration = VirtualMigrator(fp.name)
    try:
        virtual_migration.run()
    except MigratorError as err:
        sys.exit('{}'.format(err))

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
