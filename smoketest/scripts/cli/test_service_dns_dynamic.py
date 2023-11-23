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

import os
import unittest
import tempfile
import random
import string

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.utils.process import cmd
from vyos.utils.process import process_running

DDCLIENT_SYSTEMD_UNIT = '/run/systemd/system/ddclient.service.d/override.conf'
DDCLIENT_CONF = '/run/ddclient/ddclient.conf'
DDCLIENT_PID = '/run/ddclient/ddclient.pid'
DDCLIENT_PNAME = 'ddclient'

base_path = ['service', 'dns', 'dynamic']
hostname = 'test.ddns.vyos.io'
zone = 'vyos.io'
password = 'paSS_@4ord'
interface = 'eth0'

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
    def test_01_dyndns_service_standard(self):
        ddns = ['address', interface, 'service']
        services = {'cloudflare': {'protocol': 'cloudflare'},
                    'freedns': {'protocol': 'freedns', 'username': 'vyos_user'},
                    'zoneedit': {'protocol': 'zoneedit1', 'username': 'vyos_user'}}

        for svc, details in services.items():
            # Always start with a clean CLI instance
            self.cli_delete(base_path)

            self.cli_set(base_path + ddns + [svc, 'host-name', hostname])
            self.cli_set(base_path + ddns + [svc, 'password', password])
            self.cli_set(base_path + ddns + [svc, 'zone', zone])
            self.cli_set(base_path + ddns + [svc, 'ttl', ttl])
            for opt, value in details.items():
                self.cli_set(base_path + ddns + [svc, opt, value])

            # 'zone' option is supported and required by 'cloudfare', but not 'freedns' and 'zoneedit'
            self.cli_set(base_path + ddns + [svc, 'zone', zone])
            if details['protocol'] == 'cloudflare':
                pass
            else:
                # exception is raised for unsupported ones
                with self.assertRaises(ConfigSessionError):
                    self.cli_commit()
                self.cli_delete(base_path + ddns + [svc, 'zone'])

            # 'ttl' option is supported by 'cloudfare', but not 'freedns' and 'zoneedit'
            self.cli_set(base_path + ddns + [svc, 'ttl', ttl])
            if details['protocol'] == 'cloudflare':
                pass
            else:
                # exception is raised for unsupported ones
                with self.assertRaises(ConfigSessionError):
                    self.cli_commit()
                self.cli_delete(base_path + ddns + [svc, 'ttl'])

            # commit changes
            self.cli_commit()

            # Check the generating config parameters
            ddclient_conf = cmd(f'sudo cat {DDCLIENT_CONF}')
            # default value 300 seconds
            self.assertIn(f'daemon=300', ddclient_conf)
            self.assertIn(f'use=if', ddclient_conf)
            self.assertIn(f'if={interface}', ddclient_conf)
            self.assertIn(f'password={password}', ddclient_conf)

            for opt in details.keys():
                if opt == 'username':
                    login = details[opt]
                    self.assertIn(f'login={login}', ddclient_conf)
                else:
                    tmp = details[opt]
                    self.assertIn(f'{opt}={tmp}', ddclient_conf)

    # IPv6 only DDNS service configuration
    def test_02_dyndns_service_ipv6(self):
        timeout = '60'
        ddns = ['address', interface, 'service', 'dynv6']
        proto = 'dyndns2'
        user = 'none'
        password = 'paSS_4ord'
        srv = 'ddns.vyos.io'
        ip_version = 'ipv6'

        self.cli_set(base_path + ['timeout', timeout])
        self.cli_set(base_path + ddns + ['ip-version', ip_version])
        self.cli_set(base_path + ddns + ['protocol', proto])
        self.cli_set(base_path + ddns + ['server', srv])
        self.cli_set(base_path + ddns + ['username', user])
        self.cli_set(base_path + ddns + ['password', password])
        self.cli_set(base_path + ddns + ['host-name', hostname])

        # commit changes
        self.cli_commit()

        # Check the generating config parameters
        ddclient_conf = cmd(f'sudo cat {DDCLIENT_CONF}')
        self.assertIn(f'daemon={timeout}', ddclient_conf)
        self.assertIn(f'usev6=ifv6', ddclient_conf)
        self.assertIn(f'ifv6={interface}', ddclient_conf)
        self.assertIn(f'protocol={proto}', ddclient_conf)
        self.assertIn(f'server={srv}', ddclient_conf)
        self.assertIn(f'login={user}', ddclient_conf)
        self.assertIn(f'password={password}', ddclient_conf)

    # IPv4+IPv6 dual DDNS service configuration
    def test_03_dyndns_service_dual_stack(self):
        ddns = ['address', interface, 'service']
        services = {'cloudflare': {'protocol': 'cloudflare', 'zone': 'vyos.io'},
                    'freedns': {'protocol': 'freedns', 'username': 'vyos_user'}}
        password = 'vyos_pass'
        ip_version = 'both'

        for svc, details in services.items():
            # Always start with a clean CLI instance
            self.cli_delete(base_path)

            self.cli_set(base_path + ddns + [svc, 'host-name', hostname])
            self.cli_set(base_path + ddns + [svc, 'password', password])
            self.cli_set(base_path + ddns + [svc, 'ip-version', ip_version])
            for opt, value in details.items():
                self.cli_set(base_path + ddns + [svc, opt, value])

            # commit changes
            self.cli_commit()

            # Check the generating config parameters
            ddclient_conf = cmd(f'sudo cat {DDCLIENT_CONF}')
            self.assertIn(f'usev4=ifv4', ddclient_conf)
            self.assertIn(f'usev6=ifv6', ddclient_conf)
            self.assertIn(f'ifv4={interface}', ddclient_conf)
            self.assertIn(f'ifv6={interface}', ddclient_conf)
            self.assertIn(f'password={password}', ddclient_conf)

            for opt in details.keys():
                if opt == 'username':
                    login = details[opt]
                    self.assertIn(f'login={login}', ddclient_conf)
                else:
                    tmp = details[opt]
                    self.assertIn(f'{opt}={tmp}', ddclient_conf)

    def test_04_dyndns_rfc2136(self):
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
            ddclient_conf = cmd(f'sudo cat {DDCLIENT_CONF}')
            self.assertIn(f'use=if', ddclient_conf)
            self.assertIn(f'if={interface}', ddclient_conf)
            self.assertIn(f'protocol=nsupdate', ddclient_conf)
            self.assertIn(f'server={srv}', ddclient_conf)
            self.assertIn(f'zone={zone}', ddclient_conf)
            self.assertIn(f'password={key_file.name}', ddclient_conf)
            self.assertIn(f'ttl={ttl}', ddclient_conf)

    def test_05_dyndns_hostname(self):
        # Check if DDNS service can be configured and runs
        svc_path = ['address', interface, 'service', 'namecheap']
        proto = 'namecheap'
        hostnames = ['@', 'www', hostname, f'@.{hostname}']

        for name in hostnames:
            self.cli_set(base_path + svc_path + ['protocol', proto])
            self.cli_set(base_path + svc_path + ['server', server])
            self.cli_set(base_path + svc_path + ['username', username])
            self.cli_set(base_path + svc_path + ['password', password])
            self.cli_set(base_path + svc_path + ['host-name', name])

            # commit changes
            self.cli_commit()

            # Check the generating config parameters
            ddclient_conf = cmd(f'sudo cat {DDCLIENT_CONF}')
            self.assertIn(f'protocol={proto}', ddclient_conf)
            self.assertIn(f'server={server}', ddclient_conf)
            self.assertIn(f'login={username}', ddclient_conf)
            self.assertIn(f'password={password}', ddclient_conf)
            self.assertIn(f'{name}', ddclient_conf)

    def test_06_dyndns_vrf(self):
        vrf_name = f'vyos-test-{"".join(random.choices(string.ascii_letters + string.digits, k=5))}'
        svc_path = ['address', interface, 'service', 'cloudflare']

        # Always start with a clean CLI instance
        self.cli_delete(base_path)

        self.cli_set(['vrf', 'name', vrf_name, 'table', '12345'])
        self.cli_set(base_path + ['vrf', vrf_name])

        self.cli_set(base_path + svc_path + ['protocol', 'cloudflare'])
        self.cli_set(base_path + svc_path + ['host-name', hostname])
        self.cli_set(base_path + svc_path + ['zone', zone])
        self.cli_set(base_path + svc_path + ['password', password])

        # commit changes
        self.cli_commit()

        # Check for process in VRF
        systemd_override = cmd(f'cat {DDCLIENT_SYSTEMD_UNIT}')
        self.assertIn(f'ExecStart=ip vrf exec {vrf_name} /usr/bin/ddclient -file {DDCLIENT_CONF}',
                      systemd_override)

        # Check for process in VRF
        proc = cmd(f'ip vrf pids {vrf_name}')
        self.assertIn(DDCLIENT_PNAME, proc)

        # Cleanup VRF
        self.cli_delete(['vrf', 'name', vrf_name])

if __name__ == '__main__':
    unittest.main(verbosity=2)
