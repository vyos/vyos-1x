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
import pwd
import grp
import traceback
from datetime import datetime

from vyos.defaults import directories, config_status
from vyos.configsession import ConfigSession, ConfigSessionError
from vyos.configtree import ConfigTree
from vyos.utils.process import cmd

STATUS_FILE = config_status
TRACE_FILE = '/tmp/boot-config-trace'

CFG_GROUP = 'vyattacfg'

trace_config = False

if 'log' in directories:
    LOG_DIR = directories['log']
else:
    LOG_DIR = '/var/log/vyatta'

LOG_FILE = LOG_DIR + '/vyos-boot-config-loader.log'

try:
    with open('/proc/cmdline', 'r') as f:
        cmdline = f.read()
    if 'vyos-debug' in cmdline:
        os.environ['VYOS_DEBUG'] = 'yes'
    if 'vyos-config-debug' in cmdline:
        os.environ['VYOS_DEBUG'] = 'yes'
        trace_config = True
except Exception as e:
    print('{0}'.format(e))

def write_config_status(status):
    try:
        with open(STATUS_FILE, 'w') as f:
            f.write('{0}\n'.format(status))
    except Exception as e:
        print('{0}'.format(e))

def trace_to_file(trace_file_name):
    try:
        with open(trace_file_name, 'w') as trace_file:
            traceback.print_exc(file=trace_file)
    except Exception as e:
        print('{0}'.format(e))

def failsafe(config_file_name):
    fail_msg = """
    !!!!!
    There were errors loading the configuration
    Please examine the errors in
    {0}
    and correct
    !!!!!
    """.format(TRACE_FILE)

    print(fail_msg, file=sys.stderr)

    users = [x[0] for x in pwd.getpwall()]
    if 'vyos' in users:
        return

    try:
        with open(config_file_name, 'r') as f:
            config_file = f.read()
    except Exception as e:
        print("Catastrophic: no default config file "
              "'{0}'".format(config_file_name))
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

    cmd(f"useradd --create-home --no-user-group --shell /bin/vbash --password '{passwd}' "\
        "--groups frr,frrvty,vyattacfg,sudo,adm,dip,disk vyos")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Must specify boot config file.")
        sys.exit(1)
    else:
        file_name = sys.argv[1]

    # Set user and group options, so that others will be able to commit
    # Currently, the only caller does 'sg CFG_GROUP', but that may change
    cfg_group = grp.getgrnam(CFG_GROUP)
    os.setgid(cfg_group.gr_gid)

    # Need to set file permissions to 775 so that every vyattacfg group
    # member has write access to the running config
    os.umask(0o002)

    session = ConfigSession(os.getpid(), 'vyos-boot-config-loader')
    env = session.get_session_env()

    default_file_name = env['vyatta_sysconfdir'] + '/config.boot.default'

    try:
        with open(file_name, 'r') as f:
            config_file = f.read()
    except Exception:
        write_config_status(1)
        if trace_config:
            failsafe(default_file_name)
            trace_to_file(TRACE_FILE)
        sys.exit(1)

    try:
        time_begin_load = datetime.now()
        load_out = session.load_config(file_name)
        time_end_load = datetime.now()
        time_begin_commit = datetime.now()
        commit_out = session.commit()
        time_end_commit = datetime.now()
        write_config_status(0)
    except ConfigSessionError:
        # If here, there is no use doing session.discard, as we have no
        # recoverable config environment, and will only throw an error
        write_config_status(1)
        if trace_config:
            failsafe(default_file_name)
            trace_to_file(TRACE_FILE)
        sys.exit(1)

    time_elapsed_load = time_end_load - time_begin_load
    time_elapsed_commit = time_end_commit - time_begin_commit

    try:
        if not os.path.exists(LOG_DIR):
            os.mkdir(LOG_DIR)
        with open(LOG_FILE, 'a') as f:
            f.write('\n\n')
            f.write('{0}    Begin config load\n'
                    ''.format(time_begin_load))
            f.write(load_out)
            f.write('{0}    End config load\n'
                    ''.format(time_end_load))
            f.write('Elapsed time for config load: {0}\n'
                    ''.format(time_elapsed_load))
            f.write('{0}    Begin config commit\n'
                    ''.format(time_begin_commit))
            f.write(commit_out)
            f.write('{0}    End config commit\n'
                    ''.format(time_end_commit))
            f.write('Elapsed time for config commit: {0}\n'
                    ''.format(time_elapsed_commit))
    except Exception as e:
        print('{0}'.format(e))
