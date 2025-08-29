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
import re
import unittest

from json import loads

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.kea import kea_add_lease
from vyos.kea import kea_delete_lease
from vyos.utils.process import cmd
from vyos.utils.process import process_named_running
from vyos.utils.file import read_file
from vyos.template import inc_ip
from vyos.template import dec_ip

PROCESS_NAME = 'kea-dhcp4'
D2_PROCESS_NAME = 'kea-dhcp-ddns'
CTRL_PROCESS_NAME = 'kea-ctrl-agent'
KEA4_CONF = '/run/kea/kea-dhcp4.conf'
KEA4_D2_CONF = '/run/kea/kea-dhcp-ddns.conf'
KEA4_CTRL = '/run/kea/dhcp4-ctrl-socket'
HOSTSD_CLIENT = '/usr/bin/vyos-hostsd-client'
base_path = ['service', 'dhcp-server']
interface = 'dum8765'
subnet = '192.0.2.0/25'
router = inc_ip(subnet, 1)
dns_1 = inc_ip(subnet, 2)
dns_2 = inc_ip(subnet, 3)
domain_name = 'vyos.net'


class TestServiceDHCPServer(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestServiceDHCPServer, cls).setUpClass()
        # Clear out current configuration to allow running this test on a live system
        cls.cli_delete(cls, base_path)

        cidr_mask = subnet.split('/')[-1]
        cls.cli_set(
            cls, ['interfaces', 'dummy', interface, 'address', f'{router}/{cidr_mask}']
        )

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, ['interfaces', 'dummy', interface])
        super(TestServiceDHCPServer, cls).tearDownClass()

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

    def walk_path(self, obj, path):
        current = obj

        for i, key in enumerate(path):
            if isinstance(key, str):
                self.assertTrue(isinstance(current, dict), msg=f'Failed path: {path}')
                self.assertTrue(key in current, msg=f'Failed path: {path}')
            elif isinstance(key, int):
                self.assertTrue(isinstance(current, list), msg=f'Failed path: {path}')
                self.assertTrue(0 <= key < len(current), msg=f'Failed path: {path}')
            else:
                assert False, 'Invalid type'

            current = current[key]

        return current

    def verify_config_object(self, obj, path, value):
        base_obj = self.walk_path(obj, path)
        self.assertTrue(isinstance(base_obj, list))
        self.assertTrue(any(True for v in base_obj if v == value))

    def verify_config_value(self, obj, path, key, value):
        base_obj = self.walk_path(obj, path)
        if isinstance(base_obj, list):
            self.assertTrue(any(True for v in base_obj if key in v and v[key] == value))
        elif isinstance(base_obj, dict):
            self.assertTrue(key in base_obj)
            self.assertEqual(base_obj[key], value)

    def verify_service_running(self):
        try:
            tmp = cmd('grep -i kea /var/log/messages | tail -n 100')
        except OSError:
            tmp = "No relevant log entries"
        self.assertTrue(process_named_running(PROCESS_NAME), msg=f'Service not running, log: {tmp}')

    def test_dhcp_single_pool_range(self):
        shared_net_name = 'SMOKE-1'

        range_0_start = inc_ip(subnet, 10)
        range_0_stop = inc_ip(subnet, 20)
        range_1_start = inc_ip(subnet, 40)
        range_1_stop = inc_ip(subnet, 50)

        self.cli_set(base_path + ['listen-interface', interface])

        self.cli_set(base_path + ['shared-network-name', shared_net_name, 'ping-check'])

        pool = base_path + ['shared-network-name', shared_net_name, 'subnet', subnet]
        self.cli_set(pool + ['subnet-id', '1'])
        self.cli_set(pool + ['ignore-client-id'])
        self.cli_set(pool + ['ping-check'])
        # we use the first subnet IP address as default gateway
        self.cli_set(pool + ['option', 'default-router', router])
        self.cli_set(pool + ['option', 'name-server', dns_1])
        self.cli_set(pool + ['option', 'name-server', dns_2])
        self.cli_set(pool + ['option', 'domain-name', domain_name])

        # check validate() - No DHCP address range or active static-mapping set
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(pool + ['range', '0', 'start', range_0_start])
        self.cli_set(pool + ['range', '0', 'stop', range_0_stop])
        self.cli_set(pool + ['range', '1', 'start', range_1_start])
        self.cli_set(pool + ['range', '1', 'stop', range_1_stop])

        # commit changes
        self.cli_commit()

        config = read_file(KEA4_CONF)
        obj = loads(config)

        self.verify_config_value(
            obj, ['Dhcp4', 'interfaces-config'], 'interfaces', [interface]
        )
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks'], 'name', shared_net_name
        )
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'subnet', subnet
        )
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'id', 1
        )
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'match-client-id', False
        )
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'valid-lifetime', 86400
        )
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'max-valid-lifetime', 86400
        )

        # Verify ping-check
        self.verify_config_value(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'user-context'],
            'enable-ping-check',
            True
        )

        self.verify_config_value(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'user-context'],
            'enable-ping-check',
            True
        )

        # Verify options
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'domain-name', 'data': domain_name},
        )
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'domain-name-servers', 'data': f'{dns_1}, {dns_2}'},
        )
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'routers', 'data': router},
        )

        # Verify pools
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'pools'],
            {'pool': f'{range_0_start} - {range_0_stop}'},
        )
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'pools'],
            {'pool': f'{range_1_start} - {range_1_stop}'},
        )

        # Check for running process
        self.verify_service_running()

    def test_dhcp_single_pool_options(self):
        shared_net_name = 'SMOKE-0815'

        range_0_start = inc_ip(subnet, 10)
        range_0_stop = inc_ip(subnet, 20)
        smtp_server = '1.2.3.4'
        time_server = '4.3.2.1'
        tftp_server = 'tftp.vyos.io'
        search_domains = ['foo.vyos.net', 'bar.vyos.net']
        bootfile_name = 'vyos'
        bootfile_server = '192.0.2.1'
        wpad = 'http://wpad.vyos.io/foo/bar'
        server_identifier = bootfile_server
        ipv6_only_preferred = '300'
        capwap_access_controller = '192.168.2.125'

        pool = base_path + ['shared-network-name', shared_net_name, 'subnet', subnet]
        self.cli_set(pool + ['subnet-id', '1'])
        # we use the first subnet IP address as default gateway
        self.cli_set(pool + ['option', 'default-router', router])
        self.cli_set(pool + ['option', 'name-server', dns_1])
        self.cli_set(pool + ['option', 'name-server', dns_2])
        self.cli_set(pool + ['option', 'domain-name', domain_name])
        self.cli_set(pool + ['option', 'ip-forwarding'])
        self.cli_set(pool + ['option', 'smtp-server', smtp_server])
        self.cli_set(pool + ['option', 'pop-server', smtp_server])
        self.cli_set(pool + ['option', 'time-server', time_server])
        self.cli_set(pool + ['option', 'tftp-server-name', tftp_server])
        for search in search_domains:
            self.cli_set(pool + ['option', 'domain-search', search])
        self.cli_set(pool + ['option', 'bootfile-name', bootfile_name])
        self.cli_set(pool + ['option', 'bootfile-server', bootfile_server])
        self.cli_set(pool + ['option', 'wpad-url', wpad])
        self.cli_set(pool + ['option', 'server-identifier', server_identifier])
        self.cli_set(
            pool + ['option', 'capwap-controller', capwap_access_controller]
        )

        static_route = '10.0.0.0/24'
        static_route_nexthop = '192.0.2.1'

        self.cli_set(
            pool + ['option', 'static-route', static_route, 'next-hop', static_route_nexthop]
        )
        self.cli_set(pool + ['option', 'ipv6-only-preferred', ipv6_only_preferred])
        self.cli_set(pool + ['option', 'time-zone', 'Europe/London'])

        self.cli_set(pool + ['range', '0', 'start', range_0_start])
        self.cli_set(pool + ['range', '0', 'stop', range_0_stop])

        # commit changes
        self.cli_commit()

        config = read_file(KEA4_CONF)
        obj = loads(config)

        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks'], 'name', shared_net_name
        )
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'subnet', subnet
        )
        self.verify_config_value(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4'],
            'boot-file-name',
            bootfile_name,
        )
        self.verify_config_value(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4'],
            'next-server',
            bootfile_server,
        )
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'valid-lifetime', 86400
        )
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'max-valid-lifetime', 86400
        )

        # Verify options
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'domain-name', 'data': domain_name},
        )
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'domain-name-servers', 'data': f'{dns_1}, {dns_2}'},
        )
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'domain-search', 'data': ', '.join(search_domains)},
        )
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'pop-server', 'data': smtp_server},
        )
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'smtp-server', 'data': smtp_server},
        )
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'time-servers', 'data': time_server},
        )
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'routers', 'data': router},
        )
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'dhcp-server-identifier', 'data': server_identifier},
        )
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'capwap-ac-v4', 'data': capwap_access_controller},
        )
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'tftp-server-name', 'data': tftp_server},
        )
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'wpad-url', 'data': wpad},
        )
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {
                'name': 'classless-static-route',
                'data': f'{static_route} - {static_route_nexthop}, 0.0.0.0/0 - {router}',
            },
        )
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'v6-only-preferred', 'data': ipv6_only_preferred},
        )
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'ip-forwarding', 'data': 'true'},
        )

        # Time zone
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'pcode', 'data': 'GMT0BST,M3.5.0/1,M10.5.0'},
        )
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'tcode', 'data': 'Europe/London'},
        )

        # Verify pools
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'pools'],
            {'pool': f'{range_0_start} - {range_0_stop}'},
        )

        # Check for running process
        self.verify_service_running()

    def test_dhcp_single_pool_options_scoped(self):
        shared_net_name = 'SMOKE-2'

        range_0_start = inc_ip(subnet, 10)
        range_0_stop = inc_ip(subnet, 20)

        range_router = inc_ip(subnet, 5)
        range_dns_1 = inc_ip(subnet, 6)
        range_dns_2 = inc_ip(subnet, 7)

        shared_network = base_path + ['shared-network-name', shared_net_name]
        pool = shared_network + ['subnet', subnet]

        self.cli_set(pool + ['subnet-id', '1'])

        # we use the first subnet IP address as default gateway
        self.cli_set(shared_network + ['option', 'default-router', router])
        self.cli_set(shared_network + ['option', 'name-server', dns_1])
        self.cli_set(shared_network + ['option', 'name-server', dns_2])
        self.cli_set(shared_network + ['option', 'domain-name', domain_name])

        self.cli_set(pool + ['range', '0', 'start', range_0_start])
        self.cli_set(pool + ['range', '0', 'stop', range_0_stop])
        self.cli_set(pool + ['range', '0', 'option', 'default-router', range_router])
        self.cli_set(pool + ['range', '0', 'option', 'name-server', range_dns_1])
        self.cli_set(pool + ['range', '0', 'option', 'name-server', range_dns_2])

        # commit changes
        self.cli_commit()

        config = read_file(KEA4_CONF)
        obj = loads(config)

        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks'], 'name', shared_net_name
        )
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'subnet', subnet
        )
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'valid-lifetime', 86400
        )
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'max-valid-lifetime', 86400
        )

        # Verify shared-network options
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'option-data'],
            {'name': 'domain-name', 'data': domain_name},
        )
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'option-data'],
            {'name': 'domain-name-servers', 'data': f'{dns_1}, {dns_2}'},
        )
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'option-data'],
            {'name': 'routers', 'data': router},
        )

        # Verify range options
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'pools', 0, 'option-data'],
            {'name': 'domain-name-servers', 'data': f'{range_dns_1}, {range_dns_2}'},
        )
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'pools', 0, 'option-data'],
            {'name': 'routers', 'data': range_router},
        )

        # Verify pool
        self.verify_config_value(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'pools'],
            'pool',
            f'{range_0_start} - {range_0_stop}',
        )

        # Check for running process
        self.verify_service_running()

    def test_dhcp_single_pool_static_mapping(self):
        shared_net_name = 'SMOKE-2'
        domain_name = 'private'

        pool = base_path + ['shared-network-name', shared_net_name, 'subnet', subnet]
        self.cli_set(pool + ['subnet-id', '1'])
        # we use the first subnet IP address as default gateway
        self.cli_set(pool + ['option', 'default-router', router])
        self.cli_set(pool + ['option', 'name-server', dns_1])
        self.cli_set(pool + ['option', 'name-server', dns_2])
        self.cli_set(pool + ['option', 'domain-name', domain_name])

        # check validate() - No DHCP address range or active static-mapping set
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        client_base = 10
        for client in ['client1', 'client2', 'client3']:
            mac = '00:50:00:00:00:{}'.format(client_base)
            self.cli_set(pool + ['static-mapping', client, 'mac', mac])
            self.cli_set(
                pool
                + ['static-mapping', client, 'ip-address', inc_ip(subnet, client_base)]
            )
            client_base += 1

        # cannot have both mac-address and duid set
        with self.assertRaises(ConfigSessionError):
            self.cli_set(
                pool
                + [
                    'static-mapping',
                    'client1',
                    'duid',
                    '00:01:00:01:12:34:56:78:aa:bb:cc:dd:ee:11',
                ]
            )
            self.cli_commit()
        self.cli_delete(pool + ['static-mapping', 'client1', 'duid'])

        # cannot have mappings with duplicate IP addresses
        self.cli_set(pool + ['static-mapping', 'dupe1', 'mac', '00:50:00:00:fe:ff'])
        self.cli_set(
            pool + ['static-mapping', 'dupe1', 'ip-address', inc_ip(subnet, 10)]
        )
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        # Should allow disabled duplicate
        self.cli_set(pool + ['static-mapping', 'dupe1', 'disable'])
        self.cli_commit()
        self.cli_delete(pool + ['static-mapping', 'dupe1'])

        # cannot have mappings with duplicate MAC addresses
        self.cli_set(pool + ['static-mapping', 'dupe2', 'mac', '00:50:00:00:00:10'])
        self.cli_set(
            pool + ['static-mapping', 'dupe2', 'ip-address', inc_ip(subnet, 120)]
        )
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(pool + ['static-mapping', 'dupe2'])

        # cannot have mappings with duplicate MAC addresses
        self.cli_set(
            pool
            + [
                'static-mapping',
                'dupe3',
                'duid',
                '00:01:02:03:04:05:06:07:aa:aa:aa:aa:aa:01',
            ]
        )
        self.cli_set(
            pool + ['static-mapping', 'dupe3', 'ip-address', inc_ip(subnet, 121)]
        )
        self.cli_set(
            pool
            + [
                'static-mapping',
                'dupe4',
                'duid',
                '00:01:02:03:04:05:06:07:aa:aa:aa:aa:aa:01',
            ]
        )
        self.cli_set(
            pool + ['static-mapping', 'dupe4', 'ip-address', inc_ip(subnet, 121)]
        )
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(pool + ['static-mapping', 'dupe3'])
        self.cli_delete(pool + ['static-mapping', 'dupe4'])

        # commit changes
        self.cli_commit()

        config = read_file(KEA4_CONF)
        obj = loads(config)

        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks'], 'name', shared_net_name
        )
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'subnet', subnet
        )
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'id', 1
        )
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'valid-lifetime', 86400
        )
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'max-valid-lifetime', 86400
        )

        # Verify options
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'domain-name', 'data': domain_name},
        )
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'domain-name-servers', 'data': f'{dns_1}, {dns_2}'},
        )
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'routers', 'data': router},
        )

        client_base = 10
        for client in ['client1', 'client2', 'client3']:
            mac = '00:50:00:00:00:{}'.format(client_base)
            ip = inc_ip(subnet, client_base)

            self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'reservations'],
                {'hostname': client, 'hw-address': mac, 'ip-address': ip},
            )

            client_base += 1

        # Check for running process
        self.verify_service_running()

    def test_dhcp_multiple_pools(self):
        lease_time = '14400'

        for network in ['0', '1', '2', '3']:
            shared_net_name = f'VyOS-SMOKETEST-{network}'
            subnet = f'192.0.{network}.0/24'
            router = inc_ip(subnet, 1)
            dns_1 = inc_ip(subnet, 2)

            range_0_start = inc_ip(subnet, 10)
            range_0_stop = inc_ip(subnet, 20)
            range_1_start = inc_ip(subnet, 30)
            range_1_stop = inc_ip(subnet, 40)

            pool = base_path + [
                'shared-network-name',
                shared_net_name,
                'subnet',
                subnet,
            ]
            self.cli_set(pool + ['subnet-id', str(int(network) + 1)])
            # we use the first subnet IP address as default gateway
            self.cli_set(pool + ['option', 'default-router', router])
            self.cli_set(pool + ['option', 'name-server', dns_1])
            self.cli_set(pool + ['option', 'domain-name', domain_name])
            self.cli_set(pool + ['lease', lease_time])

            self.cli_set(pool + ['range', '0', 'start', range_0_start])
            self.cli_set(pool + ['range', '0', 'stop', range_0_stop])
            self.cli_set(pool + ['range', '1', 'start', range_1_start])
            self.cli_set(pool + ['range', '1', 'stop', range_1_stop])

            client_base = 60
            for client in ['client1', 'client2', 'client3', 'client4']:
                mac = '02:50:00:00:00:{}'.format(client_base)
                self.cli_set(pool + ['static-mapping', client, 'mac', mac])
                self.cli_set(
                    pool
                    + [
                        'static-mapping',
                        client,
                        'ip-address',
                        inc_ip(subnet, client_base),
                    ]
                )
                client_base += 1

        # commit changes
        self.cli_commit()

        config = read_file(KEA4_CONF)
        obj = loads(config)

        for network in ['0', '1', '2', '3']:
            shared_net_name = f'VyOS-SMOKETEST-{network}'
            subnet = f'192.0.{network}.0/24'
            router = inc_ip(subnet, 1)
            dns_1 = inc_ip(subnet, 2)

            range_0_start = inc_ip(subnet, 10)
            range_0_stop = inc_ip(subnet, 20)
            range_1_start = inc_ip(subnet, 30)
            range_1_stop = inc_ip(subnet, 40)

            self.verify_config_value(
                obj, ['Dhcp4', 'shared-networks'], 'name', shared_net_name
            )
            self.verify_config_value(
                obj,
                ['Dhcp4', 'shared-networks', int(network), 'subnet4'],
                'subnet',
                subnet,
            )
            self.verify_config_value(
                obj,
                ['Dhcp4', 'shared-networks', int(network), 'subnet4'],
                'id',
                int(network) + 1,
            )
            self.verify_config_value(
                obj,
                ['Dhcp4', 'shared-networks', int(network), 'subnet4'],
                'valid-lifetime',
                int(lease_time),
            )
            self.verify_config_value(
                obj,
                ['Dhcp4', 'shared-networks', int(network), 'subnet4'],
                'max-valid-lifetime',
                int(lease_time),
            )

            self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', int(network), 'subnet4', 0, 'option-data'],
                {'name': 'domain-name', 'data': domain_name},
            )
            self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', int(network), 'subnet4', 0, 'option-data'],
                {'name': 'domain-name-servers', 'data': dns_1},
            )
            self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', int(network), 'subnet4', 0, 'option-data'],
                {'name': 'routers', 'data': router},
            )

            self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', int(network), 'subnet4', 0, 'pools'],
                {'pool': f'{range_0_start} - {range_0_stop}'},
            )
            self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', int(network), 'subnet4', 0, 'pools'],
                {'pool': f'{range_1_start} - {range_1_stop}'},
            )

            client_base = 60
            for client in ['client1', 'client2', 'client3', 'client4']:
                mac = '02:50:00:00:00:{}'.format(client_base)
                ip = inc_ip(subnet, client_base)

                self.verify_config_object(
                    obj,
                    [
                        'Dhcp4',
                        'shared-networks',
                        int(network),
                        'subnet4',
                        0,
                        'reservations',
                    ],
                    {'hostname': client, 'hw-address': mac, 'ip-address': ip},
                )

                client_base += 1

        # Check for running process
        self.verify_service_running()

    def test_dhcp_exclude_not_in_range(self):
        # T3180: verify else path when slicing DHCP ranges and exclude address
        # is not part of the DHCP range
        range_0_start = inc_ip(subnet, 10)
        range_0_stop = inc_ip(subnet, 20)

        pool = base_path + ['shared-network-name', 'EXCLUDE-TEST', 'subnet', subnet]
        self.cli_set(pool + ['subnet-id', '1'])
        self.cli_set(pool + ['option', 'default-router', router])
        self.cli_set(pool + ['exclude', router])
        self.cli_set(pool + ['range', '0', 'option', 'default-router', router])
        self.cli_set(pool + ['range', '0', 'start', range_0_start])
        self.cli_set(pool + ['range', '0', 'stop', range_0_stop])

        # commit changes
        self.cli_commit()

        config = read_file(KEA4_CONF)
        obj = loads(config)

        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks'], 'name', 'EXCLUDE-TEST'
        )
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'subnet', subnet
        )

        pool_obj = {
            'pool': f'{range_0_start} - {range_0_stop}',
            'option-data': [{'name': 'routers', 'data': router}],
        }

        # Verify options
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'routers', 'data': router},
        )

        # Verify pools
        self.verify_config_object(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'pools'], pool_obj
        )

        # Check for running process
        self.verify_service_running()

    def test_dhcp_exclude_in_range(self):
        # T3180: verify else path when slicing DHCP ranges and exclude address
        # is not part of the DHCP range
        range_0_start = inc_ip(subnet, 10)
        range_0_stop = inc_ip(subnet, 100)

        # the DHCP exclude addresse is blanked out of the range which is done
        # by slicing one range into two ranges
        exclude_addr = inc_ip(range_0_start, 20)
        range_0_stop_excl = dec_ip(exclude_addr, 1)
        range_0_start_excl = inc_ip(exclude_addr, 1)

        pool = base_path + ['shared-network-name', 'EXCLUDE-TEST-2', 'subnet', subnet]
        self.cli_set(pool + ['subnet-id', '1'])
        self.cli_set(pool + ['option', 'default-router', router])
        self.cli_set(pool + ['exclude', exclude_addr])
        self.cli_set(pool + ['range', '0', 'option', 'default-router', router])
        self.cli_set(pool + ['range', '0', 'start', range_0_start])
        self.cli_set(pool + ['range', '0', 'stop', range_0_stop])

        # commit changes
        self.cli_commit()

        config = read_file(KEA4_CONF)
        obj = loads(config)

        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks'], 'name', 'EXCLUDE-TEST-2'
        )
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'subnet', subnet
        )

        pool_obj = {
            'pool': f'{range_0_start} - {range_0_stop_excl}',
            'option-data': [{'name': 'routers', 'data': router}],
        }

        pool_exclude_obj = {
            'pool': f'{range_0_start_excl} - {range_0_stop}',
            'option-data': [{'name': 'routers', 'data': router}],
        }

        # Verify options
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'routers', 'data': router},
        )

        self.verify_config_object(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'pools'], pool_obj
        )

        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'pools'],
            pool_exclude_obj,
        )

        # Check for running process
        self.verify_service_running()

    def test_dhcp_relay_server(self):
        # Listen on specific address and return DHCP leases from a non
        # directly connected pool
        self.cli_set(base_path + ['listen-address', router])

        relay_subnet = '10.0.0.0/16'
        relay_router = inc_ip(relay_subnet, 1)

        range_0_start = '10.0.1.0'
        range_0_stop = '10.0.250.255'

        pool = base_path + ['shared-network-name', 'RELAY', 'subnet', relay_subnet]
        self.cli_set(pool + ['subnet-id', '1'])
        self.cli_set(pool + ['option', 'default-router', relay_router])
        self.cli_set(pool + ['range', '0', 'start', range_0_start])
        self.cli_set(pool + ['range', '0', 'stop', range_0_stop])

        # commit changes
        self.cli_commit()

        config = read_file(KEA4_CONF)
        obj = loads(config)

        self.verify_config_value(
            obj, ['Dhcp4', 'interfaces-config'], 'interfaces', [f'{interface}/{router}']
        )
        self.verify_config_value(obj, ['Dhcp4', 'shared-networks'], 'name', 'RELAY')
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'subnet', relay_subnet
        )

        # Verify options
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'routers', 'data': relay_router},
        )

        # Verify pools
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'pools'],
            {'pool': f'{range_0_start} - {range_0_stop}'},
        )

        # Check for running process
        self.verify_service_running()

    def test_dhcp_high_availability(self):
        shared_net_name = 'FAILOVER'
        failover_name = 'VyOS-Failover'

        range_0_start = inc_ip(subnet, 10)
        range_0_stop = inc_ip(subnet, 20)

        pool = base_path + ['shared-network-name', shared_net_name, 'subnet', subnet]
        self.cli_set(pool + ['subnet-id', '1'])
        # we use the first subnet IP address as default gateway
        self.cli_set(pool + ['option', 'default-router', router])

        # check validate() - No DHCP address range or active static-mapping set
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(pool + ['range', '0', 'start', range_0_start])
        self.cli_set(pool + ['range', '0', 'stop', range_0_stop])

        # failover
        failover_local = router
        failover_remote = inc_ip(router, 1)

        self.cli_set(
            base_path + ['high-availability', 'source-address', failover_local]
        )
        self.cli_set(base_path + ['high-availability', 'name', failover_name])
        self.cli_set(base_path + ['high-availability', 'remote', failover_remote])
        self.cli_set(base_path + ['high-availability', 'status', 'primary'])
        ## No mode defined -> its active-active mode by default

        # commit changes
        self.cli_commit()

        config = read_file(KEA4_CONF)
        obj = loads(config)

        # Verify failover
        self.verify_config_value(
            obj, ['Dhcp4', 'control-socket'], 'socket-name', KEA4_CTRL
        )

        self.verify_config_object(
            obj,
            [
                'Dhcp4',
                'hooks-libraries',
                0,
                'parameters',
                'high-availability',
                0,
                'peers',
            ],
            {
                'name': os.uname()[1],
                'url': f'http://{failover_local}:647/',
                'role': 'primary',
                'auto-failover': True,
            },
        )

        self.verify_config_object(
            obj,
            [
                'Dhcp4',
                'hooks-libraries',
                0,
                'parameters',
                'high-availability',
                0,
                'peers',
            ],
            {
                'name': failover_name,
                'url': f'http://{failover_remote}:647/',
                'role': 'secondary',
                'auto-failover': True,
            },
        )

        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks'], 'name', shared_net_name
        )
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'subnet', subnet
        )

        # Verify options
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'routers', 'data': router},
        )

        # Verify pools
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'pools'],
            {'pool': f'{range_0_start} - {range_0_stop}'},
        )

        # Check for running process
        self.verify_service_running()

    def test_dhcp_high_availability_standby(self):
        shared_net_name = 'FAILOVER'
        failover_name = 'VyOS-Failover'

        range_0_start = inc_ip(subnet, 10)
        range_0_stop = inc_ip(subnet, 20)

        pool = base_path + ['shared-network-name', shared_net_name, 'subnet', subnet]
        self.cli_set(pool + ['subnet-id', '1'])
        # we use the first subnet IP address as default gateway
        self.cli_set(pool + ['option', 'default-router', router])
        self.cli_set(pool + ['range', '0', 'start', range_0_start])
        self.cli_set(pool + ['range', '0', 'stop', range_0_stop])

        # failover
        failover_local = router
        failover_remote = inc_ip(router, 1)

        self.cli_set(
            base_path + ['high-availability', 'source-address', failover_local]
        )
        self.cli_set(base_path + ['high-availability', 'name', failover_name])
        self.cli_set(base_path + ['high-availability', 'remote', failover_remote])
        self.cli_set(base_path + ['high-availability', 'status', 'secondary'])
        self.cli_set(base_path + ['high-availability', 'mode', 'active-passive'])

        # commit changes
        self.cli_commit()

        config = read_file(KEA4_CONF)
        obj = loads(config)

        # Verify failover
        self.verify_config_value(
            obj, ['Dhcp4', 'control-socket'], 'socket-name', KEA4_CTRL
        )

        self.verify_config_object(
            obj,
            [
                'Dhcp4',
                'hooks-libraries',
                0,
                'parameters',
                'high-availability',
                0,
                'peers',
            ],
            {
                'name': os.uname()[1],
                'url': f'http://{failover_local}:647/',
                'role': 'standby',
                'auto-failover': True,
            },
        )

        self.verify_config_object(
            obj,
            [
                'Dhcp4',
                'hooks-libraries',
                0,
                'parameters',
                'high-availability',
                0,
                'peers',
            ],
            {
                'name': failover_name,
                'url': f'http://{failover_remote}:647/',
                'role': 'primary',
                'auto-failover': True,
            },
        )

        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks'], 'name', shared_net_name
        )
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'subnet', subnet
        )

        # Verify options
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'routers', 'data': router},
        )

        # Verify pools
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'pools'],
            {'pool': f'{range_0_start} - {range_0_stop}'},
        )

        # Check for running process
        self.verify_service_running()

    def test_dhcp_dynamic_dns_update(self):
        shared_net_name = 'SMOKE-1DDNS'

        range_0_start = inc_ip(subnet, 10)
        range_0_stop  = inc_ip(subnet, 20)

        self.cli_set(base_path + ['listen-interface', interface])

        ddns = base_path + ['dynamic-dns-update']

        self.cli_set(ddns + ['send-updates', 'enable'])
        self.cli_set(ddns + ['conflict-resolution', 'enable'])
        self.cli_set(ddns + ['override-no-update', 'enable'])
        self.cli_set(ddns + ['override-client-update', 'enable'])
        self.cli_set(ddns + ['replace-client-name', 'always'])
        self.cli_set(ddns + ['update-on-renew', 'enable'])

        self.cli_set(ddns + ['tsig-key', 'domain-lan-updates', 'algorithm', 'sha256'])
        self.cli_set(ddns + ['tsig-key', 'domain-lan-updates', 'secret', 'SXQncyBXZWRuZXNkYXkgbWFoIGR1ZGVzIQ=='])
        self.cli_set(ddns + ['tsig-key', 'reverse-0-168-192', 'algorithm', 'sha256'])
        self.cli_set(ddns + ['tsig-key', 'reverse-0-168-192', 'secret', 'VGhhbmsgR29kIGl0J3MgRnJpZGF5IQ=='])
        self.cli_set(ddns + ['forward-domain', 'domain.lan', 'dns-server', '1', 'address', '192.168.0.1'])
        self.cli_set(ddns + ['forward-domain', 'domain.lan', 'dns-server', '2', 'address', '100.100.0.1'])
        self.cli_set(ddns + ['forward-domain', 'domain.lan', 'key-name', 'domain-lan-updates'])
        self.cli_set(ddns + ['reverse-domain', '0.168.192.in-addr.arpa', 'dns-server', '1', 'address', '192.168.0.1'])
        self.cli_set(ddns + ['reverse-domain', '0.168.192.in-addr.arpa', 'dns-server', '1', 'port', '1053'])
        self.cli_set(ddns + ['reverse-domain', '0.168.192.in-addr.arpa', 'dns-server', '2', 'address', '100.100.0.1'])
        self.cli_set(ddns + ['reverse-domain', '0.168.192.in-addr.arpa', 'dns-server', '2', 'port', '1153'])
        self.cli_set(ddns + ['reverse-domain', '0.168.192.in-addr.arpa', 'key-name', 'reverse-0-168-192'])

        shared = base_path + ['shared-network-name', shared_net_name]

        self.cli_set(shared + ['dynamic-dns-update', 'send-updates', 'enable'])
        self.cli_set(shared + ['dynamic-dns-update', 'conflict-resolution', 'enable'])
        self.cli_set(shared + ['dynamic-dns-update', 'ttl-percent', '75'])

        pool = shared + [ 'subnet', subnet]

        self.cli_set(pool + ['subnet-id', '1'])

        self.cli_set(pool + ['range', '0', 'start', range_0_start])
        self.cli_set(pool + ['range', '0', 'stop', range_0_stop])

        self.cli_set(pool + ['dynamic-dns-update', 'send-updates', 'enable'])
        self.cli_set(pool + ['dynamic-dns-update', 'generated-prefix', 'myfunnyprefix'])
        self.cli_set(pool + ['dynamic-dns-update', 'qualifying-suffix', 'suffix.lan'])
        self.cli_set(pool + ['dynamic-dns-update', 'hostname-char-set', 'xXyYzZ'])
        self.cli_set(pool + ['dynamic-dns-update', 'hostname-char-replacement', '_xXx_'])

        self.cli_commit()

        config = read_file(KEA4_CONF)
        d2_config = read_file(KEA4_D2_CONF)

        obj = loads(config)
        d2_obj = loads(d2_config)

        # Verify global DDNS parameters in the main config file
        self.verify_config_value(
            obj,
            ['Dhcp4'], 'dhcp-ddns',
            {'enable-updates': True, 'server-ip': '127.0.0.1', 'server-port': 53001, 'sender-ip': '', 'sender-port': 0,
                'max-queue-size': 1024, 'ncr-protocol': 'UDP', 'ncr-format': 'JSON'})

        self.verify_config_value(obj, ['Dhcp4'], 'ddns-send-updates', True)
        self.verify_config_value(obj, ['Dhcp4'], 'ddns-use-conflict-resolution', True)
        self.verify_config_value(obj, ['Dhcp4'], 'ddns-override-no-update', True)
        self.verify_config_value(obj, ['Dhcp4'], 'ddns-override-client-update', True)
        self.verify_config_value(obj, ['Dhcp4'], 'ddns-replace-client-name', 'always')
        self.verify_config_value(obj, ['Dhcp4'], 'ddns-update-on-renew', True)

        # Verify scoped DDNS parameters in the main config file
        self.verify_config_value(obj, ['Dhcp4', 'shared-networks'], 'name', shared_net_name)
        self.verify_config_value(obj, ['Dhcp4', 'shared-networks'], 'ddns-send-updates', True)
        self.verify_config_value(obj, ['Dhcp4', 'shared-networks'], 'ddns-use-conflict-resolution', True)
        self.verify_config_value(obj, ['Dhcp4', 'shared-networks'], 'ddns-ttl-percent', 0.75)

        self.verify_config_value(obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'subnet', subnet)
        self.verify_config_value(obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'id', 1)
        self.verify_config_value(obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'ddns-send-updates', True)
        self.verify_config_value(obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'ddns-generated-prefix', 'myfunnyprefix')
        self.verify_config_value(obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'ddns-qualifying-suffix', 'suffix.lan')
        self.verify_config_value(obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'hostname-char-set', 'xXyYzZ')
        self.verify_config_value(obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'hostname-char-replacement', '_xXx_')

        # Verify keys and domains configuration in the D2 config
        self.verify_config_object(
            d2_obj,
            ['DhcpDdns', 'tsig-keys'],
            {'name': 'domain-lan-updates', 'algorithm': 'HMAC-SHA256', 'secret': 'SXQncyBXZWRuZXNkYXkgbWFoIGR1ZGVzIQ=='}
        )
        self.verify_config_object(
            d2_obj,
            ['DhcpDdns', 'tsig-keys'],
            {'name': 'reverse-0-168-192', 'algorithm': 'HMAC-SHA256', 'secret': 'VGhhbmsgR29kIGl0J3MgRnJpZGF5IQ=='}
        )

        self.verify_config_value(d2_obj, ['DhcpDdns', 'forward-ddns', 'ddns-domains', 0], 'name', 'domain.lan')
        self.verify_config_value(d2_obj, ['DhcpDdns', 'forward-ddns', 'ddns-domains', 0], 'key-name', 'domain-lan-updates')
        self.verify_config_object(
            d2_obj,
            ['DhcpDdns', 'forward-ddns', 'ddns-domains', 0, 'dns-servers'],
            {'ip-address': '192.168.0.1'}
            )
        self.verify_config_object(
            d2_obj,
            ['DhcpDdns', 'forward-ddns', 'ddns-domains', 0, 'dns-servers'],
            {'ip-address': '100.100.0.1'}
            )

        self.verify_config_value(d2_obj, ['DhcpDdns', 'reverse-ddns', 'ddns-domains', 0], 'name', '0.168.192.in-addr.arpa')
        self.verify_config_value(d2_obj, ['DhcpDdns', 'reverse-ddns', 'ddns-domains', 0], 'key-name', 'reverse-0-168-192')
        self.verify_config_object(
            d2_obj,
            ['DhcpDdns', 'reverse-ddns', 'ddns-domains', 0, 'dns-servers'],
            {'ip-address': '192.168.0.1', 'port': 1053}
            )
        self.verify_config_object(
            d2_obj,
            ['DhcpDdns', 'reverse-ddns', 'ddns-domains', 0, 'dns-servers'],
            {'ip-address': '100.100.0.1', 'port': 1153}
            )

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))
        self.assertTrue(process_named_running(D2_PROCESS_NAME))

    def test_dhcp_on_interface_with_vrf(self):
        self.cli_set(['interfaces', 'ethernet', 'eth1', 'address', '10.1.1.1/30'])
        self.cli_set(['interfaces', 'ethernet', 'eth1', 'vrf', 'SMOKE-DHCP'])
        self.cli_set(
            [
                'protocols',
                'static',
                'route',
                '10.1.10.0/24',
                'interface',
                'eth1',
                'vrf',
                'SMOKE-DHCP',
            ]
        )
        self.cli_set(
            [
                'vrf',
                'name',
                'SMOKE-DHCP',
                'protocols',
                'static',
                'route',
                '10.1.10.0/24',
                'next-hop',
                '10.1.1.2',
            ]
        )
        self.cli_set(['vrf', 'name', 'SMOKE-DHCP', 'table', '1000'])
        self.cli_set(
            base_path
            + [
                'shared-network-name',
                'SMOKE-DHCP-NETWORK',
                'subnet',
                '10.1.10.0/24',
                'subnet-id',
                '1',
            ]
        )
        self.cli_set(
            base_path
            + [
                'shared-network-name',
                'SMOKE-DHCP-NETWORK',
                'subnet',
                '10.1.10.0/24',
                'option',
                'default-router',
                '10.1.10.1',
            ]
        )
        self.cli_set(
            base_path
            + [
                'shared-network-name',
                'SMOKE-DHCP-NETWORK',
                'subnet',
                '10.1.10.0/24',
                'option',
                'name-server',
                '1.1.1.1',
            ]
        )
        self.cli_set(
            base_path
            + [
                'shared-network-name',
                'SMOKE-DHCP-NETWORK',
                'subnet',
                '10.1.10.0/24',
                'range',
                '1',
                'start',
                '10.1.10.10',
            ]
        )
        self.cli_set(
            base_path
            + [
                'shared-network-name',
                'SMOKE-DHCP-NETWORK',
                'subnet',
                '10.1.10.0/24',
                'range',
                '1',
                'stop',
                '10.1.10.20',
            ]
        )
        self.cli_set(base_path + ['listen-address', '10.1.1.1'])
        self.cli_commit()

        config = read_file(KEA4_CONF)
        obj = loads(config)

        self.verify_config_value(
            obj, ['Dhcp4', 'interfaces-config'], 'interfaces', ['eth1/10.1.1.1']
        )

        self.cli_delete(['interfaces', 'ethernet', 'eth1', 'vrf', 'SMOKE-DHCP'])
        self.cli_delete(
            ['protocols', 'static', 'route', '10.1.10.0/24', 'interface', 'eth1', 'vrf']
        )
        self.cli_delete(['vrf', 'name', 'SMOKE-DHCP'])
        self.cli_commit()

    def test_dhcp_hostsd_lease_sync(self):
        shared_net_name = 'SMOKE-LEASE-SYNC'
        domain_name = 'sync.private'

        client_range = range(1, 4)
        subnet_range_start = inc_ip(subnet, 10)
        subnet_range_stop = inc_ip(subnet, 20)

        def internal_cleanup():
            for seq in client_range:
                ip_addr = inc_ip(subnet, seq)
                kea_delete_lease(4, ip_addr)
                cmd(
                    f'{HOSTSD_CLIENT} --delete-hosts --tag dhcp-server-{ip_addr} --apply'
                )

        self.addClassCleanup(internal_cleanup)

        pool = base_path + ['shared-network-name', shared_net_name, 'subnet', subnet]
        self.cli_set(pool + ['subnet-id', '1'])
        self.cli_set(pool + ['option', 'domain-name', domain_name])
        self.cli_set(pool + ['range', '0', 'start', subnet_range_start])
        self.cli_set(pool + ['range', '0', 'stop', subnet_range_stop])

        # commit changes
        self.cli_commit()

        config = read_file(KEA4_CONF)
        obj = loads(config)

        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks'], 'name', shared_net_name
        )
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'subnet', subnet
        )
        self.verify_config_value(
            obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'id', 1
        )

        # Verify options
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
            {'name': 'domain-name', 'data': domain_name},
        )
        self.verify_config_object(
            obj,
            ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'pools'],
            {'pool': f'{subnet_range_start} - {subnet_range_stop}'},
        )

        # Check for running process
        self.verify_service_running()

        # All up and running, now test vyos-hostsd store

        # 1. Inject leases into kea
        for seq in client_range:
            client = f'client{seq}'
            mac = f'00:50:00:00:00:{seq:02}'
            ip = inc_ip(subnet, seq)
            kea_add_lease(4, '', ip, host_name=client, mac_address=mac)

        # 2. Verify that leases are not available in vyos-hostsd
        tag_regex = re.escape(f'dhcp-server-{subnet.rsplit(".", 1)[0]}')
        host_json = cmd(f'{HOSTSD_CLIENT} --get-hosts {tag_regex}')
        self.assertFalse(host_json.strip('{}'))

        # 3. Restart the service to trigger vyos-hostsd sync and wait for it to start
        self.assertTrue(process_named_running(PROCESS_NAME, timeout=30))

        # 4. Verify that leases are synced and available in vyos-hostsd
        tag_regex = re.escape(f'dhcp-server-{subnet.rsplit(".", 1)[0]}')
        host_json = cmd(f'{HOSTSD_CLIENT} --get-hosts {tag_regex}')
        self.assertTrue(host_json)


if __name__ == '__main__':
    unittest.main(verbosity=2)
