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

import argparse
import atexit
import json
import signal
import time

from collections import namedtuple
from vyos.template import get_dhcp_router
from vyos.utils.process import rc_cmd
from vyos.utils.process import run
from pathlib import Path
from systemd import journal


my_name = Path(__file__).stem

# Timeout between configuration reading
# When no checks timeouts worked (e.g. no config files)
config_timeout = 1

# Useful debug info to console, use debug = True
# sudo systemctl stop vyos-failover.service
# sudo /usr/libexec/vyos/vyos-failover.py --config /run/vyos-failover.conf
debug = False
debug_output_journal = False
debug_output_print = True


def print_debug(*args, **kwargs):
    if debug:
        if debug_output_print:
            print(*args, **kwargs)
        if debug_output_journal:
            journal.send(*args, **kwargs, SYSLOG_IDENTIFIER=my_name)


def wrap_vrf(command, vrf):
    if not vrf:
        return command
    return f"sudo ip vrf exec {vrf} {command}"


def is_route_exists(ip_args):
    """Check if route with expected gateway, dev and metric exists"""
    rc, data = rc_cmd(f'ip --json route show {ip_args}')
    if rc == 0:
        data = json.loads(data)
        if len(data) > 0:
            return True
    return False


def is_port_open(ip, port, vrf=''):
    """
    Check connection to remote host and port
    Return True if host alive

    % is_port_open('example.com', 8080)
    True
    """
    cmd = wrap_vrf(f"nc -w2 -z {ip} {port}", vrf)
    rc, data = rc_cmd(cmd)
    return rc == 0


def is_target_alive(
    targets=None,
    iface='',
    proto='icmp',
    port=None,
    nexthop_vrf='',
    policy='any-available',
) -> bool:
    """Check the availability of each target in the target_dict using
    the specified protocol ICMP, ARP, TCP

    Args:
        targets (tuple of TargetNamedTuple): A dict: keys are IP addresses to check, values - dicts with options.
            Possible keys (all optional): 'vrf' and 'interface'.
        iface (str): The name of the network interface to use for the check.
        proto (str): The protocol to use for the check. Options are 'icmp', 'arp', or 'tcp'.
        port (int): The port number to use for the TCP check. Only applicable if proto is 'tcp'.
        nexthop_vrf (str): Nexthop VRF name - if specific vrf is not given for target, use this one
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
    for options in targets:
        target = options.target
        vrf = options.vrf if options.vrf else nexthop_vrf
        # don't use nexthop interface if 'vrf' is given
        iface_opt = iface if vrf == nexthop_vrf else ''
        # in any case if 'interface' is given, use it
        if options.interface:
            iface_opt = f'-I {options.interface}'
        match proto:
            case 'icmp':
                command = f'/usr/bin/ping -q {target} {iface_opt} -n -c 2 -W 1'
                command = wrap_vrf(command, vrf)
                rc, response = rc_cmd(command)
                print_debug(
                    f'    [ CHECK-TARGET ]: [{command}] -- return-code [RC: {rc}]'
                )
                if rc == 0:
                    num_reachable_targets += 1
                    if policy == 'any-available':
                        return True

            case 'arp':
                command = f'/usr/bin/arping -b -c 2 -f -w 1 -i 1 {iface_opt} {target}'
                command = wrap_vrf(command, vrf)
                rc, response = rc_cmd(command)
                print_debug(
                    f'    [ CHECK-TARGET ]: [{command}] -- return-code [RC: {rc}]'
                )
                if rc == 0:
                    num_reachable_targets += 1
                    if policy == 'any-available':
                        return True

            case _ if proto == 'tcp' and port is not None:
                if is_port_open(target, port, vrf=vrf):
                    num_reachable_targets += 1
                    if policy == 'any-available':
                        return True

            case _:
                return False

        if policy == 'all-available' and num_reachable_targets == len(targets):
            return True

    return False


TargetNamedTuple = namedtuple(
    'TargetConfig',
    [
        'target',
        'vrf',
        'interface',
    ],
)

NextHopNamedTuple = namedtuple(
    'NextHopConfig',
    [
        'route',
        'dhcp_interface',
        'next_hop',
        'vrf',
        'vrf_opt',
        'conf_iface',
        'conf_metric',
        'port',
        'port_opt',
        'policy',
        'proto',
        'targets',
        'pretty_targets',
        'timeout',
        'onlink',
    ],
)


def get_nexthop_config_vars(
    destination, vrf, vrf_opt, nexthop_config, next_hop, dhcp_interface
):
    port = nexthop_config.get('check').get('port')

    targets = tuple(
        TargetNamedTuple(
            target=target,
            vrf=target_config.get('vrf', None),
            interface=target_config.get('interface', None),
        )
        for target, target_config in nexthop_config.get('check').get('target').items()
    )

    # for print to journal and debug
    pretty_targets = []
    for target in targets:
        p = target.target
        options = []
        if target.vrf:
            options.append(f"vrf: {target.vrf}")
        if target.interface:
            options.append(f"interface: {target.interface}")
        if options:
            p += ' (' + ', '.join(options) + ')'
        pretty_targets.append(p)
    pretty_targets = ', '.join(pretty_targets)

    return NextHopNamedTuple(
        route=destination,
        dhcp_interface=dhcp_interface,
        next_hop=next_hop,
        vrf=vrf,
        vrf_opt=vrf_opt,
        # For next-hop interface is mandatory
        # For dhcp-interface it may be not given, then dhcp-interface is used
        conf_iface=nexthop_config.get('interface', dhcp_interface),
        conf_metric=int(nexthop_config.get('metric')),
        port=port,
        port_opt=f'port {port}' if port else '',
        policy=nexthop_config.get('check').get('policy'),
        proto=nexthop_config.get('check').get('type'),
        targets=targets,
        pretty_targets=pretty_targets,
        timeout=nexthop_config.get('check').get('timeout'),
        onlink='onlink' if 'onlink' in nexthop_config else '',
    )


RouteNamedTuple = namedtuple(
    'RouteConfig',
    [
        'destination',
        'vrf',
        'vrf_opt',
        'config_path',
        'nexthops',
    ],
)


def get_route_config(route, route_config, config_path, vrf):
    vrf_opt = f'vrf {vrf}' if vrf else ''
    nexthops = []
    if route_config.get('next_hop'):
        nexthops.extend(
            get_nexthop_config_vars(route, vrf, vrf_opt, nexthop_config, next_hop, None)
            for next_hop, nexthop_config in route_config.get('next_hop').items()
        )
    if route_config.get('dhcp_interface'):
        nexthops.extend(
            get_nexthop_config_vars(
                route, vrf, vrf_opt, dhcp_nexthop_config, None, interface
            )
            for interface, dhcp_nexthop_config in route_config.get(
                'dhcp_interface'
            ).items()
        )
    nexthops = tuple(nexthops)
    return RouteNamedTuple(
        destination=route,
        vrf=vrf,
        vrf_opt=vrf_opt,
        config_path=config_path,
        nexthops=nexthops,
    )


def parse_config(config, path):
    parsed = []
    vrf = config.get('vrf_context', '')
    for route, route_config in config.get('route').items():
        parsed.append(get_route_config(route, route_config, path, vrf))
    return parsed


def flush_all_routes():
    print_debug("flush_all_routes called")
    flush_cmd = 'ip route flush protocol failover table all'
    run(flush_cmd)
    journal.send(
        flush_cmd,
        SYSLOG_IDENTIFIER=my_name,
    )


kill_called = False


def kill_handler(*args):
    global kill_called
    if kill_called:
        return
    kill_called = True
    print_debug(f"kill_handler called for signal {args[0]}")


def get_ip_command_args(nhc):
    return (
        f'{nhc.route} via {nhc.next_hop} dev {nhc.conf_iface} '
        f'{nhc.onlink} metric {nhc.conf_metric} {nhc.vrf_opt} proto failover'
    )


def delete_route(ip_args):
    print_debug(f'    [ DEL ] -- ip route del {ip_args} [DELETE]')
    rc_cmd(f'ip route del {ip_args}')
    journal.send(
        f'ip route del {ip_args}',
        SYSLOG_IDENTIFIER=my_name,
    )


def update_configuration(last_modification_times, all_routes, config_dir):
    """
    Updates configuration:
        rechecks config_dir for new/updated files,
        deletes routes that were deleted from configuration

    Args:
        last_modification_times(dict): keys: relative path to file, value: last modification time.
            Is updated.
        all_routes(list): list of routes that were configured in previous call.
            Is updated.
        config_dir(Path): path to configuration directory
    """

    try:
        # First check if there are any changes at all
        have_changes = False
        for child in config_dir.iterdir():
            file_key = str(child)
            if file_key not in last_modification_times:
                have_changes = True
                print_debug(f"New file '{child}', have changes, rereading all")
                break
            modtime = child.stat().st_mtime_ns
            if modtime != last_modification_times[file_key]:
                have_changes = True
                print_debug(f"File '{child} modified, have changes, rereading all...")
                break

        if not have_changes:
            print_debug("No changes in configuration detected.")
            return

        last_modification_times.clear()
        new_routes = []

        # It is important that in configuration directory there MUST be
        # only files generated by conf_mode/protocols_failover.py - otherwise
        # the script won't be able to detect when all VRFs are disabled and
        # won't be able to stop the service gracefully
        for child in config_dir.iterdir():
            if not child.is_file():
                print(
                    f"Path {child} under configuration dir is not a file! Please clean configuration directory {config_dir}."
                )
                exit(1)

            modtime = child.stat().st_mtime_ns
            file_key = str(child)
            last_modification_times[file_key] = modtime

            try:
                config = json.loads(child.read_text())
                print_debug(f"Config from '{child}': {config}")
            except OSError as err:
                print(f'Configuration file "{child}" could not be read: {err}')
                exit(1)
            except json.JSONDecodeError as err:
                print(
                    f'Configuration file "{child}" could not be parsed as JSON: {err}'
                )
                exit(1)
            except UnicodeDecodeError as err:
                print(f'Configuration file "{child}" has Unicode errors: {err}')
                exit(1)

            parsed_config = parse_config(config, file_key)
            new_routes.extend(parsed_config)
    except OSError as err:
        print(f'Configuration dir "{config_dir}" does not exist or not readable: {err}')
        exit(1)

    old_routes_set = set(all_routes)
    new_routes_set = set(new_routes)

    delete_routes = old_routes_set - new_routes_set
    add_routes = new_routes_set - old_routes_set

    # Delete not needed routes
    for route_config in delete_routes:
        print_debug(
            f"Deleting route {route_config}, not present in updated configuration"
        )
        for nhc in route_config.nexthops:
            ip_args = get_ip_command_args(nhc)
            if is_route_exists(ip_args):
                delete_route(ip_args)
        all_routes.remove(route_config)

    # Add new routes
    print_debug(f"Adding routes {add_routes}, new in updated configuration")
    all_routes.extend(add_routes)

    print_debug(f"All routes: {all_routes}")


def process_dhcp_interface(nhc, nexthop_by_dhcp_nexthop):
    """
    Processes NextHopNamedTuple with dhcp_interface != None
    Return NextHopNamedTuple with next_hop equal to DHCP gateway of nhc.
        If there is no gateway for nhc, return None

    Args:
        nhc(NextHopNamedTuple): configuration with dhcp_interface
        nexthop_by_dhcp_nexthop(dict): dict with previous returned values
    """
    cur_dhcpgw = get_dhcp_router(nhc.dhcp_interface)
    if not cur_dhcpgw:
        cur_dhcpgw = False

    if nhc in nexthop_by_dhcp_nexthop:
        prev_dhcpgw = nexthop_by_dhcp_nexthop[nhc].next_hop
    else:
        prev_dhcpgw = False

    # Equal - do nothing, just return previous value
    if prev_dhcpgw == cur_dhcpgw:
        if not cur_dhcpgw:
            return None
        return nexthop_by_dhcp_nexthop[nhc]

    print_debug(
        f"DHCP Gateway changed for interface {nhc.dhcp_interface} from '{prev_dhcpgw}' to '{cur_dhcpgw}'"
    )

    # dhcpgw differ and there was previous dhcpgw
    if prev_dhcpgw:
        prevnhc = nexthop_by_dhcp_nexthop.pop(nhc)
        print_debug(
            f"Deleting previous nexthop {prevnhc} because of DHCP interface change"
        )
        ip_args = get_ip_command_args(prevnhc)
        if is_route_exists(ip_args):
            delete_route(ip_args)

    newnhc = None
    # dhcpgw differ and there is new dhcpgw
    if cur_dhcpgw:
        newnhc = nhc._replace(next_hop=cur_dhcpgw, dhcp_interface=None)
        print_debug(f"Saving new nexthop {newnhc} because of DHCP interface change")
        nexthop_by_dhcp_nexthop[nhc] = newnhc

    return newnhc


if __name__ == '__main__':
    print_debug(f"{my_name} started")

    # Parse command arguments and get config
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-c',
        '--config-dir',
        action='store',
        help='Path to protocols failover configuration dir',
        required=True,
        type=Path,
    )

    args = parser.parse_args()
    config_dir = Path(args.config_dir)

    last_modification_times = {}
    all_routes = []


    # Clean all `failover` routes now and at exit
    flush_all_routes()
    atexit.register(flush_all_routes)
    signal.signal(signal.SIGINT, kill_handler)
    signal.signal(signal.SIGTERM, kill_handler)

    # keys: NextHopNamedTuple with dhcp_interface != None
    # values: NextHopNamedTuple with next_hop != None
    # Translates nexthop with dhcp_interface to ususal nexthop
    nexthop_by_dhcp_nexthop = {}

    had_sleeps = True
    while not kill_called:
        # Check in case daemon was launched without routes
        if not had_sleeps:
            time.sleep(int(config_timeout))

        update_configuration(last_modification_times, all_routes, config_dir)
        had_sleeps = False

        for route_config in all_routes:
            if kill_called:
                break
            route = route_config.destination
            vrf = route_config.vrf
            vrf_opt = route_config.vrf_opt

            for nhc in route_config.nexthops:
                if nhc.dhcp_interface:
                    nhc = process_dhcp_interface(nhc, nexthop_by_dhcp_nexthop)
                    if not nhc:
                        continue

                next_hop = nhc.next_hop
                ip_args = get_ip_command_args(nhc)

                is_alive = is_target_alive(
                    nhc.targets,
                    nhc.conf_iface,
                    nhc.proto,
                    nhc.port,
                    nexthop_vrf=vrf,
                    policy=nhc.policy,
                )

                # Route not found in the current routing table
                if not is_route_exists(ip_args):
                    print_debug(f"    [NEW_ROUTE_DETECTED] route: [{route} {vrf_opt}]")
                    # Add route if check-target alive
                    if is_alive:
                        print_debug(f'    [ ADD ] -- ip route add {ip_args}\n###')
                        rc, command = rc_cmd(f'ip route add {ip_args}')
                        # If something is wrong and gateway not added
                        # Example: Error: Next-hop has invalid gateway.
                        if rc != 0:
                            print_debug(
                                f'{command} -- return-code [RC: {rc}] {next_hop} dev {nhc.conf_iface}'
                            )
                        else:
                            journal.send(
                                f'ip route add {ip_args}',
                                SYSLOG_IDENTIFIER=my_name,
                            )
                    else:
                        print_debug(
                            f'    [ TARGET_FAIL ] target checks fails for [{nhc.pretty_targets}], do nothing'
                        )
                        journal.send(
                            f'Check fail for route {route} interface "{nhc.conf_iface}" target {nhc.pretty_targets} proto {nhc.proto} '
                            f'{nhc.port_opt}',
                            SYSLOG_IDENTIFIER=my_name,
                        )
                else:
                    # Route was added, check if the target is alive
                    # We should delete route if check fails only if route exists in the routing table
                    if not is_alive:
                        print_debug(
                            f"Next_hop {next_hop} fail, target check didn't pass"
                        )
                        delete_route(ip_args)

                had_sleeps = True
                time.sleep(int(nhc.timeout))
                if kill_called:
                    break

    print_debug(f"Out of main loop, {kill_called=}")
