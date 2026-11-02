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

from vyos.utils.process import cmdl
from vyos.utils.process import process_named_running
from vyos.utils.file import file_permissions
from vyos.utils.file import read_file

PROCESS_NAME = 'telegraf'
TELEGRAF_CONF = '/run/telegraf/telegraf.conf'
TELEGRAF_ENV = '/run/telegraf/telegraf.env'
TELEGRAF_CERT_DIR = '/run/telegraf/certs'
base_path = ['service', 'monitoring', 'telegraf']
pki_base = ['pki']
prometheus_base_path = ['service', 'monitoring', 'prometheus']
org = 'log@in.local'
token = 'GuRJc12tIzfjnYdKRAIYbxdWd2aTpOT9PVYNddzDnFV4HkAcD7u7-kndTFXjGuXzJN6TTxmrvPODB4mnFcseDV=='
port = '8888'
url = 'https://foo.local'
bucket = 'main'
inputs = ['cpu', 'disk', 'mem', 'net', 'system', 'kernel', 'interrupts', 'syslog']

ca_cert_name = 'telegraf_ca'
ca_cert = """
MIIBqTCCAU+gAwIBAgIQGYypTyo8m8+//pir9JcJ/DAKBggqhkjOPQQDAjAgMQ8w
DQYDVQQKEwZ0ZXN0ZXIxDTALBgNVBAMTBHRlc3QwIBcNMjYxMTAyMDgzODM4WhgP
MjEyNjEwMDkwOTM4MzhaMCAxDzANBgNVBAoTBnRlc3RlcjENMAsGA1UEAxMEdGVz
dDBZMBMGByqGSM49AgEGCCqGSM49AwEHA0IABPljKF03H5AEFZxlS6/FUoPUpGxB
vi6fk6vg6fheYJ18K0ktIsymAc3bF90ixkRMGjiDlmbrIXaWQ6JYWGW5XGejaTBn
MA4GA1UdDwEB/wQEAwICpDATBgNVHSUEDDAKBggrBgEFBQcDATAPBgNVHRMBAf8E
BTADAQH/MB0GA1UdDgQWBBTbpL33CaFEiBDFWEpthItzZRSI2TAQBgNVHREECTAH
ggVsb2NhbDAKBggqhkjOPQQDAgNIADBFAiBDPInnpAXq3GpTUWx0zW8CeQArRE/M
K0G/m43nt0UVAwIhAPIE7I8tvkq0feemYOoXh5Cfz4fpSK+VrCh7p5Vs92WZ
"""

client_cert_name = 'telegraf_client'
client_cert = """
MIIBqDCCAU6gAwIBAgIRAKXAefczQUevhL4DnMMK3RQwCgYIKoZIzj0EAwIwKzEP
MA0GA1UEChMGdGVzdGVyMRgwFgYDVQQDEw9sb2dzLnZ5b3MubG9jYWwwIBcNMjYx
MTAyMDgzOTEwWhgPMjA3NjEwMjAwOTM5MTBaMCsxDzANBgNVBAoTBnRlc3RlcjEY
MBYGA1UEAxMPbG9ncy52eW9zLmxvY2FsMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcD
QgAEjAcVO/xkZZ0l5TKVvBEcAXFf4Rhtq7LXC/sQAKCmA97vRd8WPASmFFQQbHWd
sXKWVmdRJe7vATajAgC3sR9Tr6NRME8wDgYDVR0PAQH/BAQDAgWgMBMGA1UdJQQM
MAoGCCsGAQUFBwMBMAwGA1UdEwEB/wQCMAAwGgYDVR0RBBMwEYIPbG9ncy52eW9z
LmxvY2FsMAoGCCqGSM49BAMCA0gAMEUCIG9Efm57FEBSkDSP0rz6oliTe1MLEYG1
leRFR8qdpjSoAiEAhkFJc4iA9km1rnz1rXG1OaALsQhVzwaaH4Zc6oZirl8=
"""

client_cert_key = """
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQg3RyGlV3TOLgwEWso
PzavYp12RrGdbhxVDTl5b9+LDtWhRANCAASMBxU7/GRlnSXlMpW8ERwBcV/hGG2r
stcL+xAAoKYD3u9F3xY8BKYUVBBsdZ2xcpZWZ1El7u8BNqMCALexH1Ov
"""

class TestMonitoringTelegraf(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestMonitoringTelegraf, cls).setUpClass()
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))
        self.cli_delete(base_path)
        self.cli_commit()
        # Check for not longer running process
        self.assertFalse(process_named_running(PROCESS_NAME))
        # always forward to base class
        super().tearDown()

    def basic_influxdb_setup(self):
        # Basic setup so config file gets made
        self.cli_set(base_path + ['influxdb', 'authentication', 'organization', org])
        self.cli_set(base_path + ['influxdb', 'authentication', 'token', token])
        self.cli_set(base_path + ['influxdb', 'port', port])
        self.cli_set(base_path + ['influxdb', 'url', url])

        # commit changes
        self.cli_commit()

    def test_01_basic_config(self):
        self.basic_influxdb_setup()

        config = read_file(TELEGRAF_CONF)

        # Check telegraf config
        self.assertIn(f'organization = "{org}"', config)
        self.assertIn(f'  token = "$INFLUX_TOKEN"', config)
        self.assertIn(f'urls = ["{url}:{port}"]', config)
        self.assertIn(f'bucket = "{bucket}"', config)
        self.assertIn(f'[[inputs.exec]]', config)

        for input in inputs:
            self.assertIn(input, config)

    def test_02_loki(self):
        label = 'r123'
        loki_url = 'http://localhost'
        port = '3100'
        loki_username = 'VyOS'
        loki_password = 'PassW0Rd_VyOS'

        self.cli_set(base_path + ['loki', 'url', loki_url])
        self.cli_set(base_path + ['loki', 'port', port])
        self.cli_set(base_path + ['loki', 'metric-name-label', label])

        self.cli_set(base_path + ['loki', 'authentication', 'username', loki_username])
        # password not set
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(base_path + ['loki', 'authentication', 'password', loki_password])

        # commit changes
        self.cli_commit()

        config = read_file(TELEGRAF_CONF)
        self.assertIn(f'[[outputs.loki]]', config)
        self.assertIn(f'domain = "{loki_url}:{port}"', config)
        self.assertIn(f'metric_name_label = "{label}"', config)
        self.assertIn(f'username = "{loki_username}"', config)
        self.assertIn(f'password = "{loki_password}"', config)

    def test_03_global_tags(self):
        tags = {
            'role': 'edge-router',
            'site-id': 'fra01',
        }

        for tag, value in tags.items():
            self.cli_set(base_path + ['global-tag', tag, 'value', value])
        self.cli_set(base_path + ['prometheus-client'])

        # commit changes
        self.cli_commit()

        config = read_file(TELEGRAF_CONF)

        self.assertIn(f'[global_tags]', config)
        for tag, value in tags.items():
            self.assertIn(f'{tag} = "{value}"', config)

    def test_04_global_tag_no_value(self):
        self.cli_set(base_path + ['prometheus-client'])
        self.cli_set(base_path + ['global-tag', 'incomplete-tag'])
        # value not set - commit must fail
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(base_path + ['global-tag', 'incomplete-tag'])
        self.cli_commit()

    def test_05_frr_metrics_requires_frr_exporter(self):
        # frr-metrics can not be enabled unless the Prometheus frr-exporter
        # is configured
        self.cli_set(base_path + ['prometheus-client'])
        self.cli_set(base_path + ['frr-metrics'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(base_path + ['frr-metrics'])
        # commit again to leave a valid, running config for tearDown()
        self.cli_commit()

    def test_06_frr_metrics(self):
        frr_exporter_port = '9342'
        self.cli_set(base_path + ['prometheus-client'])
        self.cli_set(prometheus_base_path + ['frr-exporter'])
        self.cli_set(base_path + ['frr-metrics'])

        # commit changes
        self.cli_commit()

        config = read_file(TELEGRAF_CONF)
        self.assertIn(f'[[inputs.prometheus]]', config)
        self.assertIn(
            f'urls = ["http://127.0.0.1:{frr_exporter_port}/metrics"]', config
        )
        self.assertIn(f'metric_version = 2', config)
        self.assertIn(f'name_override = "frr"', config)

        # frr-metrics must be removed together with frr-exporter, otherwise
        # the next commit fails verification and leaves telegraf stopped
        self.cli_delete(base_path + ['frr-metrics'])
        self.cli_delete(prometheus_base_path)
        self.cli_commit()

    def test_07_frr_metrics_tracks_frr_exporter_changes(self):
        # T9260 regression test: changing frr-exporter's listen-address or
        # port alone - without touching "service monitoring telegraf" at
        # all - must still refresh the scrape URL Telegraf renders, since
        # Telegraf's own conf-mode script is not otherwise re-run when only
        # frr-exporter's subtree changes
        new_listen_address = '127.0.0.2'
        new_port = '9999'

        self.cli_set(base_path + ['prometheus-client'])
        self.cli_set(prometheus_base_path + ['frr-exporter'])
        self.cli_set(base_path + ['frr-metrics'])
        self.cli_commit()

        config = read_file(TELEGRAF_CONF)
        self.assertIn('urls = ["http://127.0.0.1:9342/metrics"]', config)

        # Only touch the Prometheus frr-exporter subtree
        self.cli_set(
            prometheus_base_path
            + ['frr-exporter', 'listen-address', new_listen_address]
        )
        self.cli_set(prometheus_base_path + ['frr-exporter', 'port', new_port])
        self.cli_commit()

        config = read_file(TELEGRAF_CONF)
        self.assertIn(
            f'urls = ["http://{new_listen_address}:{new_port}/metrics"]', config
        )

        self.cli_delete(base_path + ['frr-metrics'])
        self.cli_delete(prometheus_base_path)
        self.cli_commit()

    def test_08_agent_configuration(self):
        """
        Testing for agent configuration values
        Includes good values and bad values
        """
        # Make sure config file is made
        self.basic_influxdb_setup()

        config = read_file(TELEGRAF_CONF)

        # Check default values are correct
        self.assertIn("collection_jitter = \"5s\"", config)
        self.assertIn("debug = false", config)
        self.assertIn("flush_interval = \"15s\"", config)
        self.assertIn("flush_jitter = \"0s\"", config)
        self.assertIn("interval = \"15s\"", config)

        # Set new values
        self.cli_set(base_path + ['agent', 'collection-jitter', "1s"])
        self.cli_set(base_path + ['agent', 'debug'])
        self.cli_set(base_path + ['agent', 'flush-interval', "2s"])
        self.cli_set(base_path + ['agent', 'flush-jitter', "3s"])
        self.cli_set(base_path + ['agent', 'interval', "4s"])

        # Commit new values
        self.cli_commit()

        # Check values changed
        config = read_file(TELEGRAF_CONF)
        self.assertIn("collection_jitter = \"1s\"", config)
        self.assertIn("debug = true", config)
        self.assertIn("flush_interval = \"2s\"", config)
        self.assertIn("flush_jitter = \"3s\"", config)
        self.assertIn("interval = \"4s\"", config)

        # Check bad values error correctly
        with self.assertRaises(ConfigSessionError):
            self.cli_set(base_path + ['agent', 'collection-jitter', "1units"])

        with self.assertRaises(ConfigSessionError):
            self.cli_set(base_path + ['agent', 'flush-interval', "2units"])

        with self.assertRaises(ConfigSessionError):
            self.cli_set(base_path + ['agent', 'flush-jitter', "3units"])

        with self.assertRaises(ConfigSessionError):
            self.cli_set(base_path + ['agent', 'interval', "4units"])

        # Make sure 0 is not allowed
        with self.assertRaises(ConfigSessionError):
            self.cli_set(base_path + ['agent', 'interval', "0s"])

        with self.assertRaises(ConfigSessionError):
            self.cli_set(base_path + ['agent', 'flush-interval', "0s"])

        # Make sure max value is not broken
        max_s = 9223372037

        self.cli_set(base_path + ['agent', 'collection-jitter', f"{max_s}s"])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_discard()

        self.cli_set(base_path + ['agent', 'flush-interval', f"{max_s}s"])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_discard()

        self.cli_set(base_path + ['agent', 'flush-jitter', f"{max_s}s"])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_discard()

        self.cli_set(base_path + ['agent', 'interval', f"{max_s}s"])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_discard()

    def test_09_influxdb_token(self):
        new_token = 'A' * 86 + '=='

        self.basic_influxdb_setup()

        # Token is only readable by root and not exposed by systemd
        self.assertEqual(read_file(TELEGRAF_ENV, sudo=True), f'INFLUX_TOKEN={token}')
        self.assertEqual(file_permissions(TELEGRAF_ENV), '0600')
        self.assertNotIn(
            token, cmdl(['systemctl', 'show', '-p', 'Environment', 'telegraf.service'])
        )

        pid = process_named_running(PROCESS_NAME)

        # A reload keeps the old environment, a new token needs a restart
        self.cli_set(base_path + ['influxdb', 'authentication', 'token', new_token])
        self.cli_commit()

        new_pid = process_named_running(PROCESS_NAME, timeout=10)
        self.assertNotEqual(pid, new_pid)
        environ = read_file(f'/proc/{new_pid}/environ', sudo=True)
        self.assertIn(f'INFLUX_TOKEN={new_token}', environ)

    def test_10_azure_data_explorer(self):
        database = 'vyos_metrics'
        client_id = 'vyos-client'
        client_secret = 'vyos-secret'
        new_client_secret = 'vyos-new-secret'
        tenant_id = 'vyos-tenant'
        azure_path = base_path + ['azure-data-explorer']

        self.cli_set(azure_path + ['url', url])
        self.cli_set(azure_path + ['database', database])
        self.cli_set(azure_path + ['authentication', 'client-id', client_id])
        self.cli_set(azure_path + ['authentication', 'client-secret', client_secret])
        self.cli_set(azure_path + ['authentication', 'tenant-id', tenant_id])
        self.cli_commit()

        config = read_file(TELEGRAF_CONF)
        self.assertIn('[[outputs.azure_data_explorer]]', config)
        self.assertIn(f'endpoint_url = "{url}"', config)
        self.assertIn(f'database = "{database}"', config)
        self.assertIn('metrics_grouping_type = "TablePerMetric"', config)
        # Credentials must never be rendered into the world-readable config
        self.assertNotIn(client_secret, config)

        # Credentials are only readable by root and not exposed by systemd
        self.assertEqual(
            read_file(TELEGRAF_ENV, sudo=True),
            f'AZURE_CLIENT_ID={client_id}\n'
            f'AZURE_CLIENT_SECRET={client_secret}\n'
            f'AZURE_TENANT_ID={tenant_id}',
        )
        self.assertEqual(file_permissions(TELEGRAF_ENV), '0600')
        self.assertNotIn(
            client_secret,
            cmdl(['systemctl', 'show', '-p', 'Environment', 'telegraf.service']),
        )

        # The running process must see the credentials, not only the file
        pid = process_named_running(PROCESS_NAME)
        environ = read_file(f'/proc/{pid}/environ', sudo=True)
        self.assertIn(f'AZURE_CLIENT_ID={client_id}', environ)
        self.assertIn(f'AZURE_CLIENT_SECRET={client_secret}', environ)
        self.assertIn(f'AZURE_TENANT_ID={tenant_id}', environ)

        # A reload keeps the old environment, a new secret needs a restart
        self.cli_set(
            azure_path + ['authentication', 'client-secret', new_client_secret]
        )
        self.cli_commit()

        # A new PID proves a restart, the old secret must be gone from it
        new_pid = process_named_running(PROCESS_NAME, timeout=10)
        self.assertNotEqual(pid, new_pid)
        environ = read_file(f'/proc/{new_pid}/environ', sudo=True)
        self.assertIn(f'AZURE_CLIENT_SECRET={new_client_secret}', environ)
        self.assertNotIn(client_secret, environ)

        # Adding InfluxDB must keep the Azure credentials in the env file
        self.basic_influxdb_setup()
        env = read_file(TELEGRAF_ENV, sudo=True)
        self.assertIn(f'INFLUX_TOKEN={token}', env)
        self.assertIn(f'AZURE_CLIENT_SECRET={new_client_secret}', env)

        # Removing all secrets removes the file
        self.cli_delete(azure_path)
        self.cli_delete(base_path + ['influxdb'])
        self.cli_set(base_path + ['prometheus-client'])
        self.cli_commit()
        self.assertFalse(os.path.exists(TELEGRAF_ENV))

    def test_11_influxdb_tls(self):
        # T9329: InfluxDB output must be able to use the on-box PKI to
        # authenticate the remote endpoint

        server_name = 'logs.vyos.local'
        ca_file = f'{TELEGRAF_CERT_DIR}/influxdb-ca.pem'
        cert_file = f'{TELEGRAF_CERT_DIR}/influxdb-cert.pem'
        key_file = f'{TELEGRAF_CERT_DIR}/influxdb-cert.key'

        ca_path = pki_base + ['ca', ca_cert_name]
        cert_path = pki_base + ['certificate', client_cert_name]
        self.cli_set(ca_path + ['certificate', ca_cert.replace('\n', '')])
        self.cli_set(cert_path + ['certificate', client_cert.replace('\n', '')])
        self.cli_set(cert_path + ['private', 'key', client_cert_key.replace('\n', '')])

        self.basic_influxdb_setup()

        tls_path = base_path + ['influxdb', 'tls']

        # Referenced PKI objects must exist
        self.cli_set(tls_path + ['ca-certificate', 'not-existing'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(tls_path + ['ca-certificate', ca_cert_name])
        self.cli_set(tls_path + ['certificate', 'not-existing'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(tls_path + ['certificate', client_cert_name])
        self.cli_set(tls_path + ['server-name', server_name])

        # 'ca-certificate' and 'insecure' are mutually exclusive
        self.cli_set(tls_path + ['insecure'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_delete(tls_path + ['insecure'])

        # Verify that TLS options have no effect as 'url' does not use HTTPS
        url_http = url.replace('https://', 'http://')
        self.cli_set(base_path + ['influxdb', 'url', url_http])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(base_path + ['influxdb', 'url', url])
        self.cli_commit()

        config = read_file(TELEGRAF_CONF)
        self.assertIn(f'tls_ca = "{ca_file}"', config)
        self.assertIn(f'tls_cert = "{cert_file}"', config)
        self.assertIn(f'tls_key = "{key_file}"', config)
        self.assertIn(f'tls_server_name = "{server_name}"', config)
        self.assertNotIn('insecure_skip_verify', config)
        for file in [ca_file, cert_file, key_file]:
            with self.subTest(file=file):
                self.assertTrue(os.path.isfile(file))
                self.assertGreater(os.stat(file).st_size, 0)

        # PKI objects in use must not be deleted
        self.cli_delete(pki_base + ['ca', ca_cert_name])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_discard()

        # Disable verification - no CA, no stale files left behind
        self.cli_delete(tls_path)
        self.cli_set(tls_path + ['insecure'])
        self.cli_commit()

        config = read_file(TELEGRAF_CONF)
        self.assertIn('insecure_skip_verify = true', config)
        self.assertNotIn('tls_ca', config)
        self.assertNotIn('tls_cert', config)
        self.assertNotIn('tls_key', config)
        for file in [ca_file, cert_file, key_file]:
            with self.subTest(file=file):
                self.assertFalse(os.path.exists(file))

        # Only server-name set - verification enabled using system CA store
        self.cli_delete(tls_path)
        self.cli_set(tls_path + ['server-name', server_name])
        self.cli_commit()

        config = read_file(TELEGRAF_CONF)
        self.assertIn(f'tls_server_name = "{server_name}"', config)
        self.assertNotIn('insecure_skip_verify', config)

        self.cli_delete(ca_path)
        self.cli_delete(cert_path)


if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
