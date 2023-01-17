#!/usr/bin/env python3
#
# Copyright (C) 2022-2023 VyOS maintainers and contributors
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

import os
import re
import sys
import typing

from collections import OrderedDict
from hurry import filesize
from re import split as re_split
from tabulate import tabulate
from subprocess import TimeoutExpired

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

    try:
        session = vici_session()
    except Exception:
        raise vyos.opmode.UnconfiguredSubsystem("IPsec not initialized")
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


# Connections block
def _get_vici_connections():
    from vici import Session as vici_session

    try:
        session = vici_session()
    except Exception:
        raise vyos.opmode.UnconfiguredSubsystem("IPsec not initialized")
    connections = list(session.list_conns())
    return connections


def _get_convert_data_connections():
    get_connections = _get_vici_connections()
    connections = convert_data(get_connections)
    return connections


def _get_parent_sa_proposal(connection_name: str, data: list) -> dict:
    """Get parent SA proposals by connection name
    if connections not in the 'down' state

    Args:
        connection_name (str): Connection name
        data (list): List of current SAs from vici

    Returns:
        str: Parent SA connection proposal
             AES_CBC/256/HMAC_SHA2_256_128/MODP_1024
    """
    if not data:
        return {}
    for sa in data:
        # check if parent SA exist
        if connection_name not in sa.keys():
            continue
        if 'encr-alg' in sa[connection_name]:
            encr_alg = sa.get(connection_name, '').get('encr-alg')
            cipher = encr_alg.split('_')[0]
            mode = encr_alg.split('_')[1]
            encr_keysize = sa.get(connection_name, '').get('encr-keysize')
            integ_alg = sa.get(connection_name, '').get('integ-alg')
            # prf_alg = sa.get(connection_name, '').get('prf-alg')
            dh_group = sa.get(connection_name, '').get('dh-group')
            proposal = {
                'cipher': cipher,
                'mode': mode,
                'key_size': encr_keysize,
                'hash': integ_alg,
                'dh': dh_group
            }
            return proposal
        return {}


def _get_parent_sa_state(connection_name: str, data: list) -> str:
    """Get parent SA state by connection name

    Args:
        connection_name (str): Connection name
        data (list): List of current SAs from vici

    Returns:
        Parent SA connection state
    """
    ike_state = 'down'
    if not data:
        return ike_state
    for sa in data:
        # check if parent SA exist
        for connection, connection_conf in sa.items():
            if connection_name != connection:
                continue
            if connection_conf['state'].lower() == 'established':
                ike_state = 'up'
    return ike_state


def _get_child_sa_state(connection_name: str, tunnel_name: str,
                        data: list) -> str:
    """Get child SA state by connection and tunnel name

    Args:
        connection_name (str): Connection name
        tunnel_name (str): Tunnel name
        data (list): List of current SAs from vici

    Returns:
        str: `up` if child SA state is 'installed' otherwise `down`
    """
    child_sa = 'down'
    if not data:
        return child_sa
    for sa in data:
        # check if parent SA exist
        if connection_name not in sa.keys():
            continue
        child_sas = sa[connection_name]['child-sas']
        # Get all child SA states
        # there can be multiple SAs per tunnel
        child_sa_states = [
            v['state'] for k, v in child_sas.items() if v['name'] == tunnel_name
        ]
        return 'up' if 'INSTALLED' in child_sa_states else child_sa


def _get_child_sa_info(connection_name: str, tunnel_name: str,
                       data: list) -> dict:
    """Get child SA installed info by connection and tunnel name

    Args:
        connection_name (str): Connection name
        tunnel_name (str): Tunnel name
        data (list): List of current SAs from vici

    Returns:
        dict: Info of the child SA in the dictionary format
    """
    for sa in data:
        # check if parent SA exist
        if connection_name not in sa.keys():
            continue
        child_sas = sa[connection_name]['child-sas']
        # Get all child SA data
        # Skip temp SA name (first key), get only SA values as dict
        # {'OFFICE-B-tunnel-0-46': {'name': 'OFFICE-B-tunnel-0'}...}
        # i.e get all data after 'OFFICE-B-tunnel-0-46'
        child_sa_info = [
            v for k, v in child_sas.items() if 'name' in v and
            v['name'] == tunnel_name and v['state'] == 'INSTALLED'
        ]
        return child_sa_info[-1] if child_sa_info else {}


def _get_child_sa_proposal(child_sa_data: dict) -> dict:
    if child_sa_data and 'encr-alg' in child_sa_data:
        encr_alg = child_sa_data.get('encr-alg')
        cipher = encr_alg.split('_')[0]
        mode = encr_alg.split('_')[1]
        key_size = child_sa_data.get('encr-keysize')
        integ_alg = child_sa_data.get('integ-alg')
        dh_group = child_sa_data.get('dh-group')
        proposal = {
            'cipher': cipher,
            'mode': mode,
            'key_size': key_size,
            'hash': integ_alg,
            'dh': dh_group
        }
        return proposal
    return {}


def _get_raw_data_connections(list_connections: list, list_sas: list) -> list:
    """Get configured VPN IKE connections and IPsec states

    Args:
        list_connections (list): List of configured connections from vici
        list_sas (list): List of current SAs from vici

    Returns:
        list: List and status of IKE/IPsec connections/tunnels
    """
    base_dict = []
    for connections in list_connections:
        base_list = {}
        for connection, conn_conf in connections.items():
            base_list['ike_connection_name'] = connection
            base_list['ike_connection_state'] = _get_parent_sa_state(
                connection, list_sas)
            base_list['ike_remote_address'] = conn_conf['remote_addrs']
            base_list['ike_proposal'] = _get_parent_sa_proposal(
                connection, list_sas)
            base_list['local_id'] = conn_conf.get('local-1', '').get('id')
            base_list['remote_id'] = conn_conf.get('remote-1', '').get('id')
            base_list['version'] = conn_conf.get('version', 'IKE')
            base_list['children'] = []
            children = conn_conf['children']
            for tunnel, tun_options in children.items():
                state = _get_child_sa_state(connection, tunnel, list_sas)
                local_ts = tun_options.get('local-ts')
                remote_ts = tun_options.get('remote-ts')
                dpd_action = tun_options.get('dpd_action')
                close_action = tun_options.get('close_action')
                sa_info = _get_child_sa_info(connection, tunnel, list_sas)
                esp_proposal = _get_child_sa_proposal(sa_info)
                base_list['children'].append({
                    'name': tunnel,
                    'state': state,
                    'local_ts': local_ts,
                    'remote_ts': remote_ts,
                    'dpd_action': dpd_action,
                    'close_action': close_action,
                    'sa': sa_info,
                    'esp_proposal': esp_proposal
                })
        base_dict.append(base_list)
    return base_dict


def _get_raw_connections_summary(list_conn, list_sas):
    import jmespath
    data = _get_raw_data_connections(list_conn, list_sas)
    match = '[*].children[]'
    child = jmespath.search(match, data)
    tunnels_down = len([k for k in child if k['state'] == 'down'])
    tunnels_up = len([k for k in child if k['state'] == 'up'])
    tun_dict = {
        'tunnels': child,
        'total': len(child),
        'down': tunnels_down,
        'up': tunnels_up
    }
    return tun_dict


def _get_formatted_output_conections(data):
    from tabulate import tabulate
    data_entries = ''
    connections = []
    for entry in data:
        tunnels = []
        ike_name = entry['ike_connection_name']
        ike_state = entry['ike_connection_state']
        conn_type = entry.get('version', 'IKE')
        remote_addrs = ','.join(entry['ike_remote_address'])
        local_ts, remote_ts = '-', '-'
        local_id = entry['local_id']
        remote_id = entry['remote_id']
        proposal = '-'
        if entry.get('ike_proposal'):
            proposal = (f'{entry["ike_proposal"]["cipher"]}_'
                        f'{entry["ike_proposal"]["mode"]}/'
                        f'{entry["ike_proposal"]["key_size"]}/'
                        f'{entry["ike_proposal"]["hash"]}/'
                        f'{entry["ike_proposal"]["dh"]}')
        connections.append([
            ike_name, ike_state, conn_type, remote_addrs, local_ts, remote_ts,
            local_id, remote_id, proposal
        ])
        for tun in entry['children']:
            tun_name = tun.get('name')
            tun_state = tun.get('state')
            conn_type = 'IPsec'
            local_ts = '\n'.join(tun.get('local_ts'))
            remote_ts = '\n'.join(tun.get('remote_ts'))
            proposal = '-'
            if tun.get('esp_proposal'):
                proposal = (f'{tun["esp_proposal"]["cipher"]}_'
                            f'{tun["esp_proposal"]["mode"]}/'
                            f'{tun["esp_proposal"]["key_size"]}/'
                            f'{tun["esp_proposal"]["hash"]}/'
                            f'{tun["esp_proposal"]["dh"]}')
            connections.append([
                tun_name, tun_state, conn_type, remote_addrs, local_ts,
                remote_ts, local_id, remote_id, proposal
            ])
    connection_headers = [
        'Connection', 'State', 'Type', 'Remote address', 'Local TS',
        'Remote TS', 'Local id', 'Remote id', 'Proposal'
    ]
    output = tabulate(connections, connection_headers, numalign='left')
    return output


# Connections block end


def get_peer_connections(peer, tunnel):
    search = rf'^[\s]*({peer}-(tunnel-[\d]+|vti)).*'
    matches = []
    if not os.path.exists(SWANCTL_CONF):
        raise vyos.opmode.UnconfiguredSubsystem("IPsec not initialized")
    suffix = None if tunnel is None else (f'tunnel-{tunnel}' if
                                          tunnel.isnumeric() else tunnel)
    with open(SWANCTL_CONF, 'r') as f:
        for line in f.readlines():
            result = re.match(search, line)
            if result:
                if tunnel is None:
                    matches.append(result[1])
                else:
                    if result[2] == suffix:
                        matches.append(result[1])
    return matches


def reset_peer(peer: str, tunnel:typing.Optional[str]):
    conns = get_peer_connections(peer, tunnel)

    if not conns:
        raise vyos.opmode.IncorrectValue('Peer or tunnel(s) not found, aborting')

    for conn in conns:
        try:
            call(f'sudo /usr/sbin/ipsec down {conn}{{*}}', timeout = 10)
            call(f'sudo /usr/sbin/ipsec up {conn}', timeout = 10)
        except TimeoutExpired as e:
            raise vyos.opmode.InternalError(f'Timed out while resetting {conn}')

    print('Peer reset result: success')


def show_sa(raw: bool):
    sa_data = _get_raw_data_sas()
    if raw:
        return sa_data
    return _get_formatted_output_sas(sa_data)


def show_connections(raw: bool):
    list_conns = _get_convert_data_connections()
    list_sas = _get_raw_data_sas()
    if raw:
        return _get_raw_data_connections(list_conns, list_sas)

    connections = _get_raw_data_connections(list_conns, list_sas)
    return _get_formatted_output_conections(connections)


def show_connections_summary(raw: bool):
    list_conns = _get_convert_data_connections()
    list_sas = _get_raw_data_sas()
    if raw:
        return _get_raw_connections_summary(list_conns, list_sas)


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
