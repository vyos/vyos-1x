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

import os
import unittest
import glob
import json
import dbus
from tempfile import TemporaryDirectory

from base_vyostest_shim import VyOSUnitTestSHIM
from ipaddress import ip_interface

from vyos.configsession import ConfigSessionError
from vyos.config import Config
from vyos.configtree import ConfigTree
from vyos.component_version import version_info_from_file
from vyos.defaults import directories
from vyos.defaults import podman_mount_program
from vyos.utils.file import read_file
from vyos.utils.misc import wait_for
from vyos.utils.network import get_interface_vrf
from vyos.utils.network import interface_exists
from vyos.utils.process import cmdl
from vyos.utils.process import process_named_running

base_path = ['container']
PROCESS_NAME = 'conmon'
config_storage = '/etc/containers/storage.conf'

busybox_image = 'busybox:stable'
busybox_image_path = '/usr/share/vyos/busybox-stable.tar'

def cmd_to_json(command):
    c = cmdl(['podman'] + command + ['--format=json'], sudo=True)
    data = json.loads(c)[0]
    return data

class TestContainer(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestContainer, cls).setUpClass()

        # Load image for smoketest provided in vyos-1x-smoketest
        if not os.path.exists(busybox_image_path):
            cls.fail(cls, f'{busybox_image} image not available')
        cmdl(['podman', 'load', '-i', busybox_image_path], sudo=True)

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)
        cls.cli_delete(cls, ['vrf'])

    @classmethod
    def tearDownClass(cls):
        super(TestContainer, cls).tearDownClass()
        # Cleanup podman image
        cmdl(['podman', 'image', 'rm', '-f', busybox_image], sudo=True)

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

        # Ensure no container process remains
        self.assertIsNone(process_named_running(PROCESS_NAME))

        # Ensure systemd units are removed
        units = glob.glob('/run/containers/systemd/vyos*')
        self.assertEqual(units, [])
        # always forward to base class
        super().tearDown()

    def is_running(self, name):
        command = ['systemctl', 'show', f'vyos-container-{name}', '--property=ActiveState', '--value']
        return cmdl(command).strip() == 'active'

    def _test_legacy_network_migration(self, legacy_options, expected_driver):
        net_name = 'mig-net'
        cont_name = 'mig-app'
        host_name = 'mig-host'
        network_path = base_path + ['network', net_name]
        self.cli_commit()

        with TemporaryDirectory() as directory:
            config_file = os.path.join(directory, 'config.boot')
            self.cli_save(config_file)
            version = version_info_from_file(config_file)
            config = ConfigTree(version.config_body)
            config.set(network_path + ['prefix'], value='198.51.100.0/24')
            config.set(network_path + ['gateway'], value='198.51.100.254')
            config.set(network_path + ['type', 'macvlan'])
            for option, value in legacy_options:
                config.set(network_path + ['type'] + option.split(), value=value)
            for name in [cont_name, host_name]:
                config.set(base_path + ['name', name, 'image'], value=busybox_image)
                config.set(base_path + ['name', name, 'command'], value='sleep 86400')
                config.set(base_path + ['name', name, 'stop-timeout'], value='1')
            config.set(base_path + ['name', cont_name, 'network', net_name, 'address'],
                       value='198.51.100.10')
            config.set(base_path + ['name', host_name, 'allow-host-networks'])
            config.set_tag(base_path + ['network'])
            config.set_tag(base_path + ['name'])
            config.set_tag(base_path + ['name', cont_name, 'network'])
            version.update_config_body(config.to_string(no_version=True))
            version.update_component('container', 3)
            version.write(config_file)

            self._session.migrate_and_load_config(config_file)
            self.cli_commit()

        self.assertTrue(self.is_running(cont_name))
        self.assertTrue(self.is_running(host_name))
        network = cmd_to_json(['network', 'inspect', net_name])
        self.assertEqual(network['driver'], expected_driver)
        self.assertEqual(network['subnets'][0]['subnet'], '198.51.100.0/24')
        self.assertEqual(network['subnets'][0]['gateway'], '198.51.100.254')
        if expected_driver == 'macvlan':
            self.assertEqual(network['network_interface'], 'eth0')
            self.assertEqual(network['options']['mode'], 'bridge')
        else:
            self.assertEqual(network['network_interface'], f'pod-{net_name}')
        container = cmd_to_json(['container', 'inspect', cont_name])
        self.assertTrue(container['State']['Running'])
        self.assertEqual(container['NetworkSettings']['Networks'][net_name]['IPAddress'],
                         '198.51.100.10')
        host = cmd_to_json(['container', 'inspect', host_name])
        self.assertTrue(host['State']['Running'])
        self.assertEqual(host['HostConfig']['NetworkMode'], 'host')

    def test_migrate_legacy_bridge_and_macvlan(self):
        if not interface_exists('eth0'):
            self.skipTest('MACVLAN migration requires an Ethernet parent')
        self._test_legacy_network_migration([
            ('bridge', None), ('macvlan parent', 'eth0'), ('macvlan mode', 'bridge'),
        ], 'macvlan')

    def test_migrate_legacy_bare_macvlan(self):
        self._test_legacy_network_migration([], 'bridge')

    def test_basic(self):
        cont_name = 'c1'
        env_key = 'TestKey'
        env_key1 = 'TestKey1'
        env_value = 'TestValue,*'
        env_value1 = 'Test Spaced Values'

        self.cli_set(['interfaces', 'ethernet', 'eth0', 'address', '10.0.2.15/24'])
        self.cli_set(['protocols', 'static', 'route', '0.0.0.0/0',
                      'next-hop', '10.0.2.2', 'distance', '230'])
        self.cli_set(['system', 'name-server', '1.1.1.1'])
        self.cli_set(['system', 'name-server', '8.8.8.8'])

        self.cli_set(base_path + ['name', cont_name, 'image', busybox_image])
        self.cli_set(base_path + ['name', cont_name, 'allow-host-networks'])
        self.cli_set(base_path + ['name', cont_name, 'sysctl', 'parameter',
                                  'kernel.msgmax', 'value', '4096'])
        self.cli_set(base_path + ['name', cont_name, 'log-driver', 'journald'])
        self.cli_set(base_path + ['name', cont_name, 'allow-host-cgroups'])
        self.cli_set(base_path + ['name', cont_name, 'stop-timeout', '1'])
        self.cli_set(base_path + ['name', cont_name, 'environment', env_key, 'value', env_value])
        self.cli_set(base_path + ['name', cont_name, 'environment', env_key1, 'value', env_value1])
        # commit changes
        self.cli_commit()

        self.assertTrue(self.is_running(cont_name))

        # verify
        tmp = cmdl(['podman', 'exec', '-it', cont_name, 'sysctl', 'kernel.msgmax'], sudo=True)
        self.assertEqual(tmp, 'kernel.msgmax = 4096')

        l = cmd_to_json(['container', 'inspect', cont_name])
        self.assertEqual(l['HostConfig']['LogConfig']['Type'], 'journald')
        self.assertEqual(l['Config']['Healthcheck']['Test'], ['NONE'])
        self.assertEqual(l['HostConfig']['CgroupMode'], 'host')
        self.assertIn(f'{env_key}={env_value}', l['Config']['Env'])
        self.assertIn(f'{env_key1}={env_value1}', l['Config']['Env'])

        # cleanup
        self.cli_delete(['interfaces', 'ethernet', 'eth0', 'address'])
        self.cli_delete(['protocols', 'static'])
        self.cli_delete(['system', 'name-server'])

    def test_healthcheck(self):
        cont_name = 'health-test'

        self.cli_set(base_path + ['name', cont_name, 'allow-host-networks'])
        self.cli_set(base_path + ['name', cont_name, 'image', busybox_image])
        self.cli_set(base_path + ['name', cont_name, 'stop-timeout', '1'])

        self.cli_set(base_path + ['name', cont_name, 'health-check', 'command', 'true'])
        self.cli_set(base_path + ['name', cont_name, 'health-check', 'interval', '10'])
        self.cli_set(base_path + ['name', cont_name, 'health-check', 'timeout', '1'])
        self.cli_set(base_path + ['name', cont_name, 'health-check', 'retry', '2'])
        self.cli_commit()

        l = cmd_to_json(['container', 'inspect', cont_name])
        self.assertEqual(l['HostConfig']['LogConfig']['Type'], 'journald')
        self.assertEqual(l['Config']['Healthcheck']['Test'], ['CMD-SHELL', 'true'])
        self.assertEqual(l['Config']['Healthcheck']['Interval'], 10000000000)
        self.assertEqual(l['Config']['Healthcheck']['Timeout'], 1000000000)
        self.assertEqual(l['Config']['Healthcheck']['Retries'], 2)

    def test_name_server(self):
        cont_name = 'dns-test'
        net_name = 'net-test'
        name_servers = ['192.168.0.1', '192.168.0.2']
        prefix = '192.0.2.0/24'

        self.cli_set(base_path + ['network', net_name, 'prefix', prefix])

        self.cli_set(base_path + ['name', cont_name, 'image', busybox_image])
        self.cli_set(base_path + ['name', cont_name, 'stop-timeout', '1'])
        for name_server in name_servers:
            self.cli_set(base_path + ['name', cont_name, 'name-server', name_server])
        self.cli_set(
            base_path
            + [
                'name',
                cont_name,
                'network',
                net_name,
                'address',
                str(ip_interface(prefix).ip + 2),
            ]
        )

        # verify() - name server has no effect when container network has dns enabled
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(base_path + ['network', net_name, 'no-name-server'])
        self.cli_commit()

        n = cmd_to_json(['inspect', cont_name])
        self.assertEqual(n['HostConfig']['Dns'], name_servers)

        tmp = cmdl(['podman', 'exec', '-it', cont_name, 'cat', '/etc/resolv.conf'], sudo=True)
        self.assertIn(name_server, tmp)

    def test_cpu_limit(self):
        cont_name = 'c2'

        self.cli_set(base_path + ['name', cont_name, 'allow-host-networks'])
        self.cli_set(base_path + ['name', cont_name, 'image', busybox_image])
        self.cli_set(base_path + ['name', cont_name, 'cpu-quota', '1.25'])
        self.cli_set(base_path + ['name', cont_name, 'stop-timeout', '1'])

        self.cli_commit()

        self.assertTrue(self.is_running(cont_name))

    def test_unmanaged_bridge(self):
        bridge = 'br1149'
        network = 'unmanaged'
        name = 'unmanaged1'
        interface_path = ['interfaces', 'bridge', bridge]
        self.cli_set(interface_path + ['address', '10.250.49.1/24'])
        self.cli_set(interface_path + ['address', 'fd00:1149::1/64'])
        self.cli_set(base_path + ['network', network, 'prefix', '10.250.49.0/24'])
        self.cli_set(base_path + ['network', network, 'prefix', 'fd00:1149::/64'])
        self.cli_set(base_path + ['network', network, 'no-name-server'])
        self.cli_set(base_path + ['network', network, 'type', 'bridge', 'interface', bridge])
        self.cli_set(base_path + ['name', name, 'image', busybox_image])
        self.cli_set(base_path + ['name', name, 'command', 'sleep 3600'])
        self.cli_set(base_path + ['name', name, 'capability', 'net-raw'])
        self.cli_set(base_path + ['name', name, 'stop-timeout', '1'])
        self.cli_set(base_path + ['name', name, 'network', network, 'address', '10.250.49.2'])
        self.cli_set(base_path + ['name', name, 'network', network, 'address', 'fd00:1149::2'])
        try:
            self.cli_commit()
            self.assertTrue(self.is_running(name))
            info = cmd_to_json(['network', 'inspect', network])
            self.assertEqual(info['network_interface'], bridge)
            self.assertEqual(info['options']['mode'], 'unmanaged')
            container_id = cmd_to_json(['inspect', name])['Id']
            network_id = info['id']
            self.cli_set(base_path + ['network', network, 'description', 'native attachment'])
            self.cli_commit()
            self.assertEqual(cmd_to_json(['inspect', name])['Id'], container_id)
            self.assertEqual(cmd_to_json(['network', 'inspect', network])['id'], network_id)
            for path, value in [
                (interface_path, None),
                (interface_path + ['disable'], ''),
                (interface_path + ['address', '10.250.49.1/24'], None),
                (interface_path + ['mtu'], '1400'),
                (base_path + ['network', network, 'mtu'], '1400'),
                (base_path + ['network', network, 'type', 'bridge', 'interface'], None),
            ]:
                with self.subTest(path=path):
                    if value is None:
                        self.cli_delete(path)
                    elif value:
                        self.cli_set(path + [value])
                    else:
                        self.cli_set(path)
                    with self.assertRaises(ConfigSessionError):
                        self.cli_commit()
                    self.cli_discard()

            self.cli_set(base_path + ['network', 'shared', 'type', 'bridge', 'interface', bridge])
            self.cli_set(base_path + ['network', 'shared', 'prefix', '10.250.49.0/24'])
            self.cli_set(base_path + ['network', 'shared', 'no-name-server'])
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
            self.cli_discard()

            self.cli_set(base_path + ['network', 'overlap', 'prefix', '10.250.49.0/25'])
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
            self.cli_discard()

            self.cli_delete(interface_path + ['address', '10.250.49.1/24'])
            self.cli_set(interface_path + ['address', '10.250.49.1/25'])
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
            self.cli_discard()

            self.cli_set(['vrf', 'name', 'unmanaged', 'table', '1149'])
            self.cli_set(interface_path + ['vrf', 'unmanaged'])
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
            self.cli_discard()

            self.cli_set(interface_path + ['mtu', '1400'])
            self.cli_set(base_path + ['network', network, 'mtu', '1400'])
            self.cli_commit()
            self.assertTrue(self.is_running(name))
            self.assertEqual(cmd_to_json(['network', 'inspect', network])['options']['mtu'], '1400')

            # Network recreation returns before IPv6 DAD completes.
            container_pid = str(cmd_to_json(['inspect', name])['State']['Pid'])

            def ipv6_ready():
                info = json.loads(cmdl(['nsenter', '-t', container_pid, '-n',
                                       'ip', '-6', '-j', 'addr', 'show', 'dev', 'eth0'], sudo=True))[0]
                addresses = info.get('addr_info', [])
                return (any(a['local'] == 'fd00:1149::2' for a in addresses)
                        and not any(a.get('tentative', False) for a in addresses))

            self.assertTrue(wait_for(ipv6_ready, timeout=10), 'Container IPv6 DAD did not complete')
            cmdl(['podman', 'exec', name, 'ping', '-c', '1', '-W', '2', '10.250.49.1'], sudo=True)
            cmdl(['podman', 'exec', name, 'ping', '-6', '-c', '1', '-W', '2', 'fd00:1149::1'], sudo=True)
            ruleset = json.loads(cmdl(['nft', '-j', 'list', 'ruleset'], sudo=True))
            rules = [item['rule'] for item in ruleset['nftables']
                     if 'rule' in item and item['rule']['table'] == 'netavark']
            self.assertNotIn('10.250.49.0', json.dumps(rules))
            self.assertNotIn('fd00:1149::', json.dumps(rules))
            self.cli_delete(base_path + ['name', name])
            self.cli_set(base_path + ['network', network, 'description', 'no consumers'])
            self.cli_commit()
            self.assertFalse(self.is_running(name))
            self.assertNotIn(name, cmdl(['podman', 'ps', '-a', '--format', '{{.Names}}'], sudo=True).splitlines())
            self.cli_delete(base_path + ['network', network])
            self.cli_commit()
            links = json.loads(cmdl(['ip', '-j', 'address', 'show', 'dev', bridge]))
            self.assertEqual(links[0]['ifname'], bridge)
            addresses = {a['local'] for a in links[0]['addr_info']}
            self.assertIn('10.250.49.1', addresses)
            self.assertIn('fd00:1149::1', addresses)
        finally:
            self.cli_delete(base_path)
            self.cli_commit()
            self.cli_delete(interface_path)
            self.cli_commit()

    def test_unmanaged_network_replacement(self):
        interface_path = ['interfaces', 'bridge', 'br1190']
        old_path = base_path + ['network', 'old']
        new_path = base_path + ['network', 'new']
        prefixes = ['10.250.190.0/24', 'fd00:1190::/64']
        try:
            for address in ['10.250.190.1/24', 'fd00:1190::1/64']:
                self.cli_set(interface_path + ['address', address])
            for prefix in prefixes:
                self.cli_set(old_path + ['prefix', prefix])
            self.cli_set(old_path + ['no-name-server'])
            self.cli_set(old_path + ['type', 'bridge', 'interface', 'br1190'])
            self.cli_commit()
            for prefix in prefixes:
                with self.subTest(prefix=prefix):
                    self.cli_delete(old_path)
                    self.cli_set(new_path + ['prefix', prefix])
                    self.cli_set(new_path + ['no-name-server'])
                    with self.assertRaises(ConfigSessionError):
                        self.cli_commit()
                    self.cli_discard()
            self.cli_delete(old_path)
            for prefix in prefixes:
                self.cli_set(new_path + ['prefix', prefix])
            self.cli_set(new_path + ['no-name-server'])
            self.cli_delete(interface_path + ['address'])
            self.cli_commit()
        finally:
            self.cli_delete(base_path)
            self.cli_commit()
            self.cli_delete(interface_path)
            self.cli_commit()

    def test_unmanaged_bridge_dhcp_requires_configured_bridge(self):
        bridge = 'br1223'
        interface_path = ['interfaces', 'bridge', bridge]
        network_path = base_path + ['network', 'dhcp1223']
        if Config().exists(interface_path) or interface_exists(bridge):
            self.skipTest('DHCP bridge existence fixture already exists')
        try:
            self.cli_set(network_path + ['type', 'bridge', 'interface', bridge])
            self.cli_set(network_path + ['ipam', 'dhcp'])
            self.cli_set(network_path + ['no-name-server'])
            with self.assertRaisesRegex(ConfigSessionError,
                                        f'VyOS bridge "{bridge}" must be configured and enabled'):
                self.cli_commit()
            self.assertFalse(interface_exists(bridge))
            self.assertNotIn('dhcp1223', cmdl(['podman', 'network', 'ls',
                             '--format', '{{.Name}}'], sudo=True).splitlines())
            self.cli_discard()

            self.cli_set(interface_path)
            self.cli_set(network_path + ['type', 'bridge', 'interface', bridge])
            self.cli_set(network_path + ['ipam', 'dhcp'])
            self.cli_set(network_path + ['no-name-server'])
            self.cli_commit()
            self.assertTrue(interface_exists(bridge))
            self.assertTrue(Config().exists_effective(network_path))
            self.assertFalse(Config().exists_effective(interface_path + ['address']))

            self.cli_delete(network_path)
            self.cli_commit()
            self.cli_set(network_path + ['type', 'bridge', 'interface', bridge])
            self.cli_set(network_path + ['ipam', 'dhcp'])
            self.cli_set(network_path + ['no-name-server'])
            self.cli_commit()
            self.assertTrue(interface_exists(bridge))
            self.assertTrue(Config().exists_effective(network_path))
            self.assertFalse(Config().exists_effective(interface_path + ['address']))
        finally:
            self.cli_discard()
            self.cli_delete(base_path)
            self.cli_commit()
            self.cli_delete(interface_path)
            self.cli_commit()

    def test_unmanaged_bridge_dhcp(self):
        if Config().exists(['service', 'dhcp-server']):
            self.skipTest('Requires an unconfigured DHCP server for the test fixture')

        bridge = 'br1215'
        peers = ['veth1214', 'veth1215']
        network = 'dhcp1215'
        name = 'dhcp1215'
        network_path = base_path + ['network', network]
        name_path = base_path + ['name', name]
        server_path = ['service', 'dhcp-server']
        pool = server_path + ['shared-network-name', 'CONTAINER1215',
                              'subnet', '10.250.215.0/24']
        for interface in [bridge] + peers:
            kind = 'bridge' if interface == bridge else 'virtual-ethernet'
            if Config().exists(['interfaces', kind, interface]) or os.path.exists(f'/sys/class/net/{interface}'):
                self.skipTest(f'Test fixture interface {interface} already exists')

        try:
            self.cli_set(['interfaces', 'virtual-ethernet', peers[0], 'peer-name', peers[1]])
            self.cli_set(['interfaces', 'virtual-ethernet', peers[1], 'peer-name', peers[0]])
            self.cli_set(['interfaces', 'virtual-ethernet', peers[1], 'address', '10.250.215.1/24'])
            self.cli_set(['interfaces', 'bridge', bridge, 'member', 'interface', peers[0]])
            self.cli_set(server_path + ['listen-interface', peers[1]])
            self.cli_set(pool + ['subnet-id', '1215'])
            self.cli_set(pool + ['range', '1', 'start', '10.250.215.100'])
            self.cli_set(pool + ['range', '1', 'stop', '10.250.215.110'])
            self.cli_set(pool + ['option', 'default-router', '10.250.215.1'])
            self.cli_set(pool + ['option', 'name-server', '192.0.2.53'])
            self.cli_set(network_path + ['type', 'bridge', 'interface', bridge])
            self.cli_set(network_path + ['ipam', 'dhcp'])
            self.cli_set(network_path + ['no-name-server'])
            self.cli_set(name_path + ['image', busybox_image])
            self.cli_set(name_path + ['command', 'sleep 3600'])
            self.cli_set(name_path + ['capability', 'net-raw'])
            self.cli_set(name_path + ['stop-timeout', '1'])
            self.cli_set(name_path + ['network', network, 'mac', '02:00:00:00:12:15'])
            self.cli_commit()
            self.assertTrue(wait_for(lambda: self.is_running(name), timeout=90))

            def check_lease(driver, expect_gateway=True):
                info = cmd_to_json(['network', 'inspect', network])
                self.assertEqual(info['driver'], driver)
                self.assertEqual(info['ipam_options']['driver'], 'dhcp')
                pid = str(cmd_to_json(['inspect', name])['State']['Pid'])
                addresses = json.loads(cmdl(['nsenter', '-t', pid, '-n', 'ip', '-j',
                                             'address', 'show', 'dev', 'eth0'], sudo=True))
                leased = [a['local'] for link in addresses for a in link['addr_info']
                          if a['family'] == 'inet']
                self.assertTrue(any(f'10.250.215.{i}' in leased for i in range(100, 111)))
                routes = json.loads(cmdl(['nsenter', '-t', pid, '-n', 'ip', '-j', 'route'], sudo=True))
                defaults = [r for r in routes if r.get('dst') == 'default']
                if expect_gateway:
                    self.assertTrue(any(r.get('gateway') == '10.250.215.1' for r in defaults))
                else:
                    self.assertEqual(defaults, [])
                dns = cmdl(['podman', 'exec', name, 'cat', '/etc/resolv.conf'], sudo=True)
                self.assertIn('nameserver 192.0.2.53', dns)
                cmdl(['podman', 'exec', name, 'ping', '-c', '1', '-W', '2', '10.250.215.1'], sudo=True)

            check_lease('bridge')
            for path in [network_path + ['prefix', '10.250.215.0/24'],
                         network_path + ['gateway', '10.250.215.1'],
                         name_path + ['network', network, 'address', '10.250.215.2']]:
                with self.subTest(path=path):
                    self.cli_set(path)
                    diagnostic = ('DHCP IPAM cannot be combined with configured prefixes or gateways'
                                  if path[:3] == network_path else 'cannot use a static address with DHCP IPAM')
                    with self.assertRaisesRegex(ConfigSessionError, diagnostic):
                        self.cli_commit()
                    self.cli_discard()

            self.cli_delete(network_path + ['type', 'bridge'])
            self.cli_set(network_path + ['type', 'macvlan', 'parent', bridge])
            self.cli_set(network_path + ['type', 'macvlan', 'mode', 'bridge'])
            self.cli_commit()
            self.assertTrue(wait_for(lambda: self.is_running(name), timeout=90))
            check_lease('macvlan')

            self.cli_delete(name_path)
            self.cli_delete(pool + ['option', 'default-router'])
            self.cli_commit()
            self.cli_set(name_path + ['image', busybox_image])
            self.cli_set(name_path + ['command', 'sleep 3600'])
            self.cli_set(name_path + ['capability', 'net-raw'])
            self.cli_set(name_path + ['stop-timeout', '1'])
            self.cli_set(name_path + ['network', network, 'mac', '02:00:00:00:12:15'])
            self.cli_commit()
            self.assertTrue(wait_for(lambda: self.is_running(name), timeout=90))
            check_lease('macvlan', expect_gateway=False)
        finally:
            self.cli_delete(base_path)
            self.cli_delete(server_path)
            self.cli_commit()
            self.cli_delete(['interfaces', 'bridge', bridge])
            for peer in peers:
                self.cli_delete(['interfaces', 'virtual-ethernet', peer])
            self.cli_commit()

    def test_unmanaged_bridge_recovery(self):
        bridge = 'br1216'
        interface_path = ['interfaces', 'bridge', bridge]
        if Config().exists(interface_path) or os.path.exists(f'/sys/class/net/{bridge}'):
            self.skipTest('Bridge recovery fixture already exists')
        name = 'recover1216'
        other = name + '-bridge-recovery'
        network = 'recover1216'
        try:
            self.cli_set(interface_path + ['address', '10.250.216.1/24'])
            self.cli_set(base_path + ['network', network, 'prefix', '10.250.216.0/24'])
            self.cli_set(base_path + ['network', network, 'no-name-server'])
            self.cli_set(base_path + ['network', network, 'type', 'bridge', 'interface', bridge])
            self.cli_set(base_path + ['name', name, 'image', busybox_image])
            self.cli_set(base_path + ['name', name, 'command', 'sleep 3600'])
            self.cli_set(base_path + ['name', name, 'capability', 'net-raw'])
            self.cli_set(base_path + ['name', name, 'stop-timeout', '1'])
            self.cli_set(base_path + ['name', name, 'network', network, 'address', '10.250.216.2'])
            self.cli_set(base_path + ['name', other, 'image', busybox_image])
            self.cli_set(base_path + ['name', other, 'command', 'sleep 3600'])
            self.cli_set(base_path + ['name', other, 'stop-timeout', '1'])
            self.cli_set(base_path + ['name', other, 'network', network, 'address', '10.250.216.3'])
            self.cli_commit()
            self.assertTrue(self.is_running(other))
            for cycle in range(6):
                with self.subTest(cycle=cycle):
                    cmdl(['ip', 'link', 'delete', bridge], sudo=True)
                    self.assertTrue(wait_for(lambda: not self.is_running(name), timeout=10))
                    cmdl(['ip', 'link', 'add', bridge, 'type', 'bridge'], sudo=True)
                    cmdl(['ip', 'address', 'add', '10.250.216.1/24', 'dev', bridge], sudo=True)
                    cmdl(['ip', 'link', 'set', bridge, 'up'], sudo=True)
                    self.assertTrue(wait_for(lambda: self.is_running(name), timeout=30),
                                    'Container did not recover after bridge recreation')
                    state = cmdl(['systemctl', 'show', f'vyos-{network}-network',
                                  '--property=ActiveState', '--value']).strip()
                    self.assertEqual(state, 'active')
                    self.assertTrue(wait_for(lambda: self.is_running(other), timeout=30),
                                    'Second container did not recover after bridge recreation')
                    cmdl(['podman', 'exec', name, 'ping', '-c', '1', '-W', '2',
                          '10.250.216.1'], sudo=True)
            cmdl(['systemctl', 'stop', f'vyos-container-{name}'], sudo=True)
            self.assertFalse(wait_for(lambda: self.is_running(name), timeout=3),
                             'Recovery restarted a manually stopped container without a bridge event')
            self.cli_set(base_path + ['name', name, 'disable'])
            self.cli_commit()
            cmdl(['ip', 'link', 'delete', bridge], sudo=True)
            cmdl(['ip', 'link', 'add', bridge, 'type', 'bridge'], sudo=True)
            cmdl(['ip', 'address', 'add', '10.250.216.1/24', 'dev', bridge], sudo=True)
            cmdl(['ip', 'link', 'set', bridge, 'up'], sudo=True)
            self.assertFalse(wait_for(lambda: self.is_running(name), timeout=3),
                             'Recovery restarted a disabled container')
            self.cli_delete(base_path + ['name', name, 'disable'])
            self.cli_commit()
            self.assertTrue(self.is_running(name))
        finally:
            self.cli_delete(base_path)
            self.cli_commit()
            self.cli_delete(interface_path)
            self.cli_commit()

    def _configure_bridge_removal_fixture(self):
        interface_path = ['interfaces', 'bridge', 'br1221']
        network_path = base_path + ['network', 'removal1221']
        if Config().exists(interface_path) or interface_exists('br1221'):
            self.skipTest('Bridge removal fixture already exists')
        self.cli_set(interface_path + ['address', '10.250.221.1/24'])
        self.cli_set(network_path + ['prefix', '10.250.221.0/24'])
        self.cli_set(network_path + ['no-name-server'])
        self.cli_set(network_path + ['type', 'bridge', 'interface', 'br1221'])
        for name in ['removal1221', 'removalhost1221']:
            self.cli_set(base_path + ['name', name, 'image', busybox_image])
            self.cli_set(base_path + ['name', name, 'command', 'sleep 3600'])
            self.cli_set(base_path + ['name', name, 'stop-timeout', '1'])
        self.cli_set(base_path + ['name', 'removal1221', 'capability', 'net-raw'])
        self.cli_set(base_path + ['name', 'removal1221', 'network',
                                  'removal1221', 'address', '10.250.221.2'])
        self.cli_set(base_path + ['name', 'removalhost1221', 'allow-host-networks'])
        self.cli_commit()
        return interface_path, network_path

    def test_rejected_bridge_network_removal_preserves_runtime(self):
        interface_path, network_path = self._configure_bridge_removal_fixture()
        try:
            containers = {name: cmd_to_json(['inspect', name])
                          for name in ['removal1221', 'removalhost1221']}
            network_id = cmd_to_json(['network', 'inspect', 'removal1221'])['id']
            for remove_network in [False, True]:
                with self.subTest(remove_network=remove_network):
                    self.cli_delete(interface_path)
                    if remove_network:
                        self.cli_delete(network_path)
                    with self.assertRaises(ConfigSessionError):
                        self.cli_commit()
                    self.assertTrue(interface_exists('br1221'),
                                    'Rejected commit removed the bridge')
                    addresses = json.loads(cmdl(['ip', '-j', 'address', 'show', 'dev', 'br1221']))
                    self.assertIn('10.250.221.1',
                                  [a['local'] for a in addresses[0]['addr_info']])
                    for name, before in containers.items():
                        after = cmd_to_json(['inspect', name])
                        self.assertTrue(after['State']['Running'])
                        self.assertEqual(after['Id'], before['Id'])
                        self.assertEqual(after['State']['StartedAt'], before['State']['StartedAt'])
                    self.assertEqual(cmd_to_json(['network', 'inspect', 'removal1221'])['id'],
                                     network_id)
                    cmdl(['podman', 'exec', 'removal1221', 'ping', '-c', '1', '-W', '2',
                          '10.250.221.1'], sudo=True)
                    self.cli_discard()

            with TemporaryDirectory() as directory:
                config_file = os.path.join(directory, 'config.boot')
                self.cli_save(config_file)
                self._session.migrate_and_load_config(config_file)
                self.cli_commit()
            self.assertTrue(self.is_running('removal1221'))
            self.assertTrue(self.is_running('removalhost1221'))
        finally:
            self.cli_discard()
            self.cli_delete(base_path)
            self.cli_commit()
            self.cli_delete(interface_path)
            self.cli_commit()

    def test_remove_bridge_network_and_consumer(self):
        interface_path, network_path = self._configure_bridge_removal_fixture()
        try:
            host = cmd_to_json(['inspect', 'removalhost1221'])
            self.cli_delete(base_path + ['name', 'removal1221'])
            self.cli_delete(network_path)
            self.cli_delete(interface_path)
            self.cli_commit()
            self.assertFalse(interface_exists('br1221'))
            self.assertNotIn('removal1221', cmdl(['podman', 'network', 'ls',
                             '--format', '{{.Name}}'], sudo=True).splitlines())
            self.assertNotIn('removal1221', cmdl(['podman', 'ps', '-a',
                             '--format', '{{.Names}}'], sudo=True).splitlines())
            after = cmd_to_json(['inspect', 'removalhost1221'])
            self.assertTrue(after['State']['Running'])
            self.assertEqual(after['Id'], host['Id'])
            self.assertEqual(after['State']['StartedAt'], host['State']['StartedAt'])
        finally:
            self.cli_discard()
            self.cli_delete(base_path)
            self.cli_commit()
            self.cli_delete(interface_path)
            self.cli_commit()

    def test_network_removal_failure_recovery(self):
        network = 'removal1217'
        name = 'removal1217'
        sentinel = 'removal-blocker1217'
        if cmdl(['podman', 'ps', '-a', '--filter', f'name=^{sentinel}$',
                 '--format', '{{.ID}}'], sudo=True).strip():
            self.skipTest('Removal fixture name already exists')
        sentinel_id = None
        blocker_id = None
        network_path = base_path + ['network', network]
        self.cli_set(network_path + ['prefix', '10.250.217.0/24'])
        self.cli_set(base_path + ['name', name, 'image', busybox_image])
        self.cli_set(base_path + ['name', name, 'command', 'sleep 3600'])
        self.cli_set(base_path + ['name', name, 'capability', 'net-raw'])
        self.cli_set(base_path + ['name', name, 'stop-timeout', '1'])
        self.cli_set(base_path + ['name', name, 'network', network, 'address', '10.250.217.2'])
        self.cli_commit()
        try:
            sentinel_id = cmdl(['podman', 'run', '-d', '--name', sentinel, '--network', 'none',
                                busybox_image, 'sleep', '3600'], sudo=True).strip()
            blocker_id = cmdl(['podman', 'run', '-d', '--network', network,
                               busybox_image, 'sleep', '3600'], sudo=True).strip()
            self.cli_set(network_path + ['mtu', '1400'])
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
            self.cli_discard()
            self.assertTrue(wait_for(lambda: self.is_running(name), timeout=30),
                            'Consumer not restored after failed network removal')
            self.assertEqual(cmd_to_json(['network', 'inspect', network])['options']['mtu'], '1500')
            pid = str(cmd_to_json(['inspect', name])['State']['Pid'])
            links = json.loads(cmdl(['nsenter', '-t', pid, '-n', 'ip', '-j',
                                    'link', 'show', 'dev', 'eth0'], sudo=True))
            self.assertEqual(links[0]['mtu'], 1500)
            cmdl(['podman', 'exec', name, 'ping', '-c', '1', '-W', '2', '10.250.217.1'], sudo=True)
            cmdl(['podman', 'rm', '-f', blocker_id], sudo=True)
            blocker_id = None
            self.assertTrue(cmd_to_json(['inspect', sentinel_id])['State']['Running'],
                            'Network blocker cleanup removed an unrelated container')
            self.cli_set(network_path + ['mtu', '1400'])
            self.cli_commit()
            self.assertEqual(cmd_to_json(['network', 'inspect', network])['options']['mtu'], '1400')
            self.assertTrue(self.is_running(name))
        finally:
            if blocker_id is not None:
                cmdl(['podman', 'rm', '-f', '--ignore', blocker_id], sudo=True)
            if sentinel_id is not None:
                cmdl(['podman', 'rm', '-f', '--ignore', sentinel_id], sudo=True)

    def test_network_removal_restores_starting_container(self):
        network = 'start1220'
        name = 'starting1220'
        unit = f'vyos-container-{name}.service'
        dropin = f'/run/systemd/system/{unit}.d/t9592-start.conf'
        gate = '/run/t9592-starting1220'
        if os.path.exists(dropin) or os.path.exists(gate):
            self.skipTest('Starting-container fixture already exists')
        network_path = base_path + ['network', network]
        blocker_id = None
        try:
            self.cli_set(network_path + ['prefix', '10.250.220.0/24'])
            self.cli_set(base_path + ['name', name, 'image', busybox_image])
            self.cli_set(base_path + ['name', name, 'command', 'sleep 3600'])
            self.cli_set(base_path + ['name', name, 'stop-timeout', '1'])
            self.cli_set(base_path + ['name', name, 'network', network, 'address', '10.250.220.2'])
            self.cli_commit()
            blocker_id = cmdl(['podman', 'run', '-d', '--network', network,
                               busybox_image, 'sleep', '3600'], sudo=True).strip()
            cmdl(['mkdir', '-p', os.path.dirname(dropin)], sudo=True)
            cmdl(['tee', dropin], input=(
                '[Service]\n'
                f'ExecStartPre=/bin/sh -c "while [ ! -e {gate} ]; do sleep 0.1; done"\n'
            ), sudo=True)
            cmdl(['systemctl', 'daemon-reload'], sudo=True)
            cmdl(['systemctl', '--no-block', 'restart', unit], sudo=True)
            def state():
                return cmdl(['systemctl', 'show', unit, '--property=ActiveState', '--value']).strip()
            self.assertTrue(wait_for(lambda: state() == 'activating', timeout=10))
            self.cli_set(network_path + ['mtu', '1400'])
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
            self.cli_discard()
            cmdl(['touch', gate], sudo=True)
            self.assertTrue(wait_for(lambda: self.is_running(name), timeout=30),
                            'Starting consumer not restored after failed network removal')
            self.assertEqual(cmd_to_json(['network', 'inspect', network])['options']['mtu'], '1500')
        finally:
            cmdl(['rm', '-f', dropin], sudo=True)
            cmdl(['touch', gate], sudo=True)
            cmdl(['systemctl', 'daemon-reload'], sudo=True)
            if blocker_id is not None:
                cmdl(['podman', 'rm', '-f', '--ignore', blocker_id], sudo=True)
            self.cli_delete(base_path)
            self.cli_commit()
            cmdl(['rm', '-f', gate], sudo=True)

    def test_network_removal_restores_queued_start(self):
        network = 'queue1225'
        name = 'queued1225'
        active = 'active1225'
        stopped = 'stopped1225'
        unit = f'vyos-container-{name}.service'
        gate_unit = 't9592-gate1225.service'
        gate_unit_file = f'/run/systemd/system/{gate_unit}'
        dropin = f'/run/systemd/system/{unit}.d/t9592-queue.conf'
        gate = '/run/t9592-gate1225'
        if any(os.path.exists(path) for path in [gate_unit_file, dropin, gate]):
            self.skipTest('Queued-start fixture already exists')
        network_path = base_path + ['network', network]
        blocker = None

        def queued_start():
            manager = dbus.Interface(dbus.SystemBus().get_object(
                'org.freedesktop.systemd1', '/org/freedesktop/systemd1'),
                'org.freedesktop.systemd1.Manager')
            return any(job[1] == unit and job[2] == 'start' for job in manager.ListJobs())

        try:
            self.cli_set(network_path + ['prefix', '10.250.225.0/24'])
            for index, consumer in enumerate([name, active, stopped]):
                path = base_path + ['name', consumer]
                self.cli_set(path + ['image', busybox_image])
                self.cli_set(path + ['command', 'sleep 3600'])
                self.cli_set(path + ['capability', 'net-raw'])
                self.cli_set(path + ['stop-timeout', '1'])
                self.cli_set(path + ['network', network, 'address', f'10.250.225.{index + 2}'])
            self.cli_commit()
            cmdl(['systemctl', 'stop', unit, f'vyos-container-{stopped}.service'], sudo=True)
            cmdl(['systemctl', 'reset-failed', unit], sudo=True)
            blocker = cmdl(['podman', 'run', '-d', '--network', network, '--ip', '10.250.225.200',
                            busybox_image, 'sleep', '3600'], sudo=True).strip()
            cmdl(['tee', gate_unit_file], input=(
                '[Service]\nType=oneshot\nRemainAfterExit=yes\n'
                f'ExecStart=/bin/sh -c "while [ ! -e {gate} ]; do sleep 0.1; done"\n'
            ), sudo=True)
            cmdl(['mkdir', '-p', os.path.dirname(dropin)], sudo=True)
            cmdl(['tee', dropin], input=(
                f'[Unit]\nRequires={gate_unit}\nAfter={gate_unit}\n'
            ), sudo=True)
            cmdl(['systemctl', 'daemon-reload'], sudo=True)
            cmdl(['systemctl', '--no-block', 'start', unit], sudo=True)
            self.assertTrue(wait_for(queued_start, timeout=10))
            self.assertEqual(cmdl(['systemctl', 'show', unit,
                                  '--property=ActiveState', '--value']).strip(), 'inactive')
            self.assertFalse(self.is_running(stopped))

            self.cli_set(network_path + ['mtu', '1400'])
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
            self.cli_discard()
            self.assertTrue(wait_for(queued_start, timeout=10),
                            'Queued start was lost during failed network removal')
            self.assertFalse(self.is_running(stopped))
            cmdl(['touch', gate], sudo=True)
            self.assertTrue(wait_for(lambda: self.is_running(name), timeout=30),
                            'Queued consumer did not start after its dependency completed')
            self.assertTrue(wait_for(lambda: self.is_running(active), timeout=30))
            self.assertTrue(cmd_to_json(['inspect', name])['State']['Running'])
            self.assertFalse(self.is_running(stopped))
            self.assertNotIn(stopped, cmdl(['podman', 'ps', '--format', '{{.Names}}'],
                                          sudo=True).splitlines())
            self.assertEqual(cmd_to_json(['network', 'inspect', network])['options']['mtu'], '1500')
            cmdl(['podman', 'exec', name, 'ping', '-c', '1', '-W', '2',
                  '10.250.225.1'], sudo=True)
        finally:
            cmdl(['touch', gate], sudo=True)
            cmdl(['rm', '-f', dropin], sudo=True)
            cmdl(['systemctl', 'daemon-reload'], sudo=True)
            cmdl(['systemctl', 'stop', unit, gate_unit], sudo=True)
            cmdl(['rm', '-f', gate_unit_file], sudo=True)
            cmdl(['systemctl', 'daemon-reload'], sudo=True)
            if blocker is not None:
                cmdl(['podman', 'rm', '-f', '--ignore', blocker], sudo=True)
            self.cli_discard()
            self.cli_delete(base_path)
            self.cli_commit()
            cmdl(['rm', '-f', gate], sudo=True)

    def test_unmanaged_gateway_address(self):
        interface_path = ['interfaces', 'bridge', 'br1218']
        if Config().exists(interface_path) or os.path.exists('/sys/class/net/br1218'):
            self.skipTest('Gateway fixture already exists')
        network_path = base_path + ['network', 'gateway1218']
        name_path = base_path + ['name', 'gateway1218']
        try:
            for address in ['10.250.218.254/24', 'fd00:1218::fe/64']:
                self.cli_set(interface_path + ['address', address])
            for prefix in ['10.250.218.0/24', 'fd00:1218::/64']:
                self.cli_set(network_path + ['prefix', prefix])
            for gateway in ['10.250.218.254', 'fd00:1218::fe']:
                self.cli_set(network_path + ['gateway', gateway])
            self.cli_set(network_path + ['type', 'bridge', 'interface', 'br1218'])
            self.cli_set(network_path + ['no-name-server'])
            self.cli_set(name_path + ['image', busybox_image])
            self.cli_set(name_path + ['command', 'sleep 3600'])
            self.cli_set(name_path + ['stop-timeout', '1'])
            for gateway in ['10.250.218.254', 'fd00:1218::fe']:
                with self.subTest(gateway=gateway):
                    self.cli_set(name_path + ['network', 'gateway1218', 'address', gateway])
                    with self.assertRaisesRegex(ConfigSessionError, 'reserved for the network gateway'):
                        self.cli_commit()
                    self.cli_delete(name_path + ['network', 'gateway1218', 'address', gateway])
            for address in ['10.250.218.1', 'fd00:1218::1']:
                self.cli_set(name_path + ['network', 'gateway1218', 'address', address])
            self.cli_commit()
            self.assertTrue(self.is_running('gateway1218'))
            config = cmd_to_json(['inspect', 'gateway1218'])['NetworkSettings']['Networks']['gateway1218']
            self.assertEqual(config['IPAddress'], '10.250.218.1')
            self.assertEqual(config['GlobalIPv6Address'], 'fd00:1218::1')
        finally:
            self.cli_delete(base_path)
            self.cli_commit()
            self.cli_delete(interface_path)
            self.cli_commit()

    def test_unchanged_network_transition_validation(self):
        interface_path = ['interfaces', 'bridge', 'br1219']
        if Config().exists(interface_path) or os.path.exists('/sys/class/net/br1219'):
            self.skipTest('Transition fixture already exists')
        try:
            self.cli_set(interface_path + ['address', '10.250.219.1/24'])
            self.cli_set(interface_path + ['address', '10.250.220.254/24'])
            self.cli_set(base_path + ['network', 'native1219', 'type', 'bridge', 'interface', 'br1219'])
            self.cli_set(base_path + ['network', 'native1219', 'prefix', '10.250.219.0/24'])
            self.cli_set(base_path + ['network', 'native1219', 'no-name-server'])
            self.cli_set(base_path + ['network', 'managed1219', 'prefix', '10.250.220.0/24'])
            self.cli_commit()
            self.cli_set(base_path + ['network', 'managed1219', 'description', 'unchanged attachment'])
            self.cli_commit()
            self.assertTrue(Config().exists(base_path + ['network', 'managed1219', 'description']))
        finally:
            self.cli_delete(base_path)
            self.cli_commit()
            self.cli_delete(interface_path)
            self.cli_commit()

    def test_macvlan_requires_parent_and_mode(self):
        network_path = base_path + ['network', 'incomplete']
        for ipam in ['host-local', 'dhcp']:
            with self.subTest(ipam=ipam):
                try:
                    self.cli_set(network_path + ['ipam', ipam])
                    if ipam == 'host-local':
                        self.cli_set(network_path + ['prefix', '10.250.189.0/24'])
                    self.cli_set(network_path + ['type', 'macvlan'])
                    with self.assertRaisesRegex(ConfigSessionError, 'MACVLAN networks must have a parent interface'):
                        self.cli_commit()
                    self.cli_set(network_path + ['type', 'macvlan', 'parent', 'eth0'])
                    with self.assertRaisesRegex(ConfigSessionError, 'MACVLAN networks must have a mode configured'):
                        self.cli_commit()
                    self.cli_set(network_path + ['type', 'macvlan', 'mode', 'bridge'])
                    self.cli_commit()
                    cmdl(['systemctl', 'start', 'vyos-incomplete-network'], sudo=True)
                    self.assertEqual(cmd_to_json(['network', 'inspect', 'incomplete'])['driver'], 'macvlan')
                finally:
                    self.cli_delete(network_path)
                    self.cli_commit()

    def _test_consumer_restart_failures(self, native):
        network = 'restart1224'
        network_path = base_path + ['network', network]
        interface_path = ['interfaces', 'bridge', 'br1224']
        vrf_path = ['vrf', 'name', 'restart1224']
        consumers = ['a1224', 'b1224', 'c1224', 'd1224', 'e1224']
        broken = ['b1224', 'd1224']
        healthy = ['a1224', 'c1224', 'e1224']
        host_name = 'unaffected1224'
        disabled = 'f1224'
        if native and (Config().exists(interface_path) or interface_exists('br1224')):
            self.skipTest('Consumer restart bridge fixture already exists')
        if not native and (Config().exists(vrf_path) or interface_exists('restart1224')):
            self.skipTest('Consumer restart VRF fixture already exists')
        try:
            self.cli_set(network_path + ['prefix', '10.250.224.0/24'])
            self.cli_set(network_path + ['no-name-server'])
            if native:
                self.cli_set(interface_path + ['address', '10.250.224.1/24'])
                self.cli_set(network_path + ['type', 'bridge', 'interface', 'br1224'])
            else:
                self.cli_set(vrf_path + ['table', '1224'])
            for index, name in enumerate(consumers + [disabled]):
                path = base_path + ['name', name]
                self.cli_set(path + ['image', busybox_image])
                self.cli_set(path + ['command', 'sleep 3600'])
                self.cli_set(path + ['stop-timeout', '1'])
                self.cli_set(path + ['capability', 'net-raw'])
                self.cli_set(path + ['network', network, 'address', f'10.250.224.{index + 2}'])
            self.cli_set(base_path + ['name', disabled, 'disable'])
            self.cli_set(base_path + ['name', host_name, 'image', busybox_image])
            self.cli_set(base_path + ['name', host_name, 'command', 'sleep 3600'])
            self.cli_set(base_path + ['name', host_name, 'stop-timeout', '1'])
            self.cli_set(base_path + ['name', host_name, 'allow-host-networks'])
            self.cli_commit()
            for name in consumers:
                self.assertTrue(cmd_to_json(['inspect', name])['State']['Running'])
            original_network = cmd_to_json(['network', 'inspect', network])['id']
            host = cmd_to_json(['inspect', host_name])

            self.cli_set(network_path + ['mtu', '1400'])
            if native:
                self.cli_set(interface_path + ['mtu', '1400'])
            else:
                self.cli_set(network_path + ['vrf', 'restart1224'])
            for name in broken:
                self.cli_set(base_path + ['name', name, 'entrypoint', '/missing-entrypoint'])
            with self.assertRaises(ConfigSessionError) as failure:
                self.cli_commit()

            for name in healthy:
                self.assertTrue(wait_for(lambda: self.is_running(name), timeout=10),
                                f'Healthy consumer {name} was left stopped after another restart failed')
                info = cmd_to_json(['inspect', name])
                self.assertTrue(info['State']['Running'])
                pid = str(info['State']['Pid'])
                links = json.loads(cmdl(['nsenter', '-t', pid, '-n', 'ip', '-j',
                                        'link', 'show', 'dev', 'eth0'], sudo=True))
                self.assertEqual(links[0]['mtu'], 1400)
                cmdl(['podman', 'exec', name, 'ping', '-c', '1', '-W', '2',
                      '10.250.224.1'], sudo=True)
            for name in broken:
                self.assertFalse(self.is_running(name))
                self.assertIn(name, str(failure.exception))
            self.assertNotIn(disabled, str(failure.exception))
            self.assertFalse(self.is_running(disabled))
            after = cmd_to_json(['inspect', host_name])
            self.assertTrue(after['State']['Running'])
            self.assertEqual(after['Id'], host['Id'])
            self.assertEqual(after['State']['StartedAt'], host['State']['StartedAt'])
            info = cmd_to_json(['network', 'inspect', network])
            self.assertNotEqual(info['id'], original_network)
            self.assertEqual(info['options']['mtu'], '1400')
            if not native:
                self.assertEqual(get_interface_vrf(f'pod-{network}'), 'restart1224')

            for name in broken:
                self.cli_delete(base_path + ['name', name, 'entrypoint'])
            self.cli_commit()
            for name in consumers:
                self.assertTrue(cmd_to_json(['inspect', name])['State']['Running'])
            self.assertFalse(self.is_running(disabled))
        finally:
            self.cli_discard()
            self.cli_delete(base_path)
            self.cli_commit()
            self.cli_delete(interface_path if native else vrf_path)
            self.cli_commit()

    def test_managed_network_consumer_restart_failures(self):
        self._test_consumer_restart_failures(native=False)

    def test_unmanaged_network_consumer_restart_failures(self):
        self._test_consumer_restart_failures(native=True)

    def test_network_runtime_changes(self):
        network_path = base_path + ['network', 'runtime']
        name = 'runtime1'
        for network, consumer, prefix in [('runtime', name, '10.250.188.0/24'),
                                          ('untouched', 'untouched1', '10.250.187.0/24')]:
            self.cli_set(base_path + ['network', network, 'prefix', prefix])
            self.cli_set(base_path + ['name', consumer, 'image', busybox_image])
            self.cli_set(base_path + ['name', consumer, 'command', 'sleep 3600'])
            self.cli_set(base_path + ['name', consumer, 'capability', 'net-raw'])
            self.cli_set(base_path + ['name', consumer, 'stop-timeout', '1'])
            self.cli_set(base_path + ['name', consumer, 'network', network, 'address',
                                      str(ip_interface(prefix).ip + 2)])
        self.cli_commit()

        def identity(network, consumer):
            container = cmd_to_json(['inspect', consumer])
            return (cmd_to_json(['network', 'inspect', network])['id'],
                    container['Id'], container['State']['StartedAt'])

        original = identity('runtime', name)
        untouched = identity('untouched', 'untouched1')
        for setting in [['description', 'first description'], ['description', 'edited description'],
                        ['mtu', '1500'], ['type', 'bridge'], ['ipam', 'host-local'],
                        ['gateway', '10.250.188.1']]:
            with self.subTest(setting=setting):
                self.cli_set(network_path + setting)
                self.cli_commit()
                self.assertEqual(identity('runtime', name), original)
                self.assertEqual(identity('untouched', 'untouched1'), untouched)
                self.cli_delete(network_path + setting[:1])
                self.cli_commit()
                self.assertEqual(identity('runtime', name), original)

        for setting in [['mtu', '1400'], ['gateway', '10.250.188.254'], ['no-name-server']]:
            with self.subTest(setting=setting):
                before = identity('runtime', name)
                self.cli_set(network_path + setting)
                self.cli_commit()
                after = identity('runtime', name)
                self.assertNotEqual(after[0], before[0])
                self.assertNotEqual(after[1:], before[1:])
                self.assertEqual(identity('untouched', 'untouched1'), untouched)
                self.assertTrue(self.is_running(name))
                info = cmd_to_json(['network', 'inspect', 'runtime'])
                gateway = '10.250.188.254' if setting[0] != 'mtu' else '10.250.188.1'
                self.assertEqual(info['options']['mtu'], '1400')
                self.assertEqual(info['subnets'][0]['gateway'], gateway)
                self.assertEqual(info['dns_enabled'], setting[0] != 'no-name-server')
                pid = str(cmd_to_json(['inspect', name])['State']['Pid'])
                links = json.loads(cmdl(['nsenter', '-t', pid, '-n',
                                        'ip', '-j', 'link', 'show', 'dev', 'eth0'], sudo=True))
                self.assertEqual(links[0]['mtu'], 1400)
                cmdl(['podman', 'exec', name, 'ping', '-c', '1', '-W', '2', gateway], sudo=True)

    def test_network_types_mutually_exclusive(self):
        network_path = base_path + ['network', 'exclusive']
        for initial_type in ['bridge', 'macvlan']:
            with self.subTest(initial_type=initial_type):
                def set_type(network_type):
                    if network_type == 'bridge':
                        self.cli_set(network_path + ['type', 'bridge'])
                    else:
                        self.cli_set(network_path + ['type', 'macvlan', 'parent', 'eth0'])
                        self.cli_set(network_path + ['type', 'macvlan', 'mode', 'bridge'])

                other_type = 'macvlan' if initial_type == 'bridge' else 'bridge'
                try:
                    self.cli_set(network_path + ['prefix', '10.250.190.0/24'])
                    set_type(initial_type)
                    self.cli_commit()

                    set_type(other_type)
                    with self.assertRaisesRegex(ConfigSessionError, 'mutually exclusive'):
                        self.cli_commit()

                    self.cli_delete(network_path + ['type', initial_type])
                    self.cli_commit()
                finally:
                    self.cli_delete(network_path)
                    self.cli_commit()

    def test_network_types(self):
        self.cli_set(['interfaces', 'ethernet', 'eth0', 'vif', '100'])
        self.cli_set(['interfaces', 'ethernet', 'eth0', 'vif', '101'])

        # MACVLAN Networks
        self.cli_set(base_path + ['network', 'macvlan1', 'prefix', '10.0.0.0/24'])
        self.cli_set(base_path + ['network', 'macvlan1', 'type', 'macvlan', 'parent', 'eth0'])
        self.cli_set(base_path + ['network', 'macvlan1', 'type', 'macvlan', 'mode', 'bridge'])
        self.cli_set(base_path + ['network', 'macvlan2', 'prefix', '10.0.100.0/24'])
        self.cli_set(base_path + ['network', 'macvlan2', 'gateway', '10.0.100.5'])
        self.cli_set(base_path + ['network', 'macvlan2', 'type', 'macvlan', 'parent', 'eth0.100'])
        self.cli_set(base_path + ['network', 'macvlan2', 'type', 'macvlan', 'mode', 'private'])
        self.cli_set(base_path + ['network', 'macvlan3', 'prefix', '2001::/64'])
        self.cli_set(base_path + ['network', 'macvlan3', 'type', 'macvlan', 'parent', 'eth0.101'])
        self.cli_set(base_path + ['network', 'macvlan3', 'type', 'macvlan', 'mode', 'vepa'])

        # Bridge Network
        self.cli_set(base_path + ['network', 'bridge1', 'prefix', '10.0.1.0/24'])
        self.cli_set(base_path + ['network', 'bridge1', 'type', 'bridge'])

        # Bridge Network before T7186; default network type is bridge
        self.cli_set(base_path + ['network', 'bridge2', 'prefix', '10.0.2.0/24'])

        self.cli_commit()

        # Force-start the network quadlets, as not mapped to containers
        for network in ['macvlan1', 'macvlan2', 'macvlan3', 'bridge1', 'bridge2']:
            systemd_unit = f'vyos-{network}-network.service'
            cmdl(['systemctl', 'start', systemd_unit], sudo=True)

        n = cmd_to_json(['network', 'inspect', 'macvlan1'])
        self.assertEqual(n['driver'], 'macvlan')
        self.assertEqual(n['network_interface'], 'eth0')
        self.assertEqual(n['options']['mode'], 'bridge')
        self.assertEqual(n['subnets'][0]['subnet'], '10.0.0.0/24')
        self.assertEqual(n['subnets'][0]['gateway'], '10.0.0.1')

        n = cmd_to_json(['network', 'inspect', 'macvlan2'])
        self.assertEqual(n['driver'], 'macvlan')
        self.assertEqual(n['network_interface'], 'eth0.100')
        self.assertEqual(n['options']['mode'], 'private')
        self.assertEqual(n['subnets'][0]['subnet'], '10.0.100.0/24')
        self.assertEqual(n['subnets'][0]['gateway'], '10.0.100.5')

        n = cmd_to_json(['network', 'inspect', 'macvlan3'])
        self.assertEqual(n['driver'], 'macvlan')
        self.assertEqual(n['network_interface'], 'eth0.101')
        self.assertEqual(n['options']['mode'], 'vepa')
        self.assertEqual(n['subnets'][0]['subnet'], '2001::/64')
        self.assertEqual(n['subnets'][0]['gateway'], '2001::1')

        n = cmd_to_json(['network', 'inspect', 'bridge1'])
        self.assertEqual(n['driver'], 'bridge')
        self.assertEqual(n['network_interface'], 'pod-bridge1')
        self.assertEqual(n['subnets'][0]['subnet'], '10.0.1.0/24')
        self.assertEqual(n['subnets'][0]['gateway'], '10.0.1.1')

        n = cmd_to_json(['network', 'inspect', 'bridge2'])
        self.assertEqual(n['driver'], 'bridge')
        self.assertEqual(n['network_interface'], 'pod-bridge2')
        self.assertEqual(n['subnets'][0]['subnet'], '10.0.2.0/24')
        self.assertEqual(n['subnets'][0]['gateway'], '10.0.2.1')

        # Cleanup
        self.cli_delete(['interfaces', 'ethernet', 'eth0', 'vif'])

    def test_user_defined_mac(self):
        # Bridge Network
        self.cli_set(base_path + ['network', 'bridge1', 'prefix', '10.0.1.0/24'])
        self.cli_set(base_path + ['network', 'bridge1', 'type', 'bridge'])

        self.cli_set(base_path + ['name', "test1", 'image', busybox_image])
        self.cli_set(base_path + ['name', "test1", 'network', 'bridge1', 'address', '10.0.1.11'])
        self.cli_set(base_path + ['name', "test1", 'network', 'bridge1', 'mac', '02:00:00:00:00:01'])
        self.cli_set(base_path + ['name', "test1", 'stop-timeout', '1'])

        self.cli_set(base_path + ['name', "test2", 'image', busybox_image])
        self.cli_set(base_path + ['name', "test2", 'network', 'bridge1', 'address', '10.0.1.12'])
        self.cli_set(base_path + ['name', "test2", 'network', 'bridge1', 'mac', '02:00:00:00:00:02'])
        self.cli_set(base_path + ['name', "test2", 'stop-timeout', '1'])
        self.cli_commit()

        n = cmd_to_json(['container', 'inspect', 'test1'])
        self.assertEqual(n['NetworkSettings']['Networks']['bridge1']['MacAddress'], '02:00:00:00:00:01')
        n = cmd_to_json(['container', 'inspect', 'test2'])
        self.assertEqual(n['NetworkSettings']['Networks']['bridge1']['MacAddress'], '02:00:00:00:00:02')

    def test_long_name_host_interface_uniqueness(self):
        # T7736: the deterministic host-side veth interface name derived
        # from a container name is truncated to fit IFNAMSIZ. Two distinct
        # but similarly-prefixed long names must not truncate to the same
        # interface name - Podman would then refuse to attach the second
        # container's network, and its systemd unit would fail to start.
        net_name = 'longiftest'
        prefix = '192.0.2.0/24'
        name_1 = 'abcdefghij-1'
        name_2 = 'abcdefghij-2'

        self.cli_set(base_path + ['network', net_name, 'prefix', prefix])
        self.cli_set(base_path + ['name', name_1, 'image', busybox_image])
        self.cli_set(base_path + ['name', name_1, 'network', net_name, 'address', str(ip_interface(prefix).ip + 2)])
        self.cli_set(base_path + ['name', name_1, 'stop-timeout', '1'])
        self.cli_set(base_path + ['name', name_2, 'image', busybox_image])
        self.cli_set(base_path + ['name', name_2, 'network', net_name, 'address', str(ip_interface(prefix).ip + 3)])
        self.cli_set(base_path + ['name', name_2, 'stop-timeout', '1'])
        self.cli_commit()

        # Both containers run a "conmon" process at once, so checking by
        # process name alone can't distinguish which container it belongs
        # to - verify each container's own recorded PID is still alive
        for name in (name_1, name_2):
            self.assertTrue(self.is_running(name))

    def test_colliding_host_interface_names(self):
        # T7736: the host-side veth name is "veth-<name[:5]>-<hash[:4]>" for
        # long container names - two distinct names can still (rarely) hash
        # to the same result. These two are a confirmed real collision
        # (both produce "veth-aaaa9-4ded") - verify() must reject the
        # commit with a clear error instead of leaving it to Podman to fail
        # obscurely when the second container's network attachment clashes
        # with the first's interface name.
        net_name = 'collidetest'
        prefix = '192.0.2.0/24'
        name_1 = 'aaaa9000005'
        name_2 = 'aaaa9000336'

        self.cli_set(base_path + ['network', net_name, 'prefix', prefix])
        self.cli_set(base_path + ['name', name_1, 'image', busybox_image])
        self.cli_set(base_path + ['name', name_1, 'network', net_name, 'address', str(ip_interface(prefix).ip + 2)])
        self.cli_set(base_path + ['name', name_1, 'stop-timeout', '1'])
        self.cli_set(base_path + ['name', name_2, 'image', busybox_image])
        self.cli_set(base_path + ['name', name_2, 'network', net_name, 'address', str(ip_interface(prefix).ip + 3)])
        self.cli_set(base_path + ['name', name_2, 'stop-timeout', '1'])

        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_delete(base_path + ['name', name_2])
        self.cli_commit()

    def test_ipv4_network(self):
        prefix = '192.0.2.0/24'
        base_name = 'ipv4'
        net_name = 'NET01'

        self.cli_set(base_path + ['network', net_name, 'prefix', prefix])

        for ii in range(1, 6):
            name = f'{base_name}-{ii}'
            self.cli_set(base_path + ['name', name, 'image', busybox_image])
            self.cli_set(base_path + ['name', name, 'stop-timeout', '1'])
            self.cli_set(
                base_path
                + [
                    'name',
                    name,
                    'network',
                    net_name,
                    'address',
                    str(ip_interface(prefix).ip + ii),
                ]
            )

        # verify() - first IP address of a prefix cannot be used by a container
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        tmp = f'{base_name}-1'
        self.cli_delete(base_path + ['name', tmp])
        self.cli_commit()

        n = cmd_to_json(['network', 'inspect', net_name])
        self.assertEqual(n['subnets'][0]['subnet'], prefix)

        # skip first container, it was never created
        for ii in range(2, 6):
            name = f'{base_name}-{ii}'
            c = cmd_to_json(['container', 'inspect', name])
            self.assertEqual(
                c['NetworkSettings']['Networks'][net_name]['Gateway'],
                str(ip_interface(prefix).ip + 1),
            )
            self.assertEqual(
                c['NetworkSettings']['Networks'][net_name]['IPAddress'],
                str(ip_interface(prefix).ip + ii),
            )

    def test_ipv6_network(self):
        prefix = '2001:db8::/64'
        base_name = 'ipv6'
        net_name = 'NET02'

        self.cli_set(base_path + ['network', net_name, 'prefix', prefix])

        for ii in range(1, 6):
            name = f'{base_name}-{ii}'
            self.cli_set(base_path + ['name', name, 'image', busybox_image])
            self.cli_set(base_path + ['name', name, 'stop-timeout', '1'])
            self.cli_set(
                base_path
                + [
                    'name',
                    name,
                    'network',
                    net_name,
                    'address',
                    str(ip_interface(prefix).ip + ii),
                ]
            )

        # verify() - first IP address of a prefix cannot be used by a container
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        tmp = f'{base_name}-1'
        self.cli_delete(base_path + ['name', tmp])
        self.cli_commit()

        n = cmd_to_json(['network', 'inspect', net_name])
        self.assertEqual(n['subnets'][0]['subnet'], prefix)

        # skip first container, it was never created
        for ii in range(2, 6):
            name = f'{base_name}-{ii}'
            c = cmd_to_json(['container', 'inspect', name])
            self.assertEqual(
                c['NetworkSettings']['Networks'][net_name]['IPv6Gateway'],
                str(ip_interface(prefix).ip + 1),
            )
            self.assertEqual(
                c['NetworkSettings']['Networks'][net_name]['GlobalIPv6Address'],
                str(ip_interface(prefix).ip + ii),
            )

    def test_dual_stack_network(self):
        prefix4 = '192.0.2.0/24'
        prefix6 = '2001:db8::/64'
        base_name = 'dual-stack'
        net_name = 'net-4-6'

        self.cli_set(base_path + ['network', net_name, 'prefix', prefix4])
        self.cli_set(base_path + ['network', net_name, 'prefix', prefix6])

        for ii in range(1, 6):
            name = f'{base_name}-{ii}'
            self.cli_set(base_path + ['name', name, 'image', busybox_image])
            self.cli_set(base_path + ['name', name, 'stop-timeout', '1'])
            self.cli_set(
                base_path
                + [
                    'name',
                    name,
                    'network',
                    net_name,
                    'address',
                    str(ip_interface(prefix4).ip + ii),
                ]
            )
            self.cli_set(
                base_path
                + [
                    'name',
                    name,
                    'network',
                    net_name,
                    'address',
                    str(ip_interface(prefix6).ip + ii),
                ]
            )

        # verify() - first IP address of a prefix cannot be used by a container
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        tmp = f'{base_name}-1'
        self.cli_delete(base_path + ['name', tmp])
        self.cli_commit()

        n = cmd_to_json(['network', 'inspect', net_name])
        self.assertEqual(n['subnets'][0]['subnet'], prefix4)
        self.assertEqual(n['subnets'][1]['subnet'], prefix6)

        # skip first container, it was never created
        for ii in range(2, 6):
            name = f'{base_name}-{ii}'
            c = cmd_to_json(['container', 'inspect', name])
            self.assertEqual(
                c['NetworkSettings']['Networks'][net_name]['IPv6Gateway'],
                str(ip_interface(prefix6).ip + 1),
            )
            self.assertEqual(
                c['NetworkSettings']['Networks'][net_name]['GlobalIPv6Address'],
                str(ip_interface(prefix6).ip + ii),
            )
            self.assertEqual(
                c['NetworkSettings']['Networks'][net_name]['Gateway'],
                str(ip_interface(prefix4).ip + 1),
            )
            self.assertEqual(
                c['NetworkSettings']['Networks'][net_name]['IPAddress'],
                str(ip_interface(prefix4).ip + ii),
            )

    def test_no_name_server(self):
        prefix = '192.0.2.0/24'
        base_name = 'ipv4'
        net_name = 'NET01'

        self.cli_set(base_path + ['network', net_name, 'prefix', prefix])
        self.cli_set(base_path + ['network', net_name, 'no-name-server'])

        name = f'{base_name}-2'
        self.cli_set(base_path + ['name', name, 'image', busybox_image])
        self.cli_set(base_path + ['name', name, 'stop-timeout', '1'])
        self.cli_set(
            base_path
            + [
                'name',
                name,
                'network',
                net_name,
                'address',
                str(ip_interface(prefix).ip + 2),
            ]
        )
        self.cli_commit()

        n = cmd_to_json(['network', 'inspect', net_name])
        self.assertEqual(n['dns_enabled'], False)

    def test_network_mtu(self):
        prefix = '10.250.191.0/24'
        base_name = 'ipv4'
        net_name = 'NET01'

        self.cli_set(base_path + ['network', net_name, 'prefix', prefix])
        self.cli_set(base_path + ['network', net_name, 'mtu', '1280'])

        name = f'{base_name}-2'
        self.cli_set(base_path + ['name', name, 'image', busybox_image])
        self.cli_set(base_path + ['name', name, 'capability', 'net-raw'])
        self.cli_set(base_path + ['name', name, 'stop-timeout', '1'])
        self.cli_set(
            base_path
            + [
                'name',
                name,
                'network',
                net_name,
                'address',
                str(ip_interface(prefix).ip + 2),
            ]
        )
        self.cli_commit()

        n = cmd_to_json(['network', 'inspect', net_name])
        self.assertEqual(n['options']['mtu'], '1280')
        cmdl(['podman', 'exec', name, 'ping', '-c', '1', '-W', '2',
              str(ip_interface(prefix).ip + 1)], sudo=True)

        for mtu, explicit_type in [('1400', True), ('1280', False)]:
            type_path = base_path + ['network', net_name, 'type']
            if explicit_type:
                self.cli_set(type_path + ['bridge'])
            else:
                self.cli_delete(type_path)
            self.cli_set(base_path + ['network', net_name, 'mtu', mtu])
            self.cli_commit()
            self.assertTrue(self.is_running(name))
            network = cmd_to_json(['network', 'inspect', net_name])
            self.assertEqual(network['options']['mtu'], mtu)
            pid = str(cmd_to_json(['inspect', name])['State']['Pid'])
            links = json.loads(cmdl(['nsenter', '-t', pid, '-n',
                                    'ip', '-j', 'link', 'show', 'dev', 'eth0'], sudo=True))
            self.assertEqual(links[0]['mtu'], int(mtu))
            cmdl(['podman', 'exec', name, 'ping', '-c', '1', '-W', '2',
                  str(ip_interface(prefix).ip + 1)], sudo=True)

    def test_uid_gid(self):
        cont_name = 'uid-test'
        gid = '100'
        uid = '1001'

        self.cli_set(base_path + ['name', cont_name, 'allow-host-networks'])
        self.cli_set(base_path + ['name', cont_name, 'image', busybox_image])
        self.cli_set(base_path + ['name', cont_name, 'gid', gid])
        self.cli_set(base_path + ['name', cont_name, 'stop-timeout', '1'])

        # verify() - GID can only be set if UID is set
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(base_path + ['name', cont_name, 'uid', uid])

        self.cli_commit()

        # verify
        tmp = cmdl(['podman', 'exec', '-it', cont_name, 'id', '-u'], sudo=True)
        self.assertEqual(tmp, uid)
        tmp = cmdl(['podman', 'exec', '-it', cont_name, 'id', '-g'], sudo=True)
        self.assertEqual(tmp, gid)

    def test_tmpfs_chown(self):
        cont_name = 'tmpfs-test'
        uid = '1001'
        gid = '100'
        # /home exists in the busybox image and is not owned by the container
        # user: without chown the tmpfs mounted over it is not writable
        destination = '/home'

        self.cli_set(base_path + ['name', cont_name, 'allow-host-networks'])
        self.cli_set(base_path + ['name', cont_name, 'image', busybox_image])
        self.cli_set(base_path + ['name', cont_name, 'uid', uid])
        self.cli_set(base_path + ['name', cont_name, 'gid', gid])
        self.cli_set(base_path + ['name', cont_name, 'stop-timeout', '1'])
        self.cli_set(base_path + ['name', cont_name, 'tmpfs', 'home', 'destination', destination])
        self.cli_set(base_path + ['name', cont_name, 'tmpfs', 'home', 'size', '1'])
        self.cli_set(base_path + ['name', cont_name, 'tmpfs', 'home', 'chown'])
        self.cli_commit()

        self.assertTrue(self.is_running(cont_name))

        # verify
        tmp = cmdl(['podman', 'exec', '-it', cont_name, 'stat', '-c', '%u:%g', destination], sudo=True)
        self.assertEqual(tmp, f'{uid}:{gid}')
        cmdl(['podman', 'exec', '-it', cont_name, 'touch', f'{destination}/test'], sudo=True)

    def test_api_socket(self):
        base_name = 'api-test'
        container_list = range(1, 5)

        for ii in container_list:
            name = f'{base_name}-{ii}'
            self.cli_set(base_path + ['name', name, 'image', busybox_image])
            self.cli_set(base_path + ['name', name, 'allow-host-networks'])
            self.cli_set(base_path + ['name', name, 'stop-timeout', '1'])

        self.cli_commit()

        # Query API about running containers
        tmp = cmdl(
            ['curl', '--unix-socket', '/run/podman/podman.sock', '-H',
             'content-type: application/json', '-sf',
             'http://localhost/containers/json'],
            sudo=True,
        )
        tmp = json.loads(tmp)

        # We expect the same amount of containers from the API that we started above
        self.assertEqual(len(container_list), len(tmp))

    def test_network_vrf(self):
        cont_name = 'vrf-test50'
        net_name = 'vrf-test50'
        vrf_name = 'red-15'

        # create temporary VRF for testing
        self.cli_set(['vrf', 'name', vrf_name, 'table', '100'])

        self.cli_set(base_path + ['name', cont_name, 'image', busybox_image])
        self.cli_set(base_path + ['name', cont_name, 'network', net_name])
        self.cli_set(base_path + ['name', cont_name, 'stop-timeout', '1'])
        self.cli_set(base_path + ['network', net_name, 'prefix', '192.168.0.0/24'])
        self.cli_set(base_path + ['network', net_name, 'vrf', vrf_name])

        self.cli_commit()

        tmp = get_interface_vrf(f'pod-{net_name}')
        self.assertEqual(tmp, vrf_name)

        # Restart container and validate VRF assignment
        self.op_mode(['restart', 'container', cont_name])
        tmp = get_interface_vrf(f'pod-{net_name}')
        self.assertEqual(tmp, vrf_name)

        self.cli_delete(['vrf', 'name', vrf_name])

    def test_storage_mount_program(self):
        cont_name = 'storage-test'
        graphroot = directories['podman_storage']

        self.cli_set(base_path + ['name', cont_name, 'image', busybox_image])
        self.cli_set(base_path + ['name', cont_name, 'allow-host-networks'])
        self.cli_set(base_path + ['name', cont_name, 'stop-timeout', '1'])
        self.cli_commit()

        self.assertTrue(self.is_running(cont_name))

        config = read_file(config_storage)
        self.assertIn(f'graphroot = "{graphroot}"', config)

        # fuse-overlayfs is only required when the graphroot sits on overlayfs
        # (live boot), the kernel overlay driver is used everywhere else
        fstype = cmdl(['findmnt', '--noheadings', '--output', 'FSTYPE',
                       '--target', graphroot], sudo=True)
        if fstype == 'overlay':
            self.assertIn(f'mount_program = "{podman_mount_program}"', config)
            return

        self.assertNotIn('mount_program', config)

        # Storage once used with a mount program keeps using fuse-overlayfs
        # until it is reset, see T9456
        flag = read_file(os.path.join(graphroot, 'overlay', '.has-mount-program'),
                         defaultonfailure='', sudo=True)
        if flag.strip() != 'true':
            helper = os.path.basename(podman_mount_program)
            self.assertIsNone(process_named_running(helper))

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
