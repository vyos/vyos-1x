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

# Script is used to synchronize configured bridge interfaces.
# one can add a non existing interface to a bridge group (e.g. VLAN)
# but the vlan interface itself does yet not exist. It should be added
# to the bridge automatically once it's available

import argparse
import subprocess

from sys import exit
from time import sleep
from vyos.config import Config

def subprocess_cmd(command):
    process = subprocess.Popen(command,stdout=subprocess.PIPE, shell=True)
    proc_stdout = process.communicate()[0].strip()
    pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--interface', action='store', help='Interface name which should be added to bridge it is configured for', required=True)
    args, unknownargs = parser.parse_known_args()

    conf = Config()
    if not conf.list_nodes('interfaces bridge'):
        #  no bridge interfaces exist .. bail out early
        exit(0)
    else:
        for bridge in conf.list_nodes('interfaces bridge'):
            for member_if in conf.list_nodes('interfaces bridge {} member interface'.format(bridge)):
                if args.interface == member_if:
                    cmd = 'brctl addif "{}" "{}"'.format(bridge, args.interface)
                    # let interfaces etc. settle - especially required for OpenVPN bridged interfaces
                    sleep(4)
                    subprocess_cmd(cmd)

    exit(0)
