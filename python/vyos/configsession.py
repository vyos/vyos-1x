# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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
import json
import weakref
import subprocess
from tempfile import NamedTemporaryFile
from typing import TypeAlias
from typing import Union

from vyos.defaults import directories
from vyos.utils.process import is_systemd_service_running
from vyos.utils.dict import dict_to_paths
from vyos.utils.boot import boot_configuration_complete
from vyos.utils.backend import vyconf_backend
from vyos.vyconf_session import VyconfSession
from vyos.base import Warning as Warn
from vyos.defaults import DEFAULT_COMMIT_CONFIRM_MINUTES
from vyos.configtree import ConfigTree
from vyos.configtree import ConfigTreeError
from vyos.configtree import delete_dict_from_masks
from vyos.derivedtree import subtree_from_list_of_partial_paths

# type of config file path or configtree
ConfigObj: TypeAlias = Union[str, ConfigTree]


CLI_SHELL_API = '/bin/cli-shell-api'
SET = '/opt/vyatta/sbin/my_set'
DELETE = '/opt/vyatta/sbin/my_delete'
COMMENT = '/opt/vyatta/sbin/my_comment'
COMMIT = '/opt/vyatta/sbin/my_commit'
COMMIT_CONFIRM = ['/usr/bin/config-mgmt', 'commit_confirm', '-y']
CONFIRM = ['/usr/bin/config-mgmt', 'confirm']
DISCARD = '/opt/vyatta/sbin/my_discard'
SHOW_CONFIG = ['/bin/cli-shell-api', 'showConfig']
LOAD_CONFIG = ['/bin/cli-shell-api', 'loadFile']
MIGRATE_LOAD_CONFIG = ['/usr/libexec/vyos/vyos-load-config.py']
MERGE_CONFIG = ['/usr/libexec/vyos/vyos-merge-config.py']
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
RENEW = ['/opt/vyatta/bin/vyatta-op-cmd-wrapper', 'renew']
POWEROFF = ['/opt/vyatta/bin/vyatta-op-cmd-wrapper', 'poweroff']
OP_CMD_ADD = ['/opt/vyatta/bin/vyatta-op-cmd-wrapper', 'add']
OP_CMD_DELETE = ['/opt/vyatta/bin/vyatta-op-cmd-wrapper', 'delete']
PING = ['/opt/vyatta/bin/vyatta-op-cmd-wrapper', 'ping']
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

    # with the retirement of the Cstore backend, this will remain as the
    # sole indication of legacy CLI config mode, as checked by VyconfSession
    env['_OFR_CONFIGURE'] = 'ok'

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

    def __init__(self, session_id, app=APP, shared=False):
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

        # replaces ambient instance of SESSION_PID,
        # for use when running from a non-shared configsession
        session_env['SESSION_PID'] = str(session_id)

        self.__session_env = session_env
        self.__session_env['COMMIT_VIA'] = app

        self.__run_command([CLI_SHELL_API, 'setupSession'])

        if vyconf_backend() and boot_configuration_complete():
            self._vyconf_session = VyconfSession(
                pid=session_id, on_error=ConfigSessionError
            )
        else:
            self._vyconf_session = None

        self.shared = shared
        self._finalizer = None
        self._rebind_vyconf_finalizer()

    def _rebind_vyconf_finalizer(self):
        """
        (Re)register weakref finalizer for the current VyconfSession.

        Call whenever self._vyconf_session is replaced so finalize_vyconf tears
        down the live session, not a stale object left from an earlier setup.
        """
        finalizer = getattr(self, '_finalizer', None)
        if finalizer is not None:
            finalizer.detach()
            self._finalizer = None
        if not getattr(self, 'shared', False) and self._vyconf_session is not None:
            self._finalizer = weakref.finalize(
                self, self.finalize_vyconf, self._vyconf_session
            )

        if not self.shared and not self._vyconf_session:
            self._finalizer = weakref.finalize(
                self, self.finalize_legacy, self.__session_env.copy()
            )

    @classmethod
    def finalize_vyconf(cls, session: VyconfSession):
        if session.session_changed():
            Warn('Exiting with uncommitted changes')
            session.discard()
        session.exit_config_mode()
        session.teardown()

    @classmethod
    def finalize_legacy(cls, session_env):
        try:
            output = (
                subprocess.check_output(
                    [CLI_SHELL_API, 'teardownSession'], env=session_env
                )
                .decode()
                .strip()
            )
            if output:
                print(
                    'cli-shell-api teardownSession output for session {0}: {1}'.format(
                        session_env['SESSION_PID'], output
                    ),
                    file=sys.stderr,
                )
        except Exception as e:
            print(
                'Could not tear down session {0}: {1}'.format(
                    session_env['SESSION_PID'], e
                ),
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

    def vyconf_backend(self) -> bool:
        return bool(self._vyconf_session)

    def session_exists(self) -> bool:
        """
        Return True if the underlying cli-shell-api config session is still live.

        Used by long-lived callers (HTTP API) that keep one ConfigSession for the
        process lifetime and must detect mid-life session death.
        """
        try:
            self.__run_command([CLI_SHELL_API, 'inSession'])
            return True
        except ConfigSessionError:
            return False

    def ensure_session(self) -> bool:
        """
        Ensure a live config session exists for this object.

        If the session has died, best-effort teardown and re-setup using the same
        session id / environment. Returns True if a live session is available
        after the call, False if re-setup failed (caller may recreate the object).
        """
        if self.session_exists():
            return True

        try:
            subprocess.check_output(
                [CLI_SHELL_API, 'teardownSession'],
                env=self.__session_env,
                stderr=subprocess.STDOUT,
            )
        except Exception:
            # Session may already be gone; continue to setup.
            pass

        try:
            self.__run_command([CLI_SHELL_API, 'setupSession'])
            if vyconf_backend() and boot_configuration_complete():
                self._vyconf_session = VyconfSession(
                    pid=self.__session_id, on_error=ConfigSessionError
                )
            else:
                self._vyconf_session = None
            # Detach any finalizer bound to a previous VyconfSession and bind
            # one for the replacement (or none if vyconf is off).
            self._rebind_vyconf_finalizer()
            return self.session_exists()
        except ConfigSessionError:
            return False

    def set(self, path, value=None):
        if not value:
            value = []
        else:
            value = [value]
        if self._vyconf_session is None:
            self.__run_command([SET] + path + value)
        else:
            self._vyconf_session.set(path + value)

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
        if self._vyconf_session is None:
            self.__run_command([DELETE] + path + value)
        else:
            self._vyconf_session.delete(path + value)

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

    def load_section_tree(
        self, config_tree: ConfigTree, mask_dict: dict, config_dict: dict
    ):
        if (
            not mask_dict
            or 'inclusive' not in mask_dict
            or 'exclusive' not in mask_dict
        ):
            raise ConfigSessionError(
                "Missing mask data can damage the config: expected keys 'inclusive' and 'exclusive'"
            )
        try:
            mask_in = ConfigTree(internal_string=mask_dict['inclusive'])

            mask_ex_list = json.loads(mask_dict['exclusive'])
            mask_ex = subtree_from_list_of_partial_paths(config_tree, mask_ex_list)

            delete_dict = delete_dict_from_masks(config_tree, mask_in, mask_ex)

            if delete_dict:
                for p in dict_to_paths(delete_dict):
                    self.delete(p)

            if config_dict:
                for p in dict_to_paths(config_dict):
                    self.set(p)
        except (ValueError, ConfigSessionError, ConfigTreeError) as e:
            raise ConfigSessionError(e)

    def comment(self, path, value=None):
        if not value:
            value = ['']
        else:
            value = [value]
        self.__run_command([COMMENT] + path + value)

    def commit(self):
        if self._vyconf_session is None:
            out = self.__run_command([COMMIT])
        else:
            out, _ = self._vyconf_session.commit()

        return out

    def commit_confirm(self, minutes: int = DEFAULT_COMMIT_CONFIRM_MINUTES):
        out = self.__run_command(COMMIT_CONFIRM + [f'-t {minutes}'])

        return out

    def confirm(self):
        out = self.__run_command(CONFIRM)

        return out

    def discard(self):
        try:
            if self._vyconf_session is None:
                self.__run_command([DISCARD])
            else:
                self._vyconf_session.discard()
        except ConfigSessionError as e:
            # Dead session: discard must not cascade a second error (HTTP API
            # error paths always call discard; re-raising turns a 400 into 500).
            if 'without config session' in str(e):
                return
            raise

    def show_config(self, path, format='raw'):
        if self._vyconf_session is None:
            config_data = self.__run_command(SHOW_CONFIG + path)
        else:
            config_data, _ = self._vyconf_session.show_config(path)

        if format == 'raw':
            return config_data

    def load_config(self, file_path, cached: bool = False):
        if self._vyconf_session is None:
            out = self.__run_command(LOAD_CONFIG + [file_path])
        else:
            out, _ = self._vyconf_session.load_config(
                file_name=file_path, cached=cached
            )

        return out

    def load_explicit(self, file_path):
        from vyos.load_config import load
        from vyos.load_config import LoadConfigError

        try:
            load(file_path, switch='explicit')
        except LoadConfigError as e:
            raise ConfigSessionError(e) from e

    def load_config_obj(self, config_obj: ConfigObj):
        if isinstance(config_obj, ConfigTree):
            with NamedTemporaryFile() as f:
                config_obj.write_cache(f.name)
                self.load_config(f.name, cached=True)
        else:
            self.load_config(config_obj)

    def migrate_and_load_config(self, file_path):
        if self._vyconf_session is None:
            out = self.__run_command(MIGRATE_LOAD_CONFIG + [file_path])
        else:
            out, _ = self._vyconf_session.load_config(file_name=file_path, migrate=True)

        return out

    def merge_config(self, file_path, destructive=False):
        if self._vyconf_session is None:
            destr = ['--destructive'] if destructive else []
            out = self.__run_command(MERGE_CONFIG + [file_path] + destr)
        else:
            out, _ = self._vyconf_session.merge_config(
                file_name=file_path, destructive=destructive
            )

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

    def renew(self, path):
        out = self.__run_command(RENEW + path)
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

    def ping(self, host, count: int = 5, vrf: str | None = None):
        cmd = PING + [host, 'count', str(count)]
        if vrf is not None:
            cmd += ['vrf', vrf]
        out = self.__run_command(cmd)
        return out

    def traceroute(self, host, vrf: str | None = None):
        cmd = TRACEROUTE + [host]
        if vrf is not None:
            cmd += ['--vrf', vrf]
        out = self.__run_command(cmd)
        return out
