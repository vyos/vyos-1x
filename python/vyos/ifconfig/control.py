# Copyright 2019 VyOS maintainers and contributors <maintainers@vyos.io>
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


import os
from subprocess import Popen, PIPE, STDOUT

from vyos.ifconfig.register import Register


class Control(Register):
    _command_get = {}
    _command_set = {}

    debug = True

    def _debug_msg(self, msg, debug=True):
        if os.path.isfile('/tmp/vyos.ifconfig.debug') and self.debug:
            print('DEBUG/{:<6} {}'.format(self.config['ifname'], msg))

    def _popen(self, command):
        p = Popen(command, stdout=PIPE, stderr=STDOUT, shell=True)
        tmp = p.communicate()[0].strip()
        self._debug_msg(f"cmd '{command}'")
        decoded = tmp.decode()
        if decoded:
            self._debug_msg(f"returned:\n{decoded}")
        return decoded, p.returncode

    def _cmd(self, command):
        decoded, code = self._popen(command)
        if code != 0:
            # error code can be recovered with .errno
            raise OSError(code, f'{command}\nreturned: {decoded}')
        return decoded

    def _get_command(self, config, name):
        """
        Using the defined names, set data write to sysfs.
        """
        cmd = self._command_get[name]['shellcmd'].format(**config)
        return self._command_get[name].get('format', lambda _: _)(self._cmd(cmd))

    def _set_command(self, config, name, value):
        """
        Using the defined names, set data write to sysfs.
        """
        # the code can pass int as int
        value = str(value)

        validate = self._command_set[name].get('validate', None)
        if validate:
            try:
                validate(value)
            except Exception as e:
                raise e.__class__(f'Could not set {name}. {e}')

        convert = self._command_set[name].get('convert', None)
        if convert:
            value = convert(value)

        config = {**config, **{'value': value}}

        cmd = self._command_set[name]['shellcmd'].format(**config)
        return self._command_set[name].get('format', lambda _: _)(self._cmd(cmd))

    _sysfs_get = {}
    _sysfs_set = {}

    def _read_sysfs(self, filename):
        """
        Provide a single primitive w/ error checking for reading from sysfs.
        """
        value = None
        with open(filename, 'r') as f:
            value = f.read().rstrip('\n')

        self._debug_msg("read '{}' < '{}'".format(value, filename))
        return value

    def _write_sysfs(self, filename, value):
        """
        Provide a single primitive w/ error checking for writing to sysfs.
        """
        self._debug_msg("write '{}' > '{}'".format(value, filename))
        if os.path.isfile(filename):
            with open(filename, 'w') as f:
                f.write(str(value))
            return True
        return False

    def _get_sysfs(self, config, name):
        """
        Using the defined names, get data write from sysfs.
        """
        filename = self._sysfs_get[name]['location'].format(**config)
        if not filename:
            return None
        return self._read_sysfs(filename)

    def _set_sysfs(self, config, name, value):
        """
        Using the defined names, set data write to sysfs.
        """
        # the code can pass int as int
        value = str(value)

        validate = self._sysfs_set[name].get('validate', None)
        if validate:
            validate(value)

        config = {**config, **{'value': value}}

        convert = self._sysfs_set[name].get('convert', None)
        if convert:
            value = convert(value)

        commited = self._write_sysfs(
            self._sysfs_set[name]['location'].format(**config), value)
        if not commited:
            errmsg = self._sysfs_set.get('errormsg', '')
            if errmsg:
                raise TypeError(errmsg.format(**config))
        return commited

    def get_interface(self, name):
        if name in self._sysfs_get:
            return self._get_sysfs(self.config, name)
        if name in self._command_get:
            return self._get_command(self.config, name)
        raise KeyError(f'{name} is not a attribute of the interface we can get')

    def set_interface(self, name, value):
        if name in self._sysfs_set:
            return self._set_sysfs(self.config, name, value)
        if name in self._command_set:
            return self._set_command(self.config, name, value)
        raise KeyError(f'{name} is not a attribute of the interface we can set')
