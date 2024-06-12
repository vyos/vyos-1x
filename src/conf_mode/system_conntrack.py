#!/usr/bin/env python3
#
# Copyright (C) 2021-2024 VyOS maintainers and contributors
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
from vyos.utils.dict import dict_search
from vyos.utils.dict import dict_search_args
from vyos.utils.dict import dict_search_recursive
from vyos.utils.process import cmd
from vyos.utils.process import rc_cmd
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
    'ftp': {
        'ko': ['nf_nat_ftp', 'nf_conntrack_ftp'],
        'nftables': ['tcp dport {21} ct helper set "ftp_tcp" return']
    },
    'h323': {
        'ko': ['nf_nat_h323', 'nf_conntrack_h323'],
        'nftables': ['udp dport {1719} ct helper set "ras_udp" return',
                     'tcp dport {1720} ct helper set "q931_tcp" return']
    },
    'nfs': {
        'nftables': ['tcp dport {111} ct helper set "rpc_tcp" return',
                     'udp dport {111} ct helper set "rpc_udp" return']
    },
    'pptp': {
        'ko': ['nf_nat_pptp', 'nf_conntrack_pptp'],
        'nftables': ['tcp dport {1723} ct helper set "pptp_tcp" return'],
        'ipv4': True
     },
    'rtsp': {
        'ko': ['nf_nat_rtsp', 'nf_conntrack_rtsp'],
        'nftables': ['tcp dport {554} ct helper set "rtsp_tcp" return'],
        'ipv4': True
    },
    'sip': {
        'ko': ['nf_nat_sip', 'nf_conntrack_sip'],
        'nftables': ['tcp dport {5060,5061} ct helper set "sip_tcp" return',
                     'udp dport {5060,5061} ct helper set "sip_udp" return']
     },
    'sqlnet': {
        'nftables': ['tcp dport {1521,1525,1536} ct helper set "tns_tcp" return']
    },
    'tftp': {
        'ko': ['nf_nat_tftp', 'nf_conntrack_tftp'],
        'nftables': ['udp dport {69} ct helper set "tftp_udp" return']
     },
}

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
    base = ['system', 'conntrack']

    conntrack = conf.get_config_dict(base, key_mangling=('-', '_'),
                                     get_first_key=True,
                                     with_recursive_defaults=True)

    conntrack['firewall'] = conf.get_config_dict(['firewall'], key_mangling=('-', '_'),
                                                 get_first_key=True,
                                                 no_tag_node_value_mangle=True)

    conntrack['ipv4_nat_action'] = 'accept' if conf.exists(['nat']) else 'return'
    conntrack['ipv6_nat_action'] = 'accept' if conf.exists(['nat66']) else 'return'
    conntrack['wlb_action'] = 'accept' if conf.exists(['load-balancing', 'wan']) else 'return'
    conntrack['wlb_local_action'] = conf.exists(['load-balancing', 'wan', 'enable-local-traffic'])

    conntrack['module_map'] = module_map

    if conf.exists(['service', 'conntrack-sync']):
        set_dependents('conntrack_sync', conf)

    # If conntrack status changes, VRF zone rules need updating
    if conf.exists(['vrf']):
        set_dependents('vrf', conf)

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

            Warning(f'It is prefered to define {inet} conntrack ignore rules in <firewall {inet} prerouting raw> section')

        if dict_search_args(conntrack, 'timeout', 'custom', inet, 'rule') != None:
            for rule, rule_config in conntrack['timeout']['custom'][inet]['rule'].items():
                if 'protocol' not in rule_config:
                    raise ConfigError(f'Conntrack custom timeout rule {rule} requires protocol tcp or udp')
                else:
                    if 'tcp' in rule_config['protocol'] and 'udp' in rule_config['protocol']:
                        raise ConfigError(f'conntrack custom timeout rule {rule} - Cant use both tcp and udp protocol')
    return None

def generate(conntrack):
    if not os.path.exists(nftables_ct_file):
        conntrack['first_install'] = True

    # Determine if conntrack is needed
    conntrack['ipv4_firewall_action'] = 'return'
    conntrack['ipv6_firewall_action'] = 'return'

    if dict_search_args(conntrack['firewall'], 'global_options', 'state_policy') != None:
        conntrack['ipv4_firewall_action'] = 'accept'
        conntrack['ipv6_firewall_action'] = 'accept'
    else:
        for rules, path in dict_search_recursive(conntrack['firewall'], 'rule'):
            if any(('state' in rule_conf or 'connection_status' in rule_conf or 'offload_target' in rule_conf) for rule_conf in rules.values()):
                if path[0] == 'ipv4':
                    conntrack['ipv4_firewall_action'] = 'accept'
                elif path[0] == 'ipv6':
                    conntrack['ipv6_firewall_action'] = 'accept'

    render(conntrack_config, 'conntrack/vyos_nf_conntrack.conf.j2', conntrack)
    render(sysctl_file, 'conntrack/sysctl.conf.j2', conntrack)
    render(nftables_ct_file, 'conntrack/nftables-ct.j2', conntrack)
    return None

def apply(conntrack):
    # Depending on the enable/disable state of the ALG (Application Layer Gateway)
    # modules we need to either insmod or rmmod the helpers.

    add_modules = []
    rm_modules = []

    for module, module_config in module_map.items():
        if dict_search_args(conntrack, 'modules', module) is None:
            if 'ko' in module_config:
                unloaded = [mod for mod in module_config['ko'] if os.path.exists(f'/sys/module/{mod}')]
                rm_modules.extend(unloaded)
        else:
            if 'ko' in module_config:
                add_modules.extend(module_config['ko'])

    # Add modules before nftables uses them
    if add_modules:
        module_str = ' '.join(add_modules)
        cmd(f'modprobe -a {module_str}')

    # Load new nftables ruleset
    install_result, output = rc_cmd(f'nft --file {nftables_ct_file}')
    if install_result == 1:
        raise ConfigError(f'Failed to apply configuration: {output}')

    # Remove modules after nftables stops using them
    if rm_modules:
        module_str = ' '.join(rm_modules)
        cmd(f'rmmod {module_str}')

    try:
        call_dependents()
    except ConfigError:
        # Ignore config errors on dependent due to being called too early. Example:
        # ConfigError("ConfigError('Interface ethN requires an IP address!')")
        pass

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
