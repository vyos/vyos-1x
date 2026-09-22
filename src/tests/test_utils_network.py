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

import vyos.utils.network
from unittest import TestCase
from unittest.mock import patch

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

    def test_is_loopback_addr(self):
        self.assertTrue(vyos.utils.network.is_loopback_addr('127.0.0.1'))
        self.assertTrue(vyos.utils.network.is_loopback_addr('127.0.1.1'))
        self.assertTrue(vyos.utils.network.is_loopback_addr('127.1.1.1'))
        self.assertTrue(vyos.utils.network.is_loopback_addr('::1'))

        self.assertFalse(vyos.utils.network.is_loopback_addr('::2'))
        self.assertFalse(vyos.utils.network.is_loopback_addr('192.0.2.1'))

    def test_are_same_ip(self):
        self.assertTrue(vyos.utils.network._are_same_ip('192.0.2.1', '192.0.2.1'))
        self.assertFalse(vyos.utils.network._are_same_ip('192.0.2.1', '192.0.2.2'))
        self.assertTrue(vyos.utils.network._are_same_ip('::1', '::1'))
        self.assertFalse(vyos.utils.network._are_same_ip('::1', '::2'))
        # mixed address families must never compare equal, and must not raise
        self.assertFalse(vyos.utils.network._are_same_ip('192.0.2.1', '::1'))
        self.assertFalse(vyos.utils.network._are_same_ip('::1', '192.0.2.1'))

    def test_check_port_availability(self):
        self.assertTrue(vyos.utils.network.check_port_availability('::1', 8080))
        self.assertTrue(vyos.utils.network.check_port_availability('127.0.0.1', 8080))
        self.assertTrue(vyos.utils.network.check_port_availability(None, 8080, protocol='udp'))
        # We do not have 192.0.2.1 configured on this system
        self.assertFalse(vyos.utils.network.check_port_availability('192.0.2.1', 443))
        # We do not have 2001:db8::1 configured on this system
        self.assertFalse(vyos.utils.network.check_port_availability('2001:db8::1', 80, protocol='udp'))

# T7487: the kernel-assigned WWAN interface number and ModemManager's own
# modem index are independently enumerated and are not guaranteed to
# match. This mocked mmcli fixture puts them in reversed order - modem
# index 0 actually owns wwan1/cdc-wdm7, modem index 1 actually owns
# wwan0/cdc-wdm2 - the opposite of what naively stripping the 'wwan'
# prefix off the interface name (the pre-T7487 behaviour) would assume,
# and with QMI device numbers that don't coincidentally match either the
# modem index or the interface number, so a test that only checked the
# modem index couldn't accidentally pass by luck on the port number too.
def _mock_mmcli(command, *args, **kwargs):
    modem_ports = {
        '0': ['cdc-wdm7 (qmi)', 'ttyUSB3 (at)', 'wwan1 (net)'],
        '1': ['cdc-wdm2 (qmi)', 'ttyUSB0 (at)', 'wwan0 (net)'],
    }
    if command == ['mmcli', '-L', '--output-json']:
        return json.dumps(
            {
                'modem-list': [
                    '/org/freedesktop/ModemManager1/Modem/0',
                    '/org/freedesktop/ModemManager1/Modem/1',
                ]
            }
        )
    if (
        len(command) == 4
        and command[0] == 'mmcli'
        and command[1] == '--modem'
        and command[3] == '--output-json'
    ):
        return json.dumps({'modem': {'generic': {'ports': modem_ports[command[2]]}}})
    raise AssertionError(f'unexpected command passed to cmdl(): {command}')


class TestVyOSUtilsNetworkWWAN(TestCase):
    @patch('vyos.utils.network.cmdl', side_effect=_mock_mmcli)
    def test_get_wwan_modem_ports_resolves_by_ownership(self, mock_cmdl):
        idx, ports = vyos.utils.network.get_wwan_modem_ports('wwan0')
        self.assertEqual(idx, '1')
        self.assertIn('cdc-wdm2 (qmi)', ports)

        idx, ports = vyos.utils.network.get_wwan_modem_ports('wwan1')
        self.assertEqual(idx, '0')
        self.assertIn('cdc-wdm7 (qmi)', ports)

        self.assertEqual(vyos.utils.network.get_wwan_modem('wwan0'), '1')
        self.assertEqual(vyos.utils.network.get_wwan_modem('wwan1'), '0')

    @patch('vyos.utils.network.cmdl', side_effect=_mock_mmcli)
    def test_get_wwan_modem_ports_selects_owning_qmi_port(self, mock_cmdl):
        # Mirrors src/op_mode/show_wwan.py's own QMI control port
        # selection (get_wwan_modem_ports() + picking the '(qmi)' entry).
        # The real T7487 regression here was this resolving to the wrong
        # modem's cdc-wdmN control port, not just the wrong modem index.
        _, ports = vyos.utils.network.get_wwan_modem_ports('wwan0')
        qmi_port = next((p.split(' ')[0] for p in ports if p.endswith('(qmi)')), None)
        self.assertEqual(qmi_port, 'cdc-wdm2')

        _, ports = vyos.utils.network.get_wwan_modem_ports('wwan1')
        qmi_port = next((p.split(' ')[0] for p in ports if p.endswith('(qmi)')), None)
        self.assertEqual(qmi_port, 'cdc-wdm7')

    @patch('vyos.utils.network.cmdl', side_effect=_mock_mmcli)
    def test_get_wwan_modem_ports_unknown_interface(self, mock_cmdl):
        idx, ports = vyos.utils.network.get_wwan_modem_ports('wwan9')
        self.assertIsNone(idx)
        self.assertEqual(ports, [])
        self.assertIsNone(vyos.utils.network.get_wwan_modem('wwan9'))
