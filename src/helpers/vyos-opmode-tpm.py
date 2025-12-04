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
import subprocess
import time

from argparse import ArgumentParser
# from cryptography.fernet import Fernet

from vyos.tpm import tpm_exist, tpm_enabled, tpm_enable, tpm_disable

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Must specify action.")
        sys.exit(1)

    parser = ArgumentParser(description='Operation TPM enable/disable')
    parser.add_argument('--disable', help='Disable TPM', action="store_true")
    parser.add_argument('--enable', help='Enable TPM', action="store_true")
    args = parser.parse_args()

    if args.disable:
        if not tpm_exist():
            print('TPM hardware not supported on this product; '
                  'ignoring command')
            sys.exit(0)
        if not tpm_enabled():
            print('TPM support already disabled, ignoring command')
            sys.exit(0)
        tpm_disable()
        print('TPM support disabled, reboot required.')

    elif args.enable:
        if not tpm_exist():
            print('TPM hardware not supported on this product; '
                  'ignoring command')
            sys.exit(0)
        if tpm_enabled():
            print('TPM support already enabled, ignoring command')
            sys.exit(0)
        tpm_enable()
        print('TPM support enabled, reboot required.')

    print('TPM mode changes... rebooting in 5 seconds....')
    time.sleep(5)
    subprocess.run(["python3", "/usr/libexec/vyos/op_mode/powerctrl.py",
                    "--yes", "--reboot"])
    sys.exit(0)
