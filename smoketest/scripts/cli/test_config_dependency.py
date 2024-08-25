#!/usr/bin/env python3
# Copyright 2024 VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>.


import unittest
from time import sleep

from vyos.utils.process import is_systemd_service_running
from vyos.utils.process import cmd
from vyos.configsession import ConfigSessionError

from base_vyostest_shim import VyOSUnitTestSHIM


class TestConfigDep(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        # smoketests are run without configd in 1.4; with configd in 1.5
        # the tests below check behavior under configd:
        # test_configdep_error checks for regression under configd (T6559)
        # test_configdep_prio_queue checks resolution under configd (T6671)
        cls.running_state = is_systemd_service_running('vyos-configd.service')

        if not cls.running_state:
            cmd('sudo systemctl start vyos-configd.service')
            # allow time for init
            sleep(1)

        super(TestConfigDep, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        super(TestConfigDep, cls).tearDownClass()

        # return to running_state
        if not cls.running_state:
            cmd('sudo systemctl stop vyos-configd.service')

    def test_configdep_error(self):
        address_group = 'AG'
        address = '192.168.137.5'
        nat_base = ['nat', 'source', 'rule', '10']
        interface = 'eth1'

        self.cli_set(['firewall', 'group', 'address-group', address_group,
                      'address', address])
        self.cli_set(nat_base + ['outbound-interface', 'name', interface])
        self.cli_set(nat_base + ['source', 'group', 'address-group', address_group])
        self.cli_set(nat_base + ['translation', 'address', 'masquerade'])
        self.cli_commit()

        self.cli_delete(['firewall'])
        # check error in call to dependent script (nat)
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        # clean up remaining
        self.cli_delete(['nat'])
        self.cli_commit()

    def test_configdep_prio_queue(self):
        # confirm that that a dependency (in this case, conntrack ->
        # conntrack-sync) is not immediately called if the target is
        # scheduled in the priority queue, indicating that it may require an
        # intermediate activitation (bond0)
        bonding_base = ['interfaces', 'bonding']
        bond_interface = 'bond0'
        bond_address = '192.0.2.1/24'
        vrrp_group_base = ['high-availability', 'vrrp', 'group']
        vrrp_sync_group_base = ['high-availability', 'vrrp', 'sync-group']
        vrrp_group = 'ETH2'
        vrrp_sync_group = 'GROUP'
        conntrack_sync_base = ['service', 'conntrack-sync']
        conntrack_peer = '192.0.2.77'

        # simple set to trigger in-session conntrack -> conntrack-sync
        # dependency; note that this is triggered on boot in 1.4 due to
        # default 'system conntrack modules'
        self.cli_set(['system', 'conntrack', 'table-size', '524288'])

        self.cli_set(['interfaces', 'ethernet', 'eth2', 'address',
                      '198.51.100.2/24'])

        self.cli_set(bonding_base + [bond_interface, 'address',
                                     bond_address])
        self.cli_set(bonding_base + [bond_interface, 'member', 'interface',
                                     'eth3'])

        self.cli_set(vrrp_group_base + [vrrp_group, 'address',
                                        '198.51.100.200/24'])
        self.cli_set(vrrp_group_base + [vrrp_group, 'hello-source-address',
                                        '198.51.100.2'])
        self.cli_set(vrrp_group_base + [vrrp_group, 'interface', 'eth2'])
        self.cli_set(vrrp_group_base + [vrrp_group, 'priority', '200'])
        self.cli_set(vrrp_group_base + [vrrp_group, 'vrid', '22'])
        self.cli_set(vrrp_sync_group_base + [vrrp_sync_group, 'member',
                                             vrrp_group])

        self.cli_set(conntrack_sync_base + ['failover-mechanism', 'vrrp',
                                            'sync-group', vrrp_sync_group])

        self.cli_set(conntrack_sync_base + ['interface', bond_interface,
                                            'peer', conntrack_peer])

        self.cli_commit()

        # clean up
        self.cli_delete(bonding_base)
        self.cli_delete(vrrp_group_base)
        self.cli_delete(vrrp_sync_group_base)
        self.cli_delete(conntrack_sync_base)
        self.cli_delete(['interfaces', 'ethernet', 'eth2', 'address'])
        self.cli_delete(['system', 'conntrack', 'table-size'])
        self.cli_commit()

if __name__ == '__main__':
    unittest.main(verbosity=2)
