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

from vyos.utils.process import rc_cmd

def get_server_statistics(accel_statistics, pattern, sep=':') -> dict:
    import re

    stat_dict = {'sessions': {}}

    cpu = re.search(r'cpu(.*)', accel_statistics).group(0)
    # Find all lines with pattern, for example 'sstp:'
    data = re.search(rf'{pattern}(.*)', accel_statistics, re.DOTALL).group(0)
    session_starting = re.search(r'starting(.*)', data).group(0)
    session_active = re.search(r'active(.*)', data).group(0)

    for entry in {cpu, session_starting, session_active}:
        if sep in entry:
            key, value = entry.split(sep)
            if key in ['starting', 'active', 'finishing']:
                stat_dict['sessions'][key] = value.strip()
                continue
            if key == 'cpu':
                stat_dict['cpu_load_percentage'] = int(re.sub(r'%', '', value.strip()))
                continue
            stat_dict[key] = value.strip()
    return stat_dict


def accel_cmd(port: int, command: str) -> str:
    _, output = rc_cmd(f'/usr/bin/accel-cmd -p{port} {command}')
    return output


def accel_out_parse(accel_output: list[str]) -> list[dict[str, str]]:
    """ Parse accel-cmd show sessions output """
    data_list: list[dict[str, str]] = list()
    field_names: list[str] = list()

    field_names_unstripped: list[str] = accel_output.pop(0).split('|')
    for field_name in field_names_unstripped:
        field_names.append(field_name.strip())

    while accel_output:
        if '|' not in accel_output[0]:
            accel_output.pop(0)
            continue

        current_item: list[str] = accel_output.pop(0).split('|')
        item_dict: dict[str, str] = {}

        for field_index in range(len(current_item)):
            field_name: str = field_names[field_index]
            field_value: str = current_item[field_index].strip()
            item_dict[field_name] = field_value

        data_list.append(item_dict)

    return data_list
