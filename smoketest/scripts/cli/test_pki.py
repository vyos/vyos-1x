#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
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
from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError

base_path = ['pki']

valid_ca_cert = 'MIIDgTCCAmmgAwIBAgIUeM0mATGs+sKF7ViBM6DEf9fQ19swDQYJKoZIhvcNAQELBQAwVzELMAkGA1UEBhMCR0IxEzARBgNVBAgMClNvbWUtU3RhdGUxEjAQBgNVBAcMCVNvbWUtQ2l0eTENMAsGA1UECgwEVnlPUzEQMA4GA1UEAwwHVnlPUyBDQTAeFw0yMTA2MjgxMzE2NDZaFw0yNjA2MjcxMzE2NDZaMFcxCzAJBgNVBAYTAkdCMRMwEQYDVQQIDApTb21lLVN0YXRlMRIwEAYDVQQHDAlTb21lLUNpdHkxDTALBgNVBAoMBFZ5T1MxEDAOBgNVBAMMB1Z5T1MgQ0EwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQDK98WwZIqgC6teHPSsyKLLRtboy55aisJN0D3iHJ8WGKkDmIrdCR2LI4J5C82ErfPOzl4Ck4vTmqh8wnuK/dhUxxzNdFJBMPHAe/E+UawYrubtJj5g8iHYowZJT5HQKnZbcqlPvl6EizA+etO48WGljKhpimj9/LVTp81+BtFNP4tJ/vOl+iqyJ0+PxiqQNDJgAF18meQRKaT9CcXycsciG9snMlB1tdOR7KDbi8lJ86lOi5ukPJaiMgWEu4UlyFVyHJ/68NvtwRhYerMoQquqDs21OXkOd8spZL6qEsxMeK8InedA7abPaxgxORpHguPQV4Ib5HBH9Chdb9zBMheZAgMBAAGjRTBDMA8GA1UdEwEB/wQFMAMBAf8wIAYDVR0lAQH/BBYwFAYIKwYBBQUHAwIGCCsGAQUFBwMBMA4GA1UdDwEB/wQEAwIBhjANBgkqhkiG9w0BAQsFAAOCAQEAbwJZifMEDbrKPQfGLp7ZA1muM728o4EYmmE79eWwH22wGMSZI7T2xr5zRlFLs+Jha917yQK4b5xBMjQRAJlHKjzNLJ+3XaGlnWjaTBJ2SC5YktrmXRAIS7PxTRk/r1bHs/D00+sEWewbFYr8Js4a1Cv4TksTNyjHx8pvphA+KIx/4qdojTslz+oH/cakUz0M9fh2B2xsO4bab5vX+LGLCK7jjeAL4Zyjf1hDyx+Ri79L5N8h4Q69fER4cIkW7KVKUOyjEg3N4ST56urdycmyq9bXFz5pRxuZLInA6RRToJrL8i0aPLJ6SyMujfREfjqOxdW5vyNF5/RkY+5Nz8JMgQ=='
valid_ca_private_key = 'MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDK98WwZIqgC6teHPSsyKLLRtboy55aisJN0D3iHJ8WGKkDmIrdCR2LI4J5C82ErfPOzl4Ck4vTmqh8wnuK/dhUxxzNdFJBMPHAe/E+UawYrubtJj5g8iHYowZJT5HQKnZbcqlPvl6EizA+etO48WGljKhpimj9/LVTp81+BtFNP4tJ/vOl+iqyJ0+PxiqQNDJgAF18meQRKaT9CcXycsciG9snMlB1tdOR7KDbi8lJ86lOi5ukPJaiMgWEu4UlyFVyHJ/68NvtwRhYerMoQquqDs21OXkOd8spZL6qEsxMeK8InedA7abPaxgxORpHguPQV4Ib5HBH9Chdb9zBMheZAgMBAAECggEAa/CK5L0DcAvkrd9OS9lDokFhJ1qqM1KZ9NHrJyW7gP/KWow0RUqEuKtAxuj8+jOcdn4PRuV6tiUIt5iiJQ/MjYF6ktTqrZq+5nPDnzXGBTZ2vuXYxKvgThqczD4RuJfsa8O1wR/nmit/k6q0kCVmnakJI1+laHWNZRjXUs+DXcWbrUN5D4/5kyjvFilH1c8arfrO2O4DcwfX1zNbxicgYrGmjE5m6WCZKWdcgpBcIQShZfNATfXIEZ16WmDIFZnuOEUtFAzweR2ataLQNoyaTUeEe6g+ZDtUQIGKR/f0+Z4T/JMJfPX/vRn0l3nRJWWC7Okpa2xb0hVdBmS/op+TNQKBgQDvNGAkS4uUx8xw724kzCKQJRnzR80AQ6b2FoqRbAevWm+i0ntsCMyvCItAQS8Bw+9fgITvsmd9SdYPncMQZ1oQYPk5yso/SPUyuNPXtygDxUP1xS1yja5MObqyrq2O2EzcxiVxEHGlZMLTNxNA1tE8nF4c0nQpV/EfLtkQFnnUSwKBgQDZOA2hiLaiDlPj03S4UXDu6aUD2o07782CUKl6A331ZhH/8zGEiUvBKg8IG/2FyCHQDC0C6rbfoarAhrRGbDHKkDTKNmThTj+IYBkLt/5OATvqkEw8eL0nB+PY5JKH04/jE0F/YM/StUsgxvMCVhtp0u/d2Hq4V9skxah6oFbtKwKBgGEvs3wroWtyffLIpMSYl9Ze7Js2aekYk4ZahDQvYzPwl3jc8b5kGN1oqEMT+MhL1j7EFb7ZikiSLkGsBGvuwd3zuG6toNxzhQP1qkRzqvNVO5ZoZV2siMt5jQw6AlQON7RfYSj92F6tgKaWMuFeJibtFSO6se12SIY134U0zIzfAoGAQWF7yNkrj4+cdICbKzdoNKEiyAwqYpYFV2oL+OvAJ/L3DAEZMHla0eNk7t3t6yyX8NUZXz1imeFBUf25mVDLk9rf6NWCe8ZfnR6/qyVQaA47CJkyOSlmVa8sR4ZVDIkDUCflmP98zkE/QbhgQJ3GVo3lIPMdzQq0rVbJJU/Jmk0CgYEAtHRNaoKBsxKfb7N7ewlaMzwcULIORODjWM8MUXM+R50F/2uYMiTvpz6eIUVfXoFyQoioYI8kcDZ8NamiQIS7uZsHfKpgMDJkV3kOoZQusoDhasGQ0SOnxbz/y0XmNUtAePipH0jPY1SYUvWbvm2ya4aWVhBFly9hi2ZeHiVxVhk='
valid_cert = 'MIIB9zCCAZygAwIBAgIUQ5G1nyASL/YsKGyLNGhRPPQyo4kwCgYIKoZIzj0EAwIwXjELMAkGA1UEBhMCR0IxEzARBgNVBAgMClNvbWUtU3RhdGUxEjAQBgNVBAcMCVNvbWUtQ2l0eTENMAsGA1UECgwEVnlPUzEXMBUGA1UEAwwOVnlPUyBUZXN0IENlcnQwHhcNMjEwNjI4MTMyNjIyWhcNMjIwNjI4MTMyNjIyWjBeMQswCQYDVQQGEwJHQjETMBEGA1UECAwKU29tZS1TdGF0ZTESMBAGA1UEBwwJU29tZS1DaXR5MQ0wCwYDVQQKDARWeU9TMRcwFQYDVQQDDA5WeU9TIFRlc3QgQ2VydDBZMBMGByqGSM49AgEGCCqGSM49AwEHA0IABBsebIt+8rr2UysTpL8NnYUtmt47e3sC3H9IO8iI/N4uFrmGVgTLE2G+RDGzZgG/r7LviJSTuE9HX7wHLcIr0SmjODA2MAwGA1UdEwEB/wQCMAAwFgYDVR0lAQH/BAwwCgYIKwYBBQUHAwEwDgYDVR0PAQH/BAQDAgeAMAoGCCqGSM49BAMCA0kAMEYCIQD5xK5kdC3TJ7SZrBGvzIM7E7Cil/KZJUyQDR9eFNNZVQIhALg8DTfrwAawf8L+Ncjn/l2gd5cB0nGij0D7uYnm3zf/'
valid_dh_params = 'MIIBCAKCAQEAnNldZCrJk5MxhFoUlvvaYmUO+TmtL0uL62H2RIHJ+O0R+8vzdGPh6zDAzo46EJK735haUgu8+A1RTsXDOXcwBqDlVe0hYj9KaPHz1HpfNKntpoPCJAYJwiH8dd5zVMH+iBwEKlrfteV9vWHn0HUxgLJFSLp5o6y0qpKPREJu6k0XguGScrPaIw6RUwsoDy3unHfk+YeC0o040R18F75V1mXWTjQlEgM7ZO2JZkLGkhW30jB0vSHrkrFqOvtPUiyG7r3+j18IUYLTN0s+5FOCfCjvSVKibNlB1vUz5y/9Ve8roctpkRM/5R5FA0mtbl7U/yMSX4FRIQ/A9BlHiu4bowIBAg=='
valid_public_ec_key = 'MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEAoInInwjlu/3+wDqvRa/Eyg3EMvBpPyq2v4jqEtEh2n4lOCi7ZgNjr+1sQSvrn8mccpALYl3/RKOougC5oQzCg=='
valid_private_rsa_key = 'MIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQDDoAVyJPpcLBFs2NdS1qMOSj7mwKBKVZiBN3nqbLiOvEHbVe22UMNvUFU3sGs2Ta2zXwhPF3d6vPPsGlYTkO3XAffMSNXhjCsvWHiIOR4JrWf598Bpt+txBsxsa12kM3/HM7RDf3zdN2gTtwzrcWzu+zOTXlqJ2OSq/BRRZO9IMbQLQ1/h42GJHEr4THnY4zDqUjmMmIuiBXn4xoE4KFLH1+xPTVleeKvPPeJ1wsshoUjlXYOgcsrXasDUt5gtkkXsVQwR9Lvbh+RcBhT+tJmrX9Cwq4YAd3tLSNJARS9HanRZ8uV0RTyZsImdw1Fr5ySpG2oEp/Z5mbL6QYqDmQ+DAgMBAAECggEAGu7qMQf0TEJo98J3CtmwQ2Rnep+ksfdM8uVvbJ4hXs1+h7Mx8jr2XVoDEZLBgA17z8lSvIjvkz92mdgaZ8E5bbPAqSiSAeapf3A/0AmFIDH2scyxehyvVrVn6blygAvzGLr+o5hm2ZIqSySVq8jHBbQiKrT/5CCvgvcH2Rj7dMXdT5lL73tCRJZsgvFNlxyj4Omj9Lh7SjL+tIwEQaLFbvANXrZ/BPyw4OlK8daBNg9b5GvJSDitAVMgDEEApGYu1iNwMM4UJSQAC27eJdr+qJO6DDqktWOyWcyXrxJ9mDVKFNbb9QNQZDj7bFfm6rCuSdH9yYe3vly+SNJqtyCiwQKBgQDvemt/57KiwQffmoKR65NAZsQvmA4PtELYOV8NPeYH1BZN/EPmCc74iELJdQPFDYy903aRJEPGt7jfqprdPexLwt73P/XiUjPrsbqgJqfF/EMiczxAktyW3xBt2lIWU1MUUmO1ps+ZZEg8Ks4eK/3+FWqbwZ8drDBUT9BthUA0oQKBgQDRHxU6bu938PGweFJcIG6U21nsYaWiwCiTLXA5vWZ+UEqz81BUye6tIcCDgeku3HvC/0ycvrBM9F4AZCjnnEvrAJHKl6e4j+C4IpghGQvRvQ9ihDs9JIHnaoUC1i8dE3ISbbp1r7CN+J/HnAC2OeECMJuffXdnkVWaxRdxU+9towKBgCwFVeNyJO00DI126o+GPVA2U9Pn4JXUbgEvMqDNgw5nVx5Iw/ZyUSBwc85yexnq7rcqOv5dKzRJK2u6AbOvoVMf5DqRAFL1B2RJDGRKFscXIwQfKLE6DeCR6oQ3AKXn9TqkFn4axsiMnZapy6/SKGNfbnRpOCWNNGkbLtYjC3VhAoGAN0kOZapaaM0sOEk3DOAOHBB5j4KpNYOztmU23Cz0YcR8W2KiBCh2jxLzQFEiAp+LoJu59156YX3hNB1GqySo9XHrGTJKxwJSmJucuHNUqphe7t6igqGaLkH89CkHv5oaeEDGIMLX3FC0fSMDFSnsEJYlLl8PKDRF+2rLrcxQ6h0CgYAZllNu8a7tE6cM6QsCILQnNjuLuZRX8/KYWRqBJxatwZXCcMe2jti1HKTVVVCyYffOFa1QcAjCPknAmAz80l3eg6a75NnEXo0J6YLAOOxd8fD2/HidhbceCmTF+3msidIzCsBidBkgn6V5TXx2IyMSxGsJxVHfSKeooUQn6q76sg=='

class TestPKI(VyOSUnitTestSHIM.TestCase):
    def setUp(self):
        self.cli_delete(base_path)

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

    def test_valid_pki(self):
        # Valid CA
        self.cli_set(base_path + ['ca', 'smoketest', 'certificate', valid_ca_cert])
        self.cli_set(base_path + ['ca', 'smoketest', 'private', 'key', valid_ca_private_key])
        self.cli_set(base_path + ['ca', 'smoketest', 'private', 'type', 'rsa'])

        # Valid cert
        self.cli_set(base_path + ['certificate', 'smoketest', 'certificate', valid_cert])

        # Valid DH
        self.cli_set(base_path + ['dh', 'smoketest', 'parameters', valid_dh_params])

        # Valid public key
        self.cli_set(base_path + ['key-pair', 'smoketest', 'public', 'key', valid_public_ec_key])
        self.cli_set(base_path + ['key-pair', 'smoketest', 'type', 'ec'])

        # Valid private key
        self.cli_set(base_path + ['key-pair', 'smoketest1', 'private', 'key', valid_private_rsa_key])
        self.cli_set(base_path + ['key-pair', 'smoketest1', 'type', 'rsa'])

        self.cli_commit()

    def test_invalid_ca_valid_certificate(self):
        self.cli_set(base_path + ['ca', 'smoketest', 'certificate', valid_cert])

        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

    def test_invalid_certificate(self):
        self.cli_set(base_path + ['certificate', 'smoketest', 'certificate', 'invalidcertdata'])

        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

    def test_invalid_public_key(self):
        self.cli_set(base_path + ['key-pair', 'smoketest', 'public', 'key', 'invalidkeydata'])
        self.cli_set(base_path + ['key-pair', 'smoketest', 'type', 'rsa'])

        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

    def test_invalid_private_key(self):
        self.cli_set(base_path + ['key-pair', 'smoketest', 'private', 'key', 'invalidkeydata'])
        self.cli_set(base_path + ['key-pair', 'smoketest', 'type', 'rsa'])

        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

    def test_invalid_dh_parameters(self):
        self.cli_set(base_path + ['dh', 'smoketest', 'parameters', 'thisisinvalid'])

        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

if __name__ == '__main__':
    unittest.main(verbosity=2)
