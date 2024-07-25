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

import json
import unittest

from base_interfaces_test import BasicInterfaceTest
from vyos.utils.process import cmd
from vyos.utils.kernel import unload_kmod
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

        command = 'sudo ip -j l2tp show session'
        json_out = json.loads(cmd(command))
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


if __name__ == '__main__':
    # when re-running this test, cleanup loaded modules first so they are
    # reloaded on demand - not needed but test more and more features
    for module in ['l2tp_ip6', 'l2tp_ip', 'l2tp_eth', 'l2tp_eth',
                   'l2tp_netlink', 'l2tp_core']:
        unload_kmod(module)

    unittest.main(verbosity=2)
