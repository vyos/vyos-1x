# Copyright (C) 2019-2024 VyOS maintainers and contributors
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

# configsession -- the write API for the VyOS running config

import os
import re
import sys
import subprocess

from vyos.defaults import directories
from vyos.utils.process import is_systemd_service_running
from vyos.utils.dict import dict_to_paths

CLI_SHELL_API = '/bin/cli-shell-api'
SET = '/opt/vyatta/sbin/my_set'
DELETE = '/opt/vyatta/sbin/my_delete'
COMMENT = '/opt/vyatta/sbin/my_comment'
COMMIT = '/opt/vyatta/sbin/my_commit'
DISCARD = '/opt/vyatta/sbin/my_discard'
SHOW_CONFIG = ['/bin/cli-shell-api', 'showConfig']
LOAD_CONFIG = ['/bin/cli-shell-api', 'loadFile']
MIGRATE_LOAD_CONFIG = ['/usr/libexec/vyos/vyos-load-config.py']
SAVE_CONFIG = ['/usr/libexec/vyos/vyos-save-config.py']
INSTALL_IMAGE = [
    '/usr/libexec/vyos/op_mode/image_installer.py',
    '--action',
    'add',
    '--no-prompt',
    '--image-path',
]
IMPORT_PKI = ['/opt/vyatta/bin/vyatta-op-cmd-wrapper', 'import']
IMPORT_PKI_NO_PROMPT = [
    '/usr/libexec/vyos/op_mode/pki.py',
    'import_pki',
    '--no-prompt',
]
REMOVE_IMAGE = [
    '/usr/libexec/vyos/op_mode/image_manager.py',
    '--action',
    'delete',
    '--no-prompt',
    '--image-name',
]
SET_DEFAULT_IMAGE = [
    '/usr/libexec/vyos/op_mode/image_manager.py',
    '--action',
    'set',
    '--no-prompt',
    '--image-name',
]
GENERATE = ['/opt/vyatta/bin/vyatta-op-cmd-wrapper', 'generate']
SHOW = ['/opt/vyatta/bin/vyatta-op-cmd-wrapper', 'show']
RESET = ['/opt/vyatta/bin/vyatta-op-cmd-wrapper', 'reset']
REBOOT = ['/opt/vyatta/bin/vyatta-op-cmd-wrapper', 'reboot']
POWEROFF = ['/opt/vyatta/bin/vyatta-op-cmd-wrapper', 'poweroff']
OP_CMD_ADD = ['/opt/vyatta/bin/vyatta-op-cmd-wrapper', 'add']
OP_CMD_DELETE = ['/opt/vyatta/bin/vyatta-op-cmd-wrapper', 'delete']
TRACEROUTE = [
    '/usr/libexec/vyos/op_mode/mtr_execute.py',
    'mtr',
    '--for-api',
    '--report-mode',
    '--report-cycles',
    '1',
    '--json',
    '--host',
]

# Default "commit via" string
APP = 'vyos-http-api'


# When started as a service rather than from a user shell,
# the process lacks the VyOS-specific environment that comes
# from bash configs, so we have to inject it
# XXX: maybe it's better to do via a systemd environment file
def inject_vyos_env(env):
    env['VYATTA_CFG_GROUP_NAME'] = 'vyattacfg'
    env['VYATTA_USER_LEVEL_DIR'] = '/opt/vyatta/etc/shell/level/admin'
    env['VYATTA_PROCESS_CLIENT'] = 'gui2_rest'
    env['VYOS_HEADLESS_CLIENT'] = 'vyos_http_api'
    env['vyatta_bindir'] = '/opt/vyatta/bin'
    env['vyatta_cfg_templates'] = '/opt/vyatta/share/vyatta-cfg/templates'
    env['vyatta_configdir'] = directories['vyos_configdir']
    env['vyatta_datadir'] = '/opt/vyatta/share'
    env['vyatta_datarootdir'] = '/opt/vyatta/share'
    env['vyatta_libdir'] = '/opt/vyatta/lib'
    env['vyatta_libexecdir'] = '/opt/vyatta/libexec'
    env['vyatta_op_templates'] = '/opt/vyatta/share/vyatta-op/templates'
    env['vyatta_prefix'] = '/opt/vyatta'
    env['vyatta_sbindir'] = '/opt/vyatta/sbin'
    env['vyatta_sysconfdir'] = '/opt/vyatta/etc'
    env['vyos_bin_dir'] = '/usr/bin'
    env['vyos_cfg_templates'] = '/opt/vyatta/share/vyatta-cfg/templates'
    env['vyos_completion_dir'] = '/usr/libexec/vyos/completion'
    env['vyos_configdir'] = directories['vyos_configdir']
    env['vyos_conf_scripts_dir'] = '/usr/libexec/vyos/conf_mode'
    env['vyos_datadir'] = '/opt/vyatta/share'
    env['vyos_datarootdir'] = '/opt/vyatta/share'
    env['vyos_libdir'] = '/opt/vyatta/lib'
    env['vyos_libexec_dir'] = '/usr/libexec/vyos'
    env['vyos_op_scripts_dir'] = '/usr/libexec/vyos/op_mode'
    env['vyos_op_templates'] = '/opt/vyatta/share/vyatta-op/templates'
    env['vyos_prefix'] = '/opt/vyatta'
    env['vyos_sbin_dir'] = '/usr/sbin'
    env['vyos_validators_dir'] = '/usr/libexec/vyos/validators'

    # if running the vyos-configd daemon, inject the vyshim env var
    if is_systemd_service_running('vyos-configd.service'):
        env['vyshim'] = '/usr/sbin/vyshim'

    return env


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

        env_str = subprocess.check_output(
            [CLI_SHELL_API, 'getSessionEnv', str(session_id)]
        )
        self.__session_id = session_id

        # Extract actual variables from the chunk of shell it outputs
        # XXX: it's better to extend cli-shell-api to provide easily readable output
        env_list = re.findall(r'([A-Z_]+)=([^;\s]+)', env_str.decode())

        session_env = os.environ
        session_env = inject_vyos_env(session_env)
        for k, v in env_list:
            session_env[k] = v

        self.__session_env = session_env
        self.__session_env['COMMIT_VIA'] = app

        self.__run_command([CLI_SHELL_API, 'setupSession'])

    def __del__(self):
        try:
            output = (
                subprocess.check_output(
                    [CLI_SHELL_API, 'teardownSession'], env=self.__session_env
                )
                .decode()
                .strip()
            )
            if output:
                print(
                    'cli-shell-api teardownSession output for sesion {0}: {1}'.format(
                        self.__session_id, output
                    ),
                    file=sys.stderr,
                )
        except Exception as e:
            print(
                'Could not tear down session {0}: {1}'.format(self.__session_id, e),
                file=sys.stderr,
            )

    def __run_command(self, cmd_list):
        p = subprocess.Popen(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=self.__session_env,
        )
        (stdout_data, stderr_data) = p.communicate()
        output = stdout_data.decode()
        result = p.wait()
        if result != 0:
            raise ConfigSessionError(output)
        return output

    def get_session_env(self):
        return self.__session_env

    def set(self, path, value=None):
        if not value:
            value = []
        else:
            value = [value]
        self.__run_command([SET] + path + value)

    def set_section(self, path: list, d: dict):
        try:
            for p in dict_to_paths(d):
                self.set(path + p)
        except (ValueError, ConfigSessionError) as e:
            raise ConfigSessionError(e)

    def delete(self, path, value=None):
        if not value:
            value = []
        else:
            value = [value]
        self.__run_command([DELETE] + path + value)

    def load_section(self, path: list, d: dict):
        try:
            self.delete(path)
            if d:
                for p in dict_to_paths(d):
                    self.set(path + p)
        except (ValueError, ConfigSessionError) as e:
            raise ConfigSessionError(e)

    def set_section_tree(self, d: dict):
        try:
            if d:
                for p in dict_to_paths(d):
                    self.set(p)
        except (ValueError, ConfigSessionError) as e:
            raise ConfigSessionError(e)

    def load_section_tree(self, mask: dict, d: dict):
        try:
            if mask:
                for p in dict_to_paths(mask):
                    self.delete(p)
            if d:
                for p in dict_to_paths(d):
                    self.set(p)
        except (ValueError, ConfigSessionError) as e:
            raise ConfigSessionError(e)

    def comment(self, path, value=None):
        if not value:
            value = ['']
        else:
            value = [value]
        self.__run_command([COMMENT] + path + value)

    def commit(self):
        out = self.__run_command([COMMIT])
        return out

    def discard(self):
        self.__run_command([DISCARD])

    def show_config(self, path, format='raw'):
        config_data = self.__run_command(SHOW_CONFIG + path)

        if format == 'raw':
            return config_data

    def load_config(self, file_path):
        out = self.__run_command(LOAD_CONFIG + [file_path])
        return out

    def load_explicit(self, file_path):
        from vyos.load_config import load
        from vyos.load_config import LoadConfigError

        try:
            load(file_path, switch='explicit')
        except LoadConfigError as e:
            raise ConfigSessionError(e) from e

    def migrate_and_load_config(self, file_path):
        out = self.__run_command(MIGRATE_LOAD_CONFIG + [file_path])
        return out

    def save_config(self, file_path):
        out = self.__run_command(SAVE_CONFIG + [file_path])
        return out

    def install_image(self, url):
        out = self.__run_command(INSTALL_IMAGE + [url])
        return out

    def remove_image(self, name):
        out = self.__run_command(REMOVE_IMAGE + [name])
        return out

    def import_pki(self, path):
        out = self.__run_command(IMPORT_PKI + path)
        return out

    def import_pki_no_prompt(self, path):
        out = self.__run_command(IMPORT_PKI_NO_PROMPT + path)
        return out

    def set_default_image(self, name):
        out = self.__run_command(SET_DEFAULT_IMAGE + [name])
        return out

    def generate(self, path):
        out = self.__run_command(GENERATE + path)
        return out

    def show(self, path):
        out = self.__run_command(SHOW + path)
        return out

    def reboot(self, path):
        out = self.__run_command(REBOOT + path)
        return out

    def reset(self, path):
        out = self.__run_command(RESET + path)
        return out

    def poweroff(self, path):
        out = self.__run_command(POWEROFF + path)
        return out

    def add_container_image(self, name):
        out = self.__run_command(OP_CMD_ADD + ['container', 'image'] + [name])
        return out

    def delete_container_image(self, name):
        out = self.__run_command(OP_CMD_DELETE + ['container', 'image'] + [name])
        return out

    def show_container_image(self):
        out = self.__run_command(SHOW + ['container', 'image'])
        return out

    def traceroute(self, host):
        out = self.__run_command(TRACEROUTE + [host])
        return out
