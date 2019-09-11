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

import os
import sys
import subprocess
import traceback

from vyos.configsession import ConfigSession, ConfigSessionError
from vyos.configtree import ConfigTree

STATUS_FILE = '/tmp/vyos-config-status'
TRACE_FILE = '/tmp/boot-config-trace'

session = ConfigSession(os.getpid(), 'vyos-boot-config-loader')
env = session.get_session_env()

default_file_name = env['vyatta_sysconfdir'] + '/config.boot.default'

if len(sys.argv) < 1:
    print("Must be called with argument.")
    sys.exit(1)
else:
    file_name = sys.argv[1]

def write_config_status(status):
    with open(STATUS_FILE, 'w') as f:
        f.write('{0}\n'.format(status))

def trace_to_file(trace_file_name):
    with open(trace_file_name, 'w') as trace_file:
        traceback.print_exc(file=trace_file)

def failsafe():
    try:
        with open(default_file_name, 'r') as f:
            config_file = f.read()
    except Exception as e:
        print("Catastrophic: no default config file "
              "'{0}'".format(default_file_name))
        sys.exit(1)

    config = ConfigTree(config_file)
    if not config.exists(['system', 'login', 'user', 'vyos',
                          'authentication', 'encrypted-password']):
        print("No password entry in default config file;")
        print("unable to recover password for user 'vyos'.")
        sys.exit(1)
    else:
        passwd = config.return_value(['system', 'login', 'user', 'vyos',
                                      'authentication',
                                      'encrypted-password'])

    cmd = ("useradd -s /bin/bash -G 'users,sudo' -m -N -p '{0}' "
           "vyos".format(passwd))
    try:
        subprocess.check_call(cmd, shell=True)
    except subprocess.CalledProcessError as e:
        sys.exit("{0}".format(e))

    with open('/etc/motd', 'a+') as f:
        f.write('\n\n')
        f.write('!!!!!\n')
        f.write('There were errors loading the initial configuration;\n')
        f.write('please examine the errors in {0} and correct.'
                '\n'.format(TRACE_FILE))
        f.write('!!!!!\n\n')

try:
    with open(file_name, 'r') as f:
        config_file = f.read()
except Exception as e:
    write_config_status(1)
    failsafe()
    trace_to_file(TRACE_FILE)
    sys.exit("{0}".format(e))

try:
    session.load_config(file_name)
    session.commit()
    write_config_status(0)
except ConfigSessionError as e:
    write_config_status(1)
    failsafe()
    trace_to_file(TRACE_FILE)
    sys.exit(1)
