# Copyright (C) 2019-2022 VyOS maintainers and contributors
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

from binascii import hexlify

from netifaces import AF_INET
from netifaces import AF_INET6
from netifaces import ifaddresses
from netifaces import interfaces

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.ifconfig import Interface
from vyos.ifconfig import Section
from vyos.util import read_file
from vyos.util import cmd
from vyos.util import dict_search
from vyos.util import process_named_running
from vyos.util import get_interface_config
from vyos.validate import is_intf_addr_assigned
from vyos.validate import is_ipv6_link_local

def is_mirrored_to(interface, mirror_if, qdisc):
    """
    Ask TC if we are mirroring traffic to a discrete interface.

    interface: source interface
    mirror_if: destination where we mirror our data to
    qdisc: must be ffff or 1 for ingress/egress
    """
    if qdisc not in ['ffff', '1']:
        raise ValueError()

    ret_val = False
    tmp = cmd(f'tc -s -p filter ls dev {interface} parent {qdisc}: | grep mirred')
    tmp = tmp.lower()
    if mirror_if in tmp:
        ret_val = True
    return ret_val

class BasicInterfaceTest:
    class TestCase(VyOSUnitTestSHIM.TestCase):
        _test_dhcp = False
        _test_ip = False
        _test_mtu = False
        _test_vlan = False
        _test_qinq = False
        _test_ipv6 = False
        _test_ipv6_pd = False
        _test_ipv6_dhcpc6 = False
        _test_mirror = False
        _base_path = []

        _options = {}
        _interfaces = []
        _qinq_range = ['10', '20', '30']
        _vlan_range = ['100', '200', '300', '2000']
        _test_addr = ['192.0.2.1/26', '192.0.2.255/31', '192.0.2.64/32',
                      '2001:db8:1::ffff/64', '2001:db8:101::1/112']

        _mirror_interfaces = []
        # choose IPv6 minimum MTU value for tests - this must always work
        _mtu = '1280'

        @classmethod
        def setUpClass(cls):
            super(BasicInterfaceTest.TestCase, cls).setUpClass()

            # Setup mirror interfaces for SPAN (Switch Port Analyzer)
            for span in cls._mirror_interfaces:
                section = Section.section(span)
                cls.cli_set(cls, ['interfaces', section, span])

        @classmethod
        def tearDownClass(cls):
            # Tear down mirror interfaces for SPAN (Switch Port Analyzer)
            for span in cls._mirror_interfaces:
                section = Section.section(span)
                cls.cli_delete(cls, ['interfaces', section, span])

            super(BasicInterfaceTest.TestCase, cls).tearDownClass()

        def tearDown(self):
            self.cli_delete(self._base_path)
            self.cli_commit()

            # Verify that no previously interface remained on the system
            for intf in self._interfaces:
                self.assertNotIn(intf, interfaces())

            # No daemon that was started during a test should remain running
            for daemon in ['dhcp6c', 'dhclient']:
                self.assertFalse(process_named_running(daemon))

        def test_dhcp_disable_interface(self):
            if not self._test_dhcp:
                self.skipTest('not supported')

            # When interface is configured as admin down, it must be admin down
            # even when dhcpc starts on the given interface
            for interface in self._interfaces:
                self.cli_set(self._base_path + [interface, 'disable'])
                for option in self._options.get(interface, []):
                    self.cli_set(self._base_path + [interface] + option.split())

                self.cli_set(self._base_path + [interface, 'disable'])

                # Also enable DHCP (ISC DHCP always places interface in admin up
                # state so we check that we do not start DHCP client.
                # https://phabricator.vyos.net/T2767
                self.cli_set(self._base_path + [interface, 'address', 'dhcp'])

            self.cli_commit()

            # Validate interface state
            for interface in self._interfaces:
                flags = read_file(f'/sys/class/net/{interface}/flags')
                self.assertEqual(int(flags, 16) & 1, 0)

        def test_span_mirror(self):
            if not self._mirror_interfaces:
                self.skipTest('not supported')

            # Check the two-way mirror rules of ingress and egress
            for mirror in self._mirror_interfaces:
                for interface in self._interfaces:
                    self.cli_set(self._base_path + [interface, 'mirror', 'ingress', mirror])
                    self.cli_set(self._base_path + [interface, 'mirror', 'egress',  mirror])

            self.cli_commit()

            # Verify config
            for mirror in self._mirror_interfaces:
                for interface in self._interfaces:
                    self.assertTrue(is_mirrored_to(interface, mirror, 'ffff'))
                    self.assertTrue(is_mirrored_to(interface, mirror, '1'))

        def test_interface_disable(self):
            # Check if description can be added to interface and
            # can be read back
            for intf in self._interfaces:
                self.cli_set(self._base_path + [intf, 'disable'])
                for option in self._options.get(intf, []):
                    self.cli_set(self._base_path + [intf] + option.split())

            self.cli_commit()

            # Validate interface description
            for intf in self._interfaces:
                self.assertEqual(Interface(intf).get_admin_state(), 'down')

        def test_interface_description(self):
            # Check if description can be added to interface and
            # can be read back
            for intf in self._interfaces:
                test_string=f'Description-Test-{intf}'
                self.cli_set(self._base_path + [intf, 'description', test_string])
                for option in self._options.get(intf, []):
                    self.cli_set(self._base_path + [intf] + option.split())

            self.cli_commit()

            # Validate interface description
            for intf in self._interfaces:
                test_string=f'Description-Test-{intf}'
                tmp = read_file(f'/sys/class/net/{intf}/ifalias')
                self.assertEqual(tmp, test_string)
                self.assertEqual(Interface(intf).get_alias(), test_string)
                self.cli_delete(self._base_path + [intf, 'description'])

            self.cli_commit()

            # Validate remove interface description "empty"
            for intf in self._interfaces:
                tmp = read_file(f'/sys/class/net/{intf}/ifalias')
                self.assertEqual(tmp, str())
                self.assertEqual(Interface(intf).get_alias(), str())

        def test_add_single_ip_address(self):
            addr = '192.0.2.0/31'
            for intf in self._interfaces:
                self.cli_set(self._base_path + [intf, 'address', addr])
                for option in self._options.get(intf, []):
                    self.cli_set(self._base_path + [intf] + option.split())

            self.cli_commit()

            for intf in self._interfaces:
                self.assertTrue(is_intf_addr_assigned(intf, addr))
                self.assertEqual(Interface(intf).get_admin_state(), 'up')

        def test_add_multiple_ip_addresses(self):
            # Add address
            for intf in self._interfaces:
                for option in self._options.get(intf, []):
                    self.cli_set(self._base_path + [intf] + option.split())
                for addr in self._test_addr:
                    self.cli_set(self._base_path + [intf, 'address', addr])

            self.cli_commit()

            # Validate address
            for intf in self._interfaces:
                for af in AF_INET, AF_INET6:
                    for addr in ifaddresses(intf)[af]:
                        # checking link local addresses makes no sense
                        if is_ipv6_link_local(addr['addr']):
                            continue

                        self.assertTrue(is_intf_addr_assigned(intf, addr['addr']))

        def test_ipv6_link_local_address(self):
            # Common function for IPv6 link-local address assignemnts
            if not self._test_ipv6:
                self.skipTest('not supported')

            for interface in self._interfaces:
                base = self._base_path + [interface]
                # just set the interface base without any option - some interfaces
                # (VTI) do not require any option to be brought up
                self.cli_set(base)
                for option in self._options.get(interface, []):
                    self.cli_set(base + option.split())

            # after commit we must have an IPv6 link-local address
            self.cli_commit()

            for interface in self._interfaces:
                self.assertIn(AF_INET6, ifaddresses(interface))
                for addr in ifaddresses(interface)[AF_INET6]:
                    self.assertTrue(is_ipv6_link_local(addr['addr']))

            # disable IPv6 link-local address assignment
            for interface in self._interfaces:
                base = self._base_path + [interface]
                self.cli_set(base + ['ipv6', 'address', 'no-default-link-local'])

            # after commit we must have no IPv6 link-local address
            self.cli_commit()

            for interface in self._interfaces:
                self.assertNotIn(AF_INET6, ifaddresses(interface))

        def test_interface_mtu(self):
            if not self._test_mtu:
                self.skipTest('not supported')

            for intf in self._interfaces:
                base = self._base_path + [intf]
                self.cli_set(base + ['mtu', self._mtu])
                for option in self._options.get(intf, []):
                    self.cli_set(base + option.split())

            # commit interface changes
            self.cli_commit()

            # verify changed MTU
            for intf in self._interfaces:
                tmp = get_interface_config(intf)
                self.assertEqual(tmp['mtu'], int(self._mtu))

        def test_mtu_1200_no_ipv6_interface(self):
            # Testcase if MTU can be changed to 1200 on non IPv6
            # enabled interfaces
            if not self._test_mtu:
                self.skipTest('not supported')

            old_mtu = self._mtu
            self._mtu = '1200'

            for intf in self._interfaces:
                base = self._base_path + [intf]
                self.cli_set(base + ['mtu', self._mtu])

                for option in self._options.get(intf, []):
                    self.cli_set(base + option.split())

            # check validate() - can not set low MTU if 'no-default-link-local'
            # is not set on CLI
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()

            for intf in self._interfaces:
                base = self._base_path + [intf]
                self.cli_set(base + ['ipv6', 'address', 'no-default-link-local'])

            # commit interface changes
            self.cli_commit()

            # verify changed MTU
            for intf in self._interfaces:
                tmp = get_interface_config(intf)
                self.assertEqual(tmp['mtu'], int(self._mtu))

            self._mtu = old_mtu

        def test_vif_8021q_interfaces(self):
            # XXX: This testcase is not allowed to run as first testcase, reason
            # is the Wireless test will first load the wifi kernel hwsim module
            # which creates a wlan0 and wlan1 interface which will fail the
            # tearDown() test in the end that no interface is allowed to survive!
            if not self._test_vlan:
                self.skipTest('not supported')

            for interface in self._interfaces:
                base = self._base_path + [interface]
                for option in self._options.get(interface, []):
                    self.cli_set(base + option.split())

                for vlan in self._vlan_range:
                    base = self._base_path + [interface, 'vif', vlan]
                    for address in self._test_addr:
                        self.cli_set(base + ['address', address])

            self.cli_commit()

            for intf in self._interfaces:
                for vlan in self._vlan_range:
                    vif = f'{intf}.{vlan}'
                    for address in self._test_addr:
                        self.assertTrue(is_intf_addr_assigned(vif, address))

                    self.assertEqual(Interface(vif).get_admin_state(), 'up')

            # T4064: Delete interface addresses, keep VLAN interface
            for interface in self._interfaces:
                base = self._base_path + [interface]
                for vlan in self._vlan_range:
                    base = self._base_path + [interface, 'vif', vlan]
                    self.cli_delete(base + ['address'])

            self.cli_commit()

            # Verify no IP address is assigned
            for interface in self._interfaces:
                for vlan in self._vlan_range:
                    vif = f'{intf}.{vlan}'
                    for address in self._test_addr:
                        self.assertFalse(is_intf_addr_assigned(vif, address))


        def test_vif_8021q_mtu_limits(self):
            # XXX: This testcase is not allowed to run as first testcase, reason
            # is the Wireless test will first load the wifi kernel hwsim module
            # which creates a wlan0 and wlan1 interface which will fail the
            # tearDown() test in the end that no interface is allowed to survive!
            if not self._test_vlan:
                self.skipTest('not supported')

            mtu_1500 = '1500'
            mtu_9000 = '9000'

            for interface in self._interfaces:
                base = self._base_path + [interface]
                self.cli_set(base + ['mtu', mtu_1500])
                for option in self._options.get(interface, []):
                    self.cli_set(base + option.split())
                    if 'source-interface' in option:
                        iface = option.split()[-1]
                        iface_type = Section.section(iface)
                        self.cli_set(['interfaces', iface_type, iface, 'mtu', mtu_9000])

                for vlan in self._vlan_range:
                    base = self._base_path + [interface, 'vif', vlan]
                    self.cli_set(base + ['mtu', mtu_9000])

            # check validate() - VIF MTU must not be larger the parent interface
            # MTU size.
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()

            # Change MTU on base interface to be the same as on the VIF interface
            for interface in self._interfaces:
                base = self._base_path + [interface]
                self.cli_set(base + ['mtu', mtu_9000])

            self.cli_commit()

            # Verify MTU on base and VIF interfaces
            for interface in self._interfaces:
                tmp = get_interface_config(interface)
                self.assertEqual(tmp['mtu'], int(mtu_9000))

                for vlan in self._vlan_range:
                    tmp = get_interface_config(f'{interface}.{vlan}')
                    self.assertEqual(tmp['mtu'], int(mtu_9000))


        def test_vif_8021q_qos_change(self):
            # XXX: This testcase is not allowed to run as first testcase, reason
            # is the Wireless test will first load the wifi kernel hwsim module
            # which creates a wlan0 and wlan1 interface which will fail the
            # tearDown() test in the end that no interface is allowed to survive!
            if not self._test_vlan:
                self.skipTest('not supported')

            for interface in self._interfaces:
                base = self._base_path + [interface]
                for option in self._options.get(interface, []):
                    self.cli_set(base + option.split())

                for vlan in self._vlan_range:
                    base = self._base_path + [interface, 'vif', vlan]
                    self.cli_set(base + ['ingress-qos', '0:1'])
                    self.cli_set(base + ['egress-qos', '1:6'])

            self.cli_commit()

            for intf in self._interfaces:
                for vlan in self._vlan_range:
                    vif = f'{intf}.{vlan}'
                    tmp = get_interface_config(f'{vif}')

                    tmp2 = dict_search('linkinfo.info_data.ingress_qos', tmp)
                    for item in tmp2 if tmp2 else []:
                        from_key = item['from']
                        to_key = item['to']
                        self.assertEqual(from_key, 0)
                        self.assertEqual(to_key, 1)

                    tmp2 = dict_search('linkinfo.info_data.egress_qos', tmp)
                    for item in tmp2 if tmp2 else []:
                        from_key = item['from']
                        to_key = item['to']
                        self.assertEqual(from_key, 1)
                        self.assertEqual(to_key, 6)

                    self.assertEqual(Interface(vif).get_admin_state(), 'up')

            new_ingress_qos_from = 1
            new_ingress_qos_to = 6
            new_egress_qos_from = 2
            new_egress_qos_to = 7
            for interface in self._interfaces:
                base = self._base_path + [interface]
                for vlan in self._vlan_range:
                    base = self._base_path + [interface, 'vif', vlan]
                    self.cli_set(base + ['ingress-qos', f'{new_ingress_qos_from}:{new_ingress_qos_to}'])
                    self.cli_set(base + ['egress-qos', f'{new_egress_qos_from}:{new_egress_qos_to}'])

            self.cli_commit()

            for intf in self._interfaces:
                for vlan in self._vlan_range:
                    vif = f'{intf}.{vlan}'
                    tmp = get_interface_config(f'{vif}')

                    tmp2 = dict_search('linkinfo.info_data.ingress_qos', tmp)
                    if tmp2:
                        from_key = tmp2[0]['from']
                        to_key = tmp2[0]['to']
                        self.assertEqual(from_key, new_ingress_qos_from)
                        self.assertEqual(to_key, new_ingress_qos_to)

                    tmp2 = dict_search('linkinfo.info_data.egress_qos', tmp)
                    if tmp2:
                        from_key = tmp2[0]['from']
                        to_key = tmp2[0]['to']
                        self.assertEqual(from_key, new_egress_qos_from)
                        self.assertEqual(to_key, new_egress_qos_to)

        def test_vif_8021q_lower_up_down(self):
            # Testcase for https://phabricator.vyos.net/T3349
            if not self._test_vlan:
                self.skipTest('not supported')

            for interface in self._interfaces:
                base = self._base_path + [interface]
                for option in self._options.get(interface, []):
                    self.cli_set(base + option.split())

                # disable the lower interface
                self.cli_set(base + ['disable'])

                for vlan in self._vlan_range:
                    vlan_base = self._base_path + [interface, 'vif', vlan]
                    # disable the vlan interface
                    self.cli_set(vlan_base + ['disable'])

            self.cli_commit()

            # re-enable all lower interfaces
            for interface in self._interfaces:
                base = self._base_path + [interface]
                self.cli_delete(base + ['disable'])

            self.cli_commit()

            # verify that the lower interfaces are admin up and the vlan
            # interfaces are all admin down
            for interface in self._interfaces:
                self.assertEqual(Interface(interface).get_admin_state(), 'up')

                for vlan in self._vlan_range:
                    ifname = f'{interface}.{vlan}'
                    self.assertEqual(Interface(ifname).get_admin_state(), 'down')


        def test_vif_s_8021ad_vlan_interfaces(self):
            # XXX: This testcase is not allowed to run as first testcase, reason
            # is the Wireless test will first load the wifi kernel hwsim module
            # which creates a wlan0 and wlan1 interface which will fail the
            # tearDown() test in the end that no interface is allowed to survive!
            if not self._test_qinq:
                self.skipTest('not supported')

            for interface in self._interfaces:
                base = self._base_path + [interface]
                for option in self._options.get(interface, []):
                    self.cli_set(base + option.split())

                for vif_s in self._qinq_range:
                    for vif_c in self._vlan_range:
                        base = self._base_path + [interface, 'vif-s', vif_s, 'vif-c', vif_c]
                        self.cli_set(base + ['mtu', self._mtu])
                        for address in self._test_addr:
                            self.cli_set(base + ['address', address])

            self.cli_commit()

            for interface in self._interfaces:
                for vif_s in self._qinq_range:
                    tmp = get_interface_config(f'{interface}.{vif_s}')
                    self.assertEqual(dict_search('linkinfo.info_data.protocol', tmp), '802.1ad')

                    for vif_c in self._vlan_range:
                        vif = f'{interface}.{vif_s}.{vif_c}'
                        # For an unknown reason this regularely fails on the QEMU builds,
                        # thus the test for reading back IP addresses is temporary
                        # disabled. There is no big deal here, as this uses the same
                        # methods on 802.1q and here it works and is verified.
#                       for address in self._test_addr:
#                           self.assertTrue(is_intf_addr_assigned(vif, address))

                        tmp = get_interface_config(vif)
                        self.assertEqual(tmp['mtu'], int(self._mtu))


            # T4064: Delete interface addresses, keep VLAN interface
            for interface in self._interfaces:
                base = self._base_path + [interface]
                for vif_s in self._qinq_range:
                    for vif_c in self._vlan_range:
                        self.cli_delete(self._base_path + [interface, 'vif-s', vif_s, 'vif-c', vif_c, 'address'])

            self.cli_commit()
            # Verify no IP address is assigned
            for interface in self._interfaces:
                base = self._base_path + [interface]
                for vif_s in self._qinq_range:
                    for vif_c in self._vlan_range:
                        vif = f'{interface}.{vif_s}.{vif_c}'
                        for address in self._test_addr:
                            self.assertFalse(is_intf_addr_assigned(vif, address))

            # T3972: remove vif-c interfaces from vif-s
            for interface in self._interfaces:
                base = self._base_path + [interface]
                for vif_s in self._qinq_range:
                    base = self._base_path + [interface, 'vif-s', vif_s, 'vif-c']
                    self.cli_delete(base)

            self.cli_commit()


        def test_vif_s_protocol_change(self):
            # XXX: This testcase is not allowed to run as first testcase, reason
            # is the Wireless test will first load the wifi kernel hwsim module
            # which creates a wlan0 and wlan1 interface which will fail the
            # tearDown() test in the end that no interface is allowed to survive!
            if not self._test_qinq:
                self.skipTest('not supported')

            for interface in self._interfaces:
                base = self._base_path + [interface]
                for option in self._options.get(interface, []):
                    self.cli_set(base + option.split())

                for vif_s in self._qinq_range:
                    for vif_c in self._vlan_range:
                        base = self._base_path + [interface, 'vif-s', vif_s, 'vif-c', vif_c]
                        for address in self._test_addr:
                            self.cli_set(base + ['address', address])

            self.cli_commit()

            for interface in self._interfaces:
                for vif_s in self._qinq_range:
                    tmp = get_interface_config(f'{interface}.{vif_s}')
                    # check for the default value
                    self.assertEqual(tmp['linkinfo']['info_data']['protocol'], '802.1ad')

            # T3532: now change ethertype
            new_protocol = '802.1q'
            for interface in self._interfaces:
                for vif_s in self._qinq_range:
                    base = self._base_path + [interface, 'vif-s', vif_s]
                    self.cli_set(base + ['protocol', new_protocol])

            self.cli_commit()

            # Verify new ethertype configuration
            for interface in self._interfaces:
                for vif_s in self._qinq_range:
                    tmp = get_interface_config(f'{interface}.{vif_s}')
                    self.assertEqual(tmp['linkinfo']['info_data']['protocol'], new_protocol.upper())

        def test_interface_ip_options(self):
            if not self._test_ip:
                self.skipTest('not supported')

            arp_tmo = '300'
            mss = '1420'

            for interface in self._interfaces:
                path = self._base_path + [interface]
                for option in self._options.get(interface, []):
                    self.cli_set(path + option.split())

                # Options
                self.cli_set(path + ['ip', 'adjust-mss', mss])
                self.cli_set(path + ['ip', 'arp-cache-timeout', arp_tmo])
                self.cli_set(path + ['ip', 'disable-arp-filter'])
                self.cli_set(path + ['ip', 'disable-forwarding'])
                self.cli_set(path + ['ip', 'enable-directed-broadcast'])
                self.cli_set(path + ['ip', 'enable-arp-accept'])
                self.cli_set(path + ['ip', 'enable-arp-announce'])
                self.cli_set(path + ['ip', 'enable-arp-ignore'])
                self.cli_set(path + ['ip', 'enable-proxy-arp'])
                self.cli_set(path + ['ip', 'proxy-arp-pvlan'])
                self.cli_set(path + ['ip', 'source-validation', 'loose'])

            self.cli_commit()

            for interface in self._interfaces:
                base_options = f'oifname "{interface}"'
                out = cmd('sudo nft list chain raw VYOS_TCP_MSS')
                for line in out.splitlines():
                    if line.startswith(base_options):
                        self.assertIn(f'tcp option maxseg size set {mss}', line)

                tmp = read_file(f'/proc/sys/net/ipv4/neigh/{interface}/base_reachable_time_ms')
                self.assertEqual(tmp, str((int(arp_tmo) * 1000))) # tmo value is in milli seconds

                proc_base = f'/proc/sys/net/ipv4/conf/{interface}'

                tmp = read_file(f'{proc_base}/arp_filter')
                self.assertEqual('0', tmp)

                tmp = read_file(f'{proc_base}/arp_accept')
                self.assertEqual('1', tmp)

                tmp = read_file(f'{proc_base}/arp_announce')
                self.assertEqual('1', tmp)

                tmp = read_file(f'{proc_base}/arp_ignore')
                self.assertEqual('1', tmp)

                tmp = read_file(f'{proc_base}/forwarding')
                self.assertEqual('0', tmp)

                tmp = read_file(f'{proc_base}/bc_forwarding')
                self.assertEqual('1', tmp)

                tmp = read_file(f'{proc_base}/proxy_arp')
                self.assertEqual('1', tmp)

                tmp = read_file(f'{proc_base}/proxy_arp_pvlan')
                self.assertEqual('1', tmp)

                tmp = read_file(f'{proc_base}/rp_filter')
                self.assertEqual('2', tmp)

        def test_interface_ipv6_options(self):
            if not self._test_ipv6:
                self.skipTest('not supported')

            mss = '1400'
            dad_transmits = '10'

            for interface in self._interfaces:
                path = self._base_path + [interface]
                for option in self._options.get(interface, []):
                    self.cli_set(path + option.split())

                # Options
                self.cli_set(path + ['ipv6', 'adjust-mss', mss])
                self.cli_set(path + ['ipv6', 'disable-forwarding'])
                self.cli_set(path + ['ipv6', 'dup-addr-detect-transmits', dad_transmits])

            self.cli_commit()

            for interface in self._interfaces:
                base_options = f'oifname "{interface}"'
                out = cmd('sudo nft list chain ip6 raw VYOS_TCP_MSS')
                for line in out.splitlines():
                    if line.startswith(base_options):
                        self.assertIn(f'tcp option maxseg size set {mss}', line)

                proc_base = f'/proc/sys/net/ipv6/conf/{interface}'

                tmp = read_file(f'{proc_base}/forwarding')
                self.assertEqual('0', tmp)

                tmp = read_file(f'{proc_base}/dad_transmits')
                self.assertEqual(dad_transmits, tmp)

        def test_dhcpv6_client_options(self):
            if not self._test_ipv6_dhcpc6:
                self.skipTest('not supported')

            duid_base = 10
            for interface in self._interfaces:
                duid = '00:01:00:01:27:71:db:f0:00:50:00:00:00:{}'.format(duid_base)
                path = self._base_path + [interface]
                for option in self._options.get(interface, []):
                    self.cli_set(path + option.split())

                # Enable DHCPv6 client
                self.cli_set(path + ['address', 'dhcpv6'])
                self.cli_set(path + ['dhcpv6-options', 'rapid-commit'])
                self.cli_set(path + ['dhcpv6-options', 'parameters-only'])
                self.cli_set(path + ['dhcpv6-options', 'duid', duid])
                duid_base += 1

            self.cli_commit()

            duid_base = 10
            for interface in self._interfaces:
                duid = '00:01:00:01:27:71:db:f0:00:50:00:00:00:{}'.format(duid_base)
                dhcpc6_config = read_file(f'/run/dhcp6c/dhcp6c.{interface}.conf')
                self.assertIn(f'interface {interface} ' + '{', dhcpc6_config)
                self.assertIn(f'  request domain-name-servers;', dhcpc6_config)
                self.assertIn(f'  request domain-name;', dhcpc6_config)
                self.assertIn(f'  information-only;', dhcpc6_config)
                self.assertIn(f'  send ia-na 0;', dhcpc6_config)
                self.assertIn(f'  send rapid-commit;', dhcpc6_config)
                self.assertIn(f'  send client-id {duid};', dhcpc6_config)
                self.assertIn('};', dhcpc6_config)
                duid_base += 1

            # Check for running process
            self.assertTrue(process_named_running('dhcp6c'))

        def test_dhcpv6pd_auto_sla_id(self):
            if not self._test_ipv6_pd:
                self.skipTest('not supported')

            prefix_len = '56'
            sla_len = str(64 - int(prefix_len))

            delegatees = ['dum2340', 'dum2341', 'dum2342', 'dum2343', 'dum2344']

            for interface in self._interfaces:
                path = self._base_path + [interface]
                for option in self._options.get(interface, []):
                    self.cli_set(path + option.split())

                address = '1'
                # prefix delegation stuff
                pd_base = path + ['dhcpv6-options', 'pd', '0']
                self.cli_set(pd_base + ['length', prefix_len])

                for delegatee in delegatees:
                    section = Section.section(delegatee)
                    self.cli_set(['interfaces', section, delegatee])
                    self.cli_set(pd_base + ['interface', delegatee, 'address', address])
                    # increment interface address
                    address = str(int(address) + 1)

            self.cli_commit()

            for interface in self._interfaces:
                dhcpc6_config = read_file(f'/run/dhcp6c/dhcp6c.{interface}.conf')

                # verify DHCPv6 prefix delegation
                self.assertIn(f'prefix ::/{prefix_len} infinity;', dhcpc6_config)

                address = '1'
                sla_id = '0'
                for delegatee in delegatees:
                    self.assertIn(f'prefix-interface {delegatee}' + r' {', dhcpc6_config)
                    self.assertIn(f'ifid {address};', dhcpc6_config)
                    self.assertIn(f'sla-id {sla_id};', dhcpc6_config)
                    self.assertIn(f'sla-len {sla_len};', dhcpc6_config)

                    # increment sla-id
                    sla_id = str(int(sla_id) + 1)
                    # increment interface address
                    address = str(int(address) + 1)

            # Check for running process
            self.assertTrue(process_named_running('dhcp6c'))

            for delegatee in delegatees:
                # we can already cleanup the test delegatee interface here
                # as until commit() is called, nothing happens
                section = Section.section(delegatee)
                self.cli_delete(['interfaces', section, delegatee])

        def test_dhcpv6pd_manual_sla_id(self):
            if not self._test_ipv6_pd:
                self.skipTest('not supported')

            prefix_len = '56'
            sla_len = str(64 - int(prefix_len))

            delegatees = ['dum3340', 'dum3341', 'dum3342', 'dum3343', 'dum3344']

            for interface in self._interfaces:
                path = self._base_path + [interface]
                for option in self._options.get(interface, []):
                    self.cli_set(path + option.split())

                # prefix delegation stuff
                address = '1'
                sla_id = '1'
                pd_base = path + ['dhcpv6-options', 'pd', '0']
                self.cli_set(pd_base + ['length', prefix_len])

                for delegatee in delegatees:
                    section = Section.section(delegatee)
                    self.cli_set(['interfaces', section, delegatee])
                    self.cli_set(pd_base + ['interface', delegatee, 'address', address])
                    self.cli_set(pd_base + ['interface', delegatee, 'sla-id', sla_id])

                    # increment interface address
                    address = str(int(address) + 1)
                    sla_id = str(int(sla_id) + 1)

            self.cli_commit()

            # Verify dhcpc6 client configuration
            for interface in self._interfaces:
                address = '1'
                sla_id = '1'
                dhcpc6_config = read_file(f'/run/dhcp6c/dhcp6c.{interface}.conf')

                # verify DHCPv6 prefix delegation
                self.assertIn(f'prefix ::/{prefix_len} infinity;', dhcpc6_config)

                for delegatee in delegatees:
                    self.assertIn(f'prefix-interface {delegatee}' + r' {', dhcpc6_config)
                    self.assertIn(f'ifid {address};', dhcpc6_config)
                    self.assertIn(f'sla-id {sla_id};', dhcpc6_config)
                    self.assertIn(f'sla-len {sla_len};', dhcpc6_config)

                    # increment sla-id
                    sla_id = str(int(sla_id) + 1)
                    # increment interface address
                    address = str(int(address) + 1)

            # Check for running process
            self.assertTrue(process_named_running('dhcp6c'))

            for delegatee in delegatees:
                # we can already cleanup the test delegatee interface here
                # as until commit() is called, nothing happens
                section = Section.section(delegatee)
                self.cli_delete(['interfaces', section, delegatee])
