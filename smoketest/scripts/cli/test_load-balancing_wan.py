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

import json
import os
import select
import subprocess
import threading
import tempfile
import unittest
import time

from base_vyostest_shim import VyOSUnitTestSHIM
from vyos.configsession import ConfigSessionError
from vyos.utils.file import chmod_755
from vyos.utils.file import write_file
from vyos.utils.misc import wait_for
from vyos.utils.process import call
from vyos.utils.process import cmdl
from vyos.utils.process import rc_cmd

base_path = ['load-balancing']

def create_netns(name):
    return call(f'sudo ip netns add {name}')

def create_veth_pair(local='veth0', peer='ceth0'):
    return call(f'sudo ip link add {local} type veth peer name {peer}')

def move_interface_to_netns(iface, netns_name):
    return call(f'sudo ip link set {iface} netns {netns_name}')

def rename_interface(iface, new_name):
    return call(f'sudo ip link set {iface} name {new_name}')

def cmd_in_netns(netns, cmd):
    return call(f'sudo ip netns exec {netns} {cmd}')

def delete_netns(name):
    return call(f'sudo ip netns del {name}')

# Traffic lab: a LAN namespace and one namespace per ISP, all connected to
# the router by veth pairs. Every ISP owns the same "internet" address and
# answers with its name and the source address it sees.
lab_target = '198.51.100.10'

def wlb_status():
    try:
        with open('/run/wlb_status.json') as f:
            return {ifname: 'ACTIVE' if state['state'] else 'FAILED'
                    for ifname, state in json.load(f).items()}
    except (OSError, ValueError):
        return {}

def wlb_chain(chain):
    # rules are installed by the health daemon once the commit has finished
    rc, out = rc_cmd(f'sudo nft list chain ip vyos_wanloadbalance {chain}')
    return out if rc == 0 else ''

class TestLoadBalancingWan(VyOSUnitTestSHIM.TestCase):
    def lab_setup(self, lan, isps):
        """ Create the LAN namespace behind interface lan and one ISP
        namespace per interface in isps. ISP n is 10.250.n.2, the router
        uses 10.250.n.1 and 10.250.0.1 towards the LAN hosts 10.250.0.2/3. """
        def add_ns(ns, ifname, local, peer):
            create_netns(ns)
            create_veth_pair(ifname, f'{ns}-p')
            move_interface_to_netns(f'{ns}-p', ns)
            cmd_in_netns(ns, f'ip link set {ns}-p name eth0')
            cmd_in_netns(ns, 'ip link set lo up')
            cmd_in_netns(ns, 'ip link set eth0 up')
            for address in peer:
                cmd_in_netns(ns, f'ip addr add {address}/24 dev eth0')
            call(f'sudo ip addr add {local}/24 dev {ifname}')
            call(f'sudo ip link set {ifname} up')
            # cleanups run in reverse: echo services, veth pair, namespace
            self.addCleanup(delete_netns, ns)
            self.addCleanup(call, f'sudo ip link del {ifname}')
            self.addCleanup(call, f'sudo ip netns pids {ns} | xargs -r sudo kill')

        add_ns('wlb-lan', lan, '10.250.0.1', ['10.250.0.2', '10.250.0.3'])
        cmd_in_netns('wlb-lan', 'ip route add default via 10.250.0.1')
        for index, ifname in enumerate(isps, start=1):
            ns = f'wlb-isp{index}'
            add_ns(ns, ifname, f'10.250.{index}.1', [f'10.250.{index}.2'])
            cmd_in_netns(ns, f'ip addr add {lab_target}/32 dev lo')
            # port 80 answers and closes, port 90 echoes for long-lived flows
            for port, reply in [('80', f'SYSTEM:echo isp{index} peer=$SOCAT_PEERADDR'), ('90', 'EXEC:cat')]:
                server = subprocess.Popen(['sudo', 'ip', 'netns', 'exec', ns, 'socat',
                                           f'TCP-LISTEN:{port},fork,reuseaddr', reply],
                                          start_new_session=True,
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.addCleanup(self.lab_stop, server)

    @staticmethod
    def lab_stop(proc):
        # proc is sudo, which hands the signal on to the command it runs
        call(f'sudo kill {proc.pid}')
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            call(f'sudo kill -9 {proc.pid}')
            proc.wait()
        for pipe in [proc.stdin, proc.stdout]:
            if pipe:
                pipe.close()

    def lab_health(self, ifname, index):
        path = base_path + ['wan', 'interface-health', ifname]
        self.cli_set(path + ['nexthop', f'10.250.{index}.2'])
        self.cli_set(path + ['test', '10', 'type', 'ping'])
        self.cli_set(path + ['test', '10', 'target', f'10.250.{index}.2'])

    @staticmethod
    def lab_connect(port=80, source=None):
        """ Open a new connection from the LAN to the internet address and
        return the answer, e.g. "isp1 peer=10.250.1.1", or None """
        bind = f',bind={source}' if source else ''
        rc, out = rc_cmd(f'sudo ip netns exec wlb-lan socat -T2 - '
                         f'TCP:{lab_target}:{port},connect-timeout=2{bind} </dev/null')
        return out.splitlines()[-1] if rc == 0 and out else None

    @staticmethod
    def lab_count_echo_requests(isp_count):
        """ Return how many ICMP echo requests every ISP received since the
        counters were added """
        counts = []
        for index in range(1, isp_count + 1):
            rc, out = rc_cmd(f'sudo ip netns exec wlb-isp{index} nft list table ip lab')
            counts.append(int(out.split('packets ')[1].split()[0]) if rc == 0 else 0)
        return counts

    @staticmethod
    def lab_add_echo_counters(isp_count):
        for index in range(1, isp_count + 1):
            ns = f'wlb-isp{index}'
            cmd_in_netns(ns, 'nft add table ip lab')
            cmd_in_netns(ns, "nft add chain ip lab c '{ type filter hook input priority 0; }'")
            cmd_in_netns(ns, 'nft add rule ip lab c icmp type echo-request counter')

    def lab_wait_status(self, expected, timeout=30):
        found, last = self.wait_for_result(wlb_status, expected, timeout=timeout)
        self.assertTrue(found, msg=f'health state {last}, expected {expected}')

    @classmethod
    def setUpClass(cls):
        super(TestLoadBalancingWan, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

        removed_chains = [
            'wlb_mangle_isp_veth1',
            'wlb_mangle_isp_veth2',
            'wlb_mangle_isp_eth201',
            'wlb_mangle_isp_eth202'
        ]

        for chain in removed_chains:
            self.verify_nftables_chain_exists('ip vyos_wanloadbalance', chain, inverse=True)

        # always forward to base class
        super().tearDown()

    def test_table_routes(self):
        ns1 = 'ns201'
        ns2 = 'ns202'
        ns3 = 'ns203'
        iface1 = 'eth201'
        iface2 = 'eth202'
        iface3 = 'eth203'
        container_iface1 = 'ceth0'
        container_iface2 = 'ceth1'
        container_iface3 = 'ceth2'

        # Create network namespeces
        create_netns(ns1)
        create_netns(ns2)
        create_netns(ns3)
        create_veth_pair(iface1, container_iface1)
        create_veth_pair(iface2, container_iface2)
        create_veth_pair(iface3, container_iface3)

        move_interface_to_netns(container_iface1, ns1)
        move_interface_to_netns(container_iface2, ns2)
        move_interface_to_netns(container_iface3, ns3)
        call(f'sudo ip address add 203.0.113.10/24 dev {iface1}')
        call(f'sudo ip address add 192.0.2.10/24 dev {iface2}')
        call(f'sudo ip address add 198.51.100.10/24 dev {iface3}')
        call(f'sudo ip link set dev {iface1} up')
        call(f'sudo ip link set dev {iface2} up')
        call(f'sudo ip link set dev {iface3} up')
        cmd_in_netns(ns1, f'ip link set {container_iface1} name eth0')
        cmd_in_netns(ns2, f'ip link set {container_iface2} name eth0')
        cmd_in_netns(ns3, f'ip link set {container_iface3} name eth0')
        cmd_in_netns(ns1, 'ip address add 203.0.113.1/24 dev eth0')
        cmd_in_netns(ns2, 'ip address add 192.0.2.1/24 dev eth0')
        cmd_in_netns(ns3, 'ip address add 198.51.100.1/24 dev eth0')
        cmd_in_netns(ns1, 'ip link set dev eth0 up')
        cmd_in_netns(ns2, 'ip link set dev eth0 up')
        cmd_in_netns(ns3, 'ip link set dev eth0 up')

        # Set load-balancing configuration
        self.cli_set(base_path + ['wan', 'hook', '/bin/true'])
        self.cli_set(base_path + ['wan', 'interface-health', iface1, 'failure-count', '2'])
        self.cli_set(base_path + ['wan', 'interface-health', iface1, 'nexthop', '203.0.113.1'])
        self.cli_set(base_path + ['wan', 'interface-health', iface1, 'success-count', '1'])
        self.cli_set(base_path + ['wan', 'interface-health', iface2, 'failure-count', '2'])
        self.cli_set(base_path + ['wan', 'interface-health', iface2, 'nexthop', '192.0.2.1'])
        self.cli_set(base_path + ['wan', 'interface-health', iface2, 'success-count', '1'])

        self.cli_set(base_path + ['wan', 'rule', '10', 'inbound-interface', iface3])
        self.cli_set(base_path + ['wan', 'rule', '10', 'source', 'address', '198.51.100.0/24'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'interface', iface1])
        self.cli_set(base_path + ['wan', 'rule', '10', 'interface', iface2])

        # commit changes
        self.cli_commit()

        time.sleep(5)
        # Check default routes in tables 201, 202
        # Expected values
        original = 'default via 203.0.113.1 dev eth201'
        tmp = cmdl(['ip', 'route', 'show', 'table', '201'], sudo=True)
        self.assertEqual(tmp, original)

        original = 'default via 192.0.2.1 dev eth202'
        tmp = cmdl(['ip', 'route', 'show', 'table', '202'], sudo=True)
        self.assertEqual(tmp, original)

        tmp = cmdl(['ip', 'rule', 'show'], sudo=True)
        self.assertIn('from all fwmark 0xc9 lookup 201', tmp)
        self.assertIn('from all fwmark 0xca lookup 202', tmp)
        self.assertNotIn('fwmark 0xc9 lookup main suppress_prefixlength 0', tmp)
        self.assertNotIn('fwmark 0xca lookup main suppress_prefixlength 0', tmp)

        self.cli_set(base_path + ['wan', 'only-default-route'])
        self.cli_commit()

        time.sleep(5)

        tmp = cmdl(['ip', 'rule', 'show'], sudo=True)
        self.assertIn('from all fwmark 0xc9 lookup main suppress_prefixlength 0', tmp)
        self.assertIn('from all fwmark 0xc9 lookup 201', tmp)
        self.assertIn('from all fwmark 0xca lookup main suppress_prefixlength 0', tmp)
        self.assertIn('from all fwmark 0xca lookup 202', tmp)

        # Delete veth interfaces and netns
        for iface in [iface1, iface2, iface3]:
            call(f'sudo ip link del dev {iface}')

        delete_netns(ns1)
        delete_netns(ns2)
        delete_netns(ns3)

    def test_check_chains(self):
        ns1 = 'nsA'
        ns2 = 'nsB'
        ns3 = 'nsC'
        iface1 = 'veth1'
        iface2 = 'veth2'
        iface3 = 'veth3'
        container_iface1 = 'ceth0'
        container_iface2 = 'ceth1'
        container_iface3 = 'ceth2'
        mangle_isp1 = """table ip vyos_wanloadbalance {
	chain wlb_mangle_isp_veth1 {
		meta mark set 0x000000c9 ct mark set 0x000000c9 counter accept
	}
}"""
        mangle_isp2 = """table ip vyos_wanloadbalance {
	chain wlb_mangle_isp_veth2 {
		meta mark set 0x000000ca ct mark set 0x000000ca counter accept
	}
}"""
        mangle_prerouting = """table ip vyos_wanloadbalance {
	chain wlb_mangle_prerouting {
		type filter hook prerouting priority mangle; policy accept;
		iifname "veth3" ip saddr 198.51.100.0/24 ct state new counter numgen random mod 11 vmap { 0 : jump wlb_mangle_isp_veth1, 1-10 : jump wlb_mangle_isp_veth2 }
		iifname "veth3" ip saddr 198.51.100.0/24 counter meta mark set ct mark
	}
}"""
        nat_wanloadbalance = """table ip vyos_wanloadbalance {
	chain wlb_nat_postrouting {
		type nat hook postrouting priority srcnat - 1; policy accept;
		ct mark 0x000000c9 oifname "veth1" counter snat to 203.0.113.10
		ct mark 0x000000ca oifname "veth2" counter snat to 192.0.2.10
	}
}"""

        # Create network namespeces
        create_netns(ns1)
        create_netns(ns2)
        create_netns(ns3)
        create_veth_pair(iface1, container_iface1)
        create_veth_pair(iface2, container_iface2)
        create_veth_pair(iface3, container_iface3)
        move_interface_to_netns(container_iface1, ns1)
        move_interface_to_netns(container_iface2, ns2)
        move_interface_to_netns(container_iface3, ns3)
        call(f'sudo ip address add 203.0.113.10/24 dev {iface1}')
        call(f'sudo ip address add 192.0.2.10/24 dev {iface2}')
        call(f'sudo ip address add 198.51.100.10/24 dev {iface3}')

        for iface in [iface1, iface2, iface3]:
            call(f'sudo ip link set dev {iface} up')

        cmd_in_netns(ns1, f'ip link set {container_iface1} name eth0')
        cmd_in_netns(ns2, f'ip link set {container_iface2} name eth0')
        cmd_in_netns(ns3, f'ip link set {container_iface3} name eth0')
        cmd_in_netns(ns1, 'ip address add 203.0.113.1/24 dev eth0')
        cmd_in_netns(ns2, 'ip address add 192.0.2.1/24 dev eth0')
        cmd_in_netns(ns3, 'ip address add 198.51.100.1/24 dev eth0')
        cmd_in_netns(ns1, 'ip link set dev eth0 up')
        cmd_in_netns(ns2, 'ip link set dev eth0 up')
        cmd_in_netns(ns3, 'ip link set dev eth0 up')

        # Set load-balancing configuration
        self.cli_set(base_path + ['wan', 'interface-health', iface1, 'failure-count', '2'])
        self.cli_set(base_path + ['wan', 'interface-health', iface1, 'nexthop', '203.0.113.1'])
        self.cli_set(base_path + ['wan', 'interface-health', iface1, 'success-count', '1'])
        self.cli_set(base_path + ['wan', 'interface-health', iface2, 'failure-count', '2'])
        self.cli_set(base_path + ['wan', 'interface-health', iface2, 'nexthop', '192.0.2.1'])
        self.cli_set(base_path + ['wan', 'interface-health', iface2, 'success-count', '1'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'inbound-interface', iface3])
        self.cli_set(base_path + ['wan', 'rule', '10', 'source', 'address', '198.51.100.0/24'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'interface', iface1])
        self.cli_set(base_path + ['wan', 'rule', '10', 'interface', iface2, 'weight', '10'])

        # commit changes
        self.cli_commit()

        time.sleep(5)

        # Check mangle chains
        tmp = cmdl(['nft', '-s', 'list', 'chain', 'ip', 'vyos_wanloadbalance', f'wlb_mangle_isp_{iface1}'], sudo=True)
        self.assertEqual(tmp, mangle_isp1)

        tmp = cmdl(['nft', '-s', 'list', 'chain', 'ip', 'vyos_wanloadbalance', f'wlb_mangle_isp_{iface2}'], sudo=True)
        self.assertEqual(tmp, mangle_isp2)

        tmp = cmdl(['nft', '-s', 'list', 'chain', 'ip', 'vyos_wanloadbalance', 'wlb_mangle_prerouting'], sudo=True)
        self.assertEqual(tmp, mangle_prerouting)

        # Check nat chains
        tmp = cmdl(['nft', '-s', 'list', 'chain', 'ip', 'vyos_wanloadbalance', 'wlb_nat_postrouting'], sudo=True)
        self.assertEqual(tmp, nat_wanloadbalance)

        # Set limit configuration
        mangle_prerouting_limit = """table ip vyos_wanloadbalance {
	chain wlb_mangle_prerouting {
		type filter hook prerouting priority mangle; policy accept;
		iifname "veth3" ip saddr 198.51.100.0/24 ct state new limit rate 10/second burst 10 packets counter numgen random mod 11 vmap { 0 : jump wlb_mangle_isp_veth1, 1-10 : jump wlb_mangle_isp_veth2 }
		iifname "veth3" ip saddr 198.51.100.0/24 counter meta mark set ct mark
	}
}"""

        self.cli_set(base_path + ['wan', 'rule', '10', 'limit', 'rate', '10'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'limit', 'burst', '10'])

        # Commit changes
        self.cli_commit()

        time.sleep(5)

        # Check prerouting mangle chain
        tmp = cmdl(['nft', '-s', 'list', 'chain', 'ip', 'vyos_wanloadbalance', 'wlb_mangle_prerouting'], sudo=True)
        self.assertEqual(tmp, mangle_prerouting_limit)

        # Delete veth interfaces and netns
        for iface in [iface1, iface2, iface3]:
            call(f'sudo ip link del dev {iface}')

        delete_netns(ns1)
        delete_netns(ns2)
        delete_netns(ns3)

    def test_criteria_failover_hook(self):
        isp1_iface = 'eth0'
        isp2_iface = 'eth1'
        lan_iface = 'eth2'

        hook_path = '/tmp/wlb_hook.sh'
        hook_output_path = '/tmp/wlb_hook_output'
        hook_script = f"""
#!/bin/sh

ifname=$WLB_INTERFACE_NAME
state=$WLB_INTERFACE_STATE

echo "$ifname - $state" >> {hook_output_path}
"""

        # the hook reports every interface on start, keep all events and
        # drop the ones of earlier runs
        call(f'sudo rm -f {hook_output_path}')
        self.addCleanup(call, f'sudo rm -f {hook_output_path} {hook_path}')
        write_file(hook_path, hook_script)
        chmod_755(hook_path)

        self.cli_set(['interfaces', 'ethernet', isp1_iface, 'address', '203.0.113.2/30'])
        self.cli_set(['interfaces', 'ethernet', isp2_iface, 'address', '192.0.2.2/30'])
        self.cli_set(['interfaces', 'ethernet', lan_iface, 'address', '198.51.100.2/30'])

        self.cli_set(base_path + ['wan', 'hook', hook_path])
        self.cli_set(base_path + ['wan', 'interface-health', isp1_iface, 'failure-count', '1'])
        self.cli_set(base_path + ['wan', 'interface-health', isp1_iface, 'nexthop', '203.0.113.2'])
        self.cli_set(base_path + ['wan', 'interface-health', isp1_iface, 'success-count', '1'])
        self.cli_set(base_path + ['wan', 'interface-health', isp2_iface, 'failure-count', '1'])
        self.cli_set(base_path + ['wan', 'interface-health', isp2_iface, 'nexthop', '192.0.2.2'])
        self.cli_set(base_path + ['wan', 'interface-health', isp2_iface, 'success-count', '1'])
        self.cli_set(base_path + ['wan', 'rule', '5', 'exclude'])
        self.cli_set(base_path + ['wan', 'rule', '5', 'inbound-interface', 'eth*'])
        self.cli_set(base_path + ['wan', 'rule', '5', 'destination', 'address', '10.0.0.0/8'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'failover'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'inbound-interface', lan_iface])
        self.cli_set(base_path + ['wan', 'rule', '10', 'protocol', 'udp'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'source', 'address', '198.51.100.0/24'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'source', 'port', '53'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'destination', 'address', '192.0.2.0/24'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'destination', 'port', '53'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'interface', isp1_iface])
        self.cli_set(base_path + ['wan', 'rule', '10', 'interface', isp1_iface, 'weight', '10'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'interface', isp2_iface])
        self.cli_set(base_path + ['wan', 'rule', '20', 'inbound-interface', lan_iface])
        self.cli_set(base_path + ['wan', 'rule', '20', 'protocol', 'udp'])
        self.cli_set(
            base_path + ['wan', 'rule', '20', 'source', 'address', '198.51.100.0/24']
        )
        self.cli_set(base_path + ['wan', 'rule', '20', 'source', 'port', '80,443'])
        self.cli_set(
            base_path + ['wan', 'rule', '20', 'destination', 'address', '192.0.2.0/24']
        )
        self.cli_set(base_path + ['wan', 'rule', '20', 'destination', 'port', '80,443'])
        self.cli_set(base_path + ['wan', 'rule', '20', 'interface', isp2_iface])

        # commit changes
        self.cli_commit()

        time.sleep(5)

        # Verify isp1 + criteria

        nftables_search = [
            [f'iifname "eth*"', 'ip daddr 10.0.0.0/8', 'return'],
            [
                f'iifname "{lan_iface}"',
                'ip saddr 198.51.100.0/24',
                'udp sport 53',
                'ip daddr 192.0.2.0/24',
                'udp dport 53',
                f'jump wlb_mangle_isp_{isp1_iface}',
            ],
            [
                f'iifname "{lan_iface}"',
                'ip saddr 198.51.100.0/24',
                'udp sport { 80, 443 }',
                'ip daddr 192.0.2.0/24',
                'udp dport { 80, 443 }',
                f'jump wlb_mangle_isp_{isp2_iface}',
            ],
        ]

        self.verify_nftables_chain(nftables_search, 'ip vyos_wanloadbalance', 'wlb_mangle_prerouting')

        # Trigger failure on isp1 health check

        self.cli_delete(['interfaces', 'ethernet', isp1_iface, 'address', '203.0.113.2/30'])
        self.cli_commit()

        time.sleep(10)

        # Verify failover to isp2

        nftables_search = [
            [f'iifname "{lan_iface}"', f'jump wlb_mangle_isp_{isp2_iface}']
        ]

        self.verify_nftables_chain(nftables_search, 'ip vyos_wanloadbalance', 'wlb_mangle_prerouting')

        # Verify hook output

        self.assertTrue(os.path.exists(hook_output_path))

        with open(hook_output_path, 'r') as f:
            self.assertIn('eth0 - FAILED', f.read())

    def test_user_defined_health_check_script_env(self):
        isp_interfaces = {
            'eth0': ('203.0.113.2/30', '203.0.113.1'),
            'eth1': ('192.0.2.2/30', '192.0.2.1'),
        }
        lan_iface = 'eth2'
        temp_dir = tempfile.TemporaryDirectory(prefix='wlb_health_check_')
        self.addCleanup(temp_dir.cleanup)
        script_path = os.path.join(temp_dir.name, 'health_check.sh')
        output_path = os.path.join(temp_dir.name, 'health_check_output')

        health_check_script = f"""
#!/bin/sh

printf 'WLB_INTERFACE_NAME=%s WLB_SCRIPT_IFACE=%s\\n' \\
    "$WLB_INTERFACE_NAME" "$WLB_SCRIPT_IFACE" >> {output_path}

[ "$WLB_INTERFACE_NAME" = "$WLB_SCRIPT_IFACE" ]
"""

        write_file(script_path, health_check_script)
        chmod_755(script_path)

        for isp_iface, (address, nexthop) in isp_interfaces.items():
            self.cli_set(['interfaces', 'ethernet', isp_iface, 'address', address])
            self.cli_set(
                base_path + ['wan', 'interface-health', isp_iface, 'failure-count', '1']
            )
            self.cli_set(
                base_path + ['wan', 'interface-health', isp_iface, 'nexthop', nexthop]
            )
            self.cli_set(
                base_path + ['wan', 'interface-health', isp_iface, 'success-count', '1']
            )
            self.cli_set(
                base_path
                + [
                    'wan',
                    'interface-health',
                    isp_iface,
                    'test',
                    '10',
                    'test-script',
                    script_path,
                ]
            )
            self.cli_set(
                base_path
                + [
                    'wan',
                    'interface-health',
                    isp_iface,
                    'test',
                    '10',
                    'type',
                    'user-defined',
                ]
            )

        self.cli_set(
            ['interfaces', 'ethernet', lan_iface, 'address', '198.51.100.2/30']
        )
        self.cli_set(base_path + ['wan', 'rule', '10', 'inbound-interface', lan_iface])

        for isp_iface in isp_interfaces:
            self.cli_set(base_path + ['wan', 'rule', '10', 'interface', isp_iface])

        self.cli_commit()

        def check_script_output():
            if not os.path.exists(output_path):
                return False

            with open(output_path, 'r') as f:
                output = f.read()

            return all(
                f'WLB_INTERFACE_NAME={isp_iface} WLB_SCRIPT_IFACE={isp_iface}' in output
                for isp_iface in isp_interfaces
            )

        wait_for(check_script_output)

    def test_firewall_groups(self):
        isp1_iface = 'eth0'
        isp2_iface = 'eth1'
        lan_iface = 'eth2'

        network_group1 = 'NET1'
        network_group2 = 'NET2'
        port_group = 'PORT1'

        self.cli_set(['interfaces', 'ethernet', isp1_iface, 'address', '203.0.113.2/30'])
        self.cli_set(['interfaces', 'ethernet', isp2_iface, 'address', '192.0.2.2/30'])
        self.cli_set(['interfaces', 'ethernet', lan_iface, 'address', '198.51.100.2/30'])

        self.cli_set(['firewall', 'group', 'network-group', network_group1, 'network', '10.0.0.0/8'])
        self.cli_set(['firewall', 'group', 'network-group', network_group2, 'network', '198.51.100.0/24'])
        self.cli_set(['firewall', 'group', 'port-group', port_group, 'port', '53'])

        self.cli_set(base_path + ['wan', 'interface-health', isp1_iface, 'failure-count', '1'])
        self.cli_set(base_path + ['wan', 'interface-health', isp1_iface, 'nexthop', '203.0.113.2'])
        self.cli_set(base_path + ['wan', 'interface-health', isp1_iface, 'success-count', '1'])
        self.cli_set(base_path + ['wan', 'interface-health', isp2_iface, 'failure-count', '1'])
        self.cli_set(base_path + ['wan', 'interface-health', isp2_iface, 'nexthop', '192.0.2.2'])
        self.cli_set(base_path + ['wan', 'interface-health', isp2_iface, 'success-count', '1'])
        self.cli_set(base_path + ['wan', 'rule', '5', 'exclude'])
        self.cli_set(base_path + ['wan', 'rule', '5', 'inbound-interface', 'eth*'])
        self.cli_set(base_path + ['wan', 'rule', '5', 'destination', 'group', 'network-group', network_group1])
        self.cli_set(base_path + ['wan', 'rule', '10', 'failover'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'inbound-interface', lan_iface])
        self.cli_set(base_path + ['wan', 'rule', '10', 'protocol', 'udp'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'source', 'group', 'network-group', network_group2])
        self.cli_set(base_path + ['wan', 'rule', '10', 'source', 'group', 'port-group', port_group])
        self.cli_set(base_path + ['wan', 'rule', '10', 'destination', 'address', '192.0.2.0/24'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'destination', 'group', 'port-group', port_group])
        self.cli_set(base_path + ['wan', 'rule', '10', 'interface', isp1_iface])
        self.cli_set(base_path + ['wan', 'rule', '10', 'interface', isp1_iface, 'weight', '10'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'interface', isp2_iface])

        # commit changes
        self.cli_commit()

        time.sleep(5)

        nftables_search = [
            ['iifname "eth*"', f'ip daddr @N_{network_group1}', 'return'],
            [
                f'iifname "{lan_iface}"',
                f'ip saddr @N_{network_group2}',
                f'udp sport @P_{port_group}',
                'ip daddr 192.0.2.0/24',
                f'udp dport @P_{port_group}',
                f'jump wlb_mangle_isp_{isp1_iface}',
            ],
        ]

        self.verify_nftables_chain(nftables_search, 'ip vyos_wanloadbalance', 'wlb_mangle_prerouting')

    def test_3_or_more_interfaces_in_rule(self):
        lan_iface = 'eth1'

        # Interfaces for equal weight test
        self.cli_set(['interfaces', 'ethernet', 'eth0', 'vif', '101', 'address', '203.0.113.2/30'])
        self.cli_set(['interfaces', 'ethernet', 'eth0', 'vif', '102', 'address', '203.0.113.6/30'])
        self.cli_set(['interfaces', 'ethernet', 'eth0', 'vif', '103', 'address', '203.0.113.10/30'])

        # Interfaces for unequal weight test
        self.cli_set(['interfaces', 'ethernet', 'eth0', 'vif', '201', 'address', '203.0.113.14/30'])
        self.cli_set(['interfaces', 'ethernet', 'eth0', 'vif', '202', 'address', '203.0.113.18/30'])
        self.cli_set(['interfaces', 'ethernet', 'eth0', 'vif', '203', 'address', '203.0.113.22/30'])
        self.cli_set(['interfaces', 'ethernet', 'eth0', 'vif', '204', 'address', '203.0.113.26/30'])
        self.cli_set(['interfaces', 'ethernet', 'eth0', 'vif', '205', 'address', '203.0.113.30/30'])


        self.cli_set(['interfaces', 'ethernet', lan_iface, 'vif', '100', 'address', '198.51.100.2/30'])
        self.cli_set(['interfaces', 'ethernet', lan_iface, 'vif', '200', 'address', '198.51.100.6/30'])

        # Health checks for equal weight test
        self.cli_set(base_path + ['wan', 'interface-health', 'eth0.101', 'nexthop', '203.0.113.2'])
        self.cli_set(base_path + ['wan', 'interface-health', 'eth0.102', 'nexthop', '203.0.113.6'])
        self.cli_set(base_path + ['wan', 'interface-health', 'eth0.103', 'nexthop', '203.0.113.10'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'inbound-interface', f'{lan_iface}.100'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'interface', 'eth0.101'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'interface', 'eth0.102'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'interface', 'eth0.103'])

        # Health checks for unequal weight test
        self.cli_set(base_path + ['wan', 'interface-health', 'eth0.201', 'nexthop', '203.0.113.14'])
        self.cli_set(base_path + ['wan', 'interface-health', 'eth0.202', 'nexthop', '203.0.113.18'])
        self.cli_set(base_path + ['wan', 'interface-health', 'eth0.203', 'nexthop', '203.0.113.22'])
        self.cli_set(base_path + ['wan', 'interface-health', 'eth0.204', 'nexthop', '203.0.113.26'])
        self.cli_set(base_path + ['wan', 'interface-health', 'eth0.205', 'nexthop', '203.0.113.30'])
        self.cli_set(base_path + ['wan', 'rule', '20', 'inbound-interface', f'{lan_iface}.200'])
        self.cli_set(base_path + ['wan', 'rule', '20', 'interface', 'eth0.201', 'weight', '2'])
        self.cli_set(base_path + ['wan', 'rule', '20', 'interface', 'eth0.202', 'weight', '4'])
        self.cli_set(base_path + ['wan', 'rule', '20', 'interface', 'eth0.203', 'weight', '4'])
        self.cli_set(base_path + ['wan', 'rule', '20', 'interface', 'eth0.204', 'weight', '7'])
        self.cli_set(base_path + ['wan', 'rule', '20', 'interface', 'eth0.205', 'weight', '4'])

        # commit changes
        self.cli_commit()

        def check_wlb_status():
            rc, wlb_status = rc_cmd('nft list chain ip vyos_wanloadbalance wlb_mangle_prerouting')
            if rc != 0:
                return False

            # get all lines containing 'jump'
            lines = [l for l in wlb_status.splitlines() if 'jump' in l]

            # check total count of 'jump' across all matching lines
            total_jumps = sum(l.count('jump') for l in lines)

            return total_jumps == 8

        wait_for(check_wlb_status)

        nftables_search = [
            ['0 : jump wlb_mangle_isp_eth0.101',
            '1 : jump wlb_mangle_isp_eth0.102',
            '2 : jump wlb_mangle_isp_eth0.103'],
            ['0-1 : jump wlb_mangle_isp_eth0.201',
            '2-5 : jump wlb_mangle_isp_eth0.202',
            '6-9 : jump wlb_mangle_isp_eth0.203',
            '10-13 : jump wlb_mangle_isp_eth0.205',
            '14-20 : jump wlb_mangle_isp_eth0.204'],
        ]

        self.verify_nftables_chain(nftables_search, 'ip vyos_wanloadbalance', 'wlb_mangle_prerouting')
    def test_health_test_requires_target(self):
        # without a target the health daemon failed after the commit succeeded
        self.cli_set(base_path + ['wan', 'interface-health', 'eth0', 'nexthop', '192.0.2.1'])
        self.cli_set(base_path + ['wan', 'interface-health', 'eth0', 'test', '10', 'resp-time', '3'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'inbound-interface', 'eth1'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'interface', 'eth0'])

        for test_type in ['ping', 'ttl']:
            self.cli_set(base_path + ['wan', 'interface-health', 'eth0', 'test', '10', 'type', test_type])
            with self.assertRaisesRegex(ConfigSessionError, f'Missing target for {test_type} health test 10'):
                self.cli_commit()

        self.cli_set(base_path + ['wan', 'interface-health', 'eth0', 'test', '10', 'target', '192.0.2.1'])
        self.cli_commit()
    def test_protocol_not_all(self):
        # "!all" was rendered as "meta l4proto != all", which nft rejects
        self.cli_set(base_path + ['wan', 'interface-health', 'eth0', 'nexthop', '192.0.2.1'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'inbound-interface', 'eth1'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'interface', 'eth0'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'protocol', '!all'])
        with self.assertRaisesRegex(ConfigSessionError, 'Protocol "!all" matches no traffic'):
            self.cli_commit()

        self.cli_set(base_path + ['wan', 'rule', '10', 'protocol', '!tcp'])
        self.cli_commit()
        found, out = self.wait_for_result(lambda: wlb_chain('wlb_mangle_prerouting'),
                                          lambda out: 'iifname "eth1" meta l4proto != tcp' in out, timeout=15)
        self.assertTrue(found, msg=out)
    def test_rule_interface_requires_health(self):
        # an interface without health configuration was silently left out
        # of the rule, the traffic was not balanced at all
        self.cli_set(base_path + ['wan', 'interface-health', 'eth0', 'nexthop', '192.0.2.1'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'inbound-interface', 'eth2'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'interface', 'eth1'])
        with self.assertRaisesRegex(ConfigSessionError, 'Interface "eth1" on load-balancing wan rule 10 has no interface-health'):
            self.cli_commit()

        self.cli_set(base_path + ['wan', 'interface-health', 'eth1', 'nexthop', '198.51.100.1'])
        self.cli_commit()
    def test_interface_name_with_dash(self):
        # the health daemon mangled "-" in interface names to "_" and then
        # looked for interfaces which do not exist
        isps = ['wlb-isp1', 'wlb-isp2']
        self.lab_setup('wlb-lan0', isps)
        for index, ifname in enumerate(isps, start=1):
            self.lab_health(ifname, index)
            self.cli_set(base_path + ['wan', 'rule', '10', 'interface', ifname])
        self.cli_set(base_path + ['wan', 'rule', '10', 'inbound-interface', 'wlb-lan0'])
        self.cli_commit()

        self.lab_wait_status({'wlb-isp1': 'ACTIVE', 'wlb-isp2': 'ACTIVE'})
        answers = {self.lab_connect() for _ in range(20)}
        self.assertEqual(answers, {'isp1 peer=10.250.1.1', 'isp2 peer=10.250.2.1'})
    def test_inbound_interface_any(self):
        # "any" was rendered as interface name and matched no packet
        isps = ['eth231', 'eth232']
        self.lab_setup('eth230', isps)
        for index, ifname in enumerate(isps, start=1):
            self.lab_health(ifname, index)
            self.cli_set(base_path + ['wan', 'rule', '10', 'interface', ifname])
        self.cli_set(base_path + ['wan', 'rule', '10', 'inbound-interface', 'any'])
        self.cli_commit()

        self.lab_wait_status({'eth231': 'ACTIVE', 'eth232': 'ACTIVE'})
        # replies from an ISP must not be balanced back to an ISP
        found, out = self.wait_for_result(lambda: wlb_chain('wlb_mangle_prerouting'),
                                          lambda out: 'iifname != { "eth231", "eth232" }' in out, timeout=15)
        self.assertTrue(found, msg=out)
        self.assertNotIn('"any"', out)
        answers = {self.lab_connect() for _ in range(20)}
        self.assertEqual(answers, {'isp1 peer=10.250.1.1', 'isp2 peer=10.250.2.1'})
    def test_per_packet_balancing(self):
        # the option was never read, every rule balanced per flow
        isps = ['eth231', 'eth232']
        self.lab_setup('eth230', isps)
        for index, ifname in enumerate(isps, start=1):
            self.lab_health(ifname, index)
            self.cli_set(base_path + ['wan', 'rule', '10', 'interface', ifname])
        self.cli_set(base_path + ['wan', 'rule', '10', 'inbound-interface', 'eth230'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'protocol', 'icmp'])
        self.cli_set(base_path + ['wan', 'rule', '10', 'per-packet-balancing'])
        self.cli_commit()

        self.lab_wait_status({'eth231': 'ACTIVE', 'eth232': 'ACTIVE'})
        found, out = self.wait_for_result(lambda: wlb_chain('wlb_mangle_prerouting'),
                                          lambda out: 'meta l4proto icmp counter' in out, timeout=15)
        self.assertTrue(found, msg=out)
        self.assertNotIn('ct state new', out)

        # one ICMP flow - per packet, both ISPs see some of its requests
        self.lab_add_echo_counters(len(isps))
        cmd_in_netns('wlb-lan', f'ping -c 20 -i 0.05 -W 1 {lab_target}')
        counts = self.lab_count_echo_requests(len(isps))
        self.assertTrue(all(counts), msg=f'echo requests per ISP: {counts}')
    def test_limit_threshold_above(self):
        # the threshold was ignored, "above" behaved like "below"
        isps = ['eth231', 'eth232']
        self.lab_setup('eth230', isps)
        for index, ifname in enumerate(isps, start=1):
            self.lab_health(ifname, index)
        # connections beyond one per second go to isp2, all others to isp1
        rule = base_path + ['wan', 'rule', '10']
        self.cli_set(rule + ['inbound-interface', 'eth230'])
        self.cli_set(rule + ['interface', 'eth232'])
        self.cli_set(rule + ['limit', 'rate', '1'])
        self.cli_set(rule + ['limit', 'burst', '1'])
        self.cli_set(rule + ['limit', 'threshold', 'above'])
        self.cli_set(base_path + ['wan', 'rule', '20', 'inbound-interface', 'eth230'])
        self.cli_set(base_path + ['wan', 'rule', '20', 'interface', 'eth231'])
        self.cli_commit()

        self.lab_wait_status({'eth231': 'ACTIVE', 'eth232': 'ACTIVE'})
        found, out = self.wait_for_result(lambda: wlb_chain('wlb_mangle_prerouting'),
                                          lambda out: 'limit rate over 1/second burst 1 packets' in out, timeout=15)
        self.assertTrue(found, msg=out)

        answers = [self.lab_connect() for _ in range(10)]
        self.assertGreaterEqual(answers.count('isp2 peer=10.250.2.1'), 5, msg=answers)
    def test_health_test_ttl(self):
        # the ttl test treated every ping failure as healthy and an answer
        # as failure - an outage was never detected
        isps = ['eth231', 'eth232']
        self.lab_setup('eth230', isps)
        # 203.0.113.0/24 is behind isp1, which forwards it into a black hole
        call('sudo ip route add 203.0.113.0/24 via 10.250.1.2')
        self.addCleanup(call, 'sudo ip route del 203.0.113.0/24 via 10.250.1.2')
        cmd_in_netns('wlb-isp1', 'sysctl -w net.ipv4.ip_forward=1')
        cmd_in_netns('wlb-isp1', 'ip link add d0 type dummy')
        cmd_in_netns('wlb-isp1', 'ip link set d0 up')
        cmd_in_netns('wlb-isp1', 'ip addr add 192.0.2.1/30 dev d0')
        cmd_in_netns('wlb-isp1', 'ip route add 203.0.113.0/24 via 192.0.2.2')

        self.lab_health('eth232', 2)
        test = base_path + ['wan', 'interface-health', 'eth231', 'test', '10']
        self.cli_set(base_path + ['wan', 'interface-health', 'eth231', 'nexthop', '10.250.1.2'])
        self.cli_set(test + ['type', 'ttl'])
        self.cli_set(test + ['resp-time', '1'])
        for ifname in isps:
            self.cli_set(base_path + ['wan', 'rule', '10', 'interface', ifname])
        self.cli_set(base_path + ['wan', 'rule', '10', 'inbound-interface', 'eth230'])

        failed = {'eth231': 'FAILED', 'eth232': 'ACTIVE'}
        # the target answers itself, or the hop where the TTL runs out does
        for target, ttl in [('10.250.1.2', '1'), ('203.0.113.10', '1')]:
            self.cli_set(test + ['target', target])
            self.cli_set(test + ['ttl-limit', ttl])
            self.cli_commit()
            # eth231 is ACTIVE until a check fails, give it two rounds of checks
            found, _ = self.wait_for_result(wlb_status, failed, timeout=12)
            self.assertFalse(found, msg=f'ttl test to {target} with ttl {ttl} failed')

        # nothing answers - the path is broken
        self.cli_set(test + ['ttl-limit', '3'])
        self.cli_commit()
        self.lab_wait_status(failed)
    def test_hook_initial_state_all_interfaces(self):
        # the initial state was only reported to the hook for the first
        # interface
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        hook = os.path.join(tmpdir.name, 'hook.sh')
        log = os.path.join(tmpdir.name, 'hook.log')
        # the hook runs without PATH
        write_file(hook, f'#!/bin/sh\n/bin/echo "$WLB_INTERFACE_NAME $WLB_INTERFACE_STATE" >> {log}\n')
        chmod_755(hook)
        chmod_755(tmpdir.name)

        isps = ['eth231', 'eth232']
        self.lab_setup('eth230', isps)
        for index, ifname in enumerate(isps, start=1):
            self.lab_health(ifname, index)
            self.cli_set(base_path + ['wan', 'rule', '10', 'interface', ifname])
        self.cli_set(base_path + ['wan', 'rule', '10', 'inbound-interface', 'eth230'])
        self.cli_set(base_path + ['wan', 'hook', hook])
        self.cli_commit()

        def reported():
            if not os.path.exists(log):
                return set()
            with open(log) as f:
                return set(f.read().splitlines())

        found, last = self.wait_for_result(reported, {'eth231 ACTIVE', 'eth232 ACTIVE'}, timeout=20)
        self.assertTrue(found, msg=f'hook reported {last}')
    def test_mark_stable_when_adding_interface(self):
        # marks and routing tables followed the sorted interface list, adding
        # an interface renumbered the others and broke their connections
        isps = ['eth231', 'eth232', 'eth229']
        self.lab_setup('eth230', isps)
        self.lab_health('eth231', 1)
        self.lab_health('eth232', 2)
        for ifname in ['eth231', 'eth232']:
            self.cli_set(base_path + ['wan', 'rule', '10', 'interface', ifname])
        self.cli_set(base_path + ['wan', 'rule', '10', 'inbound-interface', 'eth230'])
        self.cli_commit()
        self.lab_wait_status({'eth231': 'ACTIVE', 'eth232': 'ACTIVE'})

        def isp_marks():
            marks = {}
            chain = None
            for line in rc_cmd('sudo nft list table ip vyos_wanloadbalance')[1].splitlines():
                if 'chain wlb_mangle_isp_' in line:
                    chain = line.split('wlb_mangle_isp_')[1].split()[0]
                elif chain and 'meta mark set' in line:
                    marks[chain] = line.split('meta mark set ')[1].split()[0]
            return marks

        marks = isp_marks()

        # a long-lived connection through one of the ISPs
        client = subprocess.Popen(['sudo', 'ip', 'netns', 'exec', 'wlb-lan', 'socat', '-',
                                   f'TCP:{lab_target}:90'], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, text=True)
        self.addCleanup(self.lab_stop, client)

        def echo(text, timeout=5):
            client.stdin.write(f'{text}\n')
            client.stdin.flush()
            if select.select([client.stdout], [], [], timeout)[0]:
                return client.stdout.readline().strip()
            return None

        self.assertEqual(echo('first'), 'first')

        # eth229 sorts before the interfaces already in use
        self.cli_set(base_path + ['wan', 'interface-health', 'eth229', 'nexthop', '10.250.3.2'])
        self.cli_set(base_path + ['wan', 'interface-health', 'eth229', 'test', '10', 'target', '10.250.3.2'])
        self.cli_commit()
        self.lab_wait_status({'eth229': 'ACTIVE', 'eth231': 'ACTIVE', 'eth232': 'ACTIVE'})

        new_marks = isp_marks()
        for ifname in ['eth231', 'eth232']:
            self.assertEqual(new_marks.get(ifname), marks[ifname], msg=f'mark of {ifname} changed')
        self.assertEqual(echo('second'), 'second')

        # a removed WAN load-balancing starts over with the first table
        self.cli_delete(base_path)
        self.cli_commit()
        self.assertFalse(os.path.exists('/run/wlb_tables.json'))
    def test_commit_reloads_without_gap(self):
        # every commit restarted the health daemon: rules, routes and health
        # state were gone until it was back
        isps = ['eth231', 'eth232']
        self.lab_setup('eth230', isps)
        for index, ifname in enumerate(isps, start=1):
            self.lab_health(ifname, index)
            self.cli_set(base_path + ['wan', 'rule', '10', 'interface', ifname])
        self.cli_set(base_path + ['wan', 'rule', '10', 'inbound-interface', 'eth230'])
        self.cli_commit()
        self.lab_wait_status({'eth231': 'ACTIVE', 'eth232': 'ACTIVE'})

        def daemon_pid():
            return cmdl(['systemctl', 'show', '--property=MainPID', '--value',
                         'vyos-wan-load-balance.service'])
        pid = daemon_pid()

        # new connections keep working while an unrelated change is committed
        results = []
        done = threading.Event()
        def connect():
            while not done.is_set():
                results.append(self.lab_connect() is not None)
        worker = threading.Thread(target=connect)
        worker.start()
        time.sleep(1)
        self.cli_set(base_path + ['wan', 'rule', '10', 'description', 'reload'])
        self.cli_commit()
        time.sleep(7)
        done.set()
        worker.join()
        self.assertEqual(daemon_pid(), pid)
        self.assertNotIn(False, results, msg=f'{results.count(False)} of {len(results)} connections failed')

        # a known health state survives a commit
        cmd_in_netns('wlb-isp1', 'nft add table ip block')
        cmd_in_netns('wlb-isp1', "nft add chain ip block c '{ type filter hook input priority 0; }'")
        cmd_in_netns('wlb-isp1', 'nft add rule ip block c icmp type echo-request drop')
        failed = {'eth231': 'FAILED', 'eth232': 'ACTIVE'}
        self.lab_wait_status(failed)
        self.cli_set(base_path + ['wan', 'rule', '10', 'description', 'reload again'])
        self.cli_commit()
        time.sleep(2)
        self.assertEqual(wlb_status(), failed)
        self.assertEqual(daemon_pid(), pid)

        # a removed interface takes its route and ip rule along
        self.cli_delete(base_path + ['wan', 'interface-health', 'eth232'])
        self.cli_delete(base_path + ['wan', 'rule', '10', 'interface', 'eth232'])
        self.cli_commit()
        self.lab_wait_status({'eth231': 'FAILED'})
        self.assertNotIn('lookup 202', cmdl(['ip', 'rule', 'show']))
        self.assertEqual(cmdl(['ip', 'route', 'show', 'table', '202']), '')
        self.assertEqual(daemon_pid(), pid)

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
