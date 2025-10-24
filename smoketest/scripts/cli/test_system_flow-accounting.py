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

from vyos.configsession import ConfigSessionError
from vyos.ifconfig import Section
from vyos.utils.kernel import is_module_loaded
from vyos.utils.kernel import get_module_data
from vyos.utils.process import cmd

module_name = 'ipt_NETFLOW'
base_path = ['system', 'flow-accounting']


class TestSystemFlowAccounting(VyOSUnitTestSHIM.TestCase):

    def _get_iptables_watched_interfaces(self, command, table, chain, column_name):
        iptables_command = f'{command} -vn -t {table} -L {chain}'
        data = cmd(iptables_command, message='Failed to get flows list')
        data = data.splitlines()
        self.assertGreaterEqual(
            len(data), 2, "Unexpected output of {command}, should be at least two lines"
        )
        column_index = data[1].split().index(column_name)
        interfaces = [
            line.split()[column_index] for line in data[2:] if 'NETFLOW' in line
        ]
        return interfaces

    def _get_iptables_watched_ingress_interfaces(self, command):
        return self._get_iptables_watched_interfaces(command, 'raw', 'PREROUTING', 'in')

    def _get_iptables_watched_egress_interfaces(self, command):
        return self._get_iptables_watched_interfaces(
            command, 'mangle', 'POSTROUTING', 'out'
        )

    def _assert_ingress_interfaces(self, interfaces):
        for command in 'iptables', 'ip6tables':
            self.assertEqual(
                set(self._get_iptables_watched_ingress_interfaces(command)),
                set(interfaces),
                command,
            )

    def _assert_egress_interfaces(self, interfaces):
        for command in 'iptables', 'ip6tables':
            self.assertEqual(
                set(self._get_iptables_watched_egress_interfaces(command)),
                set(interfaces),
                command,
            )

    @classmethod
    def setUpClass(cls):
        super(TestSystemFlowAccounting, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        # after service removal process must no longer run
        self.assertTrue(is_module_loaded(module_name))

        self.cli_delete(base_path)
        self.cli_commit()

        # after service removal process must no longer run
        self.assertFalse(is_module_loaded(module_name))
        self._assert_ingress_interfaces([])
        self._assert_egress_interfaces([])
        # always forward to base class
        super().tearDown()

    def test_basic(self):
        engine_id = '33'
        self.cli_set(base_path + ['netflow', 'engine-id', engine_id])

        # You need to configure at least one interface for flow-accounting
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        for interface in Section.interfaces('ethernet'):
            self.cli_set(base_path + ['netflow', 'interface', interface])

        # You need to configure at least one NetFlow server
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        netflow_server = '11.22.33.44'
        self.cli_set(base_path + ['netflow', 'server', netflow_server])

        # commit changes, this time should work
        self.cli_commit()

        # verify configuration
        self._assert_ingress_interfaces(Section.interfaces('ethernet'))
        self._assert_egress_interfaces([])

        module_data = get_module_data(module_name)
        self.assertEqual(engine_id, module_data['parameters']['engine_id'])


    def test_netflow(self):
        engine_id = '33'
        max_flows = '667'
        dummy_if = 'dum3842'
        agent_address = '192.0.2.10'
        version = '10'
        active_timeout = '900'
        inactive_timeout = '30'

        source_ipv4_address = '192.0.2.1'
        source_ipv6_address = '2001:db8::ab'
        netflow_server = {
            '11.22.33.44': {},
            '55.66.77.88': {'port': '6000'},
            '100.12.14.1': {'source-interface': dummy_if},
            '203.0.113.21': {'port': '3000', 'source-address': source_ipv4_address},
            '2001:db8::1': {'source-address': source_ipv6_address},
        }
        # ipt_NETFLOW sorts destinations by IP
        expected_destination = '11.22.33.44:2055,55.66.77.88:6000,100.12.14.1:2055%dum3842,203.0.113.21:3000@192.0.2.1,[2001:db8::1]:2055@2001:db8::ab'

        self.cli_set(
            ['interfaces', 'dummy', dummy_if, 'address', agent_address + '/32']
        )
        self.cli_set(
            ['interfaces', 'dummy', dummy_if, 'address', source_ipv4_address + '/32']
        )
        self.cli_set(
            ['interfaces', 'dummy', dummy_if, 'address', source_ipv6_address + '/128']
        )

        for interface in Section.interfaces('ethernet'):
            self.cli_set(base_path + ['netflow', 'interface', interface])

        self.cli_set(base_path + ['netflow', 'engine-id', engine_id])
        self.cli_set(base_path + ['netflow', 'max-flows', max_flows])
        self.cli_set(base_path + ['netflow', 'version', version])
        self.cli_set(base_path + ['netflow', 'active-timeout', active_timeout])
        self.cli_set(base_path + ['netflow', 'inactive-timeout', inactive_timeout])

        # You need to configure at least one netflow server
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        for server, server_config in netflow_server.items():
            self.cli_set(base_path + ['netflow', 'server', server])
            if 'port' in server_config:
                self.cli_set(base_path + ['netflow', 'server', server, 'port', server_config['port']])
            if 'source-address' in server_config:
                self.cli_set(
                    base_path
                    + [
                        'netflow',
                        'server',
                        server,
                        'source-address',
                        server_config['source-address'],
                    ]
                )
            if 'source-interface' in server_config:
                self.cli_set(
                    base_path
                    + [
                        'netflow',
                        'server',
                        server,
                        'source-interface',
                        server_config['source-interface'],
                    ]
                )

        # commit changes
        self.cli_commit()

        module_data = get_module_data(module_name)

        self.assertEqual(engine_id, module_data['parameters']['engine_id'])
        self.assertEqual(max_flows, module_data['parameters']['maxflows'])
        self.assertEqual(expected_destination, module_data['parameters']['destination'])
        self.assertEqual(version, module_data['parameters']['protocol'])
        self.assertEqual(active_timeout, module_data['parameters']['active_timeout'])
        self.assertEqual(
            inactive_timeout, module_data['parameters']['inactive_timeout']
        )

        # Test module reload with new parameters
        engine_id = '73'
        self.cli_set(base_path + ['netflow', 'engine-id', engine_id])
        self.cli_commit()

        module_data = get_module_data(module_name)

        self.assertEqual(engine_id, module_data['parameters']['engine_id'])

        self.cli_delete(['interfaces', 'dummy', dummy_if])


    def test_iptables(self):
        netflow_server = '11.22.33.44'
        self.cli_set(base_path + ['netflow', 'server', netflow_server])

        dummy_ifs = [
            'dum4000',
            'dum4001',
            'dum4002',
            'dum4003',
        ]

        self.cli_set(['interfaces', 'dummy', dummy_ifs[0], 'address', '192.0.2.100/32'])
        self.cli_set(['interfaces', 'dummy', dummy_ifs[1], 'address', '192.0.2.101/32'])
        self.cli_set(['interfaces', 'dummy', dummy_ifs[2], 'address', '192.0.2.102/32'])
        self.cli_set(['interfaces', 'dummy', dummy_ifs[3], 'address', '192.0.2.103/32'])

        # * three interfaces
        for i in range(3):
            self.cli_set(base_path + ['netflow', 'interface', dummy_ifs[i]])
        self.cli_commit()
        self._assert_ingress_interfaces(dummy_ifs[0:3])
        self._assert_egress_interfaces([])

        # * Then delete one
        self.cli_delete(base_path + ['netflow', 'interface', dummy_ifs[1]])
        self.cli_commit()
        self._assert_ingress_interfaces([dummy_ifs[0], dummy_ifs[2]])
        self._assert_egress_interfaces([])

        # * Then add one
        self.cli_set(base_path + ['netflow', 'interface', dummy_ifs[3]])
        self.cli_commit()
        self._assert_ingress_interfaces([dummy_ifs[0], dummy_ifs[2], dummy_ifs[3]])
        self._assert_egress_interfaces([])

        # * enable egress
        self.cli_set(base_path + ['enable-egress'])
        self.cli_commit()
        self._assert_ingress_interfaces([dummy_ifs[0], dummy_ifs[2], dummy_ifs[3]])
        self._assert_egress_interfaces([dummy_ifs[0], dummy_ifs[2], dummy_ifs[3]])

    def test_sampler(self):
        # Separate test because if --enable-sampler is not given to configure of
        # ipt_NETFLOW this parameter is not available
        sampling_rate = '100'
        self.cli_set(base_path + ['netflow', 'sampling-rate', sampling_rate])

        for interface in Section.interfaces('ethernet'):
            self.cli_set(base_path + ['netflow', 'interface', interface])

        netflow_server = '11.22.33.44'
        self.cli_set(base_path + ['netflow', 'server', netflow_server])

        # commit changes, this time should work
        self.cli_commit()

        module_data = get_module_data(module_name)

        if 'sampler' not in module_data['parameters']:
            self.skipTest("ipt_NETFLOW has no sampler parameter")

        self.assertEqual(
            f'random:{sampling_rate}', module_data['parameters']['sampler']
        )


if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
