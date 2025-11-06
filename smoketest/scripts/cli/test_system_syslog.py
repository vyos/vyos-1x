#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.utils.file import read_file
from vyos.utils.process import cmd
from vyos.utils.process import process_named_running
from vyos.xml_ref import default_value

PROCESS_NAME = 'rsyslogd'
RSYSLOG_CONF = '/run/rsyslog/rsyslog.conf'
CERT_DIR = '/etc/rsyslog.d/certs'

base_path = ['system', 'syslog']
pki_base = ['pki']

dummy_interface = 'dum372874'

ca_cert_name = "syslog_ca_certificate"
ca_cert = """
MIIBrTCCAV+gAwIBAgIUdTEOleLyGTteZC+yEi252lRUq8EwBQYDK2VwMEsxCzAJ
BgNVBAYTAlVTMQ4wDAYDVQQIDAVTdGF0ZTENMAsGA1UEBwwEQ2l0eTEMMAoGA1UE
CgwDT3JnMQ8wDQYDVQQDDAZSb290Q0EwIBcNMjUwOTE1MTQxNDI4WhgPMjEyNTA4
MjIxNDE0MjhaMEsxCzAJBgNVBAYTAlVTMQ4wDAYDVQQIDAVTdGF0ZTENMAsGA1UE
BwwEQ2l0eTEMMAoGA1UECgwDT3JnMQ8wDQYDVQQDDAZSb290Q0EwKjAFBgMrZXAD
IQCtTlgU+aqU/i6k6b318vebALk0zs9RvE96vw7taIt2iqNTMFEwHQYDVR0OBBYE
FHl8GywRMCWSotNGmyjuvRbPqCq8MB8GA1UdIwQYMBaAFHl8GywRMCWSotNGmyju
vRbPqCq8MA8GA1UdEwEB/wQFMAMBAf8wBQYDK2VwA0EAouZ4s+/ZeZxZxOZ7yFG0
RQ9BfPWySrX4kgavyJJeg8LNCYUIRIP6iC41MTyHUVsWwar91xBT0DKBkpwrOQ0n
Dg==
"""

client_cert_name = "syslog_client_certificate"
client_cert = """
MIIBVjCCAQgCFArrkIM+zg8luHbXwsS8cUB5xrh/MAUGAytlcDBLMQswCQYDVQQG
EwJVUzEOMAwGA1UECAwFU3RhdGUxDTALBgNVBAcMBENpdHkxDDAKBgNVBAoMA09y
ZzEPMA0GA1UEAwwGUm9vdENBMB4XDTI1MDkxNTE0MTUwN1oXDTM1MDkxMzE0MTUw
N1owUDELMAkGA1UEBhMCVVMxDjAMBgNVBAgMBVN0YXRlMQ0wCwYDVQQHDARDaXR5
MQwwCgYDVQQKDANPcmcxFDASBgNVBAMMC2V4YW1wbGUuY29tMCowBQYDK2VwAyEA
eZZRz7yVQ+exm6vyh/GdGZrTSEmtbvfafG0digqpfnUwBQYDK2VwA0EAU8/kw1i0
s4j2fPQmU1q6Qql3xaxUlDyzhRPSIeH7ZhOlNg8R7gR1QnA7Rel6oU4EqJJHvz9l
83HQAy7ZcNIoBw==
"""

client_cert_key = """
MC4CAQAwBQYDK2VwBCIEIG59XPVZoMCxBVD/eJVqJSmV+Uc0bUHjHS4bkfkjM6Jj
"""

def get_config(string=''):
    """
    Retrieve current "running configuration" from FRR
    string:        search for a specific start string in the configuration
    """
    command = 'cat /run/rsyslog/rsyslog.conf'
    if string:
        command += f' | sed -n "/^{string}$/,/}}/p"' # }} required to escape } in f-string
    return cmd(command)

class TestRSYSLOGService(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestRSYSLOGService, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)
        cls.cli_delete(cls, ['vrf'])
        cls.cli_delete(cls, pki_base)

    def tearDown(self):
        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

        # delete test certificates for syslog
        self.cli_delete(pki_base)

        # delete testing SYSLOG config
        self.cli_delete(base_path)
        self.cli_commit()

        # The default syslog implementation should make syslog.service a
        # symlink to itself
        self.assertEqual(os.readlink('/etc/systemd/system/syslog.service'),
                         '/lib/systemd/system/rsyslog.service')

        # Check for running process
        self.assertFalse(process_named_running(PROCESS_NAME))
        # always forward to base class
        super().tearDown()

    def _set_tls_certificates(self):
        self.cli_set(
            pki_base + ['ca', ca_cert_name, 'certificate', ca_cert.replace('\n', '')]
        )
        self.cli_set(
            pki_base
            + [
                'certificate',
                client_cert_name,
                'certificate',
                client_cert.replace('\n', ''),
            ]
        )
        self.cli_set(
            pki_base
            + [
                'certificate',
                client_cert_name,
                'private',
                'key',
                client_cert_key.replace('\n', ''),
            ]
        )

    def test_console(self):
        level = 'warning'
        self.cli_set(base_path + ['console', 'facility', 'all', 'level'], value=level)
        self.cli_commit()

        rsyslog_conf = get_config()
        config = [
            f'if prifilt("*.{level}") then {{', # {{ required to escape { in f-string
             'action(type="omfile" file="/dev/console")',
        ]
        for tmp in config:
            self.assertIn(tmp, rsyslog_conf)

    def test_basic(self):
        hostname = 'vyos123'
        domain_name = 'example.local'
        default_marker_interval = default_value(base_path + ['marker', 'interval'])

        facility = {
            'auth': {'level': 'info'},
            'kern': {'level': 'debug'},
            'all':  {'level': 'notice'},
        }

        self.cli_set(['system', 'host-name'], value=hostname)
        self.cli_set(['system', 'domain-name'], value=domain_name)
        self.cli_set(base_path + ['preserve-fqdn'])

        for tmp, tmp_options in facility.items():
            level = tmp_options['level']
            self.cli_set(base_path + ['local', 'facility', tmp, 'level'], value=level)

        self.cli_commit()

        config = get_config('')
        expected = [
            f'module(load="immark" interval="{default_marker_interval}")',
            'global(preserveFQDN="on")',
            f'global(localHostname="{hostname}.{domain_name}")',
        ]
        for e in expected:
            self.assertIn(e, config)

        config = get_config('#### GLOBAL LOGGING ####')
        prifilt = []
        for tmp, tmp_options in facility.items():
            if tmp == 'all':
                tmp = '*'
            level = tmp_options['level']
            prifilt.append(f'{tmp}.{level}')

        prifilt.sort()
        prifilt = ','.join(prifilt)

        self.assertIn(f'if prifilt("{prifilt}") then {{', config)
        self.assertIn( '    action(', config)
        self.assertIn( '        type="omfile"', config)
        self.assertIn( '        file="/var/log/messages"', config)
        self.assertIn( '        rotation.sizeLimit="524288"', config)
        self.assertIn( '        rotation.sizeLimitCommand="/usr/sbin/logrotate /etc/logrotate.d/vyos-rsyslog"', config)

        self.cli_set(base_path + ['marker', 'disable'])
        self.cli_commit()

        config = get_config('')
        self.assertNotIn('module(load="immark"', config)

    def test_remote(self):
        dummy_if_path = ['interfaces', 'dummy', dummy_interface]
        rhosts = {
            '169.254.0.1': {
                'facility': {'auth' : {'level': 'info'}},
                'protocol': 'udp',
            },
            '2001:db8::1': {
                'facility': {'all' : {'level': 'debug'}},
                'port': '1514',
                'protocol': 'udp',
            },
            'syslog.vyos.net': {
                'facility': {'all' : {'level': 'debug'}},
                'port': '1515',
                'protocol': 'tcp',
            },
            '169.254.0.3': {
                'facility': {'auth' : {'level': 'info'},
                             'kern' : {'level': 'debug'},
                             'all'  : {'level': 'notice'},
                },
                'format': ['include-timezone', 'octet-counted'],
                'protocol': 'tcp',
                'port': '10514',
            },
        }
        default_port = default_value(base_path + ['remote', next(iter(rhosts)), 'port'])
        default_protocol = default_value(base_path + ['remote', next(iter(rhosts)), 'protocol'])

        for remote, remote_options in rhosts.items():
            remote_base = base_path + ['remote', remote]

            if 'port' in remote_options:
                self.cli_set(remote_base + ['port'], value=remote_options['port'])

            if 'facility' in remote_options:
                for facility, facility_options in remote_options['facility'].items():
                    level = facility_options['level']
                    self.cli_set(remote_base + ['facility', facility, 'level'],
                                 value=level)

            if 'format' in remote_options:
                for format in remote_options['format']:
                    self.cli_set(remote_base + ['format'], value=format)

            if 'protocol' in remote_options:
                protocol = remote_options['protocol']
                self.cli_set(remote_base + ['protocol'], value=protocol)

            if 'source_address' in remote_options:
                source_address = remote_options['source_address']
                self.cli_set(remote_base + ['source-address', source_address])

                # check validate() - source address does not exist
                with self.assertRaises(ConfigSessionError):
                    self.cli_commit()
                self.cli_set(dummy_if_path + ['address', f'{source_address}/32'])

        self.cli_commit()

        config = read_file(RSYSLOG_CONF)
        for remote, remote_options in rhosts.items():
            config = get_config(f'# Remote syslog to {remote}')
            prifilt = []
            if 'facility' in remote_options:
                for facility, facility_options in remote_options['facility'].items():
                    level = facility_options['level']
                    if facility == 'all':
                        facility = '*'
                    prifilt.append(f'{facility}.{level}')

            prifilt.sort()
            prifilt = ','.join(prifilt)
            if not prifilt:
                # Skip test - as we do not render anything if no facility is set
                continue

            self.assertIn(f'if prifilt("{prifilt}") then {{', config)
            self.assertIn( '        type="omfwd"', config)
            self.assertIn(f'        target="{remote}"', config)

            port = default_port
            if 'port' in remote_options:
                port = remote_options['port']
            self.assertIn(f'port="{port}"', config)

            protocol = default_protocol
            if 'protocol' in remote_options:
                protocol = remote_options['protocol']
            self.assertIn(f'protocol="{protocol}"', config)

            if 'format' in remote_options:
                if 'include-timezone' in remote_options['format']:
                    self.assertIn( '        template="RSYSLOG_SyslogProtocol23Format"', config)

                if 'octet-counted' in remote_options['format']:
                    self.assertIn( '        TCP_Framing="octet-counted"', config)
                else:
                    self.assertIn( '        TCP_Framing="traditional"', config)

        # cleanup dummy interface
        self.cli_delete(dummy_if_path)

    def test_remote_tls(self):
        self._set_tls_certificates()

        rhosts = {
            '172.10.0.1': {
                'facility': {'all': {'level': 'debug'}},
                'port': '6514',
                'protocol': 'udp',
                'tls': {},
            },
            '172.10.0.2': {
                'facility': {'all': {'level': 'debug'}},
                'port': '6514',
                'protocol': 'udp',
                'tls': {
                    'auth-mode': 'anon',
                },
            },
            '172.10.0.3': {
                'facility': {'all': {'level': 'debug'}},
                'port': '6514',
                'protocol': 'tcp',
                'tls': {
                    'ca-certificate': ca_cert_name,
                    'auth-mode': 'certvalid',
                },
            },
            '172.10.0.4': {
                'facility': {'all': {'level': 'debug'}},
                'port': '6514',
                'protocol': 'tcp',
                'tls': {
                    'ca-certificate': ca_cert_name,
                    'certificate': client_cert_name,
                    'auth-mode': 'fingerprint',
                    'permitted-peers': 'SHA1:E1:DB:C4:FF:83:54:85:40:2D:56:E7:1A:C3:FF:70:22:0F:21:74:ED',
                },
            },
            '172.10.0.5': {
                'facility': {'all': {'level': 'debug'}},
                'port': '6514',
                'protocol': 'tcp',
                'tls': {
                    'ca-certificate': ca_cert_name,
                    'certificate': client_cert_name,
                    'auth-mode': 'name',
                    'permitted-peers': 'logs.example.com',
                },
            },
        }

        for remote, remote_options in rhosts.items():
            remote_base = base_path + ['remote', remote]

            if 'port' in remote_options:
                self.cli_set(remote_base + ['port'], value=remote_options['port'])

            if 'facility' in remote_options:
                for facility, facility_options in remote_options['facility'].items():
                    level = facility_options['level']
                    self.cli_set(
                        remote_base + ['facility', facility, 'level'], value=level
                    )

            if 'protocol' in remote_options:
                protocol = remote_options['protocol']
                self.cli_set(remote_base + ['protocol'], value=protocol)

            tls = remote_options['tls']
            if tls:
                for key, value in tls.items():
                    self.cli_set(remote_base + ['tls', key], value=value)
            else:
                self.cli_set(remote_base + ['tls'])

        self.cli_commit()

        read_file(RSYSLOG_CONF)
        for remote, remote_options in rhosts.items():
            with self.subTest(remote=remote):
                config = get_config(f'# Remote syslog to {remote}')

                if 'port' in remote_options:
                    port = remote_options['port']
                    self.assertIn(f'port="{port}"', config)

                self.assertIn('protocol="tcp"', config)
                self.assertIn('StreamDriver="ossl"', config)
                self.assertIn('StreamDriverMode="1"', config)

                tls = remote_options['tls']
                if 'ca-certificate' in tls:
                    self.assertIn(
                        f'StreamDriver.CAFile="{CERT_DIR}/{ca_cert_name}.pem"', config
                    )

                if 'certificate' in tls:
                    self.assertIn(
                        f'StreamDriver.CertFile="{CERT_DIR}/{client_cert_name}.pem"',
                        config,
                    )
                    self.assertIn(
                        f'StreamDriver.KeyFile="{CERT_DIR}/{client_cert_name}.key"',
                        config,
                    )

                if 'auth-mode' in tls:
                    value = tls['auth-mode']
                    auth_mode = value if value == 'anon' else f'x509/{value}'
                    self.assertIn(f'StreamDriverAuthMode="{auth_mode}"', config)

                if 'permitted-peers' in tls:
                    value = tls['permitted-peers']
                    self.assertIn(f'StreamDriverPermittedPeers="{value}"', config)

                if not tls:
                    self.assertIn(f'StreamDriverAuthMode="anon"', config)

    def test_vrf_source_address(self):
        rhosts = {
            '169.254.0.10': { },
            '169.254.0.11': {
                'vrf': {'name' : 'red', 'table' : '12321'},
                'source_address' : '169.254.0.11',
            },
            '169.254.0.12': {
                'vrf': {'name' : 'green', 'table' : '12322'},
                'source_address' : '169.254.0.12',
            },
            '169.254.0.13': {
                'vrf': {'name' : 'blue', 'table' : '12323'},
                'source_address' : '169.254.0.13',
            },
        }

        for remote, remote_options in rhosts.items():
            remote_base = base_path + ['remote', remote]
            self.cli_set(remote_base + ['facility', 'all'])

            vrf = None
            if 'vrf' in remote_options:
                vrf = remote_options['vrf']['name']
                self.cli_set(['vrf', 'name', vrf, 'table'],
                             value=remote_options['vrf']['table'])
                self.cli_set(remote_base + ['vrf'], value=vrf)

            if 'source_address' in remote_options:
                source_address = remote_options['source_address']
                self.cli_set(remote_base + ['source-address'],
                             value=source_address)

                idx = source_address.split('.')[-1]
                self.cli_set(['interfaces', 'dummy', f'dum{idx}', 'address'],
                             value=f'{source_address}/32')
                if vrf:
                    self.cli_set(['interfaces', 'dummy', f'dum{idx}', 'vrf'],
                                 value=vrf)

        self.cli_commit()

        for remote, remote_options in rhosts.items():
            config = get_config(f'# Remote syslog to {remote}')

            self.assertIn(f'target="{remote}"', config)
            if 'vrf' in remote_options:
                vrf = remote_options['vrf']['name']
                self.assertIn(f'Device="{vrf}"', config)

            if 'source_address' in remote_options:
                source_address = remote_options['source_address']
                self.assertIn(f'Address="{source_address}"', config)

        # Cleanup VRF/Dummy interfaces
        for remote, remote_options in rhosts.items():
            if 'vrf' in remote_options:
                vrf = remote_options['vrf']['name']
                self.cli_delete(['vrf', 'name', vrf])

            if 'source_address' in remote_options:
                source_address = remote_options['source_address']
                idx = source_address.split('.')[-1]
                self.cli_delete(['interfaces', 'dummy', f'dum{idx}'])

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
