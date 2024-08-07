
# Copyright 2020-2023 VyOS maintainers and contributors <maintainers@vyos.io>
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

import os
import re
import subprocess

from vyos.configtree import ConfigTree
from vyos.utils.boot import boot_configuration_complete

class VyOSError(Exception):
    """
    Raised on config access errors.
    """
    pass

class ConfigSourceError(Exception):
    '''
    Raised on error in ConfigSource subclass init.
    '''
    pass

class ConfigSource:
    def __init__(self):
        self._running_config: ConfigTree = None
        self._session_config: ConfigTree = None

    def get_configtree_tuple(self):
        return self._running_config, self._session_config

    def session_changed(self):
        """
        Returns:
            True if the config session has uncommited changes, False otherwise.
        """
        raise NotImplementedError(f"function not available for {type(self)}")

    def in_session(self):
        """
        Returns:
            True if called from a configuration session, False otherwise.
        """
        raise NotImplementedError(f"function not available for {type(self)}")

    def show_config(self, path=[], default=None, effective=False):
        """
        Args:
            path (str|list): Configuration tree path, or empty
            default (str): Default value to return

        Returns:
            str: working configuration
        """
        raise NotImplementedError(f"function not available for {type(self)}")

    def is_multi(self, path):
        """
        Args:
            path (str): Configuration tree path

        Returns:
            True if a node can have multiple values, False otherwise.

        Note:
            It also returns False if node doesn't exist.
        """
        raise NotImplementedError(f"function not available for {type(self)}")

    def is_tag(self, path):
        """
         Args:
            path (str): Configuration tree path

        Returns:
            True if a node is a tag node, False otherwise.

        Note:
            It also returns False if node doesn't exist.
        """
        raise NotImplementedError(f"function not available for {type(self)}")

    def is_leaf(self, path):
        """
         Args:
            path (str): Configuration tree path

        Returns:
            True if a node is a leaf node, False otherwise.

        Note:
            It also returns False if node doesn't exist.
        """
        raise NotImplementedError(f"function not available for {type(self)}")

class ConfigSourceSession(ConfigSource):
    def __init__(self, session_env=None):
        super().__init__()
        self._cli_shell_api = "/bin/cli-shell-api"
        self._level = []
        if session_env:
            self.__session_env = session_env
        else:
            self.__session_env = None

        # Running config can be obtained either from op or conf mode, it always succeeds
        # once the config system is initialized during boot;
        # before initialization, set to empty string
        if boot_configuration_complete():
            try:
                running_config_text = self._run([self._cli_shell_api, '--show-active-only', '--show-show-defaults', '--show-ignore-edit', 'showConfig'])
            except VyOSError:
                running_config_text = ''
        else:
            running_config_text = ''

        # Session config ("active") only exists in conf mode.
        # In op mode, we'll just use the same running config for both active and session configs.
        if self.in_session():
            try:
                session_config_text = self._run([self._cli_shell_api, '--show-working-only', '--show-show-defaults', '--show-ignore-edit', 'showConfig'])
            except VyOSError:
                session_config_text = ''
        else:
            session_config_text = running_config_text

        if running_config_text:
            self._running_config = ConfigTree(running_config_text)
        else:
            self._running_config = None

        if session_config_text:
            self._session_config = ConfigTree(session_config_text)
        else:
            self._session_config = None

    def _make_command(self, op, path):
        args = path.split()
        cmd = [self._cli_shell_api, op] + args
        return cmd

    def _run(self, cmd):
        if self.__session_env:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, env=self.__session_env)
        else:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        out = p.stdout.read()
        p.wait()
        p.communicate()
        if p.returncode != 0:
            raise VyOSError()
        else:
            return out.decode()

    def set_level(self, path):
        """
        Set the *edit level*, that is, a relative config tree path.
        Once set, all operations will be relative to this path,
        for example, after ``set_level("system")``, calling
        ``exists("name-server")`` is equivalent to calling
        ``exists("system name-server"`` without ``set_level``.

        Args:
            path (str|list): relative config path
        """
        # Make sure there's always a space between default path (level)
        # and path supplied as method argument
        # XXX: for small strings in-place concatenation is not a problem
        if isinstance(path, str):
            if path:
                self._level = re.split(r'\s+', path)
            else:
                self._level = []
        elif isinstance(path, list):
            self._level = path.copy()
        else:
            raise TypeError("Level path must be either a whitespace-separated string or a list")

    def session_changed(self):
        """
        Returns:
            True if the config session has uncommited changes, False otherwise.
        """
        try:
            self._run(self._make_command('sessionChanged', ''))
            return True
        except VyOSError:
            return False

    def in_session(self):
        """
        Returns:
            True if called from a configuration session, False otherwise.
        """
        if os.getenv('VYOS_CONFIGD', ''):
            return False
        try:
            self._run(self._make_command('inSession', ''))
            return True
        except VyOSError:
            return False

    def show_config(self, path=[], default=None, effective=False):
        """
        Args:
            path (str|list): Configuration tree path, or empty
            default (str): Default value to return

        Returns:
            str: working configuration
        """

        # show_config should be independent of CLI edit level.
        # Set the CLI edit environment to the top level, and
        # restore original on exit.
        save_env = self.__session_env

        env_str = self._run(self._make_command('getEditResetEnv', ''))
        env_list = re.findall(r'([A-Z_]+)=\'([^;\s]+)\'', env_str)
        root_env = os.environ
        for k, v in env_list:
            root_env[k] = v

        self.__session_env = root_env

        # FIXUP: by default, showConfig will give you a diff
        # if there are uncommitted changes.
        # The config parser obviously cannot work with diffs,
        # so we need to supress diff production using appropriate
        # options for getting either running (active)
        # or proposed (working) config.
        if effective:
            path = ['--show-active-only'] + path
        else:
            path = ['--show-working-only'] + path

        if isinstance(path, list):
            path = " ".join(path)
        try:
            out = self._run(self._make_command('showConfig', path))
            self.__session_env = save_env
            return out
        except VyOSError:
            self.__session_env = save_env
            return(default)

    def is_multi(self, path):
        """
        Args:
            path (str): Configuration tree path

        Returns:
            True if a node can have multiple values, False otherwise.

        Note:
            It also returns False if node doesn't exist.
        """
        try:
            path = " ".join(self._level) + " " + path
            self._run(self._make_command('isMulti', path))
            return True
        except VyOSError:
            return False

    def is_tag(self, path):
        """
         Args:
            path (str): Configuration tree path

        Returns:
            True if a node is a tag node, False otherwise.

        Note:
            It also returns False if node doesn't exist.
        """
        try:
            path = " ".join(self._level) + " " + path
            self._run(self._make_command('isTag', path))
            return True
        except VyOSError:
            return False

    def is_leaf(self, path):
        """
         Args:
            path (str): Configuration tree path

        Returns:
            True if a node is a leaf node, False otherwise.

        Note:
            It also returns False if node doesn't exist.
        """
        try:
            path = " ".join(self._level) + " " + path
            self._run(self._make_command('isLeaf', path))
            return True
        except VyOSError:
            return False

class ConfigSourceString(ConfigSource):
    def __init__(self, running_config_text=None, session_config_text=None):
        super().__init__()

        try:
            self._running_config = ConfigTree(running_config_text) if running_config_text else None
            self._session_config = ConfigTree(session_config_text) if session_config_text else None
        except ValueError:
            raise ConfigSourceError(f"Init error in {type(self)}")
