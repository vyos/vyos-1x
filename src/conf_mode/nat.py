#!/usr/bin/env python3
#
# Copyright (C) 2020-2022 VyOS maintainers and contributors
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

from distutils.version import LooseVersion
from platform import release as kernel_version
from sys import exit
from netifaces import interfaces

from vyos.base import Warning
from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.template import render
from vyos.template import is_ip_network
from vyos.util import cmd
from vyos.util import run
from vyos.util import check_kmod
from vyos.util import dict_search
from vyos.validate import is_addr_assigned
from vyos.xml import defaults
from vyos import ConfigError

from vyos import airbag
airbag.enable()

if LooseVersion(kernel_version()) > LooseVersion('5.1'):
    k_mod = ['nft_nat', 'nft_chain_nat']
else:
    k_mod = ['nft_nat', 'nft_chain_nat_ipv4']

nftables_nat_config = '/run/nftables_nat.conf'
nftables_static_nat_conf = '/run/nftables_static-nat-rules.nft'

def get_handler(json, chain, target):
    """ Get nftable rule handler number of given chain/target combination.
    Handler is required when adding NAT/Conntrack helper targets """
    for x in json:
        if x['chain'] != chain:
            continue
        if x['target'] != target:
            continue
        return x['handle']

    return None


def verify_rule(config, err_msg):
    """ Common verify steps used for both source and destination NAT """

    if (dict_search('translation.port', config) != None or
        dict_search('destination.port', config) != None or
        dict_search('source.port', config)):

        if config['protocol'] not in ['tcp', 'udp', 'tcp_udp']:
            raise ConfigError(f'{err_msg}\n' \
                              'ports can only be specified when protocol is '\
                              'either tcp, udp or tcp_udp!')

        if is_ip_network(dict_search('translation.address', config)):
            raise ConfigError(f'{err_msg}\n' \
                             'Cannot use ports with an IPv4 network as translation address as it\n' \
                             'statically maps a whole network of addresses onto another\n' \
                             'network of addresses')

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['nat']
    nat = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)

    # T2665: we must add the tagNode defaults individually until this is
    # moved to the base class
    for direction in ['source', 'destination', 'static']:
        if direction in nat:
            default_values = defaults(base + [direction, 'rule'])
            for rule in dict_search(f'{direction}.rule', nat) or []:
                nat[direction]['rule'][rule] = dict_merge(default_values,
                    nat[direction]['rule'][rule])

    # read in current nftable (once) for further processing
    tmp = cmd('nft -j list table raw')
    nftable_json = json.loads(tmp)

    # condense the full JSON table into a list with only relevand informations
    pattern = 'nftables[?rule].rule[?expr[].jump].{chain: chain, handle: handle, target: expr[].jump.target | [0]}'
    condensed_json = jmespath.search(pattern, nftable_json)

    if not conf.exists(base):
        nat['helper_functions'] = 'remove'

        # Retrieve current table handler positions
        nat['pre_ct_ignore'] = get_handler(condensed_json, 'PREROUTING', 'VYOS_CT_HELPER')
        nat['pre_ct_conntrack'] = get_handler(condensed_json, 'PREROUTING', 'NAT_CONNTRACK')
        nat['out_ct_ignore'] = get_handler(condensed_json, 'OUTPUT', 'VYOS_CT_HELPER')
        nat['out_ct_conntrack'] = get_handler(condensed_json, 'OUTPUT', 'NAT_CONNTRACK')
        nat['deleted'] = ''
        return nat

    # check if NAT connection tracking helpers need to be set up - this has to
    # be done only once
    if not get_handler(condensed_json, 'PREROUTING', 'NAT_CONNTRACK'):
        nat['helper_functions'] = 'add'

        # Retrieve current table handler positions
        nat['pre_ct_ignore'] = get_handler(condensed_json, 'PREROUTING', 'VYOS_CT_IGNORE')
        nat['pre_ct_conntrack'] = get_handler(condensed_json, 'PREROUTING', 'VYOS_CT_PREROUTING_HOOK')
        nat['out_ct_ignore'] = get_handler(condensed_json, 'OUTPUT', 'VYOS_CT_IGNORE')
        nat['out_ct_conntrack'] = get_handler(condensed_json, 'OUTPUT', 'VYOS_CT_OUTPUT_HOOK')

    return nat

def verify(nat):
    if not nat or 'deleted' in nat:
        # no need to verify the CLI as NAT is going to be deactivated
        return None

    if 'helper_functions' in nat:
        if not (nat['pre_ct_ignore'] or nat['pre_ct_conntrack'] or nat['out_ct_ignore'] or nat['out_ct_conntrack']):
            raise Exception('could not determine nftable ruleset handlers')

    if dict_search('source.rule', nat):
        for rule, config in dict_search('source.rule', nat).items():
            err_msg = f'Source NAT configuration error in rule {rule}:'
            if 'outbound_interface' not in config:
                raise ConfigError(f'{err_msg} outbound-interface not specified')

            if config['outbound_interface'] not in 'any' and config['outbound_interface'] not in interfaces():
                Warning(f'rule "{rule}" interface "{config["outbound_interface"]}" does not exist on this system')

            addr = dict_search('translation.address', config)
            if addr != None and addr != 'masquerade' and not is_ip_network(addr):
                for ip in addr.split('-'):
                    if not is_addr_assigned(ip):
                        Warning(f'IP address {ip} does not exist on the system!')

            # common rule verification
            verify_rule(config, err_msg)


    if dict_search('destination.rule', nat):
        for rule, config in dict_search('destination.rule', nat).items():
            err_msg = f'Destination NAT configuration error in rule {rule}:'

            if 'inbound_interface' not in config:
                raise ConfigError(f'{err_msg}\n' \
                                  'inbound-interface not specified')
            elif config['inbound_interface'] not in 'any' and config['inbound_interface'] not in interfaces():
                Warning(f'rule "{rule}" interface "{config["inbound_interface"]}" does not exist on this system')

            # common rule verification
            verify_rule(config, err_msg)

    if dict_search('static.rule', nat):
        for rule, config in dict_search('static.rule', nat).items():
            err_msg = f'Static NAT configuration error in rule {rule}:'

            if 'inbound_interface' not in config:
                raise ConfigError(f'{err_msg}\n' \
                                  'inbound-interface not specified')

            # common rule verification
            verify_rule(config, err_msg)

    return None

def generate(nat):
    if not os.path.exists(nftables_nat_config):
        nat['first_install'] = True

    render(nftables_nat_config, 'firewall/nftables-nat.j2', nat)
    render(nftables_static_nat_conf, 'firewall/nftables-static-nat.j2', nat)

    # dry-run newly generated configuration
    tmp = run(f'nft -c -f {nftables_nat_config}')
    if tmp > 0:
        raise ConfigError('Configuration file errors encountered!')

    tmp = run(f'nft -c -f {nftables_static_nat_conf}')
    if tmp > 0:
        raise ConfigError('Configuration file errors encountered!')

    return None

def apply(nat):
    cmd(f'nft -f {nftables_nat_config}')
    cmd(f'nft -f {nftables_static_nat_conf}')

    return None

if __name__ == '__main__':
    try:
        check_kmod(k_mod)
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
