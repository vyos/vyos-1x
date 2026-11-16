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

import unittest

from base_vyostest_shim import VyOSUnitTestSHIM
from vyos.configsession import ConfigSessionError

from vyos.pki import create_certificate
from vyos.pki import create_certificate_request
from vyos.pki import encode_certificate
from vyos.pki import encode_public_key
from vyos.pki import load_private_key
from vyos.utils.file import read_file

base_path = ['pki']

valid_ca_cert = """
MIIDgTCCAmmgAwIBAgIUeM0mATGs+sKF7ViBM6DEf9fQ19swDQYJKoZIhvcNAQEL
BQAwVzELMAkGA1UEBhMCR0IxEzARBgNVBAgMClNvbWUtU3RhdGUxEjAQBgNVBAcM
CVNvbWUtQ2l0eTENMAsGA1UECgwEVnlPUzEQMA4GA1UEAwwHVnlPUyBDQTAeFw0y
MTA2MjgxMzE2NDZaFw0yNjA2MjcxMzE2NDZaMFcxCzAJBgNVBAYTAkdCMRMwEQYD
VQQIDApTb21lLVN0YXRlMRIwEAYDVQQHDAlTb21lLUNpdHkxDTALBgNVBAoMBFZ5
T1MxEDAOBgNVBAMMB1Z5T1MgQ0EwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEK
AoIBAQDK98WwZIqgC6teHPSsyKLLRtboy55aisJN0D3iHJ8WGKkDmIrdCR2LI4J5
C82ErfPOzl4Ck4vTmqh8wnuK/dhUxxzNdFJBMPHAe/E+UawYrubtJj5g8iHYowZJ
T5HQKnZbcqlPvl6EizA+etO48WGljKhpimj9/LVTp81+BtFNP4tJ/vOl+iqyJ0+P
xiqQNDJgAF18meQRKaT9CcXycsciG9snMlB1tdOR7KDbi8lJ86lOi5ukPJaiMgWE
u4UlyFVyHJ/68NvtwRhYerMoQquqDs21OXkOd8spZL6qEsxMeK8InedA7abPaxgx
ORpHguPQV4Ib5HBH9Chdb9zBMheZAgMBAAGjRTBDMA8GA1UdEwEB/wQFMAMBAf8w
IAYDVR0lAQH/BBYwFAYIKwYBBQUHAwIGCCsGAQUFBwMBMA4GA1UdDwEB/wQEAwIB
hjANBgkqhkiG9w0BAQsFAAOCAQEAbwJZifMEDbrKPQfGLp7ZA1muM728o4EYmmE7
9eWwH22wGMSZI7T2xr5zRlFLs+Jha917yQK4b5xBMjQRAJlHKjzNLJ+3XaGlnWja
TBJ2SC5YktrmXRAIS7PxTRk/r1bHs/D00+sEWewbFYr8Js4a1Cv4TksTNyjHx8pv
phA+KIx/4qdojTslz+oH/cakUz0M9fh2B2xsO4bab5vX+LGLCK7jjeAL4Zyjf1hD
yx+Ri79L5N8h4Q69fER4cIkW7KVKUOyjEg3N4ST56urdycmyq9bXFz5pRxuZLInA
6RRToJrL8i0aPLJ6SyMujfREfjqOxdW5vyNF5/RkY+5Nz8JMgQ==
"""

valid_ca_private_key = """
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDK98WwZIqgC6te
HPSsyKLLRtboy55aisJN0D3iHJ8WGKkDmIrdCR2LI4J5C82ErfPOzl4Ck4vTmqh8
wnuK/dhUxxzNdFJBMPHAe/E+UawYrubtJj5g8iHYowZJT5HQKnZbcqlPvl6EizA+
etO48WGljKhpimj9/LVTp81+BtFNP4tJ/vOl+iqyJ0+PxiqQNDJgAF18meQRKaT9
CcXycsciG9snMlB1tdOR7KDbi8lJ86lOi5ukPJaiMgWEu4UlyFVyHJ/68NvtwRhY
erMoQquqDs21OXkOd8spZL6qEsxMeK8InedA7abPaxgxORpHguPQV4Ib5HBH9Chd
b9zBMheZAgMBAAECggEAa/CK5L0DcAvkrd9OS9lDokFhJ1qqM1KZ9NHrJyW7gP/K
Wow0RUqEuKtAxuj8+jOcdn4PRuV6tiUIt5iiJQ/MjYF6ktTqrZq+5nPDnzXGBTZ2
vuXYxKvgThqczD4RuJfsa8O1wR/nmit/k6q0kCVmnakJI1+laHWNZRjXUs+DXcWb
rUN5D4/5kyjvFilH1c8arfrO2O4DcwfX1zNbxicgYrGmjE5m6WCZKWdcgpBcIQSh
ZfNATfXIEZ16WmDIFZnuOEUtFAzweR2ataLQNoyaTUeEe6g+ZDtUQIGKR/f0+Z4T
/JMJfPX/vRn0l3nRJWWC7Okpa2xb0hVdBmS/op+TNQKBgQDvNGAkS4uUx8xw724k
zCKQJRnzR80AQ6b2FoqRbAevWm+i0ntsCMyvCItAQS8Bw+9fgITvsmd9SdYPncMQ
Z1oQYPk5yso/SPUyuNPXtygDxUP1xS1yja5MObqyrq2O2EzcxiVxEHGlZMLTNxNA
1tE8nF4c0nQpV/EfLtkQFnnUSwKBgQDZOA2hiLaiDlPj03S4UXDu6aUD2o07782C
UKl6A331ZhH/8zGEiUvBKg8IG/2FyCHQDC0C6rbfoarAhrRGbDHKkDTKNmThTj+I
YBkLt/5OATvqkEw8eL0nB+PY5JKH04/jE0F/YM/StUsgxvMCVhtp0u/d2Hq4V9sk
xah6oFbtKwKBgGEvs3wroWtyffLIpMSYl9Ze7Js2aekYk4ZahDQvYzPwl3jc8b5k
GN1oqEMT+MhL1j7EFb7ZikiSLkGsBGvuwd3zuG6toNxzhQP1qkRzqvNVO5ZoZV2s
iMt5jQw6AlQON7RfYSj92F6tgKaWMuFeJibtFSO6se12SIY134U0zIzfAoGAQWF7
yNkrj4+cdICbKzdoNKEiyAwqYpYFV2oL+OvAJ/L3DAEZMHla0eNk7t3t6yyX8NUZ
Xz1imeFBUf25mVDLk9rf6NWCe8ZfnR6/qyVQaA47CJkyOSlmVa8sR4ZVDIkDUCfl
mP98zkE/QbhgQJ3GVo3lIPMdzQq0rVbJJU/Jmk0CgYEAtHRNaoKBsxKfb7N7ewla
MzwcULIORODjWM8MUXM+R50F/2uYMiTvpz6eIUVfXoFyQoioYI8kcDZ8NamiQIS7
uZsHfKpgMDJkV3kOoZQusoDhasGQ0SOnxbz/y0XmNUtAePipH0jPY1SYUvWbvm2y
a4aWVhBFly9hi2ZeHiVxVhk=
"""

valid_cert = """
MIIB9zCCAZygAwIBAgIUQ5G1nyASL/YsKGyLNGhRPPQyo4kwCgYIKoZIzj0EAwIw
XjELMAkGA1UEBhMCR0IxEzARBgNVBAgMClNvbWUtU3RhdGUxEjAQBgNVBAcMCVNv
bWUtQ2l0eTENMAsGA1UECgwEVnlPUzEXMBUGA1UEAwwOVnlPUyBUZXN0IENlcnQw
HhcNMjEwNjI4MTMyNjIyWhcNMjIwNjI4MTMyNjIyWjBeMQswCQYDVQQGEwJHQjET
MBEGA1UECAwKU29tZS1TdGF0ZTESMBAGA1UEBwwJU29tZS1DaXR5MQ0wCwYDVQQK
DARWeU9TMRcwFQYDVQQDDA5WeU9TIFRlc3QgQ2VydDBZMBMGByqGSM49AgEGCCqG
SM49AwEHA0IABBsebIt+8rr2UysTpL8NnYUtmt47e3sC3H9IO8iI/N4uFrmGVgTL
E2G+RDGzZgG/r7LviJSTuE9HX7wHLcIr0SmjODA2MAwGA1UdEwEB/wQCMAAwFgYD
VR0lAQH/BAwwCgYIKwYBBQUHAwEwDgYDVR0PAQH/BAQDAgeAMAoGCCqGSM49BAMC
A0kAMEYCIQD5xK5kdC3TJ7SZrBGvzIM7E7Cil/KZJUyQDR9eFNNZVQIhALg8DTfr
wAawf8L+Ncjn/l2gd5cB0nGij0D7uYnm3zf/
"""

valid_dh_params = """
MIIBCAKCAQEAnNldZCrJk5MxhFoUlvvaYmUO+TmtL0uL62H2RIHJ+O0R+8vzdGPh
6zDAzo46EJK735haUgu8+A1RTsXDOXcwBqDlVe0hYj9KaPHz1HpfNKntpoPCJAYJ
wiH8dd5zVMH+iBwEKlrfteV9vWHn0HUxgLJFSLp5o6y0qpKPREJu6k0XguGScrPa
Iw6RUwsoDy3unHfk+YeC0o040R18F75V1mXWTjQlEgM7ZO2JZkLGkhW30jB0vSHr
krFqOvtPUiyG7r3+j18IUYLTN0s+5FOCfCjvSVKibNlB1vUz5y/9Ve8roctpkRM/
5R5FA0mtbl7U/yMSX4FRIQ/A9BlHiu4bowIBAg==
"""
valid_public_ec_key = """
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEAoInInwjlu/3+wDqvRa/Eyg3EMvB
pPyq2v4jqEtEh2n4lOCi7ZgNjr+1sQSvrn8mccpALYl3/RKOougC5oQzCg==
"""

valid_private_rsa_key = """
MIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQDDoAVyJPpcLBFs
2NdS1qMOSj7mwKBKVZiBN3nqbLiOvEHbVe22UMNvUFU3sGs2Ta2zXwhPF3d6vPPs
GlYTkO3XAffMSNXhjCsvWHiIOR4JrWf598Bpt+txBsxsa12kM3/HM7RDf3zdN2gT
twzrcWzu+zOTXlqJ2OSq/BRRZO9IMbQLQ1/h42GJHEr4THnY4zDqUjmMmIuiBXn4
xoE4KFLH1+xPTVleeKvPPeJ1wsshoUjlXYOgcsrXasDUt5gtkkXsVQwR9Lvbh+Rc
BhT+tJmrX9Cwq4YAd3tLSNJARS9HanRZ8uV0RTyZsImdw1Fr5ySpG2oEp/Z5mbL6
QYqDmQ+DAgMBAAECggEAGu7qMQf0TEJo98J3CtmwQ2Rnep+ksfdM8uVvbJ4hXs1+
h7Mx8jr2XVoDEZLBgA17z8lSvIjvkz92mdgaZ8E5bbPAqSiSAeapf3A/0AmFIDH2
scyxehyvVrVn6blygAvzGLr+o5hm2ZIqSySVq8jHBbQiKrT/5CCvgvcH2Rj7dMXd
T5lL73tCRJZsgvFNlxyj4Omj9Lh7SjL+tIwEQaLFbvANXrZ/BPyw4OlK8daBNg9b
5GvJSDitAVMgDEEApGYu1iNwMM4UJSQAC27eJdr+qJO6DDqktWOyWcyXrxJ9mDVK
FNbb9QNQZDj7bFfm6rCuSdH9yYe3vly+SNJqtyCiwQKBgQDvemt/57KiwQffmoKR
65NAZsQvmA4PtELYOV8NPeYH1BZN/EPmCc74iELJdQPFDYy903aRJEPGt7jfqprd
PexLwt73P/XiUjPrsbqgJqfF/EMiczxAktyW3xBt2lIWU1MUUmO1ps+ZZEg8Ks4e
K/3+FWqbwZ8drDBUT9BthUA0oQKBgQDRHxU6bu938PGweFJcIG6U21nsYaWiwCiT
LXA5vWZ+UEqz81BUye6tIcCDgeku3HvC/0ycvrBM9F4AZCjnnEvrAJHKl6e4j+C4
IpghGQvRvQ9ihDs9JIHnaoUC1i8dE3ISbbp1r7CN+J/HnAC2OeECMJuffXdnkVWa
xRdxU+9towKBgCwFVeNyJO00DI126o+GPVA2U9Pn4JXUbgEvMqDNgw5nVx5Iw/Zy
USBwc85yexnq7rcqOv5dKzRJK2u6AbOvoVMf5DqRAFL1B2RJDGRKFscXIwQfKLE6
DeCR6oQ3AKXn9TqkFn4axsiMnZapy6/SKGNfbnRpOCWNNGkbLtYjC3VhAoGAN0kO
ZapaaM0sOEk3DOAOHBB5j4KpNYOztmU23Cz0YcR8W2KiBCh2jxLzQFEiAp+LoJu5
9156YX3hNB1GqySo9XHrGTJKxwJSmJucuHNUqphe7t6igqGaLkH89CkHv5oaeEDG
IMLX3FC0fSMDFSnsEJYlLl8PKDRF+2rLrcxQ6h0CgYAZllNu8a7tE6cM6QsCILQn
NjuLuZRX8/KYWRqBJxatwZXCcMe2jti1HKTVVVCyYffOFa1QcAjCPknAmAz80l3e
g6a75NnEXo0J6YLAOOxd8fD2/HidhbceCmTF+3msidIzCsBidBkgn6V5TXx2IyMS
xGsJxVHfSKeooUQn6q76sg==
"""

valid_update_cert = """
MIICJTCCAcugAwIBAgIUZJqjNmPfVQwePjNFBtB6WI31ThMwCgYIKoZIzj0EAwIw
VzELMAkGA1UEBhMCR0IxEzARBgNVBAgMClNvbWUtU3RhdGUxEjAQBgNVBAcMCVNv
bWUtQ2l0eTENMAsGA1UECgwEVnlPUzEQMA4GA1UEAwwHdnlvcy5pbzAeFw0yMjA1
MzExNTE3NDlaFw0yMzA1MzExNTE3NDlaMFcxCzAJBgNVBAYTAkdCMRMwEQYDVQQI
DApTb21lLVN0YXRlMRIwEAYDVQQHDAlTb21lLUNpdHkxDTALBgNVBAoMBFZ5T1Mx
EDAOBgNVBAMMB3Z5b3MuaW8wWTATBgcqhkjOPQIBBggqhkjOPQMBBwNCAAQMe0h/
3CdD8mEgy+klk55QfJ8R3ZycefxCn4abWjzTXz/TuCIxqb4wpRT8DZtIn4NRimFT
mODYdEDOYxFtZm37o3UwczAMBgNVHRMBAf8EAjAAMA4GA1UdDwEB/wQEAwIHgDAT
BgNVHSUEDDAKBggrBgEFBQcDAjAdBgNVHQ4EFgQUqH7KSZpzArpMFuxLXqI8e1QD
fBkwHwYDVR0jBBgwFoAUqH7KSZpzArpMFuxLXqI8e1QDfBkwCgYIKoZIzj0EAwID
SAAwRQIhAKofUgRtcUljmbubPF6sqHtn/3TRvuafl8VfPbk3s2bJAiBp3Q1AnU/O
i7t5FGhCgnv5m8DW2F3LZPCJdW4ELQ3d9A==
"""

valid_update_private_key = """
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgvyODf22w/p7Zgfz9
dyLIT09LqLOrUN6zbAecfukiiiyhRANCAAQMe0h/3CdD8mEgy+klk55QfJ8R3Zyc
efxCn4abWjzTXz/TuCIxqb4wpRT8DZtIn4NRimFTmODYdEDOYxFtZm37
"""

rsa_8192_private_key = """
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
UUNfGzkQsPtH9QXI1fn6Miv72g14MA==
"""

rsa_8448_private_key = """
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
ZbUdb8YULvdf+ATwDZSv6xJYM/pv3xI=
"""

def rsa_material(private_key):
    """Certificate, public and private key built on the same RSA key, in the
    single line form the CLI expects"""
    def body(pem):
        return ''.join(pem.strip().splitlines()[1:-1])

    private_key = private_key.replace('\n', '')
    key = load_private_key(private_key)
    subject = {
        'country': 'GB',
        'state': 'Some-State',
        'locality': 'Some-City',
        'organization': 'VyOS',
        'common_name': 'VyOS Test',
    }
    request = create_certificate_request(subject, key)
    cert = create_certificate(request, request, key, valid_days=365, is_ca=True)
    return {
        'certificate': body(encode_certificate(cert)),
        'public': body(encode_public_key(key.public_key())),
        'private': private_key,
    }

class TestPKI(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestPKI, cls).setUpClass()
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)
        cls.cli_delete(cls, ['load-balancing', 'haproxy'])
        cls.cli_delete(cls, ['service', 'https'])

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()
        # always forward to base class
        super().tearDown()

    def test_valid_pki(self):
        # Valid CA
        self.cli_set(base_path + ['ca', 'smoketest', 'certificate', valid_ca_cert.replace('\n','')])
        self.cli_set(base_path + ['ca', 'smoketest', 'private', 'key', valid_ca_private_key.replace('\n','')])

        # Valid cert
        self.cli_set(base_path + ['certificate', 'smoketest', 'certificate', valid_cert.replace('\n','')])

        # Valid DH
        self.cli_set(base_path + ['dh', 'smoketest', 'parameters', valid_dh_params.replace('\n','')])

        # Valid public key
        self.cli_set(base_path + ['key-pair', 'smoketest', 'public', 'key', valid_public_ec_key.replace('\n','')])

        # Valid private key
        self.cli_set(base_path + ['key-pair', 'smoketest1', 'private', 'key', valid_private_rsa_key.replace('\n','')])
        self.cli_commit()

    def test_invalid_ca_valid_certificate(self):
        self.cli_set(base_path + ['ca', 'invalid-ca', 'certificate', valid_cert.replace('\n','')])

        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

    def test_certificate_in_use(self):
        cert_name = 'smoketest'

        self.cli_set(base_path + ['certificate', cert_name, 'certificate', valid_ca_cert.replace('\n','')])
        self.cli_set(base_path + ['certificate', cert_name, 'private', 'key', valid_ca_private_key.replace('\n','')])
        self.cli_commit()

        self.cli_set(['service', 'https', 'certificates', 'certificate', cert_name])
        self.cli_commit()

        self.cli_delete(base_path + ['certificate', cert_name])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_delete(['service', 'https', 'certificates', 'certificate'])

    def test_certificate_https_update(self):
        cert_name = 'smoke-test_foo'
        cert_path = f'/run/nginx/certs/{cert_name}_cert.pem'
        self.cli_set(base_path + ['certificate', cert_name, 'certificate', valid_ca_cert.replace('\n','')])
        self.cli_set(base_path + ['certificate', cert_name, 'private', 'key', valid_ca_private_key.replace('\n','')])
        self.cli_commit()

        self.cli_set(['service', 'https', 'certificates', 'certificate', cert_name])
        self.cli_commit()

        cert_data = None

        cert_data = read_file(cert_path)

        self.cli_set(base_path + ['certificate', cert_name, 'certificate', valid_update_cert.replace('\n','')])
        self.cli_set(base_path + ['certificate', cert_name, 'private', 'key', valid_update_private_key.replace('\n','')])
        self.cli_commit()

        self.assertNotEqual(cert_data, read_file(cert_path))

        self.cli_delete(['service', 'https', 'certificates', 'certificate'])

    def test_certificate_eapol_update(self):
        cert_name = 'eapol'
        interface = 'eth1'
        self.cli_set(base_path + ['certificate', cert_name, 'certificate', valid_ca_cert.replace('\n','')])
        self.cli_set(base_path + ['certificate', cert_name, 'private', 'key', valid_ca_private_key.replace('\n','')])
        self.cli_commit()

        self.cli_set(['interfaces', 'ethernet', interface, 'eapol', 'certificate', cert_name])
        self.cli_commit()

        cert_data = None

        with open(f'/run/wpa_supplicant/{interface}_cert.pem') as f:
            cert_data = f.read()

        self.cli_set(base_path + ['certificate', cert_name, 'certificate', valid_update_cert.replace('\n','')])
        self.cli_set(base_path + ['certificate', cert_name, 'private', 'key', valid_update_private_key.replace('\n','')])
        self.cli_commit()

        with open(f'/run/wpa_supplicant/{interface}_cert.pem') as f:
            self.assertNotEqual(cert_data, f.read())

        self.cli_delete(['interfaces', 'ethernet', interface, 'eapol'])

    def test_rsa_key_size(self):
        paths = [
            (['ca', 'smoketest', 'certificate'], 'certificate'),
            (['ca', 'smoketest', 'private', 'key'], 'private'),
            (['certificate', 'smoketest', 'certificate'], 'certificate'),
            (['certificate', 'smoketest', 'private', 'key'], 'private'),
            (['key-pair', 'smoketest', 'public', 'key'], 'public'),
            (['key-pair', 'smoketest', 'private', 'key'], 'private'),
        ]

        material = rsa_material(rsa_8192_private_key)
        for path, kind in paths:
            self.cli_set(base_path + path + [material[kind]])
        self.cli_commit()

        self.cli_delete(base_path)
        self.cli_commit()

        material = rsa_material(rsa_8448_private_key)
        for path, kind in paths:
            self.cli_set(base_path + path + [material[kind]])
            with self.assertRaises(ConfigSessionError) as e:
                self.cli_commit()
            self.assertIn('RSA key size of 8448 bit', ' '.join(str(e.exception).split()))
            self.cli_discard()

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
