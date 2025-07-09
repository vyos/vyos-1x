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
    Uses the ipaddress module to validate the IP address.
    :param ip: The string to check.
    :return: True if valid IP address, False otherwise.
    """
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def toggle_pam_profile(profile: str, enable: bool) -> bool:
    """
    Toggle a PAM profile using the pam-auth-update command.
    Uses subprocess to run the command and handle errors.
    :param profile: The name of the PAM profile to toggle.
    :param enable: True to enable the profile, False to disable it.
    :return: True if the profile was toggled successfully, False otherwise.
    """

    cmd = ['pam-auth-update', '--remove' if not enable else '--enable', profile]

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error enabling PAM profile '{profile}': {e.stderr.strip() if e.stderr else str(e)}")
        return False
    except FileNotFoundError:
        print(f"Command 'pam-auth-update' not found. Ensure the package is installed.")
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

        # Validate attributes / users
        if 'attribute' not in idp or not idp['attribute'] or not 'attr' in idp['attribute'] or not idp['attribute']['attr']:
            print(f"WARNING: IDP '{name}' has no attributes defined, this is not an error but you may want to define some")
        else:
            attributes = idp['attribute']['attr']
            if isinstance(attributes, str):
                attributes = [attributes]
            if not isinstance(attributes, list) or not all(isinstance(attr, str) and attr.strip() for attr in attributes):
                raise ConfigError(f"IDP '{name}' 'attribute' must be a list of strings")

        if "user" not in idp or not idp['user']:
            print(f"WARNING: IDP '{name}' has no users defined, this is not an error but you may want to define some")
        else:
            users = idp['user']
            if isinstance(users, str):
                users = [users]
            if not isinstance(users, list) or not all(isinstance(user, str) and user.strip() for user in users):
                raise ConfigError(f"IDP '{name}' 'user' must be a list of strings")

def generate(config_dict):
    # Genrate the IDP configuration file even if the user did not specify an IDP configuration (it will just be empty)
    config_json = json.dumps(config_dict, indent=4) if 'idp' in config_dict and config_dict['idp'] else '{}'

    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR, exist_ok=True)

    with open(f"{CONFIG_DIR}/idp.conf", 'w') as f:
        f.write(config_json)

def apply(config_dict):
    enable = True if 'idp' in config_dict and config_dict['idp'] else False

    if not toggle_pam_profile('saml-auth', enable):
        raise ConfigError("Failed to toggle pam profile for saml-auth")

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
