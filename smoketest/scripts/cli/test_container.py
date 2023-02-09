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

import re
import unittest
import glob
import json

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.util import cmd
from vyos.util import process_named_running
from vyos.util import read_file

base_path = ['container']
cont_image = 'busybox:stable' # busybox is included in vyos-build
prefix = '192.168.205.0/24'
net_name = 'NET01'
PROCESS_NAME = 'conmon'
PROCESS_PIDFILE = '/run/vyos-container-{0}.service.pid'
config_containers_registry = '/etc/containers/registries.conf'

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

        pid = 0
        with open(PROCESS_PIDFILE.format(cont_name), 'r') as f:
            pid = int(f.read())

        # Check for running process
        self.assertEqual(process_named_running(PROCESS_NAME), pid)

    def test_02_container_network(self):
        cont_name = 'c2'
        cont_ip = '192.168.205.25'
        self.cli_set(base_path + ['network', net_name, 'prefix', prefix])
        self.cli_set(base_path + ['name', cont_name, 'image', cont_image])
        self.cli_set(base_path + ['name', cont_name, 'network', net_name, 'address', cont_ip])

        # commit changes
        self.cli_commit()

        n = cmd_to_json(f'sudo podman network inspect {net_name}')
        json_subnet = n['subnets'][0]['subnet']

        c = cmd_to_json(f'sudo podman container inspect {cont_name}')
        json_ip = c['NetworkSettings']['Networks'][net_name]['IPAddress']

        self.assertEqual(json_subnet, prefix)
        self.assertEqual(json_ip, cont_ip)

    def test_03_container_registry(self):
        def extract_rendered_registry(text_to_find):
            registry_pattern = re.compile(r'^unqualified-search-registries = (\[.*\])', re.M)
            return re.findall(registry_pattern, text_to_find)

        with open(config_containers_registry, 'r') as f:
            registry_conf_content = f.read()

        expected_default_render_registry = json.dumps(['docker.io', 'quay.io'])
        default_rendered_registry = extract_rendered_registry(registry_conf_content)
        self.assertNotEqual(0, len(default_rendered_registry))
        self.assertEqual(expected_default_render_registry, default_rendered_registry[-1])

        self.cli_set(base_path + ['registry', 'docker.io'])
        self.cli_set(base_path + ['registry', 'example.com'])
        self.cli_commit()
        expected_render_registry = json.dumps(['docker.io', 'quay.io', 'example.com'])
        rendered_registry = extract_rendered_registry(registry_conf_content)
        self.assertNotEqual(0, len(rendered_registry))
        self.assertEqual(expected_render_registry, rendered_registry[-1])

if __name__ == '__main__':
    unittest.main(verbosity=2)
