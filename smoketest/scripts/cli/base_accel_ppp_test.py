# Copyright (C) 2020 VyOS maintainers and contributors
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
from vyos.util import cmd
from vyos.util import get_half_cpus
from vyos.util import process_named_running
from vyos.validate import is_ipv4

class BasicAccelPPPTest:
    class BaseTest(unittest.TestCase):

        def setUp(self):
            self.session = ConfigSession(os.getpid())
            # ensure we can also run this test on a live system - so lets clean
            # out the current configuration :)
            self.session.delete(self._base_path)

        def tearDown(self):
            self.session.delete(self._base_path)
            self.session.commit()
            del self.session

        def set(self, path):
            self.session.set(self._base_path + path)

        def basic_config(self):
            # PPPoE local auth mode requires local users to be configured!
            self.set(['authentication', 'local-users', 'username', 'vyos', 'password', 'vyos'])
            self.set(['authentication', 'mode', 'local'])


        def verify(self, conf):
            self.assertEqual(conf['core']['thread-count'], str(get_half_cpus()))

        def test_name_servers(self):
            """ Verify proper Name-Server configuration for IPv4 and IPv6 """
            self.basic_config()

            nameserver = ['192.0.2.1', '192.0.2.2', '2001:db8::1']
            for ns in nameserver:
                self.set(['name-server', ns])

            # commit changes
            self.session.commit()

            # Validate configuration values
            conf = ConfigParser(allow_no_value=True, delimiters='=')
            conf.read(self._config_file)

            # IPv4 and IPv6 nameservers must be checked individually
            for ns in nameserver:
                if is_ipv4(ns):
                    self.assertIn(ns, [conf['dns']['dns1'], conf['dns']['dns2']])
                else:
                    self.assertEqual(conf['ipv6-dns'][ns], None)

        def test_authentication_local(self):
            """ Test configuration of local authentication """
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
                self.session.commit()
            self.set(['authentication', 'local-users', 'username', user, 'rate-limit', 'download', download])

            # commit changes
            self.session.commit()

            # Validate configuration values
            conf = ConfigParser(allow_no_value=True, delimiters='=')
            conf.read(self._config_file)

            # basic verification
            self.verify(conf)

            # check local users
            tmp = cmd(f'sudo cat {self._chap_secrets}')
            regex = f'{user}\s+\*\s+{password}\s+{static_ip}\s+{download}/{upload}'
            tmp = re.findall(regex, tmp)
            self.assertTrue(tmp)

            # Check for running process
            self.assertTrue(process_named_running(self._process_name))
