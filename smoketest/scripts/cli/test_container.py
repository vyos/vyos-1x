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
import json

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.util import cmd
from vyos.util import process_named_running
from vyos.util import read_file

base_path = ['container']
cont_image = 'busybox'
prefix = '192.168.205.0/24'
net_name = 'NET01'
PROCESS_NAME = 'podman'

def cmd_to_json(command):
    c = cmd(command + ' --format=json')
    data = json.loads(c)[0]

    return data


class TesContainer(VyOSUnitTestSHIM.TestCase):

    def test_01_basic_container(self):
        cont_name = 'c1'

        self.cli_set(['interfaces', 'ethernet', 'eth0', 'address', '10.0.2.15/24'])
        self.cli_set(['protocols', 'static', 'route', '0.0.0.0/0', 'next-hop', '10.0.2.2'])
        self.cli_set(['system', 'name-server', '1.1.1.1'])
        self.cli_set(['system', 'name-server', '8.8.8.8'])

        self.cli_set(base_path + ['name', cont_name, 'image', cont_image])
        self.cli_set(base_path + ['name', cont_name, 'allow-host-networks'])

        # commit changes
        self.cli_commit()

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_02_container_network(self):
        cont_name = 'c2'
        cont_ip = '192.168.205.25'
        self.cli_set(base_path + ['network', net_name, 'ipv4-prefix', prefix])
        self.cli_set(base_path + ['name', cont_name, 'image', cont_image])
        self.cli_set(base_path + ['name', cont_name, 'network', net_name, 'address', cont_ip])

        # commit changes
        self.cli_commit()

        n = cmd_to_json(f'sudo podman network inspect {net_name}')
        json_subnet = n['plugins'][0]['ipam']['ranges'][0][0]['subnet']

        c = cmd_to_json(f'sudo podman container inspect {cont_name}')
        json_ip = c['NetworkSettings']['Networks'][net_name]['IPAddress']

        self.assertEqual(json_subnet, prefix)
        self.assertEqual(json_ip, cont_ip)

if __name__ == '__main__':
    unittest.main(verbosity=2)
