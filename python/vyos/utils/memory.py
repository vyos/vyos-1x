# Copyright (C) VyOS Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import re
from vyos.utils.file import read_file


def get_memory_info() -> dict:
    """Returns system memory information parsed from /proc/meminfo"""
    data = read_file('/proc/meminfo')

    result = {}
    regex = r'^(?P<key>\S+):\s+(?P<value>[0-9]+)\s+kB\s*$'
    for match in re.finditer(regex, data, flags=re.MULTILINE):
        result[match['key']] = int(match['value'])

    return result
