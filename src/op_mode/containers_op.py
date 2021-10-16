#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
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

from getpass import getuser
from vyos.configquery import ConfigTreeQuery
from vyos.util import cmd

parser = argparse.ArgumentParser()
parser.add_argument("-a", "--all", action="store_true", help="Show all containers")
parser.add_argument("-i", "--image", action="store_true", help="Show container images")
parser.add_argument("-n", "--networks", action="store_true", help="Show container images")
parser.add_argument("-p", "--pull", action="store", help="Pull image for container")
parser.add_argument("-d", "--remove", action="store", help="Delete container image")
parser.add_argument("-u", "--update", action="store", help="Update given container image")

config = ConfigTreeQuery()
base = ['container']
if not config.exists(base):
    print('Containers not configured')
    exit(0)

if getuser() != 'root':
    raise OSError('This functions needs to be run as root to return correct results!')

if __name__ == '__main__':
    args = parser.parse_args()

    if args.all:
        print(cmd('podman ps --all'))

    elif args.image:
        print(cmd('podman image ls'))

    elif args.networks:
        print(cmd('podman network ls'))

    elif args.pull:
        image = args.pull
        try:
            print(cmd(f'podman image pull {image}'))
        except:
            print(f'Can\'t find or download image "{image}"')

    elif args.remove:
        image = args.remove
        try:
            print(cmd(f'podman image rm {image}'))
        except:
            print(f'Can\'t delete image "{image}"')

    elif args.update:
        tmp = config.get_config_dict(base + ['name', args.update],
                                     key_mangling=('-', '_'), get_first_key=True)
        try:
            image = tmp['image']
            print(cmd(f'podman image pull {image}'))
        except:
            print(f'Can\'t find or download image "{image}"')
    else:
        parser.print_help()
        exit(1)

    exit(0)
