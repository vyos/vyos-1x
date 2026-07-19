#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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
from vyos.utils.process import cmdl
from vyos.utils.network import get_vrf_tableid

import vyos.opmode

ArgFamily = typing.Literal['inet', 'inet6']

def _get_xml_data(family, orig_zone=None):
    """
    Get conntrack XML output
    """
    args = ['--dump', '--family', family, '--output', 'xml']
    if orig_zone is not None:
        args.extend(['--orig-zone', str(orig_zone)])

    return cmdl(['conntrack'] + args, sudo=True)


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


def _get_raw_data(family, orig_zone=None):
    """
    Return: dictionary
    """
    xml = _get_xml_data(family, orig_zone=orig_zone)
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
    data = cmdl(['conntrack', '--stats'], sudo=True)
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
        orig_packets = orig_bytes = reply_packets = reply_bytes = '0'
        zone = ''
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
                if 'counters' in meta:
                    orig_packets = meta['counters']['packets']
                    orig_bytes = meta['counters']['bytes']
                if 'zone' in meta:
                    zone = meta['zone']
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
                if 'counters' in meta:
                    reply_packets = meta['counters']['packets']
                    reply_bytes = meta['counters']['bytes']
            if direction == 'independent':
                # T6138 flowtable offload conntrack entries without 'timeout'
                timeout = meta.get('timeout', 'n/a')
                orig_src = f'{orig_src}:{orig_sport}' if orig_sport else orig_src
                orig_dst = f'{orig_dst}:{orig_dport}' if orig_dport else orig_dst
                reply_src = f'{reply_src}:{reply_sport}' if reply_sport else reply_src
                reply_dst = f'{reply_dst}:{reply_dport}' if reply_dport else reply_dst
                state = meta['state'] if 'state' in meta else ''
                mark = meta['mark'] if 'mark' in meta else ''
                if 'zone' in meta:
                    zone = meta['zone']
                data_entry = [
                    orig_src,
                    orig_dst,
                    orig_packets,
                    orig_bytes,
                    reply_src,
                    reply_dst,
                    reply_packets,
                    reply_bytes,
                    proto,
                    state,
                    timeout,
                    mark,
                    zone,
                ]
                data_entries.append(data_entry)
    headers = [
        "Original src",
        "Original dst",
        "Original packets",
        "Original bytes",
        "Reply src",
        "Reply dst",
        "Reply packets",
        "Reply bytes",
        "Protocol",
        "State",
        "Timeout",
        "Mark",
        "Zone",
    ]
    output = tabulate(data_entries, headers, numalign="left")
    return output


def show(raw: bool, family: ArgFamily, vrf: typing.Optional[str]):
    family = 'ipv6' if family == 'inet6' else 'ipv4'

    orig_zone = get_vrf_tableid(vrf) if vrf else None
    if vrf and orig_zone is None:  # VRF is specified, but tableid is not found
        raise vyos.opmode.IncorrectValue(f'VRF \'{vrf}\' not found or has no table ID')

    conntrack_data = _get_raw_data(family, orig_zone=orig_zone)
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
