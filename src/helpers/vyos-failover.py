#!/usr/bin/env python3
#
# Copyright (C) 2022-2024 VyOS maintainers and contributors
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

import argparse
import json
import socket
import time

from vyos.utils.process import rc_cmd
from pathlib import Path
from systemd import journal


my_name = Path(__file__).stem


def is_route_exists(route, gateway, interface, metric):
    """Check if route with expected gateway, dev and metric exists"""
    rc, data = rc_cmd(f'ip --json route show protocol failover {route} '
                      f'via {gateway} dev {interface} metric {metric}')
    if rc == 0:
        data = json.loads(data)
        if len(data) > 0:
            return True
    return False


def get_best_route_options(route, debug=False):
    """
    Return current best route ('gateway, interface, metric)

    % get_best_route_options('203.0.113.1')
    ('192.168.0.1', 'eth1', 1)

    % get_best_route_options('203.0.113.254')
    (None, None, None)
    """
    rc, data = rc_cmd(f'ip --detail --json route show protocol failover {route}')
    if rc == 0:
        data = json.loads(data)
        if len(data) == 0:
            print(f'\nRoute {route} for protocol failover was not found')
            return None, None, None
        # Fake metric 999 by default
        # Search route with the lowest metric
        best_metric = 999
        for entry in data:
            if debug: print('\n', entry)
            metric = entry.get('metric')
            gateway = entry.get('gateway')
            iface = entry.get('dev')
            if metric < best_metric:
                best_metric = metric
                best_gateway = gateway
                best_interface = iface
        if debug:
            print(f'### Best_route exists: {route}, best_gateway: {best_gateway}, '
                  f'best_metric: {best_metric}, best_iface: {best_interface}')
        return best_gateway, best_interface, best_metric


def is_port_open(ip, port):
    """
    Check connection to remote host and port
    Return True if host alive

    % is_port_open('example.com', 8080)
    True
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
    s.settimeout(2)
    try:
        s.connect((ip, int(port)))
        s.shutdown(socket.SHUT_RDWR)
        return True
    except:
        return False
    finally:
        s.close()


def is_target_alive(target_list=None,
                    iface='',
                    proto='icmp',
                    port=None,
                    debug=False,
                    policy='any-available') -> bool:
    """Check the availability of each target in the target_list using
    the specified protocol ICMP, ARP, TCP

    Args:
        target_list (list): A list of IP addresses or hostnames to check.
        iface (str): The name of the network interface to use for the check.
        proto (str): The protocol to use for the check. Options are 'icmp', 'arp', or 'tcp'.
        port (int): The port number to use for the TCP check. Only applicable if proto is 'tcp'.
        debug (bool): If True, print debug information during the check.
        policy (str): The policy to use for the check. Options are 'any-available' or 'all-available'.

    Returns:
        bool: True if all targets are reachable according to the policy, False otherwise.

    Example:
        % is_target_alive(['192.0.2.1', '192.0.2.5'], 'eth1', proto='arp', policy='all-available')
        True
    """
    if iface != '':
        iface = f'-I {iface}'

    num_reachable_targets = 0
    for target in target_list:
        match proto:
            case 'icmp':
                command = f'/usr/bin/ping -q {target} {iface} -n -c 2 -W 1'
                rc, response = rc_cmd(command)
                if debug:
                    print(f'    [ CHECK-TARGET ]: [{command}] -- return-code [RC: {rc}]')
                if rc == 0:
                    num_reachable_targets += 1
                    if policy == 'any-available':
                        return True

            case 'arp':
                command = f'/usr/bin/arping -b -c 2 -f -w 1 -i 1 {iface} {target}'
                rc, response = rc_cmd(command)
                if debug:
                    print(f'    [ CHECK-TARGET ]: [{command}] -- return-code [RC: {rc}]')
                if rc == 0:
                    num_reachable_targets += 1
                    if policy == 'any-available':
                        return True

            case _ if proto == 'tcp' and port is not None:
                if is_port_open(target, port):
                    num_reachable_targets += 1
                    if policy == 'any-available':
                        return True

            case _:
                return False

        if policy == 'all-available' and num_reachable_targets == len(target_list):
            return True

    return False


if __name__ == '__main__':
    # Parse command arguments and get config
    parser = argparse.ArgumentParser()
    parser.add_argument('-c',
                        '--config',
                        action='store',
                        help='Path to protocols failover configuration',
                        required=True,
                        type=Path)

    args = parser.parse_args()
    try:
        config_path = Path(args.config)
        config = json.loads(config_path.read_text())
    except Exception as err:
        print(
            f'Configuration file "{config_path}" does not exist or malformed: {err}'
        )
        exit(1)

    # Useful debug info to console, use debug = True
    # sudo systemctl stop vyos-failover.service
    # sudo /usr/libexec/vyos/vyos-failover.py --config /run/vyos-failover.conf
    debug = False

    while(True):

        for route, route_config in config.get('route').items():

            exists_gateway, exists_iface, exists_metric =  get_best_route_options(route, debug=debug)

            for next_hop, nexthop_config in route_config.get('next_hop').items():
                conf_iface = nexthop_config.get('interface')
                conf_metric = int(nexthop_config.get('metric'))
                port = nexthop_config.get('check').get('port')
                port_opt = f'port {port}' if port else ''
                policy = nexthop_config.get('check').get('policy')
                proto = nexthop_config.get('check').get('type')
                target = nexthop_config.get('check').get('target')
                timeout = nexthop_config.get('check').get('timeout')
                onlink = 'onlink' if 'onlink' in nexthop_config else ''

                # Route not found in the current routing table
                if not is_route_exists(route, next_hop, conf_iface, conf_metric):
                    if debug: print(f"    [NEW_ROUTE_DETECTED] route: [{route}]")
                    # Add route if check-target alive
                    if is_target_alive(target, conf_iface, proto, port, debug=debug, policy=policy):
                        if debug: print(f'    [ ADD ] -- ip route add {route} via {next_hop} dev {conf_iface} '
                                        f'metric {conf_metric} proto failover\n###')
                        rc, command = rc_cmd(f'ip route add {route} via {next_hop} dev {conf_iface} '
                                             f'{onlink} metric {conf_metric} proto failover')
                        # If something is wrong and gateway not added
                        # Example: Error: Next-hop has invalid gateway.
                        if rc !=0:
                            if debug: print(f'{command} -- return-code [RC: {rc}] {next_hop} dev {conf_iface}')
                        else:
                            journal.send(f'ip route add {route} via {next_hop} dev {conf_iface} '
                                         f'{onlink} metric {conf_metric} proto failover', SYSLOG_IDENTIFIER=my_name)
                    else:
                        if debug: print(f'    [ TARGET_FAIL ] target checks fails for [{target}], do nothing')
                        journal.send(f'Check fail for route {route} target {target} proto {proto} '
                                     f'{port_opt}', SYSLOG_IDENTIFIER=my_name)

                # Route was added, check if the target is alive
                # We should delete route if check fails only if route exists in the routing table
                if not is_target_alive(target, conf_iface, proto, port, debug=debug, policy=policy) and \
                        is_route_exists(route, next_hop, conf_iface, conf_metric):
                    if debug:
                        print(f'Nexh_hop {next_hop} fail, target not response')
                        print(f'    [ DEL ] -- ip route del {route} via {next_hop} dev {conf_iface} '
                              f'metric {conf_metric} proto failover [DELETE]')
                    rc_cmd(f'ip route del {route} via {next_hop} dev {conf_iface} metric {conf_metric} proto failover')
                    journal.send(f'ip route del {route} via {next_hop} dev {conf_iface} '
                                 f'metric {conf_metric} proto failover', SYSLOG_IDENTIFIER=my_name)

                time.sleep(int(timeout))
