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
import argparse
import re
import ipaddress
import os.path
from tabulate import tabulate

from vyos.command import cmd, run

# some default values
uacctd_pidfile = '/var/run/uacctd.pid'
uacctd_pipefile = '/tmp/uacctd.pipe'


# check if ports argument have correct format
def _is_ports(ports):
    # define regex for checking
    regex_filter = re.compile('^(\d|[1-9]\d{1,3}|[1-5]\d{4}|6[0-4]\d{3}|65[0-4]\d{2}|655[0-2]\d|6553[0-5])$|^(\d|[1-9]\d{1,3}|[1-5]\d{4}|6[0-4]\d{3}|65[0-4]\d{2}|655[0-2]\d|6553[0-5])-(\d|[1-9]\d{1,3}|[1-5]\d{4}|6[0-4]\d{3}|65[0-4]\d{2}|655[0-2]\d|6553[0-5])$|^((\d|[1-9]\d{1,3}|[1-5]\d{4}|6[0-4]\d{3}|65[0-4]\d{2}|655[0-2]\d|6553[0-5]),)+(\d|[1-9]\d{1,3}|[1-5]\d{4}|6[0-4]\d{3}|65[0-4]\d{2}|655[0-2]\d|6553[0-5])$')
    if not regex_filter.search(ports):
        raise argparse.ArgumentTypeError("Invalid ports: {}".format(ports))

    # check which type nitation is used: single port, ports list, ports range
    # single port
    regex_filter = re.compile('^(\d|[1-9]\d{1,3}|[1-5]\d{4}|6[0-4]\d{3}|65[0-4]\d{2}|655[0-2]\d|6553[0-5])$')
    if regex_filter.search(ports):
        filter_ports = { 'type': 'single', 'value': int(ports) }

    # ports list
    regex_filter = re.compile('^((\d|[1-9]\d{1,3}|[1-5]\d{4}|6[0-4]\d{3}|65[0-4]\d{2}|655[0-2]\d|6553[0-5]),)+(\d|[1-9]\d{1,3}|[1-5]\d{4}|6[0-4]\d{3}|65[0-4]\d{2}|655[0-2]\d|6553[0-5])')
    if regex_filter.search(ports):
        filter_ports = { 'type': 'list', 'value': list(map(int, ports.split(','))) }

    # ports range
    regex_filter = re.compile('^(?P<first>\d|[1-9]\d{1,3}|[1-5]\d{4}|6[0-4]\d{3}|65[0-4]\d{2}|655[0-2]\d|6553[0-5])-(?P<second>\d|[1-9]\d{1,3}|[1-5]\d{4}|6[0-4]\d{3}|65[0-4]\d{2}|655[0-2]\d|6553[0-5])$')
    if regex_filter.search(ports):
        # check if second number is greater than the first
        if int(regex_filter.search(ports).group('first')) >= int(regex_filter.search(ports).group('second')):
            raise argparse.ArgumentTypeError("Invalid ports: {}".format(ports))
        filter_ports = { 'type': 'range', 'value': range(int(regex_filter.search(ports).group('first')), int(regex_filter.search(ports).group('second'))) }

    # if all above failed
    if not filter_ports:
        raise argparse.ArgumentTypeError("Failed to parse: {}".format(ports))
    else:
        return filter_ports

# check if host argument have correct format
def _is_host(host):
    # define regex for checking
    if not ipaddress.ip_address(host):
        raise argparse.ArgumentTypeError("Invalid host: {}".format(host))
    return host

# check if flow-accounting running
def _uacctd_running():
    command = 'systemctl status uacctd.service > /dev/null'
    return run(command) == 0

# get list of interfaces
def _get_ifaces_dict():
    # run command to get ifaces list
    out = cmd('/bin/ip link show')

    # read output
    ifaces_out = out.splitlines()

    # make a dictionary with interfaces and indexes
    ifaces_dict = {}
    regex_filter = re.compile('^(?P<iface_index>\d+):\ (?P<iface_name>[\w\d\.]+)[:@].*$')
    for iface_line in ifaces_out:
        if regex_filter.search(iface_line):
            ifaces_dict[int(regex_filter.search(iface_line).group('iface_index'))] = regex_filter.search(iface_line).group('iface_name')

    # return dictioanry
    return ifaces_dict

# get list of flows
def _get_flows_list():
    # run command to get flows list
    out = cmd(f'/usr/bin/pmacct -s -O json -T flows -p {uacctd_pipefile}',
                message='Failed to get flows list')

    # read output
    flows_out = out.splitlines()

    # make a list with flows
    flows_list = []
    for flow_line in flows_out:
        flows_list.append(eval(flow_line))

    # return list of flows
    return flows_list

# filter and format flows
def _flows_filter(flows, ifaces):
    # predefine filtered flows list
    flows_filtered = []

    # add interface names to flows
    for flow in flows:
        if flow['iface_in'] in ifaces:
            flow['iface_in_name'] = ifaces[flow['iface_in']]
        else:
            flow['iface_in_name'] = 'unknown'

    # iterate through flows list
    for flow in flows:
        # filter by interface
        if cmd_args.interface:
            if flow['iface_in_name'] != cmd_args.interface:
                continue
        # filter by host
        if cmd_args.host:
            if flow['ip_src'] != cmd_args.host and flow['ip_dst'] != cmd_args.host:
                continue
        # filter by ports
        if cmd_args.ports:
            if cmd_args.ports['type'] == 'single':
                if flow['port_src'] != cmd_args.ports['value'] and flow['port_dst'] != cmd_args.ports['value']:
                    continue
            else:
                if flow['port_src'] not in cmd_args.ports['value'] and flow['port_dst'] not in cmd_args.ports['value']:
                    continue
        # add filtered flows to new list
        flows_filtered.append(flow)

        # stop adding if we already reached top count
        if cmd_args.top:
            if len(flows_filtered) == cmd_args.top:
                break

    # return filtered flows
    return flows_filtered

# print flow table
def _flows_table_print(flows):
    #define headers and body
    table_headers = [ 'IN_IFACE', 'SRC_MAC', 'DST_MAC', 'SRC_IP', 'DST_IP', 'SRC_PORT', 'DST_PORT', 'PROTOCOL', 'TOS', 'PACKETS', 'FLOWS', 'BYTES' ]
    table_body = []
    # convert flows to list
    for flow in flows:
        table_body.append([flow['iface_in_name'], flow['mac_src'], flow['mac_dst'], flow['ip_src'], flow['ip_dst'], flow['port_src'], flow['port_dst'], flow['ip_proto'], flow['tos'], flow['packets'], flow['flows'], flow['bytes'] ])
    # configure and fill table
    table = tabulate(table_body, table_headers, tablefmt="simple")

    # print formatted table
    try:
        print(table)
    except IOError:
        sys.exit(0)
    except KeyboardInterrupt:
        sys.exit(0)

# check if in-memory table is active
def _check_imt():
    if not os.path.exists(uacctd_pipefile):
        print("In-memory table is not available")
        sys.exit(1)

# define program arguments
cmd_args_parser = argparse.ArgumentParser(description='show flow-accounting')
cmd_args_parser.add_argument('--action', choices=['show', 'clear', 'restart'], required=True, help='command to flow-accounting daemon')
cmd_args_parser.add_argument('--filter', choices=['interface', 'host', 'ports', 'top'], required=False,  nargs='*', help='filter flows to display')
cmd_args_parser.add_argument('--interface', required=False, help='interface name for output filtration')
cmd_args_parser.add_argument('--host', type=_is_host, required=False, help='host address for output filtration')
cmd_args_parser.add_argument('--ports', type=_is_ports, required=False, help='ports number for output filtration')
cmd_args_parser.add_argument('--top', type=int, required=False, help='top records for output filtration')
# parse arguments
cmd_args = cmd_args_parser.parse_args()


# main logic
# do nothing if uacctd daemon is not running
if not _uacctd_running():
    print("flow-accounting is not active")
    sys.exit(1)

# restart pmacct daemon
if cmd_args.action == 'restart':
    # run command to restart flow-accounting
    cmd('sudo systemctl restart uacctd.service',
        message='Failed to restart flow-accounting')

# clear in-memory collected flows
if cmd_args.action == 'clear':
    _check_imt()
    # run command to clear flows
    cmd(f'/usr/bin/pmacct -e -p {uacctd_pipefile}',
        message='Failed to clear flows')

# show table with flows
if cmd_args.action == 'show':
    _check_imt()
    # get interfaces index and names
    ifaces_dict = _get_ifaces_dict()
    # get flows
    flows_list = _get_flows_list()

    # filter and format flows
    tabledata = _flows_filter(flows_list, ifaces_dict)

    # print flows
    _flows_table_print(tabledata)

sys.exit(0)
