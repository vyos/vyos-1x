#!/usr/bin/env python3
#
# Copyright (C) 2021-2022 VyOS maintainers and contributors
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

from glob import glob
from json import loads
from sys import exit

from vyos.base import Warning
from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.configdict import node_changed
from vyos.configdiff import get_config_diff, Diff
# from vyos.configverify import verify_interface_exists
from vyos.firewall import geoip_update
from vyos.firewall import get_ips_domains_dict
from vyos.firewall import nft_add_set_elements
from vyos.firewall import nft_flush_set
from vyos.firewall import nft_init_set
from vyos.firewall import nft_update_set_elements
from vyos.template import render
from vyos.util import call
from vyos.util import cmd
from vyos.util import dict_search_args
from vyos.util import dict_search_recursive
from vyos.util import process_named_running
from vyos.util import rc_cmd
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

policy_route_conf_script = '/usr/libexec/vyos/conf_mode/policy-route.py'

nftables_conf = '/run/nftables.conf'

nftables_zone_conf = '/run/nftables_zone.conf'
nftables6_zone_conf = '/run/nftables_zone6.conf'

sysfs_config = {
    'all_ping': {'sysfs': '/proc/sys/net/ipv4/icmp_echo_ignore_all', 'enable': '0', 'disable': '1'},
    'broadcast_ping': {'sysfs': '/proc/sys/net/ipv4/icmp_echo_ignore_broadcasts', 'enable': '0', 'disable': '1'},
    'ip_src_route': {'sysfs': '/proc/sys/net/ipv4/conf/*/accept_source_route'},
    'ipv6_receive_redirects': {'sysfs': '/proc/sys/net/ipv6/conf/*/accept_redirects'},
    'ipv6_src_route': {'sysfs': '/proc/sys/net/ipv6/conf/*/accept_source_route', 'enable': '0', 'disable': '-1'},
    'log_martians': {'sysfs': '/proc/sys/net/ipv4/conf/all/log_martians'},
    'receive_redirects': {'sysfs': '/proc/sys/net/ipv4/conf/*/accept_redirects'},
    'send_redirects': {'sysfs': '/proc/sys/net/ipv4/conf/*/send_redirects'},
    'source_validation': {'sysfs': '/proc/sys/net/ipv4/conf/*/rp_filter', 'disable': '0', 'strict': '1', 'loose': '2'},
    'syn_cookies': {'sysfs': '/proc/sys/net/ipv4/tcp_syncookies'},
    'twa_hazards_protection': {'sysfs': '/proc/sys/net/ipv4/tcp_rfc1337'}
}

valid_groups = [
    'address_group',
    'domain_group',
    'network_group',
    'port_group'
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

def get_firewall_zones(conf):
    used_v4 = []
    used_v6 = []
    zone_policy = conf.get_config_dict(['zone-policy'], key_mangling=('-', '_'), get_first_key=True,
                                    no_tag_node_value_mangle=True)

    if 'zone' in zone_policy:
        for zone, zone_conf in zone_policy['zone'].items():
            if 'from' in zone_conf:
                for from_zone, from_conf in zone_conf['from'].items():
                    name = dict_search_args(from_conf, 'firewall', 'name')
                    if name:
                        used_v4.append(name)

                    ipv6_name = dict_search_args(from_conf, 'firewall', 'ipv6_name')
                    if ipv6_name:
                        used_v6.append(ipv6_name)

            if 'intra_zone_filtering' in zone_conf:
                name = dict_search_args(zone_conf, 'intra_zone_filtering', 'firewall', 'name')
                if name:
                    used_v4.append(name)

                ipv6_name = dict_search_args(zone_conf, 'intra_zone_filtering', 'firewall', 'ipv6_name')
                if ipv6_name:
                    used_v6.append(ipv6_name)
    else:
        return None

    return {'name': used_v4, 'ipv6_name': used_v6}

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
        set_name = f'GEOIP_CC_{path[1]}_{path[3]}'
        if path[0] == 'name':
            out['name'].append(set_name)
        elif path[0] == 'ipv6_name':
            out['ipv6_name'].append(set_name)
        updated = True

    if 'delete' in node_diff:
        for key, path in dict_search_recursive(node_diff['delete'], 'geoip'):
            set_name = f'GEOIP_CC_{path[1]}_{path[3]}'
            if path[0] == 'name':
                out['deleted_name'].append(set_name)
            elif path[0] == 'ipv6-name':
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

    firewall = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True,
                                    no_tag_node_value_mangle=True)

    # We have gathered the dict representation of the CLI, but there are
    # default options which we need to update into the dictionary retrived.
    # XXX: T2665: we currently have no nice way for defaults under tag
    # nodes, thus we load the defaults "by hand"
    default_values = defaults(base)
    for tmp in ['name', 'ipv6_name']:
        if tmp in default_values:
            del default_values[tmp]

    firewall = dict_merge(default_values, firewall)

    # Merge in defaults for IPv4 ruleset
    if 'name' in firewall:
        default_values = defaults(base + ['name'])
        for name in firewall['name']:
            firewall['name'][name] = dict_merge(default_values,
                                                firewall['name'][name])

    # Merge in defaults for IPv6 ruleset
    if 'ipv6_name' in firewall:
        default_values = defaults(base + ['ipv6-name'])
        for ipv6_name in firewall['ipv6_name']:
            firewall['ipv6_name'][ipv6_name] = dict_merge(default_values,
                                                          firewall['ipv6_name'][ipv6_name])

    firewall['policy_resync'] = bool('group' in firewall or node_changed(conf, base + ['group']))
    firewall['zone_policy'] = get_firewall_zones(conf)

    if 'config_trap' in firewall and firewall['config_trap'] == 'enable':
        diff = get_config_diff(conf)
        firewall['trap_diff'] = diff.get_child_nodes_diff_str(base)
        firewall['trap_targets'] = conf.get_config_dict(['service', 'snmp', 'trap-target'],
                                        key_mangling=('-', '_'), get_first_key=True,
                                        no_tag_node_value_mangle=True)

    firewall['geoip_updated'] = geoip_updated(conf, firewall)

    return firewall

def verify_rule(firewall, rule_conf, ipv6):
    if 'action' not in rule_conf:
        raise ConfigError('Rule action must be defined')

    if 'fragment' in rule_conf:
        if {'match_frag', 'match_non_frag'} <= set(rule_conf['fragment']):
            raise ConfigError('Cannot specify both "match-frag" and "match-non-frag"')

    if 'limit' in rule_conf:
        if 'rate' in rule_conf['limit']:
            rate_int = re.sub(r'\D', '', rule_conf['limit']['rate'])
            if int(rate_int) < 1:
                raise ConfigError('Limit rate integer cannot be less than 1')

    if 'ipsec' in rule_conf:
        if {'match_ipsec', 'match_non_ipsec'} <= set(rule_conf['ipsec']):
            raise ConfigError('Cannot specify both "match-ipsec" and "match-non-ipsec"')

    if 'recent' in rule_conf:
        if not {'count', 'time'} <= set(rule_conf['recent']):
            raise ConfigError('Recent "count" and "time" values must be defined')

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
        if rule_conf['protocol'] == 'icmp' and ipv6:
            raise ConfigError(f'Cannot match IPv4 ICMP protocol on IPv6, use ipv6-icmp')
        if rule_conf['protocol'] == 'ipv6-icmp' and not ipv6:
            raise ConfigError(f'Cannot match IPv6 ICMP protocol on IPv4, use icmp')

    for side in ['destination', 'source']:
        if side in rule_conf:
            side_conf = rule_conf[side]

            if dict_search_args(side_conf, 'geoip', 'country_code'):
                if 'address' in side_conf:
                    raise ConfigError('Address and GeoIP cannot both be defined')

                if dict_search_args(side_conf, 'group', 'address_group'):
                    raise ConfigError('Address-group and GeoIP cannot both be defined')

                if dict_search_args(side_conf, 'group', 'network_group'):
                    raise ConfigError('Network-group and GeoIP cannot both be defined')

            if 'group' in side_conf:
                if {'address_group', 'network_group'} <= set(side_conf['group']):
                    raise ConfigError('Only one address-group or network-group can be specified')

                for group in valid_groups:
                    if group in side_conf['group']:
                        group_name = side_conf['group'][group]

                        if group_name and group_name[0] == '!':
                            group_name = group_name[1:]

                        fw_group = f'ipv6_{group}' if ipv6 and group in ['address_group', 'network_group'] else group
                        error_group = fw_group.replace("_", "-")
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

def verify_nested_group(group_name, group, groups, seen):
    if 'include' not in group:
        return

    for g in group['include']:
        if g not in groups:
            raise ConfigError(f'Nested group "{g}" does not exist')

        if g in seen:
            raise ConfigError(f'Group "{group_name}" has a circular reference')

        seen.append(g)

        if 'include' in groups[g]:
            verify_nested_group(g, groups[g], groups, seen)

def verify(firewall):
    if 'config_trap' in firewall and firewall['config_trap'] == 'enable':
        if not firewall['trap_targets']:
            raise ConfigError(f'Firewall config-trap enabled but "service snmp trap-target" is not defined')

    if 'group' in firewall:
        for group_type in nested_group_types:
            if group_type in firewall['group']:
                groups = firewall['group'][group_type]
                for group_name, group in groups.items():
                    verify_nested_group(group_name, group, groups, [])

    for name in ['name', 'ipv6_name']:
        if name in firewall:
            for name_id, name_conf in firewall[name].items():
                if 'rule' in name_conf:
                    for rule_id, rule_conf in name_conf['rule'].items():
                        verify_rule(firewall, rule_conf, name == 'ipv6_name')

    if 'interface' in firewall:
        for ifname, if_firewall in firewall['interface'].items():
            # verify ifname needs to be disabled, dynamic devices come up later
            # verify_interface_exists(ifname)

            for direction in ['in', 'out', 'local']:
                name = dict_search_args(if_firewall, direction, 'name')
                ipv6_name = dict_search_args(if_firewall, direction, 'ipv6_name')

                if name and dict_search_args(firewall, 'name', name) == None:
                    raise ConfigError(f'Invalid firewall name "{name}" referenced on interface {ifname}')

                if ipv6_name and dict_search_args(firewall, 'ipv6_name', ipv6_name) == None:
                    raise ConfigError(f'Invalid firewall ipv6-name "{ipv6_name}" referenced on interface {ifname}')

    if firewall['zone_policy']:
        for fw_name, used_names in firewall['zone_policy'].items():
            for name in used_names:
                if dict_search_args(firewall, fw_name, name) == None:
                    raise ConfigError(f'Firewall {fw_name.replace("_", "-")} "{name}" is still referenced in zone-policy')

    return None

def generate(firewall):
    if not os.path.exists(nftables_conf):
        firewall['first_install'] = True

    if os.path.exists(nftables_zone_conf):
        firewall['zone_conf'] = nftables_zone_conf

    if os.path.exists(nftables6_zone_conf):
        firewall['zone6_conf'] = nftables6_zone_conf

    render(nftables_conf, 'firewall/nftables.j2', firewall)
    return None

def apply_sysfs(firewall):
    for name, conf in sysfs_config.items():
        paths = glob(conf['sysfs'])
        value = None

        if name in firewall:
            conf_value = firewall[name]

            if conf_value in conf:
                value = conf[conf_value]
            elif conf_value == 'enable':
                value = '1'
            elif conf_value == 'disable':
                value = '0'

        if value:
            for path in paths:
                with open(path, 'w') as f:
                    f.write(value)

def post_apply_trap(firewall):
    if 'first_install' in firewall:
        return None

    if 'config_trap' not in firewall or firewall['config_trap'] != 'enable':
        return None

    if not process_named_running('snmpd'):
        return None

    trap_username = os.getlogin()

    for host, target_conf in firewall['trap_targets'].items():
        community = target_conf['community'] if 'community' in target_conf else 'public'
        port = int(target_conf['port']) if 'port' in target_conf else 162

        base_cmd = f'snmptrap -v2c -c {community} {host}:{port} 0 {snmp_trap_mib}::{snmp_trap_name} '

        for change_type, changes in firewall['trap_diff'].items():
            for path_str, value in changes.items():
                objects = [
                    f'mgmtEventUser s "{trap_username}"',
                    f'mgmtEventSource i {snmp_event_source}',
                    f'mgmtEventType i {snmp_change_type[change_type]}'
                ]

                if change_type == 'add':
                    objects.append(f'mgmtEventCurrCfg s "{path_str} {value}"')
                elif change_type == 'delete':
                    objects.append(f'mgmtEventPrevCfg s "{path_str} {value}"')
                elif change_type == 'change':
                    objects.append(f'mgmtEventPrevCfg s "{path_str} {value[0]}"')
                    objects.append(f'mgmtEventCurrCfg s "{path_str} {value[1]}"')

                cmd(base_cmd + ' '.join(objects))

def resync_policy_route():
    # Update policy route as firewall groups were updated
    tmp, out = rc_cmd(policy_route_conf_script)
    if tmp > 0:
        Warning(f'Failed to re-apply policy route configuration! {out}')

def apply(firewall):
    install_result, output = rc_cmd(f'nft -f {nftables_conf}')
    if install_result == 1:
        raise ConfigError(f'Failed to apply firewall: {output}')

    # set firewall group domain-group xxx
    if 'group' in firewall:
        if 'domain_group' in firewall['group']:
            # T970 Enable a resolver (systemd daemon) that checks
            # domain-group addresses and update entries for domains by timeout
            # If router loaded without internet connection or for synchronization
            call('systemctl restart vyos-domain-group-resolve.service')
            for group, group_config in firewall['group']['domain_group'].items():
                domains = []
                if group_config.get('address') is not None:
                    for address in group_config.get('address'):
                        domains.append(address)
                # Add elements to domain-group, try to resolve domain => ip
                # and add elements to nft set
                ip_dict = get_ips_domains_dict(domains)
                elements = sum(ip_dict.values(), [])
                nft_init_set(f'D_{group}')
                nft_add_set_elements(f'D_{group}', elements)
        else:
            call('systemctl stop vyos-domain-group-resolve.service')

    apply_sysfs(firewall)

    if firewall['policy_resync']:
        resync_policy_route()

    if firewall['geoip_updated']:
        # Call helper script to Update set contents
        if 'name' in firewall['geoip_updated'] or 'ipv6_name' in firewall['geoip_updated']:
            print('Updating GeoIP. Please wait...')
            geoip_update(firewall)

    post_apply_trap(firewall)

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
