#!/usr/bin/env python3
#
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

import re
import unittest

from vyos.configsession import ConfigSessionError
from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.utils.file import read_file
from vyos.utils.process import process_named_running

PROCESS_NAME = 'radvd'
RADVD_CONF = '/run/radvd/radvd.conf'

interface = 'eth1'
base_path = ['service', 'router-advert', 'interface', interface]
address_base = ['interfaces', 'ethernet', interface, 'address']
prefix = '::/64'

def get_config_value(key):
    tmp = read_file(RADVD_CONF)
    tmp = re.findall(r'\n?{}\s+(.*)'.format(key), tmp)
    return tmp[0].split()[0].replace(';','')

class TestServiceRADVD(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestServiceRADVD, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, ['service', 'router-advert'])

        cls.cli_set(cls, address_base + ['2001:db8::1/64'])

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, address_base)
        super(TestServiceRADVD, cls).tearDownClass()

    def tearDown(self):
        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

        self.cli_delete(base_path)
        self.cli_commit()

        # Check for no longer running process
        self.assertFalse(process_named_running(PROCESS_NAME))

    def test_common(self):
        self.cli_set(base_path + ['prefix', prefix, 'no-on-link-flag'])
        self.cli_set(base_path + ['prefix', prefix, 'no-autonomous-flag'])
        self.cli_set(base_path + ['prefix', prefix, 'valid-lifetime', 'infinity'])
        self.cli_set(base_path + ['other-config-flag'])

        # commit changes
        self.cli_commit()

        # verify values
        tmp = get_config_value('interface')
        self.assertEqual(tmp, interface)

        tmp = get_config_value('prefix')
        self.assertEqual(tmp, prefix)

        tmp = get_config_value('AdvOtherConfigFlag')
        self.assertEqual(tmp, 'on')

        # this is a default value
        tmp = get_config_value('AdvRetransTimer')
        self.assertEqual(tmp, '0')

        # this is a default value
        tmp = get_config_value('AdvCurHopLimit')
        self.assertEqual(tmp, '64')

        # this is a default value
        tmp = get_config_value('AdvDefaultPreference')
        self.assertEqual(tmp, 'medium')

        tmp = get_config_value('AdvAutonomous')
        self.assertEqual(tmp, 'off')

        # this is a default value
        tmp = get_config_value('AdvValidLifetime')
        self.assertEqual(tmp, 'infinity')

        # this is a default value
        tmp = get_config_value('AdvPreferredLifetime')
        self.assertEqual(tmp, '14400')

        tmp = get_config_value('AdvOnLink')
        self.assertEqual(tmp, 'off')

        tmp = get_config_value('DeprecatePrefix')
        self.assertEqual(tmp, 'off')

        tmp = get_config_value('DecrementLifetimes')
        self.assertEqual(tmp, 'off')

    def test_dns(self):
        nameserver = ['2001:db8::1', '2001:db8::2']
        dnssl = ['vyos.net', 'vyos.io']
        ns_lifetime = '599'

        self.cli_set(base_path + ['prefix', prefix, 'valid-lifetime', 'infinity'])
        self.cli_set(base_path + ['other-config-flag'])

        for ns in nameserver:
            self.cli_set(base_path + ['name-server', ns])
        for sl in dnssl:
            self.cli_set(base_path + ['dnssl', sl])

        self.cli_set(base_path + ['name-server-lifetime', ns_lifetime])
        # The value, if not 0, must be at least interval max (defaults to 600).
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        ns_lifetime = '600'
        self.cli_set(base_path + ['name-server-lifetime', ns_lifetime])

        # commit changes
        self.cli_commit()

        config = read_file(RADVD_CONF)

        tmp = 'RDNSS ' + ' '.join(nameserver) + ' {'
        self.assertIn(tmp, config)

        tmp = f'AdvRDNSSLifetime {ns_lifetime};'
        self.assertIn(tmp, config)

        tmp = 'DNSSL ' + ' '.join(dnssl) + ' {'
        self.assertIn(tmp, config)

    def test_deprecate_prefix(self):
        self.cli_set(base_path + ['prefix', prefix, 'valid-lifetime', 'infinity'])
        self.cli_set(base_path + ['prefix', prefix, 'deprecate-prefix'])
        self.cli_set(base_path + ['prefix', prefix, 'decrement-lifetime'])

        # commit changes
        self.cli_commit()

        tmp = get_config_value('DeprecatePrefix')
        self.assertEqual(tmp, 'on')

        tmp = get_config_value('DecrementLifetimes')
        self.assertEqual(tmp, 'on')

    def test_route(self):
        route = '2001:db8:1000::/64'

        self.cli_set(base_path + ['prefix', prefix])
        self.cli_set(base_path + ['route', route])

        # commit changes
        self.cli_commit()

        config = read_file(RADVD_CONF)

        tmp = f'route {route}' + ' {'
        self.assertIn(tmp, config)

        self.assertIn('AdvRouteLifetime 1800;', config)
        self.assertIn('AdvRoutePreference medium;', config)
        self.assertIn('RemoveRoute on;', config)

    def test_rasrcaddress(self):
        ra_src = ['fe80::1', 'fe80::2']

        self.cli_set(base_path + ['prefix', prefix])
        for src in ra_src:
            self.cli_set(base_path + ['source-address', src])

        # commit changes
        self.cli_commit()

        config = read_file(RADVD_CONF)
        self.assertIn('AdvRASrcAddress {', config)
        for src in ra_src:
            self.assertIn(f'        {src};', config)

    def test_nat64prefix(self):
        nat64prefix = '64:ff9b::/96'
        nat64prefix_invalid = '64:ff9b::/44'

        self.cli_set(base_path + ['nat64prefix', nat64prefix])

        # and another invalid prefix
        # Invalid NAT64 prefix length for "2001:db8::/34", can only be one of:
        # /32, /40, /48, /56, /64, /96
        self.cli_set(base_path + ['nat64prefix', nat64prefix_invalid])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(base_path + ['nat64prefix', nat64prefix_invalid])

        # NAT64 valid-lifetime must not be smaller then "interval max"
        self.cli_set(base_path + ['nat64prefix', nat64prefix, 'valid-lifetime', '500'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(base_path + ['nat64prefix', nat64prefix, 'valid-lifetime'])

        # commit changes
        self.cli_commit()

        config = read_file(RADVD_CONF)

        tmp = f'nat64prefix {nat64prefix}' + ' {'
        self.assertIn(tmp, config)
        self.assertIn('AdvValidLifetime 65528;', config) # default

    def test_advsendadvert_advintervalopt(self):
        ra_src = ['fe80::1', 'fe80::2']

        self.cli_set(base_path + ['prefix', prefix])
        self.cli_set(base_path + ['no-send-advert'])
        # commit changes
        self.cli_commit()

        # Verify generated configuration
        config = read_file(RADVD_CONF)
        tmp = get_config_value('AdvSendAdvert')
        self.assertEqual(tmp, 'off')

        tmp = get_config_value('AdvIntervalOpt')
        self.assertEqual(tmp, 'on')

        self.cli_set(base_path + ['no-send-interval'])
        # commit changes
        self.cli_commit()

        # Verify generated configuration
        config = read_file(RADVD_CONF)
        tmp = get_config_value('AdvSendAdvert')
        self.assertEqual(tmp, 'off')

        tmp = get_config_value('AdvIntervalOpt')
        self.assertEqual(tmp, 'off')


if __name__ == '__main__':
    unittest.main(verbosity=2)
