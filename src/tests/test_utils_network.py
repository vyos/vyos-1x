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

import vyos.utils.network
from unittest import TestCase

class TestVyOSUtilsNetwork(TestCase):
    def setUp(self):
        pass

    def test_is_addr_assigned(self):
        self.assertTrue(vyos.utils.network.is_addr_assigned('127.0.0.1'))
        self.assertTrue(vyos.utils.network.is_addr_assigned('::1'))
        self.assertFalse(vyos.utils.network.is_addr_assigned('127.251.255.123'))

    def test_is_ipv6_link_local(self):
        self.assertFalse(vyos.utils.network.is_ipv6_link_local('169.254.0.1'))
        self.assertTrue(vyos.utils.network.is_ipv6_link_local('fe80::'))
        self.assertTrue(vyos.utils.network.is_ipv6_link_local('fe80::affe:1'))
        self.assertTrue(vyos.utils.network.is_ipv6_link_local('fe80::affe:1%eth0'))
        self.assertFalse(vyos.utils.network.is_ipv6_link_local('2001:db8::'))
        self.assertFalse(vyos.utils.network.is_ipv6_link_local('2001:db8::%eth0'))
        self.assertFalse(vyos.utils.network.is_ipv6_link_local('VyOS'))
        self.assertFalse(vyos.utils.network.is_ipv6_link_local('::1'))
        self.assertFalse(vyos.utils.network.is_ipv6_link_local('::1%lo'))

    def test_is_ipv6_link_local(self):
        self.assertTrue(vyos.utils.network.is_loopback_addr('127.0.0.1'))
        self.assertTrue(vyos.utils.network.is_loopback_addr('127.0.1.1'))
        self.assertTrue(vyos.utils.network.is_loopback_addr('127.1.1.1'))
        self.assertTrue(vyos.utils.network.is_loopback_addr('::1'))

        self.assertFalse(vyos.utils.network.is_loopback_addr('::2'))
        self.assertFalse(vyos.utils.network.is_loopback_addr('192.0.2.1'))

    def test_check_port_availability(self):
        self.assertTrue(vyos.utils.network.check_port_availability('::1', 8080))
        self.assertTrue(vyos.utils.network.check_port_availability('127.0.0.1', 8080))
        self.assertTrue(vyos.utils.network.check_port_availability(None, 8080, protocol='udp'))
        # We do not have 192.0.2.1 configured on this system
        self.assertFalse(vyos.utils.network.check_port_availability('192.0.2.1', 443))
        # We do not have 2001:db8::1 configured on this system
        self.assertFalse(vyos.utils.network.check_port_availability('2001:db8::1', 80, protocol='udp'))
