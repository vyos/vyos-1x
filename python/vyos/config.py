# Copyright 2017, 2019 VyOS maintainers and contributors <maintainers@vyos.io>
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
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

"""
A library for reading VyOS running config data.

This library is used internally by all config scripts of VyOS,
but its API should be considered stable and safe to use
in user scripts.

Note that this module will not work outside VyOS.

Node taxonomy
#############

There are multiple types of config tree nodes in VyOS, each requires
its own set of operations.

*Leaf nodes* (such as "address" in interfaces) can have values, but cannot
have children. 
Leaf nodes can have one value, multiple values, or no values at all.

For example, "system host-name" is a single-value leaf node,
"system name-server" is a multi-value leaf node (commonly abbreviated "multi node"),
and "system ip disable-forwarding" is a valueless leaf node.

Non-leaf nodes cannot have values, but they can have child nodes. They are divided into
two classes depending on whether the names of their children are fixed or not.
For example, under "system", the names of all valid child nodes are predefined
("login", "name-server" etc.).

To the contrary, children of the "system task-scheduler task" node can have arbitrary names.
Such nodes are called *tag nodes*. This terminology is confusing but we keep using it for lack
of a better word. No one remembers if the "tag" in "task Foo" is "task" or "Foo",
but the distinction is irrelevant in practice.

Configuration modes
###################

VyOS has two distinct modes: operational mode and configuration mode. When a user logins,
the CLI is in the operational mode. In this mode, only the running (effective) config is accessible for reading.

When a user enters the "configure" command, a configuration session is setup. Every config session
has its *proposed* (or *session*) config built on top of the current running config. When changes are commited, if commit succeeds,
the proposed config is merged into the running config.

In configuration mode, "base" functions like `exists`, `return_value` return values from the session config,
while functions prefixed "effective" return values from the running config.

In operational mode, all functions return values from the running config.

"""

import os
import re
import json
import subprocess

import vyos.configtree


class VyOSError(Exception):
    """
    Raised on config access errors, most commonly if the type of a config tree node
    in the system does not match the type of operation.

    """
    pass


class Config(object):
    """
    The class of config access objects.

    Internally, in the current implementation, this object is *almost* stateless,
    the only state it keeps is relative *config path* for convenient access to config
    subtrees.
    """
    def __init__(self, session_env=None):
        self._cli_shell_api = "/bin/cli-shell-api"
        self._level = []
        if session_env:
            self.__session_env = session_env
        else:
            self.__session_env = None

        # Running config can be obtained either from op or conf mode, it always succeeds
        # (if config system is initialized at all).
        if os.path.isfile('/tmp/vyos-config-status'):
            running_config_text = self._run([self._cli_shell_api, '--show-active-only', '--show-show-defaults', '--show-ignore-edit', 'showConfig'])
        else:
            with open('/opt/vyatta/etc/config/config.boot') as f:
                running_config_text = f.read()

        # Session config ("active") only exists in conf mode.
        # In op mode, we'll just use the same running config for both active and session configs.
        if self.in_session():
            session_config_text = self._run([self._cli_shell_api, '--show-working-only', '--show-show-defaults', '--show-ignore-edit', 'showConfig'])
        else:
            session_config_text = running_config_text

        self._session_config = vyos.configtree.ConfigTree(session_config_text)
        self._running_config = vyos.configtree.ConfigTree(running_config_text)

    def _make_command(self, op, path):
        args = path.split()
        cmd = [self._cli_shell_api, op] + args
        return cmd

    def _make_path(self, path):
        # Backwards-compatibility stuff: original implementation used string paths
        # libvyosconfig paths are lists, but since node names cannot contain whitespace,
        # splitting at whitespace is reasonably safe.
        # It may cause problems with exists() when it's used for checking values,
        # since values may contain whitespace.
        if isinstance(path, str):
            path = re.split(r'\s+', path)
        elif isinstance(path, list):
            pass
        else:
            raise TypeError("Path must be a whitespace-separated string or a list")
        return (self._level + path)

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
            return out.decode('ascii')

    def set_level(self, path):
        """
        Set the *edit level*, that is, a relative config tree path.
        Once set, all operations will be relative to this path,
        for example, after ``set_level("system")``, calling
        ``exists("name-server")`` is equivalent to calling
        ``exists("system name-server"`` without ``set_level``.

        Args:
            path (str): relative config path
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
            self._level = path
        else:
            raise TypeError("Level path must be either a whitespace-separated string or a list")

    def get_level(self):
        """
        Gets the current edit level.

        Returns:
            str: current edit level
        """
        return(self._level)

    def exists(self, path):
        """
        Checks if a node with given path exists in the running or proposed config

        Returns:
            True if node exists, False otherwise

        Note:
            This function cannot be used outside a configuration sessions.
            In operational mode scripts, use ``exists_effective``.
        """
        if self._session_config.exists(self._make_path(path)):
            return True
        else:
            # libvyosconfig exists() works only for _nodes_, not _values_
            # libvyattacfg one also worked for values, so we emulate that case here
            if isinstance(path, str):
                path = re.split(r'\s+', path)
            path_without_value = path[:-1]
            path_str = " ".join(path_without_value)
            try:
                value = self._session_config.return_value(self._make_path(path_str))
                return (value == path[-1])
            except vyos.configtree.ConfigTreeError:
                # node doesn't exist at all
                return False

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
        try:
            self._run(self._make_command('inSession', ''))
            return True
        except VyOSError:
            return False

    def show_config(self, path=[], default=None, effective=False):
        """
        Args:
            path (str list): Configuration tree path, or empty
            default (str): Default value to return

        Returns:
            str: working configuration
        """

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
            # ugly but can not see a better way to handle this
            if out == 'Configuration under specified path is empty\n':
                return ''
            return out
        except VyOSError:
            return(default)

    def get_config_dict(self, path=[], effective=False):
        """
        Args: path (str list): Configuration tree path, can be empty
        Returns: a dict representation of the config
        """
        res = self.show_config(self._make_path(path), effective=effective)
        config_tree = vyos.configtree.ConfigTree(res)
        config_dict = json.loads(config_tree.to_json())
        return config_dict

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

    def return_value(self, path, default=None):
        """
        Retrieve a value of single-value leaf node in the running or proposed config

        Args:
            path (str): Configuration tree path
            default (str): Default value to return if node does not exist

        Returns:
            str: Node value, if it has any
            None: if node is valueless *or* if it doesn't exist

        Note:
            Due to the issue with treatment of valueless nodes by this function,
            valueless nodes should be checked with ``exists`` instead.

            This function cannot be used outside a configuration session.
            In operational mode scripts, use ``return_effective_value``.
        """
        try:
            value = self._session_config.return_value(self._make_path(path))
        except vyos.configtree.ConfigTreeError:
            value = None

        if not value:
            return(default)
        else:
            return(value)

    def return_values(self, path, default=[]):
        """
        Retrieve all values of a multi-value leaf node in the running or proposed config

        Args:
            path (str): Configuration tree path

        Returns:
            str list: Node values, if it has any
            []: if node does not exist

        Note:
            This function cannot be used outside a configuration session.
            In operational mode scripts, use ``return_effective_values``.
        """
        try:
            values = self._session_config.return_values(self._make_path(path))
        except vyos.configtree.ConfigTreeError:
            values = []

        if not values:
            return(default)
        else:
            return(values)

    def list_nodes(self, path, default=[]):
        """
        Retrieve names of all children of a tag node in the running or proposed config

        Args:
            path (str): Configuration tree path

        Returns:
            string list: child node names

        """
        try:
            nodes = self._session_config.list_nodes(self._make_path(path))
        except vyos.configtree.ConfigTreeError:
            nodes = []

        if not nodes:
            return(default)
        else:
            return(nodes)

    def exists_effective(self, path):
        """
        Check if a node exists in the running (effective) config

        Args:
            path (str): Configuration tree path

        Returns:
            True if node exists in the running config, False otherwise

        Note:
            This function is safe to use in operational mode. In configuration mode,
            it ignores uncommited changes.
        """
        return(self._running_config.exists(self._make_path(path)))

    def return_effective_value(self, path, default=None):
        """
        Retrieve a values of a single-value leaf node in a running (effective) config

        Args:
            path (str): Configuration tree path
            default (str): Default value to return if node does not exist

        Returns:
            str: Node value
        """
        try:
            value = self._running_config.return_value(self._make_path(path))
        except vyos.configtree.ConfigTreeError:
            value = None

        if not value:
            return(default)
        else:
            return(value)


    def return_effective_values(self, path, default=[]):
        """
        Retrieve all values of a multi-value node in a running (effective) config

        Args:
            path (str): Configuration tree path

        Returns:
            str list: A list of values
        """
        try:
            values = self._running_config.return_values(self._make_path(path))
        except vyos.configtree.ConfigTreeError:
            values = []

        if not values:
            return(default)
        else:
            return(values)

    def list_effective_nodes(self, path, default=[]):
        """
        Retrieve names of all children of a tag node in the running config

        Args:
            path (str): Configuration tree path

        Returns:
            str list: child node names

        Raises:
            VyOSError: if the node is not a tag node
        """
        try:
            nodes = self._running_config.list_nodes(self._make_path(path))
        except vyos.configtree.ConfigTreeError:
            nodes = []

        if not nodes:
            return(default)
        else:
            return(nodes)
