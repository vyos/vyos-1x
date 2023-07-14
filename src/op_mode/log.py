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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json
import re
import sys
import typing

from jinja2 import Template

from vyos.utils.process import rc_cmd

import vyos.opmode

journalctl_command_template = Template("""
--no-hostname
--quiet

{% if boot %}
  --boot
{% endif %}

{% if count %}
  --lines={{ count }}
{% endif %}

{% if reverse %}
  --reverse
{% endif %}

{% if since %}
  --since={{ since }}
{% endif %}

{% if unit %}
  --unit={{ unit }}
{% endif %}

{% if utc %}
  --utc
{% endif %}

{% if raw %}
{# By default show 100 only lines for raw option if count does not set #}
{# Protection from parsing the full log by default #}
{%    if not boot %}
  --lines={{ '' ~ count if count else '100' }}
{%    endif %}
  --no-pager
  --output=json
{% endif %}
""")


def show(raw: bool,
         boot: typing.Optional[bool],
         count: typing.Optional[int],
         facility: typing.Optional[str],
         reverse: typing.Optional[bool],
         utc: typing.Optional[bool],
         unit: typing.Optional[str]):
    kwargs = dict(locals())

    journalctl_options = journalctl_command_template.render(kwargs)
    journalctl_options = re.sub(r'\s+', ' ', journalctl_options)
    rc, output = rc_cmd(f'journalctl {journalctl_options}')
    if raw:
        # Each 'journalctl --output json' line is a separate JSON object
        # So we should return list of dict
        return [json.loads(line) for line in output.split('\n')]
    return output


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
