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
CONFIG_DIR = r'/etc'
CONFIG_FILE = r'saml-sso-idp.conf'

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

def toggle_service(service: str, enable: bool) -> bool:
    try:
        if enable:
            subprocess.run(['systemctl', 'daemon-reload'], check=True)
            subprocess.run(['systemctl', 'enable', service], check=True)
            subprocess.run(['systemctl', 'start', service], check=True)
        else:
            subprocess.run(['systemctl', 'stop', service], check=True)
            subprocess.run(['systemctl', 'disable', service], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error toggling service '{service}': {e}")
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
    idp = config_dict.get('idp', {})
    if not idp:
        return # No idp config, kick out early

    for name, provider in idp.items():
        # Validate metadata URL
        metadata_url = provider.get('metadata_url', None)
        if not metadata_url:
            raise ConfigError(f"IDP: {name} must have metadata-url")
        if not check_url(metadata_url) and not check_ip(metadata_url):
            raise ConfigError(f"IDP: {name} must have a valid metadata-url")

        # Validate domains
        domains = provider.get('domain', [])
        if not isinstance(domains, list):
            domains = [domains]
        if not domains:
            raise ConfigError(f"IDP: {name} must have at least one configured domain")
        if not all(isinstance(domain, str) and domain.strip() for domain in domains):
            raise ConfigError(f"IDP: {name}, domains must be strings")

        # Validate attributes
        attributes = provider.get('attribute', {}).get('attr', {})
        if not attributes:
            print(f"WARNING: IDP: {name} has no attributes configured")
        else:
            for attr_name, attribute in attributes.items():
                if not attribute:
                    raise ConfigError(f"IDP: {name} Attribute: {attr_name} must have atleaset one possible value")

                values = attribute.get('value', [])
                if not isinstance(values, list):
                    values = [values]
                if not values:
                    raise ConfigError(f"IDP: {name} Attribute: {attr_name} must have atleaset one possible value")
                if not all(isinstance(value, str) and value.strip() for value in values):
                    raise ConfigError(f"IDP: {name} Attribute: {attr_name} values must be strings")

        # Validate users
        users = provider.get('user', [])
        if not isinstance(users, list):
            users = [users]
        if not users:
            print(f"WARNING: IDP: {name} has no users configured")
        else:
            if not all(isinstance(user, str) and user.strip() for user in users):
                raise ConfigError(f"IDP: {name}, users must be strings")

def generate(config_dict):
    try:
        if not os.path.exists(CONFIG_DIR):
            os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(f"{CONFIG_DIR}/{CONFIG_FILE}", 'w') as conf_file:
            json.dump(config_dict, conf_file, indent=4)
    except Exception:
        raise ConfigError("Could not generate config file")

def apply(config_dict):
    idp = config_dict.get('idp', {})
    enable = True if idp else False

    if not toggle_pam_profile('saml_auth', enable):
        raise ConfigError("Failed to toggle saml_auth PAM profile")

    if not toggle_service('saml-sp', enable):
        raise ConfigError("Failed to toggle saml-sp service")

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
