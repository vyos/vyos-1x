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
from vyos.template import is_ip_network
from vyos.utils.kernel import check_kmod
from vyos.utils.dict import dict_search
from vyos.utils.dict import dict_search_args
from vyos.utils.file import write_file
from vyos.utils.process import cmd
from vyos.utils.process import run
from vyos.utils.process import call
from vyos.utils.network import is_addr_assigned
from vyos.utils.network import interface_exists
from vyos.firewall import fqdn_config_parse
from vyos import ConfigError

from vyos import airbag
airbag.enable()

k_mod = ['nft_nat', 'nft_chain_nat']

nftables_nat_config = '/run/nftables_nat.conf'
nftables_static_nat_conf = '/run/nftables_static-nat-rules.nft'
domain_resolver_usage = '/run/use-vyos-domain-resolver-nat'
domain_resolver_usage_firewall = '/run/use-vyos-domain-resolver-firewall'

valid_groups = [
    'address_group',
    'domain_group',
    'network_group',
    'port_group'
]

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['nat']
    nat = conf.get_config_dict(base, key_mangling=('-', '_'),
                               get_first_key=True,
                               with_recursive_defaults=True)

    set_dependents('conntrack', conf)

    if not conf.exists(base):
        nat['deleted'] = ''
        return nat

    nat['firewall_group'] = conf.get_config_dict(['firewall', 'group'], key_mangling=('-', '_'), get_first_key=True,
                                    no_tag_node_value_mangle=True)

    # Remove dynamic firewall groups if present:
    if 'dynamic_group' in nat['firewall_group']:
        del nat['firewall_group']['dynamic_group']

    fqdn_config_parse(nat, 'nat')

    return nat

def verify_rule(config, err_msg, groups_dict):
    """ Common verify steps used for both source and destination NAT """

    if (dict_search('translation.port', config) != None or
        dict_search('translation.redirect.port', config) != None or
        dict_search('destination.port', config) != None or
        dict_search('source.port', config)):

        if config['protocol'] not in ['tcp', 'udp', 'tcp_udp']:
            raise ConfigError(f'{err_msg} ports can only be specified when '\
                              'protocol is either tcp, udp or tcp_udp!')

    for side in ['destination', 'source']:
        if side in config:
            side_conf = config[side]

            if len({'address', 'fqdn'} & set(side_conf)) > 1:
                raise ConfigError('Only one of address, fqdn or geoip can be specified')

            if 'group' in side_conf:
                if len({'address_group', 'network_group', 'domain_group'} & set(side_conf['group'])) > 1:
                    raise ConfigError('Only one address-group, network-group or domain-group can be specified')

                for group in valid_groups:
                    if group in side_conf['group']:
                        group_name = side_conf['group'][group]
                        error_group = group.replace("_", "-")

                        if group in ['address_group', 'network_group', 'domain_group']:
                            types = [t for t in ['address', 'fqdn'] if t in side_conf]
                            if types:
                                raise ConfigError(f'{error_group} and {types[0]} cannot both be defined')

                        if group_name and group_name[0] == '!':
                            group_name = group_name[1:]

                        group_obj = dict_search_args(groups_dict, group, group_name)

                        if group_obj is None:
                            raise ConfigError(f'Invalid {error_group} "{group_name}" on nat rule')

                        if not group_obj:
                            Warning(f'{error_group} "{group_name}" has no members!')

            if dict_search_args(side_conf, 'group', 'port_group'):
                if 'protocol' not in config:
                    raise ConfigError('Protocol must be defined if specifying a port-group')

                if config['protocol'] not in ['tcp', 'udp', 'tcp_udp']:
                    raise ConfigError('Protocol must be tcp, udp, or tcp_udp when specifying a port-group')

    if 'load_balance' in config:
        for item in ['source-port', 'destination-port']:
            if item in config['load_balance']['hash'] and config['protocol'] not in ['tcp', 'udp']:
                raise ConfigError('Protocol must be tcp or udp when specifying hash ports')
        count = 0
        if 'backend' in config['load_balance']:
            for member in config['load_balance']['backend']:
                weight = config['load_balance']['backend'][member]['weight']
                count = count +  int(weight)
            if count != 100:
                Warning(f'Sum of weight for nat load balance rule is not 100. You may get unexpected behaviour')

def verify(nat):
    if not nat or 'deleted' in nat:
        # no need to verify the CLI as NAT is going to be deactivated
        return None

    if dict_search('source.rule', nat):
        for rule, config in dict_search('source.rule', nat).items():
            err_msg = f'Source NAT configuration error in rule {rule}:'

            if 'outbound_interface' in config:
                if 'name' in config['outbound_interface'] and 'group' in config['outbound_interface']:
                    raise ConfigError(f'{err_msg} cannot specify both interface group and interface name for nat source rule "{rule}"')
                elif 'name' in config['outbound_interface']:
                    interface_name = config['outbound_interface']['name']
                    if interface_name not in 'any':
                        if interface_name.startswith('!'):
                            interface_name = interface_name[1:]
                        if not interface_exists(interface_name):
                            Warning(f'Interface "{interface_name}" for source NAT rule "{rule}" does not exist!')
                else:
                    group_name = config['outbound_interface']['group']
                    if group_name[0] == '!':
                        group_name = group_name[1:]
                    group_obj = dict_search_args(nat['firewall_group'], 'interface_group', group_name)
                    if group_obj is None:
                        raise ConfigError(f'Invalid interface group "{group_name}" on source nat rule')
                    if not group_obj:
                        Warning(f'interface-group "{group_name}" has no members!')

            if not dict_search('translation.address', config) and not dict_search('translation.port', config):
                if 'exclude' not in config and 'backend' not in config['load_balance']:
                    raise ConfigError(f'{err_msg} translation requires address and/or port')

            addr = dict_search('translation.address', config)
            if addr != None and addr != 'masquerade' and not is_ip_network(addr):
                for ip in addr.split('-'):
                    if not is_addr_assigned(ip):
                        Warning(f'IP address {ip} does not exist on the system!')

            # common rule verification
            verify_rule(config, err_msg, nat['firewall_group'])

    if dict_search('destination.rule', nat):
        for rule, config in dict_search('destination.rule', nat).items():
            err_msg = f'Destination NAT configuration error in rule {rule}:'

            if 'inbound_interface' in config:
                if 'name' in config['inbound_interface'] and 'group' in config['inbound_interface']:
                    raise ConfigError(f'{err_msg} cannot specify both interface group and interface name for destination nat rule "{rule}"')
                elif 'name' in config['inbound_interface']:
                    interface_name = config['inbound_interface']['name']
                    if interface_name not in 'any':
                        if interface_name.startswith('!'):
                            interface_name = interface_name[1:]
                        if not interface_exists(interface_name):
                            Warning(f'Interface "{interface_name}" for destination NAT rule "{rule}" does not exist!')
                else:
                    group_name = config['inbound_interface']['group']
                    if group_name[0] == '!':
                        group_name = group_name[1:]
                    group_obj = dict_search_args(nat['firewall_group'], 'interface_group', group_name)
                    if group_obj is None:
                        raise ConfigError(f'Invalid interface group "{group_name}" on destination nat rule')
                    if not group_obj:
                        Warning(f'interface-group "{group_name}" has no members!')

            if not dict_search('translation.address', config) and not dict_search('translation.port', config) and 'redirect' not in config['translation']:
                if 'exclude' not in config and 'backend' not in config['load_balance']:
                    raise ConfigError(f'{err_msg} translation requires address and/or port')

            # common rule verification
            verify_rule(config, err_msg, nat['firewall_group'])

    if dict_search('static.rule', nat):
        for rule, config in dict_search('static.rule', nat).items():
            err_msg = f'Static NAT configuration error in rule {rule}:'

            if 'inbound_interface' not in config:
                raise ConfigError(f'{err_msg} inbound-interface not specified')

            # common rule verification
            verify_rule(config, err_msg, nat['firewall_group'])

    return None

def generate(nat):
    if not os.path.exists(nftables_nat_config):
        nat['first_install'] = True

    render(nftables_nat_config, 'firewall/nftables-nat.j2', nat)
    render(nftables_static_nat_conf, 'firewall/nftables-static-nat.j2', nat)

    # dry-run newly generated configuration
    tmp = run(f'nft --check --file {nftables_nat_config}')
    if tmp > 0:
        raise ConfigError('Configuration file errors encountered!')

    tmp = run(f'nft --check --file {nftables_static_nat_conf}')
    if tmp > 0:
        raise ConfigError('Configuration file errors encountered!')

    return None

def apply(nat):
    check_kmod(k_mod)

    cmd(f'nft --file {nftables_nat_config}')
    cmd(f'nft --file {nftables_static_nat_conf}')

    if not nat or 'deleted' in nat:
        os.unlink(nftables_nat_config)
        os.unlink(nftables_static_nat_conf)

    call_dependents()

    # DOMAIN RESOLVER
    if nat and 'deleted' not in nat:
        domain_action = 'restart'
        if nat['ip_fqdn'].items():
            text = f'# Automatically generated by nat.py\nThis file indicates that vyos-domain-resolver service is used by nat.\n'
            write_file(domain_resolver_usage, text)
        elif os.path.exists(domain_resolver_usage):
            os.unlink(domain_resolver_usage)
            if not os.path.exists(domain_resolver_usage_firewall):
                # Firewall not using domain resolver
                domain_action = 'stop'
        call(f'systemctl {domain_action} vyos-domain-resolver.service')

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
