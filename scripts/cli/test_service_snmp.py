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

import os
import re
import unittest

import vyos.config
import vyos.configsession
import vyos.util as util
from vyos.validate import is_ipv4

SNMPD_CONF = '/etc/snmp/snmpd.conf'

base_path = ['service', 'snmp']

def get_config_value(key):
    tmp = util.read_file(SNMPD_CONF)
    return re.findall(r'\n?{}\s+(.*)'.format(key), tmp)

class TestSystemNameServer(unittest.TestCase):
    def setUp(self):
        self.session = vyos.configsession.ConfigSession(os.getpid())
        env = self.session.get_session_env()
        self.config = vyos.config.Config(session_env=env)

    def tearDown(self):
        # Delete SNNP configuration
        self.session.delete(base_path)
        self.session.commit()

    def test_snmpv2(self):
        """ Check if SNMPv2 can be configured and service runs """
        clients = ['192.0.2.1', '2001:db8::1']
        networks = ['192.0.2.128/25', '2001:db8:babe::/48']
        listen = ['127.0.0.1', '::1']

        for auth in ['ro', 'rw']:
            community = 'VyOS' + auth
            self.session.set(base_path + ['community', community, 'authorization', auth])
            for client in clients:
                self.session.set(base_path + ['community', community, 'client', client])
            for network in networks:
                self.session.set(base_path + ['community', community, 'network', network])
            for addr in listen:
                self.session.set(base_path + ['listen-address', addr])

            self.session.set(base_path + ['contact', 'maintainers@vyos.io'])
            self.session.set(base_path + ['location', 'qemu'])

        self.session.commit()

        # verify listen address, it will be returned as
        # ['unix:/run/snmpd.socket,udp:127.0.0.1:161,udp6:[::1]:161']
        # thus we need to transfor this into a proper list
        config = get_config_value('agentaddress')[0]
        expected = 'unix:/run/snmpd.socket'
        for addr in listen:
            if is_ipv4(addr):
                expected += ',udp:{}:161'.format(addr)
            else:
                expected += ',udp6:[{}]:161'.format(addr)

        self.assertTrue(expected in config)

if __name__ == '__main__':
    unittest.main()

