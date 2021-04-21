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
from vyos.configquery import query_context, ConfigQueryError
from vyos.util import cmd

config, op = query_context()

parser = argparse.ArgumentParser()
parser.add_argument("-a", "--all", action="store_true", help="Show all containers")
parser.add_argument("-i", "--image", action="store_true", help="Show container images")
parser.add_argument("-n", "--networks", action="store_true", help="Show container images")
parser.add_argument("-p", "--pull", action="store", help="Pull image for container")
parser.add_argument("-d", "--remove", action="store", help="Delete container image")

if not config.exists(['container']):
    print('Containers not configured')
    exit(0)

if __name__ == '__main__':
    args = parser.parse_args()

    if args.all:
        print(cmd('podman ps --all'))
        exit(0)
    if args.image:
        print(cmd('podman image ls'))
        exit(0)
    if args.networks:
        print(cmd('podman network ls'))
        exit(0)
    if args.pull:
        image = args.pull
        try:
            print(cmd(f'sudo podman image pull {image}'))
        except:
            print(f'Can\'t find or download image "{image}"')
        exit(0)
    if args.remove:
        image = args.remove
        try:
            print(cmd(f'sudo podman image rm {image}'))
        except:
            print(f'Can\'t delete image "{image}"')
        exit(0)
