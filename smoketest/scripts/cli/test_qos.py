#!/usr/bin/env python3
#
# Copyright (C) 2022-2023 VyOS maintainers and contributors
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
from vyos.utils.process import cmd

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

def get_tc_filter_details(interface, direction) -> list:
    # json doesn't contain all params, such as mtu
    if direction not in ['ingress', 'egress']:
        raise ValueError()
    tmp = cmd(f'tc -details filter show dev {interface} {direction}')
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
                'bandwidth' : '3000000',
                'exceed' : 'pipe',
                'burst' : '100Kb',
                'mtu' : '1600',
                'not-exceed' : 'continue',
                'priority': '15',
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
            self.cli_set(base_path + ['policy', 'limiter', policy_name, 'default', 'burst', '200kb'])
            self.cli_set(base_path + ['policy', 'limiter', policy_name, 'default', 'exceed', 'drop'])
            self.cli_set(base_path + ['policy', 'limiter', policy_name, 'default', 'mtu', '3000'])
            self.cli_set(base_path + ['policy', 'limiter', policy_name, 'default', 'not-exceed', 'ok'])

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

                if 'exceed' in qos_class_config:
                    self.cli_set(qos_class_base + ['exceed', qos_class_config['exceed']])

                if 'not-exceed' in qos_class_config:
                    self.cli_set(qos_class_base + ['not-exceed', qos_class_config['not-exceed']])

                if 'burst' in qos_class_config:
                    self.cli_set(qos_class_base + ['burst', qos_class_config['burst']])

                if 'mtu' in qos_class_config:
                    self.cli_set(qos_class_base + ['mtu', qos_class_config['mtu']])

                if 'priority' in qos_class_config:
                    self.cli_set(qos_class_base + ['priority', qos_class_config['priority']])


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

            tc_details = get_tc_filter_details(interface, 'ingress')
            self.assertTrue('filter parent ffff: protocol all pref 20 u32 chain 0' in tc_details)
            self.assertTrue('rate 1Gbit burst 15125b mtu 2Kb action drop overhead 0b linklayer ethernet' in tc_details)
            self.assertTrue('filter parent ffff: protocol all pref 15 u32 chain 0' in tc_details)
            self.assertTrue('rate 3Gbit burst 102000b mtu 1600b action pipe/continue overhead 0b linklayer ethernet' in tc_details)
            self.assertTrue('rate 500Mbit burst 204687b mtu 3000b action drop overhead 0b linklayer ethernet' in tc_details)
            self.assertTrue('filter parent ffff: protocol all pref 255 basic chain 0' in tc_details)

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
            self.assertTrue('gred' in tmp.get('kind'))
            self.assertEqual(8, len(tmp.get('options', {}).get('vqs')))
            self.assertEqual(8, tmp.get('options', {}).get('dp_cnt'))
            self.assertEqual(0, tmp.get('options', {}).get('dp_default'))
            self.assertTrue(tmp.get('options', {}).get('grio'))

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

    def test_11_shaper(self):
        bandwidth = 250
        default_bandwidth = 20
        default_ceil = 30
        class_bandwidth = 50
        class_ceil = 80
        dst_address = '192.0.2.8/32'

        for interface in self._interfaces:
            shaper_name = f'qos-shaper-{interface}'

            self.cli_set(base_path + ['interface', interface, 'egress', shaper_name])
            self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'bandwidth', f'{bandwidth}mbit'])
            self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'default', 'bandwidth', f'{default_bandwidth}mbit'])
            self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'default', 'ceiling', f'{default_ceil}mbit'])
            self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'default', 'queue-type', 'fair-queue'])
            self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'class', '23', 'bandwidth', f'{class_bandwidth}mbit'])
            self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'class', '23', 'ceiling', f'{class_ceil}mbit'])
            self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'class', '23', 'match', '10', 'ip', 'destination', 'address', dst_address])

            bandwidth += 1
            default_bandwidth += 1
            default_ceil += 1
            class_bandwidth += 1
            class_ceil += 1

        # commit changes
        self.cli_commit()

        bandwidth = 250
        default_bandwidth = 20
        default_ceil = 30
        class_bandwidth = 50
        class_ceil = 80

        for interface in self._interfaces:
            config_entries = (
                f'root rate {bandwidth}Mbit ceil {bandwidth}Mbit',
                f'prio 0 rate {class_bandwidth}Mbit ceil {class_ceil}Mbit',
                f'prio 7 rate {default_bandwidth}Mbit ceil {default_ceil}Mbit'
            )

            output = cmd(f'tc class show dev {interface}')

            for config_entry in config_entries:
                self.assertIn(config_entry, output)

            bandwidth += 1
            default_bandwidth += 1
            default_ceil += 1
            class_bandwidth += 1
            class_ceil += 1

    def test_12_shaper_with_red_queue(self):
        bandwidth = 100
        default_bandwidth = 100
        default_burst = 100
        interface = self._interfaces[0]
        class_bandwidth = 50
        dst_address = '192.0.2.8/32'

        shaper_name = f'qos-shaper-{interface}'
        self.cli_set(base_path + ['interface', interface, 'egress', shaper_name])
        self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'bandwidth', f'{bandwidth}mbit'])
        self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'default', 'bandwidth', f'{default_bandwidth}%'])
        self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'default', 'burst', f'{default_burst}'])
        self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'default', 'queue-type', 'random-detect'])

        self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'class', '2', 'bandwidth', f'{class_bandwidth}mbit'])
        self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'class', '2', 'match', '10', 'ip', 'destination', 'address', dst_address])
        self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'class', '2', 'queue-type', 'random-detect'])

        # commit changes
        self.cli_commit()

        # check root htb config
        output = cmd(f'tc class show dev {interface}')

        config_entries = (
            f'prio 0 rate {class_bandwidth}Mbit ceil 50Mbit burst 15Kb',  # specified class
            f'prio 7 rate {default_bandwidth}Mbit ceil 100Mbit burst {default_burst}b',  # default class
        )
        for config_entry in config_entries:
            self.assertIn(config_entry, output)

        output = cmd(f'tc -d qdisc show dev {interface}')
        config_entries = (
            'qdisc red',  # use random detect
            'limit 72Kb min 9Kb max 18Kb ewma 3 probability 0.1',  # default config for random detect
        )
        for config_entry in config_entries:
            self.assertIn(config_entry, output)

        # test random detect queue params
        self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'default', 'queue-limit', '1024'])
        self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'default', 'average-packet', '1024'])
        self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'default', 'maximum-threshold', '32'])
        self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'default', 'minimum-threshold', '16'])

        self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'class', '2', 'queue-limit', '1024'])
        self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'class', '2', 'average-packet', '512'])
        self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'class', '2', 'maximum-threshold', '32'])
        self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'class', '2', 'minimum-threshold', '16'])
        self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'class', '2', 'mark-probability', '20'])

        self.cli_commit()

        output = cmd(f'tc -d qdisc show dev {interface}')
        config_entries = (
            'qdisc red',  # use random detect
            'limit 1Mb min 16Kb max 32Kb ewma 3 probability 0.1',  # default config for random detect
            'limit 512Kb min 8Kb max 16Kb ewma 3 probability 0.05',  # class config for random detect
        )
        for config_entry in config_entries:
            self.assertIn(config_entry, output)

    def test_13_shaper_delete_only_rule(self):
        default_bandwidth = 100
        default_burst = 100
        interface = self._interfaces[0]
        class_bandwidth = 50
        class_ceiling = 5
        src_address = '10.1.1.0/24'

        shaper_name = f'qos-shaper-{interface}'
        self.cli_set(base_path + ['interface', interface, 'egress', shaper_name])
        self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'bandwidth', f'10mbit'])
        self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'default', 'bandwidth', f'{default_bandwidth}mbit'])
        self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'default', 'burst', f'{default_burst}'])

        self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'class', '30', 'bandwidth', f'{class_bandwidth}mbit'])
        self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'class', '30', 'ceiling', f'{class_ceiling}mbit'])
        self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'class', '30', 'match', 'ADDRESS30', 'ip', 'source', 'address', src_address])
        self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'class', '30', 'match', 'ADDRESS30', 'description', 'smoketest'])
        self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'class', '30', 'priority', '5'])
        self.cli_set(base_path + ['policy', 'shaper', shaper_name, 'class', '30', 'queue-type', 'fair-queue'])

        # commit changes
        self.cli_commit()
        # check root htb config
        output = cmd(f'tc class show dev {interface}')

        config_entries = (
            f'prio 5 rate {class_bandwidth}Mbit ceil {class_ceiling}Mbit burst 15Kb',  # specified class
            f'prio 7 rate {default_bandwidth}Mbit ceil 100Mbit burst {default_burst}b',  # default class
        )
        for config_entry in config_entries:
            self.assertIn(config_entry, output)

        self.assertTrue('' != cmd(f'tc filter show dev {interface}'))
        # self.cli_delete(base_path + ['policy', 'shaper', shaper_name, 'class', '30', 'match', 'ADDRESS30'])
        self.cli_delete(base_path + ['policy', 'shaper', shaper_name, 'class', '30', 'match', 'ADDRESS30', 'ip', 'source', 'address', src_address])
        self.cli_commit()
        self.assertEqual('', cmd(f'tc filter show dev {interface}'))

    def test_14_policy_limiter_marked_traffic(self):
        policy_name = 'smoke_test'
        base_policy_path = ['qos', 'policy', 'limiter', policy_name]

        self.cli_set(['qos', 'interface', self._interfaces[0], 'ingress', policy_name])
        self.cli_set(base_policy_path + ['class', '100', 'bandwidth', '20gbit'])
        self.cli_set(base_policy_path + ['class', '100', 'burst', '3760k'])
        self.cli_set(base_policy_path + ['class', '100', 'match', 'INTERNAL', 'mark', '100'])
        self.cli_set(base_policy_path + ['class', '100', 'priority', '20'])
        self.cli_set(base_policy_path + ['default', 'bandwidth', '1gbit'])
        self.cli_set(base_policy_path + ['default', 'burst', '125000000b'])
        self.cli_commit()

        tc_filters = cmd(f'tc filter show dev {self._interfaces[0]} ingress')
        # class 100
        self.assertIn('filter parent ffff: protocol all pref 20 fw chain 0', tc_filters)
        self.assertIn('action order 1:  police 0x1 rate 20Gbit burst 3847500b mtu 2Kb action drop overhead 0b', tc_filters)
        # default
        self.assertIn('filter parent ffff: protocol all pref 255 basic chain 0', tc_filters)
        self.assertIn('action order 1:  police 0x2 rate 1Gbit burst 125000000b mtu 2Kb action drop overhead 0b', tc_filters)

    def test_15_traffic_match_group(self):
        interface = self._interfaces[0]
        self.cli_set(['qos', 'interface', interface, 'egress', 'VyOS-HTB'])
        base_policy_path = ['qos', 'policy', 'shaper', 'VyOS-HTB']

        #old syntax
        self.cli_set(base_policy_path + ['bandwidth', '100mbit'])
        self.cli_set(base_policy_path + ['class', '10', 'bandwidth', '40%'])
        self.cli_set(base_policy_path + ['class', '10', 'match', 'AF11', 'ip', 'dscp', 'AF11'])
        self.cli_set(base_policy_path + ['class', '10', 'match', 'AF41', 'ip', 'dscp', 'AF41'])
        self.cli_set(base_policy_path + ['class', '10', 'match', 'AF43', 'ip', 'dscp', 'AF43'])
        self.cli_set(base_policy_path + ['class', '10', 'match', 'CS4', 'ip', 'dscp', 'CS4'])
        self.cli_set(base_policy_path + ['class', '10', 'priority', '1'])
        self.cli_set(base_policy_path + ['class', '10', 'queue-type', 'fair-queue'])
        self.cli_set(base_policy_path + ['class', '20', 'bandwidth', '30%'])
        self.cli_set(base_policy_path + ['class', '20', 'match', 'EF', 'ip', 'dscp', 'EF'])
        self.cli_set(base_policy_path + ['class', '20', 'match', 'CS5', 'ip', 'dscp', 'CS5'])
        self.cli_set(base_policy_path + ['class', '20', 'priority', '2'])
        self.cli_set(base_policy_path + ['class', '20', 'queue-type', 'fair-queue'])
        self.cli_set(base_policy_path + ['default', 'bandwidth', '20%'])
        self.cli_set(base_policy_path + ['default', 'queue-type', 'fair-queue'])
        self.cli_commit()

        tc_filters_old = cmd(f'tc -details filter show dev {interface}')
        self.assertIn('match 00280000/00ff0000', tc_filters_old)
        self.assertIn('match 00880000/00ff0000', tc_filters_old)
        self.assertIn('match 00980000/00ff0000', tc_filters_old)
        self.assertIn('match 00800000/00ff0000', tc_filters_old)
        self.assertIn('match 00a00000/00ff0000', tc_filters_old)
        self.assertIn('match 00b80000/00ff0000', tc_filters_old)
        # delete config by old syntax
        self.cli_delete(base_policy_path)
        self.cli_delete(['qos', 'interface', interface, 'egress', 'VyOS-HTB'])
        self.cli_commit()
        self.assertEqual('', cmd(f'tc -s filter show dev {interface}'))

        self.cli_set(['qos', 'interface', interface, 'egress', 'VyOS-HTB'])
        # prepare traffic match group
        self.cli_set(['qos', 'traffic-match-group', 'VOICE', 'description', 'voice shaper'])
        self.cli_set(['qos', 'traffic-match-group', 'VOICE', 'match', 'EF', 'ip', 'dscp', 'EF'])
        self.cli_set(['qos', 'traffic-match-group', 'VOICE', 'match', 'CS5', 'ip', 'dscp', 'CS5'])

        self.cli_set(['qos', 'traffic-match-group', 'REAL_TIME_COMMON', 'description', 'real time common filters'])
        self.cli_set(['qos', 'traffic-match-group', 'REAL_TIME_COMMON', 'match', 'AF43', 'ip', 'dscp', 'AF43'])
        self.cli_set(['qos', 'traffic-match-group', 'REAL_TIME_COMMON', 'match', 'CS4', 'ip', 'dscp', 'CS4'])

        self.cli_set(['qos', 'traffic-match-group', 'REAL_TIME', 'description', 'real time shaper'])
        self.cli_set(['qos', 'traffic-match-group', 'REAL_TIME', 'match', 'AF41', 'ip', 'dscp', 'AF41'])
        self.cli_set(['qos', 'traffic-match-group', 'REAL_TIME', 'match-group', 'REAL_TIME_COMMON'])

        # new syntax
        self.cli_set(base_policy_path + ['bandwidth', '100mbit'])
        self.cli_set(base_policy_path + ['class', '10', 'bandwidth', '40%'])
        self.cli_set(base_policy_path + ['class', '10', 'match', 'AF11', 'ip', 'dscp', 'AF11'])
        self.cli_set(base_policy_path + ['class', '10', 'match-group', 'REAL_TIME'])
        self.cli_set(base_policy_path + ['class', '10', 'priority', '1'])
        self.cli_set(base_policy_path + ['class', '10', 'queue-type', 'fair-queue'])
        self.cli_set(base_policy_path + ['class', '20', 'bandwidth', '30%'])
        self.cli_set(base_policy_path + ['class', '20', 'match-group', 'VOICE'])
        self.cli_set(base_policy_path + ['class', '20', 'priority', '2'])
        self.cli_set(base_policy_path + ['class', '20', 'queue-type', 'fair-queue'])
        self.cli_set(base_policy_path + ['default', 'bandwidth', '20%'])
        self.cli_set(base_policy_path + ['default', 'queue-type', 'fair-queue'])
        self.cli_commit()

        self.assertEqual(tc_filters_old, cmd(f'tc -details filter show dev {interface}'))

    def test_16_wrong_traffic_match_group(self):
        interface = self._interfaces[0]
        self.cli_set(['qos', 'interface', interface])

        # Can not use both IPv6 and IPv4 in one match
        self.cli_set(['qos', 'traffic-match-group', '1', 'match', 'one', 'ip', 'dscp', 'EF'])
        self.cli_set(['qos', 'traffic-match-group', '1', 'match', 'one', 'ipv6', 'dscp', 'EF'])
        with self.assertRaises(ConfigSessionError) as e:
            self.cli_commit()

        # check contain itself, should commit success
        self.cli_delete(['qos', 'traffic-match-group', '1', 'match', 'one', 'ipv6'])
        self.cli_set(['qos', 'traffic-match-group', '1', 'match-group', '1'])
        self.cli_commit()

        # check cycle dependency, should commit success
        self.cli_set(['qos', 'traffic-match-group', '1', 'match-group', '3'])
        self.cli_set(['qos', 'traffic-match-group', '2', 'match', 'one', 'ip', 'dscp', 'CS4'])
        self.cli_set(['qos', 'traffic-match-group', '2', 'match-group', '1'])

        self.cli_set(['qos', 'traffic-match-group', '3', 'match', 'one', 'ipv6', 'dscp', 'CS4'])
        self.cli_set(['qos', 'traffic-match-group', '3', 'match-group', '2'])
        self.cli_commit()

        # inherit from non exist group, should commit success with warning
        self.cli_set(['qos', 'traffic-match-group', '3', 'match-group', 'unexpected'])
        self.cli_commit()


if __name__ == '__main__':
    unittest.main(verbosity=2)
