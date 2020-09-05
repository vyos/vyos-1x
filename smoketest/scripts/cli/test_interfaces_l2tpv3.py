#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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
import jmespath
import unittest

from base_interfaces_test import BasicInterfaceTest
from vyos.util import cmd

class GeneveInterfaceTest(BasicInterfaceTest.BaseTest):
    def setUp(self):
        super().setUp()

        self._base_path = ['interfaces', 'l2tpv3']
        self._options = {
            'l2tpeth10': ['local-ip 127.0.0.1', 'remote-ip 127.10.10.10',
                          'tunnel-id 100', 'peer-tunnel-id 10',
                          'session-id 100', 'peer-session-id 10',
                          'source-port 1010', 'destination-port 10101'],
            'l2tpeth20': ['local-ip 127.0.0.1', 'peer-session-id 20',
                          'peer-tunnel-id 200', 'remote-ip 127.20.20.20',
                          'session-id 20', 'tunnel-id 200',
                          'source-port 2020', 'destination-port 20202'],
        }
        self._interfaces = list(self._options)

    def test_add_address_single(self):
        super().test_add_address_single()

        command = 'sudo ip -j l2tp show session'
        json_out = json.loads(cmd(command))
        for interface in self._options:
            for config in json_out:
                if config['interface'] == interface:
                    # convert list with configuration items into a dict
                    dict = {}
                    for opt in self._options[interface]:
                        dict.update({opt.split()[0].replace('-','_'): opt.split()[1]})

                    for key in ['peer_session_id', 'peer_tunnel_id', 'session_id', 'tunnel_id']:
                        self.assertEqual(str(config[key]), dict[key])


if __name__ == '__main__':
    unittest.main()
