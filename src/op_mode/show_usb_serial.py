#!/usr/bin/env python3
#
# Copyright (C) 2018 VyOS maintainers and contributors
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

import os

from jinja2 import Template
from pyudev import Context, Devices
from sys import exit

OUT_TMPL_SRC = """Device           Model               Vendor
------           ------              ------
{% for d in devices %}
{{ "%-16s" | format(d.device) }} {{ "%-19s" | format(d.model)}} {{d.vendor}}
{% endfor %}

"""

data = {
    'devices': []
}


base_directory = '/dev/serial/by-bus'
if not os.path.isdir(base_directory):
    print("No USB to serial converter connected")
    exit(0)

context = Context()
for root, dirs, files in os.walk(base_directory):
    for basename in files:
        os.path.join(root, basename)
        device = Devices.from_device_file(context, os.path.join(root, basename))
        tmp = {
            'device': basename,
            'model': device.properties.get('ID_MODEL'),
            'vendor': device.properties.get('ID_VENDOR_FROM_DATABASE')
        }
        data['devices'].append(tmp)

data['devices'] = sorted(data['devices'], key = lambda i: i['device'])
tmpl = Template(OUT_TMPL_SRC)
print(tmpl.render(data))

exit(0)
