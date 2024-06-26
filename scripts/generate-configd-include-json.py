#!/usr/bin/env python3
# Copyright (C) 2024 VyOS maintainers and contributors
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

import os
from jinja2 import Template

conf_scripts = 'src/conf_mode'
configd_include = 'data/configd-include.json'

configd_template = Template("""[
{% for file in files %}
"{{ file }}"{{ "," if not loop.last else "" }}
{% endfor %}
]
""", trim_blocks=True)

files = [f for f in os.listdir(conf_scripts) if os.path.isfile(f'{conf_scripts}/{f}')]
files = sorted(files)

tmp = {'files' : files}
with open(configd_include, 'w') as f:
    f.write(configd_template.render(tmp))
