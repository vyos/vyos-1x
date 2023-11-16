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
from vyos.ifconfig import Section
from vyos.utils.process import process_named_running

PROCESS_NAME = 'pimd'
base_path = ['protocols', 'pim']

class TestProtocolsPIM(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        # pimd process must be running
        self.assertTrue(process_named_running(PROCESS_NAME))

        self.cli_delete(base_path)
        self.cli_commit()

        # pimd process must be stopped by now
        self.assertFalse(process_named_running(PROCESS_NAME))

    def test_01_pim_basic(self):
        rp = '127.0.0.1'
        group = '224.0.0.0/4'
        hello = '100'
        dr_priority = '64'

        self.cli_set(base_path + ['rp', 'address', rp, 'group', group])

        interfaces = Section.interfaces('ethernet')
        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface , 'bfd'])
            self.cli_set(base_path + ['interface', interface , 'dr-priority', dr_priority])
            self.cli_set(base_path + ['interface', interface , 'hello', hello])
            self.cli_set(base_path + ['interface', interface , 'no-bsm'])
            self.cli_set(base_path + ['interface', interface , 'no-unicast-bsm'])
            self.cli_set(base_path + ['interface', interface , 'passive'])

        # commit changes
        self.cli_commit()

        # Verify FRR pimd configuration
        frrconfig = self.getFRRconfig(daemon=PROCESS_NAME)
        self.assertIn(f'ip pim rp {rp} {group}', frrconfig)

        for interface in interfaces:
            frrconfig = self.getFRRconfig(f'interface {interface}', daemon=PROCESS_NAME)
            self.assertIn(f'interface {interface}', frrconfig)
            self.assertIn(f' ip pim', frrconfig)
            self.assertIn(f' ip pim bfd', frrconfig)
            self.assertIn(f' ip pim drpriority {dr_priority}', frrconfig)
            self.assertIn(f' ip pim hello {hello}', frrconfig)
            self.assertIn(f' no ip pim bsm', frrconfig)
            self.assertIn(f' no ip pim unicast-bsm', frrconfig)
            self.assertIn(f' ip pim passive', frrconfig)

        self.cli_commit()

    def test_02_pim_advanced(self):
        rp = '127.0.0.2'
        group = '224.0.0.0/4'
        join_prune_interval = '123'
        rp_keep_alive_timer = '190'
        keep_alive_timer = '180'
        packets = '10'
        prefix_list = 'pim-test'
        register_suppress_time = '300'

        self.cli_set(base_path + ['rp', 'address', rp, 'group', group])
        self.cli_set(base_path + ['rp', 'keep-alive-timer', rp_keep_alive_timer])

        self.cli_set(base_path + ['ecmp', 'rebalance'])
        self.cli_set(base_path + ['join-prune-interval', join_prune_interval])
        self.cli_set(base_path + ['keep-alive-timer', keep_alive_timer])
        self.cli_set(base_path + ['packets', packets])
        self.cli_set(base_path + ['register-accept-list', 'prefix-list', prefix_list])
        self.cli_set(base_path + ['register-suppress-time', register_suppress_time])
        self.cli_set(base_path + ['no-v6-secondary'])
        self.cli_set(base_path + ['spt-switchover', 'infinity-and-beyond', 'prefix-list', prefix_list])
        self.cli_set(base_path + ['ssm', 'prefix-list', prefix_list])

        # check validate() - PIM require defined interfaces!
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        interfaces = Section.interfaces('ethernet')
        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface])

        # commit changes
        self.cli_commit()

        # Verify FRR pimd configuration
        frrconfig = self.getFRRconfig(daemon=PROCESS_NAME)
        self.assertIn(f'ip pim rp {rp} {group}', frrconfig)
        self.assertIn(f'ip pim rp keep-alive-timer {rp_keep_alive_timer}', frrconfig)
        self.assertIn(f'ip pim ecmp rebalance', frrconfig)
        self.assertIn(f'ip pim join-prune-interval {join_prune_interval}', frrconfig)
        self.assertIn(f'ip pim keep-alive-timer {keep_alive_timer}', frrconfig)
        self.assertIn(f'ip pim packets {packets}', frrconfig)
        self.assertIn(f'ip pim register-accept-list {prefix_list}', frrconfig)
        self.assertIn(f'ip pim register-suppress-time {register_suppress_time}', frrconfig)
        self.assertIn(f'no ip pim send-v6-secondary', frrconfig)
        self.assertIn(f'ip pim spt-switchover infinity-and-beyond prefix-list {prefix_list}', frrconfig)
        self.assertIn(f'ip pim ssm prefix-list {prefix_list}', frrconfig)

    def test_03_pim_igmp_proxy(self):
        igmp_proxy = ['protocols', 'igmp-proxy']
        rp = '127.0.0.1'
        group = '224.0.0.0/4'

        self.cli_set(base_path)
        self.cli_set(igmp_proxy)

        # check validate() - can not set both IGMP proxy and PIM
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_delete(igmp_proxy)

        self.cli_set(base_path + ['rp', 'address', rp, 'group', group])
        interfaces = Section.interfaces('ethernet')
        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface , 'bfd'])

        # commit changes
        self.cli_commit()

    def test_04_igmp(self):
        watermark_warning = '2000'
        query_interval = '1000'
        query_max_response_time = '200'
        version = '2'

        igmp_join = {
            '224.1.1.1' : { 'source' : ['1.1.1.1', '2.2.2.2', '3.3.3.3'] },
            '224.1.2.2' : { 'source' : [] },
            '224.1.3.3' : {},
        }

        self.cli_set(base_path + ['igmp', 'watermark-warning', watermark_warning])
        interfaces = Section.interfaces('ethernet')
        for interface in interfaces:
            self.cli_set(base_path + ['interface', interface , 'igmp', 'version', version])
            self.cli_set(base_path + ['interface', interface , 'igmp', 'query-interval', query_interval])
            self.cli_set(base_path + ['interface', interface , 'igmp', 'query-max-response-time', query_max_response_time])

            for join, join_config in igmp_join.items():
                self.cli_set(base_path + ['interface', interface , 'igmp', 'join', join])
                if 'source' in join_config:
                    for source in join_config['source']:
                        self.cli_set(base_path + ['interface', interface , 'igmp', 'join', join, 'source-address', source])

        self.cli_commit()

        frrconfig = self.getFRRconfig(daemon=PROCESS_NAME)
        self.assertIn(f'ip igmp watermark-warn {watermark_warning}', frrconfig)

        for interface in interfaces:
            frrconfig = self.getFRRconfig(f'interface {interface}', daemon=PROCESS_NAME)
            self.assertIn(f'interface {interface}', frrconfig)
            self.assertIn(f' ip igmp', frrconfig)
            self.assertIn(f' ip igmp version {version}', frrconfig)
            self.assertIn(f' ip igmp query-interval {query_interval}', frrconfig)
            self.assertIn(f' ip igmp query-max-response-time {query_max_response_time}', frrconfig)

            for join, join_config in igmp_join.items():
                if 'source' in join_config:
                    for source in join_config['source']:
                        self.assertIn(f' ip igmp join {join} {source}', frrconfig)
                else:
                    self.assertIn(f' ip igmp join {join}', frrconfig)

if __name__ == '__main__':
    unittest.main(verbosity=2)
