#!/usr/bin/env python3
#
# Copyright (C) 2018 VyOS maintainers and contributors
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

import sys
import os

from psutil import pid_exists
from subprocess import Popen, PIPE
from time import sleep
from netifaces import interfaces

def get_config_name(intf):
    cfg_file = r'/opt/vyatta/etc/openvpn/openvpn-{}.conf'.format(intf)
    return cfg_file

def get_pid_file(intf):
    pid_file = r'/var/run/openvpn/{}.pid'.format(intf)
    return pid_file

def subprocess_cmd(command):
    p = Popen(command, stdout=PIPE, shell=True)
    p.communicate()

if __name__ == '__main__':
    if (len(sys.argv) < 1):
        print("Must specify OpenVPN interface name!")
        sys.exit(1)

    interface = sys.argv[1]
    if os.path.isfile(get_config_name(interface)):
        pidfile = '/var/run/openvpn/{}.pid'.format(interface)
        if os.path.isfile(pidfile):
            pid = 0
            with open(pidfile, 'r') as f:
                pid = int(f.read())

            if pid_exists(pid):
                cmd = 'start-stop-daemon'
                cmd += ' --stop'
                cmd += ' --oknodo'
                cmd += ' --quiet'
                cmd += ' --pidfile ' + pidfile
                subprocess_cmd(cmd)

        # When stopping OpenVPN we need to wait for the 'old' interface to
        # vanish from the Kernel, if it is not gone, OpenVPN will report:
        # ERROR: Cannot ioctl TUNSETIFF vtun10: Device or resource busy (errno=16)
        while interface in interfaces():
            sleep(0.250) # 250ms

        # re-start OpenVPN process
        cmd = 'start-stop-daemon'
        cmd += ' --start'
        cmd += ' --oknodo'
        cmd += ' --quiet'
        cmd += ' --pidfile ' + get_pid_file(interface)
        cmd += ' --exec /usr/sbin/openvpn'
        # now pass arguments to openvpn binary
        cmd += ' --'
        cmd += ' --daemon openvpn-' + interface
        cmd += ' --config ' + get_config_name(interface)

        subprocess_cmd(cmd)
    else:
        print("OpenVPN interface {} does not exist!".format(interface))
        sys.exit(1)
