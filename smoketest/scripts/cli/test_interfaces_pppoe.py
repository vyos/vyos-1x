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

import unittest

from psutil import process_iter
from ipaddress import IPv4Address
from ipaddress import IPv6Address
from ipaddress import IPv4Network
from ipaddress import IPv6Network
from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.utils.dict import dict_search_recursive
from vyos.utils.network import get_interface_address
from vyos.xml_ref import default_value

config_file: str = '/etc/ppp/peers/{}'
base_path: list = ['interfaces', 'pppoe']
veth_path: list = ['interfaces', 'virtual-ethernet']
pppoe_server_path = ['service', 'pppoe-server']
connect_timeout: int = 20
name_servers: list = ['1.1.1.1', '2.2.2.2']
ipv4_pool: str = '100.64.0.0/18'
ipv6_pool: str = '2001:db8:8000::/48'
ipv6_pool_pd: str = '2001:db8:9000::/48'

def calculate_ipv6_interface_address(prefix: IPv6Network, sla_id: int, interface_id: int):
    # Ensure SLA-ID is 8 bits
    if not (0 <= sla_id <= 0xFF):
        raise ValueError('SLA-ID must be an 8-bit integer (0-255)')

    # Ensure Interface ID is 64 bits
    if not (0 <= interface_id <= 0xFFFFFFFFFFFFFFFF):
        raise ValueError('Interface ID must be a 64-bit integer')

    # Build the /64 subnet from the PD prefix len + SLA-ID
    subnet_int = int(prefix.network_address) | (sla_id << 64)

    # Calculate full interface address
    return IPv6Address(subnet_int | interface_id)

def get_config_value(interface, key):
    with open(config_file.format(interface), 'r') as f:
        for line in f:
            if line.startswith(key):
                return list(line.split())
    return []

def wait_for_interface(interface: str, timeout=connect_timeout) -> bool:
    """ Wait until PPPoE interface has been connected to the BRAS """
    from time import time
    from time import sleep
    from vyos.utils.network import get_interface_config

    start_time = time()
    while not get_interface_config(interface):
        sleep(0.250)
        if time() - start_time >= timeout:
            return False
    return True

# add a classmethod to setup a temporaray PPPoE server for "proper" validation
class PPPoEInterfaceTest(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(PPPoEInterfaceTest, cls).setUpClass()
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)
        cls.cli_delete(cls, veth_path)
        cls.cli_delete(cls, pppoe_server_path)

        cls._interfaces = ['pppoe10', 'pppoe20', 'pppoe30']
        cls._source_interface = 'veth102'
        pppoe_server_interface = 'veth101'

        cls.cli_set(cls, veth_path + [pppoe_server_interface, 'peer-name', cls._source_interface])
        cls.cli_set(cls, veth_path + [cls._source_interface, 'peer-name', pppoe_server_interface])

        cls.cli_set(cls, pppoe_server_path + ['authentication', 'mode', 'local'])
        cls.cli_set(cls, pppoe_server_path + ['client-ip-pool', 'IPv4-POOL', 'range', ipv4_pool])
        cls.cli_set(cls, pppoe_server_path + ['client-ipv6-pool', 'IPv6-POOL', 'prefix', ipv6_pool, 'mask', '64'])
        cls.cli_set(cls, pppoe_server_path + ['client-ipv6-pool', 'IPv6-POOL', 'delegate', ipv6_pool_pd, 'delegation-prefix', '56'])
        cls.cli_set(cls, pppoe_server_path + ['default-ipv6-pool', 'IPv6-POOL'])
        cls.cli_set(cls, pppoe_server_path + ['default-pool', 'IPv4-POOL'])
        cls.cli_set(cls, pppoe_server_path + ['gateway-address', '100.64.0.1'])
        cls.cli_set(cls, pppoe_server_path + ['interface', pppoe_server_interface])
        for ns in name_servers:
            cls.cli_set(cls, pppoe_server_path + ['name-server', ns])
        cls.cli_set(cls, pppoe_server_path + ['ppp-options', 'disable-ccp'])
        cls.cli_set(cls, pppoe_server_path + ['ppp-options', 'ipv6', 'allow'])
        cls.cli_set(cls, pppoe_server_path + ['session-control', 'disable'])

        cls.u_p_dict = {}
        for interface in cls._interfaces:
            username = f'VyOS-user-{interface}'
            password = f'VyOS-passwd-{interface}'

            cls.cli_set(cls, pppoe_server_path + ['authentication', 'local-users',
                        'username', username, 'password', password])

            cls.u_p_dict[interface] = (username, password)

        # Start PPPoE server
        cls.cli_commit(cls)

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, base_path)
        cls.cli_delete(cls, veth_path)
        cls.cli_delete(cls, pppoe_server_path)
        # Stop PPPoE server
        cls.cli_commit(cls)

        super(PPPoEInterfaceTest, cls).tearDownClass()

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

        # always forward to base class
        super().tearDown()

    def _verify_interface_address(self, interface):
        # Verify that the assigned IPv4/IPv6 addresses from the BRAS (PPPoE
        # server) are from the assigned pools
        for address in get_interface_address(interface):
            if 'family' in address and address['family'] == 'inet':
                # The PPPoE assigned IPv4 address must be from our pool
                self.assertIn(IPv4Address(address['address']), IPv4Network(ipv4_pool))
            elif 'family' in address and address['family'] == 'inet6':
                # The PPPoE assigned IPv6 address must be from our pool
                ipv6 = IPv6Address(address['address'])
                if not ipv6.is_link_local:
                    self.assertIn(ipv6, IPv6Network(ipv6_pool))

    def test_pppoe_client(self):
        # Check if PPPoE dialer can be configured and runs
        mtu = '1400'

        for interface in self._interfaces:
            (user, passwd) = self.u_p_dict[interface]

            self.cli_set(base_path + [interface, 'authentication', 'username', user])
            self.cli_set(base_path + [interface, 'authentication', 'password', passwd])
            self.cli_set(base_path + [interface, 'mtu', mtu])
            self.cli_set(base_path + [interface, 'no-peer-dns'])

            # check validate() - a source-interface is required
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
            self.cli_set(base_path + [interface, 'source-interface', self._source_interface])

        # commit changes
        self.cli_commit()

        # verify configuration file(s)
        for interface in self._interfaces:
            self.assertTrue(wait_for_interface(interface),
                            msg=f'Interface {interface} not found after {connect_timeout} seconds!')

            (user, passwd) = self.u_p_dict[interface]

            tmp = get_config_value(interface, 'mtu')[1]
            self.assertEqual(tmp, mtu)
            # MRU must default to MTU if not specified on CLI
            tmp = get_config_value(interface, 'mru')[1]
            self.assertEqual(tmp, mtu)
            tmp = get_config_value(interface, 'user')[1].replace('"', '')
            self.assertEqual(tmp, user)
            tmp = get_config_value(interface, 'password')[1].replace('"', '')
            self.assertEqual(tmp, passwd)
            tmp = get_config_value(interface, 'ifname')[1]
            self.assertEqual(tmp, interface)

            # Validate and verify assigned IP addresses
            self._verify_interface_address(interface)

            # validate that we have learned a default route
            tmp = self.getFRRopmode('show ip route 0.0.0.0/0', json=True)
            # Test if we have a default route 0.0.0.0/0 pointing to our PPPoE interface
            tmp = dict_search_recursive(tmp, 'interfaceName')

            #self.assertTrue(any(iface == interface for (iface, _) in tmp))
        self.skipTest('Bug in FRR 10.2 - PPPoE interfaces sometimes carry ifIndex 0 which is invalid')

    def test_pppoe_client_disabled_interface(self):
        # Check if PPPoE Client can be disabled
        for interface in self._interfaces:
            (user, passwd) = self.u_p_dict[interface]

            self.cli_set(base_path + [interface, 'authentication', 'username', user])
            self.cli_set(base_path + [interface, 'authentication', 'password', passwd])
            self.cli_set(base_path + [interface, 'source-interface', self._source_interface])
            self.cli_set(base_path + [interface, 'disable'])

        self.cli_commit()

        # Validate PPPoE client process - must not run as interfaces are disabled
        for interface in self._interfaces:
            running = False
            for proc in process_iter():
                if interface in proc.cmdline():
                    running = True
                    break
            self.assertFalse(running)

        # enable PPPoE interfaces
        for interface in self._interfaces:
            self.cli_delete(base_path + [interface, 'disable'])

        self.cli_commit()

    def test_pppoe_authentication(self):
        # When username or password is set - so must be the other
        for interface in self._interfaces:
            (user, passwd) = self.u_p_dict[interface]

            self.cli_set(base_path + [interface, 'source-interface', self._source_interface])
            self.cli_set(base_path + [interface, 'ipv6', 'address', 'autoconf'])
            self.cli_set(base_path + [interface, 'authentication', 'username', user])

            # check validate() - if user is set, so must be the password
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()

            self.cli_set(base_path + [interface, 'authentication', 'password', passwd])

        self.cli_commit()

        for interface in self._interfaces:
            self.assertTrue(wait_for_interface(interface),
                            msg=f'Interface {interface} not found after {connect_timeout} seconds!')

            # Validate and verify assigned IP addresses
            self._verify_interface_address(interface)

    def test_pppoe_dhcpv6pd(self):
        # Check if PPPoE dialer can be configured with DHCPv6-PD
        address = 1
        sla_id = 0xff

        for interface in self._interfaces:
            (user, passwd) = self.u_p_dict[interface]
            interface_id = ''.join(c for c in interface if c.isdigit())

            self.cli_set(base_path + [interface, 'authentication', 'username', user])
            self.cli_set(base_path + [interface, 'authentication', 'password', passwd])
            self.cli_set(base_path + [interface, 'no-default-route'])
            self.cli_set(base_path + [interface, 'no-peer-dns'])
            self.cli_set(base_path + [interface, 'source-interface', self._source_interface])
            self.cli_set(base_path + [interface, 'ipv6', 'address', 'autoconf'])

            # interface we will delegate to
            delegate_if = f'dum{interface_id}'
            self.cli_set(['interfaces', 'dummy', delegate_if])

            # prefix delegation stuff
            dhcpv6_pd_base = base_path + [interface, 'dhcpv6-options', 'pd', '0']
            self.cli_set(dhcpv6_pd_base + ['length', '56'])
            self.cli_set(dhcpv6_pd_base + ['interface', delegate_if, 'address'], value=str(address))
            self.cli_set(dhcpv6_pd_base + ['interface', delegate_if, 'sla-id'], value=str(sla_id))

        # commit changes
        self.cli_commit()

        for interface in self._interfaces:
            self.assertTrue(wait_for_interface(interface),
                            msg=f'Interface {interface} not found after {connect_timeout} seconds!')

            (user, passwd) = self.u_p_dict[interface]
            mtu_default = default_value(base_path + [interface, 'mtu'])

            tmp = get_config_value(interface, 'mtu')[1]
            self.assertEqual(tmp, mtu_default)
            tmp = get_config_value(interface, 'user')[1].replace('"', '')
            self.assertEqual(tmp, user)
            tmp = get_config_value(interface, 'password')[1].replace('"', '')
            self.assertEqual(tmp, passwd)
            tmp = get_config_value(interface, '+ipv6 ipv6cp-use-ipaddr')
            self.assertListEqual(tmp, ['+ipv6', 'ipv6cp-use-ipaddr'])

            # Validate and verify assigned IP addresses
            self._verify_interface_address(interface)

            # interface we delegated to
            delegate_if = f'dum{interface_id}'
            tmp = get_interface_address(delegate_if)
            self.assertIn('addr_info', tmp)

            # Verify IPv6 address received from out DHCPv6-PD
            for addr_info in tmp['addr_info']:
                if 'family' not in addr_info or addr_info['family'] != 'inet6':
                    continue

                # Skip link-local interface address
                ipv6 = IPv6Address(addr_info['local'])
                if ipv6.is_link_local:
                    continue

                # DHCPv6-PD assigned interface addres is of length /64
                self.assertEqual(addr_info['prefixlen'], 64)
                # Interface IP address must be within the PD pool
                self.assertIn(ipv6, IPv6Network(ipv6_pool_pd))
                # Get corresponding PD assigned prefix for this site/connection
                pd_prefix = IPv6Network(f"{ipv6}/56", strict=False)
                # Prefix must be within the PD pool
                self.assertTrue(pd_prefix.subnet_of(IPv6Network(ipv6_pool_pd)))

                gen_addr = calculate_ipv6_interface_address(pd_prefix, sla_id, address)
                self.assertEqual(gen_addr, ipv6)

            self.cli_delete(['interfaces', 'dummy', delegate_if])

    def test_pppoe_options(self):
        # Verify access-concentrator and service-name CLI options

        ac_name: str = 'ACN123'
        service_name: str = 'VyOS'

        self.cli_set(pppoe_server_path + ['access-concentrator', ac_name])
        self.cli_set(pppoe_server_path + ['service-name', service_name])
        self.cli_commit()

        # as this tests uniqueness - we only use one interface in this test
        interface = self._interfaces[0]
        (user, passwd) = self.u_p_dict[interface]

        host_uniq = 'cafe010203'

        self.cli_set(base_path + [interface, 'authentication', 'username', user])
        self.cli_set(base_path + [interface, 'authentication', 'password', passwd])
        self.cli_set(base_path + [interface, 'source-interface', self._source_interface])

        self.cli_set(base_path + [interface, 'access-concentrator', ac_name])
        self.cli_set(base_path + [interface, 'service-name', service_name])
        self.cli_set(base_path + [interface, 'host-uniq', host_uniq])

        # commit changes
        self.cli_commit()

        self.assertTrue(wait_for_interface(interface),
                        msg=f'Interface {interface} not found after {connect_timeout} seconds!')

        tmp = get_config_value(interface, 'pppoe-ac')[1]
        self.assertEqual(tmp, f'"{ac_name}"')
        tmp = get_config_value(interface, 'pppoe-service')[1]
        self.assertEqual(tmp, f'"{service_name}"')
        tmp = get_config_value(interface, 'pppoe-host-uniq')[1]
        self.assertEqual(tmp, f'"{host_uniq}"')

        # Validate and verify assigned IP addresses
        self._verify_interface_address(interface)

        self.cli_delete(pppoe_server_path + ['access-concentrator'])
        self.cli_delete(pppoe_server_path + ['service-name'])

    def test_pppoe_mtu_mru(self):
        # Check if PPPoE dialer can be configured and runs
        for interface in self._interfaces:
            (user, passwd) = self.u_p_dict[interface]
            mtu = '1400'
            mru = '1300'

            self.cli_set(base_path + [interface, 'authentication', 'username', user])
            self.cli_set(base_path + [interface, 'authentication', 'password', passwd])
            self.cli_set(base_path + [interface, 'mtu', mtu])
            self.cli_set(base_path + [interface, 'mru', '9000'])

            # check validate() - a source-interface is required
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
            self.cli_set(base_path + [interface, 'source-interface', self._source_interface])

            # check validate() - MRU needs to be less or equal then MTU
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
            self.cli_set(base_path + [interface, 'mru', mru])

        # commit changes
        self.cli_commit()

        # verify configuration file(s)
        for interface in self._interfaces:
            self.assertTrue(wait_for_interface(interface),
                            msg=f'Interface {interface} not found after {connect_timeout} seconds!')

            (user, passwd) = self.u_p_dict[interface]

            tmp = get_config_value(interface, 'mtu')[1]
            self.assertEqual(tmp, mtu)
            tmp = get_config_value(interface, 'mru')[1]
            self.assertEqual(tmp, mru)
            tmp = get_config_value(interface, 'user')[1].replace('"', '')
            self.assertEqual(tmp, user)
            tmp = get_config_value(interface, 'password')[1].replace('"', '')
            self.assertEqual(tmp, passwd)
            tmp = get_config_value(interface, 'ifname')[1]
            self.assertEqual(tmp, interface)

            # Validate and verify assigned IP addresses
            self._verify_interface_address(interface)

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
