#!/usr/bin/env python3
#
# Copyright (C) 2019-2024 VyOS maintainers and contributors
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
import json

from requests import request
from urllib3.exceptions import InsecureRequestWarning
from time import sleep

from base_vyostest_shim import VyOSUnitTestSHIM
from base_vyostest_shim import ignore_warning
from vyos.utils.file import read_file
from vyos.utils.file import write_file
from vyos.utils.process import call
from vyos.utils.process import process_named_running
from vyos.xml_ref import default_value

from vyos.configsession import ConfigSessionError

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

dh_1024 = """
MIGHAoGBAM3nvMkHGi/xmRs8cYg4pcl5sAanxel9EM+1XobVhUViXw8JvlmSEVOj
n2aXUifc4SEs3WDzVPRC8O8qQWjvErpTq/HOgt3aqBCabMgvflmt706XP0KiqnpW
EyvNiI27J3wBUzEXLIS110MxPAX5Tcug974PecFcOxn1RWrbWcx/AgEC
"""

dh_2048 = """
MIIBCAKCAQEA1mld/V7WnxxRinkOlhx/BoZkRELtIUQFYxyARBqYk4C5G3YnZNNu
zjaGyPnfIKHu8SIUH85OecM+5/co9nYlcUJuph2tbR6qNgPw7LOKIhf27u7WhvJk
iVsJhwZiWmvvMV4jTParNEI2svoooMyhHXzeweYsg6YtgLVmwiwKj3XP3gRH2i3B
Mq8CDS7X6xaKvjfeMPZBFqOM5nb6HhsbaAUyiZxrfipLvXxtnbzd/eJUQVfVdxM3
pn0i+QrO2tuNAzX7GoPc9pefrbb5xJmGS50G0uqsR59+7LhYmyZSBASA0lxTEW9t
kv/0LPvaYTY57WL7hBeqqHy/WPZHPzDI3wIBAg==
"""
# to test load config via HTTP URL
nginx_tmp_site = '/etc/nginx/sites-enabled/smoketest'
nginx_conf_smoketest = """
server {
    listen 8000;
    server_name localhost;

    root /tmp;

    index index.html;

    location / {
        try_files $uri $uri/ =404;
        autoindex on;
    }
}
"""

PROCESS_NAME = 'nginx'


class TestHTTPSService(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestHTTPSService, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)
        cls.cli_delete(cls, pki_base)

    @classmethod
    def tearDownClass(cls):
        super(TestHTTPSService, cls).tearDownClass()
        call(f'sudo rm -f {nginx_tmp_site}')

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_delete(pki_base)
        self.cli_commit()

        # Check for stopped  process
        self.assertFalse(process_named_running(PROCESS_NAME))

    def test_certificate(self):
        cert_name = 'test_https'
        dh_name = 'dh-test'

        self.cli_set(base_path + ['certificates', 'certificate', cert_name])
        # verify() - certificates do not exist (yet)
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(
            pki_base
            + ['certificate', cert_name, 'certificate', cert_data.replace('\n', '')]
        )
        self.cli_set(
            pki_base
            + ['certificate', cert_name, 'private', 'key', key_data.replace('\n', '')]
        )

        self.cli_set(base_path + ['certificates', 'dh-params', dh_name])
        # verify() - dh-params do not exist (yet)
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(
            pki_base + ['dh', dh_name, 'parameters', dh_1024.replace('\n', '')]
        )
        # verify() - dh-param minimum length is 2048 bit
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(
            pki_base + ['dh', dh_name, 'parameters', dh_2048.replace('\n', '')]
        )

        self.cli_commit()
        self.assertTrue(process_named_running(PROCESS_NAME))
        self.debug = False

    def test_api_missing_keys(self):
        self.cli_set(base_path + ['api'])
        self.assertRaises(ConfigSessionError, self.cli_commit)

    def test_api_incomplete_key(self):
        self.cli_set(base_path + ['api', 'keys', 'id', 'key-01'])
        self.assertRaises(ConfigSessionError, self.cli_commit)

    @ignore_warning(InsecureRequestWarning)
    def test_api_auth(self):
        address = '127.0.0.1'
        port = default_value(base_path + ['port'])

        key = 'MySuperSecretVyOS'
        self.cli_set(base_path + ['api', 'keys', 'id', 'key-01', 'key', key])

        self.cli_set(base_path + ['api', 'rest'])

        self.cli_set(base_path + ['listen-address', address])

        self.cli_commit()

        nginx_config = read_file('/etc/nginx/sites-enabled/default')
        self.assertIn(f'listen {address}:{port} ssl;', nginx_config)
        self.assertIn('ssl_protocols TLSv1.2 TLSv1.3;', nginx_config)  # default

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

        # Check path config
        payload = {
            'data': '{"op": "showConfig", "path": ["system", "login"]}',
            'key': f'{key}',
        }
        r = request('POST', url, verify=False, headers=headers, data=payload)
        response = r.json()
        vyos_user_exists = 'vyos' in response.get('data', {}).get('user', {})
        self.assertTrue(
            vyos_user_exists, "The 'vyos' user does not exist in the response."
        )

        # GraphQL auth test: a missing key will return status code 400, as
        # 'key' is a non-nullable field in the schema; an incorrect key is
        # caught by the resolver, and returns success 'False', so one must
        # check the return value.

        self.cli_set(base_path + ['api', 'graphql'])
        self.cli_commit()

        graphql_url = f'https://{address}/graphql'

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

        r = request(
            'POST',
            graphql_url,
            verify=False,
            headers=headers,
            json={'query': query_valid_key},
        )
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

        r = request(
            'POST',
            graphql_url,
            verify=False,
            headers=headers,
            json={'query': query_invalid_key},
        )
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

        r = request(
            'POST',
            graphql_url,
            verify=False,
            headers=headers,
            json={'query': query_no_key},
        )
        success = r.json()['data']['SystemStatus']['success']
        self.assertFalse(success)

        # GraphQL token authentication test: request token; pass in header
        # of query.

        self.cli_set(base_path + ['api', 'graphql', 'authentication', 'type', 'token'])
        self.cli_commit()

        mutation = """
        mutation {
          AuthToken (data: {username: "vyos", password: "vyos"}) {
            success
            errors
            data {
              result
            }
          }
        }
        """
        r = request(
            'POST', graphql_url, verify=False, headers=headers, json={'query': mutation}
        )

        token = r.json()['data']['AuthToken']['data']['result']['token']

        headers = {'Authorization': f'Bearer {token}'}

        query = """
        {
          ShowVersion (data: {}) {
            success
            errors
            op_mode_error {
              name
              message
              vyos_code
            }
            data {
              result
            }
          }
        }
        """

        r = request(
            'POST', graphql_url, verify=False, headers=headers, json={'query': query}
        )
        success = r.json()['data']['ShowVersion']['success']
        self.assertTrue(success)

    @ignore_warning(InsecureRequestWarning)
    def test_api_add_delete(self):
        address = '127.0.0.1'
        key = 'VyOS-key'
        url = f'https://{address}/retrieve'
        payload = {'data': '{"op": "showConfig", "path": []}', 'key': f'{key}'}
        headers = {}

        self.cli_set(base_path)
        self.cli_commit()

        r = request('POST', url, verify=False, headers=headers, data=payload)
        # api not configured; expect 503
        self.assertEqual(r.status_code, 503)

        self.cli_set(base_path + ['api', 'keys', 'id', 'key-01', 'key', key])
        self.cli_set(base_path + ['api', 'rest'])
        self.cli_commit()
        sleep(2)

        r = request('POST', url, verify=False, headers=headers, data=payload)
        # api configured; expect 200
        self.assertEqual(r.status_code, 200)

        self.cli_delete(base_path + ['api'])
        self.cli_commit()

        r = request('POST', url, verify=False, headers=headers, data=payload)
        # api deleted; expect 503
        self.assertEqual(r.status_code, 503)

    @ignore_warning(InsecureRequestWarning)
    def test_api_show(self):
        address = '127.0.0.1'
        key = 'VyOS-key'
        url = f'https://{address}/show'
        headers = {}

        self.cli_set(base_path + ['api', 'keys', 'id', 'key-01', 'key', key])
        self.cli_set(base_path + ['api', 'rest'])
        self.cli_commit()

        payload = {
            'data': '{"op": "show", "path": ["system", "image"]}',
            'key': f'{key}',
        }
        r = request('POST', url, verify=False, headers=headers, data=payload)
        self.assertEqual(r.status_code, 200)

    @ignore_warning(InsecureRequestWarning)
    def test_api_generate(self):
        address = '127.0.0.1'
        key = 'VyOS-key'
        url = f'https://{address}/generate'
        headers = {}

        self.cli_set(base_path + ['api', 'keys', 'id', 'key-01', 'key', key])
        self.cli_set(base_path + ['api', 'rest'])
        self.cli_commit()

        payload = {
            'data': '{"op": "generate", "path": ["macsec", "mka", "cak", "gcm-aes-256"]}',
            'key': f'{key}',
        }
        r = request('POST', url, verify=False, headers=headers, data=payload)
        self.assertEqual(r.status_code, 200)

    @ignore_warning(InsecureRequestWarning)
    def test_api_configure(self):
        address = '127.0.0.1'
        key = 'VyOS-key'
        url = f'https://{address}/configure'
        headers = {}
        conf_interface = 'dum0'
        conf_address = '192.0.2.44/32'

        self.cli_set(base_path + ['api', 'keys', 'id', 'key-01', 'key', key])
        self.cli_set(base_path + ['api', 'rest'])
        self.cli_commit()

        payload_path = [
            'interfaces',
            'dummy',
            f'{conf_interface}',
            'address',
            f'{conf_address}',
        ]

        payload = {'data': json.dumps({'op': 'set', 'path': payload_path}), 'key': key}

        r = request('POST', url, verify=False, headers=headers, data=payload)
        self.assertEqual(r.status_code, 200)

    @ignore_warning(InsecureRequestWarning)
    def test_api_config_file(self):
        address = '127.0.0.1'
        key = 'VyOS-key'
        url = f'https://{address}/config-file'
        headers = {}

        self.cli_set(base_path + ['api', 'keys', 'id', 'key-01', 'key', key])
        self.cli_set(base_path + ['api', 'rest'])
        self.cli_commit()

        payload = {
            'data': '{"op": "save"}',
            'key': f'{key}',
        }
        r = request('POST', url, verify=False, headers=headers, data=payload)
        self.assertEqual(r.status_code, 200)

    @ignore_warning(InsecureRequestWarning)
    def test_api_reset(self):
        address = '127.0.0.1'
        key = 'VyOS-key'
        url = f'https://{address}/reset'
        headers = {}

        self.cli_set(base_path + ['api', 'keys', 'id', 'key-01', 'key', key])
        self.cli_set(base_path + ['api', 'rest'])
        self.cli_commit()

        payload = {
            'data': '{"op": "reset", "path": ["ip", "arp", "table"]}',
            'key': f'{key}',
        }
        r = request('POST', url, verify=False, headers=headers, data=payload)
        self.assertEqual(r.status_code, 200)

    @ignore_warning(InsecureRequestWarning)
    def test_api_image(self):
        address = '127.0.0.1'
        key = 'VyOS-key'
        url = f'https://{address}/image'
        headers = {}

        self.cli_set(base_path + ['api', 'keys', 'id', 'key-01', 'key', key])
        self.cli_set(base_path + ['api', 'rest'])
        self.cli_commit()

        payload = {
            'data': '{"op": "add"}',
            'key': f'{key}',
        }
        r = request('POST', url, verify=False, headers=headers, data=payload)
        self.assertEqual(r.status_code, 400)
        self.assertIn('Missing required field "url"', r.json().get('error'))

        payload = {
            'data': '{"op": "delete"}',
            'key': f'{key}',
        }
        r = request('POST', url, verify=False, headers=headers, data=payload)
        self.assertEqual(r.status_code, 400)
        self.assertIn('Missing required field "name"', r.json().get('error'))

        payload = {
            'data': '{"op": "set_default"}',
            'key': f'{key}',
        }
        r = request('POST', url, verify=False, headers=headers, data=payload)
        self.assertEqual(r.status_code, 400)
        self.assertIn('Missing required field "name"', r.json().get('error'))

        payload = {
            'data': '{"op": "show"}',
            'key': f'{key}',
        }
        r = request('POST', url, verify=False, headers=headers, data=payload)
        self.assertEqual(r.status_code, 200)

    @ignore_warning(InsecureRequestWarning)
    def test_api_config_file_load_http(self):
        # Test load config from HTTP URL
        address = '127.0.0.1'
        key = 'VyOS-key'
        url = f'https://{address}/config-file'
        url_config = f'https://{address}/configure'
        headers = {}

        self.cli_set(base_path + ['api', 'keys', 'id', 'key-01', 'key', key])
        self.cli_set(base_path + ['api', 'rest'])
        self.cli_commit()

        # load config via HTTP requires nginx config
        call(f'sudo touch {nginx_tmp_site}')
        call(f'sudo chmod 666 {nginx_tmp_site}')
        write_file(nginx_tmp_site, nginx_conf_smoketest)
        call('sudo systemctl reload nginx')

        # save config
        payload = {
            'data': '{"op": "save", "file": "/tmp/tmp-config.boot"}',
            'key': f'{key}',
        }
        r = request('POST', url, verify=False, headers=headers, data=payload)
        self.assertEqual(r.status_code, 200)

        # change config
        payload = {
            'data': '{"op": "set", "path": ["interfaces", "dummy", "dum1", "address", "192.0.2.31/32"]}',
            'key': f'{key}',
        }
        r = request('POST', url_config, verify=False, headers=headers, data=payload)
        self.assertEqual(r.status_code, 200)

        # load config from URL
        payload = {
            'data': '{"op": "load", "file": "http://localhost:8000/tmp-config.boot"}',
            'key': f'{key}',
        }
        r = request('POST', url, verify=False, headers=headers, data=payload)
        self.assertEqual(r.status_code, 200)

        # cleanup tmp nginx conf
        call(f'sudo rm -f {nginx_tmp_site}')
        call('sudo systemctl reload nginx')


if __name__ == '__main__':
    unittest.main(verbosity=5)
