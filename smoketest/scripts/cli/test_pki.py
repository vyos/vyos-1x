#!/usr/bin/env python3
#
# Copyright (C) 2021-2024 VyOS maintainers and contributors
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

class TestPKI(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestPKI, cls).setUpClass()
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)
        cls.cli_delete(cls, ['service', 'https'])

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

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

if __name__ == '__main__':
    unittest.main(verbosity=2)
