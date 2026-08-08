# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

import re

from socket import AF_INET
from socket import AF_INET6
from socket import getaddrinfo

from vyos.template import is_ipv4
from vyos.utils.dict import dict_search_args
from vyos.utils.dict import dict_search_recursive
from vyos.utils.process import cmdl
from vyos.utils.network import get_vrf_tableid
from vyos.defaults import rt_global_table
from vyos.defaults import rt_global_vrf

# Conntrack
def conntrack_required(conf):
    required_nodes = ['nat', 'nat66', 'load-balancing wan']

    for path in required_nodes:
        if conf.exists(path):
            return True

    firewall = conf.get_config_dict(['firewall'], key_mangling=('-', '_'),
                                    no_tag_node_value_mangle=True, get_first_key=True)

    if dict_search_args(firewall, 'global_options', 'state_policy'):
        return True

    for rules, path in dict_search_recursive(firewall, 'rule'):
        if any(('state' in rule_conf or 'connection_status' in rule_conf or 'offload_target' in rule_conf) for rule_conf in rules.values()):
            return True

    return False

# Domain Resolver

def fqdn_config_parse(config, node):
    config['ip_fqdn'] = {}
    config['ip6_fqdn'] = {}

    for domain, path in dict_search_recursive(config, 'fqdn'):
        if node != 'nat':
            hook_name = path[1]
            priority = path[2]

            rule = path[4]
            suffix = path[5][0]
            set_name = f'{hook_name}_{priority}_{rule}_{suffix}'

            if (path[0] == 'ipv4') and (path[1] == 'forward' or path[1] == 'input' or path[1] == 'output' or path[1] == 'name'):
                config['ip_fqdn'][set_name] = domain
            elif (path[0] == 'ipv6') and (path[1] == 'forward' or path[1] == 'input' or path[1] == 'output' or path[1] == 'name'):
                if path[1] == 'name':
                    set_name = f'name6_{priority}_{rule}_{suffix}'
                config['ip6_fqdn'][set_name] = domain
        else:
            # Parse FQDN for NAT
            nat_direction = path[0]
            nat_rule = path[2]
            suffix = path[3][0]
            set_name = f'{nat_direction}_{nat_rule}_{suffix}'
            config['ip_fqdn'][set_name] = domain

def fqdn_resolve(fqdn, ipv6=False):
    try:
        res = getaddrinfo(fqdn, None, AF_INET6 if ipv6 else AF_INET)
        return set(item[4][0] for item in res)
    except:
        return None

def find_nftables_rule(table, chain, rule_matches=[]):
    # Find rule in table/chain that matches all criteria and return the handle
    results = cmdl(['nft', '--handle', 'list', 'chain', table, chain], sudo=True).split("\n")
    for line in results:
        if all(rule_match in line for rule_match in rule_matches):
            handle_search = re.search('handle (\d+)', line)
            if handle_search:
                return handle_search[1]
    return None

def remove_nftables_rule(table, chain, handle):
    cmdl(['nft', 'delete', 'rule', table, chain, 'handle', str(handle)], sudo=True)

# Flow-group (nftables concatenations)
#
# Flow-groups map to concatenated nftables sets so related packet fields are
# matched together (e.g. source address . destination port) rather than as
# independent criteria.
#
# nftables limits concatenated set keys to NFT_DATA_VALUE_MAXLEN (64 bytes).
# See: https://git.netfilter.org/nftables/tree/include/linux/netfilter/nf_tables.h
#      (#define NFT_DATA_VALUE_MAXLEN 64)
NFT_CONCAT_MAX_KEY_SIZE = 64

# ICMP type numbers -> symbolic names from `nft describe icmp_type`
ICMP_TYPE_NUM_TO_NAME = {
    0: 'echo-reply',
    3: 'destination-unreachable',
    4: 'source-quench',
    5: 'redirect',
    8: 'echo-request',
    9: 'router-advertisement',
    10: 'router-solicitation',
    11: 'time-exceeded',
    12: 'parameter-problem',
    13: 'timestamp-request',
    14: 'timestamp-reply',
    15: 'info-request',
    16: 'info-reply',
    17: 'address-mask-request',
    18: 'address-mask-reply',
}

# ICMPv6 type numbers -> symbolic names from `nft describe icmpv6_type`
# (132 has two aliases; prefer mld-listener-reduction to match existing CLI)
ICMPV6_TYPE_NUM_TO_NAME = {
    1: 'destination-unreachable',
    2: 'packet-too-big',
    3: 'time-exceeded',
    4: 'parameter-problem',
    128: 'echo-request',
    129: 'echo-reply',
    130: 'mld-listener-query',
    131: 'mld-listener-report',
    132: 'mld-listener-reduction',
    133: 'nd-router-solicit',
    134: 'nd-router-advert',
    135: 'nd-neighbor-solicit',
    136: 'nd-neighbor-advert',
    137: 'nd-redirect',
    138: 'router-renumbering',
    141: 'ind-neighbor-solicit',
    142: 'ind-neighbor-advert',
    143: 'mld2-listener-report',
}

# Valid ICMP codes keyed by type name (IANA / RFC792+)
ICMP_CODE_BY_TYPE = {
    'echo-reply': {0},
    'destination-unreachable': set(range(0, 16)),
    'source-quench': {0},
    'redirect': {0, 1, 2, 3},
    'echo-request': {0},
    'router-advertisement': {0},
    'router-solicitation': {0},
    'time-exceeded': {0, 1},
    'parameter-problem': {0, 1, 2},
    'timestamp-request': {0},
    'timestamp-reply': {0},
    'info-request': {0},
    'info-reply': {0},
    'address-mask-request': {0},
    'address-mask-reply': {0},
}

# Valid ICMPv6 codes keyed by type name (IANA / RFC4443+)
ICMPV6_CODE_BY_TYPE = {
    'destination-unreachable': set(range(0, 10)),
    'packet-too-big': {0},
    'time-exceeded': {0, 1},
    'parameter-problem': set(range(0, 11)),
    'echo-request': {0},
    'echo-reply': {0},
    'mld-listener-query': {0},
    'mld-listener-report': {0},
    'mld-listener-done': {0},
    'mld-listener-reduction': {0},
    'nd-router-solicit': {0},
    'nd-router-advert': {0},
    'nd-neighbor-solicit': {0},
    'nd-neighbor-advert': {0},
    'nd-redirect': {0},
    'router-renumbering': {0, 1, 255},
    'ind-neighbor-solicit': {0},
    'ind-neighbor-advert': {0},
    'mld2-listener-report': {0},
}

def icmp_type_to_name(value, family='ipv4'):
    """Resolve an ICMP/ICMPv6 type number or name to its symbolic name.

    Numeric values are looked up in the ``nft describe`` type map. Symbolic
    names are accepted as-is when they appear in the code-by-type map.

    Args:
        value: Type as configured (e.g. ``8`` or ``echo-request``).
        family: ``ipv4`` for ICMP, ``ipv6`` for ICMPv6.

    Returns:
        The symbolic type name, or None if ``value`` is not a known type.
    """
    type_map = ICMP_TYPE_NUM_TO_NAME if family == 'ipv4' else ICMPV6_TYPE_NUM_TO_NAME
    code_map = ICMP_CODE_BY_TYPE if family == 'ipv4' else ICMPV6_CODE_BY_TYPE
    value = str(value)

    if value.isdigit():
        return type_map.get(int(value))

    if value in code_map:
        return value

    return None

def icmp_codes_for_type(type_name, family='ipv4'):
    """Return the set of valid ICMP/ICMPv6 codes for a type name, or None."""
    code_map = ICMP_CODE_BY_TYPE if family == 'ipv4' else ICMPV6_CODE_BY_TYPE
    return code_map.get(type_name)

# Maps CLI flow-group parameters to nftables match expressions and key sizes.
# ``expr`` is used in typeof / rule matches; ``size`` feeds the 64-byte key check;
# ``quote`` marks values that must be quoted in set elements (e.g. ifnames).
FLOW_GROUP_PARAMS = {
    'ipv4': {
        'inbound-interface': {
            'expr': 'iifname',
            'size': 16,
            'quote': True,
        },
        'outbound-interface': {
            'expr': 'oifname',
            'size': 16,
            'quote': True,
        },
        'ipv4-source-address': {
            'expr': 'ip saddr',
            'size': 4,
        },
        'ipv4-destination-address': {
            'expr': 'ip daddr',
            'size': 4,
        },
        'source-port': {
            'expr': 'th sport',
            'size': 2,
        },
        'destination-port': {
            'expr': 'th dport',
            'size': 2,
        },
        'protocol': {
            'expr': 'meta l4proto',
            'size': 1,
        },
        'mark': {
            'expr': 'meta mark',
            'size': 4,
        },
        'connection-mark': {
            'expr': 'ct mark',
            'size': 4,
        },
        'dscp': {
            'expr': 'ip dscp',
            'size': 1,
        },
        'icmp-type': {
            'expr': 'icmp type',
            'size': 1,
        },
        'icmp-code': {
            'expr': 'icmp code',
            'size': 1,
        },
    },
    'ipv6': {
        'inbound-interface': {
            'expr': 'iifname',
            'size': 16,
            'quote': True,
        },
        'outbound-interface': {
            'expr': 'oifname',
            'size': 16,
            'quote': True,
        },
        'ipv6-source-address': {
            'expr': 'ip6 saddr',
            'size': 16,
        },
        'ipv6-destination-address': {
            'expr': 'ip6 daddr',
            'size': 16,
        },
        'source-port': {
            'expr': 'th sport',
            'size': 2,
        },
        'destination-port': {
            'expr': 'th dport',
            'size': 2,
        },
        'protocol': {
            'expr': 'meta l4proto',
            'size': 1,
        },
        'mark': {
            'expr': 'meta mark',
            'size': 4,
        },
        'connection-mark': {
            'expr': 'ct mark',
            'size': 4,
        },
        'dscp': {
            'expr': 'ip6 dscp',
            'size': 1,
        },
        'icmpv6-type': {
            'expr': 'icmpv6 type',
            'size': 1,
        },
        'icmpv6-code': {
            'expr': 'icmpv6 code',
            'size': 1,
        },
    },
}

def flow_group_parameters(group_conf):
    """Return the flow-group parameter list from config.

    A multi leaf with a single value may be stored as a bare string rather than
    a list; normalize so callers always receive a list.
    """
    parameters = group_conf.get('parameter', [])
    if isinstance(parameters, str):
        return [parameters]
    return list(parameters) if parameters else []

def _rule_has_path(rule_conf, path):
    """Return True if ``path`` exists under ``rule_conf`` (via dict_search_args)."""
    return dict_search_args(rule_conf, *path) is not None

def flow_group_rule_conflicts(rule_conf, parameters):
    """Find rule options that duplicate a referenced flow-group's parameters.

    A rule must not also configure criteria already matched by the flow-group
    (e.g. ``source address`` when the group includes ``ipv4-source-address``).

    Args:
        rule_conf: Firewall rule config dict.
        parameters: Flow-group parameter names (CLI form with hyphens).

    Returns:
        List of ``(parameter, rule_option)`` pairs for each conflict found.
    """
    address_sides = {
        'source': [
            (['source', 'address'], 'source address'),
            (['source', 'fqdn'], 'source fqdn'),
            (['source', 'geoip'], 'source geoip'),
            (['source', 'group', 'address_group'], 'source group address-group'),
            (['source', 'group', 'network_group'], 'source group network-group'),
            (['source', 'group', 'domain_group'], 'source group domain-group'),
            (['source', 'group', 'remote_group'], 'source group remote-group'),
            (['source', 'group', 'dynamic_address_group'], 'source group dynamic-address-group'),
        ],
        'destination': [
            (['destination', 'address'], 'destination address'),
            (['destination', 'fqdn'], 'destination fqdn'),
            (['destination', 'geoip'], 'destination geoip'),
            (['destination', 'group', 'address_group'], 'destination group address-group'),
            (['destination', 'group', 'network_group'], 'destination group network-group'),
            (['destination', 'group', 'domain_group'], 'destination group domain-group'),
            (['destination', 'group', 'remote_group'], 'destination group remote-group'),
            (['destination', 'group', 'dynamic_address_group'], 'destination group dynamic-address-group'),
        ],
    }

    # Map each flow-group parameter to rule config paths that conflict with it
    checks = {
        'inbound-interface': [
            (['inbound_interface'], 'inbound-interface'),
        ],
        'outbound-interface': [
            (['outbound_interface'], 'outbound-interface'),
        ],
        'ipv4-source-address': address_sides['source'],
        'ipv6-source-address': address_sides['source'],
        'ipv4-destination-address': address_sides['destination'],
        'ipv6-destination-address': address_sides['destination'],
        'source-port': [
            (['source', 'port'], 'source port'),
            (['source', 'group', 'port_group'], 'source group port-group'),
        ],
        'destination-port': [
            (['destination', 'port'], 'destination port'),
            (['destination', 'group', 'port_group'], 'destination group port-group'),
        ],
        'protocol': [
            (['protocol'], 'protocol'),
        ],
        'mark': [
            (['mark'], 'mark'),
        ],
        'connection-mark': [
            (['connection_mark'], 'connection-mark'),
        ],
        'dscp': [
            (['dscp'], 'dscp'),
            (['dscp_exclude'], 'dscp-exclude'),
        ],
        'icmp-type': [
            (['icmp'], 'icmp'),
        ],
        'icmp-code': [
            (['icmp'], 'icmp'),
        ],
        'icmpv6-type': [
            (['icmpv6'], 'icmpv6'),
        ],
        'icmpv6-code': [
            (['icmpv6'], 'icmpv6'),
        ],
    }

    conflicts = []
    seen = set()
    for param in parameters:
        for path, option in checks.get(param, []):
            if _rule_has_path(rule_conf, path):
                key = (param, option)
                if key not in seen:
                    seen.add(key)
                    conflicts.append(key)
    return conflicts

def flow_group_key_size(parameters, family):
    """Calculate the concatenated nftables key size for a parameter list.

    Args:
        parameters: Flow-group parameter names in CLI order.
        family: ``ipv4`` or ``ipv6``.

    Returns:
        ``(total_bytes, [(param, size_bytes), ...])`` for error reporting.
    """
    param_meta = FLOW_GROUP_PARAMS[family]
    sizes = []
    total = 0
    for param in parameters:
        size = param_meta[param]['size']
        sizes.append((param, size))
        total += size
    return total, sizes

def flow_group_typeof(parameters, family):
    """Build an nftables ``typeof`` / match expression for the parameter list.

    Example: ``['ipv4-source-address', 'destination-port']`` →
    ``ip saddr . th dport``.
    """
    param_meta = FLOW_GROUP_PARAMS[family]
    return ' . '.join(param_meta[p]['expr'] for p in parameters)

# nftables limits user comments to NFT_USERDATA_MAXLEN (128 bytes).
# CLI descriptions allow up to 255 characters; truncate before emitting.
NFT_COMMENT_MAX_LEN = 128

def flow_group_nft_comment(text):
    """Format a CLI description as an nftables ``comment "..."`` clause.

    Descriptions are truncated to ``NFT_COMMENT_MAX_LEN`` to match the
    nftables userdata limit, then quotes/backslashes are escaped.
    """
    truncated = str(text)[:NFT_COMMENT_MAX_LEN]
    escaped = truncated.replace('\\', '\\\\').replace('"', '\\"')
    return f'comment "{escaped}"'

def flow_group_format_element(match_conf, parameters, family):
    """Format one match as an nftables concatenated set element.

    Values follow parameter order. ICMP types are rendered as symbolic names
    when possible; interface names are quoted. Match ``description`` becomes a
    per-element comment when present.
    """
    param_meta = FLOW_GROUP_PARAMS[family]
    parts = []
    for param in parameters:
        key = param.replace('-', '_')
        value = match_conf[key]
        if param in ('icmp-type', 'icmpv6-type'):
            # Prefer symbolic names in nftables output
            type_name = icmp_type_to_name(value, family)
            if type_name:
                value = type_name
        if param_meta[param].get('quote'):
            value = f'"{value}"'
        parts.append(str(value))
    element = ' . '.join(parts)
    if 'description' in match_conf:
        element = f'{element} {flow_group_nft_comment(match_conf["description"])}'
    return element

def flow_group_elements(group_conf, family):
    """Build the comma-separated elements string for a flow-group set.

    Disabled matches are omitted. Returns an empty string when there are no
    enabled matches.
    """
    parameters = flow_group_parameters(group_conf)
    matches = group_conf.get('match', {})
    if not parameters or not matches:
        return ''
    elements = []
    for match_conf in matches.values():
        if 'disable' in match_conf:
            continue
        elements.append(flow_group_format_element(match_conf, parameters, family))
    return ', '.join(elements)

# Functions below used by template generation

def nft_action(vyos_action):
    if vyos_action == 'accept':
        return 'return'
    return vyos_action

def parse_rule(rule_conf, hook, fw_name, rule_id, ip_name, flow_groups=None):
    output = []

    if ip_name == 'ip6':
        def_suffix = '6'
        family = 'ipv6'
    else:
        def_suffix = ''
        family = 'bri' if ip_name == 'bri' else 'ipv4'

    if 'flow_group' in rule_conf and flow_groups:
        # Attach the referenced flow-group config for this rule
        group_name = rule_conf['flow_group']
        if group_name[0] == '!':
            group_name = group_name[1:]
        if group_name in flow_groups:
            rule_conf['_flow_group'] = flow_groups[group_name]

    if 'state' in rule_conf and rule_conf['state']:
        states = ",".join([s for s in rule_conf['state']])

        if states:
            output.append(f'ct state {{{states}}}')

    if 'conntrack_helper' in rule_conf:
        helper_map = {'h323': ['RAS', 'Q.931'], 'nfs': ['rpc'], 'sqlnet': ['tns']}
        helper_out = []

        for helper in rule_conf['conntrack_helper']:
            if helper in helper_map:
                helper_out.extend(helper_map[helper])
            else:
                helper_out.append(helper)

        if helper_out:
            helper_str = ','.join(f'"{s}"' for s in helper_out)
            output.append(f'ct helper {{{helper_str}}}')

    if 'connection_status' in rule_conf and rule_conf['connection_status']:
        status = rule_conf['connection_status']
        if status['nat'] == 'destination':
            nat_status = 'dnat'
            output.append(f'ct status {nat_status}')
        if status['nat'] == 'source':
            nat_status = 'snat'
            output.append(f'ct status {nat_status}')

    if 'protocol' in rule_conf and rule_conf['protocol'] != 'all':
        proto = rule_conf['protocol']
        operator = ''
        if proto[0] == '!':
            operator = '!='
            proto = proto[1:]
        if proto == 'tcp_udp':
            proto = '{tcp, udp}'
        output.append(f'meta l4proto {operator} {proto}')

    if '_flow_group' in rule_conf:
        group_name = rule_conf['flow_group']
        operator = ''
        if group_name[0] == '!':
            operator = '!='
            group_name = group_name[1:]
        parameters = flow_group_parameters(rule_conf['_flow_group'])
        expr = flow_group_typeof(parameters, family)
        set_name = f'FG{"6" if family == "ipv6" else "4"}_{group_name}'
        if operator:
            output.append(f'{expr} {operator} @{set_name}')
        else:
            output.append(f'{expr} @{set_name}')

    if 'ethernet_type' in rule_conf:
        ether_type_mapping = {
            '802.1q': '8021q',
            '802.1ad': '8021ad',
            'ipv6': 'ip6',
            'ipv4': 'ip',
            'arp': 'arp'
        }
        ether_type = rule_conf['ethernet_type']
        operator = '!=' if ether_type.startswith('!') else ''
        ether_type = ether_type.lstrip('!')
        ether_type = ether_type_mapping.get(ether_type, ether_type)
        output.append(f'ether type {operator} {ether_type}')

    for side in ['destination', 'source']:
        if side in rule_conf:
            prefix = side[0]
            side_conf = rule_conf[side]
            address_mask = side_conf.get('address_mask', None)

            if 'address' in side_conf:
                suffix = side_conf['address']
                operator = ''
                exclude = suffix[0] == '!'
                if exclude:
                    operator = '!= '
                    suffix = suffix[1:]
                if address_mask:
                    operator = '!=' if exclude else '=='
                    operator = f'& {address_mask} {operator} '

                if suffix.find('-') != -1:
                    # Range
                    start, end = suffix.split('-')
                    if is_ipv4(start):
                        output.append(f'ip {prefix}addr {operator}{suffix}')
                    else:
                        output.append(f'ip6 {prefix}addr {operator}{suffix}')
                else:
                    if is_ipv4(suffix):
                        output.append(f'ip {prefix}addr {operator}{suffix}')
                    else:
                        output.append(f'ip6 {prefix}addr {operator}{suffix}')

            if 'fqdn' in side_conf:
                fqdn = side_conf['fqdn']
                hook_name = ''
                operator = ''
                if fqdn[0] == '!':
                    operator = '!='
                if hook == 'FWD':
                    hook_name = 'forward'
                if hook == 'INP':
                    hook_name = 'input'
                if hook == 'OUT':
                    hook_name = 'output'
                if hook == 'PRE':
                    hook_name = 'prerouting'
                if hook == 'NAM':
                    hook_name = f'name{def_suffix}'
                output.append(f'{ip_name} {prefix}addr {operator} @FQDN_{hook_name}_{fw_name}_{rule_id}_{prefix}')

            country_code = dict_search_args(side_conf, 'geoip', 'country_code')
            asn = dict_search_args(side_conf, 'geoip', 'asn')
            if country_code or asn:
                geoip_prefix = 'CC' if country_code else 'ASN'
                operator = ''
                hook_name = ''
                if dict_search_args(side_conf, 'geoip', 'inverse_match') != None:
                    operator = '!='
                if hook == 'FWD':
                    hook_name = 'forward'
                if hook == 'INP':
                    hook_name = 'input'
                if hook == 'OUT':
                    hook_name = 'output'
                if hook == 'PRE':
                    hook_name = 'prerouting'
                if hook == 'NAM':
                    hook_name = f'name'
                # for policy
                if hook == 'route' or hook == 'route6':
                    hook_name = hook
                output.append(f'{ip_name} {prefix}addr {operator} @GEOIP_{geoip_prefix}{def_suffix}_{hook_name}_{fw_name}_{rule_id}')

            if 'mac_address' in side_conf:
                suffix = side_conf["mac_address"]
                if suffix[0] == '!':
                    suffix = f'!= {suffix[1:]}'
                output.append(f'ether {prefix}addr {suffix}')

            if 'port' in side_conf:
                proto = rule_conf['protocol']
                port = side_conf['port'].split(',')

                ports = []
                negated_ports = []

                for p in port:
                    if p[0] == '!':
                        negated_ports.append(p[1:])
                    else:
                        ports.append(p)

                if proto == 'tcp_udp':
                    proto = 'th'

                if ports:
                    ports_str = ','.join(ports)
                    output.append(f'{proto} {prefix}port {{{ports_str}}}')

                if negated_ports:
                    negated_ports_str = ','.join(negated_ports)
                    output.append(f'{proto} {prefix}port != {{{negated_ports_str}}}')

            if 'group' in side_conf:
                group = side_conf['group']
                for ipvx_address_group in ['address_group', 'ipv4_address_group', 'ipv6_address_group']:
                    if ipvx_address_group in group:
                        group_name = group[ipvx_address_group]
                        operator = ''
                        exclude = group_name[0] == "!"
                        if exclude:
                            operator = '!='
                            group_name = group_name[1:]
                        if address_mask:
                            operator = '!=' if exclude else '=='
                            operator = f'& {address_mask} {operator}'
                        # for bridge, change ip_name
                        if ip_name == 'bri':
                            ip_name = 'ip' if ipvx_address_group == 'ipv4_address_group' else 'ip6'
                            def_suffix = '6' if ipvx_address_group == 'ipv6_address_group' else ''
                        output.append(f'{ip_name} {prefix}addr {operator} @A{def_suffix}_{group_name}')
                for ipvx_network_group in ['network_group', 'ipv4_network_group', 'ipv6_network_group']:
                    if ipvx_network_group in group:
                        group_name = group[ipvx_network_group]
                        operator = ''
                        if group_name[0] == "!":
                            operator = '!='
                            group_name = group_name[1:]
                        # for bridge, change ip_name
                        if ip_name == 'bri':
                            ip_name = 'ip' if ipvx_network_group == 'ipv4_network_group' else 'ip6'
                            def_suffix = '6' if ipvx_network_group == 'ipv6_network_group' else ''
                        output.append(f'{ip_name} {prefix}addr {operator} @N{def_suffix}_{group_name}')
                if 'dynamic_address_group' in group:
                    group_name = group['dynamic_address_group']
                    operator = ''
                    if group_name[0] == "!":
                        operator = '!='
                        group_name = group_name[1:]
                    output.append(f'{ip_name} {prefix}addr {operator} @DA{def_suffix}_{group_name}')
                # Generate firewall group domain-group
                elif 'domain_group' in group:
                    group_name = group['domain_group']
                    operator = ''
                    if group_name[0] == '!':
                        operator = '!='
                        group_name = group_name[1:]
                    output.append(f'{ip_name} {prefix}addr {operator} @D_{group_name}')
                elif 'remote_group' in group:
                    group_name = group['remote_group']
                    operator = ''
                    if group_name[0] == '!':
                        operator = '!='
                        group_name = group_name[1:]
                    if ip_name == 'ip':
                        output.append(f'{ip_name} {prefix}addr {operator} @R_{group_name}')
                    elif ip_name == 'ip6':
                        output.append(f'{ip_name} {prefix}addr {operator} @R6_{group_name}')
                if 'mac_group' in group:
                    group_name = group['mac_group']
                    operator = ''
                    if group_name[0] == '!':
                        operator = '!='
                        group_name = group_name[1:]
                    output.append(f'ether {prefix}addr {operator} @M_{group_name}')
                if 'port_group' in group:
                    proto = rule_conf['protocol']
                    group_name = group['port_group']

                    if proto == 'tcp_udp':
                        proto = 'th'

                    operator = ''
                    if group_name[0] == '!':
                        operator = '!='
                        group_name = group_name[1:]

                    output.append(f'{proto} {prefix}port {operator} @P_{group_name}')

    if dict_search_args(rule_conf, 'action') == 'synproxy':
        output.append('ct state invalid,untracked')

    if 'hop_limit' in rule_conf:
        operators = {'eq': '==', 'gt': '>', 'lt': '<'}
        for op, operator in operators.items():
            if op in rule_conf['hop_limit']:
                value = rule_conf['hop_limit'][op]
                output.append(f'ip6 hoplimit {operator} {value}')

    if 'inbound_interface' in rule_conf:
        operator = ''
        if 'name' in rule_conf['inbound_interface']:
            iiface = rule_conf['inbound_interface']['name']
            if iiface[0] == '!':
                operator = '!='
                iiface = iiface[1:]
            output.append(f'iifname {operator} {{"{iiface}"}}')
        elif 'group' in rule_conf['inbound_interface']:
            iiface = rule_conf['inbound_interface']['group']
            if iiface[0] == '!':
                operator = '!='
                iiface = iiface[1:]
            output.append(f'iifname {operator} @I_{iiface}')

    if 'outbound_interface' in rule_conf:
        operator = ''
        if 'name' in rule_conf['outbound_interface']:
            oiface = rule_conf['outbound_interface']['name']
            if oiface[0] == '!':
                operator = '!='
                oiface = oiface[1:]
            output.append(f'oifname {operator} {{"{oiface}"}}')
        elif 'group' in rule_conf['outbound_interface']:
            oiface = rule_conf['outbound_interface']['group']
            if oiface[0] == '!':
                operator = '!='
                oiface = oiface[1:]
            output.append(f'oifname {operator} @I_{oiface}')

    if 'ttl' in rule_conf:
        operators = {'eq': '==', 'gt': '>', 'lt': '<'}
        for op, operator in operators.items():
            if op in rule_conf['ttl']:
                value = rule_conf['ttl'][op]
                output.append(f'ip ttl {operator} {value}')

    for icmp in ['icmp', 'icmpv6']:
        if icmp in rule_conf:
            if 'type_name' in rule_conf[icmp]:
                output.append(icmp + ' type ' + rule_conf[icmp]['type_name'])
            else:
                if 'code' in rule_conf[icmp]:
                    output.append(icmp + ' code ' + rule_conf[icmp]['code'])
                if 'type' in rule_conf[icmp]:
                    output.append(icmp + ' type ' + rule_conf[icmp]['type'])


    if 'packet_length' in rule_conf:
        lengths_str = ','.join(rule_conf['packet_length'])
        output.append(f'ip{def_suffix} length {{{lengths_str}}}')

    if 'packet_length_exclude' in rule_conf:
        negated_lengths_str = ','.join(rule_conf['packet_length_exclude'])
        output.append(f'ip{def_suffix} length != {{{negated_lengths_str}}}')

    if 'packet_type' in rule_conf:
        output.append(f'pkttype ' + rule_conf['packet_type'])

    if 'dscp' in rule_conf:
        dscp_str = ','.join(rule_conf['dscp'])
        output.append(f'ip{def_suffix} dscp {{{dscp_str}}}')

    if 'dscp_exclude' in rule_conf:
        negated_dscp_str = ','.join(rule_conf['dscp_exclude'])
        output.append(f'ip{def_suffix} dscp != {{{negated_dscp_str}}}')

    if 'ipsec' in rule_conf:
        if 'match_ipsec_in' in rule_conf['ipsec']:
            output.append('meta ipsec == 1')
        if 'match_none_in' in rule_conf['ipsec']:
            output.append('meta ipsec == 0')
        if 'match_ipsec_out' in rule_conf['ipsec']:
            output.append('rt ipsec exists')
        if 'match_none_out' in rule_conf['ipsec']:
            output.append('rt ipsec missing')

    if 'fragment' in rule_conf:
        # Checking for fragmentation after priority -400 is not possible,
        # so we use a priority -450 hook to set a mark
        if 'match_frag' in rule_conf['fragment']:
            output.append('meta mark 0xffff1')
        if 'match_non_frag' in rule_conf['fragment']:
            output.append('meta mark != 0xffff1')

    if 'limit' in rule_conf:
        if 'rate' in rule_conf['limit']:
            output.append(f'limit rate {rule_conf["limit"]["rate"]}')
            if 'burst' in rule_conf['limit']:
                output.append(f'burst {rule_conf["limit"]["burst"]} packets')

    if 'recent' in rule_conf:
        count = rule_conf['recent']['count']
        time = rule_conf['recent']['time']
        output.append(f'add @RECENT{def_suffix}_{hook}_{fw_name}_{rule_id} {{ {ip_name} saddr limit rate over {count}/{time} burst {count} packets }}')

    if 'gre' in rule_conf:
        gre_key = dict_search_args(rule_conf, 'gre', 'key')

        gre_flags = dict_search_args(rule_conf, 'gre', 'flags')
        output.append(parse_gre_flags(gre_flags or {}, force_keyed=gre_key is not None))

        gre_proto_alias_map = {
            '802.1q': '8021q',
            '802.1ad': '8021ad',
            'gretap': '0x6558',
        }

        gre_proto = dict_search_args(rule_conf, 'gre', 'inner_proto')
        if gre_proto is not None:
            gre_proto = gre_proto_alias_map.get(gre_proto, gre_proto)
            output.append(f'gre protocol {gre_proto}')

        gre_ver = dict_search_args(rule_conf, 'gre', 'version')
        if gre_ver == 'gre':
            output.append('gre version 0')
        elif gre_ver == 'pptp':
            output.append('gre version 1')

        if gre_key:
            # The offset of the key within the packet shifts depending on the C-flag.
            # nftables cannot handle complex enough expressions to match multiple
            # offsets based on bitfields elsewhere.
            # We enforce a specific match for the checksum flag in validation, so the
            # gre_flags dict will always have a 'checksum' key when gre_key is populated.
            if not gre_flags['checksum']:
                # No "unset" child node means C is set, we offset key lookup +32 bits
                output.append(f'@th,64,32 == {gre_key}')
            else:
                output.append(f'@th,32,32 == {gre_key}')

    if 'time' in rule_conf:
        output.append(parse_time(rule_conf['time']))

    tcp_flags = dict_search_args(rule_conf, 'tcp', 'flags')
    if tcp_flags:
        output.append(parse_tcp_flags(tcp_flags))

    # TCP MSS
    tcp_mss = dict_search_args(rule_conf, 'tcp', 'mss')
    if tcp_mss:
        output.append(f'tcp option maxseg size {tcp_mss}')

    if 'connection_mark' in rule_conf:
        conn_mark_str = ','.join(rule_conf['connection_mark'])
        output.append(f'ct mark {{{conn_mark_str}}}')

    if 'mark' in rule_conf:
        mark = rule_conf['mark']
        operator = ''
        if mark[0] == '!':
            operator = '!='
            mark = mark[1:]
        output.append(f'meta mark {operator} {{{mark}}}')

    if 'vlan' in rule_conf:
        if 'id' in rule_conf['vlan']:
            output.append(f'vlan id {rule_conf["vlan"]["id"]}')
        if 'priority' in rule_conf['vlan']:
            output.append(f'vlan pcp {rule_conf["vlan"]["priority"]}')
        if 'ethernet_type' in rule_conf['vlan']:
            ether_type_mapping = {
                '802.1q': '8021q',
                '802.1ad': '8021ad',
                'ipv6': 'ip6',
                'ipv4': 'ip',
                'arp': 'arp'
            }
            ether_type = rule_conf['vlan']['ethernet_type']
            operator = '!=' if ether_type.startswith('!') else ''
            ether_type = ether_type.lstrip('!')
            ether_type = ether_type_mapping.get(ether_type, ether_type)
            output.append(f'vlan type {operator} {ether_type}')

    if 'log' in rule_conf:
        action = rule_conf['action'] if 'action' in rule_conf else 'accept'
        #output.append(f'log prefix "[{fw_name[:19]}-{rule_id}-{action[:1].upper()}]"')
        output.append(f'log prefix "[{family}-{hook}-{fw_name}-{rule_id}-{action[:1].upper()}]"')
                        ##{family}-{hook}-{fw_name}-{rule_id}
        if 'log_options' in rule_conf:

            if 'level' in rule_conf['log_options']:
                log_level = rule_conf['log_options']['level']
                output.append(f'log level {log_level}')

            if 'group' in rule_conf['log_options']:
                log_group = rule_conf['log_options']['group']
                output.append(f'log group {log_group}')

                if 'queue_threshold' in rule_conf['log_options']:
                    queue_threshold = rule_conf['log_options']['queue_threshold']
                    output.append(f'queue-threshold {queue_threshold}')

                if 'snapshot_length' in rule_conf['log_options']:
                    log_snaplen = rule_conf['log_options']['snapshot_length']
                    output.append(f'snaplen {log_snaplen}')

    output.append('counter')

    if 'add_address_to_group' in rule_conf:
        for side in ['destination_address', 'source_address']:
            if side in rule_conf['add_address_to_group']:
                prefix = side[0]
                side_conf = rule_conf['add_address_to_group'][side]
                dyn_group = side_conf['address_group']
                if 'timeout' in side_conf:
                    timeout_value = side_conf['timeout']
                    output.append(f'set update ip{def_suffix} {prefix}addr timeout {timeout_value} @DA{def_suffix}_{dyn_group}')
                else:
                    output.append(f'set update ip{def_suffix} {prefix}addr @DA{def_suffix}_{dyn_group}')

    set_table = False
    if 'set' in rule_conf:
        # Parse set command used in policy route:
        if 'connection_mark' in rule_conf['set']:
            conn_mark = rule_conf['set']['connection_mark']
            output.append(f'ct mark set {conn_mark}')
        if 'dscp' in rule_conf['set']:
            dscp = rule_conf['set']['dscp']
            output.append(f'ip{def_suffix} dscp set {dscp}')
        if 'mark' in rule_conf['set']:
            mark = rule_conf['set']['mark']
            output.append(f'meta mark set {mark}')
        if 'vrf' in rule_conf['set']:
            set_table = True
            vrf_name = rule_conf['set']['vrf']
            if vrf_name == 'default':
                table = rt_global_vrf
            else:
                # NOTE: VRF->table ID lookup depends on the VRF iface already existing.
                table = get_vrf_tableid(vrf_name)
        if 'table' in rule_conf['set']:
            set_table = True
            table = rule_conf['set']['table']
            if table == 'main':
                table = rt_global_table
        if set_table:
            mark = 0x7FFFFFFF - int(table)
            output.append(f'meta mark set {mark}')
        if 'tcp_mss' in rule_conf['set']:
            mss = rule_conf['set']['tcp_mss']
            output.append(f'tcp option maxseg size set {mss}')
        if 'ttl' in rule_conf['set']:
            ttl = rule_conf['set']['ttl']
            output.append(f'ip ttl set {ttl}')
        if 'hop_limit' in rule_conf['set']:
            hoplimit = rule_conf['set']['hop_limit']
            output.append(f'ip6 hoplimit set {hoplimit}')

    if 'action' in rule_conf:
        if rule_conf['action'] == 'offload':
            offload_target = rule_conf['offload_target']
            output.append(f'flow add @VYOS_FLOWTABLE_{offload_target}')
        else:
            output.append(f'{rule_conf["action"]}')

            if 'jump' in rule_conf['action']:
                target = rule_conf['jump_target']
                output.append(f'NAME{def_suffix}_{target}')

            if 'queue' in rule_conf['action']:
                if 'queue' in rule_conf:
                    target = rule_conf['queue']
                    output.append(f'num {target}')

                if 'queue_options' in rule_conf:
                    queue_opts = ','.join(rule_conf['queue_options'])
                    output.append(f'{queue_opts}')

        # Synproxy
        if 'synproxy' in rule_conf:
            synproxy_mss = dict_search_args(rule_conf, 'synproxy', 'tcp', 'mss')
            if synproxy_mss:
                output.append(f'mss {synproxy_mss}')
            synproxy_ws = dict_search_args(rule_conf, 'synproxy', 'tcp', 'window_scale')
            if synproxy_ws:
                output.append(f'wscale {synproxy_ws} timestamp sack-perm')

    else:
        if set_table:
            output.append('return')

    output.append(f'comment "{family}-{hook}-{fw_name}-{rule_id}"')
    return " ".join(output)

def parse_gre_flags(flags, force_keyed=False):
    flag_map = { # nft does not have symbolic names for these.
        'checksum': 1<<0,
        'routing':  1<<1,
        'key':      1<<2,
        'sequence': 1<<3,
        'strict_routing': 1<<4,
    }

    include = 0
    exclude = 0
    for fl_name, fl_state in flags.items():
        if not fl_state:
            include |= flag_map[fl_name]
        else: # 'unset' child tag
            exclude |= flag_map[fl_name]

    if force_keyed:
        # Implied by a key-match.
        include |= flag_map['key']

    if include == 0 and exclude == 0:
        return '' # Don't bother extracting and matching no bits

    return f'gre flags & {include + exclude} == {include}'

def parse_tcp_flags(flags):
    include = [flag for flag in flags if flag != 'not']
    exclude = list(flags['not']) if 'not' in flags else []
    return f'tcp flags & ({"|".join(include + exclude)}) == {"|".join(include) if include else "0x0"}'

def expand_weekday(abbrev: str) -> str:
    mapping = {
        'mon': 'monday',
        'tue': 'tuesday',
        'wed': 'wednesday',
        'thu': 'thursday',
        'fri': 'friday',
        'sat': 'saturday',
        'sun': 'sunday',
    }
    return mapping.get(abbrev.lower(), abbrev).lower()


def parse_time(time):
    out = []
    if 'startdate' in time:
        start = time['startdate']
        if 'T' not in start and 'starttime' in time:
            start += f' {time["starttime"]}'
        out.append(f'time >= "{start}"')
    if 'starttime' in time and 'startdate' not in time:
        out.append(f'hour >= "{time["starttime"]}"')
    if 'stopdate' in time:
        stop = time['stopdate']
        if 'T' not in stop and 'stoptime' in time:
            stop += f' {time["stoptime"]}'
        out.append(f'time < "{stop}"')
    if 'stoptime' in time and 'stopdate' not in time:
        out.append(f'hour < "{time["stoptime"]}"')
    if 'weekdays' in time:
        days = [day.strip() for day in time['weekdays'].split(",") if day]
        out_days = [f'"{expand_weekday(day).title()}"' for day in days if day[0] != '!']
        out.append(f'day {{{",".join(out_days)}}}')
    return " ".join(out)
