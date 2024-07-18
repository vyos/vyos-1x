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
import typing
import sys
import vyos.opmode

import tabulate
from vyos.configquery import ConfigTreeQuery
from vyos.utils.dict import dict_search_args
from vyos.utils.dict import dict_search


def get_config_zone(conf, name=None):
    config_path = ['firewall', 'zone']
    if name:
        config_path += [name]

    zone_policy = conf.get_config_dict(config_path, key_mangling=('-', '_'),
                                       get_first_key=True,
                                       no_tag_node_value_mangle=True)
    return zone_policy


def _convert_one_zone_data(zone: str, zone_config: dict) -> dict:
    """
    Convert config dictionary of one zone to API dictionary
    :param zone: Zone name
    :type zone: str
    :param zone_config: config dictionary
    :type zone_config: dict
    :return: AP dictionary
    :rtype: dict
    """
    list_of_rules = []
    intrazone_dict = {}
    if dict_search('from', zone_config):
        for from_zone, from_zone_config in zone_config['from'].items():
            from_zone_dict = {'name': from_zone}
            if dict_search('firewall.name', from_zone_config):
                from_zone_dict['firewall'] = dict_search('firewall.name',
                                                         from_zone_config)
            if dict_search('firewall.ipv6_name', from_zone_config):
                from_zone_dict['firewall_v6'] = dict_search(
                    'firewall.ipv6_name', from_zone_config)
            list_of_rules.append(from_zone_dict)

    zone_dict = {
        'name': zone,
        'interface': dict_search('interface', zone_config),
        'type': 'LOCAL' if dict_search('local_zone',
                                       zone_config) is not None else None,
    }
    if list_of_rules:
        zone_dict['from'] = list_of_rules
    if dict_search('intra_zone_filtering.firewall.name', zone_config):
        intrazone_dict['firewall'] = dict_search(
            'intra_zone_filtering.firewall.name', zone_config)
    if dict_search('intra_zone_filtering.firewall.ipv6_name', zone_config):
        intrazone_dict['firewall_v6'] = dict_search(
            'intra_zone_filtering.firewall.ipv6_name', zone_config)
    if intrazone_dict:
        zone_dict['intrazone'] = intrazone_dict
    return zone_dict


def _convert_zones_data(zone_policies: dict) -> list:
    """
    Convert all config dictionary to API list of zone dictionaries
    :param zone_policies: config dictionary
    :type zone_policies: dict
    :return: API list
    :rtype: list
    """
    zone_list = []
    for zone, zone_config in zone_policies.items():
        zone_list.append(_convert_one_zone_data(zone, zone_config))
    return zone_list


def _convert_config(zones_config: dict, zone: str = None) -> list:
    """
    convert config to API list
    :param zones_config: zones config
    :type zones_config:
    :param zone: zone name
    :type zone: str
    :return: API list
    :rtype: list
    """
    if zone:
        if zones_config:
            output = [_convert_one_zone_data(zone, zones_config)]
        else:
            raise vyos.opmode.UnconfiguredObject(f'Zone {zone} not found')
    else:
        if zones_config:
            output = _convert_zones_data(zones_config)
        else:
            raise vyos.opmode.UnconfiguredSubsystem(
                'Zone entries are not configured')
    return output


def output_zone_list(zone_conf: dict) -> list:
    """
    Format one zone row
    :param zone_conf: zone config
    :type zone_conf: dict
    :return: formatted list of zones
    :rtype: list
    """
    zone_info = [zone_conf['name']]
    if zone_conf['type'] == 'LOCAL':
        zone_info.append('LOCAL')
    else:
        zone_info.append("\n".join(zone_conf['interface']))

    from_zone = []
    firewall = []
    firewall_v6 = []
    if 'intrazone' in zone_conf:
        from_zone.append(zone_conf['name'])

        v4_name = dict_search_args(zone_conf['intrazone'], 'firewall')
        v6_name = dict_search_args(zone_conf['intrazone'], 'firewall_v6')
        if v4_name:
            firewall.append(v4_name)
        else:
            firewall.append('')
        if v6_name:
            firewall_v6.append(v6_name)
        else:
            firewall_v6.append('')

    if 'from' in zone_conf:
        for from_conf in zone_conf['from']:
            from_zone.append(from_conf['name'])

            v4_name = dict_search_args(from_conf, 'firewall')
            v6_name = dict_search_args(from_conf, 'firewall_v6')
            if v4_name:
                firewall.append(v4_name)
            else:
                firewall.append('')
            if v6_name:
                firewall_v6.append(v6_name)
            else:
                firewall_v6.append('')

    zone_info.append("\n".join(from_zone))
    zone_info.append("\n".join(firewall))
    zone_info.append("\n".join(firewall_v6))
    return zone_info


def get_formatted_output(zone_policy: list) -> str:
    """
    Formatted output of all zones
    :param zone_policy: list of zones
    :type zone_policy: list
    :return: formatted table with zones
    :rtype: str
    """
    headers = ["Zone",
               "Interfaces",
               "From Zone",
               "Firewall IPv4",
               "Firewall IPv6"
               ]
    formatted_list = []
    for zone_conf in zone_policy:
        formatted_list.append(output_zone_list(zone_conf))
    tabulate.PRESERVE_WHITESPACE = True
    output = tabulate.tabulate(formatted_list, headers, numalign="left")
    return output


def show(raw: bool, zone: typing.Optional[str]):
    """
    Show zone-policy command
    :param raw: if API
    :type raw: bool
    :param zone: zone name
    :type zone: str
    """
    conf: ConfigTreeQuery = ConfigTreeQuery()
    zones_config: dict = get_config_zone(conf, zone)
    zone_policy_api: list = _convert_config(zones_config, zone)
    if raw:
        return zone_policy_api
    else:
        return get_formatted_output(zone_policy_api)


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
