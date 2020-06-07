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
import jinja2

import vyos.version
import vyos.limericks

from vyos.util import cmd
from vyos.util import call
from vyos.util import run
from vyos.util import read_file
from vyos.util import DEVNULL


parser = argparse.ArgumentParser()
parser.add_argument("-a", "--all", action="store_true", help="Include individual package versions")
parser.add_argument("-f", "--funny", action="store_true", help="Add something funny to the output")
parser.add_argument("-j", "--json", action="store_true", help="Produce JSON output")


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
{% if cpu %}

{% if 'vendor' in cpu %}CPU Vendor:       {{cpu.vendor}}{% endif %}
{% if 'model' in cpu %}Model:            {{cpu.model}}{% endif %}
{% if 'cpus' in cpu %}Total CPUs:       {{cpu.cpus}}{% endif %}
{% if 'sockets' in cpu %}Sockets:          {{cpu.sockets}}{% endif %}
{% if 'cores' in cpu %}Cores:            {{cpu.cores}}{% endif %}
{% if 'threads' in cpu %}Threads:          {{cpu.threads}}{% endif %}
{% if 'mhz' in cpu %}Current MHz:      {{cpu.mhz}}{% endif %}
{% if 'mhz_min' in cpu %}Minimum MHz:      {{cpu.mhz_min}}{% endif %}
{% if 'mhz_max' in cpu %}Maximum MHz:      {{cpu.mhz_max}}{% endif %}
{% endif %}

Hardware vendor:  {{hardware_vendor}}
Hardware model:   {{hardware_model}}
Hardware S/N:     {{hardware_serial}}
Hardware UUID:    {{hardware_uuid}}

Copyright:        VyOS maintainers and contributors
"""

if __name__ == '__main__':
    args = parser.parse_args()

    version_data = vyos.version.get_full_version_data()

    if args.json:
        print(json.dumps(version_data))
        sys.exit(0)

    tmpl = jinja2.Template(version_output_tmpl)
    print(tmpl.render(version_data))

    #print(version_output_tmpl.format(**version_data).strip())

    if args.all:
        print("Package versions:")
        call("dpkg -l")

    if args.funny:
        print(vyos.limericks.get_random())
