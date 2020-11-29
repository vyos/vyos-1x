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
import os
import unittest

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.template import address_from_cidr
from vyos.template import netmask_from_cidr
from vyos.util import read_file
from vyos.util import process_named_running

PROCESS_NAME = 'ntpd'
NTP_CONF = '/etc/ntp.conf'
base_path = ['system', 'ntp']

def get_config_value(key):
    tmp = read_file(NTP_CONF)
    tmp = re.findall(r'\n?{}\s+(.*)'.format(key), tmp)
    # remove possible trailing whitespaces
    return [item.strip() for item in tmp]

class TestSystemNTP(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        self.session.delete(base_path)

    def tearDown(self):
        self.session.delete(base_path)
        self.session.commit()
        del self.session

    def test_ntp_options(self):
        """ Test basic NTP support with multiple servers and their options """
        servers = ['192.0.2.1', '192.0.2.2']
        options = ['noselect', 'preempt', 'prefer']
        ntp_pool = 'pool.vyos.io'

        for server in servers:
            for option in options:
                self.session.set(base_path + ['server', server, option])

        # Test NTP pool
        self.session.set(base_path + ['server', ntp_pool, 'pool'])

        # commit changes
        self.session.commit()

        # Check generated configuration
        tmp = get_config_value('server')
        for server in servers:
            test = f'{server} iburst ' + ' '.join(options)
            self.assertTrue(test in tmp)

        tmp = get_config_value('pool')
        self.assertTrue(f'{ntp_pool} iburst' in tmp)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_ntp_clients(self):
        """ Test the allowed-networks statement """
        networks = ['192.0.2.0/24', '2001:db8:1000::/64']
        for network in networks:
            self.session.set(base_path + ['allow-clients', 'address', network])

        # Verify "NTP server not configured" verify() statement
        with self.assertRaises(ConfigSessionError):
            self.session.commit()

        servers = ['192.0.2.1', '192.0.2.2']
        for server in servers:
            self.session.set(base_path + ['server', server])

        self.session.commit()

        # Check generated client address configuration
        for network in networks:
            network_address = address_from_cidr(network)
            network_netmask = netmask_from_cidr(network)

            tmp = get_config_value(f'restrict {network_address}')[0]
            test = f'mask {network_netmask} nomodify notrap nopeer'
            self.assertTrue(tmp in test)

        # Check listen address
        tmp = get_config_value('interface')
        test = ['ignore wildcard', 'listen 127.0.0.1', 'listen ::1']
        self.assertEqual(tmp, test)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

if __name__ == '__main__':
    unittest.main()
