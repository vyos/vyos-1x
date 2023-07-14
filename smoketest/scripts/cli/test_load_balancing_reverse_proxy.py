#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
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
from vyos.utils.process import process_named_running
from vyos.utils.file import read_file

PROCESS_NAME = 'haproxy'
HAPROXY_CONF = '/run/haproxy/haproxy.cfg'
base_path = ['load-balancing', 'reverse-proxy']
proxy_interface = 'eth1'


class TestLoadBalancingReverseProxy(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

        self.cli_delete(['interfaces', 'ethernet', proxy_interface, 'address'])
        self.cli_delete(base_path)
        self.cli_commit()

        # Process must be terminated after deleting the config
        self.assertFalse(process_named_running(PROCESS_NAME))

    def test_01_lb_reverse_proxy_domain(self):
        domains_bk_first = ['n1.example.com', 'n2.example.com', 'n3.example.com']
        domain_bk_second = 'n5.example.com'
        frontend = 'https_front'
        front_port = '4433'
        bk_server_first = '192.0.2.11'
        bk_server_second = '192.0.2.12'
        bk_first_name = 'bk-01'
        bk_second_name = 'bk-02'
        bk_server_port = '9090'
        mode = 'http'
        rule_ten = '10'
        rule_twenty = '20'
        send_proxy = 'send-proxy'
        max_connections = '1000'

        back_base = base_path + ['backend']

        self.cli_set(base_path + ['service', frontend, 'mode', mode])
        self.cli_set(base_path + ['service', frontend, 'port', front_port])
        for domain in domains_bk_first:
            self.cli_set(base_path + ['service', frontend, 'rule', rule_ten, 'domain-name', domain])
        self.cli_set(base_path + ['service', frontend, 'rule', rule_ten, 'set', 'backend', bk_first_name])
        self.cli_set(base_path + ['service', frontend, 'rule', rule_twenty, 'domain-name', domain_bk_second])
        self.cli_set(base_path + ['service', frontend, 'rule', rule_twenty, 'set', 'backend', bk_second_name])

        self.cli_set(back_base + [bk_first_name, 'mode', mode])
        self.cli_set(back_base + [bk_first_name, 'server', bk_first_name, 'address', bk_server_first])
        self.cli_set(back_base + [bk_first_name, 'server', bk_first_name, 'port', bk_server_port])
        self.cli_set(back_base + [bk_first_name, 'server', bk_first_name, send_proxy])

        self.cli_set(back_base + [bk_second_name, 'mode', mode])
        self.cli_set(back_base + [bk_second_name, 'server', bk_second_name, 'address', bk_server_second])
        self.cli_set(back_base + [bk_second_name, 'server', bk_second_name, 'port', bk_server_port])

        self.cli_set(base_path + ['global-parameters', 'max-connections', max_connections])

        # commit changes
        self.cli_commit()

        config = read_file(HAPROXY_CONF)

        # Global
        self.assertIn(f'maxconn {max_connections}', config)

        # Frontend
        self.assertIn(f'frontend {frontend}', config)
        self.assertIn(f'bind :::{front_port} v4v6', config)
        self.assertIn(f'mode {mode}', config)
        for domain in domains_bk_first:
            self.assertIn(f'acl {rule_ten} hdr(host) -i {domain}', config)
        self.assertIn(f'use_backend {bk_first_name} if {rule_ten}', config)
        self.assertIn(f'acl {rule_twenty} hdr(host) -i {domain_bk_second}', config)
        self.assertIn(f'use_backend {bk_second_name} if {rule_twenty}', config)

        # Backend
        self.assertIn(f'backend {bk_first_name}', config)
        self.assertIn(f'balance roundrobin', config)
        self.assertIn(f'option forwardfor', config)
        self.assertIn('http-request add-header X-Forwarded-Proto https if { ssl_fc }', config)
        self.assertIn(f'mode {mode}', config)
        self.assertIn(f'server {bk_first_name} {bk_server_first}:{bk_server_port} send-proxy', config)

        self.assertIn(f'backend {bk_second_name}', config)
        self.assertIn(f'mode {mode}', config)
        self.assertIn(f'server {bk_second_name} {bk_server_second}:{bk_server_port}', config)


if __name__ == '__main__':
    unittest.main(verbosity=2)
