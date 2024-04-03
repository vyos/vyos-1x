#!/usr/bin/python3

# Copyright 2019-2024 VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

import sys
import tempfile
import vyos.defaults
import vyos.remote

from vyos.config import Config
from vyos.configtree import ConfigTree
from vyos.migrator import Migrator, VirtualMigrator
from vyos.utils.process import cmd
from vyos.utils.process import DEVNULL

if (len(sys.argv) < 2):
    print("Need config file name to merge.")
    print("Usage: merge <config file> [config path]")
    sys.exit(0)

file_name = sys.argv[1]

configdir = vyos.defaults.directories['config']

protocols = ['scp', 'sftp', 'http', 'https', 'ftp', 'tftp']

if any(x in file_name for x in protocols):
    config_file = vyos.remote.get_remote_config(file_name)
    if not config_file:
        sys.exit("No config file by that name.")
else:
    canonical_path = "{0}/{1}".format(configdir, file_name)
    first_err = None
    try:
        with open(canonical_path, 'r') as f:
            config_file = f.read()
    except Exception as err:
        first_err = err
        try:
            with open(file_name, 'r') as f:
                config_file = f.read()
        except Exception as err:
            print(first_err)
            print(err)
            sys.exit(1)

with tempfile.NamedTemporaryFile() as file_to_migrate:
    with open(file_to_migrate.name, 'w') as fd:
        fd.write(config_file)

    virtual_migration = VirtualMigrator(file_to_migrate.name)
    virtual_migration.run()

    migration = Migrator(file_to_migrate.name)
    migration.run()

    if virtual_migration.config_changed() or migration.config_changed():
        with open(file_to_migrate.name, 'r') as fd:
            config_file = fd.read()

merge_config_tree = ConfigTree(config_file)

effective_config = Config()
effective_config_tree = effective_config._running_config

effective_cmds = effective_config_tree.to_commands()
merge_cmds = merge_config_tree.to_commands()

effective_cmd_list = effective_cmds.splitlines()
merge_cmd_list =  merge_cmds.splitlines()

effective_cmd_set = set(effective_cmd_list)
add_cmds = [ cmd for cmd in merge_cmd_list if cmd not in effective_cmd_set ]

path = None
if (len(sys.argv) > 2):
    path = sys.argv[2:]
    if (not effective_config_tree.exists(path) and not
            merge_config_tree.exists(path)):
        print("path {} does not exist in either effective or merge"
              " config; will use root.".format(path))
        path = None
    else:
        path = " ".join(path)

if path:
    add_cmds = [ cmd for cmd in add_cmds if path in cmd ]

for add in add_cmds:
    try:
        cmd(f'/opt/vyatta/sbin/my_{add}', shell=True, stderr=DEVNULL)
    except OSError as err:
        print(err)

if effective_config.session_changed():
    print("Merge complete. Use 'commit' to make changes effective.")
else:
    print("No configuration changes to commit.")
