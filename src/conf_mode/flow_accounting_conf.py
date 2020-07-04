#!/usr/bin/env python3
#
# Copyright (C) 2018-2020 VyOS maintainers and contributors
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
from jinja2 import FileSystemLoader, Environment

from vyos.ifconfig import Section
from vyos.ifconfig import Interface
from vyos.config import Config
from vyos import ConfigError
from vyos.util import cmd
from vyos.template import render

from vyos import airbag
airbag.enable()

# default values
default_sflow_server_port = 6343
default_netflow_server_port = 2055
default_plugin_pipe_size = 10
default_captured_packet_size = 128
default_netflow_version = '9'
default_sflow_agentip = 'auto'
uacctd_conf_path = '/etc/pmacct/uacctd.conf'
iptables_nflog_table = 'raw'
iptables_nflog_chain = 'VYATTA_CT_PREROUTING_HOOK'

# helper functions
# check if node exists and return True if this is true
def _node_exists(path):
    vyos_config = Config()
    if vyos_config.exists(path):
        return True

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
def _iptables_get_nflog():
    # define list with rules
    rules = []

    # prepare regex for parsing rules
    rule_pattern = "^-A (?P<rule_definition>{0} -i (?P<interface>[\w\.\*\-]+).*--comment FLOW_ACCOUNTING_RULE.* -j NFLOG.*$)".format(iptables_nflog_chain)
    rule_re = re.compile(rule_pattern)

    for iptables_variant in ['iptables', 'ip6tables']:
        # run iptables, save output and split it by lines
        iptables_command = f'{iptables_variant} -t {iptables_nflog_table} -S {iptables_nflog_chain}'
        tmp = cmd(iptables_command, message='Failed to get flows list')

        # parse each line and add information to list
        for current_rule in tmp.splitlines():
            current_rule_parsed = rule_re.search(current_rule)
            if current_rule_parsed:
                rules.append({ 'interface': current_rule_parsed.groupdict()["interface"], 'iptables_variant': iptables_variant, 'table': iptables_nflog_table, 'rule_definition': current_rule_parsed.groupdict()["rule_definition"] })

    # return list with rules
    return rules

# modify iptables rules
def _iptables_config(configured_ifaces):
    # define list of iptables commands to modify settings
    iptable_commands = []

    # prepare extended list with configured interfaces
    configured_ifaces_extended = []
    for iface in configured_ifaces:
        configured_ifaces_extended.append({ 'iface': iface, 'iptables_variant': 'iptables' })
        configured_ifaces_extended.append({ 'iface': iface, 'iptables_variant': 'ip6tables' })

    # get currently configured interfaces with iptables rules
    active_nflog_rules = _iptables_get_nflog()

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
        if iface in active_nflog_ifaces:
            configured_ifaces_extended.remove(iface)

    # create missed rules
    for iface_extended in configured_ifaces_extended:
        iface = iface_extended['iface']
        iptables = iface_extended['iptables_variant']
        rule_definition = f'{iptables_nflog_chain} -i {iface} -m comment --comment FLOW_ACCOUNTING_RULE -j NFLOG --nflog-group 2 --nflog-size {default_captured_packet_size} --nflog-threshold 100'
        iptable_commands.append(f'{iptables} -t {iptables_nflog_table} -I {rule_definition}')

    # change iptables
    for command in iptable_commands:
        cmd(command, raising=ConfigError)


def get_config():
    vc = Config()
    vc.set_level('')
    # Convert the VyOS config to an abstract internal representation
    flow_config = {
        'flow-accounting-configured': vc.exists('system flow-accounting'),
        'buffer-size': vc.return_value('system flow-accounting buffer-size'),
        'disable-imt': _node_exists('system flow-accounting disable-imt'),
        'syslog-facility': vc.return_value('system flow-accounting syslog-facility'),
        'interfaces': None,
        'sflow': {
            'configured': vc.exists('system flow-accounting sflow'),
            'agent-address': vc.return_value('system flow-accounting sflow agent-address'),
            'sampling-rate': vc.return_value('system flow-accounting sflow sampling-rate'),
            'servers': None
        },
        'netflow': {
            'configured': vc.exists('system flow-accounting netflow'),
            'engine-id': vc.return_value('system flow-accounting netflow engine-id'),
            'max-flows': vc.return_value('system flow-accounting netflow max-flows'),
            'sampling-rate': vc.return_value('system flow-accounting netflow sampling-rate'),
            'source-ip': vc.return_value('system flow-accounting netflow source-ip'),
            'version': vc.return_value('system flow-accounting netflow version'),
            'timeout': {
                'expint': vc.return_value('system flow-accounting netflow timeout expiry-interval'),
                'general': vc.return_value('system flow-accounting netflow timeout flow-generic'),
                'icmp': vc.return_value('system flow-accounting netflow timeout icmp'),
                'maxlife': vc.return_value('system flow-accounting netflow timeout max-active-life'),
                'tcp.fin': vc.return_value('system flow-accounting netflow timeout tcp-fin'),
                'tcp': vc.return_value('system flow-accounting netflow timeout tcp-generic'),
                'tcp.rst': vc.return_value('system flow-accounting netflow timeout tcp-rst'),
                'udp': vc.return_value('system flow-accounting netflow timeout udp')
            },
            'servers': None
        }
    }

    # get interfaces list
    if vc.exists('system flow-accounting interface'):
        flow_config['interfaces'] = vc.return_values('system flow-accounting interface')

    # get sFlow collectors list
    if vc.exists('system flow-accounting sflow server'):
        flow_config['sflow']['servers'] = []
        sflow_collectors = vc.list_nodes('system flow-accounting sflow server')
        for collector in sflow_collectors:
            port = default_sflow_server_port
            if vc.return_value("system flow-accounting sflow server {} port".format(collector)):
                port = vc.return_value("system flow-accounting sflow server {} port".format(collector))
            flow_config['sflow']['servers'].append({ 'address': collector, 'port': port })

    # get NetFlow collectors list
    if vc.exists('system flow-accounting netflow server'):
        flow_config['netflow']['servers'] = []
        netflow_collectors = vc.list_nodes('system flow-accounting netflow server')
        for collector in netflow_collectors:
            port = default_netflow_server_port
            if vc.return_value("system flow-accounting netflow server {} port".format(collector)):
                port = vc.return_value("system flow-accounting netflow server {} port".format(collector))
            flow_config['netflow']['servers'].append({ 'address': collector, 'port': port })

    # get sflow agent-id
    if flow_config['sflow']['agent-address'] == None or flow_config['sflow']['agent-address'] == 'auto':
        flow_config['sflow']['agent-address'] = _sflow_default_agentip(vc)

    # get NetFlow version
    if not flow_config['netflow']['version']:
        flow_config['netflow']['version'] = default_netflow_version

    # convert NetFlow engine-id format, if this is necessary
    if flow_config['netflow']['engine-id'] and flow_config['netflow']['version'] == '5':
        regex_filter = re.compile('^\d+$')
        if regex_filter.search(flow_config['netflow']['engine-id']):
            flow_config['netflow']['engine-id'] = "{}:0".format(flow_config['netflow']['engine-id'])

    # return dict with flow-accounting configuration
    return flow_config

def verify(config):
    # Verify that configuration is valid
    # skip all checks if flow-accounting was removed
    if not config['flow-accounting-configured']:
        return True

    # check if at least one collector is enabled
    if not (config['sflow']['configured'] or config['netflow']['configured'] or not config['disable-imt']):
        raise ConfigError("You need to configure at least one sFlow or NetFlow protocol, or not set \"disable-imt\" for flow-accounting")

    # Check if at least one interface is configured
    if not config['interfaces']:
        raise ConfigError("You need to configure at least one interface for flow-accounting")

    # check that all configured interfaces exists in the system
    for iface in config['interfaces']:
        if not iface in Section.interfaces():
            # chnged from error to warning to allow adding dynamic interfaces and interface templates
            # raise ConfigError("The {} interface is not presented in the system".format(iface))
            print("Warning: the {} interface is not presented in the system".format(iface))

    # check sFlow configuration
    if config['sflow']['configured']:
        # check if at least one sFlow collector is configured if sFlow configuration is presented
        if not config['sflow']['servers']:
            raise ConfigError("You need to configure at least one sFlow server")

        # check that all sFlow collectors use the same IP protocol version
        sflow_collector_ipver = None
        for sflow_collector in config['sflow']['servers']:
            if sflow_collector_ipver:
                if sflow_collector_ipver != ip_address(sflow_collector['address']).version:
                    raise ConfigError("All sFlow servers must use the same IP protocol")
            else:
                sflow_collector_ipver = ip_address(sflow_collector['address']).version


        # check agent-id for sFlow: we should avoid mixing IPv4 agent-id with IPv6 collectors and vice-versa
        for sflow_collector in config['sflow']['servers']:
            if ip_address(sflow_collector['address']).version != ip_address(config['sflow']['agent-address']).version:
                raise ConfigError("Different IP address versions cannot be mixed in \"sflow agent-address\" and \"sflow server\". You need to set manually the same IP version for \"agent-address\" as for all sFlow servers")

        # check if configured sFlow agent-id exist in the system
        agent_id_presented = None
        for iface in Section.interfaces():
            for address in Interface(iface).get_addr():
                # check an IP, if this is not loopback
                regex_filter = re.compile('^(?!(127)|(::1)|(fe80))(?P<ipaddr>[a-f\d\.:]+)/\d+$')
                if regex_filter.search(address):
                    if regex_filter.search(address).group('ipaddr') == config['sflow']['agent-address']:
                        agent_id_presented = True
                        break
        if not agent_id_presented:
            raise ConfigError("Your \"sflow agent-address\" does not exist in the system")

    # check NetFlow configuration
    if config['netflow']['configured']:
        # check if at least one NetFlow collector is configured if NetFlow configuration is presented
        if not config['netflow']['servers']:
            raise ConfigError("You need to configure at least one NetFlow server")

        # check if configured netflow source-ip exist in the system
        if config['netflow']['source-ip']:
            source_ip_presented = None
            for iface in Section.interfaces():
                for address in Interface(iface).get_addr():
                    # check an IP
                    regex_filter = re.compile('^(?!(127)|(::1)|(fe80))(?P<ipaddr>[a-f\d\.:]+)/\d+$')
                    if regex_filter.search(address):
                        if regex_filter.search(address).group('ipaddr') == config['netflow']['source-ip']:
                            source_ip_presented = True
                            break
            if not source_ip_presented:
                raise ConfigError("Your \"netflow source-ip\" does not exist in the system")

        # check if engine-id compatible with selected protocol version
        if config['netflow']['engine-id']:
            v5_filter = '^(\d|[1-9]\d|1\d{2}|2[0-4]\d|25[0-5]):(\d|[1-9]\d|1\d{2}|2[0-4]\d|25[0-5])$'
            v9v10_filter = '^(\d|[1-9]\d{1,8}|[1-3]\d{9}|4[01]\d{8}|42[0-8]\d{7}|429[0-3]\d{6}|4294[0-8]\d{5}|42949[0-5]\d{4}|429496[0-6]\d{3}|4294967[01]\d{2}|42949672[0-8]\d|429496729[0-5])$'
            if config['netflow']['version'] == '5':
                regex_filter = re.compile(v5_filter)
                if not regex_filter.search(config['netflow']['engine-id']):
                    raise ConfigError("You cannot use NetFlow engine-id {} together with NetFlow protocol version {}".format(config['netflow']['engine-id'], config['netflow']['version']))
            else:
                regex_filter = re.compile(v9v10_filter)
                if not regex_filter.search(config['netflow']['engine-id']):
                    raise ConfigError("You cannot use NetFlow engine-id {} together with NetFlow protocol version {}".format(config['netflow']['engine-id'], config['netflow']['version']))

    # return True if all checks were passed
    return True

def generate(config):
    # skip all checks if flow-accounting was removed
    if not config['flow-accounting-configured']:
        return True

    # Calculate all necessary values
    if config['buffer-size']:
        # circular queue size
        config['plugin_pipe_size'] = int(config['buffer-size']) * 1024**2
    else:
        config['plugin_pipe_size'] = default_plugin_pipe_size * 1024**2
    # transfer buffer size
    # recommended value from pmacct developers 1/1000 of pipe size
    config['plugin_buffer_size'] = int(config['plugin_pipe_size'] / 1000)

    # Prepare a timeouts string
    timeout_string = ''
    for timeout_type, timeout_value in config['netflow']['timeout'].items():
        if timeout_value:
            if timeout_string == '':
                timeout_string = "{}{}={}".format(timeout_string, timeout_type, timeout_value)
            else:
                timeout_string = "{}:{}={}".format(timeout_string, timeout_type, timeout_value)
    config['netflow']['timeout_string'] = timeout_string

    render(uacctd_conf_path, 'netflow/uacctd.conf.tmpl', {
        'templatecfg': config,
        'snaplen': default_captured_packet_size,
    })


def apply(config):
    # define variables
    command = None
    # Check if flow-accounting was removed and define command
    if not config['flow-accounting-configured']:
        command = 'systemctl stop uacctd.service'
    else:
        command = 'systemctl restart uacctd.service'

    # run command to start or stop flow-accounting
    cmd(command, raising=ConfigError, message='Failed to start/stop flow-accounting')

    # configure iptables rules for defined interfaces
    if config['interfaces']:
        _iptables_config(config['interfaces'])
    else:
        _iptables_config([])

if __name__ == '__main__':
    try:
        config = get_config()
        verify(config)
        generate(config)
        apply(config)
    except ConfigError as e:
        print(e)
        exit(1)
