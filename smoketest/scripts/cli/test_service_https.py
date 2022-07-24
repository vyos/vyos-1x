#!/usr/bin/env python3
#
# Copyright (C) 2019-2022 VyOS maintainers and contributors
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

import unittest

from requests import request
from urllib3.exceptions import InsecureRequestWarning

from base_vyostest_shim import VyOSUnitTestSHIM
from base_vyostest_shim import ignore_warning
from vyos.util import read_file
from vyos.util import run

base_path = ['service', 'https']
pki_base = ['pki']

cert_data = """
MIICFDCCAbugAwIBAgIUfMbIsB/ozMXijYgUYG80T1ry+mcwCgYIKoZIzj0EAwIw
WTELMAkGA1UEBhMCR0IxEzARBgNVBAgMClNvbWUtU3RhdGUxEjAQBgNVBAcMCVNv
bWUtQ2l0eTENMAsGA1UECgwEVnlPUzESMBAGA1UEAwwJVnlPUyBUZXN0MB4XDTIx
MDcyMDEyNDUxMloXDTI2MDcxOTEyNDUxMlowWTELMAkGA1UEBhMCR0IxEzARBgNV
BAgMClNvbWUtU3RhdGUxEjAQBgNVBAcMCVNvbWUtQ2l0eTENMAsGA1UECgwEVnlP
UzESMBAGA1UEAwwJVnlPUyBUZXN0MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE
01HrLcNttqq4/PtoMua8rMWEkOdBu7vP94xzDO7A8C92ls1v86eePy4QllKCzIw3
QxBIoCuH2peGRfWgPRdFsKNhMF8wDwYDVR0TAQH/BAUwAwEB/zAOBgNVHQ8BAf8E
BAMCAYYwHQYDVR0lBBYwFAYIKwYBBQUHAwIGCCsGAQUFBwMBMB0GA1UdDgQWBBSu
+JnU5ZC4mkuEpqg2+Mk4K79oeDAKBggqhkjOPQQDAgNHADBEAiBEFdzQ/Bc3Lftz
ngrY605UhA6UprHhAogKgROv7iR4QgIgEFUxTtW3xXJcnUPWhhUFhyZoqfn8dE93
+dm/LDnp7C0=
"""

key_data = """
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgPLpD0Ohhoq0g4nhx
2KMIuze7ucKUt/lBEB2wc03IxXyhRANCAATTUestw222qrj8+2gy5rysxYSQ50G7
u8/3jHMM7sDwL3aWzW/zp54/LhCWUoLMjDdDEEigK4fal4ZF9aA9F0Ww
"""

class TestHTTPSService(VyOSUnitTestSHIM.TestCase):
    def setUp(self):
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        self.cli_delete(base_path)
        self.cli_delete(pki_base)

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_delete(pki_base)
        self.cli_commit()

    def test_default(self):
        self.cli_set(base_path)
        self.cli_commit()

        ret = run('sudo /usr/sbin/nginx -t')
        self.assertEqual(ret, 0)

    def test_server_block(self):
        vhost_id = 'example'
        address = '0.0.0.0'
        port = '8443'
        name = 'example.org'

        test_path = base_path + ['virtual-host', vhost_id]

        self.cli_set(test_path + ['listen-address', address])
        self.cli_set(test_path + ['listen-port', port])
        self.cli_set(test_path + ['server-name', name])

        self.cli_commit()

        ret = run('sudo /usr/sbin/nginx -t')
        self.assertEqual(ret, 0)

        nginx_config = read_file('/etc/nginx/sites-enabled/default')
        self.assertIn(f'listen {address}:{port} ssl;', nginx_config)
        self.assertIn(f'ssl_protocols TLSv1.2 TLSv1.3;', nginx_config)

    def test_certificate(self):
        self.cli_set(pki_base + ['certificate', 'test_https', 'certificate', cert_data.replace('\n','')])
        self.cli_set(pki_base + ['certificate', 'test_https', 'private', 'key', key_data.replace('\n','')])

        self.cli_set(base_path + ['certificates', 'certificate', 'test_https'])

        self.cli_commit()

        ret = run('sudo /usr/sbin/nginx -t')
        self.assertEqual(ret, 0)

    @ignore_warning(InsecureRequestWarning)
    def test_api_auth(self):
        vhost_id = 'example'
        address = '127.0.0.1'
        port = '443'
        name = 'localhost'

        self.cli_set(base_path + ['api', 'socket'])
        key = 'MySuperSecretVyOS'
        self.cli_set(base_path + ['api', 'keys', 'id', 'key-01', 'key', key])

        test_path = base_path + ['virtual-host', vhost_id]
        self.cli_set(test_path + ['listen-address', address])
        self.cli_set(test_path + ['listen-port', port])
        self.cli_set(test_path + ['server-name', name])

        self.cli_commit()

        nginx_config = read_file('/etc/nginx/sites-enabled/default')
        self.assertIn(f'listen {address}:{port} ssl;', nginx_config)
        self.assertIn(f'ssl_protocols TLSv1.2 TLSv1.3;', nginx_config)

        url = f'https://{address}/retrieve'
        payload = {'data': '{"op": "showConfig", "path": []}', 'key': f'{key}'}
        headers = {}
        r = request('POST', url, verify=False, headers=headers, data=payload)
        # Must get HTTP code 200 on success
        self.assertEqual(r.status_code, 200)

        payload_invalid = {'data': '{"op": "showConfig", "path": []}', 'key': 'invalid'}
        r = request('POST', url, verify=False, headers=headers, data=payload_invalid)
        # Must get HTTP code 401 on invalid key (Unauthorized)
        self.assertEqual(r.status_code, 401)

        payload_no_key = {'data': '{"op": "showConfig", "path": []}'}
        r = request('POST', url, verify=False, headers=headers, data=payload_no_key)
        # Must get HTTP code 401 on missing key (Unauthorized)
        self.assertEqual(r.status_code, 401)

        # GraphQL auth test: a missing key will return status code 400, as
        # 'key' is a non-nullable field in the schema; an incorrect key is
        # caught by the resolver, and returns success 'False', so one must
        # check the return value.

        self.cli_set(base_path + ['api', 'gql'])
        self.cli_commit()

        gql_url = f'https://{address}/graphql'

        query_valid_key = f"""
        {{
          SystemStatus (data: {{key: "{key}"}}) {{
            success
            errors
            data {{
              result
            }}
          }}
        }}
        """

        r = request('POST', gql_url, verify=False, headers=headers, json={'query': query_valid_key})
        success = r.json()['data']['SystemStatus']['success']
        self.assertTrue(success)

        query_invalid_key = """
        {
          SystemStatus (data: {key: "invalid"}) {
            success
            errors
            data {
              result
            }
          }
        }
        """

        r = request('POST', gql_url, verify=False, headers=headers, json={'query': query_invalid_key})
        success = r.json()['data']['SystemStatus']['success']
        self.assertFalse(success)

        query_no_key = """
        {
          SystemStatus (data: {}) {
            success
            errors
            data {
              result
            }
          }
        }
        """

        r = request('POST', gql_url, verify=False, headers=headers, json={'query': query_no_key})
        self.assertEqual(r.status_code, 400)

if __name__ == '__main__':
    unittest.main(verbosity=2)
