#!/usr/bin/env python3
#
# Copyright (C) 2024 VyOS maintainers and contributors
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
from vyos.configdict import node_changed
from vyos.configverify import verify_interface_exists
from vyos.template import render_to_string
from vyos import ConfigError
from vyos import frr
from vyos import airbag

airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base_path = ['protocols', 'openfabric']

    openfabric = conf.get_config_dict(base_path, key_mangling=('-', '_'),
                                get_first_key=True,
                                no_tag_node_value_mangle=True)

    # Remove per domain MPLS configuration - get a list of all changed Openfabric domains
    # (removed and added) so that they will be properly rendered for the FRR config.
    openfabric['domains_all'] = list(conf.list_nodes(' '.join(base_path) + f' domain') +
                                         node_changed(conf, base_path + ['domain']))

    # Get a list of all interfaces
    openfabric['interfaces_all'] = []
    for domain in openfabric['domains_all']:
        interfaces_modified = list(node_changed(conf, base_path + ['domain', domain, 'interface']) +
                                  conf.list_nodes(' '.join(base_path) + f' domain {domain} interface'))
        openfabric['interfaces_all'].extend(interfaces_modified)

    if not conf.exists(base_path):
        openfabric.update({'deleted': ''})

    return openfabric

def verify(openfabric):
    # bail out early - looks like removal from running config
    if not openfabric or 'deleted' in openfabric:
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

def generate(openfabric):
    if not openfabric or 'deleted' in openfabric:
        return None

    openfabric['frr_fabricd_config'] = render_to_string('frr/fabricd.frr.j2', openfabric)
    return None

def apply(openfabric):
    openfabric_daemon = 'fabricd'

    # Save original configuration prior to starting any commit actions
    frr_cfg = frr.FRRConfig()

    frr_cfg.load_configuration(openfabric_daemon)
    for domain in openfabric['domains_all']:
        frr_cfg.modify_section(f'^router openfabric {domain}', stop_pattern='^exit', remove_stop_mark=True)

    for interface in openfabric['interfaces_all']:
        frr_cfg.modify_section(f'^interface {interface}', stop_pattern='^exit', remove_stop_mark=True)

    if 'frr_fabricd_config' in openfabric:
        frr_cfg.add_before(frr.default_add_before, openfabric['frr_fabricd_config'])

    frr_cfg.commit_configuration(openfabric_daemon)

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
