#!/usr/bin/env python3
#
# Copyright (C) 2019-2024 VyOS maintainers and contributors
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
from vyos.utils.process import cmd
from vyos.utils.process import process_named_running

PROCESS_NAME = 'chronyd'
NTP_CONF = '/run/chrony/chrony.conf'
base_path = ['service', 'ntp']

class TestSystemNTP(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestSystemNTP, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        self.assertTrue(process_named_running(PROCESS_NAME))

        self.cli_delete(base_path)
        self.cli_commit()

        self.assertFalse(process_named_running(PROCESS_NAME))

    def test_base_options(self):
        # Test basic NTP support with multiple servers and their options
        servers = ['192.0.2.1', '192.0.2.2']
        options = ['nts', 'noselect', 'prefer']
        pools = ['pool.vyos.io']

        for server in servers:
            for option in options:
                self.cli_set(base_path + ['server', server, option])

        # Test NTP pool
        for pool in pools:
            self.cli_set(base_path + ['server', pool, 'pool'])

        # commit changes
        self.cli_commit()

        # Check generated configuration
        # this file must be read with higher permissions
        config = cmd(f'sudo cat {NTP_CONF}')
        self.assertIn('driftfile /run/chrony/drift', config)
        self.assertIn('dumpdir /run/chrony', config)
        self.assertIn('ntsdumpdir /run/chrony', config)
        self.assertIn('clientloglimit 1048576', config)
        self.assertIn('rtcsync', config)
        self.assertIn('makestep 1.0 3', config)
        self.assertIn('leapsectz right/UTC', config)

        for server in servers:
            self.assertIn(f'server {server} iburst ' + ' '.join(options), config)

        for pool in pools:
            self.assertIn(f'pool {pool} iburst', config)

    def test_clients(self):
        # Test the allowed-networks statement
        listen_address = ['127.0.0.1', '::1']
        for listen in listen_address:
            self.cli_set(base_path + ['listen-address', listen])

        networks = ['192.0.2.0/24', '2001:db8:1000::/64', '100.64.0.0', '2001:db8::ffff']
        for network in networks:
            self.cli_set(base_path + ['allow-client', 'address', network])

        # Verify "NTP server not configured" verify() statement
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        servers = ['192.0.2.1', '192.0.2.2']
        for server in servers:
            self.cli_set(base_path + ['server', server])

        self.cli_commit()

        # Check generated client address configuration
        # this file must be read with higher permissions
        config = cmd(f'sudo cat {NTP_CONF}')
        for network in networks:
            self.assertIn(f'allow {network}', config)

        # Check listen address
        for listen in listen_address:
            self.assertIn(f'bindaddress {listen}', config)

    def test_interface(self):
        interfaces = ['eth0']
        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface])

        servers = ['time1.vyos.net', 'time2.vyos.net']
        for server in servers:
            self.cli_set(base_path + ['server', server])

        self.cli_commit()

        # Check generated client address configuration
        # this file must be read with higher permissions
        config = cmd(f'sudo cat {NTP_CONF}')
        for interface in interfaces:
            self.assertIn(f'binddevice {interface}', config)

    def test_vrf(self):
        vrf_name = 'vyos-mgmt'

        self.cli_set(['vrf', 'name', vrf_name, 'table', '12345'])
        self.cli_set(base_path + ['vrf', vrf_name])

        servers = ['time1.vyos.net', 'time2.vyos.net']
        for server in servers:
            self.cli_set(base_path + ['server', server])

        self.cli_commit()

        # Check for process in VRF
        tmp = cmd(f'ip vrf pids {vrf_name}')
        self.assertIn(PROCESS_NAME, tmp)

        self.cli_delete(['vrf', 'name', vrf_name])

    def test_leap_seconds(self):
        servers = ['time1.vyos.net', 'time2.vyos.net']
        for server in servers:
            self.cli_set(base_path + ['server', server])

        self.cli_commit()

        # Check generated client address configuration
        # this file must be read with higher permissions
        config = cmd(f'sudo cat {NTP_CONF}')
        self.assertIn('leapsectz right/UTC', config) # CLI default

        for mode in ['ignore', 'system', 'smear']:
            self.cli_set(base_path + ['leap-second', mode])
            self.cli_commit()
            config = cmd(f'sudo cat {NTP_CONF}')
            if mode != 'smear':
                self.assertIn(f'leapsecmode {mode}', config)
            else:
                self.assertIn(f'leapsecmode slew', config)
                self.assertIn(f'maxslewrate 1000', config)
                self.assertIn(f'smoothtime 400 0.001024 leaponly', config)

if __name__ == '__main__':
    unittest.main(verbosity=2)
