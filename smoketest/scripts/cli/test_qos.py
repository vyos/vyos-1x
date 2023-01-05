#!/usr/bin/env python3
#
# Copyright (C) 2022 VyOS maintainers and contributors
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

from json import loads
from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.ifconfig import Section
from vyos.util import cmd

base_path = ['qos']

def get_tc_qdisc_json(interface) -> dict:
    tmp = cmd(f'tc -detail -json qdisc show dev {interface}')
    tmp = loads(tmp)
    return next(iter(tmp))

def get_tc_filter_json(interface, direction) -> list:
    if direction not in ['ingress', 'egress']:
        raise ValueError()
    tmp = cmd(f'tc -detail -json filter show dev {interface} {direction}')
    tmp = loads(tmp)
    return tmp

class TestQoS(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestQoS, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

        # We only test on physical interfaces and not VLAN (sub-)interfaces
        cls._interfaces = []
        if 'TEST_ETH' in os.environ:
            tmp = os.environ['TEST_ETH'].split()
            cls._interfaces = tmp
        else:
            for tmp in Section.interfaces('ethernet', vlan=False):
                cls._interfaces.append(tmp)

    def tearDown(self):
        # delete testing SSH config
        self.cli_delete(base_path)
        self.cli_commit()

    def test_01_cake(self):
        bandwidth = 1000000
        rtt = 200

        for interface in self._interfaces:
            policy_name = f'qos-policy-{interface}'
            self.cli_set(base_path + ['interface', interface, 'egress', policy_name])
            self.cli_set(base_path + ['policy', 'cake', policy_name, 'bandwidth', str(bandwidth)])
            self.cli_set(base_path + ['policy', 'cake', policy_name, 'rtt', str(rtt)])
            self.cli_set(base_path + ['policy', 'cake', policy_name, 'flow-isolation', 'dual-src-host'])

            bandwidth += 1000000
            rtt += 20

        # commit changes
        self.cli_commit()

        bandwidth = 1000000
        rtt = 200
        for interface in self._interfaces:
            tmp = get_tc_qdisc_json(interface)

            self.assertEqual('cake', tmp['kind'])
            # TC store rates as a 32-bit unsigned integer in bps (Bytes per second)
            self.assertEqual(int(bandwidth *125), tmp['options']['bandwidth'])
            # RTT internally is in us
            self.assertEqual(int(rtt *1000), tmp['options']['rtt'])
            self.assertEqual('dual-srchost', tmp['options']['flowmode'])
            self.assertFalse(tmp['options']['ingress'])
            self.assertFalse(tmp['options']['nat'])
            self.assertTrue(tmp['options']['raw'])

            bandwidth += 1000000
            rtt += 20

    def test_02_drop_tail(self):
        queue_limit = 50

        first = True
        for interface in self._interfaces:
            policy_name = f'qos-policy-{interface}'

            if first:
                self.cli_set(base_path + ['interface', interface, 'ingress', policy_name])
                # verify() - selected QoS policy on interface only supports egress
                with self.assertRaises(ConfigSessionError):
                    self.cli_commit()
                self.cli_delete(base_path + ['interface', interface, 'ingress', policy_name])
                first = False

            self.cli_set(base_path + ['interface', interface, 'egress', policy_name])
            self.cli_set(base_path + ['policy', 'drop-tail', policy_name, 'queue-limit', str(queue_limit)])

            queue_limit += 10

        # commit changes
        self.cli_commit()

        queue_limit = 50
        for interface in self._interfaces:
            tmp = get_tc_qdisc_json(interface)

            self.assertEqual('pfifo', tmp['kind'])
            self.assertEqual(queue_limit, tmp['options']['limit'])

            queue_limit += 10

    def test_03_fair_queue(self):
        hash_interval = 10
        queue_limit = 5
        policy_type = 'fair-queue'

        first = True
        for interface in self._interfaces:
            policy_name = f'qos-policy-{interface}'

            if first:
                self.cli_set(base_path + ['interface', interface, 'ingress', policy_name])
                # verify() - selected QoS policy on interface only supports egress
                with self.assertRaises(ConfigSessionError):
                    self.cli_commit()
                self.cli_delete(base_path + ['interface', interface, 'ingress', policy_name])
                first = False

            self.cli_set(base_path + ['interface', interface, 'egress', policy_name])
            self.cli_set(base_path + ['policy', policy_type, policy_name, 'hash-interval', str(hash_interval)])
            self.cli_set(base_path + ['policy', policy_type, policy_name, 'queue-limit', str(queue_limit)])

            hash_interval += 1
            queue_limit += 1

        # commit changes
        self.cli_commit()

        hash_interval = 10
        queue_limit = 5
        for interface in self._interfaces:
            tmp = get_tc_qdisc_json(interface)

            self.assertEqual('sfq', tmp['kind'])
            self.assertEqual(hash_interval, tmp['options']['perturb'])
            self.assertEqual(queue_limit, tmp['options']['limit'])

            hash_interval += 1
            queue_limit += 1

    def test_04_fq_codel(self):
        policy_type = 'fq-codel'
        codel_quantum = 1500
        flows = 512
        interval = 100
        queue_limit = 2048
        target = 5

        first = True
        for interface in self._interfaces:
            policy_name = f'qos-policy-{interface}'

            if first:
                self.cli_set(base_path + ['interface', interface, 'ingress', policy_name])
                # verify() - selected QoS policy on interface only supports egress
                with self.assertRaises(ConfigSessionError):
                    self.cli_commit()
                self.cli_delete(base_path + ['interface', interface, 'ingress', policy_name])
                first = False

            self.cli_set(base_path + ['interface', interface, 'egress', policy_name])
            self.cli_set(base_path + ['policy', policy_type, policy_name, 'codel-quantum', str(codel_quantum)])
            self.cli_set(base_path + ['policy', policy_type, policy_name, 'flows', str(flows)])
            self.cli_set(base_path + ['policy', policy_type, policy_name, 'interval', str(interval)])
            self.cli_set(base_path + ['policy', policy_type, policy_name, 'queue-limit', str(queue_limit)])
            self.cli_set(base_path + ['policy', policy_type, policy_name, 'target', str(target)])

            codel_quantum += 10
            flows += 2
            interval += 10
            queue_limit += 512
            target += 1

        # commit changes
        self.cli_commit()

        codel_quantum = 1500
        flows = 512
        interval = 100
        queue_limit = 2048
        target = 5
        for interface in self._interfaces:
            tmp = get_tc_qdisc_json(interface)

            self.assertEqual('fq_codel', tmp['kind'])
            self.assertEqual(codel_quantum, tmp['options']['quantum'])
            self.assertEqual(flows, tmp['options']['flows'])
            self.assertEqual(queue_limit, tmp['options']['limit'])

            # due to internal rounding we need to substract 1 from interval and target after converting to milliseconds
            # configuration of:
            # tc qdisc add dev eth0 root fq_codel quantum 1500 flows 512 interval 100ms limit 2048 target 5ms noecn
            # results in: tc -j qdisc show dev eth0
            # [{"kind":"fq_codel","handle":"8046:","root":true,"refcnt":3,"options":{"limit":2048,"flows":512,
            #   "quantum":1500,"target":4999,"interval":99999,"memory_limit":33554432,"drop_batch":64}}]
            self.assertAlmostEqual(tmp['options']['interval'], interval *1000, delta=1)
            self.assertAlmostEqual(tmp['options']['target'], target *1000 -1, delta=1)

            codel_quantum += 10
            flows += 2
            interval += 10
            queue_limit += 512
            target += 1

    def test_05_limiter(self):
        qos_config = {
            '1' : {
                'bandwidth' : '1000000',
                'match4' : {
                    'ssh'   : { 'dport' : '22', },
                    },
                },
            '2' : {
                'bandwidth' : '1000000',
                'match6' : {
                    'ssh'   : { 'dport' : '22', },
                    },
                },
            }

        first = True
        for interface in self._interfaces:
            policy_name = f'qos-policy-{interface}'

            if first:
                self.cli_set(base_path + ['interface', interface, 'egress', policy_name])
                # verify() - selected QoS policy on interface only supports egress
                with self.assertRaises(ConfigSessionError):
                    self.cli_commit()
                self.cli_delete(base_path + ['interface', interface, 'egress', policy_name])
                first = False

            self.cli_set(base_path + ['interface', interface, 'ingress', policy_name])
            # set default bandwidth parameter for all remaining connections
            self.cli_set(base_path + ['policy', 'limiter', policy_name, 'default', 'bandwidth', '500000'])

            for qos_class, qos_class_config in qos_config.items():
                qos_class_base = base_path + ['policy', 'limiter', policy_name, 'class', qos_class]

                if 'match4' in qos_class_config:
                    for match, match_config in qos_class_config['match4'].items():
                        if 'dport' in match_config:
                            self.cli_set(qos_class_base + ['match', match, 'ip', 'destination', 'port', match_config['dport']])

                if 'match6' in qos_class_config:
                    for match, match_config in qos_class_config['match6'].items():
                        if 'dport' in match_config:
                            self.cli_set(qos_class_base + ['match', match, 'ipv6', 'destination', 'port', match_config['dport']])

                if 'bandwidth' in qos_class_config:
                    self.cli_set(qos_class_base + ['bandwidth', qos_class_config['bandwidth']])


        # commit changes
        self.cli_commit()

        for interface in self._interfaces:
            for filter in get_tc_filter_json(interface, 'ingress'):
                # bail out early if filter has no attached action
                if 'options' not in filter or 'actions' not in filter['options']:
                    continue

                for qos_class, qos_class_config in qos_config.items():
                    # Every flowid starts with ffff and we encopde the class number after the colon
                    if 'flowid' not in filter['options'] or filter['options']['flowid'] != f'ffff:{qos_class}':
                        continue

                    ip_hdr_offset = 20
                    if 'match6' in qos_class_config:
                        ip_hdr_offset = 40

                    self.assertEqual(ip_hdr_offset, filter['options']['match']['off'])
                    if 'dport' in match_config:
                        dport = int(match_config['dport'])
                        self.assertEqual(f'{dport:x}', filter['options']['match']['value'])

    def test_06_network_emulator(self):
        policy_type = 'network-emulator'

        bandwidth = 1000000
        corruption = 1
        delay = 2
        duplicate = 3
        loss = 4
        queue_limit = 5
        reordering = 6

        first = True
        for interface in self._interfaces:
            policy_name = f'qos-policy-{interface}'

            if first:
                self.cli_set(base_path + ['interface', interface, 'ingress', policy_name])
                # verify() - selected QoS policy on interface only supports egress
                with self.assertRaises(ConfigSessionError):
                    self.cli_commit()
                self.cli_delete(base_path + ['interface', interface, 'ingress', policy_name])
                first = False

            self.cli_set(base_path + ['interface', interface, 'egress', policy_name])

            self.cli_set(base_path + ['policy', policy_type, policy_name, 'bandwidth', str(bandwidth)])
            self.cli_set(base_path + ['policy', policy_type, policy_name, 'corruption', str(corruption)])
            self.cli_set(base_path + ['policy', policy_type, policy_name, 'delay', str(delay)])
            self.cli_set(base_path + ['policy', policy_type, policy_name, 'duplicate', str(duplicate)])
            self.cli_set(base_path + ['policy', policy_type, policy_name, 'loss', str(loss)])
            self.cli_set(base_path + ['policy', policy_type, policy_name, 'queue-limit', str(queue_limit)])
            self.cli_set(base_path + ['policy', policy_type, policy_name, 'reordering', str(reordering)])

            bandwidth += 1000000
            corruption += 1
            delay += 1
            duplicate +=1
            loss += 1
            queue_limit += 1
            reordering += 1

        # commit changes
        self.cli_commit()

        bandwidth = 1000000
        corruption = 1
        delay = 2
        duplicate = 3
        loss = 4
        queue_limit = 5
        reordering = 6
        for interface in self._interfaces:
            tmp = get_tc_qdisc_json(interface)
            self.assertEqual('netem', tmp['kind'])

            self.assertEqual(int(bandwidth *125), tmp['options']['rate']['rate'])
            # values are in %
            self.assertEqual(corruption/100, tmp['options']['corrupt']['corrupt'])
            self.assertEqual(duplicate/100, tmp['options']['duplicate']['duplicate'])
            self.assertEqual(loss/100, tmp['options']['loss-random']['loss'])
            self.assertEqual(reordering/100, tmp['options']['reorder']['reorder'])
            self.assertEqual(delay/1000, tmp['options']['delay']['delay'])

            self.assertEqual(queue_limit, tmp['options']['limit'])

            bandwidth += 1000000
            corruption += 1
            delay += 1
            duplicate += 1
            loss += 1
            queue_limit += 1
            reordering += 1

    def test_07_priority_queue(self):
        priorities = ['1', '2', '3', '4', '5']

        first = True
        for interface in self._interfaces:
            policy_name = f'qos-policy-{interface}'

            if first:
                self.cli_set(base_path + ['interface', interface, 'ingress', policy_name])
                # verify() - selected QoS policy on interface only supports egress
                with self.assertRaises(ConfigSessionError):
                    self.cli_commit()
                self.cli_delete(base_path + ['interface', interface, 'ingress', policy_name])
                first = False

            self.cli_set(base_path + ['interface', interface, 'egress', policy_name])
            self.cli_set(base_path + ['policy', 'priority-queue', policy_name, 'default', 'queue-limit', '10'])

            for priority in priorities:
                prio_base = base_path + ['policy', 'priority-queue', policy_name, 'class', priority]
                self.cli_set(prio_base + ['match', f'prio-{priority}', 'ip', 'destination', 'port', str(1000 + int(priority))])

        # commit changes
        self.cli_commit()

    def test_08_random_detect(self):
        self.skipTest('tc returns invalid JSON here - needs iproute2 fix')
        bandwidth = 5000

        first = True
        for interface in self._interfaces:
            policy_name = f'qos-policy-{interface}'

            if first:
                self.cli_set(base_path + ['interface', interface, 'ingress', policy_name])
                # verify() - selected QoS policy on interface only supports egress
                with self.assertRaises(ConfigSessionError):
                    self.cli_commit()
                self.cli_delete(base_path + ['interface', interface, 'ingress', policy_name])
                first = False

            self.cli_set(base_path + ['interface', interface, 'egress', policy_name])
            self.cli_set(base_path + ['policy', 'random-detect', policy_name, 'bandwidth', str(bandwidth)])

            bandwidth += 1000

        # commit changes
        self.cli_commit()

        bandwidth = 5000
        for interface in self._interfaces:
            tmp = get_tc_qdisc_json(interface)
            import pprint
            pprint.pprint(tmp)

    def test_09_rate_control(self):
        bandwidth = 5000
        burst = 20
        latency = 5

        first = True
        for interface in self._interfaces:
            policy_name = f'qos-policy-{interface}'

            if first:
                self.cli_set(base_path + ['interface', interface, 'ingress', policy_name])
                # verify() - selected QoS policy on interface only supports egress
                with self.assertRaises(ConfigSessionError):
                    self.cli_commit()
                self.cli_delete(base_path + ['interface', interface, 'ingress', policy_name])
                first = False

            self.cli_set(base_path + ['interface', interface, 'egress', policy_name])
            self.cli_set(base_path + ['policy', 'rate-control', policy_name, 'bandwidth', str(bandwidth)])
            self.cli_set(base_path + ['policy', 'rate-control', policy_name, 'burst', str(burst)])
            self.cli_set(base_path + ['policy', 'rate-control', policy_name, 'latency', str(latency)])

            bandwidth += 1000
            burst += 5
            latency += 1
        # commit changes
        self.cli_commit()

        bandwidth = 5000
        burst = 20
        latency = 5
        for interface in self._interfaces:
            tmp = get_tc_qdisc_json(interface)

            self.assertEqual('tbf', tmp['kind'])
            self.assertEqual(0, tmp['options']['mpu'])
            # TC store rates as a 32-bit unsigned integer in bps (Bytes per second)
            self.assertEqual(int(bandwidth * 125), tmp['options']['rate'])

            bandwidth += 1000
            burst += 5
            latency += 1

    def test_10_round_robin(self):
        qos_config = {
            '1' : {
                'match4' : {
                    'ssh'   : { 'dport' : '22', },
                    },
                },
            '2' : {
                'match6' : {
                    'ssh'   : { 'dport' : '22', },
                    },
                },
            }

        first = True
        for interface in self._interfaces:
            policy_name = f'qos-policy-{interface}'

            if first:
                self.cli_set(base_path + ['interface', interface, 'ingress', policy_name])
                # verify() - selected QoS policy on interface only supports egress
                with self.assertRaises(ConfigSessionError):
                    self.cli_commit()
                self.cli_delete(base_path + ['interface', interface, 'ingress', policy_name])
                first = False

            self.cli_set(base_path + ['interface', interface, 'egress', policy_name])

            for qos_class, qos_class_config in qos_config.items():
                qos_class_base = base_path + ['policy', 'round-robin', policy_name, 'class', qos_class]

                if 'match4' in qos_class_config:
                    for match, match_config in qos_class_config['match4'].items():
                        if 'dport' in match_config:
                            self.cli_set(qos_class_base + ['match', match, 'ip', 'destination', 'port', match_config['dport']])

                if 'match6' in qos_class_config:
                    for match, match_config in qos_class_config['match6'].items():
                        if 'dport' in match_config:
                            self.cli_set(qos_class_base + ['match', match, 'ipv6', 'destination', 'port', match_config['dport']])


        # commit changes
        self.cli_commit()

        for interface in self._interfaces:
            import pprint
            tmp = get_tc_qdisc_json(interface)
            self.assertEqual('drr', tmp['kind'])

            for filter in get_tc_filter_json(interface, 'ingress'):
                # bail out early if filter has no attached action
                if 'options' not in filter or 'actions' not in filter['options']:
                    continue

                for qos_class, qos_class_config in qos_config.items():
                    # Every flowid starts with ffff and we encopde the class number after the colon
                    if 'flowid' not in filter['options'] or filter['options']['flowid'] != f'ffff:{qos_class}':
                        continue

                    ip_hdr_offset = 20
                    if 'match6' in qos_class_config:
                        ip_hdr_offset = 40

                    self.assertEqual(ip_hdr_offset, filter['options']['match']['off'])
                    if 'dport' in match_config:
                        dport = int(match_config['dport'])
                        self.assertEqual(f'{dport:x}', filter['options']['match']['value'])

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=True)
