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


import subprocess
import re


class VyOSError(Exception):
    pass


class Config(object):
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
        # Make sure there's always a space between default path (level)
        # and path supplied as method argument
        # XXX: for small strings in-place concatenation is not a problem
        self._level = path + " "

    def get_level(self):
        return(self._level.strip())

    def exists(self, path):
        try:
            self._run(self._make_command('exists', self._level + path))
            return True
        except VyOSError:
            return False

    def session_changed(self):
        try:
            self._run(self._make_command('sessionChanged', ''))
            return True
        except VyOSError:
            return False

    def in_session(self):
        try:
            self._run(self._make_command('inSession', ''))
            return True
        except VyOSError:
            return False

    def is_multi(self, path):
        try:
            self._run(self._make_command('isMulti', self._level + path))
            return True
        except VyOSError:
            return False

    def is_tag(self, path):
        try:
            self._run(self._make_command('isTag', self._level + path))
            return True
        except VyOSError:
            return False

    def is_leaf(self, path):
        try:
            self._run(self._make_command('isLeaf', self._level + path))
            return True
        except VyOSError:
            return False

    def return_value(self, path, default=None):
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
        full_path = self._level + path
        if not self.is_multi(path):
            raise VyOSError("Cannot use return_values on non-multi node: {0}".format(full_path))
        elif not self.is_leaf(path):
            raise VyOSError("Cannot use return_values on non-leaf node: {0}".format(full_path))
        else:
            try:
                out = self._run(self._make_command('returnValues', full_path))
                values = out.split()
                return list(map(lambda x: re.sub(r'^\'(.*)\'$', r'\1',x), values))
            except VyOSError:
                return(default)

    def list_nodes(self, path, default=[]):
        full_path = self._level + path
        if self.is_tag(path):
            try:
                out = self._run(self._make_command('listNodes', full_path))
                values = out.split()
                return list(map(lambda x: re.sub(r'^\'(.*)\'$', r'\1',x), values))
            except VyOSError:
                return(default)
        else:
            raise VyOSError("Cannot use list_nodes on a non-tag node: {0}".format(full_path))

    def exists_effective(self, path):
        try:
            self._run(self._make_command('existsEffective', self._level + path))
            return True
        except VyOSError:
            return False

    def return_effective_value(self, path, default=None):
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
