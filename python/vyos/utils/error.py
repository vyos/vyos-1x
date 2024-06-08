# Copyright 2024 VyOS maintainers and contributors <maintainers@vyos.io>
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

from enum import IntEnum

class cli_shell_api_err(IntEnum):
    """ vyatta-cfg/src/vyos-errors.h """
    VYOS_SUCCESS = 0
    VYOS_GENERAL_FAILURE = 1
    VYOS_INVALID_PATH = 2
    VYOS_EMPTY_CONFIG = 3
    VYOS_CONFIG_PARSE_ERROR = 4
