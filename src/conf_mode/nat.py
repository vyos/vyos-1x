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

from distutils.version import LooseVersion
from platform import release as kernel_version
from sys import exit
from netifaces import interfaces

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.template import render
from vyos.util import cmd
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

iptables_nat_config = '/tmp/vyos-nat-rules.nft'

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

        if '/' in (dict_search('translation.address', config) or []):
            raise ConfigError(f'{err_msg}\n' \
                             'Cannot use ports with an IPv4net type translation address as it\n' \
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
    for direction in ['source', 'destination']:
        if direction in nat:
            default_values = defaults(base + [direction, 'rule'])
            for rule in nat[direction]['rule']:
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
        nat['pre_ct_ignore'] = get_handler(condensed_json, 'PREROUTING', 'VYATTA_CT_HELPER')
        nat['pre_ct_conntrack'] = get_handler(condensed_json, 'PREROUTING', 'NAT_CONNTRACK')
        nat['out_ct_ignore'] = get_handler(condensed_json, 'OUTPUT', 'VYATTA_CT_HELPER')
        nat['out_ct_conntrack'] = get_handler(condensed_json, 'OUTPUT', 'NAT_CONNTRACK')
        nat['deleted'] = ''
        return nat

    # check if NAT connection tracking helpers need to be set up - this has to
    # be done only once
    if not get_handler(condensed_json, 'PREROUTING', 'NAT_CONNTRACK'):
        nat['helper_functions'] = 'add'

        # Retrieve current table handler positions
        nat['pre_ct_ignore'] = get_handler(condensed_json, 'PREROUTING', 'VYATTA_CT_IGNORE')
        nat['pre_ct_conntrack'] = get_handler(condensed_json, 'PREROUTING', 'VYATTA_CT_PREROUTING_HOOK')
        nat['out_ct_ignore'] = get_handler(condensed_json, 'OUTPUT', 'VYATTA_CT_IGNORE')
        nat['out_ct_conntrack'] = get_handler(condensed_json, 'OUTPUT', 'VYATTA_CT_OUTPUT_HOOK')

    return nat

def verify(nat):
    if not nat or 'deleted' in nat:
        # no need to verify the CLI as NAT is going to be deactivated
        return None

    if nat['helper_functions']:
        if not (nat['pre_ct_ignore'] or nat['pre_ct_conntrack'] or nat['out_ct_ignore'] or nat['out_ct_conntrack']):
            raise Exception('could not determine nftable ruleset handlers')

    if dict_search('source.rule', nat):
        for rule, config in dict_search('source.rule', nat).items():
            err_msg = f'Source NAT configuration error in rule {rule}:'
            if 'outbound_interface' not in config:
                raise ConfigError(f'{err_msg}\n' \
                                  'outbound-interface not specified')
            else:
                if config['outbound_interface'] not in 'any' and config['outbound_interface'] not in interfaces():
                    print(f'WARNING: rule "{rule}" interface "{config["outbound_interface"]}" does not exist on this system')


            addr = dict_search('translation.address', config)
            if addr != None:
                if addr != 'masquerade':
                    for ip in addr.split('-'):
                        if not is_addr_assigned(ip):
                            print(f'WARNING: IP address {ip} does not exist on the system!')
            elif 'exclude' not in config:
                raise ConfigError(f'{err_msg}\n' \
                                  'translation address not specified')

            # common rule verification
            verify_rule(config, err_msg)


    if dict_search('destination.rule', nat):
        for rule, config in dict_search('destination.rule', nat).items():
            err_msg = f'Destination NAT configuration error in rule {rule}:'

            if 'inbound_interface' not in config:
                raise ConfigError(f'{err_msg}\n' \
                                  'inbound-interface not specified')
            else:
                if config['inbound_interface'] not in 'any' and config['inbound_interface'] not in interfaces():
                    print(f'WARNING: rule "{rule}" interface "{config["inbound_interface"]}" does not exist on this system')


            if dict_search('translation.address', config) == None and 'exclude' not in config:
                raise ConfigError(f'{err_msg}\n' \
                                  'translation address not specified')

            # common rule verification
            verify_rule(config, err_msg)

    return None

def generate(nat):
    render(iptables_nat_config, 'firewall/nftables-nat.tmpl', nat,
           permission=0o755)
    return None

def apply(nat):
    cmd(f'{iptables_nat_config}')
    if os.path.isfile(iptables_nat_config):
        os.unlink(iptables_nat_config)

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
