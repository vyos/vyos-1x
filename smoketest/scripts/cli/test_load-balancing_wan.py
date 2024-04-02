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

import unittest
import time

from base_vyostest_shim import VyOSUnitTestSHIM
from vyos.utils.process import call
from vyos.utils.process import cmd

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

class TestLoadBalancingWan(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestLoadBalancingWan, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

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
        self.cli_set(base_path + ['wan', 'interface-health', iface1, 'failure-count', '2'])
        self.cli_set(base_path + ['wan', 'interface-health', iface1, 'nexthop', '203.0.113.1'])
        self.cli_set(base_path + ['wan', 'interface-health', iface1, 'success-count', '1'])
        self.cli_set(base_path + ['wan', 'interface-health', iface2, 'failure-count', '2'])
        self.cli_set(base_path + ['wan', 'interface-health', iface2, 'nexthop', '192.0.2.1'])
        self.cli_set(base_path + ['wan', 'interface-health', iface2, 'success-count', '1'])

        self.cli_set(base_path + ['wan', 'rule', '10', 'inbound-interface', iface3])
        self.cli_set(base_path + ['wan', 'rule', '10', 'source', 'address', '198.51.100.0/24'])


        # commit changes
        self.cli_commit()

        time.sleep(5)
        # Check default routes in tables 201, 202
        # Expected values
        original = 'default via 203.0.113.1 dev eth201'
        tmp = cmd('sudo ip route show table 201')
        self.assertEqual(tmp, original)

        original = 'default via 192.0.2.1 dev eth202'
        tmp = cmd('sudo ip route show table 202')
        self.assertEqual(tmp, original)

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
        mangle_isp1 = """table ip mangle {
	chain ISP_veth1 {
		counter ct mark set 0xc9
		counter meta mark set 0xc9
		counter accept
	}
}"""
        mangle_isp2 = """table ip mangle {
	chain ISP_veth2 {
		counter ct mark set 0xca
		counter meta mark set 0xca
		counter accept
	}
}"""
        mangle_prerouting = """table ip mangle {
	chain PREROUTING {
		type filter hook prerouting priority mangle; policy accept;
		counter jump WANLOADBALANCE_PRE
	}
}"""
        mangle_wanloadbalance_pre = """table ip mangle {
	chain WANLOADBALANCE_PRE {
		iifname "veth3" ip saddr 198.51.100.0/24 ct state new meta random & 2147483647 < 1073741824 counter jump ISP_veth1
		iifname "veth3" ip saddr 198.51.100.0/24 ct state new counter jump ISP_veth2
		iifname "veth3" ip saddr 198.51.100.0/24 counter meta mark set ct mark
	}
}"""
        nat_wanloadbalance = """table ip nat {
	chain WANLOADBALANCE {
		ct mark 0xc9 counter snat to 203.0.113.10
		ct mark 0xca counter snat to 192.0.2.10
	}
}"""
        nat_vyos_pre_snat_hook = """table ip nat {
	chain VYOS_PRE_SNAT_HOOK {
		type nat hook postrouting priority srcnat - 1; policy accept;
		counter jump WANLOADBALANCE
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
        self.cli_set(base_path + ['wan', 'rule', '10', 'interface', iface2])

        # commit changes
        self.cli_commit()

        time.sleep(5)

        # Check mangle chains
        tmp = cmd(f'sudo nft -s list chain mangle ISP_{iface1}')
        self.assertEqual(tmp, mangle_isp1)

        tmp = cmd(f'sudo nft -s list chain mangle ISP_{iface2}')
        self.assertEqual(tmp, mangle_isp2)

        tmp = cmd(f'sudo nft -s list chain mangle PREROUTING')
        self.assertEqual(tmp, mangle_prerouting)

        tmp = cmd(f'sudo nft -s list chain mangle WANLOADBALANCE_PRE')
        self.assertEqual(tmp, mangle_wanloadbalance_pre)

        # Check nat chains
        tmp = cmd(f'sudo nft -s list chain nat WANLOADBALANCE')
        self.assertEqual(tmp, nat_wanloadbalance)

        tmp = cmd(f'sudo nft -s list chain nat VYOS_PRE_SNAT_HOOK')
        self.assertEqual(tmp, nat_vyos_pre_snat_hook)

        # Delete veth interfaces and netns
        for iface in [iface1, iface2, iface3]:
            call(f'sudo ip link del dev {iface}')

        delete_netns(ns1)
        delete_netns(ns2)
        delete_netns(ns3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
