#!/usr/bin/env python3
#
# Copyright (C) 2022 VyOS maintainers and contributors
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
import argparse
import tempfile
from vyos.configsource import ConfigSourceSession, VyOSError
from vyos.configtree import ConfigTree, DiffTree
from vyos.migrator import Migrator, VirtualMigrator, MigratorError
from vyos.remote import get_remote_config
from vyos.defaults import directories
from vyos.util import cmd, DEVNULL

DEFAULT_CONFIG_PATH = os.path.join(directories['current'], 'config.boot')
protocols = ['scp', 'sftp', 'http', 'https', 'ftp', 'tftp']

class LoadConfig(ConfigSourceSession):
    """A subclass for loading a config file.
    This does not belong in configsource.py, and only has a single caller.
    """
    def __init__(self):
        super().__init__()
        if not self.in_session():
            raise VyOSError("Config can only be loaded from config session.")

    def load_config(self, file_path):
        try:
            with open(file_path) as f:
                config_file = f.read()
            load_ct = ConfigTree(config_file)
        except (OSError, ValueError) as e:
            print(repr(e))
            return -1

        eff_ct, _ = self.get_configtree_tuple()
        diff = DiffTree(eff_ct, load_ct)
        commands = diff.to_commands()
        # on an empty set of 'add' or 'delete' commands, to_commands
        # returns '\n'; prune below
        command_list = commands.splitlines()
        command_list = [c for c in command_list if c]

        if not command_list:
            return 0
        for op in command_list:
            try:
                cmd(f'/opt/vyatta/sbin/my_{op}', shell=True, stderr=DEVNULL)
            except OSError as e:
                print(e.strerror)
                return e.errno

        return 0

def get_local_config(filename):
    if os.path.isfile(filename):
        fname = filename
    else:
        sys.exit(f"No such file '{filename}'")

    if fname.endswith('.gz'):
        with gzip.open(fname, 'rb') as f:
            try:
                config_str = f.read().decode()
            except OSError as e:
                sys.exit(repr(e))
    else:
        with open(fname, 'r') as f:
            try:
                config_str = f.read()
            except OSError as e:
                sys.exit(repr(e))

    return config_str

def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('config_file', type=str, nargs='?',
                           default=DEFAULT_CONFIG_PATH,
                           help="configuration file to load")
    argparser.add_argument('--debug', action='store_true', help="Debug")
    args = argparser.parse_args()

    file_name = args.config_file
    debug = args.debug

    if any(x in file_name for x in protocols):
        config_string = get_remote_config(file_name)
        if not config_string:
            sys.exit(f"No such config file at '{file_name}'")
    else:
        config_string = get_local_config(file_name)

    try:
        config = LoadConfig()
    except VyOSError as e:
        sys.exit(repr(e))

    print(f"Loading configuration from '{file_name}'")

    tmp_config = tempfile.NamedTemporaryFile(dir='/tmp', delete=False).name
    if debug:
        print(f"migrated config at {tmp_config}")
    with open(tmp_config, 'w') as fd:
        fd.write(config_string)

    virtual_migration = VirtualMigrator(tmp_config)
    try:
        virtual_migration.run()
    except MigratorError as e:
        sys.exit(repr(e))

    migration = Migrator(tmp_config)
    try:
        migration.run()
    except MigratorError as e:
        sys.exit(repr(e))

    res = config.load_config(tmp_config)

    if not debug:
        os.remove(tmp_config)

    if res != 0:
        sys.exit(res)

    if config.session_changed():
        print("Load complete. Use 'commit' to make changes effective.")
    else:
        print("No configuration changes to commit.")

if __name__ == '__main__':
    main()
