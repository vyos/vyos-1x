# configsession -- the write API for the VyOS running config
# Copyright (C) 2019 VyOS maintainers and contributors
#
# This library is free software; you can redistribute it and/or modify it under the terms of
# the GNU Lesser General Public License as published by the Free Software Foundation;
# either version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along with this library;
# if not, write to the Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA 

import os
import re
import subprocess

CLI_SHELL_API = '/bin/cli-shell-api'
SET = '/opt/vyatta/sbin/my_set'
DELETE = '/opt/vyatta/sbin/my_delete'
COMMENT = '/opt/vyatta/sbin/my_comment'
COMMIT = '/opt/vyatta/sbin/my_commit'

APP = "vyos-api"


class ConfigSessionError(Exception):
    pass


class ConfigSession(object):
    """
    The write API of VyOS.
    """
    def __init__(self, session_id, app=APP):
        """
         Creates a new config session.

         Args:
              session_id (str): Session identifier
              app (str): Application name, purely informational

        Note:
            The session identifier MUST be globally unique within the system.
            The best practice is to only have one ConfigSession object per process
            and used the PID for the session identifier.
        """

        env_str = subprocess.check_output([CLI_SHELL_API, 'getSessionEnv', str(session_id)])

        # Extract actual variables from the chunk of shell it outputs
        # XXX: it's better to extend cli-shell-api to provide easily readable output
        env_list = re.findall(r'([A-Z_]+)=([^;\s]+)', env_str.decode())

        session_env = os.environ
        for k, v in env_list:
            session_env[k] = v

        self.__session_env = session_env
        self.__session_env["COMMIT_VIA"] = app

        self.__run_command([CLI_SHELL_API, 'setupSession'])

    def __run_command(self, cmd_list):
        p = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=self.__session_env)
        result = p.wait()
        output = p.stdout.read().decode()
        if result != 0:
            raise ConfigSessionError(output)

    def set(self, path, value=None):
        if not value:
            value = []
        else:
            value = [value]
        self.__run_command([SET] + path + value)

    def delete(self, path, value=None):
        if not value:
            value = []
        else:
            value = [value]
        self.__run_command([DELETE] + path + value)

    def comment(self, path, value=None):
        if not value:
            value = [""]
        else:
            value = [value]
        self.__run_command([COMMENT] + path + value)

    def commit(self):
        self.__run_command([COMMIT])
