# Copyright (C) 2019-2020 VyOS maintainers and contributors
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
import unittest
import json

from netifaces import ifaddresses
from netifaces import AF_INET
from netifaces import AF_INET6

from vyos.configsession import ConfigSession
from vyos.ifconfig import Interface
from vyos.util import read_file
from vyos.util import cmd
from vyos.util import dict_search
from vyos.validate import is_intf_addr_assigned
from vyos.validate import is_ipv6_link_local

def read_mirror_rule(interfaces):
    Success = 0
    for interface in interfaces:
        get_tc_cmd = 'tc -j qdisc'
        tmp = cmd(get_tc_cmd, shell=True)
        data = json.loads(tmp)
        for rule in data:
            dev = rule['dev']
            handle = rule['handle']
            kind = rule['kind']
            if dev == interface and handle == "ffff:" and kind == "ingress":
                Success+=1
            elif dev == interface and handle == "1:" and kind == "prio":
                Success+=1
    return Success

class BasicInterfaceTest:
    class BaseTest(unittest.TestCase):
        _test_ip = False
        _test_mtu = False
        _test_vlan = False
        _test_qinq = False
        _test_ipv6 = False
        _test_mirror = False
        _base_path = []

        _options = {}
        _interfaces = []
        _qinq_range = ['10', '20', '30']
        _vlan_range = ['100', '200', '300', '2000']
        # choose IPv6 minimum MTU value for tests - this must always work
        _mtu = '1280'

        def setUp(self):
            self.session = ConfigSession(os.getpid())

            self._test_addr = ['192.0.2.1/26', '192.0.2.255/31', '192.0.2.64/32',
                                '2001:db8:1::ffff/64', '2001:db8:101::1/112']
            self._test_mtu = False
            self._options = {}

        def tearDown(self):
            # we should not remove ethernet from the overall CLI
            if 'ethernet' in self._base_path:
                for interface in self._interfaces:
                    # when using a dedicated interface to test via TEST_ETH environment
                    # variable only this one will be cleared in the end - usable to test
                    # ethernet interfaces via SSH
                    self.session.delete(self._base_path + [interface])
                    self.session.set(self._base_path + [interface, 'duplex', 'auto'])
                    self.session.set(self._base_path + [interface, 'speed', 'auto'])
            else:
                self.session.delete(self._base_path)

            self.session.commit()
            del self.session

        def test_mirror(self):
            
            if self._test_mirror:
                
                # Create test dependency interface
                self.session.set(['interfaces','dummy','dum0'])
                self.session.set(['interfaces','dummy','dum1'])
                self.session.set(['interfaces','bonding','bond1','member','interface','dum0'])
                self.session.set(['interfaces','bonding','bond1','member','interface','dum1'])
                
                Success = 0
                i = 0
                # Check the two-way mirror rules of ingress and egress
                for interface in self._interfaces:
                    self.session.set(self._base_path + [interface, 'mirror', 'ingress', 'bond1'])
                    self.session.set(self._base_path + [interface, 'mirror', 'egress', 'bond1'])
                    i+=1
                self.session.commit()
                # Parse configuration
                Success = read_mirror_rule(self._interfaces)
                if Success == i*2:
                    self.assertTrue(True)
                else:
                    self.assertTrue(False)
                i=0
                self.session.delete(['interfaces','dummy'])
                self.session.delete(['interfaces','bonding'])
            else:
                return None


        def test_add_description(self):
            """
            Check if description can be added to interface
            """
            for intf in self._interfaces:
                test_string=f'Description-Test-{intf}'
                self.session.set(self._base_path + [intf, 'description', test_string])
                for option in self._options.get(intf, []):
                    self.session.set(self._base_path + [intf] + option.split())

            self.session.commit()

            # Validate interface description
            for intf in self._interfaces:
                test_string=f'Description-Test-{intf}'
                with open(f'/sys/class/net/{intf}/ifalias', 'r') as f:
                    tmp = f.read().rstrip()
                    self.assertTrue(tmp, test_string)

        def test_add_address_single(self):
            """
            Check if a single address can be added to interface.
            """
            addr = '192.0.2.0/31'
            for intf in self._interfaces:
                self.session.set(self._base_path + [intf, 'address', addr])
                for option in self._options.get(intf, []):
                    self.session.set(self._base_path + [intf] + option.split())

            self.session.commit()

            for intf in self._interfaces:
                self.assertTrue(is_intf_addr_assigned(intf, addr))

        def test_add_address_multi(self):
            """
            Check if IPv4/IPv6 addresses can be added to interface.
            """

            # Add address
            for intf in self._interfaces:
                for addr in self._test_addr:
                    self.session.set(self._base_path + [intf, 'address', addr])
                    for option in self._options.get(intf, []):
                        self.session.set(self._base_path + [intf] + option.split())

            self.session.commit()

            # Validate address
            for intf in self._interfaces:
                for af in AF_INET, AF_INET6:
                    for addr in ifaddresses(intf)[af]:
                        # checking link local addresses makes no sense
                        if is_ipv6_link_local(addr['addr']):
                            continue

                        self.assertTrue(is_intf_addr_assigned(intf, addr['addr']))

        def test_ipv6_link_local(self):
            """ Common function for IPv6 link-local address assignemnts """
            if not self._test_ipv6:
                return None

            for interface in self._interfaces:
                base = self._base_path + [interface]
                for option in self._options.get(interface, []):
                    self.session.set(base + option.split())

            # after commit we must have an IPv6 link-local address
            self.session.commit()

            for interface in self._interfaces:
                for addr in ifaddresses(interface)[AF_INET6]:
                    self.assertTrue(is_ipv6_link_local(addr['addr']))

            # disable IPv6 link-local address assignment
            for interface in self._interfaces:
                base = self._base_path + [interface]
                self.session.set(base + ['ipv6', 'address', 'no-default-link-local'])

            # after commit we must have no IPv6 link-local address
            self.session.commit()

            for interface in self._interfaces:
                self.assertTrue(AF_INET6 not in ifaddresses(interface))

        def _mtu_test(self, intf):
            """ helper function to verify MTU size """
            with open(f'/sys/class/net/{intf}/mtu', 'r') as f:
                tmp = f.read().rstrip()
                self.assertEqual(tmp, self._mtu)

        def test_change_mtu(self):
            """ Testcase if MTU can be changed on interface """
            if not self._test_mtu:
                return None

            for intf in self._interfaces:
                base = self._base_path + [intf]
                self.session.set(base + ['mtu', self._mtu])
                for option in self._options.get(intf, []):
                    self.session.set(base + option.split())

            # commit interface changes
            self.session.commit()

            # verify changed MTU
            for intf in self._interfaces:
                self._mtu_test(intf)

        def test_change_mtu_1200(self):
            """ Testcase if MTU can be changed to 1200 on non IPv6 enabled interfaces """
            if not self._test_mtu:
                return None

            old_mtu = self._mtu
            self._mtu = '1200'

            for intf in self._interfaces:
                base = self._base_path + [intf]
                self.session.set(base + ['mtu', self._mtu])
                self.session.set(base + ['ipv6', 'address', 'no-default-link-local'])

                for option in self._options.get(intf, []):
                    self.session.set(base + option.split())

            # commit interface changes
            self.session.commit()

            # verify changed MTU
            for intf in self._interfaces:
                self._mtu_test(intf)

            self._mtu = old_mtu

        def test_8021q_vlan(self):
            """ Testcase for 802.1q VLAN interfaces """
            if not self._test_vlan:
                return None

            for interface in self._interfaces:
                base = self._base_path + [interface]
                for option in self._options.get(interface, []):
                    self.session.set(base + option.split())

                for vlan in self._vlan_range:
                    base = self._base_path + [interface, 'vif', vlan]
                    self.session.set(base + ['mtu', self._mtu])
                    for address in self._test_addr:
                        self.session.set(base + ['address', address])

            self.session.commit()
            for intf in self._interfaces:
                for vlan in self._vlan_range:
                    vif = f'{intf}.{vlan}'
                    for address in self._test_addr:
                        self.assertTrue(is_intf_addr_assigned(vif, address))
                    self._mtu_test(vif)


        def test_8021ad_qinq_vlan(self):
            """ Testcase for 802.1ad Q-in-Q VLAN interfaces """
            if not self._test_qinq:
                return None

            for interface in self._interfaces:
                base = self._base_path + [interface]
                for option in self._options.get(interface, []):
                    self.session.set(base + option.split())

                for vif_s in self._qinq_range:
                    for vif_c in self._vlan_range:
                        base = self._base_path + [interface, 'vif-s', vif_s, 'vif-c', vif_c]
                        self.session.set(base + ['mtu', self._mtu])
                        for address in self._test_addr:
                            self.session.set(base + ['address', address])

            self.session.commit()

            for interface in self._interfaces:
                for vif_s in self._qinq_range:
                    tmp = json.loads(cmd(f'ip -d -j link show dev {interface}.{vif_s}'))[0]
                    self.assertEqual(dict_search('linkinfo.info_data.protocol', tmp), '802.1ad')

                    for vif_c in self._vlan_range:
                        vif = f'{interface}.{vif_s}.{vif_c}'
                        for address in self._test_addr:
                            self.assertTrue(is_intf_addr_assigned(vif, address))
                        self._mtu_test(vif)

        def test_ip_options(self):
            """ Test interface base IPv4 options """
            if not self._test_ip:
                return None

            for interface in self._interfaces:
                arp_tmo = '300'
                path = self._base_path + [interface]
                for option in self._options.get(interface, []):
                    self.session.set(path + option.split())

                # Options
                self.session.set(path + ['ip', 'arp-cache-timeout', arp_tmo])
                self.session.set(path + ['ip', 'disable-arp-filter'])
                self.session.set(path + ['ip', 'disable-forwarding'])
                self.session.set(path + ['ip', 'enable-arp-accept'])
                self.session.set(path + ['ip', 'enable-arp-announce'])
                self.session.set(path + ['ip', 'enable-arp-ignore'])
                self.session.set(path + ['ip', 'enable-proxy-arp'])
                self.session.set(path + ['ip', 'proxy-arp-pvlan'])
                self.session.set(path + ['ip', 'source-validation', 'loose'])

            self.session.commit()

            for interface in self._interfaces:
                tmp = read_file(f'/proc/sys/net/ipv4/neigh/{interface}/base_reachable_time_ms')
                self.assertEqual(tmp, str((int(arp_tmo) * 1000))) # tmo value is in milli seconds

                tmp = read_file(f'/proc/sys/net/ipv4/conf/{interface}/arp_filter')
                self.assertEqual('0', tmp)

                tmp = read_file(f'/proc/sys/net/ipv4/conf/{interface}/arp_accept')
                self.assertEqual('1', tmp)

                tmp = read_file(f'/proc/sys/net/ipv4/conf/{interface}/arp_announce')
                self.assertEqual('1', tmp)

                tmp = read_file(f'/proc/sys/net/ipv4/conf/{interface}/arp_ignore')
                self.assertEqual('1', tmp)

                tmp = read_file(f'/proc/sys/net/ipv4/conf/{interface}/forwarding')
                self.assertEqual('0', tmp)

                tmp = read_file(f'/proc/sys/net/ipv4/conf/{interface}/proxy_arp')
                self.assertEqual('1', tmp)

                tmp = read_file(f'/proc/sys/net/ipv4/conf/{interface}/proxy_arp_pvlan')
                self.assertEqual('1', tmp)

                tmp = read_file(f'/proc/sys/net/ipv4/conf/{interface}/rp_filter')
                self.assertEqual('2', tmp)

        def test_ipv6_options(self):
            """ Test interface base IPv6 options """
            if not self._test_ipv6:
                return None

            for interface in self._interfaces:
                dad_transmits = '10'
                path = self._base_path + [interface]
                for option in self._options.get(interface, []):
                    self.session.set(path + option.split())

                # Options
                self.session.set(path + ['ipv6', 'disable-forwarding'])
                self.session.set(path + ['ipv6', 'dup-addr-detect-transmits', dad_transmits])

            self.session.commit()

            for interface in self._interfaces:
                tmp = read_file(f'/proc/sys/net/ipv6/conf/{interface}/forwarding')
                self.assertEqual('0', tmp)

                tmp = read_file(f'/proc/sys/net/ipv6/conf/{interface}/dad_transmits')
                self.assertEqual(dad_transmits, tmp)
