#!/usr/bin/env python3
#
# Copyright (C) 2019-2024 VyOS maintainers and contributors
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

import os
import sys
import subprocess
import json
from vyos.config import Config
from vyos import ConfigError

from urllib.parse import urlparse
import ipaddress

# Directory where the SAML IDP configuration will be stored
CONFIG_DIR = r'/lib/security/saml-auth'

def check_url(url: str) -> bool:
    """
    Check if the given string is a valid URL.
    Returns True if valid, False otherwise.
    Uses urllib.parse to validate the URL.
    :param url: The string to check.
    :return: True if valid URL, False otherwise.
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def check_ip(ip: str) -> bool:
    """
    Check if the given string is a valid IP address (IPv4 or IPv6).
    Returns True if valid, False otherwise.
    Uses the ipaddress module to validate the IP address.
    :param ip: The string to check.
    :return: True if valid IP address, False otherwise.
    """
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def enable_pam_profile(profile: str) -> bool:
    """
    Enable a PAM profile using the pam-auth-update command.
    :param profile: The name of the PAM profile to enable.
    :return: True if the profile was enabled successfully, False otherwise.
    """
    cmd = ['pam-auth-update', '--enable', profile]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error enabling PAM profile '{profile}': {e.stderr.strip()}")
        return False
    except FileNotFoundError:
        print(f"Command 'pam-a  uth-update' not found. Ensure the package is installed.")
        return False
    except Exception as e:
        print(f"An unexpected error occurred while enabling PAM profile '{profile}': {str(e)}")
        return False

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['service', 'idp']

    config_data = conf.get_config_dict(base, key_mangling=('-', '_'))
    return config_data

def verify(config_dict):
    # User did not specify an IDP configuration kick out early
    if 'idp' not in config_dict or not config_dict['idp']:
        return

    for name, idp in config_dict['idp'].items():
        # Validate Metadata URL
        if 'metadata_url' not in idp:
            raise ConfigError(f"IDP '{name}' is missing 'metadata_url'")

        metadata_url = idp['metadata_url']
        if not check_url(metadata_url) and not check_ip(metadata_url):
            raise ConfigError(f"IDP '{name}' has an invalid 'metadata_url': {metadata_url}")

        # Validate Domains
        if 'domain' not in idp:
            raise ConfigError(f"IDP '{name}' must have at least one 'domain'")

        domains = idp['domain']
        if isinstance(domains, str):
            domains = [domains]

        if not isinstance(domains, list) or not domains:
            raise ConfigError(f"IDP '{name}' must have at least one 'domain'")

        if not all(isinstance(domain, str) and domain.strip() for domain in domains):
            raise ConfigError(f"IDP '{name}' 'domain' must be a list of strings")

def generate(config_dict):
    # User did not specify an IDP configuration kick out early
    if 'idp' not in config_dict or not config_dict['idp']:
        return

    config_json = json.dumps(config_dict, indent=4)

    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR, exist_ok=True)

    with open(f"{CONFIG_DIR}/idp.conf", 'w') as f:
        f.write(config_json)

def apply(config_dict):
    # User did not specify an IDP configuration kick out early
    if 'idp' not in config_dict or not config_dict['idp']:
        return

    # Enable the pam profile for saml-auth
    if not enable_pam_profile('saml-auth'):
        raise ConfigError("Failed to enable pam profile for saml-auth")

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
