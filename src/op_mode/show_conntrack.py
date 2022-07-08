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

import xmltodict

from tabulate import tabulate
from vyos.util import cmd


def _get_raw_data():
    """
    Get conntrack XML output
    """
    return cmd(f'sudo  conntrack --dump --output xml')


def _xml_to_dict(xml):
    """
    Convert XML to dictionary
    Return: dictionary
    """
    parse = xmltodict.parse(xml)
    # If only one conntrack entry we must change dict
    if 'meta' in parse['conntrack']['flow']:
        return dict(conntrack={'flow': [parse['conntrack']['flow']]})
    return parse


def _get_formatted_output(xml):
    """
    :param xml:
    :return: formatted output
    """
    data_entries = []
    dict_data = _xml_to_dict(xml)
    for entry in dict_data['conntrack']['flow']:
        src, dst, sport, dport, proto = {}, {}, {}, {}, {}
        for meta in entry['meta']:
            direction = meta['@direction']
            if direction in ['original']:
                if 'layer3' in meta:
                    src = meta['layer3']['src']
                    dst = meta['layer3']['dst']
                if 'layer4' in meta:
                    if meta.get('layer4').get('sport'):
                        sport = meta['layer4']['sport']
                    if meta.get('layer4').get('dport'):
                        dport = meta['layer4']['dport']
                    proto = meta['layer4']['@protoname']
            if direction == 'independent':
                conn_id = meta['id']
                timeout = meta['timeout']
                src = f'{src}:{sport}' if sport else src
                dst = f'{dst}:{dport}' if dport else dst
                state = meta['state'] if 'state' in meta else ''
                data_entries.append([conn_id, src, dst, proto, state, timeout])
    headers = ["Connection id", "Source", "Destination", "Protocol", "State", "Timeout"]
    output = tabulate(data_entries, headers, numalign="left")
    return output


def show(raw: bool):
    conntrack_data = _get_raw_data()
    if raw:
        return conntrack_data
    else:
        return _get_formatted_output(conntrack_data)


if __name__ == '__main__':
    print(show(raw=False))
