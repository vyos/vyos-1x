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

from base_interfaces_test import *

from vyos.ifconfig import Interface


class TunnelInterfaceTest(BasicInterfaceTest.BaseTest):
    _base_path = ['interfaces', 'tunnel']
    _interfaces = []

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

    remote = {
        4: '192.0.{}.1',
        6: '2002::{}:1',
    }

    addrs = {
        4: '10.100.{}.1/24',
        6:  '2001:db8:{}::1/64',
    }

    def setUp(self):
        for number in range(len(self._valid)):
            self._interfaces.append('tun%d' % (number+1))
        self._test_mtu = True
        super().setUp()

        self.session.set(['interfaces', 'dummy', 'dum444',
                          'address', '169.254.0.1/24'])
        self.session.set(
            ['interfaces', 'dummy', 'dum666', 'address', '2002::1/16'])
        self.session.commit()

        local = {
            4: Interface('dum444').get_addr()[0].split('/')[0],
            6: Interface('dum666').get_addr()[0].split('/')[0],
        }

        number = 1
        for encap, p2p, addr in self._valid:
            intf = 'tun%d' % number
            tunnel = {}
            tunnel['encapsulation'] = encap
            tunnel['local-ip'] = local[p2p].format(number)
            tunnel['remote-ip'] = self.remote[p2p].format(number)
            tunnel['address'] = self.addrs[addr].format(number)
            for name in tunnel:
                self.session.set(self._base_path + [intf, name, tunnel[name]])
            number += 1


if __name__ == '__main__':
    unittest.main()
