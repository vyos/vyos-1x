#!/usr/bin/env python3
#
# Copyright (C) 2023-2024 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import ipaddress
import json
import re
import tabulate
import textwrap

from vyos.config import Config
from vyos.utils.process import cmd
from vyos.utils.dict import dict_search_args

def get_config_node(conf, node=None, family=None, hook=None, priority=None):
    if node == 'nat':
        if family == 'ipv6':
            config_path = ['nat66']
        else:
            config_path = ['nat']

    elif node == 'policy':
        config_path = ['policy']
    else:
        config_path = ['firewall']
        if family:
            config_path += [family]
            if hook:
                config_path += [hook]
                if priority:
                    config_path += [priority]

    node_config = conf.get_config_dict(config_path, key_mangling=('-', '_'),
                                get_first_key=True, no_tag_node_value_mangle=True)

    return node_config

def get_nftables_details(family, hook, priority):
    if family == 'ipv6':
        suffix = 'ip6'
        name_prefix = 'NAME6_'
        aux='IPV6_'
    elif family == 'ipv4':
        suffix = 'ip'
        name_prefix = 'NAME_'
        aux=''
    else:
        suffix = 'bridge'
        name_prefix = 'NAME_'
        aux=''

    if hook == 'name' or hook == 'ipv6-name':
        command = f'nft list chain {suffix} vyos_filter {name_prefix}{priority}'
    else:
        up_hook = hook.upper()
        command = f'nft list chain {suffix} vyos_filter VYOS_{aux}{up_hook}_{priority}'

    try:
        results = cmd(command)
    except:
        return {}

    out = {}
    for line in results.split('\n'):
        comment_search = re.search(rf'{priority}[\- ](\d+|default-action)', line)
        if not comment_search:
            continue

        rule = {}
        rule_id = comment_search[1]
        counter_search = re.search(r'counter packets (\d+) bytes (\d+)', line)
        if counter_search:
            rule['packets'] = counter_search[1]
            rule['bytes'] = counter_search[2]

        rule['conditions'] = re.sub(r'(\b(counter packets \d+ bytes \d+|drop|reject|return|log)\b|comment "[\w\-]+")', '', line).strip()
        out[rule_id] = rule
    return out

def get_nftables_state_details(family):
    if family == 'ipv6':
        suffix = 'ip6'
        name_suffix = 'POLICY6'
    elif family == 'ipv4':
        suffix = 'ip'
        name_suffix = 'POLICY'
    else:
        # no state policy for bridge
        return {}

    command = f'nft list chain {suffix} vyos_filter VYOS_STATE_{name_suffix}'
    try:
        results = cmd(command)
    except:
        return {}

    out = {}
    for line in results.split('\n'):
        rule = {}
        for state in ['established', 'related', 'invalid']:
            if state in line:
                counter_search = re.search(r'counter packets (\d+) bytes (\d+)', line)
                if counter_search:
                    rule['packets'] = counter_search[1]
                    rule['bytes'] = counter_search[2]
                rule['conditions'] = re.sub(r'(\b(counter packets \d+ bytes \d+|drop|reject|return|log)\b|comment "[\w\-]+")', '', line).strip()
                out[state] = rule
    return out

def get_nftables_group_members(family, table, name):
    prefix = 'ip6' if family == 'ipv6' else 'ip'
    out = []

    try:
        results_str = cmd(f'nft -j list set {prefix} {table} {name}')
        results = json.loads(results_str)
    except:
        return out

    if 'nftables' not in results:
        return out

    for obj in results['nftables']:
        if 'set' not in obj:
            continue

        set_obj = obj['set']

        if 'elem' in set_obj:
            for elem in set_obj['elem']:
                if isinstance(elem, str):
                    out.append(elem)
                elif isinstance(elem, dict) and 'elem' in elem:
                    out.append(elem['elem'])

    return out

def output_firewall_vertical(rules, headers, adjust=True):
    for rule in rules:
        adjusted_rule = rule + [""] * (len(headers) - len(rule)) if adjust else rule # account for different header length, like default-action
        transformed_rule = [[header, textwrap.fill(adjusted_rule[i].replace('\n', ' '), 65)] for i, header in enumerate(headers) if i < len(adjusted_rule)] # create key-pair list from headers and rules lists; wrap at 100 char

        print(tabulate.tabulate(transformed_rule, tablefmt="presto"))
        print()

def output_firewall_name(family, hook, priority, firewall_conf, single_rule_id=None):
    print(f'\n---------------------------------\n{family} Firewall "{hook} {priority}"\n')

    details = get_nftables_details(family, hook, priority)
    rows = []

    if 'rule' in firewall_conf:
        for rule_id, rule_conf in firewall_conf['rule'].items():
            if single_rule_id and rule_id != single_rule_id:
                continue

            if 'disable' in rule_conf:
                continue

            row = [rule_id, textwrap.fill(rule_conf.get('description') or '', 50), rule_conf['action'], rule_conf['protocol'] if 'protocol' in rule_conf else 'all']
            if rule_id in details:
                rule_details = details[rule_id]
                row.append(rule_details.get('packets', 0))
                row.append(rule_details.get('bytes', 0))
                row.append(rule_details['conditions'])
            rows.append(row)

    if hook in ['input', 'forward', 'output']:
        def_action = firewall_conf['default_action'] if 'default_action' in firewall_conf else 'accept'
    else:
        def_action = firewall_conf['default_action'] if 'default_action' in firewall_conf else 'drop'
    row = ['default', '', def_action, 'all']
    rule_details = details['default-action']
    row.append(rule_details.get('packets', 0))
    row.append(rule_details.get('bytes', 0))

    rows.append(row)

    if rows:
        if args.rule:
            rows.pop()

        if args.detail:
            header = ['Rule', 'Description', 'Action', 'Protocol', 'Packets', 'Bytes', 'Conditions']
            output_firewall_vertical(rows, header)
        else:
            header = ['Rule', 'Action', 'Protocol', 'Packets', 'Bytes', 'Conditions']
            for i in rows:
                rows[rows.index(i)].pop(1)
            print(tabulate.tabulate(rows, header) + '\n')

def output_firewall_state_policy(family):
    if family == 'bridge':
        return {}
    print(f'\n---------------------------------\n{family} State Policy\n')

    details = get_nftables_state_details(family)
    rows = []

    for state, state_conf in details.items():
        row = [state, state_conf['conditions']]
        row.append(state_conf.get('packets', 0))
        row.append(state_conf.get('bytes', 0))
        row.append(state_conf.get('conditions'))
        rows.append(row)

    if rows:
        if args.rule:
            rows.pop()

        if args.detail:
            header = ['State', 'Conditions', 'Packets', 'Bytes']
            output_firewall_vertical(rows, header)
        else:
            header = ['State', 'Packets', 'Bytes', 'Conditions']
            for i in rows:
                rows[rows.index(i)].pop(1)
            print(tabulate.tabulate(rows, header) + '\n')

def output_firewall_name_statistics(family, hook, prior, prior_conf, single_rule_id=None):
    print(f'\n---------------------------------\n{family} Firewall "{hook} {prior}"\n')

    details = get_nftables_details(family, hook, prior)
    rows = []

    if 'rule' in prior_conf:
        for rule_id, rule_conf in prior_conf['rule'].items():
            if single_rule_id and rule_id != single_rule_id:
                continue

            if 'disable' in rule_conf:
                continue

            # Get source
            source_addr = dict_search_args(rule_conf, 'source', 'address')
            if not source_addr:
                source_addr = dict_search_args(rule_conf, 'source', 'group', 'address_group')
                if not source_addr:
                    source_addr = dict_search_args(rule_conf, 'source', 'group', 'network_group')
                    if not source_addr:
                        source_addr = dict_search_args(rule_conf, 'source', 'group', 'domain_group')
                        if not source_addr:
                            source_addr = dict_search_args(rule_conf, 'source', 'fqdn')
                            if not source_addr:
                                source_addr = dict_search_args(rule_conf, 'source', 'geoip', 'country_code')
                                if source_addr:
                                    source_addr = str(source_addr)[1:-1].replace('\'','')
                                    if 'inverse_match' in dict_search_args(rule_conf, 'source', 'geoip'):
                                        source_addr = 'NOT ' + str(source_addr)
                                if not source_addr:
                                    source_addr = 'any'

            # Get destination
            dest_addr = dict_search_args(rule_conf, 'destination', 'address')
            if not dest_addr:
                dest_addr = dict_search_args(rule_conf, 'destination', 'group', 'address_group')
                if not dest_addr:
                    dest_addr = dict_search_args(rule_conf, 'destination', 'group', 'network_group')
                    if not dest_addr:
                        dest_addr = dict_search_args(rule_conf, 'destination', 'group', 'domain_group')
                        if not dest_addr:
                            dest_addr = dict_search_args(rule_conf, 'destination', 'fqdn')
                            if not dest_addr:
                                dest_addr = dict_search_args(rule_conf, 'destination', 'geoip', 'country_code')
                                if dest_addr:
                                    dest_addr = str(dest_addr)[1:-1].replace('\'','')
                                    if 'inverse_match' in dict_search_args(rule_conf, 'destination', 'geoip'):
                                        dest_addr = 'NOT ' + str(dest_addr)
                                if not dest_addr:
                                    dest_addr = 'any'

            # Get inbound interface
            iiface = dict_search_args(rule_conf, 'inbound_interface', 'name')
            if not iiface:
                iiface = dict_search_args(rule_conf, 'inbound_interface', 'group')
                if not iiface:
                    iiface = 'any'

            # Get outbound interface
            oiface = dict_search_args(rule_conf, 'outbound_interface', 'name')
            if not oiface:
                oiface = dict_search_args(rule_conf, 'outbound_interface', 'group')
                if not oiface:
                    oiface = 'any'

            row = [rule_id, textwrap.fill(rule_conf.get('description') or '', 50)]
            if rule_id in details:
                rule_details = details[rule_id]
                row.append(rule_details.get('packets', 0))
                row.append(rule_details.get('bytes', 0))
            else:
                row.append('0')
                row.append('0')
            row.append(rule_conf['action'])
            row.append(source_addr)
            row.append(dest_addr)
            row.append(iiface)
            row.append(oiface)
            rows.append(row)


    if hook in ['input', 'forward', 'output']:
        row = ['default', '']
        rule_details = details['default-action']
        row.append(rule_details.get('packets', 0))
        row.append(rule_details.get('bytes', 0))
        if 'default_action' in prior_conf:
            row.append(prior_conf['default_action'])
        else:
            row.append('accept')
        row.append('any')
        row.append('any')
        row.append('any')
        row.append('any')
        rows.append(row)

    elif 'default_action' in prior_conf and not single_rule_id:
        row = ['default', '']
        if 'default-action' in details:
            rule_details = details['default-action']
            row.append(rule_details.get('packets', 0))
            row.append(rule_details.get('bytes', 0))
        else:
            row.append('0')
            row.append('0')
        row.append(prior_conf['default_action'])
        row.append('any')   # Source
        row.append('any')   # Dest
        row.append('any')   # inbound-interface
        row.append('any')   # outbound-interface
        rows.append(row)

    if rows:
        if args.detail:
            header = ['Rule', 'Description', 'Packets', 'Bytes', 'Action', 'Source', 'Destination', 'Inbound-Interface', 'Outbound-interface']
            output_firewall_vertical(rows, header)
        else:
            header = ['Rule', 'Packets', 'Bytes', 'Action', 'Source', 'Destination', 'Inbound-Interface', 'Outbound-interface']
            for i in rows:
                rows[rows.index(i)].pop(1)
            print(tabulate.tabulate(rows, header) + '\n')

def show_firewall():
    print('Rulesets Information')

    conf = Config()
    firewall = get_config_node(conf)

    if not firewall:
        return

    for family in ['ipv4', 'ipv6', 'bridge']:
        if 'global_options' in firewall:
            if 'state_policy' in firewall['global_options']:
                output_firewall_state_policy(family)

        if family in firewall:
            for hook, hook_conf in firewall[family].items():
                for prior, prior_conf in firewall[family][hook].items():
                    output_firewall_name(family, hook, prior, prior_conf)

def show_firewall_family(family):
    print(f'Rulesets {family} Information')

    conf = Config()
    firewall = get_config_node(conf)

    if not firewall:
        return

    if 'global_options' in firewall:
        if 'state_policy' in firewall['global_options']:
            output_firewall_state_policy(family)

    if family in firewall:
        for hook, hook_conf in firewall[family].items():
            for prior, prior_conf in firewall[family][hook].items():
                output_firewall_name(family, hook, prior, prior_conf)

def show_firewall_name(family, hook, priority):
    print('Ruleset Information')

    conf = Config()
    firewall = get_config_node(conf, 'firewall', family, hook, priority)
    if firewall:
        output_firewall_name(family, hook, priority, firewall)

def show_firewall_rule(family, hook, priority, rule_id):
    print('Rule Information')

    conf = Config()
    firewall = get_config_node(conf, 'firewall', family, hook, priority)
    if firewall:
        output_firewall_name(family, hook, priority, firewall, rule_id)

def show_firewall_group(name=None):
    conf = Config()
    firewall = get_config_node(conf, node='firewall')

    if 'group' not in firewall:
        return

    nat = get_config_node(conf, node='nat')
    policy = get_config_node(conf, node='policy')

    def find_references(group_type, group_name):
        out = []
        family = []
        if group_type in ['address_group', 'network_group']:
            family = ['ipv4']
        elif group_type == 'ipv6_address_group':
            family = ['ipv6']
            group_type = 'address_group'
        elif group_type == 'ipv6_network_group':
            family = ['ipv6']
            group_type = 'network_group'
        else:
            family = ['ipv4', 'ipv6', 'bridge']

        for item in family:
            # Look references in firewall
            for name_type in ['name', 'ipv6_name', 'forward', 'input', 'output']:
                if item in firewall:
                    if name_type not in firewall[item]:
                        continue
                    for priority, priority_conf in firewall[item][name_type].items():
                        if priority not in firewall[item][name_type]:
                            continue
                        if 'rule' not in priority_conf:
                            continue
                        for rule_id, rule_conf in priority_conf['rule'].items():
                            source_group = dict_search_args(rule_conf, 'source', 'group', group_type)
                            dest_group = dict_search_args(rule_conf, 'destination', 'group', group_type)
                            in_interface = dict_search_args(rule_conf, 'inbound_interface', 'group')
                            out_interface = dict_search_args(rule_conf, 'outbound_interface', 'group')
                            dyn_group_source = dict_search_args(rule_conf, 'add_address_to_group', 'source_address', group_type)
                            dyn_group_dst = dict_search_args(rule_conf, 'add_address_to_group', 'destination_address', group_type)
                            if source_group:
                                if source_group[0] == "!":
                                    source_group = source_group[1:]
                                if group_name == source_group:
                                    out.append(f'{item}-{name_type}-{priority}-{rule_id}')
                            if dest_group:
                                if dest_group[0] == "!":
                                    dest_group = dest_group[1:]
                                if group_name == dest_group:
                                    out.append(f'{item}-{name_type}-{priority}-{rule_id}')
                            if in_interface:
                                if in_interface[0] == "!":
                                    in_interface = in_interface[1:]
                                if group_name == in_interface:
                                    out.append(f'{item}-{name_type}-{priority}-{rule_id}')
                            if out_interface:
                                if out_interface[0] == "!":
                                    out_interface = out_interface[1:]
                                if group_name == out_interface:
                                    out.append(f'{item}-{name_type}-{priority}-{rule_id}')

                            if dyn_group_source:
                                if group_name == dyn_group_source:
                                    out.append(f'{item}-{name_type}-{priority}-{rule_id}')
                            if dyn_group_dst:
                                if group_name == dyn_group_dst:
                                    out.append(f'{item}-{name_type}-{priority}-{rule_id}')


            # Look references in route | route6
            for name_type in ['route', 'route6']:
                if name_type not in policy:
                    continue
                if name_type == 'route' and item == 'ipv6':
                    continue
                elif name_type == 'route6' and item == 'ipv4':
                    continue
                else:
                    for policy_name, policy_conf in policy[name_type].items():
                        if 'rule' not in policy_conf:
                            continue
                        for rule_id, rule_conf in policy_conf['rule'].items():
                            source_group = dict_search_args(rule_conf, 'source', 'group', group_type)
                            dest_group = dict_search_args(rule_conf, 'destination', 'group', group_type)
                            in_interface = dict_search_args(rule_conf, 'inbound_interface', 'group')
                            out_interface = dict_search_args(rule_conf, 'outbound_interface', 'group')
                            if source_group:
                                if source_group[0] == "!":
                                    source_group = source_group[1:]
                                if group_name == source_group:
                                    out.append(f'{name_type}-{policy_name}-{rule_id}')
                            if dest_group:
                                if dest_group[0] == "!":
                                    dest_group = dest_group[1:]
                                if group_name == dest_group:
                                    out.append(f'{name_type}-{policy_name}-{rule_id}')
                            if in_interface:
                                if in_interface[0] == "!":
                                    in_interface = in_interface[1:]
                                if group_name == in_interface:
                                    out.append(f'{name_type}-{policy_name}-{rule_id}')
                            if out_interface:
                                if out_interface[0] == "!":
                                    out_interface = out_interface[1:]
                                if group_name == out_interface:
                                    out.append(f'{name_type}-{policy_name}-{rule_id}')

        ## Look references in nat table
        for direction in ['source', 'destination']:
            if direction in nat:
                if 'rule' not in nat[direction]:
                    continue
                for rule_id, rule_conf in nat[direction]['rule'].items():
                    source_group = dict_search_args(rule_conf, 'source', 'group', group_type)
                    dest_group = dict_search_args(rule_conf, 'destination', 'group', group_type)
                    in_interface = dict_search_args(rule_conf, 'inbound_interface', 'group')
                    out_interface = dict_search_args(rule_conf, 'outbound_interface', 'group')
                    if source_group:
                        if source_group[0] == "!":
                            source_group = source_group[1:]
                        if group_name == source_group:
                            out.append(f'nat-{direction}-{rule_id}')
                    if dest_group:
                        if dest_group[0] == "!":
                            dest_group = dest_group[1:]
                        if group_name == dest_group:
                            out.append(f'nat-{direction}-{rule_id}')
                    if in_interface:
                        if in_interface[0] == "!":
                            in_interface = in_interface[1:]
                        if group_name == in_interface:
                            out.append(f'nat-{direction}-{rule_id}')
                    if out_interface:
                        if out_interface[0] == "!":
                            out_interface = out_interface[1:]
                        if group_name == out_interface:
                            out.append(f'nat-{direction}-{rule_id}')

        return out

    rows = []
    header_tail = []

    for group_type, group_type_conf in firewall['group'].items():
        ##
        if group_type != 'dynamic_group':

            for group_name, group_conf in group_type_conf.items():
                if name and name != group_name:
                    continue

                references = find_references(group_type, group_name)
                row = [group_name,  textwrap.fill(group_conf.get('description') or '', 50), group_type, '\n'.join(references) or 'N/D']
                if 'address' in group_conf:
                    row.append("\n".join(sorted(group_conf['address'])))
                elif 'network' in group_conf:
                    row.append("\n".join(sorted(group_conf['network'], key=ipaddress.ip_network)))
                elif 'mac_address' in group_conf:
                    row.append("\n".join(sorted(group_conf['mac_address'])))
                elif 'port' in group_conf:
                    row.append("\n".join(sorted(group_conf['port'])))
                elif 'interface' in group_conf:
                    row.append("\n".join(sorted(group_conf['interface'])))
                else:
                    row.append('N/D')
                rows.append(row)

        else:
            if not args.detail:
                header_tail = ['Timeout', 'Expires']

            for dynamic_type in ['address_group', 'ipv6_address_group']:
                family = 'ipv4' if dynamic_type == 'address_group' else 'ipv6'
                prefix = 'DA_' if dynamic_type == 'address_group' else 'DA6_'
                if dynamic_type in firewall['group']['dynamic_group']:
                    for dynamic_name, dynamic_conf in firewall['group']['dynamic_group'][dynamic_type].items():
                        references = find_references(dynamic_type, dynamic_name)
                        row = [dynamic_name, textwrap.fill(dynamic_conf.get('description') or '', 50), dynamic_type + '(dynamic)', '\n'.join(references) or 'N/D']

                        members = get_nftables_group_members(family, 'vyos_filter', f'{prefix}{dynamic_name}')

                        if not members:
                            if args.detail:
                                row.append('N/D')
                            else:
                                row += ["N/D"] * 3
                            rows.append(row)
                            continue

                        for idx, member in enumerate(members):
                            if isinstance(member, str):
                                # Only member, and no timeout:
                                val = member
                                timeout = "N/D"
                                expires = "N/D"
                            else:
                                val = member.get('val', 'N/D')
                                timeout = str(member.get('timeout', 'N/D'))
                                expires = str(member.get('expires', 'N/D'))

                            if args.detail:
                                row.append(f'{val} (timeout: {timeout}, expires: {expires})')
                                continue

                            if idx > 0:
                                row = [""] * 4

                            row += [val, timeout, expires]
                            rows.append(row)

                        if args.detail:
                            header_tail += [""] * (len(members) - 1)
                            rows.append(row)

    if rows:
        print('Firewall Groups\n')
        if args.detail:
            header = ['Name', 'Description', 'Type', 'References', 'Members'] + header_tail
            output_firewall_vertical(rows, header, adjust=False)
        else:
            header = ['Name', 'Type', 'References', 'Members'] + header_tail
            for i in rows:
                rows[rows.index(i)].pop(1)
            print(tabulate.tabulate(rows, header))

def show_summary():
    print('Ruleset Summary')

    conf = Config()
    firewall = get_config_node(conf)

    if not firewall:
        return

    header = ['Ruleset Hook', 'Ruleset Priority', 'Description', 'References']
    v4_out = []
    v6_out = []
    br_out = []

    if 'ipv4' in firewall:
        for hook, hook_conf in firewall['ipv4'].items():
            for prior, prior_conf in firewall['ipv4'][hook].items():
                description = prior_conf.get('description', '')
                v4_out.append([hook, prior, description])

    if 'ipv6' in firewall:
        for hook, hook_conf in firewall['ipv6'].items():
            for prior, prior_conf in firewall['ipv6'][hook].items():
                description = prior_conf.get('description', '')
                v6_out.append([hook, prior, description])

    if 'bridge' in firewall:
        for hook, hook_conf in firewall['bridge'].items():
            for prior, prior_conf in firewall['bridge'][hook].items():
                description = prior_conf.get('description', '')
                br_out.append([hook, prior, description])

    if v6_out:
        print('\nIPv6 Ruleset:\n')
        print(tabulate.tabulate(v6_out, header) + '\n')

    if v4_out:
        print('\nIPv4 Ruleset:\n')
        print(tabulate.tabulate(v4_out, header) + '\n')

    if br_out:
        print('\nBridge Ruleset:\n')
        print(tabulate.tabulate(br_out, header) + '\n')

    show_firewall_group()

def show_statistics():
    print('Rulesets Statistics')

    conf = Config()
    firewall = get_config_node(conf)

    if not firewall:
        return

    for family in ['ipv4', 'ipv6', 'bridge']:
        if 'global_options' in firewall:
            if 'state_policy' in firewall['global_options']:
                output_firewall_state_policy(family)

        if family in firewall:
            for hook, hook_conf in firewall[family].items():
                for prior, prior_conf in firewall[family][hook].items():
                    output_firewall_name_statistics(family, hook,prior, prior_conf)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--action', help='Action', required=False)
    parser.add_argument('--name', help='Firewall name', required=False, action='store', nargs='?', default='')
    parser.add_argument('--family', help='IP family', required=False, action='store', nargs='?', default='')
    parser.add_argument('--hook', help='Firewall hook', required=False, action='store', nargs='?', default='')
    parser.add_argument('--priority', help='Firewall priority', required=False, action='store', nargs='?', default='')
    parser.add_argument('--rule', help='Firewall Rule ID', required=False)
    parser.add_argument('--ipv6', help='IPv6 toggle', action='store_true')
    parser.add_argument('--detail', help='Firewall view select', required=False)

    args = parser.parse_args()

    if args.action == 'show':
        if not args.rule:
            show_firewall_name(args.family, args.hook, args.priority)
        else:
            show_firewall_rule(args.family, args.hook, args.priority, args.rule)
    elif args.action == 'show_all':
        show_firewall()
    elif args.action == 'show_family':
        show_firewall_family(args.family)
    elif args.action == 'show_group':
        show_firewall_group(args.name)
    elif args.action == 'show_statistics':
        show_statistics()
    elif args.action == 'show_summary':
        show_summary()
