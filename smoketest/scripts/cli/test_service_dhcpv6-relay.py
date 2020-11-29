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
from vyos.ifconfig import Section
from vyos.template import address_from_cidr
from vyos.util import cmd
from vyos.util import process_named_running
from vyos.util import read_file

PROCESS_NAME = 'dhcrelay'
RELAY_CONF = '/run/dhcp-relay/dhcpv6.conf'
base_path = ['service', 'dhcpv6-relay']

upstream_if = 'eth0'
upstream_if_addr = '2001:db8::1/64'
listen_addr = '2001:db8:ffff::1/64'
interfaces = []

class TestServiceDHCPv6Relay(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())
        for tmp in interfaces:
            listen = listen_addr
            if tmp == upstream_if:
                listen = upstream_if_addr
            self.session.set(['interfaces', 'ethernet', tmp, 'address', listen])

    def tearDown(self):
        self.session.delete(base_path)
        for tmp in interfaces:
            listen = listen_addr
            if tmp == upstream_if:
                listen = upstream_if_addr
            self.session.delete(['interfaces', 'ethernet', tmp, 'address', listen])

        self.session.commit()
        del self.session

    def test_relay_default(self):
        dhcpv6_server = '2001:db8::ffff'
        hop_count = '20'

        self.session.set(base_path + ['use-interface-id-option'])
        self.session.set(base_path + ['max-hop-count', hop_count])

        # check validate() - Must set at least one listen and upstream
        # interface addresses.
        with self.assertRaises(ConfigSessionError):
            self.session.commit()
        self.session.set(base_path + ['upstream-interface', upstream_if, 'address', dhcpv6_server])

        # check validate() - Must set at least one listen and upstream
        # interface addresses.
        with self.assertRaises(ConfigSessionError):
            self.session.commit()

        # add listener on all ethernet interfaces except the upstream interface
        for tmp in interfaces:
            if tmp == upstream_if:
                continue
            self.session.set(base_path + ['listen-interface', tmp, 'address', listen_addr.split('/')[0]])

        # commit changes
        self.session.commit()

        # Check configured port
        config = read_file(RELAY_CONF)

        # Test configured upstream interfaces
        self.assertIn(f'-u {dhcpv6_server}%{upstream_if}', config)

        # Check listener on all ethernet interfaces
        for tmp in interfaces:
            if tmp == upstream_if:
                continue
            addr = listen_addr.split('/')[0]
            self.assertIn(f'-l {addr}%{tmp}', config)

        # Check hop count
        self.assertIn(f'-c {hop_count}', config)
        # Check Interface ID option
        self.assertIn('-I', config)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

if __name__ == '__main__':
    for tmp in Section.interfaces('ethernet'):
        if '.' not in tmp:
            interfaces.append(tmp)

    unittest.main()

