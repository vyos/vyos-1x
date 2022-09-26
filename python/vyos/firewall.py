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

import csv
import gzip
import os
import re

from pathlib import Path
from time import strftime

from vyos.remote import download
from vyos.template import is_ipv4
from vyos.template import render
from vyos.util import call
from vyos.util import cmd
from vyos.util import dict_search_args
from vyos.util import dict_search_recursive
from vyos.util import run


# Functions for firewall group domain-groups
def get_ips_domains_dict(list_domains):
    """
    Get list of IPv4 addresses by list of domains
    Ex: get_ips_domains_dict(['ex1.com', 'ex2.com'])
        {'ex1.com': ['192.0.2.1'], 'ex2.com': ['192.0.2.2', '192.0.2.3']}
    """
    from socket import gethostbyname_ex
    from socket import gaierror

    ip_dict = {}
    for domain in list_domains:
        try:
            _, _, ips = gethostbyname_ex(domain)
            ip_dict[domain] = ips
        except gaierror:
            pass

    return ip_dict

def nft_init_set(group_name, table="vyos_filter", family="ip"):
    """
    table ip vyos_filter {
        set GROUP_NAME
            type ipv4_addr
           flags interval
        }
    """
    return call(f'nft add set ip {table} {group_name} {{ type ipv4_addr\\; flags interval\\; }}')


def nft_add_set_elements(group_name, elements, table="vyos_filter", family="ip"):
    """
    table ip vyos_filter {
        set GROUP_NAME {
            type ipv4_addr
            flags interval
            elements = { 192.0.2.1, 192.0.2.2 }
        }
    """
    elements = ", ".join(elements)
    return call(f'nft add element {family} {table} {group_name} {{ {elements} }} ')

def nft_flush_set(group_name, table="vyos_filter", family="ip"):
    """
    Flush elements of nft set
    """
    return call(f'nft flush set {family} {table} {group_name}')

def nft_update_set_elements(group_name, elements, table="vyos_filter", family="ip"):
    """
    Update elements of nft set
    """
    flush_set = nft_flush_set(group_name, table="vyos_filter", family="ip")
    nft_add_set = nft_add_set_elements(group_name, elements, table="vyos_filter", family="ip")
    return flush_set, nft_add_set

# END firewall group domain-group (sets)

def find_nftables_rule(table, chain, rule_matches=[]):
    # Find rule in table/chain that matches all criteria and return the handle
    results = cmd(f'sudo nft -a list chain {table} {chain}').split("\n")
    for line in results:
        if all(rule_match in line for rule_match in rule_matches):
            handle_search = re.search('handle (\d+)', line)
            if handle_search:
                return handle_search[1]
    return None

def remove_nftables_rule(table, chain, handle):
    cmd(f'sudo nft delete rule {table} {chain} handle {handle}')

# Functions below used by template generation

def nft_action(vyos_action):
    if vyos_action == 'accept':
        return 'return'
    return vyos_action

def parse_rule(rule_conf, fw_name, rule_id, ip_name):
    output = []
    def_suffix = '6' if ip_name == 'ip6' else ''

    if 'state' in rule_conf and rule_conf['state']:
        states = ",".join([s for s, v in rule_conf['state'].items() if v == 'enable'])

        if states:
            output.append(f'ct state {{{states}}}')

    if 'connection_status' in rule_conf and rule_conf['connection_status']:
        status = rule_conf['connection_status']
        if status['nat'] == 'destination':
            nat_status = '{dnat}'
            output.append(f'ct status {nat_status}')
        if status['nat'] == 'source':
            nat_status = '{snat}'
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

    for side in ['destination', 'source']:
        if side in rule_conf:
            prefix = side[0]
            side_conf = rule_conf[side]

            if 'address' in side_conf:
                suffix = side_conf['address']
                if suffix[0] == '!':
                    suffix = f'!= {suffix[1:]}'
                output.append(f'{ip_name} {prefix}addr {suffix}')

            if dict_search_args(side_conf, 'geoip', 'country_code'):
                operator = ''
                if dict_search_args(side_conf, 'geoip', 'inverse_match') != None:
                    operator = '!='
                output.append(f'{ip_name} {prefix}addr {operator} @GEOIP_CC_{fw_name}_{rule_id}')

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
                if 'address_group' in group:
                    group_name = group['address_group']
                    operator = ''
                    if group_name[0] == '!':
                        operator = '!='
                        group_name = group_name[1:]
                    output.append(f'{ip_name} {prefix}addr {operator} @A{def_suffix}_{group_name}')
                # Generate firewall group domain-group
                elif 'domain_group' in group:
                    group_name = group['domain_group']
                    operator = ''
                    if group_name[0] == '!':
                        operator = '!='
                        group_name = group_name[1:]
                    output.append(f'{ip_name} {prefix}addr {operator} @D_{group_name}')
                elif 'network_group' in group:
                    group_name = group['network_group']
                    operator = ''
                    if group_name[0] == '!':
                        operator = '!='
                        group_name = group_name[1:]
                    output.append(f'{ip_name} {prefix}addr {operator} @N{def_suffix}_{group_name}')
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

    if 'log' in rule_conf and rule_conf['log'] == 'enable':
        action = rule_conf['action'] if 'action' in rule_conf else 'accept'
        output.append(f'log prefix "[{fw_name[:19]}-{rule_id}-{action[:1].upper()}]"')

        if 'log_level' in rule_conf:
            log_level = rule_conf['log_level']
            output.append(f'level {log_level}')


    if 'hop_limit' in rule_conf:
        operators = {'eq': '==', 'gt': '>', 'lt': '<'}
        for op, operator in operators.items():
            if op in rule_conf['hop_limit']:
                value = rule_conf['hop_limit'][op]
                output.append(f'ip6 hoplimit {operator} {value}')

    if 'inbound_interface' in rule_conf:
        iiface = rule_conf['inbound_interface']
        output.append(f'iifname {iiface}')

    if 'outbound_interface' in rule_conf:
        oiface = rule_conf['outbound_interface']
        output.append(f'oifname {oiface}')

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

    if 'dscp' in rule_conf:
        dscp_str = ','.join(rule_conf['dscp'])
        output.append(f'ip{def_suffix} dscp {{{dscp_str}}}')

    if 'dscp_exclude' in rule_conf:
        negated_dscp_str = ','.join(rule_conf['dscp_exclude'])
        output.append(f'ip{def_suffix} dscp != {{{negated_dscp_str}}}')

    if 'ipsec' in rule_conf:
        if 'match_ipsec' in rule_conf['ipsec']:
            output.append('meta ipsec == 1')
        if 'match_non_ipsec' in rule_conf['ipsec']:
            output.append('meta ipsec == 0')

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
        output.append(f'add @RECENT{def_suffix}_{fw_name}_{rule_id} {{ {ip_name} saddr limit rate over {count}/{time} burst {count} packets }}')

    if 'time' in rule_conf:
        output.append(parse_time(rule_conf['time']))

    tcp_flags = dict_search_args(rule_conf, 'tcp', 'flags')
    if tcp_flags:
        output.append(parse_tcp_flags(tcp_flags))

    # TCP MSS
    tcp_mss = dict_search_args(rule_conf, 'tcp', 'mss')
    if tcp_mss:
        output.append(f'tcp option maxseg size {tcp_mss}')

    output.append('counter')

    if 'set' in rule_conf:
        output.append(parse_policy_set(rule_conf['set'], def_suffix))

    if 'action' in rule_conf:
        output.append(nft_action(rule_conf['action']))
        if 'jump' in rule_conf['action']:
            target = rule_conf['jump_target']
            output.append(f'NAME{def_suffix}_{target}')

    else:
        output.append('return')

    output.append(f'comment "{fw_name}-{rule_id}"')
    return " ".join(output)

def parse_tcp_flags(flags):
    include = [flag for flag in flags if flag != 'not']
    exclude = list(flags['not']) if 'not' in flags else []
    return f'tcp flags & ({"|".join(include + exclude)}) == {"|".join(include) if include else "0x0"}'

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
        days = time['weekdays'].split(",")
        out_days = [f'"{day}"' for day in days if day[0] != '!']
        out.append(f'day {{{",".join(out_days)}}}')
    return " ".join(out)

def parse_policy_set(set_conf, def_suffix):
    out = []
    if 'dscp' in set_conf:
        dscp = set_conf['dscp']
        out.append(f'ip{def_suffix} dscp set {dscp}')
    if 'mark' in set_conf:
        mark = set_conf['mark']
        out.append(f'meta mark set {mark}')
    if 'table' in set_conf:
        table = set_conf['table']
        if table == 'main':
            table = '254'
        mark = 0x7FFFFFFF - int(table)
        out.append(f'meta mark set {mark}')
    if 'tcp_mss' in set_conf:
        mss = set_conf['tcp_mss']
        out.append(f'tcp option maxseg size set {mss}')
    return " ".join(out)

# GeoIP

nftables_geoip_conf = '/run/nftables-geoip.conf'
geoip_database = '/usr/share/vyos-geoip/dbip-country-lite.csv.gz'
geoip_lock_file = '/run/vyos-geoip.lock'

def geoip_load_data(codes=[]):
    data = None

    if not os.path.exists(geoip_database):
        return []

    try:
        with gzip.open(geoip_database, mode='rt') as csv_fh:
            reader = csv.reader(csv_fh)
            out = []
            for start, end, code in reader:
                if code.lower() in codes:
                    out.append([start, end, code.lower()])
            return out
    except:
        print('Error: Failed to open GeoIP database')
    return []

def geoip_download_data():
    url = 'https://download.db-ip.com/free/dbip-country-lite-{}.csv.gz'.format(strftime("%Y-%m"))
    try:
        dirname = os.path.dirname(geoip_database)
        if not os.path.exists(dirname):
            os.mkdir(dirname)

        download(geoip_database, url)
        print("Downloaded GeoIP database")
        return True
    except:
        print("Error: Failed to download GeoIP database")
    return False

class GeoIPLock(object):
    def __init__(self, file):
        self.file = file

    def __enter__(self):
        if os.path.exists(self.file):
            return False

        Path(self.file).touch()
        return True

    def __exit__(self, exc_type, exc_value, tb):
        os.unlink(self.file)

def geoip_update(firewall, force=False):
    with GeoIPLock(geoip_lock_file) as lock:
        if not lock:
            print("Script is already running")
            return False

        if not firewall:
            print("Firewall is not configured")
            return True

        if not os.path.exists(geoip_database):
            if not geoip_download_data():
                return False
        elif force:
            geoip_download_data()

        ipv4_codes = {}
        ipv6_codes = {}

        ipv4_sets = {}
        ipv6_sets = {}

        # Map country codes to set names
        for codes, path in dict_search_recursive(firewall, 'country_code'):
            set_name = f'GEOIP_CC_{path[1]}_{path[3]}'
            if path[0] == 'name':
                for code in codes:
                    ipv4_codes.setdefault(code, []).append(set_name)
            elif path[0] == 'ipv6_name':
                for code in codes:
                    ipv6_codes.setdefault(code, []).append(set_name)

        if not ipv4_codes and not ipv6_codes:
            if force:
                print("GeoIP not in use by firewall")
            return True

        geoip_data = geoip_load_data([*ipv4_codes, *ipv6_codes])

        # Iterate IP blocks to assign to sets
        for start, end, code in geoip_data:
            ipv4 = is_ipv4(start)
            if code in ipv4_codes and ipv4:
                ip_range = f'{start}-{end}' if start != end else start
                for setname in ipv4_codes[code]:
                    ipv4_sets.setdefault(setname, []).append(ip_range)
            if code in ipv6_codes and not ipv4:
                ip_range = f'{start}-{end}' if start != end else start
                for setname in ipv6_codes[code]:
                    ipv6_sets.setdefault(setname, []).append(ip_range)

        render(nftables_geoip_conf, 'firewall/nftables-geoip-update.j2', {
            'ipv4_sets': ipv4_sets,
            'ipv6_sets': ipv6_sets
        })

        result = run(f'nft -f {nftables_geoip_conf}')
        if result != 0:
            print('Error: GeoIP failed to update firewall')
            return False

        return True
