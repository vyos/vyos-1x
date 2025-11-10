# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>.
#
#

import os
import weakref
import tempfile
import json
from functools import wraps
from typing import Type

from vyos.proto import vyconf_client
from vyos.migrate import ConfigMigrate
from vyos.migrate import ConfigMigrateError
from vyos.component_version import append_system_version
from vyos.utils.session import in_config_session
from vyos.proto.vyconf_proto import Errnum
from vyos.utils.commit import acquire_commit_lock_file
from vyos.utils.commit import release_commit_lock_file
from vyos.utils.commit import call_commit_hooks
from vyos.remote import get_config_file


class VyconfSessionError(Exception):
    pass


def new_session(pid: int, sudo_user: str, user: str):
    out = vyconf_client.send_request(
        'setup_session',
        client_pid=pid,
        client_sudo_user=sudo_user,
        client_user=user,
    )
    return out.output


class VyconfSession:
    def __init__(
        self,
        pid: int = None,
        token: str = None,
        extant=False,
        on_error: Type[Exception] = None,
    ):
        self.pid = pid if pid else os.getpid()
        self.sudo_user = os.environ.get('SUDO_USER', None)
        self.user = os.environ.get('USER', None)

        self.in_config_session = in_config_session()

        match token:
            case None:
                # config-mode sessions are persistent, and managed by caller (CLI or ConfigSession)
                #
                # op-mode sessions are ephemeral, unless forced with extant=True:
                # --- open a new session on init; teardown in finalizer
                if self.in_config_session:
                    out = vyconf_client.send_request(
                        'session_of_pid', client_pid=self.pid
                    )
                    if out.output is None:
                        self.__token = new_session(self.pid, self.sudo_user, self.user)
                        out = vyconf_client.send_request(
                            'enter_configuration_mode', token=self.__token
                        )
                        if out.status:
                            raise VyconfSessionError(self.output(out))
                    else:
                        self.__token = out.output
                else:
                    if not extant:
                        self.__token = new_session(self.pid, self.sudo_user, self.user)
                    else:
                        out = vyconf_client.send_request(
                            'session_of_pid', client_pid=self.pid
                        )
                        if out.output is None:
                            raise ValueError(f'No existing session for pid {self.pid}')
                        self.__token = out.output
            case _:
                out = vyconf_client.send_request('session_exists', token=token)
                if out.status:
                    raise ValueError(f'No existing session for token: {token}')
                self.__token = token

        if not self.in_config_session and not extant:
            self._finalizer = weakref.finalize(self, self._teardown, self.__token)

        self.on_error = on_error

    @classmethod
    def _teardown(cls, token):
        vyconf_client.send_request('teardown', token)

    def teardown(self):
        self._teardown(self.__token)

    def exit_config_mode(self):
        if self.session_changed():
            return 'Uncommited changes', Errnum.UNCOMMITED_CHANGES
        out = vyconf_client.send_request('exit_configuration_mode', token=self.__token)
        return self.output(out), out.status

    def in_session(self) -> bool:
        return self.in_config_session

    def session_changed(self) -> bool:
        out = vyconf_client.send_request('session_changed', token=self.__token)
        return not bool(out.status)

    def get_config(self):
        out = vyconf_client.send_request('get_config', token=self.__token)
        if out.status:
            raise VyconfSessionError(self.output(out))
        return out.output

    def show_sessions(
        self, exclude_self: bool = False, exclude_other: bool = False
    ) -> list | dict:
        out = vyconf_client.send_request(
            'show_sessions',
            token=self.__token,
            exclude_self=exclude_self,
            exclude_other=exclude_other,
        )

        lst = json.loads(out.output)
        if len(lst) == 1:
            return lst[0]
        return lst

    @staticmethod
    def config_mode(f):
        @wraps(f)
        def wrapped(self, *args, **kwargs):
            msg = 'operation not available outside of config mode'
            if not self.in_config_session:
                if self.on_error is None:
                    raise VyconfSessionError(msg)
                raise self.on_error(msg)
            return f(self, *args, **kwargs)

        return wrapped

    @staticmethod
    def raise_exception(f):
        @wraps(f)
        def wrapped(self, *args, **kwargs):
            if self.on_error is None:
                return f(self, *args, **kwargs)
            o, e = f(self, *args, **kwargs)
            if e:
                raise self.on_error(o)
            return o, e

        return wrapped

    @staticmethod
    def output(o):
        out = ''
        for res in (o.output, o.error, o.warning):
            if res is not None:
                out = out + res
        return out

    @config_mode
    def discard(self) -> tuple[str, int]:
        out = vyconf_client.send_request('discard', token=self.__token)
        return self.output(out), out.status

    @raise_exception
    @config_mode
    def set(self, path: list[str]) -> tuple[str, int]:
        out = vyconf_client.send_request('set', token=self.__token, path=path)
        return self.output(out), out.status

    @raise_exception
    @config_mode
    def delete(self, path: list[str]) -> tuple[str, int]:
        out = vyconf_client.send_request('delete', token=self.__token, path=path)
        return self.output(out), out.status

    @raise_exception
    def aux_set(
        self, path: list[str], script_name: str, tag_value: str = None
    ) -> tuple[str, int]:
        out = vyconf_client.send_request(
            'aux_set',
            token=self.__token,
            path=path,
            script_name=script_name,
            tag_value=tag_value,
        )
        return self.output(out), out.status

    @raise_exception
    def aux_delete(
        self, path: list[str], script_name: str, tag_value: str = None
    ) -> tuple[str, int]:
        out = vyconf_client.send_request(
            'aux_delete',
            token=self.__token,
            path=path,
            script_name=script_name,
            tag_value=tag_value,
        )
        return self.output(out), out.status

    @raise_exception
    @config_mode
    def commit(self) -> tuple[str, int]:
        if not self.session_changed():
            out = 'No changes to commit'
            return out, 0

        lock_fd, out = acquire_commit_lock_file()
        if lock_fd is None:
            return out, Errnum.COMMIT_IN_PROGRESS

        pre_out, _ = call_commit_hooks('pre')
        out = vyconf_client.send_request('commit', token=self.__token)
        os.environ['COMMIT_STATUS'] = 'FAILURE' if out.status else 'SUCCESS'
        post_out, _ = call_commit_hooks('post')

        release_commit_lock_file(lock_fd)

        return pre_out + self.output(out) + post_out, out.status

    @raise_exception
    @config_mode
    def load_config(
        self, file_name: str, migrate: bool = False, cached: bool = False
    ) -> tuple[str, int]:
        # pylint: disable=consider-using-with
        file_path = tempfile.NamedTemporaryFile(delete=False).name
        err = get_config_file(file_name, file_path)
        if err:
            os.remove(file_path)
            return str(err), Errnum.INVALID_VALUE
        if not cached:
            if migrate:
                config_migrate = ConfigMigrate(file_path)
                try:
                    config_migrate.run()
                except ConfigMigrateError as e:
                    os.remove(file_path)
                    return repr(e), 1

        out = vyconf_client.send_request(
            'load', token=self.__token, location=file_path, cached=cached
        )

        if not cached:
            os.remove(file_path)

        return self.output(out), out.status

    @raise_exception
    @config_mode
    def merge_config(
        self, file_name: str, migrate: bool = False, destructive: bool = False
    ) -> tuple[str, int]:
        # pylint: disable=consider-using-with
        file_path = tempfile.NamedTemporaryFile(delete=False).name
        err = get_config_file(file_name, file_path)
        if err:
            os.remove(file_path)
            return str(err), Errnum.INVALID_VALUE
        if migrate:
            config_migrate = ConfigMigrate(file_path)
            try:
                config_migrate.run()
            except ConfigMigrateError as e:
                os.remove(file_path)
                return repr(e), 1

        out = vyconf_client.send_request(
            'merge', token=self.__token, location=file_path, destructive=destructive
        )

        os.remove(file_path)

        return self.output(out), out.status

    @raise_exception
    def save_config(self, file: str, append_version: bool = False) -> tuple[str, int]:
        file = os.path.realpath(file)
        out = vyconf_client.send_request('save', token=self.__token, location=file)
        if append_version:
            append_system_version(file)
        return self.output(out), out.status

    @raise_exception
    def show_config(self, path: list[str] = None) -> tuple[str, int]:
        if path is None:
            path = []
        out = vyconf_client.send_request('show_config', token=self.__token, path=path)
        return self.output(out), out.status
