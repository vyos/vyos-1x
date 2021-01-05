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

import os
import unittest

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.util import cmd
from vyos.util import process_named_running

PROCESS_NAME = 'bgpd'
ASN = '64512'
base_path = ['protocols', 'bgp', ASN]

neighbor_config = {
    '192.0.2.1' : {
        'remote_as'   : '100',
        'adv_interv'  : '400',
        'passive'     : '',
        'password'    : 'VyOS-Secure123',
        'shutdown'    : '',
        'cap_over'    : '',
        'ttl_security': '5',
        },
    '192.0.2.2' : {
        'remote_as'   : '200',
        'shutdown'    : '',
        'no_cap_nego' : '',
        'port'        : '667',
        'cap_strict'  : '',
        },
    '192.0.2.3' : {
#        XXX: not available in current Perl backend
#       'description' : 'foo bar baz',
        'remote_as'   : '200',
        'passive'     : '',
        'multi_hop'   : '5',
        },
}

peer_group_config = {
    'foo' : {
        'remote_as'   : '100',
        'passive'     : '',
        'password'    : 'VyOS-Secure123',
        'shutdown'    : '',
        'cap_over'    : '',
#        XXX: not available in current Perl backend
#       'ttl_security': '5',
        },
    'bar' : {
        'remote_as'   : '200',
        'shutdown'    : '',
        'no_cap_nego' : '',
        },
    'baz' : {
        'remote_as'   : '200',
        'passive'     : '',
        'multi_hop'   : '5',
        },
}


def getFRRBGPconfig():
    return cmd(f'vtysh -c "show run" | sed -n "/router bgp {ASN}/,/^!/p"')

class TestProtocolsBGP(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())

    def tearDown(self):
        self.session.delete(base_path)
        self.session.commit()
        del self.session

    def test_bgp_01_simple(self):
        router_id = '127.0.0.1'
        local_pref = '500'

        self.session.set(base_path + ['parameters', 'router-id', router_id])
        self.session.set(base_path + ['parameters', 'log-neighbor-changes'])
        # Default local preference (higher=more preferred)
        self.session.set(base_path + ['parameters', 'default', 'local-pref', local_pref])
        # Deactivate IPv4 unicast for a peer by default
        self.session.set(base_path + ['parameters', 'default', 'no-ipv4-unicast'])

        # commit changes
        self.session.commit()

        # Verify FRR bgpd configuration
        frrconfig = getFRRBGPconfig()
        self.assertIn(f'router bgp {ASN}', frrconfig)
        self.assertIn(f' bgp router-id {router_id}', frrconfig)
        self.assertIn(f' bgp log-neighbor-changes', frrconfig)
        self.assertIn(f' bgp default local-preference {local_pref}', frrconfig)
        self.assertIn(f' no bgp default ipv4-unicast', frrconfig)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_bgp_02_neighbors(self):
        for neighbor, config in neighbor_config.items():
            if 'remote_as' in config:
                self.session.set(base_path + ['neighbor', neighbor, 'remote-as', config["remote_as"]])
            if 'description' in config:
                self.session.set(base_path + ['neighbor', neighbor, 'description', config["description"]])
            if 'passive' in config:
                self.session.set(base_path + ['neighbor', neighbor, 'passive'])
            if 'password' in config:
                self.session.set(base_path + ['neighbor', neighbor, 'password', config["password"]])
            if 'shutdown' in config:
                self.session.set(base_path + ['neighbor', neighbor, 'shutdown'])
            if 'adv_interv' in config:
                self.session.set(base_path + ['neighbor', neighbor, 'advertisement-interval', config["adv_interv"]])
            if 'no_cap_nego' in config:
                self.session.set(base_path + ['neighbor', neighbor, 'disable-capability-negotiation'])
            if 'port' in config:
                self.session.set(base_path + ['neighbor', neighbor, 'port', config["port"]])
            if 'multi_hop' in config:
                self.session.set(base_path + ['neighbor', neighbor, 'ebgp-multihop', config["multi_hop"]])
            if 'cap_over' in config:
                self.session.set(base_path + ['neighbor', neighbor, 'override-capability'])
            if 'cap_strict' in config:
                self.session.set(base_path + ['neighbor', neighbor, 'strict-capability-match'])
            if 'ttl_security' in config:
                self.session.set(base_path + ['neighbor', neighbor, 'ttl-security', 'hops', config["ttl_security"]])

        # commit changes
        self.session.commit()

        # Verify FRR bgpd configuration
        frrconfig = getFRRBGPconfig()
        self.assertIn(f'router bgp {ASN}', frrconfig)

        for neighbor, config in neighbor_config.items():
            if 'remote_as' in config:
                self.assertIn(f' neighbor {neighbor} remote-as {config["remote_as"]}', frrconfig)
            if 'description' in config:
                self.assertIn(f' neighbor {neighbor} description {config["description"]}', frrconfig)
            if 'passive' in config:
                self.assertIn(f' neighbor {neighbor} passive', frrconfig)
            if 'password' in config:
                self.assertIn(f' neighbor {neighbor} password {config["password"]}', frrconfig)
            if 'shutdown' in config:
                self.assertIn(f' neighbor {neighbor} shutdown', frrconfig)
            if 'adv_interv' in config:
                self.assertIn(f' neighbor {neighbor} advertisement-interval {config["adv_interv"]}', frrconfig)
            if 'no_cap_nego' in config:
                self.assertIn(f' neighbor {neighbor} dont-capability-negotiate', frrconfig)
            if 'port' in config:
                self.assertIn(f' neighbor {neighbor} port {config["port"]}', frrconfig)
            if 'multi_hop' in config:
                self.assertIn(f' neighbor {neighbor} ebgp-multihop {config["multi_hop"]}', frrconfig)
            if 'cap_over' in config:
                self.assertIn(f' neighbor {neighbor} override-capability', frrconfig)
            if 'cap_strict' in config:
                self.assertIn(f' neighbor {neighbor} strict-capability-match', frrconfig)
            if 'ttl_security' in config:
                self.assertIn(f' neighbor {neighbor} ttl-security hops {config["ttl_security"]}', frrconfig)

    def test_bgp_03_peer_groups(self):
        for peer_group, config in peer_group_config.items():
            self.session.set(base_path + ['peer-group', peer_group, 'remote-as', config["remote_as"]])
            if 'passive' in config:
                self.session.set(base_path + ['peer-group', peer_group, 'passive'])
            if 'password' in config:
                self.session.set(base_path + ['peer-group', peer_group, 'password', config["password"]])
            if 'shutdown' in config:
                self.session.set(base_path + ['peer-group', peer_group, 'shutdown'])
            if 'no_cap_nego' in config:
                self.session.set(base_path + ['peer-group', peer_group, 'disable-capability-negotiation'])
            if 'multi_hop' in config:
                self.session.set(base_path + ['peer-group', peer_group, 'ebgp-multihop', config["multi_hop"]])
            if 'cap_over' in config:
                self.session.set(base_path + ['peer-group', peer_group, 'override-capability'])
            if 'ttl_security' in config:
                self.session.set(base_path + ['peer-group', peer_group, 'ttl-security', 'hops', config["ttl_security"]])

        # commit changes
        self.session.commit()

        # Verify FRR bgpd configuration
        frrconfig = getFRRBGPconfig()
        self.assertIn(f'router bgp {ASN}', frrconfig)

        for peer_group, config in peer_group_config.items():
            self.assertIn(f' neighbor {peer_group} peer-group', frrconfig)

            if 'remote_as' in config:
                self.assertIn(f' neighbor {peer_group} remote-as {config["remote_as"]}', frrconfig)
            if 'passive' in config:
                self.assertIn(f' neighbor {peer_group} passive', frrconfig)
            if 'password' in config:
                self.assertIn(f' neighbor {peer_group} password {config["password"]}', frrconfig)
            if 'shutdown' in config:
                self.assertIn(f' neighbor {peer_group} shutdown', frrconfig)
            if 'no_cap_nego' in config:
                self.assertIn(f' neighbor {peer_group} dont-capability-negotiate', frrconfig)
            if 'multi_hop' in config:
                self.assertIn(f' neighbor {peer_group} ebgp-multihop {config["multi_hop"]}', frrconfig)
            if 'cap_over' in config:
                self.assertIn(f' neighbor {peer_group} override-capability', frrconfig)
            if 'ttl_security' in config:
                self.assertIn(f' neighbor {peer_group} ttl-security hops {config["ttl_security"]}', frrconfig)

if __name__ == '__main__':
    unittest.main(verbosity=2)
