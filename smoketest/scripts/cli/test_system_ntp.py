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

import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.template import address_from_cidr
from vyos.template import netmask_from_cidr
from vyos.util import read_file
from vyos.util import process_named_running

PROCESS_NAME = 'ntpd'
NTP_CONF = '/run/ntpd/ntpd.conf'
base_path = ['system', 'ntp']

class TestSystemNTP(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestSystemNTP, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

        self.assertFalse(process_named_running(PROCESS_NAME))

    def test_01_ntp_options(self):
        # Test basic NTP support with multiple servers and their options
        servers = ['192.0.2.1', '192.0.2.2']
        options = ['noselect', 'preempt', 'prefer']
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
        config = read_file(NTP_CONF)
        self.assertIn('driftfile /var/lib/ntp/ntp.drift', config)
        self.assertIn('restrict default noquery nopeer notrap nomodify', config)
        self.assertIn('restrict source nomodify notrap noquery', config)
        self.assertIn('restrict 127.0.0.1', config)
        self.assertIn('restrict -6 ::1', config)

        for server in servers:
            self.assertIn(f'server {server} iburst ' + ' '.join(options), config)

        for pool in pools:
            self.assertIn(f'pool {pool} iburst', config)

    def test_02_ntp_clients(self):
        # Test the allowed-networks statement
        listen_address = ['127.0.0.1', '::1']
        for listen in listen_address:
            self.cli_set(base_path + ['listen-address', listen])

        networks = ['192.0.2.0/24', '2001:db8:1000::/64']
        for network in networks:
            self.cli_set(base_path + ['allow-clients', 'address', network])

        # Verify "NTP server not configured" verify() statement
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        servers = ['192.0.2.1', '192.0.2.2']
        for server in servers:
            self.cli_set(base_path + ['server', server])

        self.cli_commit()

        # Check generated client address configuration
        config = read_file(NTP_CONF)
        self.assertIn('restrict default ignore', config)

        for network in networks:
            network_address = address_from_cidr(network)
            network_netmask = netmask_from_cidr(network)
            self.assertIn(f'restrict {network_address} mask {network_netmask} nomodify notrap nopeer', config)

        # Check listen address
        self.assertIn('interface ignore wildcard', config)
        for listen in listen_address:
            self.assertIn(f'interface listen {listen}', config)

    def test_03_ntp_interface(self):
        interfaces = ['eth0', 'eth1']
        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface])

        servers = ['time1.vyos.net', 'time2.vyos.net']
        for server in servers:
            self.cli_set(base_path + ['server', server])

        self.cli_commit()

        # Check generated client address configuration
        config = read_file(NTP_CONF)
        self.assertIn('interface ignore wildcard', config)
        for interface in interfaces:
            self.assertIn(f'interface listen {interface}', config)

if __name__ == '__main__':
    unittest.main(verbosity=2)
