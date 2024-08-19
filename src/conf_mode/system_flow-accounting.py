#!/usr/bin/env python3
#
# Copyright (C) 2018-2024 VyOS maintainers and contributors
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
from ipaddress import ip_address

from vyos.config import Config
from vyos.config import config_dict_merge
from vyos.configverify import verify_vrf
from vyos.configverify import verify_interface_exists
from vyos.template import render
from vyos.utils.process import call
from vyos.utils.process import cmd
from vyos.utils.process import run
from vyos.utils.network import is_addr_assigned
from vyos import ConfigError
from vyos import airbag
airbag.enable()

uacctd_conf_path = '/run/pmacct/uacctd.conf'
systemd_service = 'uacctd.service'
systemd_override = f'/run/systemd/system/{systemd_service}.d/override.conf'
nftables_nflog_table = 'raw'
nftables_nflog_chain = 'VYOS_PREROUTING_HOOK'
egress_nftables_nflog_table = 'inet mangle'
egress_nftables_nflog_chain = 'FORWARD'

# get nftables rule dict for chain in table
def _nftables_get_nflog(chain, table):
    # define list with rules
    rules = []

    # prepare regex for parsing rules
    rule_pattern = '[io]ifname "(?P<interface>[\w\.\*\-]+)".*handle (?P<handle>[\d]+)'
    rule_re = re.compile(rule_pattern)

    # run nftables, save output and split it by lines
    nftables_command = f'nft -a list chain {table} {chain}'
    tmp = cmd(nftables_command, message='Failed to get flows list')
    # parse each line and add information to list
    for current_rule in tmp.splitlines():
        if 'FLOW_ACCOUNTING_RULE' not in current_rule:
            continue
        current_rule_parsed = rule_re.search(current_rule)
        if current_rule_parsed:
            groups = current_rule_parsed.groupdict()
            rules.append({ 'interface': groups["interface"], 'table': table, 'handle': groups["handle"] })

    # return list with rules
    return rules

def _nftables_config(configured_ifaces, direction, length=None):
    # define list of nftables commands to modify settings
    nftable_commands = []
    nftables_chain = nftables_nflog_chain
    nftables_table = nftables_nflog_table

    if direction == "egress":
        nftables_chain = egress_nftables_nflog_chain
        nftables_table = egress_nftables_nflog_table

    # prepare extended list with configured interfaces
    configured_ifaces_extended = []
    for iface in configured_ifaces:
        configured_ifaces_extended.append({ 'iface': iface })

    # get currently configured interfaces with nftables rules
    active_nflog_rules = _nftables_get_nflog(nftables_chain, nftables_table)

    # compare current active list with configured one and delete excessive interfaces, add missed
    active_nflog_ifaces = []
    for rule in active_nflog_rules:
        interface = rule['interface']
        if interface not in configured_ifaces:
            table = rule['table']
            handle = rule['handle']
            nftable_commands.append(f'nft delete rule {table} {nftables_chain} handle {handle}')
        else:
            active_nflog_ifaces.append({
                'iface': interface,
            })

    # do not create new rules for already configured interfaces
    for iface in active_nflog_ifaces:
        if iface in active_nflog_ifaces and iface in configured_ifaces_extended:
            configured_ifaces_extended.remove(iface)

    # create missed rules
    for iface_extended in configured_ifaces_extended:
        iface = iface_extended['iface']
        iface_prefix = "o" if direction == "egress" else "i"
        rule_definition = f'{iface_prefix}ifname "{iface}" counter log group 2 snaplen {length} queue-threshold 100 comment "FLOW_ACCOUNTING_RULE"'
        nftable_commands.append(f'nft insert rule {nftables_table} {nftables_chain} {rule_definition}')
        # Also add IPv6 ingres logging
        if nftables_table == nftables_nflog_table:
            nftable_commands.append(f'nft insert rule ip6 {nftables_table} {nftables_chain} {rule_definition}')

    # change nftables
    for command in nftable_commands:
        cmd(command, raising=ConfigError)


def _nftables_trigger_setup(operation: str) -> None:
    """Add a dummy rule to unlock the main pmacct loop with a packet-trigger

    Args:
        operation (str): 'add' or 'delete' a trigger
    """
    # check if a chain exists
    table_exists = False
    if run('nft -snj list table ip pmacct') == 0:
        table_exists = True

    if operation == 'delete' and table_exists:
        nft_cmd: str = 'nft delete table ip pmacct'
        cmd(nft_cmd, raising=ConfigError)
    if operation == 'add' and not table_exists:
        nft_cmds: list[str] = [
            'nft add table ip pmacct',
            'nft add chain ip pmacct pmacct_out { type filter hook output priority raw - 50 \\; policy accept \\; }',
            'nft add rule ip pmacct pmacct_out oif lo ip daddr 127.0.254.0 counter log group 2 snaplen 1 queue-threshold 0 comment NFLOG_TRIGGER'
        ]
        for nft_cmd in nft_cmds:
            cmd(nft_cmd, raising=ConfigError)


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['system', 'flow-accounting']
    if not conf.exists(base):
        return None

    flow_accounting = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)

    # We have gathered the dict representation of the CLI, but there are
    # default values which we need to conditionally update into the
    # dictionary retrieved.
    default_values = conf.get_config_defaults(**flow_accounting.kwargs,
                                              recursive=True)

    # delete individual flow type defaults - should only be added if user
    # sets this feature
    for flow_type in ['sflow', 'netflow']:
        if flow_type not in flow_accounting and flow_type in default_values:
            del default_values[flow_type]

    flow_accounting = config_dict_merge(default_values, flow_accounting)

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
        verify_interface_exists(flow_config, interface, warning_only=True)

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

        # check if vrf is defined for Sflow
        verify_vrf(flow_config)
        sflow_vrf = None
        if 'vrf' in flow_config:
            sflow_vrf = flow_config['vrf']

        # check agent-id for sFlow: we should avoid mixing IPv4 agent-id with IPv6 collectors and vice-versa
        for server in flow_config['sflow']['server']:
            if 'agent_address' in flow_config['sflow']:
                if ip_address(server).version != ip_address(flow_config['sflow']['agent_address']).version:
                    raise ConfigError('IPv4 and IPv6 addresses can not be mixed in "sflow agent-address" and "sflow '\
                                      'server". You need to set the same IP version for both "agent-address" and '\
                                      'all sFlow servers')

        if 'agent_address' in flow_config['sflow']:
            tmp = flow_config['sflow']['agent_address']
            if not is_addr_assigned(tmp, sflow_vrf):
                raise ConfigError(f'Configured "sflow agent-address {tmp}" does not exist in the system!')

        # Check if configured sflow source-address exist in the system
        if 'source_address' in flow_config['sflow']:
            if not is_addr_assigned(flow_config['sflow']['source_address'], sflow_vrf):
                tmp = flow_config['sflow']['source_address']
                raise ConfigError(f'Configured "sflow source-address {tmp}" does not exist on the system!')

    # check NetFlow configuration
    if 'netflow' in flow_config:
        # check if vrf is defined for netflow
        netflow_vrf = None
        if 'vrf' in flow_config:
            netflow_vrf = flow_config['vrf']

        # check if at least one NetFlow collector is configured if NetFlow configuration is presented
        if 'server' not in flow_config['netflow']:
            raise ConfigError('You need to configure at least one NetFlow server!')

        # Check if configured netflow source-address exist in the system
        if 'source_address' in flow_config['netflow']:
            if not is_addr_assigned(flow_config['netflow']['source_address'], netflow_vrf):
                tmp = flow_config['netflow']['source_address']
                raise ConfigError(f'Configured "netflow source-address {tmp}" does not exist on the system!')

        # Check if engine-id compatible with selected protocol version
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
                    raise ConfigError(f'Can not use NetFlow engine-id "{engine_id}" together '\
                                      f'with NetFlow protocol version "{version}"!')

    # return True if all checks were passed
    return True

def generate(flow_config):
    if not flow_config:
        return None

    render(uacctd_conf_path, 'pmacct/uacctd.conf.j2', flow_config)
    render(systemd_override, 'pmacct/override.conf.j2', flow_config)
    # Reload systemd manager configuration
    call('systemctl daemon-reload')

def apply(flow_config):
    # Check if flow-accounting was removed and define command
    if not flow_config:
        _nftables_config([], 'ingress')
        _nftables_config([], 'egress')

        # Stop flow-accounting daemon and remove configuration file
        call(f'systemctl stop {systemd_service}')
        if os.path.exists(uacctd_conf_path):
            os.unlink(uacctd_conf_path)

        # must be done after systemctl
        _nftables_trigger_setup('delete')

        return

    # Start/reload flow-accounting daemon
    call(f'systemctl restart {systemd_service}')

    # configure nftables rules for defined interfaces
    if 'interface' in flow_config:
        _nftables_config(flow_config['interface'], 'ingress', flow_config['packet_length'])

        # configure egress the same way if configured otherwise remove it
        if 'enable_egress' in flow_config:
            _nftables_config(flow_config['interface'], 'egress', flow_config['packet_length'])
        else:
            _nftables_config([], 'egress')

    # add a trigger for signal processing
    _nftables_trigger_setup('add')


if __name__ == '__main__':
    try:
        config = get_config()
        verify(config)
        generate(config)
        apply(config)
    except ConfigError as e:
        print(e)
        exit(1)
