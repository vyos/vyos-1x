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

import os
import jmespath
import json
import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.util import read_file
from vyos.template import is_ipv6

base_path = ['load-balancing', 'inbound', 'ipvsadm']
virtual_ip = '127.0.0.1'
virtual_ip6 = 'fc00::1'
IPVSADM_CONF = '/tmp/ipvsadm.rules'

class TestLoadBalancingInboundIPvsAdm(VyOSUnitTestSHIM.TestCase):
    def setUp(self):
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        self.cli_delete(base_path)

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()
    
    def test_load_balancing_inbound_duplicate_virtual_service_rule(self):
        rule = 0
        backend_port = 18032
        virtual_port = 8080
        backend_id = 0
        for protocol in ['tcp', 'udp', 'sctp']:
            for mode in ['direct', 'tunnel', 'nat']:
                for ip in [virtual_ip, virtual_ip6]:
                    rule += 1
                    backend_port +=1 
                    backend_id += 1
                    self.cli_set(base_path + ['rule', str(rule), 'virtual-address', ip])
                    self.cli_set(base_path + ['rule', str(rule), 'port', str(virtual_port)])
                    self.cli_set(base_path + ['rule', str(rule), 'algorithm', 'rr'])
                    self.cli_set(base_path + ['rule', str(rule), 'mode', mode])
                    self.cli_set(base_path + ['rule', str(rule), 'protocol', protocol])
        
        # configuration error exception was thrown: Configuration error in rule 2: Do not allow duplicate virtual servers!
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
    
    def test_load_balancing_inbound_no_virtual_service_rule(self):
        rule = 0
        backend_port = 18032
        backend_id = 0
        for protocol in ['tcp', 'udp', 'sctp']:
            for mode in ['direct', 'tunnel', 'nat']:
                rule += 1
                backend_port +=1 
                backend_id += 1
                self.cli_set(base_path + ['rule', str(rule), 'algorithm', 'rr'])
                self.cli_set(base_path + ['rule', str(rule), 'mode', mode])
                self.cli_set(base_path + ['rule', str(rule), 'protocol', protocol])
        
        # configuration error exception was thrown: Configuration error in rule 1: The virtual server IP and port must exist!
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
    
    def test_load_balancing_inbound_diff_address_family_rule(self):
        rule = 0
        backend_port = 18032
        virtual_port = 8080
        backend_id = 0
        for protocol in ['tcp', 'udp', 'sctp']:
            for mode in ['direct', 'tunnel', 'nat']:
                for ip in [virtual_ip, virtual_ip6]:
                    rule += 1
                    backend_port +=1 
                    backend_id += 1
                    self.cli_set(base_path + ['rule', str(rule), 'virtual-address', ip])
                    if is_ipv6(ip):
                        self.cli_set(base_path + ['rule', str(rule), 'backend', f'127.{backend_id}.0.2'])
                    else:
                        self.cli_set(base_path + ['rule', str(rule), 'backend', f'fc00:{backend_id}::2'])
                    self.cli_set(base_path + ['rule', str(rule), 'port', str(virtual_port)])
                    self.cli_set(base_path + ['rule', str(rule), 'algorithm', 'rr'])
                    self.cli_set(base_path + ['rule', str(rule), 'mode', mode])
                    self.cli_set(base_path + ['rule', str(rule), 'protocol', protocol])
        
        # configuration error exception was thrown: Configuration error in rule 1: The back-end server with IP 127.0.0.1 and the virtual server with IP fc00:1::2 have different address families!
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
    
    def test_load_balancing_inbound_no_mode_algorithm_rule(self):
        rule = 0
        backend_port = 18032
        virtual_port = 8080
        backend_id = 0
        for protocol in ['tcp', 'udp', 'sctp']:
            for mode in ['direct', 'tunnel', 'nat']:
                for ip in [virtual_ip, virtual_ip6]:
                    rule += 1
                    backend_port +=1 
                    backend_id += 1
                    self.cli_set(base_path + ['rule', str(rule), 'virtual-address', ip])
                    if is_ipv6(ip):
                        self.cli_set(base_path + ['rule', str(rule), 'backend', f'127.{backend_id}.0.2'])
                    else:
                        self.cli_set(base_path + ['rule', str(rule), 'backend', f'fc00:{backend_id}::2'])
                    self.cli_set(base_path + ['rule', str(rule), 'port', str(virtual_port)])
                    self.cli_set(base_path + ['rule', str(rule), 'protocol', protocol])
        
        # configuration error exception was thrown: Configuration error in rule 1: mode and algorithm must be configured!
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
    
    def test_load_balancing_inbound_base_rule(self):
        rule = 0
        backend_port = 18032
        virtual_port = 8080
        backend_id = 0
        for protocol in ['tcp', 'udp', 'sctp']:
            for mode in ['direct', 'tunnel', 'nat']:
                for ip in [virtual_ip, virtual_ip6]:
                    rule += 1
                    backend_port +=1 
                    virtual_port +=1
                    backend_id += 1
                    self.cli_set(base_path + ['rule', str(rule), 'virtual-address', ip])
                    if is_ipv6(ip):
                        self.cli_set(base_path + ['rule', str(rule), 'backend', f'fc00:{backend_id}::2'])
                    else:
                        self.cli_set(base_path + ['rule', str(rule), 'backend', f'127.{backend_id}.0.2'])
                    self.cli_set(base_path + ['rule', str(rule), 'port', str(virtual_port)])
                    self.cli_set(base_path + ['rule', str(rule), 'algorithm', 'rr'])
                    self.cli_set(base_path + ['rule', str(rule), 'mode', mode])
                    self.cli_set(base_path + ['rule', str(rule), 'protocol', protocol])
        self.cli_commit()
        
        # Check configured port
        config = read_file(IPVSADM_CONF)
        
        backend_port = 18032
        virtual_port = 8080
        backend_id = 0
        for protocol in ['tcp', 'udp', 'sctp']:
            for mode in ['direct', 'tunnel', 'nat']:
                for ip in [virtual_ip, virtual_ip6]:
                    backend_port +=1 
                    virtual_port +=1
                    backend_id += 1
                    if is_ipv6(ip):
                        self.assertIn(f'{virtual_ip6}', config)
                        self.assertIn(f'fc00:{backend_id}::2', config)
                    else:
                        self.assertIn(f'{virtual_ip}', config)
                        self.assertIn(f'127.{backend_id}.0.2', config)
                    self.assertIn(str(virtual_port), config)
                    
                    if mode == 'direct':
                        self.assertIn('-g', config)
                    elif mode == 'tunnel':
                        self.assertIn('-i', config)
                    elif mode == 'nat':
                        self.assertIn('-m', config)
                    
                    if protocol == 'tcp':
                        self.assertIn('-t', config)
                    elif protocol == 'udp':
                        self.assertIn('-u', config)
                    elif protocol == 'sctp':
                        self.assertIn('--sctp-service', config)
    
    def test_load_balancing_inbound_no_backend(self):
        rule = 0
        virtual_port = 8080
        for protocol in ['tcp', 'udp', 'sctp']:
            for mode in ['direct', 'tunnel', 'nat']:
                for ip in [virtual_ip, virtual_ip6]:
                    rule += 1
                    virtual_port += 1
                    self.cli_set(base_path + ['rule', str(rule), 'virtual-address', ip])
                    self.cli_set(base_path + ['rule', str(rule), 'port', str(virtual_port)])
                    self.cli_set(base_path + ['rule', str(rule), 'algorithm', 'rr'])
                    self.cli_set(base_path + ['rule', str(rule), 'mode', mode])
                    self.cli_set(base_path + ['rule', str(rule), 'protocol', protocol])
        self.cli_commit()
        
        # Check configured port
        config = read_file(IPVSADM_CONF)
        
        virtual_port = 8080
        for protocol in ['tcp', 'udp', 'sctp']:
            for mode in ['direct', 'tunnel', 'nat']:
                for ip in [virtual_ip, virtual_ip6]:
                    virtual_port += 1
                    
                    if is_ipv6(ip):
                        self.assertIn(f'{virtual_ip6}', config)
                    else:
                        self.assertIn(f'{virtual_ip}', config)
                    self.assertIn(str(virtual_port), config)
                    
                    if protocol == 'tcp':
                        self.assertIn('-t', config)
                    elif protocol == 'udp':
                        self.assertIn('-u', config)
                    elif protocol == 'sctp':
                        self.assertIn('--sctp-service', config)
    
    def test_load_balancing_inbound_no_rule(self):
        # There is no need for any more validation here, because it only ensures that the configuration can work normally when no rules are set
        self.cli_set(base_path)
        self.cli_commit()

if __name__ == '__main__':
    unittest.main(verbosity=2)
