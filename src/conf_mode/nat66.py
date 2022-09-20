#!/usr/bin/env python3
#
# Copyright (C) 2020-2021 VyOS maintainers and contributors
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

from vyos.base import Warning
from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.template import render
from vyos.util import cmd
from vyos.util import check_kmod
from vyos.util import dict_search
from vyos.template import is_ipv6
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

k_mod = ['nft_nat', 'nft_chain_nat']

nftables_nat66_config = '/run/nftables_nat66.nft'
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
            if 'rule' in nat[direction]:
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
        nat['pre_ct_ignore'] = get_handler(condensed_json, 'PREROUTING', 'VYOS_CT_HELPER')
        nat['pre_ct_conntrack'] = get_handler(condensed_json, 'PREROUTING', 'NAT_CONNTRACK')
        nat['out_ct_ignore'] = get_handler(condensed_json, 'OUTPUT', 'VYOS_CT_HELPER')
        nat['out_ct_conntrack'] = get_handler(condensed_json, 'OUTPUT', 'NAT_CONNTRACK')
        nat['deleted'] = ''
        return nat

    # check if NAT66 connection tracking helpers need to be set up - this has to
    # be done only once
    if not get_handler(condensed_json, 'PREROUTING', 'NAT_CONNTRACK'):
        nat['helper_functions'] = 'add'

        # Retrieve current table handler positions
        nat['pre_ct_ignore'] = get_handler(condensed_json, 'PREROUTING', 'VYOS_CT_IGNORE')
        nat['pre_ct_conntrack'] = get_handler(condensed_json, 'PREROUTING', 'VYOS_CT_PREROUTING_HOOK')
        nat['out_ct_ignore'] = get_handler(condensed_json, 'OUTPUT', 'VYOS_CT_IGNORE')
        nat['out_ct_conntrack'] = get_handler(condensed_json, 'OUTPUT', 'VYOS_CT_OUTPUT_HOOK')
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
                raise ConfigError(f'{err_msg} outbound-interface not specified')

            if config['outbound_interface'] not in interfaces():
                raise ConfigError(f'rule "{rule}" interface "{config["outbound_interface"]}" does not exist on this system')

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

            if 'inbound_interface' not in config:
                raise ConfigError(f'{err_msg}\n' \
                                  'inbound-interface not specified')
            else:
                if config['inbound_interface'] not in 'any' and config['inbound_interface'] not in interfaces():
                    Warning(f'rule "{rule}" interface "{config["inbound_interface"]}" does not exist on this system')

    return None

def generate(nat):
    if not os.path.exists(nftables_nat66_config):
        nat['first_install'] = True

    render(nftables_nat66_config, 'firewall/nftables-nat66.j2', nat, permission=0o755)
    render(ndppd_config, 'ndppd/ndppd.conf.j2', nat, permission=0o755)
    return None

def apply(nat):
    if not nat:
        return None

    cmd(f'nft -f {nftables_nat66_config}')

    if 'deleted' in nat or not dict_search('source.rule', nat):
        cmd('systemctl stop ndppd')
        if os.path.isfile(ndppd_config):
            os.unlink(ndppd_config)
    else:
        cmd('systemctl restart ndppd')

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
