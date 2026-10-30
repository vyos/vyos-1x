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

import os
import stat
import tempfile
from unittest import TestCase
from unittest.mock import patch

from vyos.utils import wwan
from vyos.utils.wwan import connect_options

autoconf = {'address': {'autoconf': {}}}


class TestUtilsWWAN(TestCase):
    def test_connect_options_ip_type(self):
        cases = [
            ('ipv4', {'address': ['dhcp']}),
            ('ipv4v6', {'address': ['dhcp', 'dhcpv6']}),
            ('ipv4v6', {'address': ['dhcp'], 'ipv6': autoconf}),
            ('ipv6', {'address': ['dhcpv6']}),
            ('ipv6', {'address': ['dhcpv6'], 'ipv6': autoconf}),
            # SLAAC is the only way of getting an address, thus the interface
            # has no "address" node at all
            ('ipv6', {'ipv6': autoconf}),
            # nothing to get an address for, the type is left at the default
            ('ipv4', {}),
        ]
        for ip_type, config in cases:
            with self.subTest(config=config):
                options = connect_options({'apn': 'internet', **config})
                self.assertEqual(options, f'ip-type={ip_type},apn=internet')

    def test_connect_options_authentication(self):
        config = {
            'apn': 'internet',
            'address': ['dhcp'],
            'authentication': {'username': 'user', 'password': 'secret'},
        }
        self.assertEqual(
            connect_options(config),
            'ip-type=ipv4,apn=internet,user=user,password=secret',
        )


class TestUtilsWWANBearerState(TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = patch.object(wwan, 'bearer_state_dir', tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_nothing_recorded(self):
        self.assertIsNone(wwan.get_bearer_router('wwan0', 'ipv4'))
        self.assertIsNone(wwan.get_bearer_address('wwan0', 'ipv6'))

    def test_round_trip_per_interface_and_family(self):
        wwan.set_bearer_router('wwan0', 'ipv4', '192.0.2.1')
        wwan.set_bearer_router('wwan0', 'ipv6', '2001:db8::1')
        wwan.set_bearer_address('wwan0', 'ipv4', '192.0.2.2/30')
        wwan.set_bearer_router('wwan1', 'ipv4', '198.51.100.1')

        self.assertEqual(wwan.get_bearer_router('wwan0', 'ipv4'), '192.0.2.1')
        self.assertEqual(wwan.get_bearer_router('wwan0', 'ipv6'), '2001:db8::1')
        self.assertEqual(wwan.get_bearer_address('wwan0', 'ipv4'), '192.0.2.2/30')
        self.assertEqual(wwan.get_bearer_router('wwan1', 'ipv4'), '198.51.100.1')
        # the router and the address of a family are kept apart
        self.assertIsNone(wwan.get_bearer_address('wwan0', 'ipv6'))

    def test_empty_value_forgets(self):
        wwan.set_bearer_router('wwan0', 'ipv4', '192.0.2.1')
        wwan.set_bearer_router('wwan0', 'ipv4', None)
        self.assertIsNone(wwan.get_bearer_router('wwan0', 'ipv4'))
        # forgetting something that was never recorded is not an error
        wwan.set_bearer_address('wwan0', 'ipv6', None)

    def test_write_is_atomic(self):
        wwan.set_bearer_router('wwan0', 'ipv4', '192.0.2.1')
        # a failure while replacing leaves the old value in place and no
        # temporary file behind
        with patch.object(wwan.os, 'replace', side_effect=OSError):
            with self.assertRaises(OSError):
                wwan.set_bearer_router('wwan0', 'ipv4', '198.51.100.1')
        self.assertEqual(wwan.get_bearer_router('wwan0', 'ipv4'), '192.0.2.1')
        self.assertEqual(os.listdir(wwan.bearer_state_dir), ['wwan0.ipv4-router'])

    def test_state_file_is_readable_by_others(self):
        wwan.set_bearer_address('wwan0', 'ipv4', '192.0.2.2/30')
        path = os.path.join(wwan.bearer_state_dir, 'wwan0.ipv4-address')
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o644)

