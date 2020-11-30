#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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

import jmespath
import json
import os

from sys import exit
from netifaces import interfaces

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.template import render
from vyos.util import cmd
from vyos.util import check_kmod
from vyos.util import dict_search
from vyos.template import is_ipv6
from vyos.xml import defaults
from vyos import ConfigError
import platform
from vyos import airbag
airbag.enable()

k_mod = ['nft_nat', 'nft_chain_nat']

iptables_nat_config = '/tmp/vyos-nat66-rules.nft'
ndppd_config = '/run/ndppd/ndppd.conf'

def get_handler(json, chain, target):
    """ Get nftable rule handler number of given chain/target combination.
    Handler is required when adding NAT66/Conntrack helper targets """
    for x in json:
        if x['chain'] != chain:
            continue
        if x['target'] != target:
            continue
        return x['handle']

    return None

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    
    base = ['nat66']
    nat = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)

    # T2665: we must add the tagNode defaults individually until this is
    # moved to the base class
    for direction in ['source', 'destination']:
        if direction in nat:
            default_values = defaults(base + [direction, 'rule'])
            for rule in nat[direction]['rule']:
                nat[direction]['rule'][rule] = dict_merge(default_values,
                    nat[direction]['rule'][rule])

    # read in current nftable (once) for further processing
    tmp = cmd('nft -j list table ip6 raw')
    nftable_json = json.loads(tmp)

    # condense the full JSON table into a list with only relevand informations
    pattern = 'nftables[?rule].rule[?expr[].jump].{chain: chain, handle: handle, target: expr[].jump.target | [0]}'
    condensed_json = jmespath.search(pattern, nftable_json)

    if not conf.exists(base):
        nat['helper_functions'] = 'remove'

        nat['pre_ct_conntrack'] = get_handler(condensed_json, 'PREROUTING', 'NAT_CONNTRACK')
        nat['out_ct_conntrack'] = get_handler(condensed_json, 'OUTPUT','NAT_CONNTRACK')

        nat['deleted'] = ''

        return nat

    # check if NAT66 connection tracking helpers need to be set up - this has to
    # be done only once
    if not get_handler(condensed_json, 'PREROUTING', 'NAT_CONNTRACK'):
        nat['helper_functions'] = 'add'

        # Retrieve current table handler positions
        nat['pre_ct_conntrack'] = get_handler(condensed_json, 'PREROUTING', 'VYATTA_CT_PREROUTING_HOOK')
        nat['out_ct_conntrack'] = get_handler(condensed_json, 'OUTPUT','VYATTA_CT_OUTPUT_HOOK')
    else:
        nat['helper_functions'] = 'has'

    return nat

def verify(nat):
    if not nat or 'deleted' in nat:
        # no need to verify the CLI as NAT66 is going to be deactivated
        return None

    if 'helper_functions' in nat and nat['helper_functions'] != 'has':
        if not (nat['pre_ct_conntrack'] or nat['out_ct_conntrack']):
            raise Exception('could not determine nftable ruleset handlers')
    
    if dict_search('source.rule', nat):
        for rule, config in dict_search('source.rule', nat).items():
            err_msg = f'Source NAT66 configuration error in rule {rule}:'
            if 'outbound_interface' not in config:
                raise ConfigError(f'{err_msg}\n' \
                                  'outbound-interface not specified')
            else:
                if config['outbound_interface'] not in 'any' and config['outbound_interface'] not in interfaces():
                    print(f'WARNING: rule "{rule}" interface "{config["outbound_interface"]}" does not exist on this system')


            prefix = dict_search('translation.prefix', config)
            if prefix != None:
                if not is_ipv6(prefix):
                    raise ConfigError(f'Warning: IPv6 prefix {prefix} is not a valid address prefix')
            
            prefix = dict_search('source.prefix', config)
            if prefix != None:
                if not is_ipv6(prefix):
                    raise ConfigError(f'{err_msg} source-prefix not specified')


    if dict_search('destination.rule', nat):
        for rule, config in dict_search('destination.rule', nat).items():
            err_msg = f'Destination NAT66 configuration error in rule {rule}:'

            if 'inbound_interface' not in config:
                raise ConfigError(f'{err_msg}\n' \
                                  'inbound-interface not specified')
            else:
                if config['inbound_interface'] not in 'any' and config['inbound_interface'] not in interfaces():
                    print(f'WARNING: rule "{rule}" interface "{config["inbound_interface"]}" does not exist on this system')

    return None

def nat66_conf_to_ndp_proxy_conf(nat):
    ndpproxy = {
        'interface': {}
    }
    if  not nat or 'deleted' in nat:
        # no need to verify the CLI as NAT66 is going to be deactivated
        return None
    # Detect and convert the default configuration of the configured interface
    source_rule = dict_search('source.rule', nat)
    if source_rule:
        for rule,config in source_rule.items():
            interface_ndp = {
                'router': 'yes',
                'timeout': 500,
                'ttl': 30000,
                'prefix': {}
            }
            if config['outbound_interface'] not in ndpproxy['interface']:
                ndpproxy['interface'].update({config['outbound_interface']: interface_ndp})
        for rule,config in source_rule.items():
            if config['outbound_interface'] in ndpproxy['interface']:
                prefix = dict_search('translation.prefix', config)
                if prefix:
                    nat66_prefix = config['translation']['prefix']
                    if nat66_prefix not in ndpproxy['interface'][config['outbound_interface']]['prefix']:
                        ndpproxy['interface'][config['outbound_interface']]['prefix'].update({nat66_prefix: {'mode':'auto'}})
    
    # Detect and convert the default configuration of the configured interface
    destination_rule = dict_search('destination.rule', nat)
    if destination_rule:
        for rule,config in destination_rule.items():
            interface_ndp = {
                'router': 'yes',
                'timeout': 500,
                'ttl': 30000,
                'prefix': {}
            }
            if config['inbound_interface'] not in ndpproxy['interface']:
                ndpproxy['interface'].update({config['inbound_interface']: interface_ndp})
        for rule,config in destination_rule.items():
            if rule['interface'] in ndpproxy['interface']:
                prefix = dict_search('destination.address', config)
                if prefix:
                    nat66_address = config['destination']['address']
                    if nat66_prefix not in ndpproxy['interface'][config['inbound_interface']]['prefix']:
                        ndpproxy['interface'][config['inbound_interface']]['prefix'].update({nat66_prefix: {'mode':'auto'}})
    
    return ndpproxy

def generate(nat,ndp_proxy):
    render(iptables_nat_config, 'firewall/nftables-nat66.tmpl', nat, permission=0o755)
    if ndp_proxy == None:
        return None
    render(ndppd_config, 'proxy-ndp/ndppd.conf.tmpl', ndp_proxy, permission=0o755)
    return None

def apply(nat):
    cmd(f'{iptables_nat_config}')
    cmd('systemctl restart ndppd')
    if os.path.isfile(iptables_nat_config):
        os.unlink(iptables_nat_config)

    return None

if __name__ == '__main__':
    try:
        check_kmod(k_mod)
        c = get_config()
        verify(c)
        ndp_proxy = nat66_conf_to_ndp_proxy_conf(c)
        generate(c,ndp_proxy)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
