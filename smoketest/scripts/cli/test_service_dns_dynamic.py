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

from getpass import getuser
from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.util import read_file
from vyos.util import process_named_running

PROCESS_NAME = 'ddclient'
DDCLIENT_CONF = '/run/ddclient/ddclient.conf'
base_path = ['service', 'dns', 'dynamic']

def get_config_value(key):
    tmp = read_file(DDCLIENT_CONF)
    tmp = re.findall(r'\n?{}=+(.*)'.format(key), tmp)
    tmp = tmp[0].rstrip(',')
    return tmp

class TestServiceDDNS(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())

    def tearDown(self):
        # Delete DDNS configuration
        self.session.delete(base_path)
        self.session.commit()

        del self.session

    def test_service(self):
        """ Check individual DDNS service providers """
        ddns = ['interface', 'eth0', 'service']
        services = ['cloudflare', 'afraid', 'dyndns', 'zoneedit']

        for service in services:
            user = 'vyos_user'
            password = 'vyos_pass'
            zone = 'vyos.io'
            self.session.delete(base_path)
            self.session.set(base_path + ddns + [service, 'host-name', 'test.ddns.vyos.io'])
            self.session.set(base_path + ddns + [service, 'login', user])
            self.session.set(base_path + ddns + [service, 'password', password])
            self.session.set(base_path + ddns + [service, 'zone', zone])

            # commit changes
            if service == 'cloudflare':
                self.session.commit()
            else:
                # zone option only works on cloudflare, an exception is raised
                # for all others
                with self.assertRaises(ConfigSessionError):
                    self.session.commit()
                self.session.delete(base_path + ddns + [service, 'zone', 'vyos.io'])
                # commit changes again - now it should work
                self.session.commit()

            # we can only read the configuration file when we operate as 'root'
            if getuser() == 'root':
                protocol = get_config_value('protocol')
                login = get_config_value('login')
                pwd = get_config_value('password')

                # some services need special treatment
                protoname = service
                if service == 'cloudflare':
                    tmp = get_config_value('zone')
                    self.assertTrue(tmp == zone)
                elif service == 'afraid':
                    protoname = 'freedns'
                elif service == 'dyndns':
                    protoname = 'dyndns2'
                elif service == 'zoneedit':
                    protoname = 'zoneedit1'

                self.assertTrue(protocol == protoname)
                self.assertTrue(login == user)
                self.assertTrue(pwd == "'" + password + "'")

            # Check for running process
            self.assertTrue(process_named_running(PROCESS_NAME))

    def test_rfc2136(self):
        """ Check if DDNS service can be configured and runs """
        ddns = ['interface', 'eth0', 'rfc2136', 'vyos']
        ddns_key_file = '/config/auth/my.key'

        self.session.set(base_path + ddns + ['key', ddns_key_file])
        self.session.set(base_path + ddns + ['record', 'test.ddns.vyos.io'])
        self.session.set(base_path + ddns + ['server', 'ns1.vyos.io'])
        self.session.set(base_path + ddns + ['ttl', '300'])
        self.session.set(base_path + ddns + ['zone', 'vyos.io'])

        # ensure an exception will be raised as no key is present
        if os.path.exists(ddns_key_file):
            os.unlink(ddns_key_file)

        # check validate() - the key file does not exist yet
        with self.assertRaises(ConfigSessionError):
            self.session.commit()

        with open(ddns_key_file, 'w') as f:
            f.write('S3cretKey')

        # commit changes
        self.session.commit()

        # TODO: inspect generated configuration file

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

if __name__ == '__main__':
    unittest.main(verbosity=2)
