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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json
import requests
import sys
import typing
import shutil

from datetime import datetime
from tabulate import tabulate
from pathlib import Path

import vyos.opmode
from vyos.utils.process import cmd
from vyos.utils.process import rc_cmd
from vyos.configquery import op_mode_config_dict
from vyos.utils.dict import dict_search
from vyos.utils.dict import dict_set_nested

zt_config_path = Path('/config/vyos-generated-zerotier')

def detailed_output(dataset, headers):
    for data in dataset:
        adjusted_rule = data + [""] * (len(headers) - len(data)) # account for different header length, like default-action
        transformed_rule = [[header, adjusted_rule[i]] for i, header in enumerate(headers) if i < len(adjusted_rule)] # create key-pair list from headers and rules lists; wrap at 100 char

        print(tabulate(transformed_rule, tablefmt="presto"))
        print()


def _get_zt_cli_data(interface: str,
                     command: str,
                     raw: bool,
                     return_json: bool):
    command = f"zerotier-cli -D/config/vyos-generated-zerotier/{interface} {command}"
    if raw or return_json:
        command += " -j"

    if raw:
        rc, tmp = rc_cmd(command)
        if rc != 0:
            raise vyos.opmode.Error(f"Command execution failed")
        return json.loads(tmp)
    elif return_json:
        rc, tmp = rc_cmd(command)
        if rc != 0:
            raise vyos.opmode.Error(f"Command execution failed")
        return json.loads(tmp)
    else:
        rc, tmp = rc_cmd(command)
        if rc != 0:
            raise vyos.opmode.Error(f"Command execution failed")

    return tmp


def zt_api(url, api_token, api_type):
    # Create the headers for API calls
    if api_type == "service":
        headers = {
            "X-ZT1-Auth": api_token
        }
    elif api_type == "central":
        headers = {
            'Authorization': f'token {api_token}'
        }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raises HTTPError for bad responses (4xx and 5xx)
        return response
    except requests.exceptions.HTTPError as http_err:
        raise vyos.opmode.Error(f'HTTP error occurred: {http_err}')
    except Exception as err:
        raise vyos.opmode.Error(f'Other error occurred: {err}')


def show(raw: bool,
         return_json: bool,
         interface: typing.Optional[str],
         command: typing.Optional[str]):

    rc, output = rc_cmd(f'systemctl --no-block status vyos-zerotier-{interface}')
    if rc != 0:
        raise vyos.opmode.Error(f"ZeroTier service is not active for interface {interface}")

    cli_data = _get_zt_cli_data(interface, command, raw, return_json);

    if raw:
        return {'zerotier': cli_data}
    elif return_json:
        return json.dumps(cli_data, indent=4)
    else:
        return cli_data


def show_peers(raw: bool,
               interface: typing.Optional[str],
               peers_detail: bool,
               detail: bool):

    localNodeList = []
    controllerNodeList = []
    controllerNetworkList = []

    peer_dict = op_mode_config_dict(['interfaces', 'zerotier', interface], key_mangling=('-', '_'), get_first_key=True)
    primary_port = dict_search('primary.port', peer_dict)

    # peers-all and peers-detail does API calls to ZeroTier Central and requires API key to be configured
    api_token = dict_search('controller_api_key', peer_dict)
    if not api_token:
        raise vyos.opmode.Error("This command requires a ZeroTier Central API key to be configured")

    # Use ZeroTier Central API by default; allow for custom controller URL
    controller_url = dict_search('controller_api_url', peer_dict)
    if not controller_url:
        controller_url = 'https://api.zerotier.com/api/v1'

    # Generate a list to filter by nodes with an active connection
    if peers_detail:
        # Get the api token for local API call
        token_path = zt_config_path / interface / 'authtoken.secret'
        if not token_path.exists():
            raise vyos.opmode.Error(
                f"authtoken.secret not found! This should have been created when creating an interface. Does {interface} exist"
            )

        authtoken = token_path.read_text()

        network_data = zt_api(f'http://127.0.0.1:{primary_port}/peer', authtoken, 'service').json()
        for peers in network_data:
            localNodeList.append(peers['address'])

    # Get list of all networks in a ZeroTier controller
    network_data = zt_api(f'{controller_url}/network', api_token, 'central').json()
    for networks in network_data:
        controllerNetworkList.append(networks['id'])

    raw_dict = {}
    for controllerNode in controllerNetworkList:
        network_data = zt_api(f'{controller_url}/network/{controllerNode}/member', api_token, 'central').json()
        for member in network_data:
            if peers_detail:
                if localNodeList and member['nodeId'] in localNodeList:
                    if raw:
                        dict_set_nested(f'zerotier.networks.{controllerNode}.members.{member["nodeId"]}',
                                        member ,
                                        raw_dict)
                        continue

                    controllerNodeList.append([
                        dict_search('name', member),
                        dict_search('nodeId', member),
                        dict_search('description', member),
                        '\n'.join(dict_search('config.ipAssignments', member)),
                        dict_search('networkId', member),
                        dict_search('physicalAddress', member),
                        *([datetime.fromtimestamp(dict_search('lastSeen', member)/1000).strftime("%d %b %Y %H:%M")] if detail else []),
                        *([dict_search('clientVersion', member)] if detail else []),
                        *([dict_search('config.authorized', member)] if detail else [])
                    ])
            else:
                if raw:
                    dict_set_nested(f'zerotier.networks.{controllerNode}.members.{member["nodeId"]}',
                                    member ,
                                    raw_dict)
                    continue

                controllerNodeList.append([
                    dict_search('name', member),
                    dict_search('nodeId', member),
                    dict_search('description', member),
                    '\n'.join(dict_search('config.ipAssignments', member)),
                    dict_search('networkId', member),
                    dict_search('physicalAddress', member)
                    ])

    if raw:
        return raw_dict

    if detail:
        headers = ['Name', 'NodeID', 'Description', 'ZeroTier IP', 'Network', 'Public IP', 'Last Seen', 'Version', 'Authorized']

        sorted_list = sorted(controllerNodeList, key=lambda x: x[0].lower())
        detailed_output(sorted_list, headers)
    else:
        headers = ['Name', 'NodeID', 'Description', 'ZeroTier IP', 'Network', 'Public IP']

        sorted_list = sorted(controllerNodeList, key=lambda x: x[0].lower())
        print(tabulate(sorted_list, headers))


def set(raw: bool,
        allowed: str,
        interface: str,
        network_id: str,
        state: str):

    rc, output = rc_cmd(f'systemctl --no-block status vyos-zerotier-{interface}')
    if rc != 0:
        raise vyos.opmode.Error(f"ZeroTier service is not active for interface {interface}")

    interface_path = zt_config_path / interface

    cmd(f"zerotier-cli -D{interface_path} set {network_id} {allowed}={state}")


def restart(interface: str):
    rc, output = rc_cmd(f'systemctl --no-block status vyos-zerotier-{interface}')
    if rc != 0:
        raise vyos.opmode.Error(f"Failed to restart {interface}. Does {interface} exist?")

    cmd(f'systemctl --no-block restart vyos-zerotier-{interface}')

def delete_config(interface: str):
    rc, output = rc_cmd(f'systemctl --no-block status vyos-zerotier-{interface}')
    if rc == 0:
        raise vyos.opmode.Error(f"Interface {interface} is active. Unable to delete config directory")

    config_path = zt_config_path / interface
    if not config_path.exists():
        raise vyos.opmode.Error(f"Config directory does not exist; nothing to archive")

    if any(config_path.iterdir()):
        archive_path = zt_config_path / 'archive' / f'{interface}-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
        shutil.move(config_path, archive_path)
    else:
        raise vyos.opmode.Error(f"Config directory is empty; nothing to archive")

    if any(archive_path.iterdir()):
        print(f"Archive created at {archive_path}")
    else:
        raise vyos.opmode.Error(f"Failed to create archive")


def import_config(path: str):
    archive_path = zt_config_path / 'archive' / path
    config_path = zt_config_path / path.split('-')[0]

    if config_path.exists():
        raise vyos.opmode.Error(f"Config directory already exists; cannot import config")

    if archive_path.exists():
        shutil.move(archive_path, config_path)
    else:
        raise vyos.opmode.Error(f"Archive not found")

    if config_path.exists():
        print(f"Config imported from {archive_path} to {config_path}")
    else:
        raise vyos.opmode.Error(f"Failed to import config")


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
