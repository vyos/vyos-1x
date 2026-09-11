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

import json
import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.utils.process import cmdl

base_path = ['protocols', 'static', 'arp']
interface = 'eth0'
address = '192.0.2.1/24'

class TestARP(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestARP, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

        # we need a L2 interface with a L3 address to properly configure ARP entries
        cls.cli_set(cls, ['interfaces', 'ethernet', interface, 'address', address])

    @classmethod
    def tearDownClass(cls):
        # cleanuop L2 interface
        cls.cli_delete(cls, ['interfaces', 'ethernet', interface, 'address', address])
        cls.cli_commit(cls)

        super(TestARP, cls).tearDownClass()

    def tearDown(self):
        # delete test config
        self.cli_delete(base_path)
        self.cli_commit()
        # always forward to base class
        super().tearDown()

    def test_static_arp(self):
        test_data = {
            '192.0.2.10' : { 'mac' : '00:01:02:03:04:0a' },
            '192.0.2.11' : { 'mac' : '00:01:02:03:04:0b' },
            '192.0.2.12' : { 'mac' : '00:01:02:03:04:0c' },
            '192.0.2.13' : { 'mac' : '00:01:02:03:04:0d' },
            '192.0.2.14' : { 'mac' : '00:01:02:03:04:0e' },
            '192.0.2.15' : { 'mac' : '00:01:02:03:04:0f' },
        }

        for host, host_config in test_data.items():
            self.cli_set(base_path + ['interface', interface, 'address', host, 'mac', host_config['mac']])

        self.cli_commit()

        arp_table = json.loads(cmdl(['ip', '-j', '-4', 'neigh', 'show']))
        for host, host_config in test_data.items():
            # As we search within a list of hosts we need to mark if it was
            # found or not. This ensures all hosts from test_data are processed
            found = False
            for entry in arp_table:
                # Other ARP entry - not related to this testcase
                if entry['dst'] not in list(test_data):
                    continue

                if entry['dst'] == host:
                    self.assertEqual(entry['lladdr'], host_config['mac'])
                    self.assertEqual(entry['dev'], interface)
                    found = True

            if found == False:
                print(entry)
            self.assertTrue(found)

    def test_static_arp_deletion(self):
        # deleting the "protocols static arp" node must remove the
        # previously installed PERMANENT ARP entry from the kernel
        host = '192.0.2.10'
        mac = '00:01:02:03:04:0a'

        def get_static_arp_entry():
            # Return our static (PERMANENT) neighbour, matched by dst + dev.
            arp_table = json.loads(cmdl(['ip', '-j', '-4', 'neigh', 'show']))
            for entry in arp_table:
                if (
                    entry['dst'] == host
                    and entry['dev'] == interface
                    and 'PERMANENT' in entry.get('state', [])
                ):
                    return entry
            return None

        self.cli_set(base_path + ['interface', interface, 'address', host, 'mac', mac])
        self.cli_commit()

        # the static PERMANENT entry must be present with all configured fields
        entry = get_static_arp_entry()
        self.assertIsNotNone(entry)
        self.assertEqual(entry['dst'], host)
        self.assertEqual(entry['lladdr'], mac)
        self.assertEqual(entry['dev'], interface)

        # delete the whole node and verify the static entry is gone
        self.cli_delete(base_path)
        self.cli_commit()

        self.assertIsNone(get_static_arp_entry())

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
