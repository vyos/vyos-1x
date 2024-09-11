#!/usr/bin/env python3
#
# Copyright (C) 2020-2024 VyOS maintainers and contributors
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

from sys import exit

from vyos.base import Warning
from vyos.config import Config
from vyos.configdep import set_dependents, call_dependents
from vyos.template import render
from vyos.utils.dict import dict_search
from vyos.utils.kernel import check_kmod
from vyos.utils.network import interface_exists
from vyos.utils.process import cmd
from vyos.utils.process import run
from vyos.template import is_ipv6
from vyos import ConfigError
from vyos import airbag
airbag.enable()

k_mod = ['nft_nat', 'nft_chain_nat']

nftables_nat66_config = '/run/nftables_nat66.nft'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['nat66']
    nat = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)

    set_dependents('conntrack', conf)

    if not conf.exists(base):
        nat['deleted'] = ''
        return nat

    nat['firewall_group'] = conf.get_config_dict(['firewall', 'group'], key_mangling=('-', '_'), get_first_key=True,
                                    no_tag_node_value_mangle=True)

    # Remove dynamic firewall groups if present:
    if 'dynamic_group' in nat['firewall_group']:
        del nat['firewall_group']['dynamic_group']

    return nat

def verify(nat):
    if not nat or 'deleted' in nat:
        # no need to verify the CLI as NAT66 is going to be deactivated
        return None

    if dict_search('source.rule', nat):
        for rule, config in dict_search('source.rule', nat).items():
            err_msg = f'Source NAT66 configuration error in rule {rule}:'

            if 'outbound_interface' in config:
                if 'name' in config['outbound_interface'] and 'group' in config['outbound_interface']:
                    raise ConfigError(f'{err_msg} cannot specify both interface group and interface name for nat source rule "{rule}"')
                elif 'name' in config['outbound_interface']:
                    interface_name = config['outbound_interface']['name']
                    if interface_name not in 'any':
                        if interface_name.startswith('!'):
                            interface_name = interface_name[1:]
                        if not interface_exists(interface_name):
                            Warning(f'Interface "{interface_name}" for source NAT66 rule "{rule}" does not exist!')

            addr = dict_search('translation.address', config)
            if addr != None:
                if addr != 'masquerade' and not is_ipv6(addr):
                    raise ConfigError(f'IPv6 address {addr} is not a valid address')
            else:
                if 'exclude' not in config:
                    raise ConfigError(f'{err_msg} translation address not specified')

            prefix = dict_search('source.prefix', config)
            if prefix != None:
                if not is_ipv6(prefix):
                    raise ConfigError(f'{err_msg} source-prefix not specified')

    if dict_search('destination.rule', nat):
        for rule, config in dict_search('destination.rule', nat).items():
            err_msg = f'Destination NAT66 configuration error in rule {rule}:'

            if 'inbound_interface' in config:
                if 'name' in config['inbound_interface'] and 'group' in config['inbound_interface']:
                    raise ConfigError(f'{err_msg} cannot specify both interface group and interface name for destination nat rule "{rule}"')
                elif 'name' in config['inbound_interface']:
                    interface_name = config['inbound_interface']['name']
                    if interface_name not in 'any':
                        if interface_name.startswith('!'):
                            interface_name = interface_name[1:]
                        if not interface_exists(interface_name):
                            Warning(f'Interface "{interface_name}" for destination NAT66 rule "{rule}" does not exist!')

            if 'destination' in config and 'group' in config['destination']:
                if len({'address_group', 'network_group', 'domain_group'} & set(config['destination']['group'])) > 1:
                    raise ConfigError('Only one address-group, network-group or domain-group can be specified')

    return None

def generate(nat):
    if not os.path.exists(nftables_nat66_config):
        nat['first_install'] = True

    render(nftables_nat66_config, 'firewall/nftables-nat66.j2', nat)

    # dry-run newly generated configuration
    tmp = run(f'nft --check --file {nftables_nat66_config}')
    if tmp > 0:
        raise ConfigError('Configuration file errors encountered!')

    return None

def apply(nat):
    check_kmod(k_mod)

    cmd(f'nft --file {nftables_nat66_config}')

    if not nat or 'deleted' in nat:
        os.unlink(nftables_nat66_config)

    call_dependents()

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
