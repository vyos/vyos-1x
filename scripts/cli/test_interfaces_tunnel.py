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
import unittest

from vyos.configsession import ConfigSession

from base_interfaces_test import BasicInterfaceTest

class TunnelInterfaceTest(BasicInterfaceTest.BaseTest):
    # encoding, tunnel endpoint (v4/v6), address (v4/v6)
    _valid = [
        ('gre', 4, 4),
        ('gre', 4, 6),
        ('ip6gre', 6, 4),
        ('ip6gre', 6, 6),
        ('gre-bridge', 4, 4),
        ('ipip', 4, 4),
        ('ipip', 4, 6),
        ('ipip6', 6, 4),
        ('ipip6', 6, 6),
        ('ip6ip6', 6, 6),
        ('sit', 4, 6),
    ]

    local = {
        4: '10.100.{}.1/24',
        6:  '2001:db8:{}::1/64',
    }

    remote = {
        4: '192.0.{}.1',
        6: '2002::{}:1',
    }

    address = {
        4: '10.100.{}.1/24',
        6:  '2001:db8:{}::1/64',
    }

    def setUp(self):
        local = {}
        remote = {}
        address = {}

        self._intf_dummy = ['interfaces', 'dummy']
        self._base_path = ['interfaces', 'tunnel']
        self._interfaces = ['tun{}'.format(n) for n in range(len(self._valid))]

        self._test_mtu = True
        super().setUp()

        for number in range(len(self._valid)):
            dum4 = 'dum4{}'.format(number)
            dum6 = 'dum6{}'.format(number)

            ipv4 = self.local[4].format(number)
            ipv6 = self.local[6].format(number)

            local.setdefault(4, {})[number] = ipv4
            local.setdefault(6, {})[number] = ipv6

            ipv4 = self.remote[4].format(number)
            ipv6 = self.remote[6].format(number)

            remote.setdefault(4, {})[number] = ipv4
            remote.setdefault(6, {})[number] = ipv6

            ipv4 = self.address[4].format(number)
            ipv6 = self.address[6].format(number)

            address.setdefault(4, {})[number] = ipv4
            address.setdefault(6, {})[number] = ipv6

            self.session.set(self._intf_dummy + [dum4, 'address', ipv4])
            self.session.set(self._intf_dummy + [dum6, 'address', ipv6])
        self.session.commit()

        for number, (encap, p2p, addr) in enumerate(self._valid):
            intf = 'tun%d' % number
            tunnel = {}
            tunnel['encapsulation'] = encap
            tunnel['local-ip'] = local[p2p][number].split('/')[0]
            tunnel['remote-ip'] = remote[p2p][number].split('/')[0]
            tunnel['address'] = address[addr][number]
            for name in tunnel:
                self.session.set(self._base_path + [intf, name, tunnel[name]])

    def tearDown(self):
        self.session.delete(self._intf_dummy)
        super().tearDown()


if __name__ == '__main__':
    unittest.main()
