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

import re
import sys

from collections import OrderedDict
from hurry import filesize
from re import split as re_split
from tabulate import tabulate

from vyos.util import call
from vyos.util import convert_data
from vyos.util import seconds_to_human

import vyos.opmode


SWANCTL_CONF = '/etc/swanctl/swanctl.conf'


def _convert(text):
    return int(text) if text.isdigit() else text.lower()


def _alphanum_key(key):
    return [_convert(c) for c in re_split('([0-9]+)', str(key))]


def _get_vici_sas():
    from vici import Session as vici_session

    session = vici_session()
    sas = list(session.list_sas())
    return sas


def _get_raw_data_sas():
    get_sas = _get_vici_sas()
    sas = convert_data(get_sas)
    return sas


def _get_formatted_output_sas(sas):
    sa_data = []
    for sa in sas:
        for parent_sa in sa.values():
            # create an item for each child-sa
            for child_sa in parent_sa.get('child-sas', {}).values():
                # prepare a list for output data
                sa_out_name = sa_out_state = sa_out_uptime = sa_out_bytes = sa_out_packets = sa_out_remote_addr = sa_out_remote_id = sa_out_proposal = 'N/A'

                # collect raw data
                sa_name = child_sa.get('name')
                sa_state = child_sa.get('state')
                sa_uptime = child_sa.get('install-time')
                sa_bytes_in = child_sa.get('bytes-in')
                sa_bytes_out = child_sa.get('bytes-out')
                sa_packets_in = child_sa.get('packets-in')
                sa_packets_out = child_sa.get('packets-out')
                sa_remote_addr = parent_sa.get('remote-host')
                sa_remote_id = parent_sa.get('remote-id')
                sa_proposal_encr_alg = child_sa.get('encr-alg')
                sa_proposal_integ_alg = child_sa.get('integ-alg')
                sa_proposal_encr_keysize = child_sa.get('encr-keysize')
                sa_proposal_dh_group = child_sa.get('dh-group')

                # format data to display
                if sa_name:
                    sa_out_name = sa_name
                if sa_state:
                    if sa_state == 'INSTALLED':
                        sa_out_state = 'up'
                    else:
                        sa_out_state = 'down'
                if sa_uptime:
                    sa_out_uptime = seconds_to_human(sa_uptime)
                if sa_bytes_in and sa_bytes_out:
                    bytes_in = filesize.size(int(sa_bytes_in))
                    bytes_out = filesize.size(int(sa_bytes_out))
                    sa_out_bytes = f'{bytes_in}/{bytes_out}'
                if sa_packets_in and sa_packets_out:
                    packets_in = filesize.size(int(sa_packets_in),
                                               system=filesize.si)
                    packets_out = filesize.size(int(sa_packets_out),
                                                system=filesize.si)
                    packets_str = f'{packets_in}/{packets_out}'
                    sa_out_packets = re.sub(r'B', r'', packets_str)
                if sa_remote_addr:
                    sa_out_remote_addr = sa_remote_addr
                if sa_remote_id:
                    sa_out_remote_id = sa_remote_id
                # format proposal
                if sa_proposal_encr_alg:
                    sa_out_proposal = sa_proposal_encr_alg
                if sa_proposal_encr_keysize:
                    sa_proposal_encr_keysize_str = sa_proposal_encr_keysize
                    sa_out_proposal = f'{sa_out_proposal}_{sa_proposal_encr_keysize_str}'
                if sa_proposal_integ_alg:
                    sa_proposal_integ_alg_str = sa_proposal_integ_alg
                    sa_out_proposal = f'{sa_out_proposal}/{sa_proposal_integ_alg_str}'
                if sa_proposal_dh_group:
                    sa_proposal_dh_group_str = sa_proposal_dh_group
                    sa_out_proposal = f'{sa_out_proposal}/{sa_proposal_dh_group_str}'

                # add a new item to output data
                sa_data.append([
                    sa_out_name, sa_out_state, sa_out_uptime, sa_out_bytes,
                    sa_out_packets, sa_out_remote_addr, sa_out_remote_id,
                    sa_out_proposal
                ])

    headers = [
        "Connection", "State", "Uptime", "Bytes In/Out", "Packets In/Out",
        "Remote address", "Remote ID", "Proposal"
    ]
    sa_data = sorted(sa_data, key=_alphanum_key)
    output = tabulate(sa_data, headers)
    return output


def get_peer_connections(peer, tunnel, return_all = False):
    search = rf'^[\s]*({peer}-(tunnel-[\d]+|vti)).*'
    matches = []
    with open(SWANCTL_CONF, 'r') as f:
        for line in f.readlines():
            result = re.match(search, line)
            if result:
                suffix = f'tunnel-{tunnel}' if tunnel.isnumeric() else tunnel
                if return_all or (result[2] == suffix):
                    matches.append(result[1])
    return matches


def reset_peer(peer: str, tunnel:str):
    if not peer:
        print('Invalid peer, aborting')
        return

    conns = get_peer_connections(peer, tunnel, return_all = (not tunnel or tunnel == 'all'))

    if not conns:
        print('Tunnel(s) not found, aborting')
        return

    result = True
    for conn in conns:
        try:
            call(f'sudo /usr/sbin/ipsec down {conn}{{*}}', timeout = 10)
            call(f'sudo /usr/sbin/ipsec up {conn}', timeout = 10)
        except TimeoutExpired as e:
            print(f'Timed out while resetting {conn}')
            result = False


    print('Peer reset result: ' + ('success' if result else 'failed'))


def show_sa(raw: bool):
    sa_data = _get_raw_data_sas()
    if raw:
        return sa_data
    return _get_formatted_output_sas(sa_data)


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
