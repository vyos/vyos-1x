#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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
from base_vyostest_shim import CSTORE_GUARD_TIME

from vyos.ifconfig import Section
from vyos.frrender import babel_daemon
from vyos.utils.process import process_named_running
from vyos.xml_ref import default_value

base_path = ['protocols', 'babel']

class TestProtocolsBABEL(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._interfaces = Section.interfaces('ethernet', vlan=False)
        # call base-classes classmethod
        super(TestProtocolsBABEL, cls).setUpClass()
        # Retrieve FRR daemon PID - it is not allowed to crash, thus PID must remain the same
        cls.daemon_pid = process_named_running(babel_daemon)
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)
        cls.cli_delete(cls, ['policy', 'prefix-list'])
        cls.cli_delete(cls, ['policy', 'prefix-list6'])
        # Enable CSTORE guard time required by FRR related tests
        cls._commit_guard_time = CSTORE_GUARD_TIME

    def tearDown(self):
        # always destroy the entire babel configuration to make the processes
        # life as hard as possible
        self.cli_delete(base_path)
        self.cli_delete(['policy', 'prefix-list'])
        self.cli_delete(['policy', 'prefix-list6'])
        self.cli_commit()

        # check process health and continuity
        self.assertEqual(self.daemon_pid, process_named_running(babel_daemon))

    def test_01_basic(self):
        diversity_factor = '64'
        resend_delay = '100'
        smoothing_half_life = '400'

        self.cli_set(base_path + ['parameters', 'diversity'])
        self.cli_set(base_path + ['parameters', 'diversity-factor', diversity_factor])
        self.cli_set(base_path + ['parameters', 'resend-delay', resend_delay])
        self.cli_set(base_path + ['parameters', 'smoothing-half-life', smoothing_half_life])

        self.cli_commit()

        frrconfig = self.getFRRconfig('router babel', endsection='^exit')
        self.assertIn(f' babel diversity', frrconfig)
        self.assertIn(f' babel diversity-factor {diversity_factor}', frrconfig)
        self.assertIn(f' babel resend-delay {resend_delay}', frrconfig)
        self.assertIn(f' babel smoothing-half-life {smoothing_half_life}', frrconfig)

    def test_02_redistribute(self):
        ipv4_protos = ['bgp', 'connected', 'isis', 'kernel', 'nhrp', 'ospf', 'rip', 'static']
        ipv6_protos = ['bgp', 'connected', 'isis', 'kernel', 'ospfv3', 'ripng', 'static']

        self.cli_set(base_path + ['interface', self._interfaces[0], 'enable-timestamps'])

        for protocol in ipv4_protos:
            self.cli_set(base_path + ['redistribute', 'ipv4', protocol])
        for protocol in ipv6_protos:
            self.cli_set(base_path + ['redistribute', 'ipv6', protocol])

        self.cli_commit()

        frrconfig = self.getFRRconfig('router babel', endsection='^exit', empty_retry=5)
        for protocol in ipv4_protos:
            self.assertIn(f' redistribute ipv4 {protocol}', frrconfig)
        for protocol in ipv6_protos:
            if protocol == 'ospfv3':
                protocol = 'ospf6'
            self.assertIn(f' redistribute ipv6 {protocol}', frrconfig)

    def test_03_distribute_list(self):
        access_list_in4 = '40'
        access_list_out4 = '50'
        access_list_in4_iface = '44'
        access_list_out4_iface = '55'
        access_list_in6 = 'AL-foo-in6'
        access_list_out6 = 'AL-foo-out6'

        prefix_list_in4 = 'PL-foo-in4'
        prefix_list_out4 = 'PL-foo-out4'
        prefix_list_in6 = 'PL-foo-in6'
        prefix_list_out6 = 'PL-foo-out6'

        self.cli_set(['policy', 'access-list', access_list_in4])
        self.cli_set(['policy', 'access-list', access_list_out4])
        self.cli_set(['policy', 'access-list6', access_list_in6])
        self.cli_set(['policy', 'access-list6', access_list_out6])

        self.cli_set(['policy', 'access-list', f'{access_list_in4_iface}'])
        self.cli_set(['policy', 'access-list', f'{access_list_out4_iface}'])

        self.cli_set(['policy', 'prefix-list', prefix_list_in4])
        self.cli_set(['policy', 'prefix-list', prefix_list_out4])
        self.cli_set(['policy', 'prefix-list6', prefix_list_in6])
        self.cli_set(['policy', 'prefix-list6', prefix_list_out6])

        self.cli_set(base_path + ['distribute-list', 'ipv4', 'access-list', 'in', access_list_in4])
        self.cli_set(base_path + ['distribute-list', 'ipv4', 'access-list', 'out', access_list_out4])
        self.cli_set(base_path + ['distribute-list', 'ipv6', 'access-list', 'in', access_list_in6])
        self.cli_set(base_path + ['distribute-list', 'ipv6', 'access-list', 'out', access_list_out6])

        self.cli_set(base_path + ['distribute-list', 'ipv4', 'prefix-list', 'in', prefix_list_in4])
        self.cli_set(base_path + ['distribute-list', 'ipv4', 'prefix-list', 'out', prefix_list_out4])
        self.cli_set(base_path + ['distribute-list', 'ipv6', 'prefix-list', 'in', prefix_list_in6])
        self.cli_set(base_path + ['distribute-list', 'ipv6', 'prefix-list', 'out', prefix_list_out6])

        for interface in self._interfaces:
            self.cli_set(base_path + ['interface', interface])

            self.cli_set(['policy', 'access-list6', f'{access_list_in6}-{interface}'])
            self.cli_set(['policy', 'access-list6', f'{access_list_out6}-{interface}'])

            self.cli_set(['policy', 'prefix-list', f'{prefix_list_in4}-{interface}'])
            self.cli_set(['policy', 'prefix-list', f'{prefix_list_out4}-{interface}'])
            self.cli_set(['policy', 'prefix-list6', f'{prefix_list_in6}-{interface}'])
            self.cli_set(['policy', 'prefix-list6', f'{prefix_list_out6}-{interface}'])

            tmp_path = base_path + ['distribute-list', 'ipv4', 'interface', interface]
            self.cli_set(tmp_path + ['access-list', 'in', f'{access_list_in4_iface}'])
            self.cli_set(tmp_path + ['access-list', 'out', f'{access_list_out4_iface}'])
            self.cli_set(tmp_path + ['prefix-list', 'in', f'{prefix_list_in4}-{interface}'])
            self.cli_set(tmp_path + ['prefix-list', 'out', f'{prefix_list_out4}-{interface}'])

            tmp_path = base_path + ['distribute-list', 'ipv6', 'interface', interface]
            self.cli_set(tmp_path + ['access-list', 'in', f'{access_list_in6}-{interface}'])
            self.cli_set(tmp_path + ['access-list', 'out', f'{access_list_out6}-{interface}'])
            self.cli_set(tmp_path + ['prefix-list', 'in', f'{prefix_list_in6}-{interface}'])
            self.cli_set(tmp_path + ['prefix-list', 'out', f'{prefix_list_out6}-{interface}'])

        self.cli_commit()

        frrconfig = self.getFRRconfig('router babel', endsection='^exit')
        self.assertIn(f' distribute-list {access_list_in4} in', frrconfig)
        self.assertIn(f' distribute-list {access_list_out4} out', frrconfig)
        self.assertIn(f' ipv6 distribute-list {access_list_in6} in', frrconfig)
        self.assertIn(f' ipv6 distribute-list {access_list_out6} out', frrconfig)

        self.assertIn(f' distribute-list prefix {prefix_list_in4} in', frrconfig)
        self.assertIn(f' distribute-list prefix {prefix_list_out4} out', frrconfig)
        self.assertIn(f' ipv6 distribute-list prefix {prefix_list_in6} in', frrconfig)
        self.assertIn(f' ipv6 distribute-list prefix {prefix_list_out6} out', frrconfig)

        for interface in self._interfaces:
            self.assertIn(f' distribute-list {access_list_in4_iface} in {interface}', frrconfig)
            self.assertIn(f' distribute-list {access_list_out4_iface} out {interface}', frrconfig)
            self.assertIn(f' ipv6 distribute-list {access_list_in6}-{interface} in {interface}', frrconfig)
            self.assertIn(f' ipv6 distribute-list {access_list_out6}-{interface} out {interface}', frrconfig)

            self.assertIn(f' distribute-list prefix {prefix_list_in4}-{interface} in {interface}', frrconfig)
            self.assertIn(f' distribute-list prefix {prefix_list_out4}-{interface} out {interface}', frrconfig)
            self.assertIn(f' ipv6 distribute-list prefix {prefix_list_in6}-{interface} in {interface}', frrconfig)
            self.assertIn(f' ipv6 distribute-list prefix {prefix_list_out6}-{interface} out {interface}', frrconfig)

    def test_04_interfaces(self):
        def_update_interval = default_value(base_path + ['interface', 'eth0', 'update-interval'])
        channel = '20'
        hello_interval = '1000'
        max_rtt_penalty = '100'
        rtt_decay = '23'
        rtt_max = '119'
        rtt_min = '11'
        rxcost = '40000'
        type = 'wired'

        for interface in self._interfaces:
            self.cli_set(base_path + ['interface', interface])
            self.cli_set(base_path + ['interface', interface, 'channel', channel])
            self.cli_set(base_path + ['interface', interface, 'enable-timestamps'])
            self.cli_set(base_path + ['interface', interface, 'hello-interval', hello_interval])
            self.cli_set(base_path + ['interface', interface, 'max-rtt-penalty', max_rtt_penalty])
            self.cli_set(base_path + ['interface', interface, 'rtt-decay', rtt_decay])
            self.cli_set(base_path + ['interface', interface, 'rtt-max', rtt_max])
            self.cli_set(base_path + ['interface', interface, 'rtt-min', rtt_min])
            self.cli_set(base_path + ['interface', interface, 'rxcost', rxcost])
            self.cli_set(base_path + ['interface', interface, 'split-horizon', 'disable'])
            self.cli_set(base_path + ['interface', interface, 'type', type])

        self.cli_commit()

        frrconfig = self.getFRRconfig('router babel', endsection='^exit')
        for interface in self._interfaces:
            self.assertIn(f' network {interface}', frrconfig)

            iface_config = self.getFRRconfig(f'interface {interface}', endsection='^exit')
            self.assertIn(f' babel channel {channel}', iface_config)
            self.assertIn(f' babel enable-timestamps', iface_config)
            self.assertIn(f' babel update-interval {def_update_interval}', iface_config)
            self.assertIn(f' babel hello-interval {hello_interval}', iface_config)
            self.assertIn(f' babel rtt-decay {rtt_decay}', iface_config)
            self.assertIn(f' babel rtt-max {rtt_max}', iface_config)
            self.assertIn(f' babel rtt-min {rtt_min}', iface_config)
            self.assertIn(f' babel rxcost {rxcost}', iface_config)
            self.assertIn(f' babel max-rtt-penalty {max_rtt_penalty}', iface_config)
            self.assertIn(f' no babel split-horizon', iface_config)
            self.assertIn(f' babel {type}', iface_config)

if __name__ == '__main__':
    unittest.main(verbosity=2)
