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

class Warning():
    def __init__(self, message):
        # Reformat the message and trim it to 72 characters in length
        message = fill(message, width=72)
        print(f'\nWARNING: {message}')

class DeprecationWarning():
    def __init__(self, message):
        # Reformat the message and trim it to 72 characters in length
        message = fill(message, width=72)
        print(f'\nDEPRECATION WARNING: {message}\n')

class ConfigError(Exception):
    def __init__(self, message):
        # Reformat the message and trim it to 72 characters in length
        message = fill(message, width=72)
        # Call the base class constructor with the parameters it needs
        super().__init__(message)
