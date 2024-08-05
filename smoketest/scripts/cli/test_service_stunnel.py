#!/usr/bin/env python3
#
# Copyright (C) 2024 VyOS maintainers and contributors
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
import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.utils.process import process_named_running
from vyos.utils.file import read_file


PROCESS_NAME = 'stunnel'
STUNNEL_CONF = '/run/stunnel/stunnel.conf'
base_path = ['service', 'stunnel']

ca_certificate = """
MIIDnTCCAoWgAwIBAgIUcSMo/zT/GUAyH3uM3Hr3qjCDmMUwDQYJKoZIhvcNAQELBQAwVzELMAkGA1U
EBhMCR0IxEzARBgNVBAgMClNvbWUtU3RhdGUxEjAQBgNVBAcMCVNvbWUtQ2l0eTENMAsGA1UECgwEVn
lPUzEQMA4GA1UEAwwHdnlvcy5pbzAeFw0yNDA2MDQwNjU1MDFaFw0yOTA2MDMwNjU1MDFaMFcxCzAJB
gNVBAYTAkdCMRMwEQYDVQQIDApTb21lLVN0YXRlMRIwEAYDVQQHDAlTb21lLUNpdHkxDTALBgNVBAoM
BFZ5T1MxEDAOBgNVBAMMB3Z5b3MuaW8wggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCzN7B
Zw0OBBgeGL7KCKdDIUfBEhh08+3V8Nm7K23mU/pYd3bR5WXt9VWkW5YWUw1hr1N3qEQ2AZX8TrIDj37
zzy1jyDCvJHGWnKTOOAboNIInP+PvUQrSH8SDAw/+/KjKKgM069NFhGq9TTHg4BAYC0GsZL+JE3Ptee
cIVmekf5Dw+vnD0Mlwx5Ouaf/9OwRcGhfwEkIORQLXDuMayOI/JdFbaDVlA6Z/d8GLp3Xlc8/l5XFtg
fvMNQSB9B69Cs4qwU/yey8tPWeDBiW6Cx2XOnKqiNBaCY1BzvSH+hmHcos1DOLHgEZ3d2zaNn2mrhmB
Ry7/5Ww7O5PoF00OB9WHFAgMBAAGjYTBfMA8GA1UdEwEB/wQFMAMBAf8wDgYDVR0PAQH/BAQDAgGGMB
0GA1UdJQQWMBQGCCsGAQUFBwMCBggrBgEFBQcDATAdBgNVHQ4EFgQU4zgMpOMOweRZUbeNewJnh5xZL
XwwDQYJKoZIhvcNAQELBQADggEBAAEK+jXvCKuC/n8qu9XFcLYfO3kUKPlXD30V61KRZilHyYGYu0MY
sSNeX8+K7CpeAo06HHocrrDfCKltoLFuix7qblr2DEub+v3V21pllMfThkz9FsXWFGfmOyI7sXNXUg9
cVQHzj2SvMj+IfnJoCIuYnigmlKVTuxV31iYv2RpML/PBw29xI0G/AsmXZK4wOQ0eA9gU+ggURE98hG
8f4DRpGVnlyP1d+P2Va0bsl3Yek9QfrotnmE1EzwZzPZyCL9rv8oDjfJ98O3YqoNSRNvD+Glke2ZlTj
WFw+uCj0GTki5+V40E9X9Rwcje+s/5zWDBfu0akufcI1nsu++rZz/s=
"""

ca_private_key = """
MIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQCzN7BZw0OBBgeGL7KCKdDIUfBEhh0
8+3V8Nm7K23mU/pYd3bR5WXt9VWkW5YWUw1hr1N3qEQ2AZX8TrIDj37zzy1jyDCvJHGWnKTOOAboNII
nP+PvUQrSH8SDAw/+/KjKKgM069NFhGq9TTHg4BAYC0GsZL+JE3PteecIVmekf5Dw+vnD0Mlwx5Ouaf
/9OwRcGhfwEkIORQLXDuMayOI/JdFbaDVlA6Z/d8GLp3Xlc8/l5XFtgfvMNQSB9B69Cs4qwU/yey8tP
WeDBiW6Cx2XOnKqiNBaCY1BzvSH+hmHcos1DOLHgEZ3d2zaNn2mrhmBRy7/5Ww7O5PoF00OB9WHFAgM
BAAECggEAHFC/pacCutdrh+lwUD1wFb5QclsoMnLeYJYvEhD0GDTTHfvh4ExhhO9iL7Jq1RK6HStgNn
OkSPWASuj14kr+zRwDPRbsMhWw/+S0FwsxzJIoA/poO2SgplvUG3C8LwVpP9XS1y5ICIoRSl1qHxuPo
ZExYqTcoJmzg31ES2pqWVXPx14DdpE6yvSL2XwFS4mb291OkydnvKSBcK0MwgEWLQHouzMjihJ1MCXx
7NXsOxFX76OpmywMW7EtTLEngxL9b61hCYwWeNxmx9pN8qRzmvayKl40VLyqAlVcElZ7aEK0+O/Qpsu
QhsFRjA4HcXUqlHbvh92OqX+QmBU2RIZ27wKBgQDnJ8E8cJOlJ9ZvFBfw8az49IX9E72oxb2yaXm0Eo
OQ2Jz88+b2jzWqf3wdGvigNO25DbdYYodR7iJJo4OYPuyAnkJMWdPQ91ADo7ABwJiBqtUHC+Gvq5Rmm
I2T3T4+Vqu5Sa8lVfHWfv7Pnb++I5/7bH+VuGspyf+0NcpPh9UfIwKBgQDGet1wh0+2378HnnQNb10w
wxDiMC2hP+3RGPB6bKHLJ60LE+Ed2KFY+j8Q1+jQk9eMe6A75bwB/q6rMO1evpauCHTJoA863HxXtuL
P9ozVpDk9k4TbiSOsD0s8TXL3XG1ANshk4VfuLboKj4MEwiuxfGt6QGpsgLfHcmlkFIM99wKBgQDeea
C97wvrVOBJoGk6eSAlrBKZdTqBCXB+Go4MBhWifxj5TDXq8AKSyohF6wOIDekOxmjEJHBhJnTRsxKgo
U82qxrcKUh4Qs878Xsg9KDTi/vkAEeCr/zwkbsRqUqS7Q/yET0FDibobuoIIKe+9MKxVcel7g0V91in
tW22BeHVSQKBgQCKctwSiaCWTP8A/ouvb3ZO9FLLpJW/vEtUpxPgIfS+NH/lkUlfu2PZID5rrmAtVmN
uEDJWdcsujQwkSC3cABA1d5qXpnnZMkHeIamXLUFSKYrwI/3x8XibpdNyTgga+jMPLuecTwA6GVWD1l
WrNRKrbMG/9j0GUMdhbbKMaC6gQwKBgQCC9EUZBqCXS167OZNPQN4oKx6nJ9uTKUVyPigr12cMpPL6t
JwZAVVwSnyg+cVznNrMhAnG547c0NnoOe+nd9zczLJOuQHHLSMZUH08c2ZWtwpwbHDWI55hfZL4te8e
dEcxanXNYAfSMMtOoA+LmcCtfvqld/EucAN4mKTPGmWPQg==
"""

srv_certificate = """
MIIDsTCCApmgAwIBAgIUIvMZU3zc3iYl6JzbDLSvr8NOK5swDQYJKoZIhvcNAQELBQAwVzELMAkGA1U
EBhMCR0IxEzARBgNVBAgMClNvbWUtU3RhdGUxEjAQBgNVBAcMCVNvbWUtQ2l0eTENMAsGA1UECgwEVn
lPUzEQMA4GA1UEAwwHdnlvcy5pbzAeFw0yNDA2MDQwNjU1NDVaFw0yNTA2MDQwNjU1NDVaMFcxCzAJB
gNVBAYTAkdCMRMwEQYDVQQIDApTb21lLVN0YXRlMRIwEAYDVQQHDAlTb21lLUNpdHkxDTALBgNVBAoM
BFZ5T1MxEDAOBgNVBAMMB3Z5b3MuaW8wggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCtani
zx0h1fEH0pMRBB7V7nUAnSOAiCRUNpeTz6RoUqH0y/UaxM+kqitUm+MSAWxEJAXW4ZlxNzU+tC6DOwP
d+7/rZsT6fKeCbMIs8Es9VaXd2sZzb7DajEygeyIy1b3JGXIiNJ9KcOxzhmu5VHe+6qLCO3FDt4iFIr
HXJxwQKm8qL6zgn7f9kboQYBHKOhY8x+ghkhLYAwMlvIHGwjF+I/p65J1LOBhAsmOLcX0/CygKXz5qe
wyG16zNft6OWPIOBTs56NnNlW6EdqomxBM5SWr888qEjUy0ruUpAH4Ug8SloL+AeDW+TqUUcfoOiTi9
3ZJ/t9YRj0+wQw4vakpUTAgMBAAGjdTBzMAwGA1UdEwEB/wQCMAAwDgYDVR0PAQH/BAQDAgeAMBMGA1
UdJQQMMAoGCCsGAQUFBwMBMB0GA1UdDgQWBBTCubAbczcJE76YabOv+2oVV1zNSzAfBgNVHSMEGDAWg
BTjOAyk4w7B5FlRt417AmeHnFktfDANBgkqhkiG9w0BAQsFAAOCAQEAjW9ovWDgEoUi8DWwNVtudKiT
6ylJTSMqY7C+qJlRHpnZ64TNZFXI0BldYZr0QXGsZ257m9m9BiUcZr6UR0hywy4SiyxuteufniKIp9E
vqv0aJhdTXO+l5msaGWu7YvWYqXW0m3rA9oiNYyBcNSFzlwiyvztYUmFFPrvhFHVSt+DuxZSltdf78G
exS4YRMCTI+cuCfBt65Vkss4bNJH7kyWVc5aSQ/vKitMxB10gzsUa7psgS6LsBWxnehd3HKBPaHiWG9
ssHKhHJWfjifgz0K1Y0/vi33USPJ1cBhWWx/dolXWmSmpfqXpD3Q84YjVWIRnFpQzwbT650v/H+fwB1
zw==
"""

srv_private_key = """
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCtanizx0h1fEH0pMRBB7V7nUAnSOA
iCRUNpeTz6RoUqH0y/UaxM+kqitUm+MSAWxEJAXW4ZlxNzU+tC6DOwPd+7/rZsT6fKeCbMIs8Es9VaX
d2sZzb7DajEygeyIy1b3JGXIiNJ9KcOxzhmu5VHe+6qLCO3FDt4iFIrHXJxwQKm8qL6zgn7f9kboQYB
HKOhY8x+ghkhLYAwMlvIHGwjF+I/p65J1LOBhAsmOLcX0/CygKXz5qewyG16zNft6OWPIOBTs56NnNl
W6EdqomxBM5SWr888qEjUy0ruUpAH4Ug8SloL+AeDW+TqUUcfoOiTi93ZJ/t9YRj0+wQw4vakpUTAgM
BAAECggEAEa54SyBSb4QxYg/bYM636Y2G3oU229GK6il+4YMOy99tZeG0L6+IInR7DO5ddBbqSD2esq
QL3PTw9EcUvi/9AYjXeL3H5vOeo+7Rq4OMIfx5wp+Ty6AB5s5hD1kfG7AWzzzHwYNiHS2Gdtb/XldfO
5bP6xO5/rSenynSbWCTir8yakfoDenT12CXWzU+T10MKhoTXb/Uao+bMjziKEviK6OWq0vsLlDqyOAE
Va685s7T0vHTfSs+yK9pqVypHXbkH1nJCoi9P4pcJ4Sslc3meStv3bqg8T62Ufv8QkQLTfJyKZlR1aV
9ZjWT84YoH1XRnnkAZ+BMC267sHeBJbu6EQKBgQDbIUjQh/iPlkK77tFa//gSMD5ouJtuwtdS1MJ44p
C81A140vjpkSCdU8zWRifi+akR1k6fXCp6VFUFvTCXkGlpbD4TNjCCRJjS4SoQ89jEnePQ2iS59jkn3
V3OPNitOzk0jEm/x3R5wNdPlSX6+pLiUZAtMgcmCMv205VOkeqx8QKBgQDKmB3FtEfkKRrGkOJgaEkY
iXp9b0Uy8peBoTcdqMMnXSlm9+CfIdhSwbQDiAhEcUeCE/S6TDqaMS+ekKFfs6kDlaJMStGsy81lwr5
W/oZOldajDCu1CDInc+czkep10lsHdQwr71zXntiK3Fwq8Mr3ROBSpaH+DWIjILiQIOMzQwKBgQC7Mt
UUqIQUjkZWbG/XcMLJLwOxzLukRLlUXsQAJ3WEixczN/BDAKM/JB7ikq5yfdwMi+tAwqjbNn4n1/bSF
CGpWToyiWGpd9aimI6qStbNKSE9A47KeulbAAaqMFreqrB1Dr/WIRuFA9QsfXsjzLp8szcbFRj8ShmM
tDZiF8/K0QKBgQCYbb0wzESu8RJZRhddC/m7QWzsxXReMdI2UTLj2N8EVf7ZnzTc5h0Znu4vHgGCZWy
0/QjLxqDs9Ibsmcsg807+CG51UnHRvgFLSCvnzlcE943nXTfhXEpIDtdsoKO0hFHDGZjP0aeb/8LTL5
sVH9jGFIdnB4ILYMxuu6bBokzvewKBgBWbjPppjrM46bZ0rwEYCcG0F/k6TKkw4pjyrDR4B0XsrqTjK
0yz0ga7FHe10saeS2cXMqygdkjhWLZ6Zhrp0LAEzhEvdiBYeRH37J9Bvwo2YIHakox4hJCSXNnELs/A
GhUb5YIISNnZnZZeUD/Z0IJXJryjk9eUbhDCgEZRVzeT
"""


def get_config_value(key):
    tmp = read_file(STUNNEL_CONF)
    tmp = re.findall(f'\n?{key}\s+(.*)', tmp)
    return tmp


def read_config():
    config = {'global': {},
              'services': {}
              }
    service_pattern = re.compile(r'\[(.+?)\]')
    key_value_pattern = re.compile(r'(\S+)\s*=\s*(.+)')
    service = None

    for line in read_file(STUNNEL_CONF).split('\n'):
        line.strip()
        if not line or line.startswith(';'):
            continue
        if service_pattern.match(line):
            service = line.strip('[]')
            config['services'][service] = {}
        key_value_match = key_value_pattern.match(line)
        if key_value_match:
            key, value = key_value_match.group(1), key_value_match.group(2)
            if service:
                apply_value(config['services'][service], key, value)
            else:
                apply_value(config['global'], key, value)

    return config


def apply_value(service_config, key, value):
    if service_config.get(key) is None:
        service_config[key] = value
    else:
        if not isinstance(service_config[key], list):
            service_config[key] = [
                service_config[key]]
        else:
            service_config[key].append(value)


class TestServiceStunnel(VyOSUnitTestSHIM.TestCase):
    maxDiff = None
    @classmethod
    def setUpClass(cls):
        super(TestServiceStunnel, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)
        cls.is_valid_conf = True

    def tearDown(self):
        # Check for running process
        if self.is_valid_conf:
            self.assertTrue(process_named_running(PROCESS_NAME))
        self.is_valid_conf = True
        # delete testing Stunnel config
        self.cli_delete(base_path)
        self.cli_delete(['pki'])
        self.cli_commit()

        # Check for stopped process
        self.assertFalse(process_named_running(PROCESS_NAME))

    def set_pki(self):
        self.cli_set(['pki', 'ca', 'ca-1', 'certificate', ca_certificate.replace('\n','')])
        self.cli_set(['pki', 'ca', 'ca-1', 'private', 'key', ca_private_key.replace('\n','')])
        self.cli_set(['pki', 'certificate', 'srv-1', 'certificate', srv_certificate.replace('\n','')])
        self.cli_set(['pki', 'certificate', 'srv-1', 'private', 'key', srv_private_key.replace('\n','')])
        self.cli_commit()

    def test_01_stunnel_simple_client(self):
        service = 'app1'
        self.cli_set(base_path + ['client', service, 'connect', 'port', '9001'])

        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(base_path + ['client', service, 'listen', 'port', '8001'])

        self.cli_commit()
        config = read_config()

        self.assertEqual('/run/stunnel/stunnel.pid', config['global']['pid'])
        self.assertEqual('notice', config['global']['debug'])
        self.assertListEqual([service], list(config['services']))
        self.assertEqual('8001', config['services'][service]['accept'])
        self.assertEqual('9001', config['services'][service]['connect'])
        self.assertEqual('yes', config['services'][service]['client'])

    def test_02_stunnel_simple_server(self):
        service = 'ser1'
        self.set_pki()
        self.cli_set(base_path + ['server', service, 'connect', 'port', '8080'])
        self.cli_set(base_path + ['server', service, 'ssl', 'certificate', 'srv-1'])

        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(base_path + ['server', service, 'listen', 'port', '9001'])

        self.cli_commit()
        config = read_config()

        self.assertEqual('/run/stunnel/stunnel.pid', config['global']['pid'])
        self.assertEqual('notice', config['global']['debug'])
        self.assertListEqual([service], list(config['services']))
        self.assertEqual('9001', config['services'][service]['accept'])
        self.assertEqual('8080', config['services'][service]['connect'])
        self.assertIsNone(config['services'][service].get('client'))
        self.assertEqual('/run/stunnel/server-ser1-srv-1.pem', config['services'][service]['cert'])
        self.assertEqual('/run/stunnel/server-ser1-srv-1.pem.key', config['services'][service]['key'])

    def test_03_multy_services(self):
        self.set_pki()
        clients = ['app1', 'app2', 'app3']
        servers = ['serv1', 'serv2', 'serv3']
        port = 80
        for service in clients:
            port += 1
            self.cli_set(base_path + ['client', service, 'listen', 'port', f'{port}'])
            port += 1
            self.cli_set(base_path + ['client', service, 'connect', 'port', f'{port}'])
            if service == 'app2':
                self.cli_set(base_path + ['client', service, 'connect', 'address', f'192.168.0.10'])
                self.cli_set(base_path + ['client', service, 'listen', 'address', '127.0.0.1'])
                self.cli_set(base_path + ['client', service, 'protocol', 'connect'])
                self.cli_set(base_path + ['client', service, 'options', 'authentication', 'basic'])
                self.cli_set(base_path + ['client', service, 'options', 'domain', 'basic.com'])
                self.cli_set(base_path + ['client', service, 'options', 'host', 'address', '127.0.0.1'])
                self.cli_set(base_path + ['client', service, 'options', 'host', 'port', '5000'])
                self.cli_set(base_path + ['client', service, 'options', 'password', 'test_pass'])
                self.cli_set(base_path + ['client', service, 'options', 'username', 'test'])
            if service == 'app3':
                self.cli_set(base_path + ['client', service, 'ssl', 'ca-certificate', 'ca-1'])
                self.cli_set(base_path + ['client', service, 'ssl', 'certificate', 'srv-1'])

        for service in servers:
            port += 1
            self.cli_set(base_path + ['server', service, 'listen', 'port', f'{port}'])
            port += 1
            self.cli_set(base_path + ['server', service, 'connect', 'port', f'{port}'])
            self.cli_set(base_path + ['server', service, 'ssl', 'certificate', 'srv-1'])
            if service == 'serv2':
                self.cli_set(base_path + ['server', service, 'ssl', 'ca-certificate', 'ca-1'])
                self.cli_set(base_path + ['server', service, 'connect', 'address', f'google.com'])
                self.cli_set(base_path + ['server', service, 'listen', 'address', f'127.0.0.1'])
            if service == 'serv3':
                self.cli_set(base_path + ['server', service, 'connect', 'address', f'10.18.105.10'])
                self.cli_set(base_path + ['server', service, 'protocol', 'imap'])

        self.cli_commit()
        config = read_config()

        self.assertEqual('/run/stunnel/stunnel.pid', config['global']['pid'])
        self.assertListEqual(clients + servers, list(config['services']))
        self.assertDictEqual(config['services'], {
            'app1': {
                'client': 'yes',
                'accept': '81',
                'connect': '82'
            },
            'app2': {
                'client': 'yes',
                'accept': '127.0.0.1:83',
                'connect': '192.168.0.10:84',
                'protocol': 'connect',
                'protocolAuthentication': 'basic',
                'protocolDomain': 'basic.com',
                'protocolHost': '127.0.0.1:5000',
                'protocolPassword': 'test_pass',
                'protocolUsername': 'test'
            },
            'app3': {
                'client': 'yes',
                'accept': '85',
                'connect': '86',
                'CApath': '/run/stunnel/ca',
                'CAfile': 'client-app3-ca.pem',
                'cert': '/run/stunnel/client-app3-srv-1.pem',
                'key': '/run/stunnel/client-app3-srv-1.pem.key'
            },
            'serv1': {
                'accept': '87',
                'connect': '88',
                'cert': '/run/stunnel/server-serv1-srv-1.pem',
                'key': '/run/stunnel/server-serv1-srv-1.pem.key'
            },
            'serv2': {
                'accept': '127.0.0.1:89',
                'connect': 'google.com:90',
                'CApath': '/run/stunnel/ca',
                'CAfile': 'server-serv2-ca.pem',
                'cert': '/run/stunnel/server-serv2-srv-1.pem',
                'key': '/run/stunnel/server-serv2-srv-1.pem.key'
            },
            'serv3': {
                'accept': '91',
                'connect': '10.18.105.10:92',
                'protocol': 'imap',
                'cert': '/run/stunnel/server-serv3-srv-1.pem',
                'key': '/run/stunnel/server-serv3-srv-1.pem.key'
            }
        })

    def test_04_cert_problems(self):
        service = 'app1'
        self.cli_set(base_path + ['client', service, 'connect', 'port', '9001'])
        self.cli_set(base_path + ['client', service, 'listen', 'port', '8001'])
        self.cli_set(base_path + ['client', service, 'ssl', 'ca-certificate', 'ca-2'])

        # ca not exist in pki
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_delete(base_path + ['client', service, 'ssl', 'ca-certificate', 'ca-2'])
        self.cli_set(base_path + ['client', service, 'ssl', 'certificate', 'srv-2'])

        # cert not exist in pki
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(base_path)

        self.cli_set(base_path + ['server', service, 'connect', 'port', '8080'])
        self.cli_set(base_path + ['server', service, 'listen', 'port', '9001'])

        # Create server without any cert
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(base_path + ['server', service, 'ssl', 'ca-certificate', 'ca-2'])
        # ca not exist in pki
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_delete(base_path + ['server', service, 'ssl', 'ca-certificate', 'ca-2'])
        self.cli_set(base_path + ['server', service, 'ssl', 'certificate', 'srv-2'])
        # cert not exist in pki
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.is_valid_conf = False

    def test_05_psk_auth(self):
        modes = ['client', 'server']
        psk_id_1 = 'psk_id_1'
        psk_secret_1 = '1234567890ABCDEF1234567890ABCDEF'
        psk_id_2 = 'psk_id_2'
        psk_secret_2 = '1234567890ABCDEF1234567890ABCDEA'
        expected_config = {
            'global': {'pid': '/run/stunnel/stunnel.pid',
                       'debug': 'notice'},
            'services': {}}
        port = 8000
        for mode in modes:
            service = f'{mode}-one'
            psk_secrets = f'/run/stunnel/psk/{mode}_{service}.txt'
            expected_config['services'][service] = {
                'PSKsecrets': psk_secrets,
            }
            port += 1
            expected_config['services'][service]['accept'] = f'{port}'
            self.cli_set(base_path + [mode, service, 'listen', 'port', f'{port}'])
            port += 1
            expected_config['services'][service]['connect'] = f'{port}'
            self.cli_set(base_path + [mode, service, 'connect', 'port', f'{port}'])
            self.cli_set(base_path + [mode, service, 'psk', 'smoketest1', 'id', psk_id_1])
            with self.assertRaises(ConfigSessionError):
                self.cli_set(base_path + [mode, service, 'psk', 'smoketest1', 'secret', '123'])
            with self.assertRaises(ConfigSessionError):
                self.cli_set(base_path + [mode, service, 'psk', 'smoketest1', 'secret', '1234567890ABCDEF1234567890ABCDEZ'])
            self.cli_set(base_path + [mode, service, 'psk', 'smoketest1', 'secret', psk_secret_1])
            self.cli_set(base_path + [mode, service, 'psk', 'smoketest2', 'id', psk_id_2])
            self.cli_set(base_path + [mode, service, 'psk', 'smoketest2', 'secret', psk_secret_2])
            if mode != 'server':
                expected_config['services'][service]['client'] = 'yes'

            self.cli_commit()
            config = read_config()

            self.assertDictEqual(expected_config, config)

            self.assertListEqual([f'{psk_id_1}:{psk_secret_1}',
                                  f'{psk_id_2}:{psk_secret_2}'],
                [line for line in read_file(psk_secrets).split('\n')])

    def test_06_socks_proxy(self):
        server_port = '9001'
        client_port = '9000'
        srv_name = 'srv-one'
        cli_name = 'cli-one'
        expected_config = {
            'global': {'pid': '/run/stunnel/stunnel.pid',
                       'debug': 'notice'},
            'services': {
                'cli-one': {
                    'PSKsecrets': f'/run/stunnel/psk/client_{cli_name}.txt',
                    'client': 'yes',
                    'accept': client_port,
                    'connect': server_port
                },
                'srv-one': {
                    'PSKsecrets': f'/run/stunnel/psk/server_{srv_name}.txt',
                    'accept': server_port,
                    'protocol': 'socks'
                }
            }}

        self.cli_set(base_path + ['server', srv_name, 'listen', 'port', server_port])
        self.cli_set(base_path + ['server', srv_name, 'connect', 'port', '9005'])
        self.cli_set(base_path + ['server', srv_name, 'protocol', 'socks'])
        self.cli_set(base_path + ['server', srv_name, 'psk', 'sock_proxy', 'id', cli_name])
        self.cli_set(base_path + ['server', srv_name, 'psk', 'sock_proxy', 'secret', '1234567890ABCDEF1234567890ABCDEF'])

        self.cli_set(base_path + ['client', cli_name, 'listen', 'port', client_port])
        self.cli_set(base_path + ['client', cli_name, 'connect', 'port', server_port])
        self.cli_set(base_path + ['client', cli_name, 'psk', 'sock_proxy', 'id', cli_name])
        self.cli_set(base_path + ['client', cli_name, 'psk', 'sock_proxy', 'secret', '1234567890ABCDEF1234567890ABCDEF'])

        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_delete(base_path + ['server', srv_name, 'connect'])
        self.cli_commit()
        config = read_config()

        self.assertDictEqual(expected_config, config)

    def test_07_available_port(self):
        expected_config = {
            'global': {'pid': '/run/stunnel/stunnel.pid',
                       'debug': 'notice'},
            'services': {
                'app1': {
                    'client': 'yes',
                    'accept': '8001',
                    'connect': '9001'
                },
                'srv1': {
                    'PSKsecrets': f'/run/stunnel/psk/server_srv1.txt',
                    'accept': '127.0.0.1:8002',
                    'connect': '9001'
                }
            }}
        self.cli_set(base_path + ['client', 'app1', 'connect', 'port', '9001'])
        self.cli_set(base_path + ['client', 'app1', 'listen', 'port', '8001'])

        self.cli_set(base_path + ['server', 'srv1', 'connect', 'port', '9001'])
        self.cli_set(base_path + ['server', 'srv1', 'listen', 'address',
                                  '127.0.0.1'])
        self.cli_set(base_path + ['server', 'srv1', 'listen', 'port', '8001'])
        self.cli_set(base_path + ['server', 'srv1', 'psk', 'smoketest1',
                                  'id', 'foo'])
        self.cli_set(base_path + ['server', 'srv1', 'psk', 'smoketest1',
                                  'secret', '1234567890ABCDEF1234567890ABCDEF'])

        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(base_path + ['server', 'srv1', 'listen', 'port', '8002'])
        self.cli_commit()

        config = read_config()
        self.assertDictEqual(expected_config, config)

    def test_08_two_endpoints(self):
        expected_config = {
            'global': {'pid': '/run/stunnel/stunnel.pid',
                       'debug': 'notice'},
            'services': {
                'app1': {
                    'client': 'yes',
                    'accept': '8001',
                    'connect': '9001'
                }
            }}

        self.cli_set(base_path + ['client', 'app1', 'listen', 'port', '8001'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(base_path + ['client', 'app1', 'connect', 'port', '9001'])
        self.cli_commit()

        config = read_config()
        self.assertDictEqual(expected_config, config)

    def test_09_pki_still_used(self):
        service = 'ser1'
        self.set_pki()
        self.cli_set(base_path + ['server', service, 'connect', 'port', '8080'])
        self.cli_set(base_path + ['server', service, 'listen', 'port', '9001'])
        self.cli_set(base_path + ['server', service, 'ssl', 'certificate', 'srv-1'])
        self.cli_commit()

        self.cli_delete(['pki'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_delete(base_path)
        self.cli_commit()

        self.is_valid_conf = False

    def test_99_protocols(self):
        self.set_pki()
        service = 'one'
        proto_address = 'google.com'
        proto_port = '80'
        modes = ['client', 'server']
        protocols = ['cifs', 'connect', 'imap', 'nntp', 'pgsql', 'pop3',
                     'proxy', 'smtp', 'socks']
        options = ['authentication', 'domain', 'host', 'password', 'username']

        for protocol in protocols:
            for mode in modes:
                expected_config = {
                    'global': {'pid': '/run/stunnel/stunnel.pid',
                               'debug': 'notice'},
                    'services': {'one': {
                        'accept': '8001',
                        'protocol': protocol,
                    }}}
                if not(mode == 'server' and protocol == 'socks'):
                    self.cli_set(base_path + [mode, service, 'connect', 'port', '9001'])
                    expected_config['services']['one']['connect'] = '9001'
                self.cli_set(base_path + [mode, service, 'listen', 'port', '8001'])

                if mode == 'server':
                    expected_config['services'][service]['cert'] = '/run/stunnel/server-one-srv-1.pem'
                    expected_config['services'][service]['key'] = '/run/stunnel/server-one-srv-1.pem.key'
                    self.cli_set(base_path + [mode, service, 'ssl',
                                              'certificate', 'srv-1'])
                else:
                    expected_config['services'][service]['client'] = 'yes'

                # protocols connect and nntp is only supported in client mode.
                if mode == 'server' and protocol in ['connect', 'nntp']:
                    with self.assertRaises(ConfigSessionError):
                        self.cli_set(base_path + [mode, service, 'protocol', protocol])
                        # self.cli_commit()
                else:
                    self.cli_set(base_path + [mode, service, 'protocol', protocol])
                    self.cli_commit()
                    config = read_config()

                    self.assertDictEqual(expected_config, config)

                expected_config['services'][service]['protocolDomain'] = 'valdomain'
                expected_config['services'][service]['protocolPassword'] = 'valpassword'
                expected_config['services'][service]['protocolUsername'] = 'valusername'

                for option in options:
                    if option == 'authentication':
                        expected_config['services'][service]['protocolAuthentication'] = \
                            'basic' if protocol == 'connect' else 'plain'
                        continue

                    if option == 'host' and mode != 'server':
                        expected_config['services'][service]['protocolHost'] = \
                            f'{proto_address}:{proto_port}'
                        self.cli_set(base_path + [mode, service, 'options',
                                         option, 'address', f'{proto_address}'])
                        self.cli_set(base_path + [mode, service, 'options',
                                                  option, 'port', f'{proto_port}'])
                        continue
                    if mode == 'server':
                        with self.assertRaises(ConfigSessionError):
                            self.cli_set(
                                base_path + [mode, service, 'options', option, f'val{option}'])
                    else:
                        self.cli_set(
                            base_path + [mode, service, 'options', option, f'val{option}'])
                # Additional option is only supported in the 'connect' and 'smtp' protocols.
                if mode != 'server':
                    if protocol not in ['connect', 'smtp']:
                        with self.assertRaises(ConfigSessionError):
                            self.cli_commit()
                    else:
                        if protocol == 'smtp':
                            # Protocol smtp does not support options domain and host
                            with self.assertRaises(ConfigSessionError):
                                self.cli_commit()

                            self.cli_delete(
                                base_path + [mode, service, 'options', 'domain'])
                            self.cli_delete(
                                base_path + [mode, service, 'options', 'host'])
                            del expected_config['services'][service]['protocolDomain']
                            del expected_config['services'][service]['protocolHost']

                        self.cli_commit()
                        config = read_config()

                        self.assertDictEqual(expected_config, config)

                self.cli_delete(base_path)
                self.cli_commit()

        self.is_valid_conf = False


if __name__ == '__main__':
    unittest.main(verbosity=2)
