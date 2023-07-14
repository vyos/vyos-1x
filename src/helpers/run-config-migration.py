#!/usr/bin/python3

# Copyright 2019 VyOS maintainers and contributors <maintainers@vyos.io>
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
# You should have received a copy of the GNU Lesser General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import argparse
import datetime

from vyos.utils.process import cmd
from vyos.migrator import Migrator, VirtualMigrator

def main():
    argparser = argparse.ArgumentParser(
            formatter_class=argparse.RawTextHelpFormatter)
    argparser.add_argument('config_file', type=str,
            help="configuration file to migrate")
    argparser.add_argument('--force', action='store_true',
            help="Force calling of all migration scripts.")
    argparser.add_argument('--set-vintage', type=str,
            choices=['vyatta', 'vyos'],
            help="Set the format for the config version footer in config"
            " file:\n"
            "set to 'vyatta':\n"
            "(for '/* === vyatta-config-version ... */' format)\n"
            "or 'vyos':\n"
            "(for '// vyos-config-version ...' format).")
    argparser.add_argument('--virtual', action='store_true',
            help="Update the format of the trailing comments in"
                 " config file,\nfrom 'vyatta' to 'vyos'; no migration"
                 " scripts are run.")
    args = argparser.parse_args()

    config_file_name = args.config_file
    force_on = args.force
    vintage = args.set_vintage
    virtual = args.virtual

    if not os.access(config_file_name, os.R_OK):
        print("Read error: {}.".format(config_file_name))
        sys.exit(1)

    if not os.access(config_file_name, os.W_OK):
        print("Write error: {}.".format(config_file_name))
        sys.exit(1)

    separator = "."
    backup_file_name = separator.join([config_file_name,
            '{0:%Y-%m-%d-%H%M%S}'.format(datetime.datetime.now()),
            'pre-migration'])

    cmd(f'cp -p {config_file_name} {backup_file_name}')

    if not virtual:
        virtual_migration = VirtualMigrator(config_file_name)
        virtual_migration.run()

        migration = Migrator(config_file_name, force=force_on)
        migration.run()

        if not migration.config_changed():
            os.remove(backup_file_name)
    else:
        virtual_migration = VirtualMigrator(config_file_name,
                                            set_vintage=vintage)

        virtual_migration.run()

        if not virtual_migration.config_changed():
            os.remove(backup_file_name)

if __name__ == '__main__':
    main()
