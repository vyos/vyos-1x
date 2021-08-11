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
import tabulate

from vyos.config import Config
from vyos.util import dict_search_args

def get_config_zone(conf, name=None):
    config_path = ['zone-policy']
    if name:
        config_path += ['zone', name]

    zone_policy = conf.get_config_dict(config_path, key_mangling=('-', '_'),
                                get_first_key=True, no_tag_node_value_mangle=True)
    return zone_policy

def output_zone_name(zone, zone_conf):
    print(f'\n---------------------------------\nZone: "{zone}"\n')
    
    interfaces = ', '.join(zone_conf['interface']) if 'interface' in zone_conf else ''
    if 'local_zone' in zone_conf:
        interfaces = 'LOCAL'

    print(f'Interfaces: {interfaces}\n')

    header = ['From Zone', 'Firewall']
    rows = []

    if 'from' in zone_conf:
        for from_name, from_conf in zone_conf['from'].items():
            row = [from_name]
            v4_name = dict_search_args(from_conf, 'firewall', 'name')
            v6_name = dict_search_args(from_conf, 'firewall', 'ipv6_name')

            if v4_name:
                rows.append(row + [v4_name])

            if v6_name:
                rows.append(row + [f'{v6_name} [IPv6]'])

    if rows:
        print('From Zones:\n')
        print(tabulate.tabulate(rows, header))

def show_zone_policy(zone):
    conf = Config()
    zone_policy = get_config_zone(conf, zone)

    if not zone_policy:
        return

    if 'zone' in zone_policy:
        for zone, zone_conf in zone_policy['zone'].items():
            output_zone_name(zone, zone_conf)
    elif zone:
        output_zone_name(zone, zone_policy)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--action', help='Action', required=False)
    parser.add_argument('--name', help='Zone name', required=False, action='store', nargs='?', default='')

    args = parser.parse_args()

    if args.action == 'show':
        show_zone_policy(args.name)
