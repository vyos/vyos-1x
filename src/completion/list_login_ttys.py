#!/usr/bin/env python3
#
# Copyright (C) 2024 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from vyos.utils.serial import get_serial_units

if __name__ == '__main__':
    # Autocomplete uses runtime state rather than the config tree, as a manual 
    # restart/cleanup may be needed for deleted devices. 
    tty_completions = [ '<text>' ] + [ x['device'] for x in get_serial_units() if 'device' in x ]
    print(' '.join(tty_completions))


