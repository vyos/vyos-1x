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

import os
import re
import unittest

from configparser import ConfigParser
from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.util import process_named_running
from vyos.util import cmd

process_name = 'accel-pppd'
base_path = ['service', 'pppoe-server']
local_if = ['interfaces', 'dummy', 'dum667']
pppoe_conf = '/run/accel-pppd/pppoe.conf'

ac_name = 'ACN'
gateway = '192.0.2.1'
nameserver = '9.9.9.9'
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
        mtu = '1492'

        # validate some common values in the configuration
        for tmp in ['log_syslog', 'pppoe', 'chap-secrets', 'ippool',
                    'auth_mschap_v2', 'auth_mschap_v1', 'auth_chap_md5',
                    'auth_pap', 'shaper']:
            # Settings without values provide None
            self.assertEqual(conf['modules'][tmp], None)

        # check Access Concentrator setting
        self.assertTrue(conf['pppoe']['ac-name'] == ac_name)
        self.assertTrue(conf['pppoe'].getboolean('verbose'))
        self.assertTrue(conf['pppoe']['interface'], interface)

        # check ppp
        self.assertTrue(conf['ppp'].getboolean('verbose'))
        self.assertTrue(conf['ppp'].getboolean('check-ip'))
        self.assertEqual(conf['ppp']['mtu'], mtu)
        self.assertEqual(conf['ppp']['lcp-echo-interval'], '30')
        self.assertEqual(conf['ppp']['lcp-echo-timeout'], '0')
        self.assertEqual(conf['ppp']['lcp-echo-failure'], '3')

    def basic_config(self):
        self.session.set(local_if + ['address', '192.0.2.1/32'])

        # PPPoE local auth mode requires local users to be configured!
        self.session.set(base_path + ['authentication', 'local-users', 'username', 'vyos', 'password', 'vyos'])
        self.session.set(base_path + ['authentication', 'mode', 'local'])

        self.session.set(base_path + ['access-concentrator', ac_name])
        self.session.set(base_path + ['authentication', 'mode', 'local'])
        self.session.set(base_path + ['name-server', nameserver])
        self.session.set(base_path + ['interface', interface])
        self.session.set(base_path + ['local-ip', gateway])

    def test_local_user(self):
        """ Test configuration of local authentication for PPPoE server """
        self.basic_config()

        # other settings
        self.session.set(base_path + ['ppp-options', 'ccp'])
        self.session.set(base_path + ['ppp-options', 'mppe', 'require'])
        self.session.set(base_path + ['limits', 'connection-limit', '20/min'])

        # upload / download limit
        user = 'test'
        password = 'test2'
        static_ip = '100.100.100.101'
        self.session.set(base_path + ['authentication', 'local-users', 'username', user, 'password', password])
        self.session.set(base_path + ['authentication', 'local-users', 'username', user, 'static-ip', static_ip])
        self.session.set(base_path + ['authentication', 'local-users', 'username', user, 'rate-limit', 'upload', '5000'])

        # upload rate-limit requires also download rate-limit
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(base_path + ['authentication', 'local-users', 'username', user, 'rate-limit', 'download', '10000'])

        # min-mtu
        min_mtu = '1400'
        self.session.set(base_path + ['ppp-options', 'min-mtu', min_mtu])

        # mru
        mru = '9000'
        self.session.set(base_path + ['ppp-options', 'mru', mru])

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

        # check ppp
        self.assertEqual(conf['ppp']['mppe'], 'require')
        self.assertEqual(conf['ppp']['min-mtu'], min_mtu)
        self.assertEqual(conf['ppp']['mru'], mru)

        self.assertTrue(conf['ppp'].getboolean('ccp'))

        # check other settings
        self.assertEqual(conf['connlimit']['limit'], '20/min')

        # check local users
        tmp = cmd('sudo cat /run/accel-pppd/pppoe.chap-secrets')
        regex = f'{user}\s+\*\s+{password}\s+{static_ip}\s+10000/5000'
        tmp = re.findall(regex, tmp)
        self.assertTrue(tmp)

        # Check for running process
        self.assertTrue(process_named_running(process_name))

    def test_radius_auth(self):
        """ Test configuration of RADIUS authentication for PPPoE server """
        radius_server = '192.0.2.22'
        radius_key = 'secretVyOS'
        radius_port = '2000'
        radius_port_acc = '3000'
        radius_acct_interim_jitter = '9'
        radius_called_sid = 'ifname:mac'

        self.basic_config()

        self.session.set(base_path + ['authentication', 'mode', 'radius'])
        self.session.set(base_path + ['authentication', 'radius', 'server', radius_server, 'key', radius_key])
        self.session.set(base_path + ['authentication', 'radius', 'server', radius_server, 'port', radius_port])
        self.session.set(base_path + ['authentication', 'radius', 'server', radius_server, 'acct-port', radius_port_acc])
        self.session.set(base_path + ['authentication', 'radius', 'acct-interim-jitter', radius_acct_interim_jitter])
        self.session.set(base_path + ['authentication', 'radius', 'called-sid-format', radius_called_sid])

        coa_server = '4.4.4.4'
        coa_key = 'testCoA'
        self.session.set(base_path + ['authentication', 'radius', 'dynamic-author', 'server', coa_server])
        self.session.set(base_path + ['authentication', 'radius', 'dynamic-author', 'key', coa_key])

        nas_id = 'VyOS-PPPoE'
        nas_ip = '7.7.7.7'
        self.session.set(base_path + ['authentication', 'radius', 'nas-identifier', nas_id])
        self.session.set(base_path + ['authentication', 'radius', 'nas-ip-address', nas_ip])

        source_address = '1.2.3.4'
        self.session.set(base_path + ['authentication', 'radius', 'source-address', source_address])

        # commit changes
        self.session.commit()

        # Validate configuration values
        conf = ConfigParser(allow_no_value=True)
        conf.read(pppoe_conf)

        # basic verification
        self.verify(conf)

        # check auth
        self.assertTrue(conf['radius'].getboolean('verbose'))
        self.assertEqual(conf['radius']['acct-timeout'], '3')
        self.assertEqual(conf['radius']['timeout'], '3')
        self.assertEqual(conf['radius']['max-try'], '3')
        self.assertEqual(conf['radius']['gw-ip-address'], gateway)
        self.assertEqual(conf['radius']['acct-interim-jitter'], radius_acct_interim_jitter)
        self.assertEqual(conf['radius']['called-sid'], radius_called_sid)
        self.assertEqual(conf['radius']['dae-server'], f'{coa_server}:1700,{coa_key}')
        self.assertEqual(conf['radius']['nas-identifier'], nas_id)
        self.assertEqual(conf['radius']['nas-ip-address'], nas_ip)
        self.assertEqual(conf['radius']['bind'], source_address)

        server = conf['radius']['server'].split(',')
        self.assertEqual(radius_server, server[0])
        self.assertEqual(radius_key, server[1])
        self.assertEqual(f'auth-port={radius_port}', server[2])
        self.assertEqual(f'acct-port={radius_port_acc}', server[3])
        self.assertEqual(f'req-limit=0', server[4])
        self.assertEqual(f'fail-time=0', server[5])

        # check defaults
        self.assertEqual(conf['ppp']['mppe'], 'prefer')
        self.assertFalse(conf['ppp'].getboolean('ccp'))

        # Check for running process
        self.assertTrue(process_named_running(process_name))

    def test_auth_protocols(self):
        """ Test configuration of local authentication for PPPoE server """
        self.basic_config()

        # explicitly test mschap-v2 - no special reason
        self.session.set(base_path + ['authentication', 'protocols', 'mschap-v2'])

        # commit changes
        self.session.commit()

        # Validate configuration values
        conf = ConfigParser(allow_no_value=True)
        conf.read(pppoe_conf)

        self.assertEqual(conf['modules']['auth_mschap_v2'], None)

        # Check for running process
        self.assertTrue(process_named_running(process_name))


    def test_ip_pool(self):
        """ Test configuration of IPv6 client pools """
        self.basic_config()

        subnet = '172.18.0.0/24'
        self.session.set(base_path + ['client-ip-pool', 'subnet', subnet])

        start = '192.0.2.10'
        stop = '192.0.2.20'
        start_stop = f'{start}-{stop}'
        self.session.set(base_path + ['client-ip-pool', 'start', start])
        self.session.set(base_path + ['client-ip-pool', 'stop', stop])

        # commit changes
        self.session.commit()

        # Validate configuration values
        conf = ConfigParser(allow_no_value=True)
        conf.read(pppoe_conf)

        # check configured subnet
        self.assertEqual(conf['ip-pool'][subnet], None)
        self.assertEqual(conf['ip-pool'][start_stop], None)
        self.assertEqual(conf['ip-pool']['gw-ip-address'], gateway)


    def test_ipv6_pool(self):
        """ Test configuration of IPv6 client pools """
        self.basic_config()

        # Enable IPv6
        allow_ipv6 = 'allow'
        random = 'random'
        self.session.set(base_path + ['ppp-options', 'ipv6', allow_ipv6])
        self.session.set(base_path + ['ppp-options', 'ipv6-intf-id', random])
        self.session.set(base_path + ['ppp-options', 'ipv6-accept-peer-intf-id'])
        self.session.set(base_path + ['ppp-options', 'ipv6-peer-intf-id', random])

        prefix = '2001:db8:ffff::/64'
        prefix_mask = '128'
        client_prefix = f'{prefix},{prefix_mask}'
        self.session.set(base_path + ['client-ipv6-pool', 'prefix', prefix, 'mask', prefix_mask])

        delegate_prefix = '2001:db8::/40'
        delegate_mask = '56'
        self.session.set(base_path + ['client-ipv6-pool', 'delegate', delegate_prefix, 'delegation-prefix', delegate_mask])

        # commit changes
        self.session.commit()

        # Validate configuration values
        conf = ConfigParser(allow_no_value=True, delimiters='=')
        conf.read(pppoe_conf)

        for tmp in ['ipv6pool', 'ipv6_nd', 'ipv6_dhcp']:
            self.assertEqual(conf['modules'][tmp], None)

        self.assertEqual(conf['ppp']['ipv6'], allow_ipv6)
        self.assertEqual(conf['ppp']['ipv6-intf-id'], random)
        self.assertEqual(conf['ppp']['ipv6-peer-intf-id'], random)
        self.assertTrue(conf['ppp'].getboolean('ipv6-accept-peer-intf-id'))

        self.assertEqual(conf['ipv6-pool'][client_prefix], None)
        self.assertEqual(conf['ipv6-pool']['delegate'], f'{delegate_prefix},{delegate_mask}')

        # Check for running process
        self.assertTrue(process_named_running(process_name))

if __name__ == '__main__':
    unittest.main()
