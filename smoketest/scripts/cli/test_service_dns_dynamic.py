#!/usr/bin/env python3
#
# Copyright (C) 2019-2023 VyOS maintainers and contributors
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
import tempfile

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.utils.process import cmd
from vyos.utils.process import process_running

DDCLIENT_CONF = '/run/ddclient/ddclient.conf'
DDCLIENT_PID = '/run/ddclient/ddclient.pid'

base_path = ['service', 'dns', 'dynamic']
hostname = 'test.ddns.vyos.io'
zone = 'vyos.io'
password = 'paSS_@4ord'
interface = 'eth0'


def get_config_value(key):
    tmp = cmd(f'sudo cat {DDCLIENT_CONF}')
    vals = re.findall(r'\n?{}=([.-@_A-Za-z0-9]+),? \\'.format(key), tmp)
    return vals[0] if vals else ''


class TestServiceDDNS(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        # Check for running process
        self.assertTrue(process_running(DDCLIENT_PID))

        # Delete DDNS configuration
        self.cli_delete(base_path)
        self.cli_commit()

        # PID file must no londer exist after process exited
        self.assertFalse(os.path.exists(DDCLIENT_PID))

    # IPv4 standard DDNS service configuration
    def test_dyndns_service_standard(self):
        ddns = ['address', interface, 'service']
        services = {'cloudflare': {'protocol': 'cloudflare'},
                    'freedns': {'protocol': 'freedns', 'username': 'vyos_user'},
                    'zoneedit': {'protocol': 'zoneedit1', 'username': 'vyos_user'}}

        for svc, details in services.items():
            self.cli_delete(base_path)
            self.cli_set(base_path + ddns + [svc, 'host-name', hostname])
            for opt, value in details.items():
                self.cli_set(base_path + ddns + [svc, opt, value])
            self.cli_set(base_path + ddns + [svc, 'password', password])
            self.cli_set(base_path + ddns + [svc, 'zone', zone])

            # commit changes
            if details['protocol'] == 'cloudflare':
                self.cli_commit()
            else:
                # zone option does not work on all protocols, an exception is
                # raised for all others
                with self.assertRaises(ConfigSessionError):
                    self.cli_commit()
                self.cli_delete(base_path + ddns + [svc, 'zone', zone])
                # commit changes again - now it should work
                self.cli_commit()

            # Check the generating config parameters
            self.assertEqual(get_config_value('use'), 'if')
            self.assertEqual(get_config_value('if'), interface)
            self.assertEqual(get_config_value('password'), password)

            for opt in details.keys():
                if opt == 'username':
                    self.assertEqual(get_config_value('login'), details[opt])
                else:
                    self.assertEqual(get_config_value(opt), details[opt])

    # IPv6 only DDNS service configuration
    def test_dyndns_service_ipv6(self):
        ddns = ['address', interface, 'service', 'dynv6']
        proto = 'dyndns2'
        user = 'none'
        password = 'paSS_4ord'
        srv = 'ddns.vyos.io'
        ip_version = 'ipv6'

        self.cli_set(base_path + ddns + ['ip-version', ip_version])
        self.cli_set(base_path + ddns + ['protocol', proto])
        self.cli_set(base_path + ddns + ['server', srv])
        self.cli_set(base_path + ddns + ['username', user])
        self.cli_set(base_path + ddns + ['password', password])
        self.cli_set(base_path + ddns + ['host-name', hostname])

        # commit changes
        self.cli_commit()

        # Check the generating config parameters
        self.assertEqual(get_config_value('usev6'), 'ifv6')
        self.assertEqual(get_config_value('ifv6'), interface)
        self.assertEqual(get_config_value('protocol'), proto)
        self.assertEqual(get_config_value('server'), srv)
        self.assertEqual(get_config_value('login'), user)
        self.assertEqual(get_config_value('password'), password)

    # IPv4+IPv6 dual DDNS service configuration
    def test_dyndns_service_dual_stack(self):
        ddns = ['address', interface, 'service']
        services = {'cloudflare': {'protocol': 'cloudflare', 'zone': 'vyos.io'},
                    'freedns': {'protocol': 'freedns', 'username': 'vyos_user'}}
        password = 'vyos_pass'
        ip_version = 'both'

        for svc, details in services.items():
            self.cli_delete(base_path)
            self.cli_set(base_path + ddns + [svc, 'host-name', hostname])
            for opt, value in details.items():
                self.cli_set(base_path + ddns + [svc, opt, value])
            self.cli_set(base_path + ddns + [svc, 'password', password])
            self.cli_set(base_path + ddns + [svc, 'ip-version', ip_version])

            # commit changes
            self.cli_commit()

            # Check the generating config parameters
            self.assertEqual(get_config_value('usev4'), 'ifv4')
            self.assertEqual(get_config_value('usev6'), 'ifv6')
            self.assertEqual(get_config_value('ifv4'), interface)
            self.assertEqual(get_config_value('ifv6'), interface)
            self.assertEqual(get_config_value('password'), password)

            for opt in details.keys():
                if opt == 'username':
                    self.assertEqual(get_config_value('login'), details[opt])
                else:
                    self.assertEqual(get_config_value(opt), details[opt])

    def test_dyndns_rfc2136(self):
        # Check if DDNS service can be configured and runs
        ddns = ['address', interface, 'rfc2136', 'vyos']
        srv = 'ns1.vyos.io'
        zone = 'vyos.io'
        ttl = '300'

        with tempfile.NamedTemporaryFile(prefix='/config/auth/') as key_file:
            key_file.write(b'S3cretKey')

            self.cli_set(base_path + ddns + ['server', srv])
            self.cli_set(base_path + ddns + ['zone', zone])
            self.cli_set(base_path + ddns + ['key', key_file.name])
            self.cli_set(base_path + ddns + ['ttl', ttl])
            self.cli_set(base_path + ddns + ['host-name', hostname])

            # commit changes
            self.cli_commit()

            # Check some generating config parameters
            self.assertEqual(get_config_value('use'), 'if')
            self.assertEqual(get_config_value('if'), interface)
            self.assertEqual(get_config_value('protocol'), 'nsupdate')
            self.assertEqual(get_config_value('server'), srv)
            self.assertEqual(get_config_value('zone'), zone)
            self.assertEqual(get_config_value('password'), key_file.name)
            self.assertEqual(get_config_value('ttl'), ttl)


if __name__ == '__main__':
    unittest.main(verbosity=2)
