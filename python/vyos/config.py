# Copyright (c) 2017 VyOS maintainers and contributors
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the Software
# is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included 
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, 
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS
# OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR
#  IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

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

    def return_value(self, path):
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
                raise VyOSError("Path doesn't exist: {0}".format(full_path))

    def return_values(self, path):
        full_path = self._level + path
        if not self.is_multi(path):
            raise VyOSError("Cannot use return_values on non-multi node: {0}".format(full_path))
        elif not self.is_leaf(path):
            raise VyOSError("Cannot use return_values on non-leaf node: {0}".format(full_path))
        else:
            try:
                out = self._run(self._make_command('returnValues', full_path))
                return out
            except VyOSError:
                raise VyOSError("Path doesn't exist: {0}".format(full_path))

    def list_nodes(self, path):
        full_path = self._level + path
        if self.is_tag(path):
            try:
                out = self._run(self._make_command('listNodes', full_path))
                values = out.split()
                return list(map(lambda x: re.sub(r'^\'(.*)\'$', r'\1',x), values))
            except VyOSError:
                raise VyOSError("Path doesn't exist: {0}".format(full_path)) 
        else:
            raise VyOSError("Cannot use list_nodes on a non-tag node: {0}".format(full_path))
