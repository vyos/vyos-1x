#!/usr/bin/env python3
#
# Copyright (C) 2016 VyOS maintainers and contributors
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
# File: vyos-show-version
# Purpose:
#    Displays image version and system information.
#    Used by the "run show version" command.


import os
import sys
import argparse
import json

import pystache

import vyos.version
import vyos.limericks

from vyos.util import cmd
from vyos.util import call
from vyos.util import run
from vyos.util import DEVNULL


parser = argparse.ArgumentParser()
parser.add_argument("-a", "--all", action="store_true", help="Include individual package versions")
parser.add_argument("-f", "--funny", action="store_true", help="Add something funny to the output")
parser.add_argument("-j", "--json", action="store_true", help="Produce JSON output")

def read_file(name):
    try:
        with open (name, "r") as f:
            data = f.read()
        return data.strip()
    except:
        # This works since we only read /sys/class/* stuff
        # with this function
        return "Unknown"

version_output_tmpl = """
Version:          VyOS {{version}}
Release Train:    {{release_train}}

Built by:         {{built_by}}
Built on:         {{built_on}}
Build UUID:       {{build_uuid}}
Build Commit ID:  {{build_git}}

Architecture:     {{system_arch}}
Boot via:         {{boot_via}}
System type:      {{system_type}}

Hardware vendor:  {{hardware_vendor}}
Hardware model:   {{hardware_model}}
Hardware S/N:     {{hardware_serial}}
Hardware UUID:    {{hardware_uuid}}

Copyright:        VyOS maintainers and contributors

"""

if __name__ == '__main__':
    args = parser.parse_args()

    version_data = vyos.version.get_version_data()

    # Get system architecture (well, kernel architecture rather)
    version_data['system_arch'] = cmd('uname -m')


    # Get hypervisor name, if any
    system_type = "bare metal"
    try:
        hypervisor = cmd('hvinfo',stderr=DEVNULL)
        system_type = "{0} guest".format(hypervisor)
    except OSError:
        # hvinfo returns 1 if it cannot detect any hypervisor
        pass
    version_data['system_type'] = system_type


    # Get boot type, it can be livecd, installed image, or, possible, a system installed
    # via legacy "install system" mechanism
    # In installed images, the squashfs image file is named after its image version,
    # while on livecd it's just "filesystem.squashfs", that's how we tell a livecd boot
    # from an installed image
    boot_via = "installed image"
    if run(""" grep -e '^overlay.*/filesystem.squashfs' /proc/mounts >/dev/null""") == 0:
        boot_via = "livecd"
    elif run(""" grep '^overlay /' /proc/mounts >/dev/null """) != 0:
        boot_via = "legacy non-image installation"
    version_data['boot_via'] = boot_via


    # Get hardware details from DMI
    version_data['hardware_vendor'] = read_file('/sys/class/dmi/id/sys_vendor')
    version_data['hardware_model']  = read_file('/sys/class/dmi/id/product_name')

    # These two assume script is run as root, normal users can't access those files
    version_data['hardware_serial'] = read_file('/sys/class/dmi/id/subsystem/id/product_serial')
    version_data['hardware_uuid']   = read_file('/sys/class/dmi/id/subsystem/id/product_uuid')


    if args.json:
        print(json.dumps(version_data))
        sys.exit(0)
    else:
        output = pystache.render(version_output_tmpl, version_data).strip()
        print(output)

        if args.all:
           print("Package versions:")
           call("dpkg -l")

        if args.funny:
            print(vyos.limericks.get_random())
