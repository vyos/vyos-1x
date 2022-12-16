#!/usr/bin/env python3
#
# Copyright (C) 2020-2021 VyOS maintainers and contributors
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

from json import loads

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.utils.dict import dict_search_recursive
from vyos.utils.process import process_named_running
from vyos.utils.file import read_file
from vyos.template import address_from_cidr
from vyos.template import inc_ip
from vyos.template import dec_ip
from vyos.template import netmask_from_cidr

PROCESS_NAME = 'kea-dhcp4'
CTRL_PROCESS_NAME = 'kea-ctrl-agent'
KEA4_CONF = '/run/kea/kea-dhcp4.conf'
KEA4_CTRL = '/run/kea/dhcp4-ctrl-socket'
base_path = ['service', 'dhcp-server']
subnet = '192.0.2.0/25'
router = inc_ip(subnet, 1)
dns_1 = inc_ip(subnet, 2)
dns_2 = inc_ip(subnet, 3)
domain_name = 'vyos.net'

class TestServiceDHCPServer(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestServiceDHCPServer, cls).setUpClass()

        cidr_mask = subnet.split('/')[-1]
        cls.cli_set(cls, ['interfaces', 'dummy', 'dum8765', 'address', f'{router}/{cidr_mask}'])

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, ['interfaces', 'dummy', 'dum8765'])
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
                assert False, "Invalid type"

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

    def test_dhcp_single_pool_range(self):
        shared_net_name = 'SMOKE-1'

        range_0_start = inc_ip(subnet, 10)
        range_0_stop  = inc_ip(subnet, 20)
        range_1_start = inc_ip(subnet, 40)
        range_1_stop  = inc_ip(subnet, 50)

        pool = base_path + ['shared-network-name', shared_net_name, 'subnet', subnet]
        # we use the first subnet IP address as default gateway
        self.cli_set(pool + ['default-router', router])
        self.cli_set(pool + ['name-server', dns_1])
        self.cli_set(pool + ['name-server', dns_2])
        self.cli_set(pool + ['domain-name', domain_name])

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

        self.verify_config_value(obj, ['Dhcp4', 'shared-networks'], 'name', shared_net_name)
        self.verify_config_value(obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'subnet', subnet)
        self.verify_config_value(obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'valid-lifetime', 86400)
        self.verify_config_value(obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'max-valid-lifetime', 86400)

        # Verify options
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
                {'name': 'domain-name', 'data': domain_name})
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
                {'name': 'domain-name-servers', 'data': f'{dns_1}, {dns_2}'})
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
                {'name': 'routers', 'data': router})

        # Verify pools
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'pools'],
                {'pool': f'{range_0_start} - {range_0_stop}'})
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'pools'],
                {'pool': f'{range_1_start} - {range_1_stop}'})

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_dhcp_single_pool_options(self):
        shared_net_name = 'SMOKE-0815'

        range_0_start       = inc_ip(subnet, 10)
        range_0_stop        = inc_ip(subnet, 20)
        smtp_server         = '1.2.3.4'
        time_server         = '4.3.2.1'
        tftp_server         = 'tftp.vyos.io'
        search_domains      = ['foo.vyos.net', 'bar.vyos.net']
        bootfile_name       = 'vyos'
        bootfile_server     = '192.0.2.1'
        wpad                = 'http://wpad.vyos.io/foo/bar'
        server_identifier   = bootfile_server
        ipv6_only_preferred = '300'

        pool = base_path + ['shared-network-name', shared_net_name, 'subnet', subnet]
        # we use the first subnet IP address as default gateway
        self.cli_set(pool + ['default-router', router])
        self.cli_set(pool + ['name-server', dns_1])
        self.cli_set(pool + ['name-server', dns_2])
        self.cli_set(pool + ['domain-name', domain_name])
        self.cli_set(pool + ['ip-forwarding'])
        self.cli_set(pool + ['smtp-server', smtp_server])
        self.cli_set(pool + ['pop-server', smtp_server])
        self.cli_set(pool + ['time-server', time_server])
        self.cli_set(pool + ['tftp-server-name', tftp_server])
        for search in search_domains:
            self.cli_set(pool + ['domain-search', search])
        self.cli_set(pool + ['bootfile-name', bootfile_name])
        self.cli_set(pool + ['bootfile-server', bootfile_server])
        self.cli_set(pool + ['wpad-url', wpad])
        self.cli_set(pool + ['server-identifier', server_identifier])

        self.cli_set(pool + ['static-route', '10.0.0.0/24', 'next-hop', '192.0.2.1'])
        self.cli_set(pool + ['ipv6-only-preferred', ipv6_only_preferred])

        # check validate() - No DHCP address range or active static-mapping set
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(pool + ['range', '0', 'start', range_0_start])
        self.cli_set(pool + ['range', '0', 'stop', range_0_stop])

        # commit changes
        self.cli_commit()

        config = read_file(KEA4_CONF)
        obj = loads(config)

        self.verify_config_value(obj, ['Dhcp4', 'shared-networks'], 'name', shared_net_name)
        self.verify_config_value(obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'subnet', subnet)
        self.verify_config_value(obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'boot-file-name', bootfile_name)
        self.verify_config_value(obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'next-server', bootfile_server)
        self.verify_config_value(obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'valid-lifetime', 86400)
        self.verify_config_value(obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'max-valid-lifetime', 86400)

        # Verify options
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
                {'name': 'domain-name', 'data': domain_name})
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
                {'name': 'domain-name-servers', 'data': f'{dns_1}, {dns_2}'})
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
                {'name': 'domain-search', 'data': ', '.join(search_domains)})
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
                {'name': 'pop-server', 'data': smtp_server})
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
                {'name': 'smtp-server', 'data': smtp_server})
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
                {'name': 'time-servers', 'data': time_server})
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
                {'name': 'routers', 'data': router})
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
                {'name': 'dhcp-server-identifier', 'data': server_identifier})
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
                {'name': 'tftp-server-name', 'data': tftp_server})
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
                {'name': 'wpad-url', 'data': wpad})
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
                {'name': 'rfc3442-static-route', 'data': '24,10,0,0,192,0,2,1, 0,192,0,2,1'})
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
                {'name': 'windows-static-route', 'data': '24,10,0,0,192,0,2,1'})
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
                {'name': 'v6-only-preferred', 'data': ipv6_only_preferred})
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
                {'name': 'ip-forwarding', 'data': "true"})

        # Verify pools
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'pools'],
                {'pool': f'{range_0_start} - {range_0_stop}'})

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_dhcp_single_pool_static_mapping(self):
        shared_net_name = 'SMOKE-2'
        domain_name = 'private'

        pool = base_path + ['shared-network-name', shared_net_name, 'subnet', subnet]
        # we use the first subnet IP address as default gateway
        self.cli_set(pool + ['default-router', router])
        self.cli_set(pool + ['name-server', dns_1])
        self.cli_set(pool + ['name-server', dns_2])
        self.cli_set(pool + ['domain-name', domain_name])

        # check validate() - No DHCP address range or active static-mapping set
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        client_base = 10
        for client in ['client1', 'client2', 'client3']:
            mac = '00:50:00:00:00:{}'.format(client_base)
            self.cli_set(pool + ['static-mapping', client, 'mac-address', mac])
            self.cli_set(pool + ['static-mapping', client, 'ip-address', inc_ip(subnet, client_base)])
            client_base += 1

        # commit changes
        self.cli_commit()

        config = read_file(KEA4_CONF)
        obj = loads(config)

        self.verify_config_value(obj, ['Dhcp4', 'shared-networks'], 'name', shared_net_name)
        self.verify_config_value(obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'subnet', subnet)
        self.verify_config_value(obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'valid-lifetime', 86400)
        self.verify_config_value(obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'max-valid-lifetime', 86400)

        # Verify options
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
                {'name': 'domain-name', 'data': domain_name})
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
                {'name': 'domain-name-servers', 'data': f'{dns_1}, {dns_2}'})
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
                {'name': 'routers', 'data': router})

        client_base = 10
        for client in ['client1', 'client2', 'client3']:
            mac = '00:50:00:00:00:{}'.format(client_base)
            ip = inc_ip(subnet, client_base)

            self.verify_config_object(
                    obj,
                    ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'reservations'],
                    {'hw-address': mac, 'ip-address': ip})

            client_base += 1

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_dhcp_multiple_pools(self):
        lease_time = '14400'

        for network in ['0', '1', '2', '3']:
            shared_net_name = f'VyOS-SMOKETEST-{network}'
            subnet = f'192.0.{network}.0/24'
            router = inc_ip(subnet, 1)
            dns_1 = inc_ip(subnet, 2)

            range_0_start = inc_ip(subnet, 10)
            range_0_stop  = inc_ip(subnet, 20)
            range_1_start = inc_ip(subnet, 30)
            range_1_stop  = inc_ip(subnet, 40)

            pool = base_path + ['shared-network-name', shared_net_name, 'subnet', subnet]
            # we use the first subnet IP address as default gateway
            self.cli_set(pool + ['default-router', router])
            self.cli_set(pool + ['name-server', dns_1])
            self.cli_set(pool + ['domain-name', domain_name])
            self.cli_set(pool + ['lease', lease_time])

            self.cli_set(pool + ['range', '0', 'start', range_0_start])
            self.cli_set(pool + ['range', '0', 'stop', range_0_stop])
            self.cli_set(pool + ['range', '1', 'start', range_1_start])
            self.cli_set(pool + ['range', '1', 'stop', range_1_stop])

            client_base = 60
            for client in ['client1', 'client2', 'client3', 'client4']:
                mac = '02:50:00:00:00:{}'.format(client_base)
                self.cli_set(pool + ['static-mapping', client, 'mac-address', mac])
                self.cli_set(pool + ['static-mapping', client, 'ip-address', inc_ip(subnet, client_base)])
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
            range_0_stop  = inc_ip(subnet, 20)
            range_1_start = inc_ip(subnet, 30)
            range_1_stop  = inc_ip(subnet, 40)

            self.verify_config_value(obj, ['Dhcp4', 'shared-networks'], 'name', shared_net_name)
            self.verify_config_value(obj, ['Dhcp4', 'shared-networks', int(network), 'subnet4'], 'subnet', subnet)
            self.verify_config_value(obj, ['Dhcp4', 'shared-networks', int(network), 'subnet4'], 'valid-lifetime', int(lease_time))
            self.verify_config_value(obj, ['Dhcp4', 'shared-networks', int(network), 'subnet4'], 'max-valid-lifetime', int(lease_time))

            self.verify_config_object(
                    obj,
                    ['Dhcp4', 'shared-networks', int(network), 'subnet4', 0, 'option-data'],
                    {'name': 'domain-name', 'data': domain_name})
            self.verify_config_object(
                    obj,
                    ['Dhcp4', 'shared-networks', int(network), 'subnet4', 0, 'option-data'],
                    {'name': 'domain-name-servers', 'data': dns_1})
            self.verify_config_object(
                    obj,
                    ['Dhcp4', 'shared-networks', int(network), 'subnet4', 0, 'option-data'],
                    {'name': 'routers', 'data': router})

            self.verify_config_object(
                    obj,
                    ['Dhcp4', 'shared-networks', int(network), 'subnet4', 0, 'pools'],
                    {'pool': f'{range_0_start} - {range_0_stop}'})
            self.verify_config_object(
                    obj,
                    ['Dhcp4', 'shared-networks', int(network), 'subnet4', 0, 'pools'],
                    {'pool': f'{range_1_start} - {range_1_stop}'})

            client_base = 60
            for client in ['client1', 'client2', 'client3', 'client4']:
                mac = '02:50:00:00:00:{}'.format(client_base)
                ip = inc_ip(subnet, client_base)

                self.verify_config_object(
                        obj,
                        ['Dhcp4', 'shared-networks', int(network), 'subnet4', 0, 'reservations'],
                        {'hw-address': mac, 'ip-address': ip})

                client_base += 1

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_dhcp_exclude_not_in_range(self):
        # T3180: verify else path when slicing DHCP ranges and exclude address
        # is not part of the DHCP range
        range_0_start = inc_ip(subnet, 10)
        range_0_stop  = inc_ip(subnet, 20)

        pool = base_path + ['shared-network-name', 'EXCLUDE-TEST', 'subnet', subnet]
        self.cli_set(pool + ['default-router', router])
        self.cli_set(pool + ['exclude', router])
        self.cli_set(pool + ['range', '0', 'start', range_0_start])
        self.cli_set(pool + ['range', '0', 'stop', range_0_stop])

        # commit changes
        self.cli_commit()

        config = read_file(KEA4_CONF)
        obj = loads(config)

        self.verify_config_value(obj, ['Dhcp4', 'shared-networks'], 'name', 'EXCLUDE-TEST')
        self.verify_config_value(obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'subnet', subnet)

        # Verify options
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
                {'name': 'routers', 'data': router})

        # Verify pools
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'pools'],
                {'pool': f'{range_0_start} - {range_0_stop}'})

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_dhcp_exclude_in_range(self):
        # T3180: verify else path when slicing DHCP ranges and exclude address
        # is not part of the DHCP range
        range_0_start = inc_ip(subnet, 10)
        range_0_stop  = inc_ip(subnet, 100)

        # the DHCP exclude addresse is blanked out of the range which is done
        # by slicing one range into two ranges
        exclude_addr  = inc_ip(range_0_start, 20)
        range_0_stop_excl = dec_ip(exclude_addr, 1)
        range_0_start_excl = inc_ip(exclude_addr, 1)

        pool = base_path + ['shared-network-name', 'EXCLUDE-TEST-2', 'subnet', subnet]
        self.cli_set(pool + ['default-router', router])
        self.cli_set(pool + ['exclude', exclude_addr])
        self.cli_set(pool + ['range', '0', 'start', range_0_start])
        self.cli_set(pool + ['range', '0', 'stop', range_0_stop])

        # commit changes
        self.cli_commit()

        config = read_file(KEA4_CONF)
        obj = loads(config)

        self.verify_config_value(obj, ['Dhcp4', 'shared-networks'], 'name', 'EXCLUDE-TEST-2')
        self.verify_config_value(obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'subnet', subnet)

        # Verify options
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
                {'name': 'routers', 'data': router})

        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'pools'],
                {'pool': f'{range_0_start} - {range_0_stop_excl}'})

        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'pools'],
                {'pool': f'{range_0_start_excl} - {range_0_stop}'})

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_dhcp_relay_server(self):
        # Listen on specific address and return DHCP leases from a non
        # directly connected pool
        self.cli_set(base_path + ['listen-address', router])

        relay_subnet = '10.0.0.0/16'
        relay_router = inc_ip(relay_subnet, 1)

        range_0_start = '10.0.1.0'
        range_0_stop  = '10.0.250.255'

        pool = base_path + ['shared-network-name', 'RELAY', 'subnet', relay_subnet]
        self.cli_set(pool + ['default-router', relay_router])
        self.cli_set(pool + ['range', '0', 'start', range_0_start])
        self.cli_set(pool + ['range', '0', 'stop', range_0_stop])

        # commit changes
        self.cli_commit()

        config = read_file(KEA4_CONF)
        obj = loads(config)

        self.verify_config_value(obj, ['Dhcp4', 'shared-networks'], 'name', 'RELAY')
        self.verify_config_value(obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'subnet', relay_subnet)

        # Verify options
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
                {'name': 'routers', 'data': relay_router})

        # Verify pools
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'pools'],
                {'pool': f'{range_0_start} - {range_0_stop}'})

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_dhcp_failover(self):
        shared_net_name = 'FAILOVER'
        failover_name = 'VyOS-Failover'

        range_0_start = inc_ip(subnet, 10)
        range_0_stop  = inc_ip(subnet, 20)

        pool = base_path + ['shared-network-name', shared_net_name, 'subnet', subnet]
        # we use the first subnet IP address as default gateway
        self.cli_set(pool + ['default-router', router])

        # check validate() - No DHCP address range or active static-mapping set
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(pool + ['range', '0', 'start', range_0_start])
        self.cli_set(pool + ['range', '0', 'stop', range_0_stop])

        # failover
        failover_local = router
        failover_remote = inc_ip(router, 1)

        self.cli_set(base_path + ['failover', 'source-address', failover_local])
        self.cli_set(base_path + ['failover', 'name', failover_name])
        self.cli_set(base_path + ['failover', 'remote', failover_remote])
        self.cli_set(base_path + ['failover', 'status', 'primary'])

        # commit changes
        self.cli_commit()

        config = read_file(KEA4_CONF)
        obj = loads(config)

        # Verify failover
        self.verify_config_value(obj, ['Dhcp4', 'control-socket'], 'socket-name', KEA4_CTRL)

        self.verify_config_object(
            obj,
            ['Dhcp4', 'hooks-libraries', 0, 'parameters', 'high-availability', 0, 'peers'],
            {'name': os.uname()[1], 'url': f'http://{failover_local}:647/', 'role': 'primary', 'auto-failover': True})

        self.verify_config_object(
            obj,
            ['Dhcp4', 'hooks-libraries', 0, 'parameters', 'high-availability', 0, 'peers'],
            {'name': failover_name, 'url': f'http://{failover_remote}:647/', 'role': 'standby', 'auto-failover': True})

        self.verify_config_value(obj, ['Dhcp4', 'shared-networks'], 'name', shared_net_name)
        self.verify_config_value(obj, ['Dhcp4', 'shared-networks', 0, 'subnet4'], 'subnet', subnet)

        # Verify options
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'option-data'],
                {'name': 'routers', 'data': router})

        # Verify pools
        self.verify_config_object(
                obj,
                ['Dhcp4', 'shared-networks', 0, 'subnet4', 0, 'pools'],
                {'pool': f'{range_0_start} - {range_0_stop}'})

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))
        self.assertTrue(process_named_running(CTRL_PROCESS_NAME))

if __name__ == '__main__':
    unittest.main(verbosity=2)
