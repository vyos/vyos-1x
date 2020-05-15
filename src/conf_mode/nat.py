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

from copy import deepcopy
from sys import exit
from netifaces import interfaces

from vyos.config import Config
from vyos.template import render
from vyos.util import call, cmd
from vyos.validate import is_addr_assigned
from vyos import ConfigError

default_config_data = {
    'deleted': False,
    'destination': [],
    'helper_functions': None,
    'pre_ct_helper': '',
    'pre_ct_conntrack': '',
    'out_ct_helper': '',
    'out_ct_conntrack': '',
    'source': []
}

iptables_nat_config = '/tmp/vyos-nat-rules.nft'

def _check_kmod():
    """ load required Kernel modules """
    modules = ['nft_nat', 'nft_chain_nat_ipv4']
    for module in modules:
        if not os.path.exists(f'/sys/module/{module}'):
            if call(f'modprobe {module}') != 0:
                raise ConfigError(f'Loading Kernel module {module} failed')


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


def verify_rule(rule, err_msg):
    if rule['translation_port'] or rule['dest_port']:
        if rule['protocol'] not in ['tcp', 'udp', 'tcp_udp']:
            proto = rule['protocol']
            raise ConfigError(f'{err_msg} ports can only be specified when protocol is "tcp", "udp" or "tcp_udp" (currently "{proto}")')

        if '/' in rule['translation_address']:
            raise ConfigError(f'{err_msg}\n' \
                             'Cannot use ports with an IPv4net type translation address as it\n' \
                             'statically maps a whole network of addresses onto another\n' \
                             'network of addresses')


def parse_source_destination(conf, source_dest):
    """ Common wrapper to read in both NAT source and destination CLI """
    tmp = []
    base_level = ['nat', source_dest]
    conf.set_level(base_level)
    for number in conf.list_nodes(['rule']):
        rule = {
            'description': '',
            'dest_address': '',
            'dest_port': '',
            'disable': False,
            'exclude': False,
            'interface_in': '',
            'interface_out': '',
            'log': False,
            'protocol': '',
            'number': number,
            'source_address': '',
            'source_port': '',
            'translation_address': '',
            'translation_port': ''
        }
        conf.set_level(base_level + ['rule', number])

        if conf.exists(['description']):
            rule['description'] = conf.return_value(['description'])

        if conf.exists(['destination', 'address']):
            rule['dest_address'] = conf.return_value(['destination', 'address'])

        if conf.exists(['destination', 'port']):
            rule['dest_port'] = conf.return_value(['destination', 'port'])

        if conf.exists(['disable']):
            rule['disable'] = True

        if conf.exists(['exclude']):
            rule['exclude'] = True

        if conf.exists(['inbound-interface']):
            rule['interface_in'] = conf.return_value(['inbound-interface'])

        if conf.exists(['outbound-interface']):
            rule['interface_out'] = conf.return_value(['outbound-interface'])

        if conf.exists(['log']):
            rule['log'] = True

        if conf.exists(['protocol']):
            rule['protocol'] = conf.return_value(['protocol'])

        if conf.exists(['source', 'address']):
            rule['source_address'] = conf.return_value(['source', 'address'])

        if conf.exists(['source', 'port']):
            rule['source_port'] = conf.return_value(['source', 'port'])

        if conf.exists(['translation', 'address']):
            rule['translation_address'] = conf.return_value(['translation', 'address'])

        if conf.exists(['translation', 'port']):
            rule['translation_port'] = conf.return_value(['translation', 'port'])

        tmp.append(rule)

    return tmp

def get_config():
    nat = deepcopy(default_config_data)
    conf = Config()

    # read in current nftable (once) for further processing
    tmp = cmd('nft -j list table raw')
    nftable_json = json.loads(tmp)

    # condense the full JSON table into a list with only relevand informations
    pattern = 'nftables[?rule].rule[?expr[].jump].{chain: chain, handle: handle, target: expr[].jump.target | [0]}'
    condensed_json = jmespath.search(pattern, nftable_json)

    if not conf.exists(['nat']):
        nat['helper_functions'] = 'remove'

        # Retrieve current table handler positions
        nat['pre_ct_ignore'] = get_handler(condensed_json, 'PREROUTING', 'VYATTA_CT_HELPER')
        nat['pre_ct_conntrack'] = get_handler(condensed_json, 'PREROUTING', 'NAT_CONNTRACK')
        nat['out_ct_ignore'] = get_handler(condensed_json, 'OUTPUT', 'VYATTA_CT_HELPER')
        nat['out_ct_conntrack'] = get_handler(condensed_json, 'OUTPUT', 'NAT_CONNTRACK')

        nat['deleted'] = True

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

    # set config level for parsing in NAT configuration
    conf.set_level(['nat'])

    # use a common wrapper function to read in the source / destination
    # tree from the config - thus we do not need to replicate almost the
    # same code :-)
    for tgt in ['source', 'destination']:
        nat[tgt] = parse_source_destination(conf, tgt)

    return nat

def verify(nat):
    if nat['deleted']:
        # no need to verify the CLI as NAT is going to be deactivated
        return None

    if nat['helper_functions']:
        if not (nat['pre_ct_ignore'] or nat['pre_ct_conntrack'] or nat['out_ct_ignore'] or nat['out_ct_conntrack']):
            raise Exception('could not determine nftable ruleset handlers')

    for rule in nat['source']:
        interface = rule['interface_out']
        err_msg = f"Source NAT configuration error in rule {rule['number']}:"

        if interface and interface not in interfaces():
            print(f'NAT configuration warning: interface {interface} does not exist on this system')

        if not rule['interface_out']:
            raise ConfigError(f'{err_msg} outbound-interface not specified')

        if not rule['translation_address']:
            raise ConfigError(f'{err_msg} translation address not specified')
        else:
            addr = rule['translation_address']
            if addr != 'masquerade' and not is_addr_assigned(addr):
                printf(f'Warning: IP address {addr} does not exist on the system!')

        # common rule verification
        verify_rule(rule, err_msg)

    for rule in nat['destination']:
        interface = rule['interface_in']
        err_msg = f"Destination NAT configuration error in rule {rule['number']}:"

        if interface and interface not in interfaces():
            print(f'NAT configuration warning: interface {interface} does not exist on this system')

        if not rule['interface_in']:
            raise ConfigError(f'{err_msg} inbound-interface not specified')

        # common rule verification
        verify_rule(rule, err_msg)

    return None

def generate(nat):
    render(iptables_nat_config, 'firewall/nftables-nat.tmpl', nat, trim_blocks=True, permission=0o755)

    return None

def apply(nat):
    cmd(f'{iptables_nat_config}')
    if os.path.isfile(iptables_nat_config):
        os.unlink(iptables_nat_config)

    return None

if __name__ == '__main__':
    try:
        _check_kmod()
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
