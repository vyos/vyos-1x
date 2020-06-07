#!/usr/bin/env python3
#
# Copyright (C) 2016-2020 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Purpose:
#    Displays image version and system information.
#    Used by the "run show version" command.

import sys
import argparse
import json

import vyos.version
import vyos.limericks

from vyos.util import call

parser = argparse.ArgumentParser()
parser.add_argument("-a", "--all", action="store_true", help="Include individual package versions")
parser.add_argument("-f", "--funny", action="store_true", help="Add something funny to the output")
parser.add_argument("-j", "--json", action="store_true", help="Produce JSON output")

version_output_tmpl = """
Version:          VyOS {version}
Release Train:    {release_train}

Built by:         {built_by}
Built on:         {built_on}
Build UUID:       {build_uuid}
Build Commit ID:  {build_git}

Architecture:     {system_arch}
Boot via:         {boot_via}
System type:      {system_type}

Hardware vendor:  {hardware_vendor}
Hardware model:   {hardware_model}
Hardware S/N:     {hardware_serial}
Hardware UUID:    {hardware_uuid}

Copyright:        VyOS maintainers and contributors
"""

if __name__ == '__main__':
    args = parser.parse_args()

    version_data = vyos.version.get_full_version_data()

    if args.json:
        print(json.dumps(version_data))
        sys.exit(0)

    print(version_output_tmpl.format(**version_data).strip())

    if args.all:
        print("Package versions:")
        call("dpkg -l")

    if args.funny:
        print(vyos.limericks.get_random())
