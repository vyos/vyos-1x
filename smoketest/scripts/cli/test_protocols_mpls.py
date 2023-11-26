#!/usr/bin/env python3
#
# Copyright (C) 2021-2023 VyOS maintainers and contributors
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

from base_vyostest_shim import VyOSUnitTestSHIM
from vyos.configsession import ConfigSessionError
from vyos.ifconfig import Section
from vyos.utils.process import process_named_running

PROCESS_NAME = 'ldpd'
base_path = ['protocols', 'mpls', 'ldp']

peers = {
    '192.0.2.10' : {
        'intv_rx'    : '500',
        'intv_tx'    : '600',
        'multihop'   : '',
        'source_addr': '192.0.2.254',
        },
    '192.0.2.20' : {
        'echo_mode'  : '',
        'intv_echo'  : '100',
        'intv_mult'  : '100',
        'intv_rx'    : '222',
        'intv_tx'    : '333',
        'passive'    : '',
        'shutdown'   : '',
        },
    '2001:db8::a' : {
        'source_addr': '2001:db8::1',
        },
    '2001:db8::b' : {
        'source_addr': '2001:db8::1',
        'multihop'   : '',
        },
}

profiles = {
    'foo' : {
        'echo_mode'  : '',
        'intv_echo'  : '100',
        'intv_mult'  : '101',
        'intv_rx'    : '222',
        'intv_tx'    : '333',
        'shutdown'   : '',
        },
    'bar' : {
        'intv_mult'  : '102',
        'intv_rx'    : '444',
        'passive'    : '',
        },
}

class TestProtocolsMPLS(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestProtocolsMPLS, cls).setUpClass()

        # Retrieve FRR daemon PID - it is not allowed to crash, thus PID must remain the same
        cls.daemon_pid = process_named_running(PROCESS_NAME)

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

        # check process health and continuity
        self.assertEqual(self.daemon_pid, process_named_running(PROCESS_NAME))

    def test_mpls_basic(self):
        router_id = '1.2.3.4'
        transport_ipv4_addr = '5.6.7.8'
        interfaces = Section.interfaces('ethernet')

        self.cli_set(base_path + ['router-id', router_id])

        # At least one LDP interface must be configured
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface])

        # LDP transport address missing
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(base_path + ['discovery', 'transport-ipv4-address', transport_ipv4_addr])

        # Commit changes
        self.cli_commit()

        # Validate configuration
        frrconfig = self.getFRRconfig('mpls ldp', daemon=PROCESS_NAME)
        self.assertIn(f'mpls ldp', frrconfig)
        self.assertIn(f' router-id {router_id}', frrconfig)

        # Validate AFI IPv4
        afiv4_config = self.getFRRconfig(' address-family ipv4', daemon=PROCESS_NAME)
        self.assertIn(f'  discovery transport-address {transport_ipv4_addr}', afiv4_config)
        for interface in interfaces:
            self.assertIn(f'  interface {interface}', afiv4_config)

if __name__ == '__main__':
    unittest.main(verbosity=2)
