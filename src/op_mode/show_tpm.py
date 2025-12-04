#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

import sys

from vyos.tpm import tpm_exist, tpm_enabled

if __name__ == '__main__':

    if tpm_exist():
        tpm_hw_string = "Supported"
    else:
        tpm_hw_string = "Not supported"

    print(f'TPM hardware:       {tpm_hw_string}')

    if tpm_enabled():
        tpm_mode_string = "Enabled"
    else:
        tpm_mode_string = "Disabled"

    print(f'TPM Operation Mode: {tpm_mode_string}')
    sys.exit(0)
