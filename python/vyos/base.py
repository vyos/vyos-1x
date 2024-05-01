# Copyright 2018-2022 VyOS maintainers and contributors <maintainers@vyos.io>
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

from textwrap import fill


class BaseWarning:
    def __init__(self, header, message, **kwargs):
        self.message = message
        self.kwargs = kwargs
        if 'width' not in kwargs:
            self.width = 72
        if 'initial_indent' in kwargs:
            del self.kwargs['initial_indent']
        if 'subsequent_indent' in kwargs:
            del self.kwargs['subsequent_indent']
        self.textinitindent = header
        self.standardindent = ''

    def print(self):
        messages = self.message.split('\n')
        isfirstmessage = True
        initial_indent = self.textinitindent
        print('')
        for mes in messages:
            mes = fill(mes, initial_indent=initial_indent,
                       subsequent_indent=self.standardindent, **self.kwargs)
            if isfirstmessage:
                isfirstmessage = False
                initial_indent = self.standardindent
            print(f'{mes}')
        print('', flush=True)


class Warning():
    def __init__(self, message, **kwargs):
        self.BaseWarn = BaseWarning('WARNING: ', message, **kwargs)
        self.BaseWarn.print()


class DeprecationWarning():
    def __init__(self, message, **kwargs):
        # Reformat the message and trim it to 72 characters in length
        self.BaseWarn = BaseWarning('DEPRECATION WARNING: ', message, **kwargs)
        self.BaseWarn.print()


class ConfigError(Exception):
    def __init__(self, message):
        # Reformat the message and trim it to 72 characters in length
        message = fill(message, width=72)
        # Call the base class constructor with the parameters it needs
        super().__init__(message)
