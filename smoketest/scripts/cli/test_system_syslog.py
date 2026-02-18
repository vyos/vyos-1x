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
base_logs_path = ['system', 'logs']
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
        self.cli_delete(base_logs_path)
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

    def _set_facilities(self, base, facility_map):
        for facility, facility_options in facility_map.items():
            level = facility_options['level']
            self.cli_set(base + ['facility', facility, 'level'], value=level)

    # Build prifilt selector strings the same way as rsyslog.conf.j2, e.g.
    # "auth.info,*.notice;auth.none" when specific facilities coexist with "all".
    def _prifilt_selectors(self, facility_map):
        keys = sorted(facility_map)
        specific = []
        for facility in keys:
            if facility != 'all':
                specific.append(facility)

        selectors = []
        for facility in keys:
            opts = facility_map[facility]
            level = opts['level'].replace('all', 'debug')
            if facility == 'all':
                sel = f'*.{level}'
                for sf in specific:
                    sel += f';{sf}.none'
            else:
                sel = f'{facility}.{level}'
            selectors.append(sel)

        prifilt = ','.join(selectors)
        self._assert_prifilt_sane(prifilt, facility_map)
        return prifilt

    def _assert_prifilt_sane(self, prifilt, facility_map):
        has_all = 'all' in facility_map
        specific_facilities = sorted(f for f in facility_map if f != 'all')
        self.assertTrue(prifilt)
        self.assertNotIn(' ', prifilt)
        parts = prifilt.split(',')
        self.assertTrue(all(parts))
        wildcard_parts = [p for p in parts if p.startswith('*.')]
        if has_all:
            self.assertEqual(len(wildcard_parts), 1)
            wildcard = wildcard_parts[0]
            if specific_facilities:
                base, *exclusions = wildcard.split(';')
                self.assertTrue(base.startswith('*.'))
                expected = {f'{fac}.none' for fac in specific_facilities}
                self.assertEqual(set(exclusions), expected)
            else:
                self.assertNotIn(';', wildcard)
        else:
            self.assertEqual(len(wildcard_parts), 0)
            self.assertNotIn(';', prifilt)

        for part in parts:
            if ';' in part:
                base, *exclusions = part.split(';')
                self.assertTrue(base.startswith('*.'))
                self.assertNotIn('*.none', base)
                for ex in exclusions:
                    self.assertTrue(ex.endswith('.none'))
                    self.assertFalse(ex.startswith('*.'))
                    self.assertNotIn(',', ex)
            else:
                if part.startswith('*.'):
                    self.assertTrue(has_all)
                    continue
                self.assertEqual(part.count('.'), 1)
                self.assertFalse(part.startswith('*.'))

    def test_console(self):
        facility = {
            'all': {'level': 'warning'},
        }
        self._set_facilities(base_path + ['console'], facility)
        self.cli_commit()

        rsyslog_conf = get_config()
        expected_prifilt = self._prifilt_selectors(facility)
        self.assertIn(f'if prifilt("{expected_prifilt}") then {{', rsyslog_conf)
        self.assertIn('action(type="omfile" file="/dev/console")', rsyslog_conf)

        self.cli_delete(base_path + ['console'])
        facility = {
            'auth': {'level': 'info'},
            'kern': {'level': 'debug'},
        }
        self._set_facilities(base_path + ['console'], facility)
        self.cli_commit()

        rsyslog_conf = get_config()
        expected_prifilt = self._prifilt_selectors(facility)
        self.assertIn(f'if prifilt("{expected_prifilt}") then {{', rsyslog_conf)
        self.assertIn('action(type="omfile" file="/dev/console")', rsyslog_conf)

        facility['all'] = {'level': 'notice'}
        self._set_facilities(base_path + ['console'], facility)
        self.cli_commit()

        rsyslog_conf = get_config()
        expected_prifilt = self._prifilt_selectors(facility)
        self.assertIn(f'if prifilt("{expected_prifilt}") then {{', rsyslog_conf)
        self.assertIn('action(type="omfile" file="/dev/console")', rsyslog_conf)

    def test_basic(self):
        hostname = 'vyos123'
        domain_name = 'example.local'
        default_marker_interval = default_value(base_path + ['marker', 'interval'])
        default_rsyslog_max_size = default_value(
            base_logs_path + ['logrotate', 'messages', 'max-size']
        )

        facility = {
            'auth': {'level': 'info'},
            'kern': {'level': 'debug'},
            'all':  {'level': 'notice'},
        }

        self.cli_set(['system', 'host-name'], value=hostname)
        self.cli_set(['system', 'domain-name'], value=domain_name)
        self.cli_set(base_path + ['preserve-fqdn'])

        self._set_facilities(base_path + ['local'], facility)

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
        expected_prifilt = self._prifilt_selectors(facility)
        self.assertIn(f'if prifilt("{expected_prifilt}") then {{', config)
        self.assertIn( '    action(', config)
        self.assertIn( '        type="omfile"', config)
        self.assertIn( '        file="/var/log/messages"', config)
        size_limit = int(default_rsyslog_max_size) * 1024 * 1024
        self.assertIn(f'        rotation.sizeLimit="{size_limit}"', config)
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
                self._set_facilities(remote_base, remote_options['facility'])

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
            prifilt = ''
            if 'facility' in remote_options:
                prifilt = self._prifilt_selectors(remote_options['facility'])
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
                'protocol': 'tcp',
                'tls': {},
            },
            '172.10.0.2': {
                'facility': {'all': {'level': 'debug'}},
                'port': '6514',
                'protocol': 'tcp',
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
                    'permitted-peer': [
                        'SHA1:E1:DB:C4:FF:83:54:85:40:2D:56:E7:1A:C3:FF:70:22:0F:21:74:ED',
                        ' SHA1:FF:70:22:0F:21:74:ED:54:85:40:2D:56:E7:1A:C3:E1:DB:C4:FF:83 ',
                    ],
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
                    'permitted-peer': [
                        'logs.example.com',
                        '   ',
                    ],
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
                    if type(value) is list:
                        values = value
                        for value in values:
                            self.cli_set(remote_base + ['tls', key], value=value)
                    else:
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

                if 'permitted-peer' in tls:
                    values = tls['permitted-peer']
                    value = ','.join([v.strip() for v in values if v.strip()])
                    self.assertIn(f'StreamDriverPermittedPeers="{value}"', config)

                if not tls:
                    self.assertIn('StreamDriverAuthMode="anon"', config)

    def test_remote_tls_protocol_udp(self):
        remote_base = base_path + ['remote', '172.11.0.1']
        self.cli_set(remote_base + ['port'], value='6514')
        self.cli_set(remote_base + ['facility', 'all', 'level'], value='debug')
        self.cli_set(remote_base + ['protocol'], value='udp')
        self.cli_set(remote_base + ['tls'])

        err_msg = "TLS is enabled for remote \"172.11.0.1\", but protocol is set to UDP"
        with self.assertRaisesRegex(ConfigSessionError, err_msg):
            self.cli_commit()

        self.cli_set(base_path + ['remote', '172.11.0.1', 'protocol'], value='tcp')
        self.cli_commit()

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
