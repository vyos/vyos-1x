#!/usr/bin/env python3
#
# Copyright (C) 2018-2021 VyOS maintainers and contributors
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
import ipaddress

from ipaddress import ip_address

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.ifconfig import Section
from vyos.ifconfig import Interface
from vyos.template import render
from vyos.util import cmd
from vyos.validate import is_addr_assigned
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

# default values
default_captured_packet_size = 128

uacctd_conf_path = '/etc/pmacct/uacctd.conf'
iptables_nflog_table = 'raw'
iptables_nflog_chain = 'VYATTA_CT_PREROUTING_HOOK'
egress_iptables_nflog_table = 'mangle'
egress_iptables_nflog_chain = 'FORWARD'

# get sFlow agent-ip if agent-address is "auto" (default behaviour)
def _sflow_default_agentip(config):
    # check if any of BGP, OSPF, OSPFv3 protocols are configured and use router-id from there
    if config.exists('protocols bgp'):
        bgp_router_id = config.return_value("protocols bgp {} parameters router-id".format(config.list_nodes('protocols bgp')[0]))
        if bgp_router_id:
            return bgp_router_id
    if config.return_value('protocols ospf parameters router-id'):
        return config.return_value('protocols ospf parameters router-id')
    if config.return_value('protocols ospfv3 parameters router-id'):
        return config.return_value('protocols ospfv3 parameters router-id')

    # if router-id was not found, use first available ip of any interface
    for iface in Section.interfaces():
        for address in Interface(iface).get_addr():
            # return an IP, if this is not loopback
            regex_filter = re.compile('^(?!(127)|(::1)|(fe80))(?P<ipaddr>[a-f\d\.:]+)/\d+$')
            if regex_filter.search(address):
                return regex_filter.search(address).group('ipaddr')

    # return nothing by default
    return None

# get iptables rule dict for chain in table
def _iptables_get_nflog(chain, table):
    # define list with rules
    rules = []

    # prepare regex for parsing rules
    rule_pattern = "^-A (?P<rule_definition>{0} (\-i|\-o) (?P<interface>[\w\.\*\-]+).*--comment FLOW_ACCOUNTING_RULE.* -j NFLOG.*$)".format(chain)
    rule_re = re.compile(rule_pattern)

    for iptables_variant in ['iptables', 'ip6tables']:
        # run iptables, save output and split it by lines
        iptables_command = f'{iptables_variant} -t {table} -S {chain}'
        tmp = cmd(iptables_command, message='Failed to get flows list')

        # parse each line and add information to list
        for current_rule in tmp.splitlines():
            current_rule_parsed = rule_re.search(current_rule)
            if current_rule_parsed:
                rules.append({ 'interface': current_rule_parsed.groupdict()["interface"], 'iptables_variant': iptables_variant, 'table': table, 'rule_definition': current_rule_parsed.groupdict()["rule_definition"] })

    # return list with rules
    return rules

# modify iptables rules
def _iptables_config(configured_ifaces, direction):
    # define list of iptables commands to modify settings
    iptable_commands = []
    iptables_chain = iptables_nflog_chain
    iptables_table = iptables_nflog_table

    if direction == "egress":
        iptables_chain = egress_iptables_nflog_chain
        iptables_table = egress_iptables_nflog_table

    # prepare extended list with configured interfaces
    configured_ifaces_extended = []
    for iface in configured_ifaces:
        configured_ifaces_extended.append({ 'iface': iface, 'iptables_variant': 'iptables' })
        configured_ifaces_extended.append({ 'iface': iface, 'iptables_variant': 'ip6tables' })

    # get currently configured interfaces with iptables rules
    active_nflog_rules = _iptables_get_nflog(iptables_chain, iptables_table)

    # compare current active list with configured one and delete excessive interfaces, add missed
    active_nflog_ifaces = []
    for rule in active_nflog_rules:
        iptables = rule['iptables_variant']
        interface = rule['interface']
        if interface not in configured_ifaces:
            table = rule['table']
            rule = rule['rule_definition']
            iptable_commands.append(f'{iptables} -t {table} -D {rule}')
        else:
            active_nflog_ifaces.append({
                'iface': interface,
                'iptables_variant': iptables,
            })

    # do not create new rules for already configured interfaces
    for iface in active_nflog_ifaces:
        if iface in active_nflog_ifaces and iface in configured_ifaces_extended:
            configured_ifaces_extended.remove(iface)

    # create missed rules
    for iface_extended in configured_ifaces_extended:
        iface = iface_extended['iface']
        iptables = iface_extended['iptables_variant']
        iptables_op = "-i"
        if direction == "egress":
            iptables_op = "-o"

        rule_definition = f'{iptables_chain} {iptables_op} {iface} -m comment --comment FLOW_ACCOUNTING_RULE -j NFLOG --nflog-group 2 --nflog-size {default_captured_packet_size} --nflog-threshold 100'
        iptable_commands.append(f'{iptables} -t {iptables_table} -I {rule_definition}')

    # change iptables
    for command in iptable_commands:
        cmd(command, raising=ConfigError)


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['system', 'flow-accounting']
    if not conf.exists(base):
        return None

    flow_accounting = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_values = defaults(base)

    # delete individual flow type default - should only be added if user uses
    # this feature
    for flow_type in ['sflow', 'netflow']:
        if flow_type in default_values:
            del default_values[flow_type]
    flow_accounting = dict_merge(default_values, flow_accounting)

    for flow_type in ['sflow', 'netflow']:
        if flow_type in flow_accounting:
            default_values = defaults(base + [flow_type])
            # we need to merge individual server configurations
            if 'server' in default_values:
                del default_values['server']
            flow_accounting[flow_type] = dict_merge(default_values, flow_accounting[flow_type])

            if 'server' in flow_accounting[flow_type]:
                default_values = defaults(base + [flow_type, 'server'])
                for server in flow_accounting[flow_type]['server']:
                    flow_accounting[flow_type]['server'][server] = dict_merge(
                        default_values,flow_accounting[flow_type]['server'][server])

    flow_accounting['snaplen'] = default_captured_packet_size

    return flow_accounting

def verify(flow_config):
    if not flow_config:
        return None

    # check if at least one collector is enabled
    if 'sflow' not in flow_config and 'netflow' not in flow_config and 'disable_imt' in flow_config:
        raise ConfigError('You need to configure at least sFlow or NetFlow, ' \
                          'or not set "disable-imt" for flow-accounting!')

    # Check if at least one interface is configured
    if 'interface' not in flow_config:
        raise ConfigError('Flow accounting requires at least one interface to ' \
                          'be configured!')

    # check that all configured interfaces exists in the system
    for interface in flow_config['interface']:
        if interface not in Section.interfaces():
            # Changed from error to warning to allow adding dynamic interfaces
            # and interface templates
            print(f'Warning: Interface "{interface}" is not presented in the system')

    # check sFlow configuration
    if 'sflow' in flow_config:
        # check if at least one sFlow collector is configured
        if 'server' not in flow_config['sflow']:
            raise ConfigError('You need to configure at least one sFlow server!')

        # check that all sFlow collectors use the same IP protocol version
        sflow_collector_ipver = None
        for server in flow_config['sflow']['server']:
            if sflow_collector_ipver:
                if sflow_collector_ipver != ip_address(server).version:
                    raise ConfigError("All sFlow servers must use the same IP protocol")
            else:
                sflow_collector_ipver = ip_address(server).version

        # check agent-id for sFlow: we should avoid mixing IPv4 agent-id with IPv6 collectors and vice-versa
        for server in flow_config['sflow']['server']:
            if flow_config['sflow']['agent_address'] != 'auto':
                if ip_address(server).version != ip_address(flow_config['sflow']['agent_address']).version:
                    raise ConfigError("Different IP address versions cannot be mixed in \"sflow agent-address\" and \"sflow server\". You need to set manually the same IP version for \"agent-address\" as for all sFlow servers")

        if 'agent_address' in flow_config['sflow']:
            agent_address = flow_config['sflow']['agent_address']
            if agent_address != 'auto' and not is_addr_assigned(agent_address):
                print(f'Warning: Configured "sflow agent-address" does not exist in the system!')

    # check NetFlow configuration
    if 'netflow' in flow_config:
        # check if at least one NetFlow collector is configured if NetFlow configuration is presented
        if 'server' not in flow_config['netflow']:
            raise ConfigError('You need to configure at least one NetFlow server!')

        # check if configured netflow source-ip exist in the system
        if 'source_address' in flow_config['netflow']:
            if not is_addr_assigned(flow_config['netflow']['source_address']):
                print(f'Warning: Configured "netflow source-address" does not exist on the system!')

        # check if engine-id compatible with selected protocol version
        if 'engine_id' in flow_config['netflow']:
            v5_filter = '^(\d|[1-9]\d|1\d{2}|2[0-4]\d|25[0-5]):(\d|[1-9]\d|1\d{2}|2[0-4]\d|25[0-5])$'
            v9v10_filter = '^(\d|[1-9]\d{1,8}|[1-3]\d{9}|4[01]\d{8}|42[0-8]\d{7}|429[0-3]\d{6}|4294[0-8]\d{5}|42949[0-5]\d{4}|429496[0-6]\d{3}|4294967[01]\d{2}|42949672[0-8]\d|429496729[0-5])$'
            engine_id = flow_config['netflow']['engine_id']
            version = flow_config['netflow']['version']

            if flow_config['netflow']['version'] == '5':
                regex_filter = re.compile(v5_filter)
                if not regex_filter.search(engine_id):
                    raise ConfigError(f'You cannot use NetFlow engine-id "{engine_id}" '\
                                      f'together with NetFlow protocol version "{version}"!')
            else:
                regex_filter = re.compile(v9v10_filter)
                if not regex_filter.search(flow_config['netflow']['engine_id']):
                    raise ConfigError("You cannot use NetFlow engine-id {} together with NetFlow protocol version {}".format(config['netflow']['engine-id'], config['netflow']['version']))

    # return True if all checks were passed
    return True

def generate(flow_config):
    if not flow_config:
        return None

    render(uacctd_conf_path, 'netflow/uacctd.conf.tmpl', flow_config)

def apply(flow_config):
    action = 'restart'
    # Check if flow-accounting was removed and define command
    if not flow_config:
        _iptables_config([], 'ingress')
        _iptables_config([], 'egress')

        # Stop flow-accounting daemon
        cmd('systemctl stop uacctd.service')
        return

    # Start/reload flow-accounting daemon
    cmd(f'systemctl restart uacctd.service')

    # configure iptables rules for defined interfaces
    if 'interface' in flow_config:
        _iptables_config(flow_config['interface'], 'ingress')

        # configure egress the same way if configured otherwise remove it
        if 'enable_egress' in flow_config:
            _iptables_config(flow_config['interface'], 'egress')
        else:
            _iptables_config([], 'egress')

if __name__ == '__main__':
    try:
        config = get_config()
        verify(config)
        generate(config)
        apply(config)
    except ConfigError as e:
        print(e)
        exit(1)
