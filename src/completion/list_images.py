#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
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

import argparse
import os
import sys

from vyos.system.image import is_live_boot
from vyos.system.image import get_running_image


parser = argparse.ArgumentParser(description='list available system images')
parser.add_argument('--no-running', action='store_true',
                    help='do not display the currently running image')

def get_images(omit_running: bool = False) -> list[str]:
    if is_live_boot():
        return []
    images = os.listdir("/lib/live/mount/persistence/boot")
    if omit_running:
        images.remove(get_running_image())
    if 'grub' in images:
        images.remove('grub')
    if 'efi' in images:
        images.remove('efi')
    return sorted(images)

if __name__ == '__main__':
    args = parser.parse_args()
    print("\n".join(get_images(omit_running=args.no_running)))
    sys.exit(0)
