#!/usr/bin/env python3
#
# Copyright (C) 2020-2024 VyOS maintainers and contributors
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
from vyos.template import ip_from_cidr
from vyos.utils.process import process_named_running
from vyos.utils.file import read_file

OCSERV_CONF = '/run/ocserv/ocserv.conf'
base_path = ['vpn', 'openconnect']

pki_path = ['pki']

cert_name = 'OCServ'
cert_data = """
MIIDsTCCApmgAwIBAgIURNQMaYmRIP/d+/OPWPWmuwkYHbswDQYJKoZIhvcNAQEL
BQAwVzELMAkGA1UEBhMCR0IxEzARBgNVBAgMClNvbWUtU3RhdGUxEjAQBgNVBAcM
CVNvbWUtQ2l0eTENMAsGA1UECgwEVnlPUzEQMA4GA1UEAwwHdnlvcy5pbzAeFw0y
NDA0MDIxNjQxMTRaFw0yNTA0MDIxNjQxMTRaMFcxCzAJBgNVBAYTAkdCMRMwEQYD
VQQIDApTb21lLVN0YXRlMRIwEAYDVQQHDAlTb21lLUNpdHkxDTALBgNVBAoMBFZ5
T1MxEDAOBgNVBAMMB3Z5b3MuaW8wggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEK
AoIBAQDFeexWVV70fBLOxGofWYlcNxJ9JyLviAZZDXrBIYfQnSrYp51yMKRPTH1e
Sjr7gIxVArAqLoYFgo7frRDkCKg8/izTopxtBTV2XJkLqDGA7DOrtBhgj0zjmF0A
WWIWi83WHc+sTHSvIqNLCDAZgnnzf1ch3W/na10hBTnFX4Yv6CJ4I7doSIyWzaQr
RvUXfaNYnvege+RrG5LzkVGxD2EhHyBqfQ2mxvlgqICqKSZkL56a3c/MHAm+7MKl
2KbSGxwNDs+SpHrCgWVIsl9w0bN2NSAu6GzyfW7V+V1dkiCggLlxXGhGncPMiQ7T
M7GKQULnQl5o/15GkW72Tg6wUdDpAgMBAAGjdTBzMAwGA1UdEwEB/wQCMAAwDgYD
VR0PAQH/BAQDAgeAMBMGA1UdJQQMMAoGCCsGAQUFBwMBMB0GA1UdDgQWBBTtil1X
c6dXA6kxZtZCgjx9QPzeLDAfBgNVHSMEGDAWgBTKMZvYAW1thn/uxX1fpcbP5vKq
dzANBgkqhkiG9w0BAQsFAAOCAQEARjS+QYJDz+XTdwK/lMF1GhSdacGnOIWRsbRx
N7odsyBV7Ud5W+Py79n+/PRirw2+jAaGXFmmgdxrcjlM+dZnlO3X0QCIuNdODggD
0J/u1ICPdm9TcJ2lEdbIE2vm2Q9P5RdQ7En7zg8Wu+rcNPlIxd3pHFOMX79vOcgi
RkWWII6tyeeT9COYgXUbg37wf2LkVv4b5PcShrfkWZVFWKDKr1maJ+iMwcIlosOe
Gj3SKe7gKBuPbMRwtocqKAYbW1GH12tA49DNkvxVKxVqnP4nHkwgfOJdpcZAjlyb
gLkzVKInZwg5EvJ7qtSJirDap9jyuLTfr5TmxbcdEhmAqeS41A==
"""

cert_key_data = """
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDFeexWVV70fBLO
xGofWYlcNxJ9JyLviAZZDXrBIYfQnSrYp51yMKRPTH1eSjr7gIxVArAqLoYFgo7f
rRDkCKg8/izTopxtBTV2XJkLqDGA7DOrtBhgj0zjmF0AWWIWi83WHc+sTHSvIqNL
CDAZgnnzf1ch3W/na10hBTnFX4Yv6CJ4I7doSIyWzaQrRvUXfaNYnvege+RrG5Lz
kVGxD2EhHyBqfQ2mxvlgqICqKSZkL56a3c/MHAm+7MKl2KbSGxwNDs+SpHrCgWVI
sl9w0bN2NSAu6GzyfW7V+V1dkiCggLlxXGhGncPMiQ7TM7GKQULnQl5o/15GkW72
Tg6wUdDpAgMBAAECggEACbR8bHZv9GT/9EshNLQ3n3a8wQuCLd0fWWi5A90sKbun
pj5/6uOVbP5DL7Xx4HgIrYmJyIZBI5aEg11Oi15vjOZ9o9MF4V0UVmJQ9TU0EEl2
H/X5uA54MWaaCiaFFGWU3UqEG8wldJFSZCFyt7Y6scBW3b0JFF7+6dyyDPoCWWqh
cNR41Hv0T0eqfXGOXX1JcBlLbqy0QXXeFoLlxV3ouIgWgkKJk7u3vDWCVM/ofP0m
/GyZYWCEA2JljEQZaVgtk1afFoamrjM4doMiirk+Tix4yGno94HLJdDUynqdLNAd
ZdKunFVAJau17b1VVPyfgIvIaPRvSGQVQoXH6TuB2QKBgQD5LRYTxsd8WsOwlB2R
SBYdzDff7c3VuNSAYTp7O2MqWrsoXm2MxLzEJLJUen+jQphL6ti/ObdrSOnKF2So
SizYeJ1Irx4M4BPSdy/Yt3T/+e+Y4K7iQ7Pdvdc/dlZ5XuNHYzuA/F7Ft/9rhUy9
jSdQYANX+7h8vL7YrEjvhMMMZQKBgQDK4mG4D7XowLlBWv1fK4n/ErWvYSxH/X+A
VVnLv4z4aZHyRS2nTfQnb8PKbHJ/65x9yZs8a+6HqE4CAH+0LfZuOI8qn9OksxPZ
7GuQk/FiVyGXtu18hzlfhzmb0ZTjAalZ5b68DOIhyZIHVketebhljXaB5bfwdIgt
7vTOfotANQKBgQCWiA5WVDgfgBXIjzJtmkcCKWV3+onnG4oFJLfXysDVzYpTkPhN
mm0PcbvqHTcOwiSPeIkIvS15usrCM++zW1xMSlF6n5Bf5t8Svr5BBlPAcJW2ncYJ
Gy2GQDHRPQRwvko/zkscWVpHyCieJCGAQc4GWHqspH2Hnd8Ntsc5K9NJoQKBgFR1
5/5rM+yghr7pdT9wbbNtg4tuZbPWmYTAg3Bp3vLvaB22pOnYbwMX6SdU/Fm6qVxI
WMLPn+6Dp2337TICTGvYSemRvdb74hC/9ouquzuYUFjLg5Rq6vyU2+u9VUEnyOuu
1DePGXi9ZHh/d7mFSbmlKaesDWYh7StKJknsrmXdAoGBAOm+FnzryKkhIq/ELyT9
8v4wr0lxCcAP3nNb/P5ocv3m7hRLIkf4S9k/gAL+gE/OtdesomQKjOz7noLO+I2H
rj6ZfC/lhPIRJ4XK5BqgqqH53Zcl/HDoaUjbpmyMvZVoQfUHLut8Y912R6mfm65z
qXl1L7EdHTY+SdoThNJTpmWb
"""

ca_name = 'VyOS-CA'
ca_data = """
MIIDnTCCAoWgAwIBAgIUFVRURZXSbQ7F0DiSZYfqY0gQORMwDQYJKoZIhvcNAQEL
BQAwVzELMAkGA1UEBhMCR0IxEzARBgNVBAgMClNvbWUtU3RhdGUxEjAQBgNVBAcM
CVNvbWUtQ2l0eTENMAsGA1UECgwEVnlPUzEQMA4GA1UEAwwHdnlvcy5pbzAeFw0y
NDA0MDIxNjQxMDFaFw0yOTA0MDExNjQxMDFaMFcxCzAJBgNVBAYTAkdCMRMwEQYD
VQQIDApTb21lLVN0YXRlMRIwEAYDVQQHDAlTb21lLUNpdHkxDTALBgNVBAoMBFZ5
T1MxEDAOBgNVBAMMB3Z5b3MuaW8wggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEK
AoIBAQCg7Mjl6+rs8Bdkjqgl2QDuHfrH2mTDCeB7WuNTnIz0BPDtlmwIdqhU7LdC
B/zUSABAa6LBe/Z/bKWCRKyq8fU2/4uWECe975IMXOfFdYT6KA78DROvOi32JZml
n0LAXV+538eb+g19xNtoBhPO8igiNevfkV+nJehRK/41ATj+assTOv87vaSX7Wqy
aP/ZqkIdQD9Kc3cqB4JsYjkWcniHL9yk4oY3cjKK8PJ1pi4FqgFHt2hA+Ic+NvbA
hc47K9otP8FM4jkSii3MZfHA6Czb43BtbR+YEiWPzBhzE2bCuIgeRUumMF1Z+CAT
6U7Cpx3XPh+Ac2RnDa8wKeQ1eqE1AgMBAAGjYTBfMA8GA1UdEwEB/wQFMAMBAf8w
DgYDVR0PAQH/BAQDAgGGMB0GA1UdJQQWMBQGCCsGAQUFBwMCBggrBgEFBQcDATAd
BgNVHQ4EFgQUyjGb2AFtbYZ/7sV9X6XGz+byqncwDQYJKoZIhvcNAQELBQADggEB
AArGXCq92vtaUZt528lC34ENPL9bQ7nRAS/ojplAzM9reW3o56sfYWf1M8iwRsJT
LbAwSnVB929RLlDolNpLwpzd1XaMt61Zcx4MFQmQCd+40dfuvMhluZaxt+F9bC1Z
cA7uwe/2HrAIULq3sga9LzSph6dNuyd1rGchr4xHCJ7u4WcF0kqi0Hjcn9S/ppEc
ba2L3rRqZmCbe6Yngx+MS06jonGw0z8F6e8LMkcvJUlNMEC76P+5Byjp4xZGP+y3
DtIfsfijpb+t1OUe75YmWflTFnHR9GlybNYTxGAl49mFw6LlS1kefXyPtfuReLmv
n+vZdJAWTq76zAPT3n9FClo=
"""

ca_key_data = """
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCg7Mjl6+rs8Bdk
jqgl2QDuHfrH2mTDCeB7WuNTnIz0BPDtlmwIdqhU7LdCB/zUSABAa6LBe/Z/bKWC
RKyq8fU2/4uWECe975IMXOfFdYT6KA78DROvOi32JZmln0LAXV+538eb+g19xNto
BhPO8igiNevfkV+nJehRK/41ATj+assTOv87vaSX7WqyaP/ZqkIdQD9Kc3cqB4Js
YjkWcniHL9yk4oY3cjKK8PJ1pi4FqgFHt2hA+Ic+NvbAhc47K9otP8FM4jkSii3M
ZfHA6Czb43BtbR+YEiWPzBhzE2bCuIgeRUumMF1Z+CAT6U7Cpx3XPh+Ac2RnDa8w
KeQ1eqE1AgMBAAECggEAEDDaoqVqmMWsONoQiWRMr2h1RZvPxP7OpuKVWiF3XgrM
Ob9HZc+Ybpj1dC+NDMekvNaHhMuF2Lqz6UgjDjzzVMH/x4yfDwFWUqebSxbglvGm
Vk4zg48JNkmArLT6GJQccD1XXjZZmqSOhagM4KalCpIdxfvgoZbTCa2xMSCLHS+1
HCDcmpCoeXM6ZBPTn0NbjRDAqIzCwcq2veG7RSz040obk8h7nrdv7jhxRGmtPmPF
zKgGLNn6GnL7AwYVMiidjj/ntvM4B1OMs9MwUYbtpg98TWcWyu+ZRakUrnVf9z2a
IHCKyuJvke/PNqMgw+L8KV4/478XxWhXfl7K1F3nMQKBgQDRBUDYNFH0wC4MMWsA
+RGwyz7RlzACChDJCMtA/agbW06gUoE9UYf8KtLQQQYljlLJHxHGD72QnuM+sowG
GXnbD4BabA9TQiQUG5c6boznTy1uU1gt8T0Zl0mmC7vIMoMBVd5bb0qrZvuR123k
DGYn6crug9uvMIYSSlhGmBGTJQKBgQDFGC3vfkCyXzLoYy+RIs/rXgyBF1PUYQty
DgL0N811L0H7a8JhFnt4FvodUbxv2ob+1kIc9e3yXT6FsGyO7IDOnqgeQKy74bYq
VPZZuf1FOFb9fuxf00pn1FmhAF4OuSWkhVhrKkyrZwdD8ArjLK253J94dogjdKAY
fN1csaOA0QKBgD0zUZI8d4a3QoRVb+RACTr/t6v8nZTrR5DlX0XvP2qLKJFutuKy
XaOrEkDh2R/j9T9oNncMos+WhikUdEVQ7koC1u0i2LXjFtdAYN4+Akmz+DRmeNoy
2VYF4w2YP+pVR+B7OPkCtBVNuPkx3743Fy42mTGPMCKyjX8Lf59j5Tl1AoGBAI3s
k2dZqozHMIlWovIH92CtIKP0gFD2cJ94p3fklvZDSWgaeKYg4lffc8uZB/AjlAH9
ly3ziZx0uIjcOc/RTg96/+SI/dls9xgUhjCmVVJ692ki9GMsau/JYaEl+pTvjcOi
ocDJfNwQHJM3Tx+3FII59DtyXyXo3T/E6kHNSMeBAoGAR9M48DTspv9OH1S7X6yR
6MtMY5ltsBmB3gPhQFxiDKBvARkIkAPqObQ9TG/VuOz2Purq0Oz7SHsY2jiFDd2K
EGo6JfG61NDdIhiQC99ztSgt7NtvSCnX22SfVDWoFxSK+tek7tvDVXAXCNy4ZESM
EUGJ6NDHImb80aF+xZ3wYKw=
"""

PROCESS_NAME = 'ocserv-main'
config_file = '/run/ocserv/ocserv.conf'
auth_file = '/run/ocserv/ocpasswd'
otp_file = '/run/ocserv/users.oath'

listen_if = 'dum116'
listen_address = '100.64.0.1/32'

class TestVPNOpenConnect(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestVPNOpenConnect, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

        cls.cli_set(cls, ['interfaces', 'dummy', listen_if, 'address', listen_address])

        cls.cli_set(cls, pki_path + ['ca', cert_name, 'certificate', ca_data.replace('\n','')])
        cls.cli_set(cls, pki_path + ['ca', cert_name, 'private', 'key', ca_key_data.replace('\n','')])
        cls.cli_set(cls, pki_path + ['certificate', cert_name, 'certificate', cert_data.replace('\n','')])
        cls.cli_set(cls, pki_path + ['certificate', cert_name, 'private', 'key', cert_key_data.replace('\n','')])

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, pki_path)
        cls.cli_delete(cls, ['interfaces', 'dummy', listen_if])
        super(TestVPNOpenConnect, cls).tearDownClass()

    def tearDown(self):
        self.assertTrue(process_named_running(PROCESS_NAME))

        self.cli_delete(base_path)
        self.cli_commit()

        self.assertFalse(process_named_running(PROCESS_NAME))

    def test_ocserv(self):
        user = 'vyos_user'
        password = 'vyos_pass'
        otp = '37500000026900000000200000000000'
        v4_subnet = '192.0.2.0/24'
        v6_prefix = '2001:db8:1000::/64'
        v6_len = '126'
        name_server = ['1.2.3.4', '1.2.3.5', '2001:db8::1']
        split_dns = ['vyos.net', 'vyos.io']

        self.cli_set(base_path + ['authentication', 'local-users', 'username', user, 'password', password])
        self.cli_set(base_path + ['authentication', 'local-users', 'username', user, 'otp', 'key', otp])
        self.cli_set(base_path + ['authentication', 'mode', 'local', 'password-otp'])

        self.cli_set(base_path + ['network-settings', 'client-ip-settings', 'subnet', v4_subnet])
        self.cli_set(base_path + ['network-settings', 'client-ipv6-pool', 'prefix', v6_prefix])
        self.cli_set(base_path + ['network-settings', 'client-ipv6-pool', 'mask', v6_len])

        for ns in name_server:
            self.cli_set(base_path + ['network-settings', 'name-server', ns])
        for domain in split_dns:
            self.cli_set(base_path + ['network-settings', 'split-dns', domain])

        # SSL certificates are mandatory
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(base_path + ['ssl', 'ca-certificate', cert_name])
        self.cli_set(base_path + ['ssl', 'certificate', cert_name])

        listen_ip_no_cidr = ip_from_cidr(listen_address)
        self.cli_set(base_path + ['listen-address', listen_ip_no_cidr])

        self.cli_commit()

        # Verify configuration
        daemon_config = read_file(config_file)

        # Verify TLS string (with default setting)
        self.assertIn('tls-priorities = "NORMAL:%SERVER_PRECEDENCE:%COMPAT:-RSA:-VERS-SSL3.0:-ARCFOUR-128:-VERS-TLS1.0:-VERS-TLS1.1"', daemon_config)

        # authentication mode local password-otp
        self.assertIn(f'auth = "plain[passwd=/run/ocserv/ocpasswd,otp=/run/ocserv/users.oath]"', daemon_config)
        self.assertIn(f'listen-host = {listen_ip_no_cidr}', daemon_config)
        self.assertIn(f'ipv4-network = {v4_subnet}', daemon_config)
        self.assertIn(f'ipv6-network = {v6_prefix}', daemon_config)
        self.assertIn(f'ipv6-subnet-prefix = {v6_len}', daemon_config)

        # defaults
        self.assertIn(f'tcp-port = 443', daemon_config)
        self.assertIn(f'udp-port = 443', daemon_config)

        for ns in name_server:
            self.assertIn(f'dns = {ns}', daemon_config)
        for domain in split_dns:
            self.assertIn(f'split-dns = {domain}', daemon_config)

        auth_config = read_file(auth_file)
        self.assertIn(f'{user}:*:$', auth_config)

        otp_config = read_file(otp_file)
        self.assertIn(f'HOTP/T30/6 {user} - {otp}', otp_config)


        # Verify HTTP security headers
        self.cli_set(base_path + ['http-security-headers'])
        self.cli_commit()

        daemon_config = read_file(config_file)

        self.assertIn('included-http-headers = Strict-Transport-Security: max-age=31536000 ; includeSubDomains', daemon_config)
        self.assertIn('included-http-headers = X-Frame-Options: deny', daemon_config)
        self.assertIn('included-http-headers = X-Content-Type-Options: nosniff', daemon_config)
        self.assertIn('included-http-headers = Content-Security-Policy: default-src "none"', daemon_config)
        self.assertIn('included-http-headers = X-Permitted-Cross-Domain-Policies: none', daemon_config)
        self.assertIn('included-http-headers = Referrer-Policy: no-referrer', daemon_config)
        self.assertIn('included-http-headers = Clear-Site-Data: "cache","cookies","storage"', daemon_config)
        self.assertIn('included-http-headers = Cross-Origin-Embedder-Policy: require-corp', daemon_config)
        self.assertIn('included-http-headers = Cross-Origin-Opener-Policy: same-origin', daemon_config)
        self.assertIn('included-http-headers = Cross-Origin-Resource-Policy: same-origin', daemon_config)
        self.assertIn('included-http-headers = X-XSS-Protection: 0', daemon_config)
        self.assertIn('included-http-headers = Pragma: no-cache', daemon_config)
        self.assertIn('included-http-headers = Cache-control: no-store, no-cache', daemon_config)

        # Set TLS version to the highest security (v1.3 min)
        self.cli_set(base_path + ['tls-version-min', '1.3'])
        self.cli_commit()

        # Verify TLS string
        daemon_config = read_file(config_file)
        self.assertIn('tls-priorities = "NORMAL:%SERVER_PRECEDENCE:%COMPAT:-RSA:-VERS-SSL3.0:-ARCFOUR-128:-VERS-TLS1.0:-VERS-TLS1.1:-VERS-TLS1.2"', daemon_config)

if __name__ == '__main__':
    unittest.main(verbosity=2)
