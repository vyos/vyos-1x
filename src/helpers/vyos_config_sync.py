#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
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
from typing import Optional, List, Union, Dict, Any

from vyos.config import Config
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


def retrieve_config(section: str = None) -> Optional[Dict[str, Any]]:
    """Retrieves the configuration from the local server.

    Args:
        section: str: The section of the configuration to retrieve. Default is None.

    Returns:
        Optional[Dict[str, Any]]: The retrieved configuration as a dictionary, or None if an error occurred.
    """
    if section is None:
        section = []
    else:
        section = section.split()

    conf = Config()
    config = conf.get_config_dict(section, get_first_key=True)
    if config:
        return config
    return None


def set_remote_config(
        address: str,
        key: str,
        op: str,
        path: str = None,
        section: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Loads the VyOS configuration in JSON format to a remote host.

    Args:
        address (str): The address of the remote host.
        key (str): The key to use for loading the configuration.
        path (Optional[str]): The path of the configuration. Default is None.
        section (Optional[str]): The section of the configuration to load. Default is None.

    Returns:
        Optional[Dict[str, Any]]: The response from the remote host as a dictionary, or None if an error occurred.
    """

    if path is None:
        path = []
    else:
        path = path.split()
    headers = {'Content-Type': 'application/json'}

    # Disable the InsecureRequestWarning
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    url = f'https://{address}/configure-section'
    data = json.dumps({
        'op': mode,
        'path': path,
        'section': section,
        'key': key
    })

    try:
        config = post_request(url, data, headers)
        return config.json()
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        logger.error(f"An error occurred: {e}")
        return None


def is_section_revised(section: str) -> bool:
    from vyos.config_mgmt import is_node_revised
    return is_node_revised([section])


def config_sync(secondary_address: str,
                secondary_key: str,
                sections: List[str],
                mode: str):
    """Retrieve a config section from primary router in JSON format and send it to
       secondary router
    """
    # Config sync only if sections changed
    if not any(map(is_section_revised, sections)):
        return

    logger.info(
        f"Config synchronization: Mode={mode}, Secondary={secondary_address}"
    )

    # Sync sections ("nat", "firewall", etc)
    for section in sections:
        config_json = retrieve_config(section=section)
        # Check if config path deesn't exist, for example "set nat"
        # we set empty value for config_json data
        # As we cannot send to the remote host section "nat None" config
        if not config_json:
            config_json = ""
        logger.debug(
            f"Retrieved config for section '{section}': {config_json}")
        set_config = set_remote_config(address=secondary_address,
                                       key=secondary_key,
                                       op=mode,
                                       path=section,
                                       section=config_json)
        logger.debug(f"Set config for section '{section}': {set_config}")


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
    sections = config.get('section')
    timeout = int(config.get('secondary', {}).get('timeout'))

    if not all([
            mode, secondary_address, secondary_key, sections
    ]):
        logger.error(
            "Missing required configuration data for config synchronization.")
        exit(0)

    config_sync(secondary_address, secondary_key,
                sections, mode)
