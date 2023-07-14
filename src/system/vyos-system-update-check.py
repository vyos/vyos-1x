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

import argparse
import json
import jmespath

from pathlib import Path
from sys import exit
from time import sleep

from vyos.utils.process import call

import vyos.version

motd_file = Path('/run/motd.d/10-vyos-update')


if __name__ == '__main__':
    # Parse command arguments and get config
    parser = argparse.ArgumentParser()
    parser.add_argument('-c',
                        '--config',
                        action='store',
                        help='Path to system-update-check configuration',
                        required=True,
                        type=Path)

    args = parser.parse_args()
    try:
        config_path = Path(args.config)
        config = json.loads(config_path.read_text())
    except Exception as err:
        print(
            f'Configuration file "{config_path}" does not exist or malformed: {err}'
        )
        exit(1)

    url_json = config.get('url')
    local_data = vyos.version.get_full_version_data()
    local_version = local_data.get('version')

    while True:
        remote_data = vyos.version.get_remote_version(url_json)
        if remote_data:
            url = jmespath.search('[0].url', remote_data)
            remote_version = jmespath.search('[0].version', remote_data)
            if local_version != remote_version and remote_version:
                call(f'wall -n "Update available: {remote_version} \nUpdate URL: {url}"')
                # MOTD used in /run/motd.d/10-update
                motd_file.parent.mkdir(exist_ok=True)
                motd_file.write_text(f'---\n'
                                     f'Current version: {local_version}\n'
                                     f'Update available: \033[1;34m{remote_version}\033[0m\n'
                                     f'---\n')
        # Check every 12 hours
        sleep(43200)
