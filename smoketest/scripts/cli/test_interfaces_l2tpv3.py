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

import json
import unittest

from base_interfaces_test import BasicInterfaceTest
from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.utils.network import get_interface_config
from vyos.utils.process import cmdl
from vyos.utils.kernel import unload_kmod

def get_l2tp(kind: str) -> list:
    # "ip l2tp show" ignores a tunnel_id filter
    return json.loads(cmdl(['ip', '-j', 'l2tp', 'show', kind], sudo=True))

class L2TPv3InterfaceTest(BasicInterfaceTest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._base_path = ['interfaces', 'l2tpv3']
        cls._options = {
            'l2tpeth10': ['source-address 127.0.0.1', 'remote 127.10.10.10',
                          'tunnel-id 100', 'peer-tunnel-id 10',
                          'session-id 100', 'peer-session-id 10',
                          'source-port 1010', 'destination-port 10101'],
            'l2tpeth20': ['source-address 127.0.0.1', 'peer-session-id 20',
                          'peer-tunnel-id 200', 'remote 127.20.20.20',
                          'session-id 20', 'tunnel-id 200',
                          'source-port 2020', 'destination-port 20202'],
        }
        cls._interfaces = list(cls._options)
        # call base-classes classmethod
        super(L2TPv3InterfaceTest, cls).setUpClass()

    def test_add_single_ip_address(self):
        super().test_add_single_ip_address()

        command = ['ip', '-j', 'l2tp', 'show', 'session']
        json_out = json.loads(cmdl(command, sudo=True))
        for interface in self._options:
            for config in json_out:
                if config['interface'] == interface:
                    # convert list with configuration items into a dict
                    dict = {}
                    for opt in self._options[interface]:
                        dict.update({opt.split()[0].replace('-','_'): opt.split()[1]})

                    for key in ['peer_session_id', 'peer_tunnel_id',
                                'session_id', 'tunnel_id']:
                        self.assertEqual(str(config[key]), dict[key])

    def test_shared_tunnel(self):
        # Interfaces sharing one tunnel, each one with its own session
        tunnel_id = 300
        sessions = range(301, 306)
        interfaces = [f'l2tpeth{session}' for session in sessions]

        def tunnel_peers():
            return [tunnel['peer'] for tunnel in get_l2tp('tunnel')
                    if tunnel['tunnel_id'] == tunnel_id]

        def tunnel_sessions():
            return {session['interface']: session['session_id']
                    for session in get_l2tp('session')
                    if session['tunnel_id'] == tunnel_id}

        for session, interface in zip(sessions, interfaces):
            path = self._base_path + [interface]
            self.cli_set(path + ['source-address', '127.0.0.1'])
            self.cli_set(path + ['remote', '127.30.30.30'])
            self.cli_set(path + ['tunnel-id', str(tunnel_id)])
            self.cli_set(path + ['peer-tunnel-id', '30'])
            self.cli_set(path + ['session-id', str(session)])
            self.cli_set(path + ['peer-session-id', str(session - 300)])
            self.cli_set(path + ['source-port', '3030'])
            self.cli_set(path + ['destination-port', '30303'])
        self.cli_commit()

        expected = dict(zip(interfaces, sessions))
        self.assertEqual(tunnel_peers(), ['127.30.30.30'])
        self.assertEqual(tunnel_sessions(), expected)

        # Changing one interface recreates its session only, the other
        # sessions in the tunnel must survive
        ifindex = {i: get_interface_config(i)['ifindex'] for i in interfaces}
        self.cli_set(self._base_path + [interfaces[0], 'mtu', '1400'])
        self.cli_commit()
        self.assertEqual(tunnel_sessions(), expected)
        self.assertEqual(get_interface_config(interfaces[0])['mtu'], 1400)
        for interface in interfaces[1:]:
            self.assertEqual(get_interface_config(interface)['ifindex'],
                             ifindex[interface])

        # Tunnel settings must be identical on all interfaces sharing it.
        # Commit errors are line wrapped, hence the \s+ in the patterns below
        self.cli_set(self._base_path + [interfaces[-1], 'remote', '127.31.31.31'])
        with self.assertRaisesRegex(ConfigSessionError, r'different\s+"remote"'):
            self.cli_commit()
        self.cli_discard()

        # Every session in the tunnel needs its own session-id
        self.cli_set(self._base_path + [interfaces[-1], 'session-id', str(sessions[0])])
        with self.assertRaisesRegex(ConfigSessionError, r'already\s+uses\s+session-id'):
            self.cli_commit()
        self.cli_discard()

        # Changing the tunnel on all interfaces at once rebuilds it with all
        # sessions
        for interface in interfaces:
            self.cli_set(self._base_path + [interface, 'remote', '127.31.31.31'])
        self.cli_commit()
        self.assertEqual(tunnel_peers(), ['127.31.31.31'])
        self.assertEqual(tunnel_sessions(), expected)

        # Replacing an interface in the same commit keeps the tunnel
        old = interfaces.pop()
        new = 'l2tpeth306'
        self.cli_delete(self._base_path + [old])
        for option in ['source-address 127.0.0.1', 'remote 127.31.31.31',
                       f'tunnel-id {tunnel_id}', 'peer-tunnel-id 30',
                       'session-id 306', 'peer-session-id 6',
                       'source-port 3030', 'destination-port 30303']:
            self.cli_set(self._base_path + [new] + option.split())
        self.cli_commit()
        interfaces.append(new)
        del expected[old]
        expected[new] = 306
        self.assertEqual(tunnel_peers(), ['127.31.31.31'])
        self.assertEqual(tunnel_sessions(), expected)

        # The tunnel is kept as long as an interface still uses it
        self.cli_delete(self._base_path + [interfaces[0]])
        self.cli_commit()
        del expected[interfaces[0]]
        self.assertEqual(tunnel_peers(), ['127.31.31.31'])
        self.assertEqual(tunnel_sessions(), expected)

        self.cli_delete(self._base_path)
        self.cli_commit()
        self.assertEqual(tunnel_peers(), [])
        self.assertEqual(tunnel_sessions(), {})

    def test_change_ids(self):
        # Changing the tunnel or session ID of an interface must release the
        # session it holds in the Kernel, other sessions stay untouched
        def l2tp_sessions():
            return sorted((s['interface'], s['tunnel_id'], s['session_id'])
                          for s in get_l2tp('session') if s['tunnel_id'] in (600, 610))

        def l2tp_tunnels():
            return sorted(t['tunnel_id'] for t in get_l2tp('tunnel')
                          if t['tunnel_id'] in (600, 610))

        for interface, session in [('l2tpeth601', 601), ('l2tpeth602', 602)]:
            for option in ['source-address 127.0.0.1', 'remote 127.60.60.60',
                           'tunnel-id 600', 'peer-tunnel-id 60',
                           f'session-id {session}', f'peer-session-id {session - 600}']:
                self.cli_set(self._base_path + [interface] + option.split())
        self.cli_commit()
        self.assertEqual(l2tp_sessions(), [('l2tpeth601', 600, 601),
                                           ('l2tpeth602', 600, 602)])

        ifindex = get_interface_config('l2tpeth602')['ifindex']
        self.cli_set(self._base_path + ['l2tpeth601', 'session-id', '603'])
        self.cli_commit()
        self.assertEqual(l2tp_sessions(), [('l2tpeth601', 600, 603),
                                           ('l2tpeth602', 600, 602)])
        self.assertEqual(get_interface_config('l2tpeth602')['ifindex'], ifindex)

        # The old tunnel stays as long as another interface uses it. Two UDP
        # tunnels can not share the local address and port.
        for option in ['tunnel-id 610', 'source-port 6100', 'destination-port 6101']:
            self.cli_set(self._base_path + ['l2tpeth602'] + option.split())
        self.cli_commit()
        self.assertEqual(l2tp_tunnels(), [600, 610])
        self.assertEqual(l2tp_sessions(), [('l2tpeth601', 600, 603),
                                           ('l2tpeth602', 610, 602)])

        for option in ['tunnel-id 610', 'source-port 6100', 'destination-port 6101']:
            self.cli_set(self._base_path + ['l2tpeth601'] + option.split())
        self.cli_commit()
        self.assertEqual(l2tp_tunnels(), [610])
        self.assertEqual(l2tp_sessions(), [('l2tpeth601', 610, 603),
                                           ('l2tpeth602', 610, 602)])

        self.cli_delete(self._base_path)
        self.cli_commit()
        self.assertEqual(l2tp_tunnels(), [])

    def test_session_error(self):
        # With IP encapsulation the Kernel rejects a session ID used in another
        # tunnel. The commit must fail with a clean error and not leave the
        # tunnel created for the session behind.
        for interface, tunnel in [('l2tpeth701', '700'), ('l2tpeth711', '710')]:
            for option in ['encapsulation ip', 'source-address 127.0.0.1',
                           'remote 127.70.70.70', f'tunnel-id {tunnel}',
                           f'peer-tunnel-id {tunnel}', 'session-id 777',
                           'peer-session-id 777']:
                self.cli_set(self._base_path + [interface] + option.split())
            if interface == 'l2tpeth701':
                self.cli_commit()

        with self.assertRaisesRegex(ConfigSessionError,
                                    r'Could\s+not\s+create\s+L2TPv3\s+session\s+777') as e:
            self.cli_commit()
        self.assertNotIn('Traceback', str(e.exception))
        self.cli_discard()

        self.assertEqual(sorted(t['tunnel_id'] for t in get_l2tp('tunnel')
                                if t['tunnel_id'] in (700, 710)), [700])
        self.assertEqual([(s['interface'], s['tunnel_id']) for s in get_l2tp('session')
                          if s['session_id'] == 777], [('l2tpeth701', 700)])

    def test_ids_leading_zero(self):
        # The CLI accepts IDs with leading zeros, iproute2 would read them octal
        interface = 'l2tpeth500'
        path = self._base_path + [interface]
        for option in ['source-address 127.0.0.1', 'remote 127.50.50.50',
                       'tunnel-id 0500', 'peer-tunnel-id 050',
                       'session-id 0500', 'peer-session-id 050']:
            self.cli_set(path + option.split())
        self.cli_commit()

        tunnels = [t for t in get_l2tp('tunnel') if t['tunnel_id'] == 500]
        self.assertEqual([t['peer_tunnel'] for t in tunnels], [50])
        sessions = [(s['interface'], s['session_id'], s['peer_session_id'])
                    for s in get_l2tp('session') if s['tunnel_id'] == 500]
        self.assertEqual(sessions, [(interface, 500, 50)])

        # Re-applying must find its own tunnel and session again
        self.cli_set(path + ['mtu', '1400'])
        self.cli_commit()
        self.assertEqual(get_interface_config(interface)['mtu'], 1400)

        self.cli_delete(path)
        self.cli_commit()
        # 320 is 0500 read as octal
        self.assertEqual([t for t in get_l2tp('tunnel') if t['tunnel_id'] in (320, 500)], [])


if __name__ == '__main__':
    # when re-running this test, cleanup loaded modules first so they are
    # reloaded on demand - not needed but test more and more features
    for module in ['l2tp_ip6', 'l2tp_ip', 'l2tp_eth', 'l2tp_eth',
                   'l2tp_netlink', 'l2tp_core']:
        unload_kmod(module)

    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
