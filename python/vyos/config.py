# Copyright 2017 VyOS maintainers and contributors <maintainers@vyos.io>
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
but its API should be considered stable and it is safe to use
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
of a better word. The knowledge of whether in "task Foo" the "tag" is "task" or "Foo" is lost
in time, luckily, the distinction is irrelevant in practice.

Configuration modes
###################

VyOS has two distinct modes: operational mode and configuration mode. When a user logins,
the CLI is in the operational mode. In this mode, only the running (effective) config is accessible for reading.

When a user enters the "configure" command, a configuration session is setup. Every config session
has its *proposed* config built on top of the current running config. When changes are commited, if commit succeeds,
the proposed config is merged into the running config.

For this reason, this library has two sets of functions. The base versions, such as ``exists`` or ``return_value``
are only usable in configuration mode. They take all nodes into account, in both proposed and running configs.
Configuration scripts require access to uncommited changes for obvious reasons. Configuration mode completion helpers
should also use these functions because not having nodes you've just created in completion is annoying.

However, in operational mode, only the running config is available. Currently, you need to use special functions
for reading it from operational mode scripts, they can be distinguished by the word "effective" in their names.
In the future base versions may be made to detect if they are called from a config session or not.
"""

import subprocess
import re


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
    def __init__(self):
        self._cli_shell_api = "/bin/cli-shell-api"
        self._level = ""

    def _make_command(self, op, path):
        args = path.split()
        cmd = [self._cli_shell_api, op] + args
        return cmd

    def _run(self, cmd):
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        out = p.stdout.read()
        p.wait()
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
        self._level = path + " "

    def get_level(self):
        """
        Gets the current edit level.

        Returns:
            str: current edit level
        """
        return(self._level.strip())

    def exists(self, path):
        """
        Checks if a node with given path exists in the running or proposed config

        Returns:
            True if node exists, False otherwise

        Note:
            This function cannot be used outside a configuration sessions.
            In operational mode scripts, use ``exists_effective``.
        """
        try:
            self._run(self._make_command('exists', self._level + path))
            return True
        except VyOSError:
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

    def show_config(self, path='', default=None):
        """
        Args:
            path (str): Configuration tree path, or empty
            default (str): Default value to return

        Returns:
            str: working configuration
        """
        try:
            out = self._run(self._make_command('showConfig', path))
            return out
        except VyOSError:
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
            self._run(self._make_command('isMulti', self._level + path))
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
            self._run(self._make_command('isTag', self._level + path))
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
            self._run(self._make_command('isLeaf', self._level + path))
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

        Raises:
            VyOSError: if node is not a single-value leaf node

        Note:
            Due to the issue with treatment of valueless nodes by this function,
            valueless nodes should be checked with ``exists`` instead.

            This function cannot be used outside a configuration session.
            In operational mode scripts, use ``return_effective_value``.
        """
        full_path = self._level + path
        if self.is_multi(path):
            raise VyOSError("Cannot use return_value on multi node: {0}".format(full_path))
        elif not self.is_leaf(path):
            raise VyOSError("Cannot use return_value on non-leaf node: {0}".format(full_path))
        else:
            try:
                out = self._run(self._make_command('returnValue', full_path))
                return out
            except VyOSError:
                return(default)

    def return_values(self, path, default=[]):
        """
        Retrieve all values of a multi-value leaf node in the running or proposed config

        Args:
            path (str): Configuration tree path

        Returns:
            str list: Node values, if it has any
            None: if node does not exist

        Raises:
            VyOSError: if node is not a multi-value leaf node

        Note:
            This function cannot be used outside a configuration session.
            In operational mode scripts, use ``return_effective_values``.
        """
        full_path = self._level + path
        if not self.is_multi(path):
            raise VyOSError("Cannot use return_values on non-multi node: {0}".format(full_path))
        elif not self.is_leaf(path):
            raise VyOSError("Cannot use return_values on non-leaf node: {0}".format(full_path))
        else:
            try:
                out = self._run(self._make_command('returnValues', full_path))
                values = re.findall(r"\'(.*?)\'", out)
                return values
            except VyOSError:
                return(default)

    def list_nodes(self, path, default=[]):
        """
        Retrieve names of all children of a tag node in the running or proposed config

        Args:
            path (str): Configuration tree path

        Returns:
            string list: child node names

        Raises:
            VyOSError: if the node is not a tag node

        Note:
            There is no way to list all children of a non-tag node in
            the current config backend.

            This function cannot be used outside a configuration session.
            In operational mode scripts, use ``list_effective_nodes``.
        """
        full_path = self._level + path
        if self.is_tag(path):
            try:
                out = self._run(self._make_command('listNodes', full_path))
                values = re.findall(r"\'(.*?)\'", out)
                return values
            except VyOSError:
                return(default)
        else:
            raise VyOSError("Cannot use list_nodes on a non-tag node: {0}".format(full_path))

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
        try:
            self._run(self._make_command('existsEffective', self._level + path))
            return True
        except VyOSError:
            return False

    def return_effective_value(self, path, default=None):
        """
        Retrieve a values of a single-value leaf node in a running (effective) config

        Args:
            path (str): Configuration tree path
            default (str): Default value to return if node does not exist

        Returns:
            str: Node value

        Raises:
            VyOSError: if node is not a multi-value leaf node
        """
        full_path = self._level + path
        if self.is_multi(path):
            raise VyOSError("Cannot use return_effective_value on multi node: {0}".format(full_path))
        elif not self.is_leaf(path):
            raise VyOSError("Cannot use return_effective_value on non-leaf node: {0}".format(full_path))
        else:
            try:
                out = self._run(self._make_command('returnEffectiveValue', full_path))
                return out
            except VyOSError:
                return(default)

    def return_effective_values(self, path, default=[]):
        """
        Retrieve all values of a multi-value node in a running (effective) config

        Args:
            path (str): Configuration tree path

        Returns:
            str list: A list of values

        Raises:
            VyOSError: if node is not a multi-value leaf node
        """
        full_path = self._level + path
        if not self.is_multi(path):
            raise VyOSError("Cannot use return_effective_values on non-multi node: {0}".format(full_path))
        elif not self.is_leaf(path):
            raise VyOSError("Cannot use return_effective_values on non-leaf node: {0}".format(full_path))
        else:
            try:
                out = self._run(self._make_command('returnEffectiveValues', full_path))
                return out
            except VyOSError:
                return(default)

    def list_effective_nodes(self, path, default=[]):
        """
        Retrieve names of all children of a tag node in the running config

        Args:
            path (str): Configuration tree path

        Returns:
            str list: child node names

        Raises:
            VyOSError: if the node is not a tag node

        Note:
            There is no way to list all children of a non-tag node in
            the current config backend.
        """
        full_path = self._level + path
        if self.is_tag(path):
            try:
                out = self._run(self._make_command('listEffectiveNodes', full_path))
                values = out.split()
                return list(map(lambda x: re.sub(r'^\'(.*)\'$', r'\1',x), values))
            except VyOSError:
                return(default)
        else:
            raise VyOSError("Cannot use list_effective_nodes on a non-tag node: {0}".format(full_path))
