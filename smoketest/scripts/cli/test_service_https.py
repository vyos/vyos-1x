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

import unittest

from base_vyostest_shim import VyOSUnitTestSHIM
from vyos.util import run

from vyos.configsession import ConfigSessionError

base_path = ['service', 'https']

class TestHTTPSService(VyOSUnitTestSHIM.TestCase):
    def setUp(self):
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        self.cli_delete(base_path)

    def tearDown(self):
        self.cli_delete(base_path)
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

<<<<<<< HEAD
        ret = run('sudo /usr/sbin/nginx -t')
        self.assertEqual(ret, 0)
=======
        nginx_config = read_file('/etc/nginx/sites-enabled/default')
        self.assertIn(f'listen {address}:{port} ssl;', nginx_config)
        self.assertIn(f'ssl_protocols TLSv1.2 TLSv1.3;', nginx_config)
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_certificate(self):
        self.cli_set(pki_base + ['certificate', 'test_https', 'certificate', cert_data.replace('\n','')])
        self.cli_set(pki_base + ['certificate', 'test_https', 'private', 'key', key_data.replace('\n','')])

        self.cli_set(base_path + ['certificates', 'certificate', 'test_https'])

        self.cli_commit()
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_api_missing_keys(self):
        self.cli_set(base_path + ['api'])
        self.assertRaises(ConfigSessionError, self.cli_commit)

    def test_api_incomplete_key(self):
        self.cli_set(base_path + ['api', 'keys', 'id', 'key-01'])
        self.assertRaises(ConfigSessionError, self.cli_commit)

    @ignore_warning(InsecureRequestWarning)
    def test_api_auth(self):
        vhost_id = 'example'
        address = '127.0.0.1'
        port = '443'
        name = 'localhost'

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

        # Check path config
        payload = {'data': '{"op": "showConfig", "path": ["system", "login"]}', 'key': f'{key}'}
        r = request('POST', url, verify=False, headers=headers, data=payload)
        response = r.json()
        vyos_user_exists = 'vyos' in response.get('data', {}).get('user', {})
        self.assertTrue(vyos_user_exists, "The 'vyos' user does not exist in the response.")

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

        r = request('POST', graphql_url, verify=False, headers=headers, json={'query': query_valid_key})
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

        r = request('POST', graphql_url, verify=False, headers=headers, json={'query': query_invalid_key})
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

        r = request('POST', graphql_url, verify=False, headers=headers, json={'query': query_no_key})
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
        r = request('POST', graphql_url, verify=False, headers=headers, json={'query': mutation})

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

        r = request('POST', graphql_url, verify=False, headers=headers, json={'query': query})
        success = r.json()['data']['ShowVersion']['success']
        self.assertTrue(success)

    @ignore_warning(InsecureRequestWarning)
    def test_api_show(self):
        address = '127.0.0.1'
        key = 'VyOS-key'
        url = f'https://{address}/show'
        headers = {}

        self.cli_set(base_path + ['api', 'keys', 'id', 'key-01', 'key', key])
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
        self.cli_commit()

        payload_path = [
            "interfaces",
            "dummy",
            f"{conf_interface}",
            "address",
            f"{conf_address}",
        ]

        payload = {'data': json.dumps({"op": "set", "path": payload_path}), 'key': key}

        r = request('POST', url, verify=False, headers=headers, data=payload)
        self.assertEqual(r.status_code, 200)

    @ignore_warning(InsecureRequestWarning)
    def test_api_config_file(self):
        address = '127.0.0.1'
        key = 'VyOS-key'
        url = f'https://{address}/config-file'
        headers = {}

        self.cli_set(base_path + ['api', 'keys', 'id', 'key-01', 'key', key])
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
        self.cli_commit()

        payload = {
            'data': '{"op": "reset", "path": ["ip", "arp", "table"]}',
            'key': f'{key}',
        }
        r = request('POST', url, verify=False, headers=headers, data=payload)
        self.assertEqual(r.status_code, 200)

>>>>>>> 8c450ea7f (https api: T5772: check if keys are configured)

if __name__ == '__main__':
    unittest.main(verbosity=5)
