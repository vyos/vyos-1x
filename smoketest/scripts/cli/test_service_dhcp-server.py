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

import re
import os
import unittest

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.util import cmd
from vyos.util import process_named_running
from vyos.util import read_file
from vyos.template import address_from_cidr
from vyos.template import inc_ip
from vyos.template import dec_ip
from vyos.template import netmask_from_cidr

PROCESS_NAME = 'dhcpd'
DHCPD_CONF = '/run/dhcp-server/dhcpd.conf'
base_path = ['service', 'dhcp-server']
subnet = '192.0.2.0/25'
router = inc_ip(subnet, 1)
dns_1 = inc_ip(subnet, 2)
dns_2 = inc_ip(subnet, 3)
domain_name = 'vyos.net'

class TestServiceDHCPServer(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())
        cidr_mask = subnet.split('/')[-1]
        self.session.set(['interfaces', 'dummy', 'dum8765', 'address', f'{router}/{cidr_mask}'])

    def tearDown(self):
        self.session.delete(['interfaces', 'dummy', 'dum8765'])
        self.session.delete(base_path)
        self.session.commit()
        del self.session

    def test_dhcp_single_pool_range(self):
        shared_net_name = 'SMOKE-1'

        range_0_start = inc_ip(subnet, 10)
        range_0_stop  = inc_ip(subnet, 20)
        range_1_start = inc_ip(subnet, 40)
        range_1_stop  = inc_ip(subnet, 50)

        self.session.set(base_path + ['dynamic-dns-update'])

        pool = base_path + ['shared-network-name', shared_net_name, 'subnet', subnet]
        # we use the first subnet IP address as default gateway
        self.session.set(pool + ['default-router', router])
        self.session.set(pool + ['dns-server', dns_1])
        self.session.set(pool + ['dns-server', dns_2])
        self.session.set(pool + ['domain-name', domain_name])

        # check validate() - No DHCP address range or active static-mapping set
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(pool + ['range', '0', 'start', range_0_start])
        self.session.set(pool + ['range', '0', 'stop', range_0_stop])
        self.session.set(pool + ['range', '1', 'start', range_1_start])
        self.session.set(pool + ['range', '1', 'stop', range_1_stop])

        # commit changes
        self.session.commit()

        config = read_file(DHCPD_CONF)
        network = address_from_cidr(subnet)
        netmask = netmask_from_cidr(subnet)
        self.assertIn(f'ddns-update-style interim;', config)
        self.assertIn(f'subnet {network} netmask {netmask}' + r' {', config)
        self.assertIn(f'option domain-name-servers {dns_1}, {dns_2};', config)
        self.assertIn(f'option routers {router};', config)
        self.assertIn(f'option domain-name "{domain_name}";', config)
        self.assertIn(f'default-lease-time 86400;', config)
        self.assertIn(f'max-lease-time 86400;', config)
        self.assertIn(f'range {range_0_start} {range_0_stop};', config)
        self.assertIn(f'range {range_1_start} {range_1_stop};', config)
        self.assertIn(f'set shared-networkname = "{shared_net_name}";', config)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_dhcp_single_pool_options(self):
        shared_net_name = 'SMOKE-0815'

        range_0_start   = inc_ip(subnet, 10)
        range_0_stop    = inc_ip(subnet, 20)
        smtp_server     = '1.2.3.4'
        time_server     = '4.3.2.1'
        tftp_server     = 'tftp.vyos.io'
        search_domains  = ['foo.vyos.net', 'bar.vyos.net']
        bootfile_name   = 'vyos'
        bootfile_server = '192.0.2.1'
        wpad            = 'http://wpad.vyos.io/foo/bar'
        server_identifier = bootfile_server

        pool = base_path + ['shared-network-name', shared_net_name, 'subnet', subnet]
        # we use the first subnet IP address as default gateway
        self.session.set(pool + ['default-router', router])
        self.session.set(pool + ['dns-server', dns_1])
        self.session.set(pool + ['dns-server', dns_2])
        self.session.set(pool + ['domain-name', domain_name])
        self.session.set(pool + ['ip-forwarding'])
        self.session.set(pool + ['smtp-server', smtp_server])
        self.session.set(pool + ['pop-server', smtp_server])
        self.session.set(pool + ['time-server', time_server])
        self.session.set(pool + ['tftp-server-name', tftp_server])
        for search in search_domains:
            self.session.set(pool + ['domain-search', search])
        self.session.set(pool + ['bootfile-name', bootfile_name])
        self.session.set(pool + ['bootfile-server', bootfile_server])
        self.session.set(pool + ['wpad-url', wpad])
        self.session.set(pool + ['server-identifier', server_identifier])

        self.session.set(pool + ['static-route', 'destination-subnet', '10.0.0.0/24'])
        self.session.set(pool + ['static-route', 'router', '192.0.2.1'])

        # check validate() - No DHCP address range or active static-mapping set
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(pool + ['range', '0', 'start', range_0_start])
        self.session.set(pool + ['range', '0', 'stop', range_0_stop])

        # failover
        failover_local = router
        failover_remote = inc_ip(router, 1)

        self.session.set(pool + ['failover', 'local-address', failover_local])
        self.session.set(pool + ['failover', 'name', shared_net_name])
        self.session.set(pool + ['failover', 'peer-address', failover_remote])
        self.session.set(pool + ['failover', 'status', 'primary'])

        # commit changes
        self.session.commit()

        config = read_file(DHCPD_CONF)

        self.assertIn(f'failover peer "{shared_net_name}"' + r' {', config)
        self.assertIn(f'primary;', config)
        self.assertIn(f'mclt 1800;', config)
        self.assertIn(f'mclt 1800;', config)
        self.assertIn(f'split 128;', config)
        self.assertIn(f'port 520;', config)
        self.assertIn(f'peer port 520;', config)
        self.assertIn(f'max-response-delay 30;', config)
        self.assertIn(f'max-unacked-updates 10;', config)
        self.assertIn(f'load balance max seconds 3;', config)
        self.assertIn(f'peer port 520;', config)
        self.assertIn(f'address {failover_local};', config)
        self.assertIn(f'peer address {failover_remote};', config)

        network = address_from_cidr(subnet)
        netmask = netmask_from_cidr(subnet)
        self.assertIn(f'ddns-update-style none;', config)
        self.assertIn(f'subnet {network} netmask {netmask}' + r' {', config)
        self.assertIn(f'option domain-name-servers {dns_1}, {dns_2};', config)
        self.assertIn(f'option routers {router};', config)
        self.assertIn(f'option domain-name "{domain_name}";', config)

        search = '"' + ('", "').join(search_domains) + '"'
        self.assertIn(f'option domain-search {search};', config)

        self.assertIn(f'option ip-forwarding true;', config)
        self.assertIn(f'option smtp-server {smtp_server};', config)
        self.assertIn(f'option pop-server {smtp_server};', config)
        self.assertIn(f'option time-servers {time_server};', config)
        self.assertIn(f'option wpad-url "{wpad}";', config)
        self.assertIn(f'option dhcp-server-identifier {server_identifier};', config)
        self.assertIn(f'option tftp-server-name "{tftp_server}";', config)
        self.assertIn(f'option bootfile-name "{bootfile_name}";', config)
        self.assertIn(f'filename "{bootfile_name}";', config)
        self.assertIn(f'next-server {bootfile_server};', config)
        self.assertIn(f'default-lease-time 86400;', config)
        self.assertIn(f'max-lease-time 86400;', config)
        self.assertIn(f'range {range_0_start} {range_0_stop};', config)
        self.assertIn(f'set shared-networkname = "{shared_net_name}";', config)
        self.assertIn(f'failover peer "{shared_net_name}";', config)
        self.assertIn(f'deny dynamic bootp clients;', config)

        # weird syntax for those static routes
        self.assertIn(f'option rfc3442-static-route 24,10,0,0,192,0,2,1, 0,192,0,2,1;', config)
        self.assertIn(f'option windows-static-route 24,10,0,0,192,0,2,1;', config)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_dhcp_single_pool_static_mapping(self):
        shared_net_name = 'SMOKE-2'

        pool = base_path + ['shared-network-name', shared_net_name, 'subnet', subnet]
        # we use the first subnet IP address as default gateway
        self.session.set(pool + ['default-router', router])
        self.session.set(pool + ['dns-server', dns_1])
        self.session.set(pool + ['dns-server', dns_2])
        self.session.set(pool + ['domain-name', domain_name])

        # check validate() - No DHCP address range or active static-mapping set
        with self.assertRaises(ConfigSessionError):
            self.session.commit()

        client_base = 10
        for client in ['client1', 'client2', 'client3']:
            mac = '00:50:00:00:00:{}'.format(client_base)
            self.session.set(pool + ['static-mapping', client, 'mac-address', mac])
            self.session.set(pool + ['static-mapping', client, 'ip-address', inc_ip(subnet, client_base)])
            client_base += 1

        # commit changes
        self.session.commit()

        config = read_file(DHCPD_CONF)
        network = address_from_cidr(subnet)
        netmask = netmask_from_cidr(subnet)
        self.assertIn(f'ddns-update-style none;', config)
        self.assertIn(f'subnet {network} netmask {netmask}' + r' {', config)
        self.assertIn(f'option domain-name-servers {dns_1}, {dns_2};', config)
        self.assertIn(f'option routers {router};', config)
        self.assertIn(f'option domain-name "{domain_name}";', config)
        self.assertIn(f'default-lease-time 86400;', config)
        self.assertIn(f'max-lease-time 86400;', config)

        client_base = 10
        for client in ['client1', 'client2', 'client3']:
            mac = '00:50:00:00:00:{}'.format(client_base)
            ip = inc_ip(subnet, client_base)
            self.assertIn(f'host {shared_net_name}_{client}' + ' {', config)
            self.assertIn(f'fixed-address {ip};', config)
            self.assertIn(f'hardware ethernet {mac};', config)
            client_base += 1

        self.assertIn(f'set shared-networkname = "{shared_net_name}";', config)

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
            self.session.set(pool + ['default-router', router])
            self.session.set(pool + ['dns-server', dns_1])
            self.session.set(pool + ['domain-name', domain_name])
            self.session.set(pool + ['lease', lease_time])

            self.session.set(pool + ['range', '0', 'start', range_0_start])
            self.session.set(pool + ['range', '0', 'stop', range_0_stop])
            self.session.set(pool + ['range', '1', 'start', range_1_start])
            self.session.set(pool + ['range', '1', 'stop', range_1_stop])

            client_base = 60
            for client in ['client1', 'client2', 'client3', 'client4']:
                mac = '02:50:00:00:00:{}'.format(client_base)
                self.session.set(pool + ['static-mapping', client, 'mac-address', mac])
                self.session.set(pool + ['static-mapping', client, 'ip-address', inc_ip(subnet, client_base)])
                client_base += 1

        # commit changes
        self.session.commit()

        config = read_file(DHCPD_CONF)
        for network in ['0', '1', '2', '3']:
            shared_net_name = f'VyOS-SMOKETEST-{network}'
            subnet = f'192.0.{network}.0/24'
            router = inc_ip(subnet, 1)
            dns_1 = inc_ip(subnet, 2)

            range_0_start = inc_ip(subnet, 10)
            range_0_stop  = inc_ip(subnet, 20)
            range_1_start = inc_ip(subnet, 30)
            range_1_stop  = inc_ip(subnet, 40)

            network = address_from_cidr(subnet)
            netmask = netmask_from_cidr(subnet)

            self.assertIn(f'ddns-update-style none;', config)
            self.assertIn(f'subnet {network} netmask {netmask}' + r' {', config)
            self.assertIn(f'option domain-name-servers {dns_1};', config)
            self.assertIn(f'option routers {router};', config)
            self.assertIn(f'option domain-name "{domain_name}";', config)
            self.assertIn(f'default-lease-time {lease_time};', config)
            self.assertIn(f'max-lease-time {lease_time};', config)
            self.assertIn(f'range {range_0_start} {range_0_stop};', config)
            self.assertIn(f'range {range_1_start} {range_1_stop};', config)
            self.assertIn(f'set shared-networkname = "{shared_net_name}";', config)

            client_base = 60
            for client in ['client1', 'client2', 'client3', 'client4']:
                mac = '02:50:00:00:00:{}'.format(client_base)
                ip = inc_ip(subnet, client_base)
                self.assertIn(f'host {shared_net_name}_{client}' + ' {', config)
                self.assertIn(f'fixed-address {ip};', config)
                self.assertIn(f'hardware ethernet {mac};', config)
                client_base += 1

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_dhcp_exclude_not_in_range(self):
        # T3180: verify else path when slicing DHCP ranges and exclude address
        # is not part of the DHCP range
        range_0_start = inc_ip(subnet, 10)
        range_0_stop  = inc_ip(subnet, 20)

        pool = base_path + ['shared-network-name', 'EXCLUDE-TEST', 'subnet', subnet]
        self.session.set(pool + ['default-router', router])
        self.session.set(pool + ['exclude', router])
        self.session.set(pool + ['range', '0', 'start', range_0_start])
        self.session.set(pool + ['range', '0', 'stop', range_0_stop])

        # commit changes
        self.session.commit()

        # VErify
        config = read_file(DHCPD_CONF)
        network = address_from_cidr(subnet)
        netmask = netmask_from_cidr(subnet)

        self.assertIn(f'subnet {network} netmask {netmask}' + r' {', config)
        self.assertIn(f'option routers {router};', config)
        self.assertIn(f'range {range_0_start} {range_0_stop};', config)

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
        self.session.set(pool + ['default-router', router])
        self.session.set(pool + ['exclude', exclude_addr])
        self.session.set(pool + ['range', '0', 'start', range_0_start])
        self.session.set(pool + ['range', '0', 'stop', range_0_stop])

        # commit changes
        self.session.commit()

        # VErify
        config = read_file(DHCPD_CONF)
        network = address_from_cidr(subnet)
        netmask = netmask_from_cidr(subnet)

        self.assertIn(f'subnet {network} netmask {netmask}' + r' {', config)
        self.assertIn(f'option routers {router};', config)
        self.assertIn(f'range {range_0_start} {range_0_stop_excl};', config)
        self.assertIn(f'range {range_0_start_excl} {range_0_stop};', config)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

if __name__ == '__main__':
    unittest.main(verbosity=2)
