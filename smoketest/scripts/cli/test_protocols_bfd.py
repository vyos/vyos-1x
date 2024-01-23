#!/usr/bin/env python3
#
# Copyright (C) 2021-2023 VyOS maintainers and contributors
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

PROCESS_NAME = 'bfdd'
base_path = ['protocols', 'bfd']

dum_if = 'dum1001'
vrf_name = 'red'
peers = {
    '192.0.2.10' : {
        'intv_rx'    : '500',
        'intv_tx'    : '600',
        'multihop'   : '',
        'source_addr': '192.0.2.254',
        'profile'    : 'foo-bar-baz',
        'minimum_ttl': '20',
    },
    '192.0.2.20' : {
        'echo_mode'  : '',
        'intv_echo'  : '100',
        'intv_mult'  : '100',
        'intv_rx'    : '222',
        'intv_tx'    : '333',
        'passive'    : '',
        'shutdown'   : '',
        'profile'    : 'foo',
        'source_intf': dum_if,
    },
    '2001:db8::1000:1' : {
        'source_addr': '2001:db8::1',
        'vrf'        : vrf_name,
    },
    '2001:db8::2000:1' : {
        'source_addr': '2001:db8::1',
        'multihop'   : '',
        'profile'    : 'baz_foo',
    },
}

profiles = {
    'foo' : {
        'echo_mode'  : '',
        'intv_echo'  : '100',
        'intv_mult'  : '101',
        'intv_rx'    : '222',
        'intv_tx'    : '333',
        'shutdown'   : '',
        'minimum_ttl': '40',
        },
    'foo-bar-baz' : {
        'intv_mult'  : '4',
        'intv_rx'    : '400',
        'intv_tx'    : '400',
        },
    'baz_foo' : {
        'intv_mult'  : '102',
        'intv_rx'    : '444',
        'passive'    : '',
        },
}

class TestProtocolsBFD(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestProtocolsBFD, cls).setUpClass()

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

    def test_bfd_peer(self):
        self.cli_set(['vrf', 'name', vrf_name, 'table', '1000'])

        for peer, peer_config in peers.items():
            if 'echo_mode' in peer_config:
                self.cli_set(base_path + ['peer', peer, 'echo-mode'])
            if 'intv_echo' in peer_config:
                self.cli_set(base_path + ['peer', peer, 'interval', 'echo-interval', peer_config["intv_echo"]])
            if 'intv_mult' in peer_config:
                self.cli_set(base_path + ['peer', peer, 'interval', 'multiplier', peer_config["intv_mult"]])
            if 'intv_rx' in peer_config:
                self.cli_set(base_path + ['peer', peer, 'interval', 'receive', peer_config["intv_rx"]])
            if 'intv_tx' in peer_config:
                self.cli_set(base_path + ['peer', peer, 'interval', 'transmit', peer_config["intv_tx"]])
            if 'minimum_ttl' in peer_config:
                self.cli_set(base_path + ['peer', peer, 'minimum-ttl', peer_config["minimum_ttl"]])
            if 'multihop' in peer_config:
                self.cli_set(base_path + ['peer', peer, 'multihop'])
            if 'passive' in peer_config:
                self.cli_set(base_path + ['peer', peer, 'passive'])
            if 'shutdown' in peer_config:
                self.cli_set(base_path + ['peer', peer, 'shutdown'])
            if 'source_addr' in peer_config:
                self.cli_set(base_path + ['peer', peer, 'source', 'address', peer_config["source_addr"]])
            if 'source_intf' in peer_config:
                self.cli_set(base_path + ['peer', peer, 'source', 'interface', peer_config["source_intf"]])
            if 'vrf' in peer_config:
                self.cli_set(base_path + ['peer', peer, 'vrf', peer_config["vrf"]])

        # commit changes
        self.cli_commit()

        # Verify FRR bgpd configuration
        frrconfig = self.getFRRconfig('bfd', daemon=PROCESS_NAME)
        for peer, peer_config in peers.items():
            tmp = f'peer {peer}'
            if 'multihop' in peer_config:
                tmp += f' multihop'
            if 'source_addr' in peer_config:
                tmp += f' local-address {peer_config["source_addr"]}'
            if 'source_intf' in peer_config:
                tmp += f' interface {peer_config["source_intf"]}'
            if 'vrf' in peer_config:
                tmp += f' vrf {peer_config["vrf"]}'

            self.assertIn(tmp, frrconfig)
            peerconfig = self.getFRRconfig(f' peer {peer}', end='', daemon=PROCESS_NAME)

            if 'echo_mode' in peer_config:
                self.assertIn(f'echo-mode', peerconfig)
            if 'intv_echo' in peer_config:
                self.assertIn(f'echo receive-interval {peer_config["intv_echo"]}', peerconfig)
                self.assertIn(f'echo transmit-interval {peer_config["intv_echo"]}', peerconfig)
            if 'intv_mult' in peer_config:
                self.assertIn(f'detect-multiplier {peer_config["intv_mult"]}', peerconfig)
            if 'intv_rx' in peer_config:
                self.assertIn(f'receive-interval {peer_config["intv_rx"]}', peerconfig)
            if 'intv_tx' in peer_config:
                self.assertIn(f'transmit-interval {peer_config["intv_tx"]}', peerconfig)
            if 'minimum_ttl' in peer_config:
                self.assertIn(f'minimum-ttl {peer_config["minimum_ttl"]}', peerconfig)
            if 'passive' in peer_config:
                self.assertIn(f'passive-mode', peerconfig)
            if 'shutdown' in peer_config:
                self.assertIn(f'shutdown', peerconfig)
            else:
                self.assertNotIn(f'shutdown', peerconfig)

        self.cli_delete(['vrf', 'name', vrf_name])

    def test_bfd_profile(self):
        for profile, profile_config in profiles.items():
            if 'echo_mode' in profile_config:
                self.cli_set(base_path + ['profile', profile, 'echo-mode'])
            if 'intv_echo' in profile_config:
                self.cli_set(base_path + ['profile', profile, 'interval', 'echo-interval', profile_config["intv_echo"]])
            if 'intv_mult' in profile_config:
                self.cli_set(base_path + ['profile', profile, 'interval', 'multiplier', profile_config["intv_mult"]])
            if 'intv_rx' in profile_config:
                self.cli_set(base_path + ['profile', profile, 'interval', 'receive', profile_config["intv_rx"]])
            if 'intv_tx' in profile_config:
                self.cli_set(base_path + ['profile', profile, 'interval', 'transmit', profile_config["intv_tx"]])
            if 'minimum_ttl' in profile_config:
                self.cli_set(base_path + ['profile', profile, 'minimum-ttl', profile_config["minimum_ttl"]])
            if 'passive' in profile_config:
                self.cli_set(base_path + ['profile', profile, 'passive'])
            if 'shutdown' in profile_config:
                self.cli_set(base_path + ['profile', profile, 'shutdown'])

        for peer, peer_config in peers.items():
            if 'profile' in peer_config:
                self.cli_set(base_path + ['peer', peer, 'profile', peer_config["profile"] + 'wrong'])
            if 'source_addr' in peer_config:
                self.cli_set(base_path + ['peer', peer, 'source', 'address', peer_config["source_addr"]])
            if 'source_intf' in peer_config:
                self.cli_set(base_path + ['peer', peer, 'source', 'interface', peer_config["source_intf"]])

        # BFD profile does not exist!
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        for peer, peer_config in peers.items():
            if 'profile' in peer_config:
                self.cli_set(base_path + ['peer', peer, 'profile', peer_config["profile"]])

        # commit changes
        self.cli_commit()

        # Verify FRR bgpd configuration
        for profile, profile_config in profiles.items():
            config = self.getFRRconfig(f' profile {profile}', endsection='^ !')
            if 'echo_mode' in profile_config:
                self.assertIn(f' echo-mode', config)
            if 'intv_echo' in profile_config:
                self.assertIn(f' echo receive-interval {profile_config["intv_echo"]}', config)
                self.assertIn(f' echo transmit-interval {profile_config["intv_echo"]}', config)
            if 'intv_mult' in profile_config:
                self.assertIn(f' detect-multiplier {profile_config["intv_mult"]}', config)
            if 'intv_rx' in profile_config:
                self.assertIn(f' receive-interval {profile_config["intv_rx"]}', config)
            if 'intv_tx' in profile_config:
                self.assertIn(f' transmit-interval {profile_config["intv_tx"]}', config)
            if 'minimum_ttl' in profile_config:
                self.assertIn(f' minimum-ttl {profile_config["minimum_ttl"]}', config)
            if 'passive' in profile_config:
                self.assertIn(f' passive-mode', config)
            if 'shutdown' in profile_config:
                self.assertIn(f' shutdown', config)
            else:
                self.assertNotIn(f'shutdown', config)

        for peer, peer_config in peers.items():
            peerconfig = self.getFRRconfig(f' peer {peer}', end='', daemon=PROCESS_NAME)
            if 'profile' in peer_config:
                self.assertIn(f' profile {peer_config["profile"]}', peerconfig)

if __name__ == '__main__':
    unittest.main(verbosity=2)
