#!/usr/bin/env python3
#
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

import re
import unittest

from vyos.configsession import ConfigSessionError
from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.util import read_file
from vyos.util import process_named_running

RADVD_CONF = '/run/radvd/radvd.conf'

interface = 'eth1'
base_path = ['service', 'router-advert', 'interface', interface]
address_base = ['interfaces', 'ethernet', interface, 'address']

def get_config_value(key):
    tmp = read_file(RADVD_CONF)
    tmp = re.findall(r'\n?{}\s+(.*)'.format(key), tmp)
    return tmp[0].split()[0].replace(';','')

class TestServiceRADVD(VyOSUnitTestSHIM.TestCase):
    def setUp(self):
        self.cli_set(address_base + ['2001:db8::1/64'])

    def tearDown(self):
        self.cli_delete(address_base)
        self.cli_delete(base_path)
        self.cli_commit()

    def test_common(self):
        self.cli_set(base_path + ['prefix', '::/64', 'no-on-link-flag'])
        self.cli_set(base_path + ['prefix', '::/64', 'no-autonomous-flag'])
        self.cli_set(base_path + ['prefix', '::/64', 'valid-lifetime', 'infinity'])
        self.cli_set(base_path + ['other-config-flag'])

        # commit changes
        self.cli_commit()

        # verify values
        tmp = get_config_value('interface')
        self.assertEqual(tmp, interface)

        tmp = get_config_value('prefix')
        self.assertEqual(tmp, '::/64')

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

        # Check for running process
        self.assertTrue(process_named_running('radvd'))

    def test_dns(self):
        nameserver = ['2001:db8::1', '2001:db8::2']
        dnssl = ['vyos.net', 'vyos.io']
        ns_lifetime = '599'

        self.cli_set(base_path + ['prefix', '::/64', 'valid-lifetime', 'infinity'])
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
