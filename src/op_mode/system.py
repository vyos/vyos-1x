#!/usr/bin/env python3
#
# Copyright (C) 2022-2024 VyOS maintainers and contributors
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

import jmespath
import sys

from vyos.configquery import ConfigTreeQuery

import vyos.opmode
import vyos.version

config = ConfigTreeQuery()
base = ['system', 'update-check']


def _compare_version_raw():
    url = config.value(base + ['url'])
    local_data = vyos.version.get_full_version_data()
    remote_data = vyos.version.get_remote_version(url)
    if not remote_data:
        return {"error": True,
                "reason": "Unable to get remote version"}
    if local_data.get('version') and remote_data:
        local_version = local_data.get('version')
        remote_version = jmespath.search('[0].version', remote_data)
        image_url = jmespath.search('[0].url', remote_data)
        if local_data.get('version') != remote_version:
            return {"error": False,
                    "update_available": True,
                    "local_version": local_version,
                    "remote_version": remote_version,
                    "url": image_url}
        return {"update_available": False,
                "local_version": local_version,
                "remote_version": remote_version}


def _formatted_compare_version(data):
    local_version = data.get('local_version')
    remote_version = data.get('remote_version')
    url = data.get('url')
    if {'update_available','local_version', 'remote_version', 'url'} <= set(data):
        return f'Current version: {local_version}\n\nUpdate available: {remote_version}\nUpdate URL: {url}'
    elif local_version == remote_version and remote_version is not None:
        return f'No available updates for your system \n' \
               f'current version: {local_version}\nremote version: {remote_version}'
    else:
        return 'Update not found'


def _verify():
    if not config.exists(base):
        return False
    return True


def show_update(raw: bool):
    if not _verify():
        raise vyos.opmode.UnconfiguredSubsystem("system update-check not configured")
    data = _compare_version_raw()
    if raw:
        return data
    else:
        return _formatted_compare_version(data)


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
