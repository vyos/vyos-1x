#!/usr/bin/env python3
#
# Copyright (C) 2018 VyOS maintainers and contributors
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
#

import sys
import re
import ipaddress
import subprocess

from vyos.config import Config
from vyos import ConfigError
import vyos.interfaces
from vyos.ifconfig import Interface
from jinja2 import Template

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

# pmacct config template
uacct_conf_jinja = '''# Genereated from VyOS configuration
daemonize: true
promisc: false
pidfile: /var/run/uacctd.pid
uacctd_group: 2
uacctd_nl_size: 2097152
snaplen: {{ snaplen }}
aggregate: in_iface,src_mac,dst_mac,vlan,src_host,dst_host,src_port,dst_port,proto,tos,flows
plugin_pipe_size: {{ templatecfg['plugin_pipe_size'] }}
plugin_buffer_size: {{ templatecfg['plugin_buffer_size'] }}
{%- if templatecfg['syslog-facility'] != none %}
syslog: {{ templatecfg['syslog-facility'] }}
{%- endif %}
{%- if templatecfg['disable-imt'] == none %}
imt_path: /tmp/uacctd.pipe
imt_mem_pools_number: 169
{%- endif %}
plugins:
{%- if templatecfg['netflow']['servers'] != none -%}
    {% for server in templatecfg['netflow']['servers'] %}
        {%- if loop.last -%}nfprobe[nf_{{ server['address'] }}]{%- else %}nfprobe[nf_{{ server['address'] }}],{%- endif %}
    {%- endfor -%}
    {% set plugins_presented = true %}
{%- endif %}
{%- if templatecfg['sflow']['servers'] != none -%}
    {% if plugins_presented -%}
        {%- for server in templatecfg['sflow']['servers'] -%}
            ,sfprobe[sf_{{ server['address'] }}]
        {%- endfor %}
    {%- else %}
        {%- for server in templatecfg['sflow']['servers'] %}
            {%- if loop.last -%}sfprobe[sf_{{ server['address'] }}]{%- else %}sfprobe[sf_{{ server['address'] }}],{%- endif %}
        {%- endfor %}
    {%- endif -%}
    {% set plugins_presented = true %}
{%- endif %}
{%- if templatecfg['disable-imt'] == none %}
    {%- if plugins_presented -%},memory{%- else %}memory{%- endif %}
{%- endif %}
{%- if templatecfg['netflow']['servers'] != none %}
{%- for server in templatecfg['netflow']['servers'] %}
nfprobe_receiver[nf_{{ server['address'] }}]: {{ server['address'] }}:{{ server['port'] }}
nfprobe_version[nf_{{ server['address'] }}]: {{ templatecfg['netflow']['version'] }}
{%- if templatecfg['netflow']['engine-id'] != none %}
nfprobe_engine[nf_{{ server['address'] }}]: {{ templatecfg['netflow']['engine-id'] }}
{%- endif %}
{%- if templatecfg['netflow']['max-flows'] != none %}
nfprobe_maxflows[nf_{{ server['address'] }}]: {{ templatecfg['netflow']['max-flows'] }}
{%- endif %}
{%- if templatecfg['netflow']['sampling-rate'] != none %}
sampling_rate[nf_{{ server['address'] }}]: {{ templatecfg['netflow']['sampling-rate'] }}
{%- endif %}
{%- if templatecfg['netflow']['source-ip'] != none %}
nfprobe_source_ip[nf_{{ server['address'] }}]: {{ templatecfg['netflow']['source-ip'] }}
{%- endif %}
{%- if templatecfg['netflow']['timeout_string'] != '' %}
nfprobe_timeouts[nf_{{ server['address'] }}]: {{ templatecfg['netflow']['timeout_string'] }}
{%- endif %}
{%- endfor %}
{%- endif %}
{%- if templatecfg['sflow']['servers'] != none %}
{%- for server in templatecfg['sflow']['servers'] %}
sfprobe_receiver[sf_{{ server['address'] }}]: {{ server['address'] }}:{{ server['port'] }}
sfprobe_agentip[sf_{{ server['address'] }}]: {{ templatecfg['sflow']['agent-address'] }}
{%- if templatecfg['sflow']['sampling-rate'] != none %}
sampling_rate[sf_{{ server['address'] }}]: {{ templatecfg['sflow']['sampling-rate'] }}
{%- endif %}
{%- endfor %}
{% endif %}
'''

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
    for iface in vyos.interfaces.list_interfaces():
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
        iptables_command = "sudo {0} -t {1} -S {2}".format(iptables_variant, iptables_nflog_table, iptables_nflog_chain)
        process = subprocess.Popen(iptables_command, stdout=subprocess.PIPE, shell=True, universal_newlines=True)
        stdout, stderr = process.communicate()
        if not process.returncode == 0:
            print("Failed to get flows list: command \"{}\" returned exit code: {}\nError: {}".format(command, process.returncode, stderr))
            sys.exit(1)
        iptables_out = stdout.splitlines()

        # parse each line and add information to list
        for current_rule in iptables_out:
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
        if rule['interface'] not in configured_ifaces:
            iptable_commands.append("sudo {0} -t {1} -D {2}".format(rule['iptables_variant'], rule['table'], rule['rule_definition']))
        else:
            active_nflog_ifaces.append({ 'iface': rule['interface'], 'iptables_variant': rule['iptables_variant'] })

    # do not create new rules for already configured interfaces
    for iface in active_nflog_ifaces:
        if iface in active_nflog_ifaces:
            configured_ifaces_extended.remove(iface)

    # create missed rules
    for iface_extended in configured_ifaces_extended:
        rule_definition = "{0} -i {1} -m comment --comment FLOW_ACCOUNTING_RULE -j NFLOG --nflog-group 2 --nflog-size {2} --nflog-threshold 100".format(iptables_nflog_chain, iface_extended['iface'], default_captured_packet_size)
        iptable_commands.append("sudo {0} -t {1} -I {2}".format(iface_extended['iptables_variant'], iptables_nflog_table, rule_definition))

    # change iptables
    for command in iptable_commands:
        return_code = subprocess.call(command.split(' '))
        if not return_code == 0:
            raise ConfigError("Failed to run command: {}\nExit code {}".format(command, return_code))


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
        if not iface in vyos.interfaces.list_interfaces():
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
                if sflow_collector_ipver != ipaddress.ip_address(sflow_collector['address']).version:
                    raise ConfigError("All sFlow servers must use the same IP protocol")
            else:
                sflow_collector_ipver = ipaddress.ip_address(sflow_collector['address']).version


        # check agent-id for sFlow: we should avoid mixing IPv4 agent-id with IPv6 collectors and vice-versa
        for sflow_collector in config['sflow']['servers']:
            if ipaddress.ip_address(sflow_collector['address']).version != ipaddress.ip_address(config['sflow']['agent-address']).version:
                raise ConfigError("Different IP address versions cannot be mixed in \"sflow agent-address\" and \"sflow server\". You need to set manually the same IP version for \"agent-address\" as for all sFlow servers")

        # check if configured sFlow agent-id exist in the system
        agent_id_presented = None
        for iface in vyos.interfaces.list_interfaces():
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
            for iface in vyos.interfaces.list_interfaces():
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

    # Generate daemon configs
    uacct_conf_template = Template(uacct_conf_jinja)
    uacct_conf_file_data = uacct_conf_template.render(templatecfg = config, snaplen = default_captured_packet_size)

    # save generated config to uacctd.conf
    with open(uacctd_conf_path, 'w') as file:
        file.write(uacct_conf_file_data)


def apply(config):
    # define variables
    command = None
    # Check if flow-accounting was removed and define command
    if not config['flow-accounting-configured']:
        command = '/usr/bin/sudo /bin/systemctl stop uacctd'
    else:
        command = '/usr/bin/sudo /bin/systemctl restart uacctd'

    # run command to start or stop flow-accounting
    return_code = subprocess.call(command.split(' '))
    if not return_code == 0:
        raise ConfigError("Failed to start/stop flow-accounting: command {} returned exit code {}".format(command, return_code))

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
        sys.exit(1)
