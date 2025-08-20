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

from sys import exit

from vyos.base import Warning
from vyos.config import Config
from vyos.configverify import verify_interface_exists
from vyos.configverify import has_frr_protocol_in_dict
from vyos.utils.process import is_systemd_service_running
from vyos.frrender import FRRender
from vyos.frrender import get_frrender_dict
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    return get_frrender_dict(conf)

def verify(config_dict):
    if not has_frr_protocol_in_dict(config_dict, 'openfabric'):
        return None

    openfabric = config_dict['openfabric']
    if 'deleted' in openfabric:
        return None

    if 'net' not in openfabric:
        raise ConfigError('Network entity is mandatory!')

    # last byte in OpenFabric area address must be 0
    tmp = openfabric['net'].split('.')
    if int(tmp[-1]) != 0:
        raise ConfigError('Last byte of OpenFabric network entity title must always be 0!')

    if 'domain' not in openfabric:
        raise ConfigError('OpenFabric domain name is mandatory!')

    interfaces_used = []

    for domain, domain_config in openfabric['domain'].items():
        # If interface not set
        if 'interface' not in domain_config:
            raise ConfigError(f'Interface used for routing updates in OpenFabric "{domain}" is mandatory!')

        for iface, iface_config in domain_config['interface'].items():
            verify_interface_exists(openfabric, iface)

            # interface can be activated only on one OpenFabric instance
            if iface in interfaces_used:
                raise ConfigError(f'Interface {iface} is already used in different OpenFabric instance!')

            if 'address_family' not in iface_config or len(iface_config['address_family']) < 1:
                raise ConfigError(f'Need to specify address family for the interface "{iface}"!')

            # If md5 and plaintext-password set at the same time
            if 'password' in iface_config:
                if {'md5', 'plaintext_password'} <= set(iface_config['password']):
                    raise ConfigError(f'Can use either md5 or plaintext-password for password for the interface!')

            if iface == 'lo' and 'passive' not in iface_config:
                Warning('For loopback interface passive mode is implied!')

            interfaces_used.append(iface)

        # If md5 and plaintext-password set at the same time
        password = 'domain_password'
        if password in domain_config:
            if {'md5', 'plaintext_password'} <= set(domain_config[password]):
                raise ConfigError(f'Can use either md5 or plaintext-password for domain-password!')

    return None

def generate(config_dict):
    if config_dict and not is_systemd_service_running('vyos-configd.service'):
        FRRender().generate(config_dict)
    return None

def apply(config_dict):
    if config_dict and not is_systemd_service_running('vyos-configd.service'):
        FRRender().apply()
    return None

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
