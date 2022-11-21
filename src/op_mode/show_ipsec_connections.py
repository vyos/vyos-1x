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

import sys

from vyos.util import convert_data


def _get_vici_sas():
    from vici import Session as vici_session

    try:
        session = vici_session()
    except PermissionError:
        print("You do not have a permission to connect to the IPsec daemon")
        sys.exit(1)
    except ConnectionRefusedError:
        print("IPsec is not runing")
        sys.exit(1)
    except Exception as e:
        print("An error occured: {0}".format(e))
        sys.exit(1)
    sas = list(session.list_sas())
    return convert_data(sas)


def _get_vici_connections():
    from vici import Session as vici_session

    try:
        session = vici_session()
    except PermissionError:
        print("You do not have a permission to connect to the IPsec daemon")
        sys.exit(1)
    except ConnectionRefusedError:
        print("IPsec is not runing")
        sys.exit(1)
    except Exception as e:
        print("An error occured: {0}".format(e))
        sys.exit(1)
    connections = list(session.list_conns())
    return convert_data(connections)


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
            return {}
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
    if not data:
        return 'down'
    for sa in data:
        # check if parent SA exist
        if connection_name not in sa.keys():
            return 'down'
        if sa[connection_name]['state'].lower() == 'established':
            return 'up'
        else:
            return 'down'


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
    if not data:
        return 'down'
    for sa in data:
        # check if parent SA exist
        if connection_name not in sa.keys():
            return 'down'
        child_sas = sa[connection_name]['child-sas']
        # Get all child SA states
        # there can be multiple SAs per tunnel
        child_sa_states = [
            v['state'] for k, v in child_sas.items() if v['name'] == tunnel_name
        ]
        return 'up' if 'INSTALLED' in child_sa_states else 'down'


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
            return {}
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
                    'esp_proposal': esp_proposal
                })
        base_dict.append(base_list)
    return base_dict


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


def main():
    list_conns = _get_vici_connections()
    list_sas = _get_vici_sas()
    connections = _get_raw_data_connections(list_conns, list_sas)
    return _get_formatted_output_conections(connections)


if __name__ == '__main__':
    print(main())
