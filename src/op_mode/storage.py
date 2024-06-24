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
#

import sys

import vyos.opmode

from jinja2 import Template

output_tmpl = """
Filesystem: {{filesystem}}
Size:       {{size}}
Used:       {{used}} ({{use_percentage}}%)
Available:  {{avail}} ({{avail_percentage}}%)
"""

def _get_formatted_output():
    return _get_system_storage()

def show(raw: bool):
    from vyos.utils.disk import get_persistent_storage_stats

    if raw:
        res = get_persistent_storage_stats(human_units=False)
        if res is None:
            raise vyos.opmode.DataUnavailable("Storage statistics are not available")
        else:
            return res
    else:
        data = get_persistent_storage_stats(human_units=True)
        if data is None:
            return "Storage statistics are not available"
        else:
            data["avail_percentage"] = 100 - int(data["use_percentage"])
            tmpl = Template(output_tmpl)
            return tmpl.render(data).strip()

    return output

if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)

