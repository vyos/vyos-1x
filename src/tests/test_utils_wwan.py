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

from unittest import TestCase

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
