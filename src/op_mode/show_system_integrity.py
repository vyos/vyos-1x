#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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
#
#

import sys
import os
import re
import json
from datetime import datetime, timedelta

version_file = r'/usr/share/vyos/version.json'


def _get_sys_build_version():
    if not os.path.exists(version_file):
        return None
    buf = open(version_file, 'r').read()
    j = json.loads(buf)
    if not 'built_on' in j:
        return None
    return datetime.strptime(j['built_on'], '%a %d %b %Y %H:%M %Z')


def _check_pkgs(build_stamp):
    pkg_diffs = {
        'buildtime': str(build_stamp),
        'pkg': {}
    }

    pkg_info = os.listdir('/var/lib/dpkg/info/')
    for file in pkg_info:
        if re.search('\.list$', file):
            fts = os.stat('/var/lib/dpkg/info/' + file).st_mtime
            dt_str = (datetime.utcfromtimestamp(
                fts).strftime('%Y-%m-%d %H:%M:%S'))
            fdt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
            if fdt > build_stamp:
                pkg_diffs['pkg'].update(
                    {str(re.sub('\.list', '', file)): str(fdt)})

    if len(pkg_diffs['pkg']) != 0:
        return pkg_diffs
    else:
        return None


if __name__ == '__main__':
    built_date = _get_sys_build_version()
    if not built_date:
        sys.exit(1)
    pkgs = _check_pkgs(built_date)
    if pkgs:
        print (
            "The following packages don\'t fit the image creation time\nbuild time:\t" + pkgs['buildtime'])
        for k, v in pkgs['pkg'].items():
            print ("installed: " + v + '\t' + k)
