#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
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

from vyos.configsession import ConfigSessionError
from vyos.utils.process import process_named_running
from vyos.utils.file import read_file

PROCESS_NAME = 'haproxy'
HAPROXY_CONF = '/run/haproxy/haproxy.cfg'
base_path = ['load-balancing', 'haproxy']
proxy_interface = 'eth1'

valid_ca_cert = """
MIIDnTCCAoWgAwIBAgIUewSDtLiZbhg1YEslMnqRl1shoPcwDQYJKoZIhvcNAQEL
BQAwVzELMAkGA1UEBhMCR0IxEzARBgNVBAgMClNvbWUtU3RhdGUxEjAQBgNVBAcM
CVNvbWUtQ2l0eTENMAsGA1UECgwEVnlPUzEQMA4GA1UEAwwHdnlvcy5pbzAeFw0y
NDA0MDEwNTQ3MzJaFw0yOTAzMzEwNTQ3MzJaMFcxCzAJBgNVBAYTAkdCMRMwEQYD
VQQIDApTb21lLVN0YXRlMRIwEAYDVQQHDAlTb21lLUNpdHkxDTALBgNVBAoMBFZ5
T1MxEDAOBgNVBAMMB3Z5b3MuaW8wggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEK
AoIBAQC/D6W27rfpdPIf16JHs8fx/7VehyCk8m03dPAQqv6wQiHF5xhXaFZER1+c
nf7oExp9zi/4HJ/KRbcc1loVArXtV0zwAUftBmUeezGVfxhCHKhP89GnV4NB97jj
klHFSxjEoT/0YvJQ1IV/3Cos1T5O8x14WIi31l7WQGYAyWxUXiP8QxGVmF3odEJo
O3e7Ew9HFkamvuL6Z6c4uAVMM7uYXme7q0OM49Wu7C9hj39ZKbjG5FFKZTj+zDKg
SbOiQaFk3blOky/e3ifNjZelGtussYPOMBkUirLvrSGGy7s3lm8Yp5PH5+UkVQB2
rZyxRdZTC9kh+dShR1s/qcPnDw7lAgMBAAGjYTBfMA8GA1UdEwEB/wQFMAMBAf8w
DgYDVR0PAQH/BAQDAgGGMB0GA1UdJQQWMBQGCCsGAQUFBwMCBggrBgEFBQcDATAd
BgNVHQ4EFgQU/HE2UPn8JQB/9EL52GquPxZqr5MwDQYJKoZIhvcNAQELBQADggEB
AIkMmqyoMqidTa3lvUPJNl4H+Ef/yPQkTkrsOd3WL8DQysyUdMLdQozr3K1bH5XB
wRxoXX211nu4WhN18LsFJRCuHBSxmaNkBGFyl+JNvhPUSI6j0somNMCS75KJ0ZDx
2HZsXmmJFF902VQxCR7vCIrFDrKDYq1e7GQbFS8t46FlpqivQMQWNPt18Bthj/1Y
lO2GKRWFCX8VlOW7FtDQ6B3oC1oAGHBBGogAx7/0gh9DnYBKT14V/kuWW3RNABZJ
ewHO1C6icQdnjtaREDyTP4oyL+uyAfXrFfbpti2hc00f8oYPQZYxj1yxl4UAdNij
mS6YqH/WRioGMe3tBVeSdoo=
"""

valid_ca_private_key = """
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC/D6W27rfpdPIf
16JHs8fx/7VehyCk8m03dPAQqv6wQiHF5xhXaFZER1+cnf7oExp9zi/4HJ/KRbcc
1loVArXtV0zwAUftBmUeezGVfxhCHKhP89GnV4NB97jjklHFSxjEoT/0YvJQ1IV/
3Cos1T5O8x14WIi31l7WQGYAyWxUXiP8QxGVmF3odEJoO3e7Ew9HFkamvuL6Z6c4
uAVMM7uYXme7q0OM49Wu7C9hj39ZKbjG5FFKZTj+zDKgSbOiQaFk3blOky/e3ifN
jZelGtussYPOMBkUirLvrSGGy7s3lm8Yp5PH5+UkVQB2rZyxRdZTC9kh+dShR1s/
qcPnDw7lAgMBAAECggEAGm+j0kf9koPn7Jf9kEZD6CwlgEraLXiNvBqmDOhcDS9Z
VPTA3XdGWHQ3uofx+VKLW9TntkDfqzEyQP83v6h8W7a0opDKzvUPkMQi/Dh1ttAY
SdfGrozhUINiRbq9LbtSVgKpwrreJGkDf8mK3GE1Gd9xuHEnmahDvwlyE7HLF3Eh
2xJDSAPx3OxcjR5hW7vbojhVCyCfuYTlZB86f0Sb8SqxZMt/y2zKmbzoTqpUBWbg
lBnE7GJoNR07DWjxvEP8r6kQMh670I01SUR42CSK8X8asHhhZHUcggsNno+BBc6K
sy4HzDIYIay6oy0atcVzKsGrlNCveeAiSEcw7x2yAQKBgQDsXz2FbhXYV5Vbt4wU
5EWOa7if/+FG+TcVezOF3xlNBgykjXHQaYTYHrJq0qsEFrNT3ZGm9ezY4LdF3BTt
5z/+i8QlCCw/nr3N7JZx6U5+OJl1j3NLFoFx3+DXo31pgJJEQCHHwdCkF5IuOcZ/
b3nXkRZ80BVv7XD6F9bMHEwLYQKBgQDO7THcRDbsE6/+7VsTDf0P/JENba3DBBu1
gjb1ItL5FHJwMgnkUadRZRo0QKye848ugribed39qSoJfNaBJrAT5T8S/9q+lXft
vXUckcBO1CKNaP9gqF5fPIdNHf64GbmCiiHjOTE3rwJjkxJPpzLXyvgBO4aLeesK
ThBdW+iWBQKBgD3crz08knsMcQqP/xl4pLuhdbBqR4tLrh7xH4rp2LVP3/8xBZiG
BT6Kyicq+5cWWdiZJIWN127rYQvnjZK18wmriqomeW4tHX/Ha5hkdyaRqZga8xGz
0iz7at0E7M2v2JgEMNMW5oQLpzZx6IFxq3G/hyMjUnj4q5jIpG7G+SABAoGBAKgT
8Ika+4WcpDssrup2VVTT8Tp4GUkroBo6D8vkInvhiObrLi+/x2mM9tD0q4JdEbNU
yQC454EwFA4q0c2MED/I2QfkvNhLbmO0nVi8ZvlgxEQawjzP5f/zmW8haxI9Cvsm
mkoH3Zt+UzFwd9ItXFX97p6JrErEmA8Bw7chfXXFAoGACWR/c+s7hnX6gzyah3N1
Db0xAaS6M9fzogcg2OM1i/6OCOcp4Sh1fmPG7tN45CCnFkhgVoRkSSA5MJAe2I/r
xFm72VX7567T+4qIFua2iDxIBA/Z4zmj+RYfhHGPYZjdSjprKJxY6QOv5aoluBvE
mlLy1Hmcry+ukWZtWezZfGY=
"""

valid_cert = """
MIIDsTCCApmgAwIBAgIUDKOfYIwwtjww0vAMvJnXnGLhL+0wDQYJKoZIhvcNAQEL
BQAwVzELMAkGA1UEBhMCR0IxEzARBgNVBAgMClNvbWUtU3RhdGUxEjAQBgNVBAcM
CVNvbWUtQ2l0eTENMAsGA1UECgwEVnlPUzEQMA4GA1UEAwwHdnlvcy5pbzAeFw0y
NDA0MDEwNTQ5NTdaFw0yNTA0MDEwNTQ5NTdaMFcxCzAJBgNVBAYTAkdCMRMwEQYD
VQQIDApTb21lLVN0YXRlMRIwEAYDVQQHDAlTb21lLUNpdHkxDTALBgNVBAoMBFZ5
T1MxEDAOBgNVBAMMB3Z5b3MuaW8wggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEK
AoIBAQCHtW25Umt6rqm2gfzqAZg1/VsqefZwAqIUAm2T3VwHQZ/2tNdr8ROWASii
W5PToC7N8StMwFl2YoIof+MXGMO00toTTJePZOJKjF9U9hL3kuYuY1+yng4fl+E0
96xVobb2KY4lMZ2rVwmpB7jkNO2LWxbJ6vHKcwMOhlx/8NEKIoVmkBT1Zkgy5dgn
PgTtJcdVIU75XhQWqBmAUsMmACuZfqSYJbAv3hHz5V+Ejt0dI6mlGM7TXsCC9tKM
64paIKZooFm78IsxJ26jHpZ8eh+SDBz0VBydBFWXm8VhOJ8NlZ1opAh3AWxFZDGt
49uOsy82VmUcHPyoZ8DKYkBFHfSpAgMBAAGjdTBzMAwGA1UdEwEB/wQCMAAwDgYD
VR0PAQH/BAQDAgeAMBMGA1UdJQQMMAoGCCsGAQUFBwMBMB0GA1UdDgQWBBTeTcgM
pRxAMjVBirjzo2QUu5H5fzAfBgNVHSMEGDAWgBT8cTZQ+fwlAH/0QvnYaq4/Fmqv
kzANBgkqhkiG9w0BAQsFAAOCAQEAi4dBcH7TIYwWRW6bWRubMA7ztonV4EYb15Zf
9yNafMWAEEBOii/DFo+j/ky9oInl7ZHw7gTIyXfLEarX/bM6fHOgiyj4zp3u6RnH
5qlBypu/YCnyPjE/GvV05m2rrXnxZ4rCtcoO4u/HyGbV+jGnCmjShKICKyu1FdMd
eeZRrLKPO/yghadGH34WVQnrbaorwlbi+NjB6fxmZQx5HE/SyK/9sb6WCpLMGHoy
MpdQo3lV1ewtL3ElIWDq6mO030Mo5pwpjIU+8yHHNBVzg6mlGVgQPAp0gbUei9aP
CJ8SLmMEi3NDk0E/sPgVC17e6bf2bx2nRuXROZekG2dd90Iu8g==
"""

valid_cert_private_key = """
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCHtW25Umt6rqm2
gfzqAZg1/VsqefZwAqIUAm2T3VwHQZ/2tNdr8ROWASiiW5PToC7N8StMwFl2YoIo
f+MXGMO00toTTJePZOJKjF9U9hL3kuYuY1+yng4fl+E096xVobb2KY4lMZ2rVwmp
B7jkNO2LWxbJ6vHKcwMOhlx/8NEKIoVmkBT1Zkgy5dgnPgTtJcdVIU75XhQWqBmA
UsMmACuZfqSYJbAv3hHz5V+Ejt0dI6mlGM7TXsCC9tKM64paIKZooFm78IsxJ26j
HpZ8eh+SDBz0VBydBFWXm8VhOJ8NlZ1opAh3AWxFZDGt49uOsy82VmUcHPyoZ8DK
YkBFHfSpAgMBAAECggEABofhw0W/ACEMcAjmpNTFkFCUXPGQXWDVD7EzuIZSNdOv
yOm4Rbys6H6/B7wwO6KVagoBf1Cw5Xh1YtFPuoZxsZ+liMD6eLc+SB/j/RTYAhPO
0bvsyK3gSF8w4nGKWLce9M74ZRwThkG6qGijmlDdPyP3r2kn8GoTQzVOWYZbavk/
H3uE6PsZSWjOY+Mnm3vEmeItPYKGZ5+IP+YiTqZ4NCggBwH7csnR3/kbwY5Ns7jl
3Av+EAdIeUwDNeMfLTzN7GphJR7gL6YQIhGKxE+W0GHXL2FubnnrFx8G75HFh1ay
GkJXEqY5Lbd+7VPS0KcQdwhMSSoJsY5GUORUqrU80QKBgQC/0wJSu+Gfe7dONIby
mnGRppSRIQVRjCjbVIN+Y2h1Kp3aK0qDpV7KFLCiUUtz9rWHR/NB4cDaIW543T55
/jXUMD2j3EqtbtlsVQfDLQV7DyDrMmBAs4REHmyZmWTzHjCDUO79ahdOlZs34Alz
wfpX3L3WVYGIAJKZtsUZ8FbrGQKBgQC1HFgVZ1PqP9/pW50RMh06BbQrhWPGiWgH
Rn5bFthLkp3uqr9bReBq9tu3sqJuAhFudH68wup+Z+fTcHAcNg2Rs+Q+IKnULdB/
UQHYoPjeWOvHAuOmgn9iD9OD7GCIv8fZmLit09vAsOWq+NKNBKCknGM70CDrvAlQ
lOAUa34YEQKBgQC5i8GThWiYe3Kzktt1jy6LVDYgq3AZkRl0Diui9UT1EGPfxEAv
VqZ5kcnJOBlj8h9k25PRBi0k0XGqN1dXaS1oMcFt3ofdenuU7iqz/7htcBTHa9Lu
wrYNreAeMuISyADlBEQnm5cvzEZ3pZ1++wLMOhjmWY8Rnnwvczrz/CYXAQKBgH+t
vcNJFvWblkUzWuWWiNgw0TWlUhPTJs2KOuYIku+kK0bohQLZnj6KTZeRjcU0HAnc
gsScPShkJCEBsWeSC7reMVhDOrbknYpEF6MayJgn5ABm3wqyEQ+WzKzCZcPCQCf8
7KVPKCsOCrufsv/LdVzXC3ZNYggOhhqS+e4rYbehAoGBAIsq252o3vgrunzS5FZx
IONA2FvYrxVbDn5aF8WfNSdKFy3CAlt0P+Fm8gYbrKylIfMXpL8Oqc9RJou5onZP
ZXLrtgVJR9W020qTurO2f91qfU8646n11hR9ObBB1IYbagOU0Pw1Nrq/FRp/u2tx
7i7xFz2WEiQeSCPaKYOiqM3t
"""


class TestLoadBalancingReverseProxy(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

        self.cli_delete(['interfaces', 'ethernet', proxy_interface, 'address'])
        self.cli_delete(base_path)
        self.cli_delete(['pki'])
        self.cli_commit()

        # Process must be terminated after deleting the config
        self.assertFalse(process_named_running(PROCESS_NAME))

    def base_config(self):
        self.cli_set(base_path + ['service', 'https_front', 'mode', 'http'])
        self.cli_set(base_path + ['service', 'https_front', 'port', '4433'])
        self.cli_set(base_path + ['service', 'https_front', 'backend', 'bk-01'])

        self.cli_set(base_path + ['backend', 'bk-01', 'mode', 'http'])
        self.cli_set(base_path + ['backend', 'bk-01', 'server', 'bk-01', 'address', '192.0.2.11'])
        self.cli_set(base_path + ['backend', 'bk-01', 'server', 'bk-01', 'port', '9090'])
        self.cli_set(base_path + ['backend', 'bk-01', 'server', 'bk-01', 'send-proxy'])

        self.cli_set(base_path + ['global-parameters', 'max-connections', '1000'])

    def configure_pki(self):

        # Valid CA
        self.cli_set(['pki', 'ca', 'smoketest', 'certificate', valid_ca_cert.replace('\n','')])
        self.cli_set(['pki', 'ca', 'smoketest', 'private', 'key', valid_ca_private_key.replace('\n','')])

        # Valid cert
        self.cli_set(['pki', 'certificate', 'smoketest', 'certificate', valid_cert.replace('\n','')])
        self.cli_set(['pki', 'certificate', 'smoketest', 'private', 'key', valid_cert_private_key.replace('\n','')])

    def test_01_lb_reverse_proxy_domain(self):
        domains_bk_first = ['n1.example.com', 'n2.example.com', 'n3.example.com']
        domain_bk_second = 'n5.example.com'
        frontend = 'https_front'
        front_port = '4433'
        bk_server_first = '192.0.2.11'
        bk_server_second = '192.0.2.12'
        bk_first_name = 'bk-01'
        bk_second_name = 'bk-02'
        bk_server_port = '9090'
        mode = 'http'
        rule_ten = '10'
        rule_twenty = '20'
        rule_thirty = '30'
        send_proxy = 'send-proxy'
        max_connections = '1000'

        back_base = base_path + ['backend']

        self.cli_set(base_path + ['service', frontend, 'mode', mode])
        self.cli_set(base_path + ['service', frontend, 'port', front_port])
        for domain in domains_bk_first:
            self.cli_set(base_path + ['service', frontend, 'rule', rule_ten, 'domain-name', domain])
        self.cli_set(base_path + ['service', frontend, 'rule', rule_ten, 'set', 'backend', bk_first_name])
        self.cli_set(base_path + ['service', frontend, 'rule', rule_twenty, 'domain-name', domain_bk_second])
        self.cli_set(base_path + ['service', frontend, 'rule', rule_twenty, 'set', 'backend', bk_second_name])
        self.cli_set(base_path + ['service', frontend, 'rule', rule_thirty, 'url-path', 'end', '/test'])
        self.cli_set(base_path + ['service', frontend, 'rule', rule_thirty, 'set', 'backend', bk_second_name])

        self.cli_set(back_base + [bk_first_name, 'mode', mode])
        self.cli_set(back_base + [bk_first_name, 'server', bk_first_name, 'address', bk_server_first])
        self.cli_set(back_base + [bk_first_name, 'server', bk_first_name, 'port', bk_server_port])
        self.cli_set(back_base + [bk_first_name, 'server', bk_first_name, send_proxy])

        self.cli_set(back_base + [bk_second_name, 'mode', mode])
        self.cli_set(back_base + [bk_second_name, 'server', bk_second_name, 'address', bk_server_second])
        self.cli_set(back_base + [bk_second_name, 'server', bk_second_name, 'port', bk_server_port])
        self.cli_set(back_base + [bk_second_name, 'server', bk_second_name, 'backup'])

        self.cli_set(base_path + ['global-parameters', 'max-connections', max_connections])

        # commit changes
        self.cli_commit()

        config = read_file(HAPROXY_CONF)

        # Global
        self.assertIn(f'maxconn {max_connections}', config)

        # Frontend
        self.assertIn(f'frontend {frontend}', config)
        self.assertIn(f'bind [::]:{front_port} v4v6', config)
        self.assertIn(f'mode {mode}', config)
        for domain in domains_bk_first:
            self.assertIn(f'acl {rule_ten} hdr(host) -i {domain}', config)
        self.assertIn(f'use_backend {bk_first_name} if {rule_ten}', config)
        self.assertIn(f'acl {rule_twenty} hdr(host) -i {domain_bk_second}', config)
        self.assertIn(f'use_backend {bk_second_name} if {rule_twenty}', config)
        self.assertIn(f'acl {rule_thirty} path -i -m end /test', config)
        self.assertIn(f'use_backend {bk_second_name} if {rule_thirty}', config)

        # Backend
        self.assertIn(f'backend {bk_first_name}', config)
        self.assertIn(f'balance roundrobin', config)
        self.assertIn(f'option forwardfor', config)
        self.assertIn('http-request add-header X-Forwarded-Proto https if { ssl_fc }', config)
        self.assertIn(f'mode {mode}', config)
        self.assertIn(f'server {bk_first_name} {bk_server_first}:{bk_server_port} send-proxy', config)

        self.assertIn(f'backend {bk_second_name}', config)
        self.assertIn(f'mode {mode}', config)
        self.assertIn(f'server {bk_second_name} {bk_server_second}:{bk_server_port}', config)
        self.assertIn(f'server {bk_second_name} {bk_server_second}:{bk_server_port} backup', config)

    def test_02_lb_reverse_proxy_cert_not_exists(self):
        self.base_config()
        self.cli_set(base_path + ['service', 'https_front', 'ssl', 'certificate', 'cert'])

        with self.assertRaises(ConfigSessionError) as e:
            self.cli_commit()
        # self.assertIn('\nCertificates does not exist in PKI\n', str(e.exception))

        self.cli_delete(base_path)
        self.configure_pki()

        self.base_config()
        self.cli_set(base_path + ['service', 'https_front', 'ssl', 'certificate', 'cert'])

        with self.assertRaises(ConfigSessionError) as e:
            self.cli_commit()
        # self.assertIn('\nCertificate "cert" does not exist\n', str(e.exception))

        self.cli_delete(base_path + ['service', 'https_front', 'ssl', 'certificate', 'cert'])
        self.cli_set(base_path + ['service', 'https_front', 'ssl', 'certificate', 'smoketest'])
        self.cli_commit()

    def test_03_lb_reverse_proxy_ca_not_exists(self):
        self.base_config()
        self.cli_set(base_path + ['backend', 'bk-01', 'ssl', 'ca-certificate', 'ca-test'])

        with self.assertRaises(ConfigSessionError) as e:
            self.cli_commit()
        # self.assertIn('\nCA certificates does not exist in PKI\n', str(e.exception))

        self.cli_delete(base_path)
        self.configure_pki()

        self.base_config()
        self.cli_set(base_path + ['backend', 'bk-01', 'ssl', 'ca-certificate', 'ca-test'])

        with self.assertRaises(ConfigSessionError) as e:
            self.cli_commit()
        # self.assertIn('\nCA certificate "ca-test" does not exist\n', str(e.exception))

        self.cli_delete(base_path + ['backend', 'bk-01', 'ssl', 'ca-certificate', 'ca-test'])
        self.cli_set(base_path + ['backend', 'bk-01', 'ssl', 'ca-certificate', 'smoketest'])
        self.cli_commit()

    def test_04_lb_reverse_proxy_backend_ssl_no_verify(self):
        # Setup base
        self.configure_pki()
        self.base_config()

        # Set no-verify option
        self.cli_set(base_path + ['backend', 'bk-01', 'ssl', 'no-verify'])
        self.cli_commit()

        # Test no-verify option
        config = read_file(HAPROXY_CONF)
        self.assertIn('server bk-01 192.0.2.11:9090 send-proxy ssl verify none', config)

        # Test setting ca-certificate alongside no-verify option fails, to test config validation
        self.cli_set(base_path + ['backend', 'bk-01', 'ssl', 'ca-certificate', 'smoketest'])
        with self.assertRaises(ConfigSessionError) as e:
            self.cli_commit()

    def test_05_lb_reverse_proxy_backend_http_check(self):
        # Setup base
        self.base_config()

        # Set http-check
        self.cli_set(base_path + ['backend', 'bk-01', 'http-check', 'method', 'get'])
        self.cli_commit()

        # Test http-check
        config = read_file(HAPROXY_CONF)
        self.assertIn('option httpchk', config)
        self.assertIn('http-check send meth GET', config)

        # Set http-check with uri and status
        self.cli_set(base_path + ['backend', 'bk-01', 'http-check', 'uri', '/health'])
        self.cli_set(base_path + ['backend', 'bk-01', 'http-check', 'expect', 'status', '200'])
        self.cli_commit()

        # Test http-check with uri and status
        config = read_file(HAPROXY_CONF)
        self.assertIn('option httpchk', config)
        self.assertIn('http-check send meth GET uri /health', config)
        self.assertIn('http-check expect status 200', config)

        # Set http-check with string
        self.cli_delete(base_path + ['backend', 'bk-01', 'http-check', 'expect', 'status', '200'])
        self.cli_set(base_path + ['backend', 'bk-01', 'http-check', 'expect', 'string', 'success'])
        self.cli_commit()

        # Test http-check with string
        config = read_file(HAPROXY_CONF)
        self.assertIn('option httpchk', config)
        self.assertIn('http-check send meth GET uri /health', config)
        self.assertIn('http-check expect string success', config)

        # Test configuring both http-check & health-check fails validation script
        self.cli_set(base_path + ['backend', 'bk-01', 'health-check', 'ldap'])
        with self.assertRaises(ConfigSessionError) as e:
            self.cli_commit()

    def test_06_lb_reverse_proxy_tcp_mode(self):
        frontend = 'tcp_8443'
        mode = 'tcp'
        front_port = '8433'
        tcp_request_delay = "5000"
        rule_thirty = '30'
        domain_bk = 'n6.example.com'
        ssl_opt = "req-ssl-sni"
        bk_name = 'bk-03'
        bk_server = '192.0.2.11'
        bk_server_port = '9090'

        back_base = base_path + ['backend']

        self.cli_set(base_path + ['service', frontend, 'mode', mode])
        self.cli_set(base_path + ['service', frontend, 'port', front_port])
        self.cli_set(base_path + ['service', frontend, 'tcp-request', 'inspect-delay', tcp_request_delay])

        self.cli_set(base_path + ['service', frontend, 'rule', rule_thirty, 'domain-name', domain_bk])
        self.cli_set(base_path + ['service', frontend, 'rule', rule_thirty, 'ssl', ssl_opt])
        self.cli_set(base_path + ['service', frontend, 'rule', rule_thirty, 'set', 'backend', bk_name])

        self.cli_set(back_base + [bk_name, 'mode', mode])
        self.cli_set(back_base + [bk_name, 'server', bk_name, 'address', bk_server])
        self.cli_set(back_base + [bk_name, 'server', bk_name, 'port', bk_server_port])

        # commit changes
        self.cli_commit()

        config = read_file(HAPROXY_CONF)

        # Frontend
        self.assertIn(f'frontend {frontend}', config)
        self.assertIn(f'bind [::]:{front_port} v4v6', config)
        self.assertIn(f'mode {mode}', config)

        self.assertIn(f'tcp-request inspect-delay {tcp_request_delay}', config)
        self.assertIn(f"tcp-request content accept if {{ req_ssl_hello_type 1 }}", config)
        self.assertIn(f'acl {rule_thirty} req_ssl_sni -i {domain_bk}', config)
        self.assertIn(f'use_backend {bk_name} if {rule_thirty}', config)

        # Backend
        self.assertIn(f'backend {bk_name}', config)
        self.assertIn(f'balance roundrobin', config)
        self.assertIn(f'mode {mode}', config)
        self.assertIn(f'server {bk_name} {bk_server}:{bk_server_port}', config)

    def test_07_lb_reverse_proxy_http_response_headers(self):
        # Setup base
        self.configure_pki()
        self.base_config()

        # Set example headers in both frontend and backend
        self.cli_set(base_path + ['service', 'https_front', 'http-response-headers', 'Cache-Control', 'value', 'max-age=604800'])
        self.cli_set(base_path + ['backend', 'bk-01',  'http-response-headers', 'Proxy-Backend-ID', 'value', 'bk-01'])
        self.cli_commit()

        # Test headers are present in generated configuration file
        config = read_file(HAPROXY_CONF)
        self.assertIn('http-response set-header Cache-Control \'max-age=604800\'', config)
        self.assertIn('http-response set-header Proxy-Backend-ID \'bk-01\'', config)

        # Test setting alongside modes other than http is blocked by validation conditions
        self.cli_set(base_path + ['service', 'https_front', 'mode', 'tcp'])
        with self.assertRaises(ConfigSessionError) as e:
            self.cli_commit()

    def test_08_lb_reverse_proxy_tcp_health_checks(self):
        # Setup PKI
        self.configure_pki()

        # Define variables
        frontend = 'fe_ldaps'
        mode = 'tcp'
        health_check = 'ldap'
        front_port = '636'
        bk_name = 'bk_ldap'
        bk_servers = ['192.0.2.11', '192.0.2.12']
        bk_server_port = '389'

        # Configure frontend
        self.cli_set(base_path + ['service', frontend, 'mode', mode])
        self.cli_set(base_path + ['service', frontend, 'port', front_port])
        self.cli_set(base_path + ['service', frontend, 'ssl', 'certificate', 'smoketest'])

        # Configure backend
        self.cli_set(base_path + ['backend', bk_name, 'mode', mode])
        self.cli_set(base_path + ['backend', bk_name, 'health-check', health_check])
        for index, bk_server in enumerate(bk_servers):
            self.cli_set(base_path + ['backend', bk_name, 'server', f'srv-{index}', 'address', bk_server])
            self.cli_set(base_path + ['backend', bk_name, 'server', f'srv-{index}', 'port', bk_server_port])

        # Commit & read config
        self.cli_commit()
        config = read_file(HAPROXY_CONF)

        # Validate Frontend
        self.assertIn(f'frontend {frontend}', config)
        self.assertIn(f'bind [::]:{front_port} v4v6 ssl crt /run/haproxy/smoketest.pem', config)
        self.assertIn(f'mode {mode}', config)
        self.assertIn(f'backend {bk_name}', config)

        # Validate Backend
        self.assertIn(f'backend {bk_name}', config)
        self.assertIn(f'option {health_check}-check', config)
        self.assertIn(f'mode {mode}', config)
        for index, bk_server in enumerate(bk_servers):
            self.assertIn(f'server srv-{index} {bk_server}:{bk_server_port}', config)

        # Validate SMTP option renders correctly
        self.cli_set(base_path + ['backend', bk_name, 'health-check', 'smtp'])
        self.cli_commit()
        config = read_file(HAPROXY_CONF)
        self.assertIn(f'option smtpchk', config)

    def test_09_lb_reverse_proxy_logging(self):
        # Setup base
        self.base_config()
        self.cli_commit()

        # Ensure default logging configuration is present
        config = read_file(HAPROXY_CONF)

        # Test global-parameters logging options
        self.cli_set(base_path + ['global-parameters', 'logging', 'facility', 'local1', 'level', 'err'])
        self.cli_set(base_path + ['global-parameters', 'logging', 'facility', 'local2', 'level', 'warning'])
        self.cli_commit()

        # Test global logging parameters are generated in configuration file
        config = read_file(HAPROXY_CONF)
        self.assertIn('log /dev/log local1 err', config)
        self.assertIn('log /dev/log local2 warning', config)

        # Test backend logging options
        backend_path = base_path + ['backend', 'bk-01']
        self.cli_set(backend_path + ['logging', 'facility', 'local3', 'level', 'debug'])
        self.cli_set(backend_path + ['logging', 'facility', 'local4', 'level', 'info'])
        self.cli_commit()

        # Test backend logging parameters are generated in configuration file
        config = read_file(HAPROXY_CONF)
        self.assertIn('log /dev/log local3 debug', config)
        self.assertIn('log /dev/log local4 info', config)

        # Test service logging options
        service_path = base_path + ['service', 'https_front']
        self.cli_set(service_path + ['logging', 'facility', 'local5', 'level', 'notice'])
        self.cli_set(service_path + ['logging', 'facility', 'local6', 'level', 'crit'])
        self.cli_commit()

        # Test service logging parameters are generated in configuration file
        config = read_file(HAPROXY_CONF)
        self.assertIn('log /dev/log local5 notice', config)
        self.assertIn('log /dev/log local6 crit', config)

if __name__ == '__main__':
    unittest.main(verbosity=2)
