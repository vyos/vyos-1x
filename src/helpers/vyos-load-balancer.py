#!/usr/bin/python3

# Copyright 2024 VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

import json
import os
import signal
import sys
import time

from vyos.config import Config
from vyos.template import render
from vyos.utils.commit import commit_in_progress
from vyos.utils.network import get_interface_address
from vyos.utils.process import run
from vyos.xml_ref import get_defaults
from vyos.wanloadbalance import health_ping_host
from vyos.wanloadbalance import health_ping_host_ttl
from vyos.wanloadbalance import parse_dhcp_nexthop

nftables_wlb_conf = '/run/nftables_wlb.conf'
wlb_status_file = '/run/wlb_status.json'
wlb_pid_file = '/run/wlb_daemon.pid'
sleep_interval = 5 # Main loop sleep interval

def health_check(ifname, conf, state, test_defaults):
    # Run health tests for interface

    if 'test' not in conf:
        resp_time = test_defaults['resp-time']
        target = conf['nexthop']

        if target == 'dhcp':
            target = state['dhcp_nexthop']

        if not target:
            return False

        return health_ping_host(target, ifname, wait_time=resp_time)

    for test_id, test_conf in conf['test'].items():
        check_type = test_conf['type']

        if check_type == 'ping':
            resp_time = test_conf['resp_time']
            target = test_conf['target']
            if not health_ping_host(target, ifname, wait_time=resp_time):
                return False
        elif check_type == 'ttl':
            target = test_conf['target']
            ttl_limit = test_conf['ttl_limit']
            if not health_ping_host_ttl(target, ifname, ttl_limit=ttl_limit):
                return False
        elif check_type == 'user-defined':
            script = test_conf['test_script']
            rc = run(script)
            if rc != 0:
                return False

    return True

def on_state_change(lb, ifname, state):
    # Run hook on state change
    if 'hook' in lb:
        script_path = os.path.join('/config/scripts/', lb['hook'])
        state_str = 'ACTIVE' if state else 'FAILED'
        run(script_path, env=[f'WLB_INTERFACE_NAME={ifname}', f'WLB_INTERFACE_STATE={state_str}'])

    print(f'INFO: State change: {ifname} -> {state}')

def get_ipv4_address(ifname):
    # Get primary ipv4 address on interface (for source nat)
    addr_json = get_interface_address(ifname)
    if 'addr_info' in addr_json and len(addr_json['addr_info']) > 0:
        for addr_info in addr_json['addr_info']:
            if addr_info['family'] == 'inet':
                if 'local' in addr_info:
                    return addr_json['addr_info'][0]['local']
    return None

def dhcp_update(lb, ifname):
    # Update on DHCP address/nexthop changes

    if 'dhcp_nexthop' in lb['health_state'][ifname]:
        dhcp_nexthop_addr = parse_dhcp_nexthop(ifname)
        table_num = lb['health_state'][ifname]['table_number']

        if dhcp_nexthop_addr and lb['health_state'][ifname]['dhcp_nexthop'] != dhcp_nexthop_addr:
            lb['health_state'][ifname]['dhcp_nexthop'] = dhcp_nexthop_addr
            run(f'ip route replace table {table_num} default dev {ifname} via {dhcp_nexthop_addr}')

    if_addr = get_ipv4_address(ifname)
    if if_addr and if_addr != lb['health_state'][ifname]['if_addr']:
        lb['health_state'][ifname]['if_addr'] = if_addr
        nftables_update(lb)

def nftables_update(lb):
    # Atomically reload nftables table from template
    if not os.path.exists(nftables_wlb_conf):
        lb['first_install'] = True
    elif 'first_install' in lb:
        del lb['first_install']

    render(nftables_wlb_conf, 'load-balancing/nftables-wlb.j2', lb)

    rc = run(f'nft -f {nftables_wlb_conf}')

    if rc != 0:
        print('ERROR: Failed to apply WLB nftables config')
        return False

    return True

def get_config():
    conf = Config()
    base = ['load-balancing', 'wan']
    lb = conf.get_config_dict(base, key_mangling=('-', '_'),
                            get_first_key=True, with_recursive_defaults=True)

    lb['test_defaults'] = get_defaults(base + ['interface-health', 'A', 'test', 'B'], get_first_key=True)

    return lb

if __name__ == '__main__':
    while commit_in_progress():
        print("Notice: Waiting for commit to complete...")
        time.sleep(1)

    lb = get_config()

    lb['health_state'] = {}
    lb['mark_offset'] = 0xc8

    # Create state dicts, interface address and nexthop, install routes and ip rules
    if 'interface_health' in lb:
        index = 1
        for ifname, health_conf in lb['interface_health'].items():
            table_num = lb['mark_offset'] + index
            lb['health_state'][ifname] = {
                'if_addr': get_ipv4_address(ifname),
                'failure_count': 0,
                'success_count': 0,
                'last_success': 0,
                'last_failure': 0,
                'state': True,
                'state_changed': False,
                'table_number': table_num,
                'mark': hex(table_num)
            }

            if health_conf['nexthop'] == 'dhcp':
                dhcp_nexthop_addr = parse_dhcp_nexthop(ifname)
                if dhcp_nexthop_addr:
                    lb['health_state'][ifname]['dhcp_nexthop'] = dhcp_nexthop_addr
                    run(f'ip route replace table {table_num} default dev {ifname} via {dhcp_nexthop_addr}')
            else:
                run(f'ip route replace table {table_num} default dev {ifname} via {health_conf["nexthop"]}')

            run(f'ip route delete table {table_num}')
            run(f'ip rule add fwmark {hex(table_num)} table {table_num}')

            index += 1

        nftables_update(lb)

        run('ip route flush cache')

        if 'flush_connections' in lb:
            run('conntrack -F')
            run('conntrack -F expect')

        with open(wlb_status_file, 'w') as f:
            f.write(json.dumps(lb['health_state']))

    # Signal handler SIGUSR2 -> dhcpcd update
    def handle_sigusr2(signum, frame):
        for ifname, health_conf in lb['interface_health'].items():
            if 'nexthop' in health_conf and health_conf['nexthop'] == 'dhcp':
                dhcp_update(lb, ifname)

    # Signal handler SIGTERM -> exit
    def handle_sigterm(signum, frame):
        if os.path.exists(wlb_status_file):
            os.unlink(wlb_status_file)

        if os.path.exists(wlb_pid_file):
            os.unlink(wlb_pid_file)

        sys.exit(0)

    signal.signal(signal.SIGUSR2, handle_sigusr2)
    signal.signal(signal.SIGTERM, handle_sigterm)

    with open(wlb_pid_file, 'w') as f:
        f.write(str(os.getpid()))

    # Main loop
    while True:
        if 'interface_health' in lb:
            for ifname, health_conf in lb['interface_health'].items():
                state = lb['health_state'][ifname]

                result = health_check(ifname, health_conf, state=state, test_defaults=lb['test_defaults'])

                state_changed = result != state['state']
                state['state_changed'] = False

                if result:
                    state['failure_count'] = 0
                    state['success_count'] += 1
                    state['last_success'] = time.time()
                    if state_changed and state['success_count'] >= int(health_conf['success_count']):
                        state['state'] = True
                        state['state_changed'] = True
                elif not result:
                    state['failure_count'] += 1
                    state['success_count'] = 0
                    state['last_failure'] = time.time()
                    if state_changed and state['failure_count'] >= int(health_conf['failure_count']):
                        state['state'] = False
                        state['state_changed'] = True

                if state['state_changed']:
                    state['if_addr'] = get_ipv4_address(ifname)
                    on_state_change(lb, ifname, state['state'])

                if health_conf['nexthop'] == 'dhcp':
                    dhcp_update(lb, ifname)

        if any(state['state_changed'] for ifname, state in lb['health_state'].items()):
            if not nftables_update(lb):
                break

            run('ip route flush cache')

            if 'flush_connections' in lb:
                run('conntrack -F')
                run('conntrack -F expect')

            with open(wlb_status_file, 'w') as f:
                f.write(json.dumps(lb['health_state']))

        time.sleep(sleep_interval)

    if os.path.exists(wlb_status_file):
        os.unlink(wlb_status_file)

    if os.path.exists(wlb_pid_file):
        os.unlink(wlb_pid_file)
