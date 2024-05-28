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
import glob
import json

from base_vyostest_shim import VyOSUnitTestSHIM
from ipaddress import ip_interface

from vyos.configsession import ConfigSessionError
from vyos.utils.process import cmd
from vyos.utils.process import process_named_running

base_path = ['container']
cont_image = 'busybox:stable' # busybox is included in vyos-build
PROCESS_NAME = 'conmon'
PROCESS_PIDFILE = '/run/vyos-container-{0}.service.pid'

busybox_image_path = '/usr/share/vyos/busybox-stable.tar'

def cmd_to_json(command):
    c = cmd(command + ' --format=json')
    data = json.loads(c)[0]
    return data

class TestContainer(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestContainer, cls).setUpClass()

        # Load image for smoketest provided in vyos-build
        try:
            cmd(f'cat {busybox_image_path} | sudo podman load')
        except:
            cls.skipTest(cls, reason='busybox image not available')

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    @classmethod
    def tearDownClass(cls):
        super(TestContainer, cls).tearDownClass()

        # Cleanup podman image
        cmd(f'sudo podman image rm -f {cont_image}')

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

        # Ensure no container process remains
        self.assertIsNone(process_named_running(PROCESS_NAME))

        # Ensure systemd units are removed
        units = glob.glob('/run/systemd/system/vyos-container-*')
        self.assertEqual(units, [])

    def test_basic(self):
        cont_name = 'c1'

        self.cli_set(['interfaces', 'ethernet', 'eth0', 'address', '10.0.2.15/24'])
        self.cli_set(['protocols', 'static', 'route', '0.0.0.0/0', 'next-hop', '10.0.2.2'])
        self.cli_set(['system', 'name-server', '1.1.1.1'])
        self.cli_set(['system', 'name-server', '8.8.8.8'])

        self.cli_set(base_path + ['name', cont_name, 'image', cont_image])
        self.cli_set(base_path + ['name', cont_name, 'allow-host-networks'])

        # commit changes
        self.cli_commit()

        pid = 0
        with open(PROCESS_PIDFILE.format(cont_name), 'r') as f:
            pid = int(f.read())

        # Check for running process
        self.assertEqual(process_named_running(PROCESS_NAME), pid)

    def test_cpu_limit(self):
        cont_name = 'c2'

        self.cli_set(base_path + ['name', cont_name, 'allow-host-networks'])
        self.cli_set(base_path + ['name', cont_name, 'image', cont_image])
        self.cli_set(base_path + ['name', cont_name, 'cpu-quota', '1.25'])

        self.cli_commit()

        pid = 0
        with open(PROCESS_PIDFILE.format(cont_name), 'r') as f:
            pid = int(f.read())

        # Check for running process
        self.assertEqual(process_named_running(PROCESS_NAME), pid)

    def test_ipv4_network(self):
        prefix = '192.0.2.0/24'
        base_name = 'ipv4'
        net_name = 'NET01'

        self.cli_set(base_path + ['network', net_name, 'prefix', prefix])

        for ii in range(1, 6):
            name = f'{base_name}-{ii}'
            self.cli_set(base_path + ['name', name, 'image', cont_image])
            self.cli_set(base_path + ['name', name, 'network', net_name, 'address', str(ip_interface(prefix).ip + ii)])

        # verify() - first IP address of a prefix can not be used by a container
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        tmp = f'{base_name}-1'
        self.cli_delete(base_path + ['name', tmp])
        self.cli_commit()

        n = cmd_to_json(f'sudo podman network inspect {net_name}')
        self.assertEqual(n['subnets'][0]['subnet'], prefix)

        # skipt first container, it was never created
        for ii in range(2, 6):
            name = f'{base_name}-{ii}'
            c = cmd_to_json(f'sudo podman container inspect {name}')
            self.assertEqual(c['NetworkSettings']['Networks'][net_name]['Gateway']  , str(ip_interface(prefix).ip + 1))
            self.assertEqual(c['NetworkSettings']['Networks'][net_name]['IPAddress'], str(ip_interface(prefix).ip + ii))

    def test_ipv6_network(self):
        prefix = '2001:db8::/64'
        base_name = 'ipv6'
        net_name = 'NET02'

        self.cli_set(base_path + ['network', net_name, 'prefix', prefix])

        for ii in range(1, 6):
            name = f'{base_name}-{ii}'
            self.cli_set(base_path + ['name', name, 'image', cont_image])
            self.cli_set(base_path + ['name', name, 'network', net_name, 'address', str(ip_interface(prefix).ip + ii)])

        # verify() - first IP address of a prefix can not be used by a container
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        tmp = f'{base_name}-1'
        self.cli_delete(base_path + ['name', tmp])
        self.cli_commit()

        n = cmd_to_json(f'sudo podman network inspect {net_name}')
        self.assertEqual(n['subnets'][0]['subnet'], prefix)

        # skipt first container, it was never created
        for ii in range(2, 6):
            name = f'{base_name}-{ii}'
            c = cmd_to_json(f'sudo podman container inspect {name}')
            self.assertEqual(c['NetworkSettings']['Networks'][net_name]['IPv6Gateway']      , str(ip_interface(prefix).ip + 1))
            self.assertEqual(c['NetworkSettings']['Networks'][net_name]['GlobalIPv6Address'], str(ip_interface(prefix).ip + ii))

    def test_dual_stack_network(self):
        prefix4 = '192.0.2.0/24'
        prefix6 = '2001:db8::/64'
        base_name = 'dual-stack'
        net_name = 'net-4-6'

        self.cli_set(base_path + ['network', net_name, 'prefix', prefix4])
        self.cli_set(base_path + ['network', net_name, 'prefix', prefix6])

        for ii in range(1, 6):
            name = f'{base_name}-{ii}'
            self.cli_set(base_path + ['name', name, 'image', cont_image])
            self.cli_set(base_path + ['name', name, 'network', net_name, 'address', str(ip_interface(prefix4).ip + ii)])
            self.cli_set(base_path + ['name', name, 'network', net_name, 'address', str(ip_interface(prefix6).ip + ii)])

        # verify() - first IP address of a prefix can not be used by a container
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        tmp = f'{base_name}-1'
        self.cli_delete(base_path + ['name', tmp])
        self.cli_commit()

        n = cmd_to_json(f'sudo podman network inspect {net_name}')
        self.assertEqual(n['subnets'][0]['subnet'], prefix4)
        self.assertEqual(n['subnets'][1]['subnet'], prefix6)

        # skipt first container, it was never created
        for ii in range(2, 6):
            name = f'{base_name}-{ii}'
            c = cmd_to_json(f'sudo podman container inspect {name}')
            self.assertEqual(c['NetworkSettings']['Networks'][net_name]['IPv6Gateway']      , str(ip_interface(prefix6).ip + 1))
            self.assertEqual(c['NetworkSettings']['Networks'][net_name]['GlobalIPv6Address'], str(ip_interface(prefix6).ip + ii))
            self.assertEqual(c['NetworkSettings']['Networks'][net_name]['Gateway']          , str(ip_interface(prefix4).ip + 1))
            self.assertEqual(c['NetworkSettings']['Networks'][net_name]['IPAddress']        , str(ip_interface(prefix4).ip + ii))

    def test_uid_gid(self):
        cont_name = 'uid-test'
        gid = '100'
        uid = '1001'

        self.cli_set(base_path + ['name', cont_name, 'allow-host-networks'])
        self.cli_set(base_path + ['name', cont_name, 'image', cont_image])
        self.cli_set(base_path + ['name', cont_name, 'gid', gid])

        # verify() - GID can only be set if UID is set
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(base_path + ['name', cont_name, 'uid', uid])

        self.cli_commit()

        # verify
        tmp = cmd(f'sudo podman exec -it {cont_name} id -u')
        self.assertEqual(tmp, uid)
        tmp = cmd(f'sudo podman exec -it {cont_name} id -g')
        self.assertEqual(tmp, gid)

if __name__ == '__main__':
    unittest.main(verbosity=2)
