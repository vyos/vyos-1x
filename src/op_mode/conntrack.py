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

import sys
import typing
import xmltodict

from tabulate import tabulate
from vyos.utils.process import cmd

import vyos.opmode

ArgFamily = typing.Literal['inet', 'inet6']

def _get_xml_data(family):
    """
    Get conntrack XML output
    """
    return cmd(f'sudo conntrack --dump --family {family} --output xml')


def _xml_to_dict(xml):
    """
    Convert XML to dictionary
    Return: dictionary
    """
    parse = xmltodict.parse(xml, attr_prefix='')
    # If only one conntrack entry we must change dict
    if 'meta' in parse['conntrack']['flow']:
        return dict(conntrack={'flow': [parse['conntrack']['flow']]})
    return parse


def _get_raw_data(family):
    """
    Return: dictionary
    """
    xml = _get_xml_data(family)
    if len(xml) == 0:
        output = {'conntrack':
            {
                'error': True,
                'reason': 'entries not found'
            }
        }
        return output
    return _xml_to_dict(xml)


def _get_raw_statistics():
    entries = []
    data = cmd('sudo conntrack --stats')
    data = data.replace('  \t', '').split('\n')
    for entry in data:
        entries.append(entry.split())
    return entries


def get_formatted_statistics(entries):
    headers = [
        "CPU",
        "Found",
        "Invalid",
        "Insert",
        "Insert fail",
        "Drop",
        "Early drop",
        "Errors",
        "Search restart",
        "",
        "",
    ]
    # Process each entry to extract and format the values after '='
    processed_entries = [
        [value.split('=')[-1] for value in entry]
        for entry in entries
    ]
    output = tabulate(processed_entries, headers, numalign="left")
    return output


def get_formatted_output(dict_data):
    """
    :param xml:
    :return: formatted output
    """
    data_entries = []
    if 'error' in dict_data['conntrack']:
        return 'Entries not found'
    for entry in dict_data['conntrack']['flow']:
        orig_src, orig_dst, orig_sport, orig_dport = {}, {}, {}, {}
        reply_src, reply_dst, reply_sport, reply_dport = {}, {}, {}, {}
        proto = {}
        for meta in entry['meta']:
            direction = meta['direction']
            if direction in ['original']:
                if 'layer3' in meta:
                    orig_src = meta['layer3']['src']
                    orig_dst = meta['layer3']['dst']
                if 'layer4' in meta:
                    if meta.get('layer4').get('sport'):
                        orig_sport = meta['layer4']['sport']
                    if meta.get('layer4').get('dport'):
                        orig_dport = meta['layer4']['dport']
                    proto = meta['layer4']['protoname']
            if direction in ['reply']:
                if 'layer3' in meta:
                    reply_src = meta['layer3']['src']
                    reply_dst = meta['layer3']['dst']
                if 'layer4' in meta:
                    if meta.get('layer4').get('sport'):
                        reply_sport = meta['layer4']['sport']
                    if meta.get('layer4').get('dport'):
                        reply_dport = meta['layer4']['dport']
                    proto = meta['layer4']['protoname']
            if direction == 'independent':
                conn_id = meta['id']
                # T6138 flowtable offload conntrack entries without 'timeout'
                timeout = meta.get('timeout', 'n/a')
                orig_src = f'{orig_src}:{orig_sport}' if orig_sport else orig_src
                orig_dst = f'{orig_dst}:{orig_dport}' if orig_dport else orig_dst
                reply_src = f'{reply_src}:{reply_sport}' if reply_sport else reply_src
                reply_dst = f'{reply_dst}:{reply_dport}' if reply_dport else reply_dst
                state = meta['state'] if 'state' in meta else ''
                mark = meta['mark'] if 'mark' in meta else ''
                zone = meta['zone'] if 'zone' in meta else ''
                data_entries.append(
                    [conn_id, orig_src, orig_dst, reply_src, reply_dst, proto, state, timeout, mark, zone])
    headers = ["Id", "Original src", "Original dst", "Reply src", "Reply dst", "Protocol", "State", "Timeout", "Mark",
               "Zone"]
    output = tabulate(data_entries, headers, numalign="left")
    return output


def show(raw: bool, family: ArgFamily):
    family = 'ipv6' if family == 'inet6' else 'ipv4'
    conntrack_data = _get_raw_data(family)
    if raw:
        return conntrack_data
    else:
        return get_formatted_output(conntrack_data)


def show_statistics(raw: bool):
    conntrack_statistics = _get_raw_statistics()
    if raw:
        return conntrack_statistics
    else:
        return get_formatted_statistics(conntrack_statistics)


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
