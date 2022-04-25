#!/usr/bin/env python3
#
# Copyright (C) 2020-2022 VyOS maintainers and contributors
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

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.template import inc_ip
from vyos.util import process_named_running
from vyos.util import read_file

PROCESS_NAME = 'dhcpd'
DHCPD_CONF = '/run/dhcp-server/dhcpdv6.conf'
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
        cls.cli_set(cls, ['interfaces', 'ethernet', interface, 'address', interface_addr])

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, ['interfaces', 'ethernet', interface, 'address', interface_addr])
        cls.cli_commit(cls)

        super(TestServiceDHCPv6Server, cls).tearDownClass()

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

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

        # we use the first subnet IP address as default gateway
        self.cli_set(pool + ['name-server', dns_1])
        self.cli_set(pool + ['name-server', dns_2])
        self.cli_set(pool + ['name-server', dns_2])
        self.cli_set(pool + ['lease-time', 'default', lease_time])
        self.cli_set(pool + ['lease-time', 'maximum', max_lease_time])
        self.cli_set(pool + ['lease-time', 'minimum', min_lease_time])
        self.cli_set(pool + ['nis-domain', domain])
        self.cli_set(pool + ['nisplus-domain', domain])
        self.cli_set(pool + ['sip-server', sip_server])
        self.cli_set(pool + ['sntp-server', sntp_server])
        self.cli_set(pool + ['address-range', 'start', range_start, 'stop', range_stop])

        for server in nis_servers:
            self.cli_set(pool + ['nis-server', server])
            self.cli_set(pool + ['nisplus-server', server])

        for search in search_domains:
            self.cli_set(pool + ['domain-search', search])

        client_base = 1
        for client in ['client1', 'client2', 'client3']:
            cid = '00:01:00:01:12:34:56:78:aa:bb:cc:dd:ee:{}'.format(client_base)
            self.cli_set(pool + ['static-mapping', client, 'identifier', cid])
            self.cli_set(pool + ['static-mapping', client, 'ipv6-address', inc_ip(subnet, client_base)])
            self.cli_set(pool + ['static-mapping', client, 'ipv6-prefix', inc_ip(subnet, client_base << 64) + '/64'])
            client_base += 1

        # commit changes
        self.cli_commit()

        config = read_file(DHCPD_CONF)
        self.assertIn(f'option dhcp6.preference {preference};', config)

        self.assertIn(f'subnet6 {subnet}' + r' {', config)
        search = '"' + '", "'.join(search_domains) + '"'
        nissrv = ', '.join(nis_servers)
        self.assertIn(f'range6 {range_start} {range_stop};', config)
        self.assertIn(f'default-lease-time {lease_time};', config)
        self.assertIn(f'default-lease-time {lease_time};', config)
        self.assertIn(f'max-lease-time {max_lease_time};', config)
        self.assertIn(f'min-lease-time {min_lease_time};', config)
        self.assertIn(f'option dhcp6.domain-search {search};', config)
        self.assertIn(f'option dhcp6.name-servers {dns_1}, {dns_2};', config)
        self.assertIn(f'option dhcp6.nis-domain-name "{domain}";', config)
        self.assertIn(f'option dhcp6.nis-servers {nissrv};', config)
        self.assertIn(f'option dhcp6.nisp-domain-name "{domain}";', config)
        self.assertIn(f'option dhcp6.nisp-servers {nissrv};', config)
        self.assertIn(f'set shared-networkname = "{shared_net_name}";', config)

        client_base = 1
        for client in ['client1', 'client2', 'client3']:
            cid = '00:01:00:01:12:34:56:78:aa:bb:cc:dd:ee:{}'.format(client_base)
            ip = inc_ip(subnet, client_base)
            prefix = inc_ip(subnet, client_base << 64) + '/64'
            self.assertIn(f'host {shared_net_name}_{client}' + ' {', config)
            self.assertIn(f'fixed-address6 {ip};', config)
            self.assertIn(f'fixed-prefix6 {prefix};', config)
            self.assertIn(f'host-identifier option dhcp6.client-id {cid};', config)
            client_base += 1

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))


    def test_prefix_delegation(self):
        shared_net_name = 'SMOKE-2'
        range_start = inc_ip(subnet, 256)  # ::100
        range_stop = inc_ip(subnet, 65535) # ::ffff
        delegate_start = '2001:db8:ee::'
        delegate_stop = '2001:db8:ee:ff00::'
        delegate_len = '56'

        pool = base_path + ['shared-network-name', shared_net_name, 'subnet', subnet]

        self.cli_set(pool + ['address-range', 'start', range_start, 'stop', range_stop])
        self.cli_set(pool + ['prefix-delegation', 'start', delegate_start, 'stop', delegate_stop])
        self.cli_set(pool + ['prefix-delegation', 'start', delegate_start, 'prefix-length', delegate_len])

        # commit changes
        self.cli_commit()

        config = read_file(DHCPD_CONF)
        self.assertIn(f'subnet6 {subnet}' + r' {', config)
        self.assertIn(f'range6 {range_start} {range_stop};', config)
        self.assertIn(f'prefix6 {delegate_start} {delegate_stop} /{delegate_len};', config)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_global_nameserver(self):
        shared_net_name = 'SMOKE-3'
        ns_global_1 = '2001:db8::1111'
        ns_global_2 = '2001:db8::2222'

        self.cli_set(base_path + ['global-parameters', 'name-server', ns_global_1])
        self.cli_set(base_path + ['global-parameters', 'name-server', ns_global_2])
        self.cli_set(base_path + ['shared-network-name', shared_net_name, 'subnet', subnet])

        # commit changes
        self.cli_commit()

        config = read_file(DHCPD_CONF)
        self.assertIn(f'option dhcp6.name-servers {ns_global_1}, {ns_global_2};', config)
        self.assertIn(f'subnet6 {subnet}' + r' {', config)
        self.assertIn(f'set shared-networkname = "{shared_net_name}";', config)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

if __name__ == '__main__':
    unittest.main(verbosity=2)
