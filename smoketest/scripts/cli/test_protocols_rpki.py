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
from vyos.utils.process import process_named_running

base_path = ['protocols', 'rpki']
PROCESS_NAME = 'bgpd'

rpki_key_name = 'rpki-smoketest'
rpki_key_type = 'ssh-rsa'

rpki_ssh_key = """
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAABFwAAAAdz
c2gtcnNhAAAAAwEAAQAAAQEAweDyflDFR4qyEwETbJkZ2ZZc+sJNiDTvYpwGsWIk
ju49lJSxHe1xKf8FhwfyMu40Snt1yDlRmmmz4CsbLgbuZGMPvXG11e34+C0pSVUv
pF6aqRTeLl1pDRK7Rnjgm3su+I8SRLQR4qbLG6VXWOFuVpwiqbExLaU0hFYTPNP+
dArNpsWEEKsohk6pTXdhg3VzWp3vCMjl2JTshDa3lD7p2xISSAReEY0fnfEAmQzH
4Z6DIwwGdFuMWoQIg+oFBM9ARrO2/FIjRsz6AecR/WeU72JEw4aJic1/cAJQA6Pi
QBHwkuo3Wll1tbpxeRZoB2NQG22ETyJLvhfTaooNLT9HpQAAA8joU5dM6FOXTAAA
AAdzc2gtcnNhAAABAQDB4PJ+UMVHirITARNsmRnZllz6wk2INO9inAaxYiSO7j2U
lLEd7XEp/wWHB/Iy7jRKe3XIOVGaabPgKxsuBu5kYw+9cbXV7fj4LSlJVS+kXpqp
FN4uXWkNErtGeOCbey74jxJEtBHipssbpVdY4W5WnCKpsTEtpTSEVhM80/50Cs2m
xYQQqyiGTqlNd2GDdXNane8IyOXYlOyENreUPunbEhJIBF4RjR+d8QCZDMfhnoMj
DAZ0W4xahAiD6gUEz0BGs7b8UiNGzPoB5xH9Z5TvYkTDhomJzX9wAlADo+JAEfCS
6jdaWXW1unF5FmgHY1AbbYRPIku+F9Nqig0tP0elAAAAAwEAAQAAAQACkDlUjzfU
htJs6uY5WNrdJB5NmHUS+HQzzxFNlhkapK6+wKqI1UNaRUtq6iF7J+gcFf7MK2nX
S098BsXguWm8fQzPuemoDvHsQhiaJhyvpSqRUrvPTB/f8t/0AhQiKiJIWgfpTaIw
53inAGwjujNNxNm2eafHTThhCYxOkRT7rsT6bnSio6yeqPy5QHg7IKFztp5FXDUy
iOS3aX3SvzQcDUkMXALdvzX50t1XIk+X48Rgkq72dL4VpV2oMNDu3hM6FqBUplf9
Mv3s51FNSma/cibCQoVufrIfoqYjkNTjIpYFUcq4zZ0/KvgXgzSsy9VN/4Ttbalr
Ouu7X/SHJbvhAAAAgGPFsXgONYQvXxCnK1dIueozgaZg1I/n522E2ZCOXBW4dYJV
yNpppwRreDzuFzTDEe061MpNHfScjVBJCCulivFYWscL6oaGsryDbFxO3QmB4I98
UBqrds2yan9/JGc6EYe299yvaHy7Y64+NC0+fN8H2RAZ61T4w10JrCaJRyvzAAAA
gQDvBfuV1U7o9k/fbU+U7W2UYnWblpOZAMfi1XQP6IJJeyWs90PdTdXh+l0eIQrC
awIiRJytNfxMmbD4huwTf77fWiyCcPznmALQ7ex/yJ+W5Z0V4dPGF3h7o1uiS236
JhQ7mfcliCkhp/1PIklBIMPcCp0zl+s9wMv2hX7w1Pah9QAAAIEAz6YgU9Xute+J
+dBwoWxEQ+igR6KE55Um7O9AvSrqnCm9r7lSFsXC2ErYOxoDSJ3yIBEV0b4XAGn6
tbbVIs3jS8BnLHxclAHQecOx1PGn7PKbnPW0oJRq/X9QCIEelKYvlykpayn7uZoo
TXqcDaPZxfPpmPdye8chVJvdygi7kPEAAAAMY3BvQExSMS53dWUzAQIDBAUGBw==
"""

rpki_ssh_pub = """
AAAAB3NzaC1yc2EAAAADAQABAAABAQDB4PJ+UMVHirITARNsmRnZllz6wk2INO9i
nAaxYiSO7j2UlLEd7XEp/wWHB/Iy7jRKe3XIOVGaabPgKxsuBu5kYw+9cbXV7fj4
LSlJVS+kXpqpFN4uXWkNErtGeOCbey74jxJEtBHipssbpVdY4W5WnCKpsTEtpTSE
VhM80/50Cs2mxYQQqyiGTqlNd2GDdXNane8IyOXYlOyENreUPunbEhJIBF4RjR+d
8QCZDMfhnoMjDAZ0W4xahAiD6gUEz0BGs7b8UiNGzPoB5xH9Z5TvYkTDhomJzX9w
AlADo+JAEfCS6jdaWXW1unF5FmgHY1AbbYRPIku+F9Nqig0tP0el
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

        self.cli_set(base_path + ['polling-period', polling])

        for cache_name, cache_config in cache.items():
            self.cli_set(base_path + ['cache', cache_name, 'port', cache_config['port']])
            self.cli_set(base_path + ['cache', cache_name, 'preference', cache_config['preference']])
            self.cli_set(base_path + ['cache', cache_name, 'ssh', 'username', cache_config['username']])
            self.cli_set(base_path + ['cache', cache_name, 'ssh', 'key', rpki_key_name])

        # commit changes
        self.cli_commit()

        # Verify FRR configuration
        frrconfig = self.getFRRconfig('rpki')
        self.assertIn(f'rpki polling_period {polling}', frrconfig)

        for cache_name, cache_config in cache.items():
            port = cache_config['port']
            preference = cache_config['preference']
            username = cache_config['username']
            self.assertIn(f'rpki cache {cache_name} {port} {username} /run/frr/id_rpki_{cache_name} /run/frr/id_rpki_{cache_name}.pub preference {preference}', frrconfig)

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
