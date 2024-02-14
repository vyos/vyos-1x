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
from vyos.utils.process import process_named_running

base_path = ['protocols', 'rpki']
PROCESS_NAME = 'bgpd'

rpki_key_name = 'rpki-smoketest'
rpki_key_type = 'ssh-rsa'

rpki_ssh_key = """
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAABFwAAAAdzc2gtcn
NhAAAAAwEAAQAAAQEAweDyflDFR4qyEwETbJkZ2ZZc+sJNiDTvYpwGsWIkju49lJSxHe1x
Kf8FhwfyMu40Snt1yDlRmmmz4CsbLgbuZGMPvXG11e34+C0pSVUvpF6aqRTeLl1pDRK7Rn
jgm3su+I8SRLQR4qbLG6VXWOFuVpwiqbExLaU0hFYTPNP+dArNpsWEEKsohk6pTXdhg3Vz
Wp3vCMjl2JTshDa3lD7p2xISSAReEY0fnfEAmQzH4Z6DIwwGdFuMWoQIg+oFBM9ARrO2/F
IjRsz6AecR/WeU72JEw4aJic1/cAJQA6PiQBHwkuo3Wll1tbpxeRZoB2NQG22ETyJLvhfT
aooNLT9HpQAAA8joU5dM6FOXTAAAAAdzc2gtcnNhAAABAQDB4PJ+UMVHirITARNsmRnZll
z6wk2INO9inAaxYiSO7j2UlLEd7XEp/wWHB/Iy7jRKe3XIOVGaabPgKxsuBu5kYw+9cbXV
7fj4LSlJVS+kXpqpFN4uXWkNErtGeOCbey74jxJEtBHipssbpVdY4W5WnCKpsTEtpTSEVh
M80/50Cs2mxYQQqyiGTqlNd2GDdXNane8IyOXYlOyENreUPunbEhJIBF4RjR+d8QCZDMfh
noMjDAZ0W4xahAiD6gUEz0BGs7b8UiNGzPoB5xH9Z5TvYkTDhomJzX9wAlADo+JAEfCS6j
daWXW1unF5FmgHY1AbbYRPIku+F9Nqig0tP0elAAAAAwEAAQAAAQACkDlUjzfUhtJs6uY5
WNrdJB5NmHUS+HQzzxFNlhkapK6+wKqI1UNaRUtq6iF7J+gcFf7MK2nXS098BsXguWm8fQ
zPuemoDvHsQhiaJhyvpSqRUrvPTB/f8t/0AhQiKiJIWgfpTaIw53inAGwjujNNxNm2eafH
TThhCYxOkRT7rsT6bnSio6yeqPy5QHg7IKFztp5FXDUyiOS3aX3SvzQcDUkMXALdvzX50t
1XIk+X48Rgkq72dL4VpV2oMNDu3hM6FqBUplf9Mv3s51FNSma/cibCQoVufrIfoqYjkNTj
IpYFUcq4zZ0/KvgXgzSsy9VN/4TtbalrOuu7X/SHJbvhAAAAgGPFsXgONYQvXxCnK1dIue
ozgaZg1I/n522E2ZCOXBW4dYJVyNpppwRreDzuFzTDEe061MpNHfScjVBJCCulivFYWscL
6oaGsryDbFxO3QmB4I98UBqrds2yan9/JGc6EYe299yvaHy7Y64+NC0+fN8H2RAZ61T4w1
0JrCaJRyvzAAAAgQDvBfuV1U7o9k/fbU+U7W2UYnWblpOZAMfi1XQP6IJJeyWs90PdTdXh
+l0eIQrCawIiRJytNfxMmbD4huwTf77fWiyCcPznmALQ7ex/yJ+W5Z0V4dPGF3h7o1uiS2
36JhQ7mfcliCkhp/1PIklBIMPcCp0zl+s9wMv2hX7w1Pah9QAAAIEAz6YgU9Xute+J+dBw
oWxEQ+igR6KE55Um7O9AvSrqnCm9r7lSFsXC2ErYOxoDSJ3yIBEV0b4XAGn6tbbVIs3jS8
BnLHxclAHQecOx1PGn7PKbnPW0oJRq/X9QCIEelKYvlykpayn7uZooTXqcDaPZxfPpmPdy
e8chVJvdygi7kPEAAAAMY3BvQExSMS53dWUzAQIDBAUGBw==
"""

rpki_ssh_pub = """
AAAAB3NzaC1yc2EAAAADAQABAAABAQDB4PJ+UMVHirITARNsmRnZllz6wk2INO9inAaxYi
SO7j2UlLEd7XEp/wWHB/Iy7jRKe3XIOVGaabPgKxsuBu5kYw+9cbXV7fj4LSlJVS+kXpqp
FN4uXWkNErtGeOCbey74jxJEtBHipssbpVdY4W5WnCKpsTEtpTSEVhM80/50Cs2mxYQQqy
iGTqlNd2GDdXNane8IyOXYlOyENreUPunbEhJIBF4RjR+d8QCZDMfhnoMjDAZ0W4xahAiD
6gUEz0BGs7b8UiNGzPoB5xH9Z5TvYkTDhomJzX9wAlADo+JAEfCS6jdaWXW1unF5FmgHY1
AbbYRPIku+F9Nqig0tP0el
"""

rpki_ssh_key_replacement = """
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAABFwAAAAdzc2gtcn
NhAAAAAwEAAQAAAQEAtLPMwiGR3o6puPDbus9Yqoah9/7rv7i6ykykPmcEZ6ERnA0N6bl7
LkQxnCuX270ukTTZOhROvQnvQYIZohCMz27Q16z7r+I755QXL0x8x4Gqhg/hQUY7UtX6ts
db8+pO7G1PL4r9zT6/KJAF/wv86DezJ3I6TMaA7MCikXfQWJisBvhgAXF1+7V9CWaroGgV
/hHzQJu1yd4cfsYoHyeDaZ+lwFw4egNItIy63fIGDxrnXaonJ1ODGQh7zWlpl/cwQR/KyJ
P8vvOZ9olQ6syZV+DAcAo4Fe59wW2Zj4bl8bdGcdiDn0grkafxwTcg9ynr9kwQ8b66oXY4
hwB4vlPFPwAAA8jkGyX45Bsl+AAAAAdzc2gtcnNhAAABAQC0s8zCIZHejqm48Nu6z1iqhq
H3/uu/uLrKTKQ+ZwRnoRGcDQ3puXsuRDGcK5fbvS6RNNk6FE69Ce9BghmiEIzPbtDXrPuv
4jvnlBcvTHzHgaqGD+FBRjtS1fq2x1vz6k7sbU8viv3NPr8okAX/C/zoN7MncjpMxoDswK
KRd9BYmKwG+GABcXX7tX0JZqugaBX+EfNAm7XJ3hx+xigfJ4Npn6XAXDh6A0i0jLrd8gYP
GuddqicnU4MZCHvNaWmX9zBBH8rIk/y+85n2iVDqzJlX4MBwCjgV7n3BbZmPhuXxt0Zx2I
OfSCuRp/HBNyD3Kev2TBDxvrqhdjiHAHi+U8U/AAAAAwEAAQAAAQA99gkX5/rknXaE+9Hc
VIzKrC+NodOkgetKwszuuNRB1HD9WVyT8A3U5307V5dSuaPmFoEF8UCugWGQzNONRq+B0T
W7Po1u2dxAo/7vMQL4RfX60icjAroExWqakfFtycIWP8UPQFGWtxVFC12C/tFRrwe3Vuu2
t7otdEBKMRM3zU0Hj88/5FIk/MDhththDCKTMe4+iwNKo30dyqSCckpTd2k5de9JYz8Aom
87jtQcyDdynaELSo9CsA8KRPlozZ4VSWTVLH+Cv2TZWPL7hy79YvvIfuF/Sd6PGkNwG1Vj
TAbq2Wx4uq+HmpNiz7W0LnbZtQJ7dzLA3FZlvQMC8fVBAAAAgQDWvImVZCyVWpoG+LnKY3
joegjKRYKdgKRPCqGoIHiYsqCRxqSRW3jsuQCCvk4YO3/ZmqORiGktK+5r8R1QEtwg5qbi
N7GZD34m7USNuqG2G/4puEly8syMmR6VRRvEURFQrpv2wniXNSefvsDc+WDqTfXGUxr+FT
478wkzjwc/fAAAAIEA9uP0Ym3OC3cZ5FOvmu51lxo5lqPlUeE78axg2I4u/9Il8nOvSVuq
B9X5wAUyGAGcUjT3EZmRAtL2sQxc5T0Vw3bnxCjzukEbFM+DRtYy1hXSOoGTTwKoMWBpho
R3X5uRLUQL/22C4rd7tSJpjqnZXIH0B5z2fFh4vzu8/SrgCrUAAACBALtep4BcGJfjfhfF
ODzQe7Rk7tsaX8pfNv6bQu0sR5C9pDURFRf0fRC0oqgeTuzq/vHPyNLsUUgTCpKWiLFmvU
G9pelLT3XPPgzA+g0gycM0unuX8kkP3T5VQAM/7u0+h1CaJ8A6cCkzvDJxYdfio3WR60OP
ulHg7HCcyomFLaSjAAAADGNwb0BMUjEud3VlMwECAwQFBg==
"""

rpki_ssh_pub_replacement = """
AAAAB3NzaC1yc2EAAAADAQABAAABAQC0s8zCIZHejqm48Nu6z1iqhqH3/uu/uLrKTKQ+Zw
RnoRGcDQ3puXsuRDGcK5fbvS6RNNk6FE69Ce9BghmiEIzPbtDXrPuv4jvnlBcvTHzHgaqG
D+FBRjtS1fq2x1vz6k7sbU8viv3NPr8okAX/C/zoN7MncjpMxoDswKKRd9BYmKwG+GABcX
X7tX0JZqugaBX+EfNAm7XJ3hx+xigfJ4Npn6XAXDh6A0i0jLrd8gYPGuddqicnU4MZCHvN
aWmX9zBBH8rIk/y+85n2iVDqzJlX4MBwCjgV7n3BbZmPhuXxt0Zx2IOfSCuRp/HBNyD3Ke
v2TBDxvrqhdjiHAHi+U8U/
"""

class TestProtocolsRPKI(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        # call base-classes classmethod
        super(TestProtocolsRPKI, cls).setUpClass()
        # Retrieve FRR daemon PID - it is not allowed to crash, thus PID must remain the same
        cls.daemon_pid = process_named_running(PROCESS_NAME)
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

        # check process health and continuity
        self.assertEqual(self.daemon_pid, process_named_running(PROCESS_NAME))

    def test_rpki(self):
        expire_interval = '3600'
        polling_period = '600'
        retry_interval = '300'
        cache = {
            '192.0.2.1' : {
                'port' : '8080',
                'preference' : '10'
            },
            '2001:db8::1' : {
                'port' : '1234',
                'preference' : '30'
            },
            'rpki.vyos.net' : {
                'port' : '5678',
                'preference' : '40'
            },
        }

        self.cli_set(base_path + ['expire-interval', expire_interval])
        self.cli_set(base_path + ['polling-period', polling_period])
        self.cli_set(base_path + ['retry-interval', retry_interval])

        for peer, peer_config in cache.items():
            self.cli_set(base_path + ['cache', peer, 'port', peer_config['port']])
            self.cli_set(base_path + ['cache', peer, 'preference', peer_config['preference']])

        # commit changes
        self.cli_commit()

        # Verify FRR configuration
        frrconfig = self.getFRRconfig('rpki')
        self.assertIn(f'rpki expire_interval {expire_interval}', frrconfig)
        self.assertIn(f'rpki polling_period {polling_period}', frrconfig)
        self.assertIn(f'rpki retry_interval {retry_interval}', frrconfig)

        for peer, peer_config in cache.items():
            port = peer_config['port']
            preference = peer_config['preference']
            self.assertIn(f'rpki cache {peer} {port} preference {preference}', frrconfig)

    def test_rpki_ssh(self):
        polling = '7200'
        cache = {
            '192.0.2.3' : {
                'port' : '1234',
                'username' : 'foo',
                'preference' : '10'
            },
            '192.0.2.4' : {
                'port' : '5678',
                'username' : 'bar',
                'preference' : '20'
            },
        }

        self.cli_set(['pki', 'openssh', rpki_key_name, 'private', 'key', rpki_ssh_key.replace('\n','')])
        self.cli_set(['pki', 'openssh', rpki_key_name, 'public', 'key', rpki_ssh_pub.replace('\n','')])
        self.cli_set(['pki', 'openssh', rpki_key_name, 'public', 'type', rpki_key_type])

        for cache_name, cache_config in cache.items():
            self.cli_set(base_path + ['cache', cache_name, 'port', cache_config['port']])
            self.cli_set(base_path + ['cache', cache_name, 'preference', cache_config['preference']])
            self.cli_set(base_path + ['cache', cache_name, 'ssh', 'username', cache_config['username']])
            self.cli_set(base_path + ['cache', cache_name, 'ssh', 'key', rpki_key_name])

        # commit changes
        self.cli_commit()

        # Verify FRR configuration
        frrconfig = self.getFRRconfig('rpki')
        for cache_name, cache_config in cache.items():
            port = cache_config['port']
            preference = cache_config['preference']
            username = cache_config['username']
            self.assertIn(f'rpki cache {cache_name} {port} {username} /run/frr/id_rpki_{cache_name} /run/frr/id_rpki_{cache_name}.pub preference {preference}', frrconfig)

            # Verify content of SSH keys
            tmp = read_file(f'/run/frr/id_rpki_{cache_name}')
            self.assertIn(rpki_ssh_key.replace('\n',''), tmp)
            tmp = read_file(f'/run/frr/id_rpki_{cache_name}.pub')
            self.assertIn(rpki_ssh_pub.replace('\n',''), tmp)

        # Change OpenSSH key and verify it was properly written to filesystem
        self.cli_set(['pki', 'openssh', rpki_key_name, 'private', 'key', rpki_ssh_key_replacement.replace('\n','')])
        self.cli_set(['pki', 'openssh', rpki_key_name, 'public', 'key', rpki_ssh_pub_replacement.replace('\n','')])
        # commit changes
        self.cli_commit()

        for cache_name, cache_config in cache.items():
            port = cache_config['port']
            preference = cache_config['preference']
            username = cache_config['username']
            self.assertIn(f'rpki cache {cache_name} {port} {username} /run/frr/id_rpki_{cache_name} /run/frr/id_rpki_{cache_name}.pub preference {preference}', frrconfig)

            # Verify content of SSH keys
            tmp = read_file(f'/run/frr/id_rpki_{cache_name}')
            self.assertIn(rpki_ssh_key_replacement.replace('\n',''), tmp)
            tmp = read_file(f'/run/frr/id_rpki_{cache_name}.pub')
            self.assertIn(rpki_ssh_pub_replacement.replace('\n',''), tmp)

        self.cli_delete(['pki', 'openssh'])

    def test_rpki_verify_preference(self):
        cache = {
            '192.0.2.1' : {
                'port' : '8080',
                'preference' : '1'
            },
            '192.0.2.2' : {
                'port' : '9090',
                'preference' : '1'
            },
        }

        for peer, peer_config in cache.items():
            self.cli_set(base_path + ['cache', peer, 'port', peer_config['port']])
            self.cli_set(base_path + ['cache', peer, 'preference', peer_config['preference']])

        # check validate() - preferences must be unique
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

if __name__ == '__main__':
    unittest.main(verbosity=2)
