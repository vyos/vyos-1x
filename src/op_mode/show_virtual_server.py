#!/usr/bin/env python3
#
# Copyright (C) 2022 VyOS maintainers and contributors
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

from vyos.configquery import ConfigTreeQuery
from vyos.utils.process import call

def is_configured():
    """ Check if high-availability virtual-server is configured """
    config = ConfigTreeQuery()
    if not config.exists(['high-availability', 'virtual-server']):
        return False
    return True

if __name__ == '__main__':

    if is_configured() == False:
        print('Virtual server not configured!')
        exit(0)

    call('sudo ipvsadm --list --numeric')
