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

from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError
from vyos.util import cmd
from vyos.util import dict_search

base_path = ['load-balancing', 'inbound', 'ipvsadm']
virtual_ip = '127.0.0.1'
virtual_ip6 = 'fc00::1'

class TestLoadBalancingInbound(unittest.TestCase):
    def setUp(self):
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        self.session = ConfigSession(os.getpid())
        self.session.delete(base_path)

    def tearDown(self):
        self.session.delete(base_path)
        self.session.commit()
    
    def test_load_balancing_inbound_base_rule(self):
        rule = 0
        backend_ip = '127.0.0.2'
        backend_ip6 = 'fc00::2'
        backend_port = 18032
        virtual_port = 8080
        backend_id = 0
        for protocol in ['tcp', 'udp', 'sctp']:
            for mode in ['dr', 'tun', 'nat']:
                for ip in [4, 6]:
                    rule += 1
                    backend_port +=1 
                    virtual_port +=1
                    if ip == 6:
                        self.session.set(base_path + ['rule', str(rule), 'virtual-ip', virtual_ip6])
                        self.session.set(base_path + ['rule', str(rule), 'backend', str(backend_id), 'backend-ip', backend_ip6])
                    elif ip == 4:
                        self.session.set(base_path + ['rule', str(rule), 'virtual-ip', virtual_ip])
                        self.session.set(base_path + ['rule', str(rule), 'backend', str(backend_id), 'backend-ip', backend_ip])
                    self.session.set(base_path + ['rule', str(rule), 'virtual-port', str(virtual_port)])
                    self.session.set(base_path + ['rule', str(rule), 'mode', mode])
                    self.session.set(base_path + ['rule', str(rule), 'protocol', protocol])
        self.session.commit()
    
    def test_load_balancing_inbound_no_backend(self):
        rule = 0
        virtual_port = 8080
        for protocol in ['tcp', 'udp', 'sctp']:
            for mode in ['dr', 'tun', 'nat']:
                for ip in [4, 6]:
                    rule += 1
                    virtual_port += 1
                    if ip == 6:
                        self.session.set(base_path + ['rule', str(rule), 'virtual-ip', virtual_ip6])
                    elif ip == 4:
                        self.session.set(base_path + ['rule', str(rule), 'virtual-ip', virtual_ip])
                    self.session.set(base_path + ['rule', str(rule), 'virtual-port', str(virtual_port)])
                    self.session.set(base_path + ['rule', str(rule), 'mode', mode])
                    self.session.set(base_path + ['rule', str(rule), 'protocol', protocol])
        self.session.commit()
    
    def test_load_balancing_inbound_no_rule(self):
        self.session.set(base_path)
        self.session.commit()

if __name__ == '__main__':
    unittest.main(verbosity=2)
