#!/usr/bin/env python3
#
# Copyright (C) 2024 VyOS maintainers and contributors
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

from vyos.utils.process import run

dhclient_lease = '/var/lib/dhcp/dhclient_{0}.lease'

def nft_rule(rule_conf, rule_id, local=False, exclude=False, limit=False, weight=None, health_state=None, action=None, restore_mark=False):
    output = []

    if 'inbound_interface' in rule_conf:
        ifname = rule_conf['inbound_interface']
        if local and not exclude:
            output.append(f'oifname != "{ifname}"')
        elif not local:
            output.append(f'iifname "{ifname}"')

    if 'protocol' in rule_conf and rule_conf['protocol'] != 'all':
        protocol = rule_conf['protocol']

        if protocol == 'tcp_udp':
            protocol = '{ tcp, udp }'

        output.append(f'meta l4proto {protocol}')

    for direction in ['source', 'destination']:
        if direction not in rule_conf:
            continue

        direction_conf = rule_conf[direction]
        prefix = direction[:1]

        if 'address' in direction_conf:
            operator = ''
            address = direction_conf['address']
            if address[:1] == '!':
                operator = '!='
                address = address[1:]
            output.append(f'ip {prefix}addr {operator} {address}')

        if 'port' in direction_conf:
            operator = ''
            port = direction_conf['port']
            if port[:1] == '!':
                operator = '!='
                port = port[1:]
            output.append(f'th {prefix}port {operator} {port}')

    if 'source_based_routing' not in rule_conf and not restore_mark:
        output.append('ct state new')

    if limit and 'limit' in rule_conf and 'rate' in rule_conf['limit']:
        output.append(f'limit rate {rule_conf["limit"]["rate"]}/{rule_conf["limit"]["period"]}')
        if 'burst' in rule_conf['limit']:
            output.append(f'burst {rule_conf["limit"]["burst"]} packets')

    output.append('counter')

    if restore_mark:
        output.append('meta mark set ct mark')
    elif weight:
        weights, total_weight = wlb_weight_interfaces(rule_conf, health_state)
        if len(weights) > 1: # Create weight-based verdict map
            vmap_str = ", ".join(f'{weight} : jump wlb_mangle_isp_{ifname}' for ifname, weight in weights)
            output.append(f'numgen random mod {total_weight} vmap {{ {vmap_str} }}')
        elif len(weights) == 1: # Jump to single ISP
            ifname, _ = weights[0]
            output.append(f'jump wlb_mangle_isp_{ifname}')
        else: # No healthy interfaces
            return ""
    elif action:
        output.append(action)

    return " ".join(output)

def wlb_weight_interfaces(rule_conf, health_state):
    interfaces = [(ifname, int(if_conf.get('weight', 1))) for ifname, if_conf in rule_conf['interface'].items() if health_state[ifname]['state']]

    if not interfaces:
        return [], 0

    if 'failover' in rule_conf:
        for ifpair in sorted(interfaces, key=lambda i: i[1], reverse=True):
            return [ifpair], ifpair[1] # Return highest weight interface that is ACTIVE when in failover

    total_weight = sum(weight for ifname, weight in interfaces)
    out = []
    start = 0
    for ifname, weight in sorted(interfaces, key=lambda i: i[1]): # build weight ranges
        end = start + weight - 1
        out.append((ifname, f'{start}-{end}' if end > start else start))
        start = weight

    return out, total_weight

def health_ping_host(host, ifname, count=1, wait_time=0):
    cmd_str = f'ping -c {count} -W {wait_time} -I {ifname} {host}'
    rc = run(cmd_str)
    return rc == 0

def health_ping_host_ttl(host, ifname, count=1, ttl_limit=0):
    cmd_str = f'ping -c {count} -t {ttl_limit} -I {ifname} {host}'
    rc = run(cmd_str)
    return rc != 0

def parse_dhcp_nexthop(ifname):
    lease_file = dhclient_lease.format(ifname)

    if not os.path.exists(lease_file):
        return False

    with open(lease_file, 'r') as f:
        for line in f.readlines():
            data = line.replace('\n', '').split('=')
            if data[0] == 'new_routers':
                return data[1].replace("'", '').split(" ")[0]

    return None
