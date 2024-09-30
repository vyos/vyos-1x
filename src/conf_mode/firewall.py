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
import re

from sys import exit

from vyos.base import Warning
from vyos.config import Config
from vyos.configdict import is_node_changed
from vyos.configdiff import get_config_diff, Diff
from vyos.configdep import set_dependents, call_dependents
from vyos.configverify import verify_interface_exists
from vyos.ethtool import Ethtool
from vyos.firewall import fqdn_config_parse
from vyos.firewall import geoip_update
from vyos.template import render
from vyos.utils.dict import dict_search_args
from vyos.utils.dict import dict_search_recursive
from vyos.utils.process import call
from vyos.utils.process import cmd
from vyos.utils.process import rc_cmd
from vyos import ConfigError
from vyos import airbag
from pathlib import Path
from subprocess import run as subp_run

airbag.enable()

nftables_conf = '/run/nftables.conf'
domain_resolver_usage = '/run/use-vyos-domain-resolver-firewall'
domain_resolver_usage_nat = '/run/use-vyos-domain-resolver-nat'

sysctl_file = r'/run/sysctl/10-vyos-firewall.conf'

valid_groups = [
    'address_group',
    'domain_group',
    'network_group',
    'port_group',
    'interface_group',
    ## Added for group ussage in bridge firewall
    'ipv4_address_group',
    'ipv6_address_group',
    'ipv4_network_group',
    'ipv6_network_group'
]

nested_group_types = [
    'address_group', 'network_group', 'mac_group',
    'port_group', 'ipv6_address_group', 'ipv6_network_group'
]

snmp_change_type = {
    'unknown': 0,
    'add': 1,
    'delete': 2,
    'change': 3
}
snmp_event_source = 1
snmp_trap_mib = 'VYATTA-TRAP-MIB'
snmp_trap_name = 'mgmtEventTrap'

def geoip_updated(conf, firewall):
    diff = get_config_diff(conf)
    node_diff = diff.get_child_nodes_diff(['firewall'], expand_nodes=Diff.DELETE, recursive=True)

    out = {
        'name': [],
        'ipv6_name': [],
        'deleted_name': [],
        'deleted_ipv6_name': []
    }
    updated = False

    for key, path in dict_search_recursive(firewall, 'geoip'):
        set_name = f'GEOIP_CC_{path[1]}_{path[2]}_{path[4]}'
        if (path[0] == 'ipv4'):
            out['name'].append(set_name)
        elif (path[0] == 'ipv6'):
            set_name = f'GEOIP_CC6_{path[1]}_{path[2]}_{path[4]}'
            out['ipv6_name'].append(set_name)

        updated = True

    if 'delete' in node_diff:
        for key, path in dict_search_recursive(node_diff['delete'], 'geoip'):
            set_name = f'GEOIP_CC_{path[1]}_{path[2]}_{path[4]}'
            if (path[0] == 'ipv4'):
                out['deleted_name'].append(set_name)
            elif (path[0] == 'ipv6'):
                set_name = f'GEOIP_CC_{path[1]}_{path[2]}_{path[4]}'
                out['deleted_ipv6_name'].append(set_name)
            updated = True

    if updated:
        return out

    return False

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['firewall']

    firewall = conf.get_config_dict(base, key_mangling=('-', '_'),
                                    no_tag_node_value_mangle=True,
                                    get_first_key=True,
                                    with_recursive_defaults=True)


    firewall['group_resync'] = bool('group' in firewall or is_node_changed(conf, base + ['group']))
    if firewall['group_resync']:
        # Update nat and policy-route as firewall groups were updated
        set_dependents('group_resync', conf)

    firewall['geoip_updated'] = geoip_updated(conf, firewall)

    fqdn_config_parse(firewall, 'firewall')

    set_dependents('conntrack', conf)

    return firewall

def verify_jump_target(firewall, hook, jump_target, family, recursive=False):
    targets_seen = []
    targets_pending = [jump_target]

    while targets_pending:
        target = targets_pending.pop()

        if 'name' not in firewall[family]:
            raise ConfigError(f'Invalid jump-target. Firewall {family} name {target} does not exist on the system')
        elif target not in dict_search_args(firewall, family, 'name'):
            raise ConfigError(f'Invalid jump-target. Firewall {family} name {target} does not exist on the system')

        target_rules = dict_search_args(firewall, family, 'name', target, 'rule')
        no_ipsec_in = hook in ('output', )

        if target_rules:
            for target_rule_conf in target_rules.values():
                # Output hook types will not tolerate 'meta ipsec exists' matches even in jump targets:
                if no_ipsec_in and (dict_search_args(target_rule_conf, 'ipsec', 'match_ipsec_in') is not None \
                                    or dict_search_args(target_rule_conf, 'ipsec', 'match_none_in') is not None):
                    raise ConfigError(f'Invalid jump-target for {hook}. Firewall {family} name {target} rules contain incompatible ipsec inbound matches')
                # Make sure we're not looping back on ourselves somewhere:
                if recursive and 'jump_target' in target_rule_conf:
                    child_target = target_rule_conf['jump_target']
                    if child_target in targets_seen:
                        raise ConfigError(f'Loop detected in jump-targets, firewall {family} name {target} refers to previously traversed {family} name {child_target}')
                    targets_pending.append(child_target)
                    if len(targets_seen) == 7:
                        path_txt = ' -> '.join(targets_seen)
                        Warning(f'Deep nesting of jump targets has reached 8 levels deep, following the path {path_txt} -> {child_target}!')

        targets_seen.append(target)

def verify_rule(firewall, family, hook, priority, rule_id, rule_conf):
    if 'action' not in rule_conf:
        raise ConfigError('Rule action must be defined')

    if 'jump' in rule_conf['action'] and 'jump_target' not in rule_conf:
        raise ConfigError('Action set to jump, but no jump-target specified')

    if 'jump_target' in rule_conf:
        if 'jump' not in rule_conf['action']:
            raise ConfigError('jump-target defined, but action jump needed and it is not defined')
        target = rule_conf['jump_target']
        if hook != 'name': # This is a bit clumsy, but consolidates a chunk of code. 
            verify_jump_target(firewall, hook, target, family, recursive=True)
        else:
            verify_jump_target(firewall, hook, target, family, recursive=False)

    if rule_conf['action'] == 'offload':
        if 'offload_target' not in rule_conf:
            raise ConfigError('Action set to offload, but no offload-target specified')

        offload_target = rule_conf['offload_target']

        if not dict_search_args(firewall, 'flowtable', offload_target):
            raise ConfigError(f'Invalid offload-target. Flowtable "{offload_target}" does not exist on the system')

    if rule_conf['action'] != 'synproxy' and 'synproxy' in rule_conf:
        raise ConfigError('"synproxy" option allowed only for action synproxy')
    if rule_conf['action'] == 'synproxy':
        if 'state' in rule_conf:
            raise ConfigError('For action "synproxy" state cannot be defined')
        if not rule_conf.get('synproxy', {}).get('tcp'):
            raise ConfigError('synproxy TCP MSS is not defined')
        if rule_conf.get('protocol', {}) != 'tcp':
            raise ConfigError('For action "synproxy" the protocol must be set to TCP')

    if 'queue_options' in rule_conf:
        if 'queue' not in rule_conf['action']:
            raise ConfigError('queue-options defined, but action queue needed and it is not defined')
        if 'fanout' in rule_conf['queue_options'] and ('queue' not in rule_conf or '-' not in rule_conf['queue']):
            raise ConfigError('queue-options fanout defined, then queue needs to be defined as a range')

    if 'queue' in rule_conf and 'queue' not in rule_conf['action']:
        raise ConfigError('queue defined, but action queue needed and it is not defined')

    if 'fragment' in rule_conf:
        if {'match_frag', 'match_non_frag'} <= set(rule_conf['fragment']):
            raise ConfigError('Cannot specify both "match-frag" and "match-non-frag"')

    if 'limit' in rule_conf:
        if 'rate' in rule_conf['limit']:
            rate_int = re.sub(r'\D', '', rule_conf['limit']['rate'])
            if int(rate_int) < 1:
                raise ConfigError('Limit rate integer cannot be less than 1')

    if 'ipsec' in rule_conf:
        if {'match_ipsec_in', 'match_none_in'} <= set(rule_conf['ipsec']):
            raise ConfigError('Cannot specify both "match-ipsec" and "match-none"')
        if {'match_ipsec_out', 'match_none_out'} <= set(rule_conf['ipsec']):
            raise ConfigError('Cannot specify both "match-ipsec" and "match-none"')

    if 'recent' in rule_conf:
        if not {'count', 'time'} <= set(rule_conf['recent']):
            raise ConfigError('Recent "count" and "time" values must be defined')

    if 'gre' in rule_conf:
        if dict_search_args(rule_conf, 'protocol') != 'gre':
            raise ConfigError('Protocol must be gre when matching GRE flags and fields')

        if dict_search_args(rule_conf, 'gre', 'key'):
            if dict_search_args(rule_conf, 'gre', 'version') == 'pptp':
                raise ConfigError('GRE tunnel keys are not present in PPTP')

            if dict_search_args(rule_conf, 'gre', 'flags', 'checksum') is None:
                # There is no builtin match in nftables for the GRE key, so we need to do a raw lookup.
                # The offset of the key within the packet shifts depending on the C-flag. 
                # 99% of the time, nobody will have checksums enabled - it's usually a manual config option. 
                # We can either assume it is unset unless otherwise directed 
                # (confusing, requires doco to explain why it doesn't work sometimes)
                # or, demand an explicit selection to be made for this specific match rule. 
                # This check enforces the latter. The user is free to create rules for both cases. 
                raise ConfigError('Matching GRE tunnel key requires an explicit checksum flag match. For most cases, use "gre flags checksum unset"')

            if dict_search_args(rule_conf, 'gre', 'flags', 'key', 'unset') is not None:
                raise ConfigError('Matching GRE tunnel key implies "flags key", cannot specify "flags key unset"')

        gre_inner_proto = dict_search_args(rule_conf, 'gre', 'inner_proto')
        if gre_inner_proto is not None:
            try:
                gre_inner_value = int(gre_inner_proto, 0)
                if gre_inner_value < 0 or gre_inner_value > 65535:
                    raise ConfigError('inner-proto outside valid ethertype range 0-65535')
            except ValueError:
                pass # Symbolic constant, pre-validated before reaching here. 

    tcp_flags = dict_search_args(rule_conf, 'tcp', 'flags')
    if tcp_flags:
        if dict_search_args(rule_conf, 'protocol') != 'tcp':
            raise ConfigError('Protocol must be tcp when specifying tcp flags')

        not_flags = dict_search_args(rule_conf, 'tcp', 'flags', 'not')
        if not_flags:
            duplicates = [flag for flag in tcp_flags if flag in not_flags]
            if duplicates:
                raise ConfigError(f'Cannot match a tcp flag as set and not set')

    if 'protocol' in rule_conf:
        if rule_conf['protocol'] == 'icmp' and family == 'ipv6':
            raise ConfigError(f'Cannot match IPv4 ICMP protocol on IPv6, use ipv6-icmp')
        if rule_conf['protocol'] == 'ipv6-icmp' and family == 'ipv4':
            raise ConfigError(f'Cannot match IPv6 ICMP protocol on IPv4, use icmp')

    for side in ['destination', 'source']:
        if side in rule_conf:
            side_conf = rule_conf[side]

            if len({'address', 'fqdn', 'geoip'} & set(side_conf)) > 1:
                raise ConfigError('Only one of address, fqdn or geoip can be specified')

            if 'group' in side_conf:
                if len({'address_group', 'network_group', 'domain_group'} & set(side_conf['group'])) > 1:
                    raise ConfigError('Only one address-group, network-group or domain-group can be specified')

                for group in valid_groups:
                    if group in side_conf['group']:
                        group_name = side_conf['group'][group]

                        if family == 'ipv6' and group in ['address_group', 'network_group']:
                            fw_group = f'ipv6_{group}'
                        elif family == 'bridge':
                            if group =='ipv4_address_group':
                                fw_group = 'address_group'
                            elif group == 'ipv4_network_group':
                                fw_group = 'network_group'
                            else:
                                fw_group = group
                        else:
                            fw_group = group

                        error_group = fw_group.replace("_", "-")

                        if group in ['address_group', 'network_group', 'domain_group']:
                            types = [t for t in ['address', 'fqdn', 'geoip'] if t in side_conf]
                            if types:
                                raise ConfigError(f'{error_group} and {types[0]} cannot both be defined')

                        if group_name and group_name[0] == '!':
                            group_name = group_name[1:]

                        group_obj = dict_search_args(firewall, 'group', fw_group, group_name)

                        if group_obj is None:
                            raise ConfigError(f'Invalid {error_group} "{group_name}" on firewall rule')

                        if not group_obj:
                            Warning(f'{error_group} "{group_name}" has no members!')

            if 'port' in side_conf or dict_search_args(side_conf, 'group', 'port_group'):
                if 'protocol' not in rule_conf:
                    raise ConfigError('Protocol must be defined if specifying a port or port-group')

                if rule_conf['protocol'] not in ['tcp', 'udp', 'tcp_udp']:
                    raise ConfigError('Protocol must be tcp, udp, or tcp_udp when specifying a port or port-group')

            if 'port' in side_conf and dict_search_args(side_conf, 'group', 'port_group'):
                raise ConfigError(f'{side} port-group and port cannot both be defined')

    if 'add_address_to_group' in rule_conf:
        for type in ['destination_address', 'source_address']:
            if type in rule_conf['add_address_to_group']:
                if 'address_group' not in rule_conf['add_address_to_group'][type]:
                    raise ConfigError(f'Dynamic address group must be defined.')
                else:
                    target = rule_conf['add_address_to_group'][type]['address_group']
                    fwall_group = 'ipv6_address_group' if family == 'ipv6' else 'address_group'
                    group_obj = dict_search_args(firewall, 'group', 'dynamic_group', fwall_group, target)
                    if group_obj is None:
                            raise ConfigError(f'Invalid dynamic address group on firewall rule')

    if 'log_options' in rule_conf:
        if 'log' not in rule_conf:
            raise ConfigError('log-options defined, but log is not enable')

        if 'snapshot_length' in rule_conf['log_options'] and 'group' not in rule_conf['log_options']:
            raise ConfigError('log-options snapshot-length defined, but log group is not define')

        if 'queue_threshold' in rule_conf['log_options'] and 'group' not in rule_conf['log_options']:
            raise ConfigError('log-options queue-threshold defined, but log group is not define')

    for direction in ['inbound_interface','outbound_interface']:
        if direction in rule_conf:
            if 'name' in rule_conf[direction] and 'group' in rule_conf[direction]:
                raise ConfigError(f'Cannot specify both interface group and interface name for {direction}')
            if 'group' in rule_conf[direction]:
                group_name = rule_conf[direction]['group']
                if group_name[0] == '!':
                    group_name = group_name[1:]
                group_obj = dict_search_args(firewall, 'group', 'interface_group', group_name)
                if group_obj is None:
                    raise ConfigError(f'Invalid interface group "{group_name}" on firewall rule')
                if not group_obj:
                    Warning(f'interface-group "{group_name}" has no members!')

def verify_nested_group(group_name, group, groups, seen):
    if 'include' not in group:
        return

    seen.append(group_name)

    for g in group['include']:
        if g not in groups:
            raise ConfigError(f'Nested group "{g}" does not exist')

        if g in seen:
            raise ConfigError(f'Group "{group_name}" has a circular reference')

        if 'include' in groups[g]:
            verify_nested_group(g, groups[g], groups, seen)

def verify_hardware_offload(ifname):
    ethtool = Ethtool(ifname)
    enabled, fixed = ethtool.get_hw_tc_offload()

    if not enabled and fixed:
        raise ConfigError(f'Interface "{ifname}" does not support hardware offload')

    if not enabled:
        raise ConfigError(f'Interface "{ifname}" requires "offload hw-tc-offload"')

def verify(firewall):
    if 'flowtable' in firewall:
        for flowtable, flowtable_conf in firewall['flowtable'].items():
            if 'interface' not in flowtable_conf:
                raise ConfigError(f'Flowtable "{flowtable}" requires at least one interface')

            for ifname in flowtable_conf['interface']:
                verify_interface_exists(firewall, ifname)

            if dict_search_args(flowtable_conf, 'offload') == 'hardware':
                interfaces = flowtable_conf['interface']

                for ifname in interfaces:
                    verify_hardware_offload(ifname)

    if 'group' in firewall:
        for group_type in nested_group_types:
            if group_type in firewall['group']:
                groups = firewall['group'][group_type]
                for group_name, group in groups.items():
                    verify_nested_group(group_name, group, groups, [])

    for family in ['ipv4', 'ipv6', 'bridge']:
        if family in firewall:
            for chain in ['name','forward','input','output', 'prerouting']:
                if chain in firewall[family]:
                    for priority, priority_conf in firewall[family][chain].items():
                        if 'jump' in priority_conf['default_action'] and 'default_jump_target' not in priority_conf:
                            raise ConfigError('default-action set to jump, but no default-jump-target specified')
                        if 'default_jump_target' in priority_conf:
                            target = priority_conf['default_jump_target']
                            if 'jump' not in priority_conf['default_action']:
                                raise ConfigError('default-jump-target defined, but default-action jump needed and it is not defined')
                            if priority_conf['default_jump_target'] == priority:
                                raise ConfigError(f'Loop detected on default-jump-target.')
                            if target not in dict_search_args(firewall[family], 'name'):
                                raise ConfigError(f'Invalid jump-target. Firewall name {target} does not exist on the system')
                        if 'rule' in priority_conf:
                            for rule_id, rule_conf in priority_conf['rule'].items():
                                verify_rule(firewall, family, chain, priority, rule_id, rule_conf)

    local_zone = False
    zone_interfaces = []

    if 'zone' in firewall:
        for zone, zone_conf in firewall['zone'].items():
            if 'local_zone' not in zone_conf and 'interface' not in zone_conf:
                raise ConfigError(f'Zone "{zone}" has no interfaces and is not the local zone')

            if 'local_zone' in zone_conf:
                if local_zone:
                    raise ConfigError('There cannot be multiple local zones')
                if 'interface' in zone_conf:
                    raise ConfigError('Local zone cannot have interfaces assigned')
                if 'intra_zone_filtering' in zone_conf:
                    raise ConfigError('Local zone cannot use intra-zone-filtering')
                local_zone = True

            if 'interface' in zone_conf:
                found_duplicates = [intf for intf in zone_conf['interface'] if intf in zone_interfaces]

                if found_duplicates:
                    raise ConfigError(f'Interfaces cannot be assigned to multiple zones')

                zone_interfaces += zone_conf['interface']

            if 'intra_zone_filtering' in zone_conf:
                intra_zone = zone_conf['intra_zone_filtering']

                if len(intra_zone) > 1:
                    raise ConfigError('Only one intra-zone-filtering action must be specified')

                if 'firewall' in intra_zone:
                    v4_name = dict_search_args(intra_zone, 'firewall', 'name')
                    if v4_name and not dict_search_args(firewall, 'ipv4', 'name', v4_name):
                        raise ConfigError(f'Firewall name "{v4_name}" does not exist')

                    v6_name = dict_search_args(intra_zone, 'firewall', 'ipv6_name')
                    if v6_name and not dict_search_args(firewall, 'ipv6', 'name', v6_name):
                        raise ConfigError(f'Firewall ipv6-name "{v6_name}" does not exist')

                    if not v4_name and not v6_name:
                        raise ConfigError('No firewall names specified for intra-zone-filtering')

            if 'from' in zone_conf:
                for from_zone, from_conf in zone_conf['from'].items():
                    if from_zone not in firewall['zone']:
                        raise ConfigError(f'Zone "{zone}" refers to a non-existent or deleted zone "{from_zone}"')

                    v4_name = dict_search_args(from_conf, 'firewall', 'name')
                    if v4_name and not dict_search_args(firewall, 'ipv4', 'name', v4_name):
                        raise ConfigError(f'Firewall name "{v4_name}" does not exist')

                    v6_name = dict_search_args(from_conf, 'firewall', 'ipv6_name')
                    if v6_name and not dict_search_args(firewall, 'ipv6', 'name', v6_name):
                        raise ConfigError(f'Firewall ipv6-name "{v6_name}" does not exist')

    return None

def generate(firewall):
    if not os.path.exists(nftables_conf):
        firewall['first_install'] = True

    if 'zone' in firewall:
        for local_zone, local_zone_conf in firewall['zone'].items():
            if 'local_zone' not in local_zone_conf:
                continue

            local_zone_conf['from_local'] = {}

            for zone, zone_conf in firewall['zone'].items():
                if zone == local_zone or 'from' not in zone_conf:
                    continue
                if local_zone in zone_conf['from']:
                    local_zone_conf['from_local'][zone] = zone_conf['from'][local_zone]

    render(nftables_conf, 'firewall/nftables.j2', firewall)
    render(sysctl_file, 'firewall/sysctl-firewall.conf.j2', firewall)
    return None

def parse_firewall_error(output):
    # Define the regex patterns to extract the error message and the comment
    error_pattern = re.compile(r'Error:\s*(.*?)\n')
    comment_pattern = re.compile(r'comment\s+"([^"]+)"')
    error_output = []

    # Find all error messages in the output
    error_matches = error_pattern.findall(output)
    # Find all comment matches in the output
    comment_matches = comment_pattern.findall(output)

    if not error_matches or not comment_matches:
        raise ConfigError(f'Unknown firewall error detected: {output}')

    error_output.append('Fail to apply firewall')
    # Loop over the matches and process them
    for error_message, comment in zip(error_matches, comment_matches):
        # Parse the comment
        parsed_entries = comment.split('-')
        family = 'bridge' if parsed_entries[0] == 'bri' else parsed_entries[0]
        if parsed_entries[1] == 'NAM':
            chain = 'name'
        elif parsed_entries[1] == 'FWD':
            chain = 'forward'
        elif parsed_entries[1] == 'INP':
            chain = 'input'
        elif parsed_entries[1] == 'OUT':
            chain = 'output'
        elif parsed_entries[1] == 'PRE':
            chain = 'prerouting'
        error_output.append(f'Error found on: firewall {family} {chain} {parsed_entries[2]} rule {parsed_entries[3]}')
        error_output.append(f'\tError message: {error_message.strip()}')

    raise ConfigError('\n'.join(error_output))

def apply(firewall):
    # Use nft -c option to check current configuration file
    completed_process = subp_run(['nft', '-c', '--file', nftables_conf], capture_output=True)
    install_result = completed_process.returncode
    if install_result == 1:
        # We need to handle firewall error
        output = completed_process.stderr
        parse_firewall_error(output.decode())

    # No error detected during check, we can apply the new configuration
    install_result, output = rc_cmd(f'nft --file {nftables_conf}')
    # Double check just in case
    if install_result == 1:
        raise ConfigError(f'Failed to apply firewall: {output}')

    # Apply firewall global-options sysctl settings
    cmd(f'sysctl -f {sysctl_file}')

    call_dependents()

    ## DOMAIN RESOLVER
    domain_action = 'restart'
    if dict_search_args(firewall, 'group', 'domain_group') or firewall['ip_fqdn'].items() or firewall['ip6_fqdn'].items():
        text = f'# Automatically generated by firewall.py\nThis file indicates that vyos-domain-resolver service is used by the firewall.\n'
        Path(domain_resolver_usage).write_text(text)
    else:
        Path(domain_resolver_usage).unlink(missing_ok=True)
        if not Path('/run').glob('use-vyos-domain-resolver*'):
            domain_action = 'stop'
    call(f'systemctl {domain_action} vyos-domain-resolver.service')

    if firewall['geoip_updated']:
        # Call helper script to Update set contents
        if 'name' in firewall['geoip_updated'] or 'ipv6_name' in firewall['geoip_updated']:
            print('Updating GeoIP. Please wait...')
            geoip_update(firewall)

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
