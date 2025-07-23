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

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['service', 'idp']

    config_data = conf.get_config_dict(base, key_mangling=('-', '_'))
    return config_data

def verify(config_dict):
    def check_url(url: str) -> bool:
        """
        Verify if a string is a valid URL.

        Args:
            url (str): The URL string.

        Returns:
            True if the string is a valid URL false otherwise.
        """
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except ValueError:
            return False
    def check_ip(ip: str) -> bool:
        """
        Verify if a string is a valid IPv4/IPv6.

        Args:
            url (str): The IP string.

        Returns:
            True if the string is a valid IPv4/IPv6 false otherwise.
        """
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    def verify_attributes(attributes: dict):
        """
        Verify a list of attributes

        Args:
            attributes (dict): Attributes to verify.

        Raises:
            ConfigError: If attributes are not valid
        """
        req_attributes = attributes.get('req', {})
        suff_attributes = attributes.get('suff', {})
        for attr_name, attr in req_attributes.items():
            values = attr.get('value', [])
            if not values:
                raise ConfigError(f"IDP attribute '{attr_name}' must have a value")
            if not isinstance(values, list):
                values = [values]
            if not all(isinstance(value, str) and value.strip() for value in values):
                raise ConfigError(f"IDP attribute '{attr_name}' values must be non-empty strings")

        for attr_name, attr in suff_attributes.items():
            values = attr.get('value', [])
            if not values:
                raise ConfigError(f"IDP attribute '{attr_name}' must have a value")
            if not isinstance(values, list):
                values = [values]
            if not all(isinstance(value, str) and value.strip() for value in values):
                raise ConfigError(f"IDP attribute '{attr_name}' values must be non-empty strings")

    idp = config_dict.get('idp', {})

    providers = idp.get('providers', {})

    if not providers:
        return # Early kick out (no providers/idp)

    for provider_name, provider in providers.items():
        default_sso_level = provider.get('default_sso_level')
        if not default_sso_level:
            raise ConfigError("IDP: default-sso-level must be set as operator or admin")

        # Verify provider domains
        domains = provider.get('domain', [])
        if not isinstance(domains, list):
            domains = [domains]
        if not domains:
            raise ConfigError(f"IDP: {provider_name}: Must have atleast one domain set")
        if not all(isinstance(domain, str) and domain.strip() for domain in domains):
            raise ConfigError(f"IDP: {provider_name}: Domains must be non-empty strings")

        # Verify metadata-url
        metadata_url = provider.get('metadata_url')
        if not metadata_url:
            raise ConfigError(f"IDP: {provider_name}: Must have a metadata-url")
        if not check_url(metadata_url) and not check_ip(metadata_url):
            raise ConfigError(f"IDP: {provider_name}: metadata-url must be a valid URL")

        users = provider.get("user", {})
        attributes = provider.get("attribute", {})

        if not users and not attributes:
            print(f"""WARNING: IDP: '{provider_name}' has no attributes or users configured,\n
            any user from your domain list will be able to login at the default-sso-level""")

        # Verify Users
        admin_users = users.get('admin', [])
        operator_users = users.get('operator', [])
        if admin_users:
            if not isinstance(admin_users, list):
                admin_users = [admin_users]
            if not all(isinstance(admin_user, str) and admin_user.strip() for admin_user in admin_users):
                raise ConfigError(f"IDP: {provider_name}: Admin users must be non-empty strings")
        if operator_users:
            if not isinstance(operator_users, list):
                operator_users = [operator_users]
            if not all(isinstance(operator_user, str) and operator_user.strip() for operator_user in operator_users):
                raise ConfigError(f"IDP: {provider_name}: Operator users must be non-empty strings")

        # Verify attributes
        admin_attributes = attributes.get('admin', {})
        verify_attributes(admin_attributes)
        operator_attributes = attributes.get('operator', {})
        verify_attributes(operator_attributes)

def generate(config_dict):
    try:
        if not os.path.exists(CONFIG_DIR):
            os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(f"{CONFIG_DIR}/{CONFIG_FILE}", 'w') as conf_file:
            json.dump(config_dict, conf_file, indent=4)
    except Exception:
        raise ConfigError("Could not generate config file")

def apply(config_dict):
    def toggle_pam_profile(profile: str, enable: bool) -> bool:
        """
        Enable / Disable a pam profile

        Args:
            profile (str): Name of the profile to toggle
            enable (bool): Should the pam profile be enabled or disabled

        Returns:
            True if the profile was successfully toggled, False otherwise
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
        """
        Enable / Disable a systemd service

        Args:
            service (str): Name of the service to toggle
            enable (bool): Should the service be enabled or disabled

        Returns:
            True if the service was successfully toggled, False otherwise
        """
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

    idp = config_dict.get('idp', {})
    providers = idp.get('provider', {})
    enable = True if idp and providers else False

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
