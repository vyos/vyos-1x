#!/usr/bin/env python3
#
# Copyright (C) 2023-2024 VyOS maintainers and contributors
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
#
#

import os
import json
import requests
import urllib3
import logging
from typing import Optional, List, Tuple, Dict, Any

from vyos.config import Config
from vyos.configtree import ConfigTree
from vyos.configtree import mask_inclusive
from vyos.template import bracketize_ipv6


CONFIG_FILE = '/run/config_sync_conf.conf'

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.name = os.path.basename(__file__)

# API
API_HEADERS = {'Content-Type': 'application/json'}


def post_request(url: str,
                 data: str,
                 headers: Dict[str, str]) -> requests.Response:
    """Sends a POST request to the specified URL

    Args:
        url (str): The URL to send the POST request to.
        data (Dict[str, Any]): The data to send with the POST request.
        headers (Dict[str, str]): The headers to include with the POST request.

    Returns:
        requests.Response: The response object representing the server's response to the request
    """

    response = requests.post(url,
                             data=data,
                             headers=headers,
                             verify=False,
                             timeout=timeout)
    return response



def retrieve_config(sections: List[list[str]]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Retrieves the configuration from the local server.

    Args:
        sections: List[list[str]]: The list of sections of the configuration
        to retrieve, given as list of paths.

    Returns:
        Tuple[Dict[str, Any],Dict[str,Any]]: The tuple (mask, config) where:
            - mask: The tree of paths of sections, as a dictionary.
            - config: The subtree of masked config data, as a dictionary.
    """

    mask = ConfigTree('')
    for section in sections:
        mask.set(section)
    mask_dict = json.loads(mask.to_json())

    config = Config()
    config_tree = config.get_config_tree()
    masked = mask_inclusive(config_tree, mask)
    config_dict = json.loads(masked.to_json())

    return mask_dict, config_dict

def set_remote_config(
        address: str,
        key: str,
        op: str,
        mask: Dict[str, Any],
        config: Dict[str, Any],
        port: int) -> Optional[Dict[str, Any]]:
    """Loads the VyOS configuration in JSON format to a remote host.

    Args:
        address (str): The address of the remote host.
        key (str): The key to use for loading the configuration.
        op (str): The operation to perform (set or load).
        mask (dict): The dict of paths in sections.
        config (dict): The dict of masked config data.
        port (int): The remote API port

    Returns:
        Optional[Dict[str, Any]]: The response from the remote host as a
        dictionary, or None if a RequestException occurred.
    """

    headers = {'Content-Type': 'application/json'}

    # Disable the InsecureRequestWarning
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    url = f'https://{address}:{port}/configure-section'
    data = json.dumps({
        'op': op,
        'mask': mask,
        'config': config,
        'key': key
    })

    try:
        config = post_request(url, data, headers)
        return config.json()
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        logger.error(f"An error occurred: {e}")
        return None


def is_section_revised(section: List[str]) -> bool:
    from vyos.config_mgmt import is_node_revised
    return is_node_revised(section)


def config_sync(secondary_address: str,
                secondary_key: str,
                sections: List[list[str]],
                mode: str,
                secondary_port: int):
    """Retrieve a config section from primary router in JSON format and send it to
       secondary router
    """
    if not any(map(is_section_revised, sections)):
        return

    logger.info(
        f"Config synchronization: Mode={mode}, Secondary={secondary_address}"
    )

    # Sync sections ("nat", "firewall", etc)
    mask_dict, config_dict = retrieve_config(sections)
    logger.debug(
        f"Retrieved config for sections '{sections}': {config_dict}")

    set_config = set_remote_config(address=secondary_address,
                                   key=secondary_key,
                                   op=mode,
                                   mask=mask_dict,
                                   config=config_dict,
                                   port=secondary_port)

    logger.debug(f"Set config for sections '{sections}': {set_config}")


if __name__ == '__main__':
    # Read configuration from file
    if not os.path.exists(CONFIG_FILE):
        logger.error(f"Post-commit: No config file '{CONFIG_FILE}' exists")
        exit(0)

    with open(CONFIG_FILE, 'r') as f:
        config_data = f.read()

    config = json.loads(config_data)

    mode = config.get('mode')
    secondary_address = config.get('secondary', {}).get('address')
    secondary_address = bracketize_ipv6(secondary_address)
    secondary_key = config.get('secondary', {}).get('key')
    secondary_port = int(config.get('secondary', {}).get('port', 443))
    sections = config.get('section')
    timeout = int(config.get('secondary', {}).get('timeout'))

    if not all([mode, secondary_address, secondary_key, sections]):
        logger.error("Missing required configuration data for config synchronization.")
        exit(0)

    # Generate list_sections of sections/subsections
    # [
    #   ['interfaces', 'pseudo-ethernet'], ['interfaces', 'virtual-ethernet'], ['nat'], ['nat66']
    # ]
    list_sections = []
    for section, subsections in sections.items():
        if subsections:
            for subsection in subsections:
                list_sections.append([section, subsection])
        else:
            list_sections.append([section])

    config_sync(secondary_address, secondary_key, list_sections, mode, secondary_port)
