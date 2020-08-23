#!/usr/bin/env python3
#
# Copyright (C) 020 VyOS maintainers and contributors
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

from configparser import ConfigParser
from psutil import process_iter
from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError

base_path = ['service', 'pppoe-server']
local_if = ['interfaces', 'dummy', 'dum667']
pppoe_conf = '/run/accel-pppd/pppoe.conf'

ac_name = 'ACN'
subnet = '172.18.0.0/24'
gateway = '192.0.2.1'
nameserver = '9.9.9.9'
mtu = '1492'
interface = 'eth0'

class TestServicePPPoEServer(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        self.session.delete(base_path)

    def tearDown(self):
        self.session.delete(base_path)
        self.session.delete(local_if)
        self.session.commit()
        del self.session

    def verify(self, conf):
        # validate some common values in the configuration
        for tmp in ['log_syslog', 'pppoe', 'chap-secrets', 'ippool', 'ipv6pool',
                    'ipv6_nd', 'ipv6_dhcp', 'auth_mschap_v2', 'auth_mschap_v1',
                    'auth_chap_md5', 'auth_pap', 'shaper']:
            # Settings without values provide None
            self.assertEqual(conf['modules'][tmp], None)

        # check Access Concentrator setting
        self.assertTrue(conf['pppoe']['ac-name'] == ac_name)
        self.assertTrue(conf['pppoe'].getboolean('verbose'))
        self.assertTrue(conf['pppoe']['interface'], interface)

        # check configured subnet
        self.assertEqual(conf['ip-pool'][subnet], None)
        self.assertEqual(conf['ip-pool']['gw-ip-address'], gateway)

        # check ppp
        self.assertTrue(conf['ppp'].getboolean('verbose'))
        self.assertTrue(conf['ppp'].getboolean('check-ip'))
        self.assertFalse(conf['ppp'].getboolean('ccp'))
        self.assertEqual(conf['ppp']['min-mtu'], mtu)
        self.assertEqual(conf['ppp']['mtu'], mtu)
        self.assertEqual(conf['ppp']['mppe'], 'prefer')
        self.assertEqual(conf['ppp']['lcp-echo-interval'], '30')
        self.assertEqual(conf['ppp']['lcp-echo-timeout'], '0')
        self.assertEqual(conf['ppp']['lcp-echo-failure'], '3')

    def test_local_auth(self):
        """ Test configuration of local authentication for PPPoE server """
        self.session.set(local_if + ['address', '192.0.2.1/32'])
        self.session.set(base_path + ['access-concentrator', ac_name])
        self.session.set(base_path + ['authentication', 'local-users', 'username', 'vyos', 'password', 'vyos'])
        self.session.set(base_path + ['authentication', 'mode', 'local'])
        self.session.set(base_path + ['client-ip-pool', 'subnet', subnet])
        self.session.set(base_path + ['name-server', nameserver])
        self.session.set(base_path + ['interface', interface])
        self.session.set(base_path + ['local-ip', gateway])

        # commit changes
        self.session.commit()

        # Validate configuration values
        conf = ConfigParser(allow_no_value=True)
        conf.read(pppoe_conf)

        # basic verification
        self.verify(conf)

        # check auth
        self.assertEqual(conf['chap-secrets']['chap-secrets'], '/run/accel-pppd/pppoe.chap-secrets')
        self.assertEqual(conf['chap-secrets']['gw-ip-address'], gateway)

        # Check for running process
        self.assertTrue('accel-pppd' in (p.name() for p in process_iter()))

    def test_radius_auth(self):
        """ Test configuration of RADIUS authentication for PPPoE server """
        radius_server = '192.0.2.22'
        radius_key = 'secretVyOS'
        radius_port = '2000'
        radius_port_acc = '3000'

        self.session.set(local_if + ['address', '192.0.2.1/32'])
        self.session.set(base_path + ['access-concentrator', ac_name])
        self.session.set(base_path + ['authentication', 'radius', 'server', radius_server, 'key', radius_key])
        self.session.set(base_path + ['authentication', 'radius', 'server', radius_server, 'port', radius_port])
        self.session.set(base_path + ['authentication', 'radius', 'server', radius_server, 'acct-port', radius_port_acc])

        self.session.set(base_path + ['authentication', 'mode', 'radius'])
        self.session.set(base_path + ['client-ip-pool', 'subnet', subnet])
        self.session.set(base_path + ['name-server', nameserver])
        self.session.set(base_path + ['interface', interface])
        self.session.set(base_path + ['local-ip', gateway])

        # commit changes
        self.session.commit()

        # Validate configuration values
        conf = ConfigParser(allow_no_value=True)
        conf.read(pppoe_conf)

        # basic verification
        self.verify(conf)

        # check auth
        self.assertTrue(conf['radius'].getboolean('verbose'))
        self.assertTrue(conf['radius']['acct-timeout'], '3')
        self.assertTrue(conf['radius']['timeout'], '3')
        self.assertTrue(conf['radius']['max-try'], '3')
        self.assertTrue(conf['radius']['gw-ip-address'], gateway)

        server = conf['radius']['server'].split(',')
        self.assertEqual(radius_server, server[0])
        self.assertEqual(radius_key, server[1])
        self.assertEqual(f'auth-port={radius_port}', server[2])
        self.assertEqual(f'acct-port={radius_port_acc}', server[3])
        self.assertEqual(f'req-limit=0', server[4])
        self.assertEqual(f'fail-time=0', server[5])

        # Check for running process
        self.assertTrue('accel-pppd' in (p.name() for p in process_iter()))

if __name__ == '__main__':
    unittest.main()
