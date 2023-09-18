#!/usr/bin/env python3
#
# Copyright (C) 2021-2023 VyOS maintainers and contributors
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
import re

from sys import exit

from vyos.config import Config
from vyos.utils.process import process_named_running
from vyos.utils.dict import dict_search
<<<<<<< HEAD
=======
from vyos.utils.dict import dict_search_args
from vyos.utils.dict import dict_search_recursive
>>>>>>> 734d84f69 (conntrack: T5571: Refactor conntrack to be independent conf script from firewall, nat, nat66)
from vyos.utils.process import cmd
from vyos.utils.process import run
from vyos.template import render
from vyos import ConfigError
from vyos import airbag
airbag.enable()

conntrack_config = r'/etc/modprobe.d/vyatta_nf_conntrack.conf'
sysctl_file = r'/run/sysctl/10-vyos-conntrack.conf'
nftables_ct_file = r'/run/nftables-ct.conf'

# Every ALG (Application Layer Gateway) consists of either a Kernel Object
# also called a Kernel Module/Driver or some rules present in iptables
module_map = {
    'ftp' : {
        'ko' : ['nf_nat_ftp', 'nf_conntrack_ftp'],
    },
    'h323' : {
        'ko' : ['nf_nat_h323', 'nf_conntrack_h323'],
    },
    'nfs' : {
        'nftables' : ['ct helper set "rpc_tcp" tcp dport {111} return',
                      'ct helper set "rpc_udp" udp dport {111} return']
    },
    'pptp' : {
        'ko' : ['nf_nat_pptp', 'nf_conntrack_pptp'],
     },
    'sip' : {
        'ko' : ['nf_nat_sip', 'nf_conntrack_sip'],
     },
    'sqlnet' : {
        'nftables' : ['ct helper set "tns_tcp" tcp dport {1521,1525,1536} return']
    },
    'tftp' : {
        'ko' : ['nf_nat_tftp', 'nf_conntrack_tftp'],
     },
}

def resync_conntrackd():
    tmp = run('/usr/libexec/vyos/conf_mode/conntrack_sync.py')
    if tmp > 0:
        print('ERROR: error restarting conntrackd!')

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['system', 'conntrack']

    conntrack = conf.get_config_dict(base, key_mangling=('-', '_'),
                                     get_first_key=True,
                                     with_recursive_defaults=True)

<<<<<<< HEAD
    return conntrack

def verify(conntrack):
    if dict_search('ignore.rule', conntrack) != None:
        for rule, rule_config in conntrack['ignore']['rule'].items():
            if dict_search('destination.port', rule_config) or \
               dict_search('source.port', rule_config):
               if 'protocol' not in rule_config or rule_config['protocol'] not in ['tcp', 'udp']:
                   raise ConfigError(f'Port requires tcp or udp as protocol in rule {rule}')
=======
    conntrack['firewall'] = conf.get_config_dict(['firewall'], key_mangling=('-', '_'),
                                                 get_first_key=True,
                                                 no_tag_node_value_mangle=True)

    conntrack['flowtable_enabled'] = False
    flow_offload = dict_search_args(conntrack['firewall'], 'global_options', 'flow_offload')
    if flow_offload and 'disable' not in flow_offload:
        for offload_type in ('software', 'hardware'):
            if dict_search_args(flow_offload, offload_type, 'interface'):
                conntrack['flowtable_enabled'] = True
                break

    conntrack['ipv4_nat_action'] = 'accept' if conf.exists(['nat']) else 'return'
    conntrack['ipv6_nat_action'] = 'accept' if conf.exists(['nat66']) else 'return'
    conntrack['wlb_action'] = 'accept' if conf.exists(['load-balancing', 'wan']) else 'return'
    conntrack['wlb_local_action'] = conf.exists(['load-balancing', 'wan', 'enable-local-traffic'])

    conntrack['module_map'] = module_map

    return conntrack

def verify(conntrack):
    for inet in ['ipv4', 'ipv6']:
        if dict_search_args(conntrack, 'ignore', inet, 'rule') != None:
            for rule, rule_config in conntrack['ignore'][inet]['rule'].items():
                if dict_search('destination.port', rule_config) or \
                   dict_search('destination.group.port_group', rule_config) or \
                   dict_search('source.port', rule_config) or \
                   dict_search('source.group.port_group', rule_config):
                   if 'protocol' not in rule_config or rule_config['protocol'] not in ['tcp', 'udp']:
                       raise ConfigError(f'Port requires tcp or udp as protocol in rule {rule}')

                tcp_flags = dict_search_args(rule_config, 'tcp', 'flags')
                if tcp_flags:
                    if dict_search_args(rule_config, 'protocol') != 'tcp':
                        raise ConfigError('Protocol must be tcp when specifying tcp flags')

                    not_flags = dict_search_args(rule_config, 'tcp', 'flags', 'not')
                    if not_flags:
                        duplicates = [flag for flag in tcp_flags if flag in not_flags]
                        if duplicates:
                            raise ConfigError(f'Cannot match a tcp flag as set and not set')

                for side in ['destination', 'source']:
                    if side in rule_config:
                        side_conf = rule_config[side]

                        if 'group' in side_conf:
                            if len({'address_group', 'network_group', 'domain_group'} & set(side_conf['group'])) > 1:
                                raise ConfigError('Only one address-group, network-group or domain-group can be specified')

                            for group in valid_groups:
                                if group in side_conf['group']:
                                    group_name = side_conf['group'][group]
                                    error_group = group.replace("_", "-")

                                    if group in ['address_group', 'network_group', 'domain_group']:
                                        if 'address' in side_conf:
                                            raise ConfigError(f'{error_group} and address cannot both be defined')

                                    if group_name and group_name[0] == '!':
                                        group_name = group_name[1:]

                                    if inet == 'ipv6':
                                        group = f'ipv6_{group}'

                                    group_obj = dict_search_args(conntrack['firewall'], 'group', group, group_name)

                                    if group_obj is None:
                                        raise ConfigError(f'Invalid {error_group} "{group_name}" on ignore rule')

                                    if not group_obj:
                                        Warning(f'{error_group} "{group_name}" has no members!')
>>>>>>> 734d84f69 (conntrack: T5571: Refactor conntrack to be independent conf script from firewall, nat, nat66)

    return None

def generate(conntrack):
    if not os.path.exists(nftables_ct_file):
        conntrack['first_install'] = True

    # Determine if conntrack is needed
    conntrack['ipv4_firewall_action'] = 'return'
    conntrack['ipv6_firewall_action'] = 'return'

    if conntrack['flowtable_enabled']:
        conntrack['ipv4_firewall_action'] = 'accept'
        conntrack['ipv6_firewall_action'] = 'accept'
    else:
        for rules, path in dict_search_recursive(conntrack['firewall'], 'rule'):
            if any(('state' in rule_conf or 'connection_status' in rule_conf) for rule_conf in rules.values()):
                if path[0] == 'ipv4':
                    conntrack['ipv4_firewall_action'] = 'accept'
                elif path[0] == 'ipv6':
                    conntrack['ipv6_firewall_action'] = 'accept'

    render(conntrack_config, 'conntrack/vyos_nf_conntrack.conf.j2', conntrack)
    render(sysctl_file, 'conntrack/sysctl.conf.j2', conntrack)
    render(nftables_ct_file, 'conntrack/nftables-ct.j2', conntrack)

    # dry-run newly generated configuration
    tmp = run(f'nft -c -f {nftables_ct_file}')
    if tmp > 0:
        if os.path.exists(nftables_ct_file):
            os.unlink(nftables_ct_file)
        raise ConfigError('Configuration file errors encountered!')

    return None

<<<<<<< HEAD
def find_nftables_ct_rule(rule):
    helper_search = re.search('ct helper set "(\w+)"', rule)
    if helper_search:
        rule = helper_search[1]
    return find_nftables_rule('raw', 'VYOS_CT_HELPER', [rule])

def find_remove_rule(rule):
    handle = find_nftables_ct_rule(rule)
    if handle:
        remove_nftables_rule('raw', 'VYOS_CT_HELPER', handle)

=======
>>>>>>> 734d84f69 (conntrack: T5571: Refactor conntrack to be independent conf script from firewall, nat, nat66)
def apply(conntrack):
    # Depending on the enable/disable state of the ALG (Application Layer Gateway)
    # modules we need to either insmod or rmmod the helpers.
    for module, module_config in module_map.items():
        if dict_search(f'modules.{module}', conntrack) is None:
            if 'ko' in module_config:
                for mod in module_config['ko']:
                    # Only remove the module if it's loaded
                    if os.path.exists(f'/sys/module/{mod}'):
                        cmd(f'rmmod {mod}')
<<<<<<< HEAD
            if 'nftables' in module_config:
                for rule in module_config['nftables']:
                    find_remove_rule(rule)
=======
>>>>>>> 734d84f69 (conntrack: T5571: Refactor conntrack to be independent conf script from firewall, nat, nat66)
        else:
            if 'ko' in module_config:
                for mod in module_config['ko']:
                    cmd(f'modprobe {mod}')
<<<<<<< HEAD
            if 'nftables' in module_config:
                for rule in module_config['nftables']:
                    if not find_nftables_ct_rule(rule):
                        cmd(f'nft insert rule ip raw VYOS_CT_HELPER {rule}')
=======
>>>>>>> 734d84f69 (conntrack: T5571: Refactor conntrack to be independent conf script from firewall, nat, nat66)

    # Load new nftables ruleset
    cmd(f'nft -f {nftables_ct_file}')

    if process_named_running('conntrackd'):
        # Reload conntrack-sync daemon to fetch new sysctl values
        resync_conntrackd()

    # We silently ignore all errors
    # See: https://bugzilla.redhat.com/show_bug.cgi?id=1264080
    cmd(f'sysctl -f {sysctl_file}')

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
