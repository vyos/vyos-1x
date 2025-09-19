#!/usr/bin/env python3
#
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

import sys
import argparse
import re
import ipaddress

from tabulate import tabulate
from vyos.utils.kernel import is_module_loaded
from vyos.utils.process import cmd
from vyos.logger import syslog
from vyos.configquery import ConfigTreeQuery
from vyos import ipt_netflow

# some default values
flows_dump_path = '/proc/net/stat/ipt_netflow_flows'

def parse_port(port):
    try:
        port_num = int(port)
        if (port_num >= 0) and (port_num <= 65535):
            return port_num
        else:
            raise ValueError("out of the 0-65535 range".format(port))
    except ValueError as e:
        raise ValueError("Incorrect port number \'{0}\': {1}".format(port, e))

def parse_ports(arg):
    if re.match(r'^\d+$', arg):
        # Single port
        port = parse_port(arg)
        return {"type": "single", "values": (port,)}
    elif re.match(r'^\d+\-\d+$', arg):
        # Port range
        ports = arg.split("-")
        ports = list(map(parse_port, ports))
        if ports[0] > ports[1]:
            raise ValueError("Malformed port range \'{0}\': lower end is greater than the higher".format(arg))
        else:
            return {"type": "range", "values": range(ports[0], ports[1] + 1)}
    elif re.match(r'^\d+,.*\d$', arg):
        # Port list
        ports = re.split(r',+', arg)  # This allows duplicate commas like '1,,2,3,4'
        ports = list(map(parse_port, ports))
        return {"type": "list", "values": ports}
    else:
        raise ValueError("Malformed port spec \'{0}\'".format(arg))

# check if host argument have correct format
def check_host(host):
    # define regex for checking
    if not ipaddress.ip_address(host):
        raise ValueError("Invalid host \'{}\', must be a valid IP or IPv6 address".format(host))

# check if flow-accounting running
def _netflow_running():
    return is_module_loaded(ipt_netflow.module_name)


# get list of interfaces
def _get_ifaces_dict():
    # run command to get ifaces list
    out = cmd('/bin/ip link show')

    # read output
    ifaces_out = out.splitlines()

    # make a dictionary with interfaces and indexes
    ifaces_dict = {}
    regex_filter = re.compile(r'^(?P<iface_index>\d+):\ (?P<iface_name>[\w\d\.]+)[:@].*$')
    for iface_line in ifaces_out:
        if regex_filter.search(iface_line):
            ifaces_dict[int(regex_filter.search(iface_line).group('iface_index'))] = regex_filter.search(iface_line).group('iface_name')

    # return dictioanry
    return ifaces_dict


# get list of flows
def _get_flows_list():
    # File format:
    # When MAC disabled:
    # # hash a dev:i,o proto src:ip,port dst:ip,port nexthop tos,tcpflags,options,tcpoptions packets bytes ts:first,last
    # 1 c06c 0 4,-1 1 10.2.0.7,0 10.1.0.5,0 0.0.0.0 0,0,0,0 186 15624 92261,131
    # 2 1e3ca 0 3,-1 1 10.1.0.5,0 10.2.0.7,2048 0.0.0.0 0,0,0,0 186 15624 92261,132

    # When MAC enabled + VLAN fix:
    # hash a dev:i,o mac:src,dst vlan type proto src:ip,port dst:ip,port nexthop tos,tcpflags,options,tcpoptions packets bytes ts:first,last
    # 1 11a41 0 4,-1 0c:27:1f:55:00:00,0c:e8:b1:71:00:02 - 0800 1 10.2.0.7,0 10.1.0.5,0 0.0.0.0 0,0,0,0 1182 99288 591502,529
    # 2 13bc5 0 4,-1 0c:27:1f:55:00:00,0c:e8:b1:71:00:02 - 0800 1 10.2.0.7,0 10.2.0.1,2048 0.0.0.0 0,0,0,0 577 48468 590831,1006
    # 3 166dd 0 3,-1 0c:f1:0a:d5:00:00,0c:e8:b1:71:00:01 - 0800 1 10.1.0.5,0 10.2.0.7,2048 0.0.0.0 0,0,0,0 1182 99288 591502,529


    flows_list = []
    with open(flows_dump_path) as f:
        headers = f.readline()
        headers = headers.split()
        for i, h in enumerate(headers):

            if ',' in h and ':' not in h:
                h = 'extra:' + h

            if ':' in h:
                key, subkeys = h.split(':', 1)
                headers[i] = {'key': key, 'subkeys': subkeys.split(',')}

        linenum = 1
        for flow_line in f:
            linenum += 1
            flow_dict = {}
            flow_line = flow_line.split()
            if len(flow_line) != len(headers):
                syslog.error(
                    f'Unexpected number of elements in {flows_dump_path}, line {linenum}'
                )
                continue
            for i, val in enumerate(flow_line):
                if isinstance(headers[i], str):
                    flow_dict[headers[i]] = val
                elif isinstance(headers[i], dict):
                    val = val.split(',')
                    if len(val) != len(headers[i]['subkeys']):
                        syslog.error(
                            f"Unexpected number of elements in {flows_dump_path} in column {headers[i]['key']} in line {linenum}"
                        )
                        continue
                    flow_dict[headers[i]['key']] = dict(zip(headers[i]['subkeys'], val))
                else:
                    assert False, "Unexpected type of header"
            flows_list.append(flow_dict)

    # return list of flows
    return flows_list


# filter and format flows
def _flows_filter(flows, ifaces):
    # predefine filtered flows list
    flows_filtered = []

    def _iface_to_str(iface):
        if int(iface) in ifaces:
            return ifaces[int(iface)]
        return 'unknown'

    # add interface names to flows
    for flow in flows:
        flow['iface_in_name'] = _iface_to_str(flow['dev']['i'])
        flow['iface_out_name'] = _iface_to_str(flow['dev']['o'])

    # iterate through flows list
    for flow in flows:
        # filter by interface
        if cmd_args.interface:
            if flow['iface_in_name'] != cmd_args.interface:
                continue
        # filter by host
        if cmd_args.host:
            if (
                flow['src']['ip'] != cmd_args.host
                and flow['dst']['ip'] != cmd_args.host
            ):
                continue
        # filter by ports
        if cmd_args.ports:
            # for 'single' it is a tuple with one value, for 'list' - list of ports, for range - range of ports
            if (
                int(flow['src']['port']) not in cmd_args.ports['values']
                and int(flow['dst']['port']) not in cmd_args.ports['values']
            ):
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
    # define headers and body
    table_headers = [
        'IN_IFACE',
        'SRC_MAC',
        'DST_MAC',
        'SRC_IP',
        'DST_IP',
        'SRC_PORT',
        'DST_PORT',
        'PROTOCOL',
        'TOS',
        'PACKETS',
        # 'FLOWS', # What was here in pmacct?
        'BYTES',
    ]
    table_body = []
    # convert flows to list
    for flow in flows:
        table_line = [
            flow.get('iface_in_name'),
            flow.get('mac', {}).get('src'),
            flow.get('mac', {}).get('dst'),
            flow.get('src', {}).get('ip'),
            flow.get('dst', {}).get('ip'),
            flow.get('src', {}).get('port'),
            flow.get('dst', {}).get('port'),
            flow.get('proto'),
            flow.get('extra', {}).get('tos'),
            flow.get('packets'),
            # flow.get('flows'),
            flow.get('bytes'),
        ]
        table_body.append(table_line)
    # configure and fill table
    table = tabulate(table_body, table_headers, tablefmt="simple")

    # print formatted table
    try:
        print(table)
    except IOError:
        sys.exit(0)
    except KeyboardInterrupt:
        sys.exit(0)


# define program arguments
cmd_args_parser = argparse.ArgumentParser(description='show flow-accounting')
# 'clear' and 'restart' are not implemented
cmd_args_parser.add_argument(
    '--action',
    choices=['show', 'restart'],
    default='show',
    help='show stat or restart module',
)
cmd_args_parser.add_argument(
    '--filter',
    choices=['interface', 'host', 'ports', 'top'],
    required=False,
    nargs='*',
    help='filter flows to display',
)
cmd_args_parser.add_argument(
    '--interface', required=False, help='interface name for output filtration'
)
cmd_args_parser.add_argument(
    '--host', type=str, required=False, help='host address for output filtering'
)
cmd_args_parser.add_argument(
    '--ports',
    type=str,
    required=False,
    help='port number, range or list for output filtering',
)
cmd_args_parser.add_argument(
    '--top', type=int, required=False, help='top records for output filtering'
)
# parse arguments
cmd_args = cmd_args_parser.parse_args()

try:
    if cmd_args.host:
        check_host(cmd_args.host)

    if cmd_args.ports:
        cmd_args.ports = parse_ports(cmd_args.ports)
except ValueError as e:
    print(e)
    sys.exit(1)

# main logic
# do nothing if ipt_NETFLOW is not active
if not _netflow_running():
    print("flow-accounting is not active")
    sys.exit(1)

# show table with flows
if cmd_args.action == 'show':
    # get interfaces index and names
    ifaces_dict = _get_ifaces_dict()
    # get flows
    flows_list = _get_flows_list()

    # filter and format flows
    tabledata = _flows_filter(flows_list, ifaces_dict)

    # print flows
    _flows_table_print(tabledata)

if cmd_args.action == 'restart':
    ipt_netflow.stop()

    # get needed interfaces
    conf = ConfigTreeQuery()
    config_path = ['system', 'flow-accounting']
    if not conf.exists(config_path + ['netflow', 'interface']):
        print("Flow accounting not configured, exiting")
        sys.exit(1)

    ingress_interfaces = conf.values(config_path + ['netflow', 'interface'])
    if conf.exists(config_path + ['enable-egress']):
        egress_interfaces = ingress_interfaces
    else:
        egress_interfaces = []

    ipt_netflow.start(ingress_interfaces, egress_interfaces)

sys.exit(0)
