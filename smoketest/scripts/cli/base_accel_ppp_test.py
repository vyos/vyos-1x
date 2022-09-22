# Copyright (C) 2020-2022 VyOS maintainers and contributors
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

from base_vyostest_shim import VyOSUnitTestSHIM
from configparser import ConfigParser

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.template import is_ipv4
from vyos.util import cmd
from vyos.util import get_half_cpus
from vyos.util import process_named_running

class BasicAccelPPPTest:
    class TestCase(VyOSUnitTestSHIM.TestCase):

        @classmethod
        def setUpClass(cls):
            cls._process_name = 'accel-pppd'

            super(BasicAccelPPPTest.TestCase, cls).setUpClass()

            # ensure we can also run this test on a live system - so lets clean
            # out the current configuration :)
            cls.cli_delete(cls, cls._base_path)

        def setUp(self):
            self._gateway = '192.0.2.1'
            # ensure we can also run this test on a live system - so lets clean
            # out the current configuration :)
            self.cli_delete(self._base_path)

        def tearDown(self):
            # Check for running process
            self.assertTrue(process_named_running(self._process_name))

            self.cli_delete(self._base_path)
            self.cli_commit()

            # Check for running process
            self.assertFalse(process_named_running(self._process_name))

        def set(self, path):
            self.cli_set(self._base_path + path)

        def delete(self, path):
            self.cli_delete(self._base_path + path)

        def basic_config(self):
            # PPPoE local auth mode requires local users to be configured!
            self.set(['authentication', 'local-users', 'username', 'vyos', 'password', 'vyos'])
            self.set(['authentication', 'mode', 'local'])
            self.set(['gateway-address', self._gateway])

        def verify(self, conf):
            self.assertEqual(conf['core']['thread-count'], str(get_half_cpus()))

        def test_accel_name_servers(self):
            # Verify proper Name-Server configuration for IPv4 and IPv6
            self.basic_config()

            nameserver = ['192.0.2.1', '192.0.2.2', '2001:db8::1']
            for ns in nameserver:
                self.set(['name-server', ns])

            # commit changes
            self.cli_commit()

            # Validate configuration values
            conf = ConfigParser(allow_no_value=True, delimiters='=')
            conf.read(self._config_file)

            # IPv4 and IPv6 nameservers must be checked individually
            for ns in nameserver:
                if is_ipv4(ns):
                    self.assertIn(ns, [conf['dns']['dns1'], conf['dns']['dns2']])
                else:
                    self.assertEqual(conf['ipv6-dns'][ns], None)

        def test_accel_local_authentication(self):
            # Test configuration of local authentication
            self.basic_config()

            # upload / download limit
            user = 'test'
            password = 'test2'
            static_ip = '100.100.100.101'
            upload = '5000'
            download = '10000'

            self.set(['authentication', 'local-users', 'username', user, 'password', password])
            self.set(['authentication', 'local-users', 'username', user, 'static-ip', static_ip])
            self.set(['authentication', 'local-users', 'username', user, 'rate-limit', 'upload', upload])

            # upload rate-limit requires also download rate-limit
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
            self.set(['authentication', 'local-users', 'username', user, 'rate-limit', 'download', download])

            # commit changes
            self.cli_commit()

            # Validate configuration values
            conf = ConfigParser(allow_no_value=True, delimiters='=')
            conf.read(self._config_file)

            # check proper path to chap-secrets file
            self.assertEqual(conf['chap-secrets']['chap-secrets'], self._chap_secrets)

            # basic verification
            self.verify(conf)

            # check local users
            tmp = cmd(f'sudo cat {self._chap_secrets}')
            regex = f'{user}\s+\*\s+{password}\s+{static_ip}\s+{download}/{upload}'
            tmp = re.findall(regex, tmp)
            self.assertTrue(tmp)

            # Check local-users default value(s)
            self.delete(['authentication', 'local-users', 'username', user, 'static-ip'])
            # commit changes
            self.cli_commit()

            # check local users
            tmp = cmd(f'sudo cat {self._chap_secrets}')
            regex = f'{user}\s+\*\s+{password}\s+\*\s+{download}/{upload}'
            tmp = re.findall(regex, tmp)
            self.assertTrue(tmp)

        def test_accel_radius_authentication(self):
            # Test configuration of RADIUS authentication for PPPoE server
            self.basic_config()

            radius_server = '192.0.2.22'
            radius_key = 'secretVyOS'
            radius_port = '2000'
            radius_port_acc = '3000'

            self.set(['authentication', 'mode', 'radius'])
            self.set(['authentication', 'radius', 'server', radius_server, 'key', radius_key])
            self.set(['authentication', 'radius', 'server', radius_server, 'port', radius_port])
            self.set(['authentication', 'radius', 'server', radius_server, 'acct-port', radius_port_acc])

            coa_server = '4.4.4.4'
            coa_key = 'testCoA'
            self.set(['authentication', 'radius', 'dynamic-author', 'server', coa_server])
            self.set(['authentication', 'radius', 'dynamic-author', 'key', coa_key])

            nas_id = 'VyOS-PPPoE'
            nas_ip = '7.7.7.7'
            self.set(['authentication', 'radius', 'nas-identifier', nas_id])
            self.set(['authentication', 'radius', 'nas-ip-address', nas_ip])

            source_address = '1.2.3.4'
            self.set(['authentication', 'radius', 'source-address', source_address])

            # commit changes
            self.cli_commit()

            # Validate configuration values
            conf = ConfigParser(allow_no_value=True, delimiters='=')
            conf.read(self._config_file)

            # basic verification
            self.verify(conf)

            # check auth
            self.assertTrue(conf['radius'].getboolean('verbose'))
            self.assertEqual(conf['radius']['acct-timeout'], '3')
            self.assertEqual(conf['radius']['timeout'], '3')
            self.assertEqual(conf['radius']['max-try'], '3')

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

            #
            # Disable Radius Accounting
            #
            self.delete(['authentication', 'radius', 'server', radius_server, 'acct-port'])
            self.set(['authentication', 'radius', 'server', radius_server, 'disable-accounting'])

            # commit changes
            self.cli_commit()

            conf.read(self._config_file)

            server = conf['radius']['server'].split(',')
            self.assertEqual(radius_server, server[0])
            self.assertEqual(radius_key, server[1])
            self.assertEqual(f'auth-port={radius_port}', server[2])
            self.assertEqual(f'acct-port=0', server[3])
            self.assertEqual(f'req-limit=0', server[4])
            self.assertEqual(f'fail-time=0', server[5])

