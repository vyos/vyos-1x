#!/usr/bin/env python3
#
# Copyright (C) 2020-2023 VyOS maintainers and contributors
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

from json import loads

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.template import inc_ip
from vyos.utils.process import process_named_running
from vyos.utils.file import read_file

PROCESS_NAME = 'kea-dhcp6'
KEA6_CONF = '/run/kea/kea-dhcp6.conf'
base_path = ['service', 'dhcpv6-server']

subnet = '2001:db8:f00::/64'
dns_1 = '2001:db8::1'
dns_2 = '2001:db8::2'
domain = 'vyos.net'
nis_servers = ['2001:db8:ffff::1', '2001:db8:ffff::2']
interface = 'eth0'
interface_addr = inc_ip(subnet, 1) + '/64'

class TestServiceDHCPv6Server(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestServiceDHCPv6Server, cls).setUpClass()
        # Clear out current configuration to allow running this test on a live system
        cls.cli_delete(cls, base_path)

        cls.cli_set(cls, ['interfaces', 'ethernet', interface, 'address', interface_addr])

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, ['interfaces', 'ethernet', interface, 'address', interface_addr])
        cls.cli_commit(cls)

        super(TestServiceDHCPv6Server, cls).tearDownClass()

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

    def test_single_pool(self):
        shared_net_name = 'SMOKE-1'
        search_domains  = ['foo.vyos.net', 'bar.vyos.net']
        lease_time = '1200'
        max_lease_time = '72000'
        min_lease_time = '600'
        preference = '10'
        sip_server = 'sip.vyos.net'
        sntp_server = inc_ip(subnet, 100)
        range_start = inc_ip(subnet, 256)  # ::100
        range_stop = inc_ip(subnet, 65535) # ::ffff

        pool = base_path + ['shared-network-name', shared_net_name, 'subnet', subnet]

        self.cli_set(base_path + ['preference', preference])
        self.cli_set(pool + ['interface', interface])
        self.cli_set(pool + ['subnet-id', '1'])
        # we use the first subnet IP address as default gateway
        self.cli_set(pool + ['lease-time', 'default', lease_time])
        self.cli_set(pool + ['lease-time', 'maximum', max_lease_time])
        self.cli_set(pool + ['lease-time', 'minimum', min_lease_time])
        self.cli_set(pool + ['option', 'name-server', dns_1])
        self.cli_set(pool + ['option', 'name-server', dns_2])
        self.cli_set(pool + ['option', 'name-server', dns_2])
        self.cli_set(pool + ['option', 'nis-domain', domain])
        self.cli_set(pool + ['option', 'nisplus-domain', domain])
        self.cli_set(pool + ['option', 'sip-server', sip_server])
        self.cli_set(pool + ['option', 'sntp-server', sntp_server])
        self.cli_set(pool + ['range', '1', 'start', range_start])
        self.cli_set(pool + ['range', '1', 'stop', range_stop])

        for server in nis_servers:
            self.cli_set(pool + ['option', 'nis-server', server])
            self.cli_set(pool + ['option', 'nisplus-server', server])

        for search in search_domains:
            self.cli_set(pool + ['option', 'domain-search', search])

        client_base = 1
        for client in ['client1', 'client2', 'client3']:
            duid = f'00:01:00:01:12:34:56:78:aa:bb:cc:dd:ee:{client_base:02}'
            self.cli_set(pool + ['static-mapping', client, 'duid', duid])
            self.cli_set(pool + ['static-mapping', client, 'ipv6-address', inc_ip(subnet, client_base)])
            self.cli_set(pool + ['static-mapping', client, 'ipv6-prefix', inc_ip(subnet, client_base << 64) + '/64'])
            client_base += 1

        # cannot have both mac-address and duid set
        with self.assertRaises(ConfigSessionError):
            self.cli_set(pool + ['static-mapping', 'client1', 'mac', '00:50:00:00:00:11'])
            self.cli_commit()
        self.cli_delete(pool + ['static-mapping', 'client1', 'mac'])

        # commit changes
        self.cli_commit()

        config = read_file(KEA6_CONF)
        obj = loads(config)

        self.verify_config_value(obj, ['Dhcp6', 'shared-networks'], 'name', shared_net_name)
        self.verify_config_value(obj, ['Dhcp6', 'shared-networks', 0, 'subnet6'], 'subnet', subnet)
        self.verify_config_value(obj, ['Dhcp6', 'shared-networks', 0, 'subnet6'], 'interface', interface)
        self.verify_config_value(obj, ['Dhcp6', 'shared-networks', 0, 'subnet6'], 'id', 1)
        self.verify_config_value(obj, ['Dhcp6', 'shared-networks', 0, 'subnet6'], 'valid-lifetime', int(lease_time))
        self.verify_config_value(obj, ['Dhcp6', 'shared-networks', 0, 'subnet6'], 'min-valid-lifetime', int(min_lease_time))
        self.verify_config_value(obj, ['Dhcp6', 'shared-networks', 0, 'subnet6'], 'max-valid-lifetime', int(max_lease_time))

        # Verify options
        self.verify_config_object(
                obj,
                ['Dhcp6', 'shared-networks', 0, 'subnet6', 0, 'option-data'],
                {'name': 'dns-servers', 'data': f'{dns_1}, {dns_2}'})
        self.verify_config_object(
                obj,
                ['Dhcp6', 'shared-networks', 0, 'subnet6', 0, 'option-data'],
                {'name': 'domain-search', 'data': ", ".join(search_domains)})
        self.verify_config_object(
                obj,
                ['Dhcp6', 'shared-networks', 0, 'subnet6', 0, 'option-data'],
                {'name': 'nis-domain-name', 'data': domain})
        self.verify_config_object(
                obj,
                ['Dhcp6', 'shared-networks', 0, 'subnet6', 0, 'option-data'],
                {'name': 'nis-servers', 'data': ", ".join(nis_servers)})
        self.verify_config_object(
                obj,
                ['Dhcp6', 'shared-networks', 0, 'subnet6', 0, 'option-data'],
                {'name': 'nisp-domain-name', 'data': domain})
        self.verify_config_object(
                obj,
                ['Dhcp6', 'shared-networks', 0, 'subnet6', 0, 'option-data'],
                {'name': 'nisp-servers', 'data': ", ".join(nis_servers)})
        self.verify_config_object(
                obj,
                ['Dhcp6', 'shared-networks', 0, 'subnet6', 0, 'option-data'],
                {'name': 'sntp-servers', 'data': sntp_server})
        self.verify_config_object(
                obj,
                ['Dhcp6', 'shared-networks', 0, 'subnet6', 0, 'option-data'],
                {'name': 'sip-server-dns', 'data': sip_server})

        # Verify pools
        self.verify_config_object(
                obj,
                ['Dhcp6', 'shared-networks', 0, 'subnet6', 0, 'pools'],
                {'pool': f'{range_start} - {range_stop}'})

        client_base = 1
        for client in ['client1', 'client2', 'client3']:
            duid = f'00:01:00:01:12:34:56:78:aa:bb:cc:dd:ee:{client_base:02}'
            ip = inc_ip(subnet, client_base)
            prefix = inc_ip(subnet, client_base << 64) + '/64'

            self.verify_config_object(
                    obj,
                    ['Dhcp6', 'shared-networks', 0, 'subnet6', 0, 'reservations'],
                    {'hostname': client, 'duid': duid, 'ip-addresses': [ip], 'prefixes': [prefix]})

            client_base += 1

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))


    def test_prefix_delegation(self):
        shared_net_name = 'SMOKE-2'
        range_start = inc_ip(subnet, 256)  # ::100
        range_stop = inc_ip(subnet, 65535) # ::ffff
        delegate_start = '2001:db8:ee::'
        delegate_len = '64'
        prefix_len = '56'
        exclude_len = '66'

        pool = base_path + ['shared-network-name', shared_net_name, 'subnet', subnet]
        self.cli_set(pool + ['subnet-id', '1'])
        self.cli_set(pool + ['range', '1', 'start', range_start])
        self.cli_set(pool + ['range', '1', 'stop', range_stop])
        self.cli_set(pool + ['prefix-delegation', 'prefix', delegate_start, 'delegated-length', delegate_len])
        self.cli_set(pool + ['prefix-delegation', 'prefix', delegate_start, 'prefix-length', prefix_len])
        self.cli_set(pool + ['prefix-delegation', 'prefix', delegate_start, 'excluded-prefix', delegate_start])
        self.cli_set(pool + ['prefix-delegation', 'prefix', delegate_start, 'excluded-prefix-length', exclude_len])

        # commit changes
        self.cli_commit()

        config = read_file(KEA6_CONF)
        obj = loads(config)

        self.verify_config_value(obj, ['Dhcp6', 'shared-networks'], 'name', shared_net_name)
        self.verify_config_value(obj, ['Dhcp6', 'shared-networks', 0, 'subnet6'], 'subnet', subnet)

        # Verify pools
        self.verify_config_object(
                obj,
                ['Dhcp6', 'shared-networks', 0, 'subnet6', 0, 'pools'],
                {'pool': f'{range_start} - {range_stop}'})

        self.verify_config_object(
                obj,
                ['Dhcp6', 'shared-networks', 0, 'subnet6', 0, 'pd-pools'],
                {
                    'prefix': delegate_start,
                    'prefix-len': int(prefix_len),
                    'delegated-len': int(delegate_len),
                    'excluded-prefix': delegate_start,
                    'excluded-prefix-len': int(exclude_len)
                })

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_global_nameserver(self):
        shared_net_name = 'SMOKE-3'
        ns_global_1 = '2001:db8::1111'
        ns_global_2 = '2001:db8::2222'

        self.cli_set(base_path + ['global-parameters', 'name-server', ns_global_1])
        self.cli_set(base_path + ['global-parameters', 'name-server', ns_global_2])
        self.cli_set(base_path + ['shared-network-name', shared_net_name, 'subnet', subnet, 'subnet-id', '1'])

        # commit changes
        self.cli_commit()

        config = read_file(KEA6_CONF)
        obj = loads(config)

        self.verify_config_value(obj, ['Dhcp6', 'shared-networks'], 'name', shared_net_name)
        self.verify_config_value(obj, ['Dhcp6', 'shared-networks', 0, 'subnet6'], 'subnet', subnet)
        self.verify_config_value(obj, ['Dhcp6', 'shared-networks', 0, 'subnet6'], 'id', 1)

        self.verify_config_object(
                obj,
                ['Dhcp6', 'option-data'],
                {'name': 'dns-servers', "code": 23, "space": "dhcp6", "csv-format": True, 'data': f'{ns_global_1}, {ns_global_2}'})

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

if __name__ == '__main__':
    unittest.main(verbosity=2)
