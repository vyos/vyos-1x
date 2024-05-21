#!/usr/bin/env python3
#
# Copyright (C) 2024 VyOS maintainers and contributors
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

from vyos.config import Config


def get_qos_traffic_match_group():
    config = Config()
    base = ['qos', 'traffic-match-group']
    conf = config.get_config_dict(base, key_mangling=('-', '_'))
    groups = []

    for group in conf.get('traffic_match_group', []):
        groups.append(group)

    return groups


if __name__ == "__main__":
    groups = get_qos_traffic_match_group()
    print(" ".join(groups))

