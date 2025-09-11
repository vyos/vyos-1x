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

import re

import os
import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.firewall import find_nftables_rule
from vyos.utils.file import read_file
from vyos.utils.file import read_json
from vyos.utils.process import cmd
from vyos.utils.system import sysctl_read
from vyos.xml_ref import default_value

base_path = ['system', 'conntrack']

def get_sysctl(parameter):
    tmp = parameter.replace(r'.', r'/')
    return read_file(f'/proc/sys/{tmp}')

def get_logger_config():
    return read_json('/run/vyos-conntrack-logger.conf')


def chain_priority_conntrack_compatible(table, chain, chain_type, hook):
    # Conntrack hooks into nftables at priority -200
    # Verify that base chain priority is a number greater than -200 (lower priority)
    # Priority must be lower than conntrack in order to read or update conntrack entries

    chain_contents = cmd(f'sudo nft list chain {table} {chain}')
    chain_search = re.search(
        rf'type {chain_type} hook {hook} priority (-*\d+)\;',
        chain_contents,
    )

    if chain_search is None:
        return False

    chain_priority = int(chain_search.group(1))

    if chain_priority <= -200:
        return False

    return True

class TestSystemConntrack(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestSystemConntrack, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

    def test_conntrack_options(self):
        conntrack_config = {
            'net.netfilter.nf_conntrack_expect_max' : {
                'cli'           : ['expect-table-size'],
                'test_value'    : '8192',
                'default_value' : '2048',
            },
            'net.nf_conntrack_max' :{
                'cli'           : ['table-size'],
                'test_value'    : '500000',
                'default_value' : '262144',
            },
            'net.ipv4.tcp_max_syn_backlog' :{
                'cli'           : ['tcp', 'half-open-connections'],
                'test_value'    : '2048',
                'default_value' : '512',
            },
            'net.netfilter.nf_conntrack_tcp_loose' :{
                'cli'           : ['tcp', 'loose'],
                'test_value'    : 'disable',
                'default_value' : '1',
            },
            'net.netfilter.nf_conntrack_tcp_max_retrans' :{
                'cli'           : ['tcp', 'max-retrans'],
                'test_value'    : '128',
                'default_value' : '3',
            },
        }

        for parameter, parameter_config in conntrack_config.items():
            self.cli_set(base_path + parameter_config['cli'] + [parameter_config['test_value']])

        # commit changes
        self.cli_commit()

        # validate configuration
        for parameter, parameter_config in conntrack_config.items():
            tmp = parameter_config['test_value']
            # net.netfilter.nf_conntrack_tcp_loose has a fancy "disable" value,
            # make this work
            if tmp == 'disable':
                tmp = '0'
            self.assertEqual(get_sysctl(f'{parameter}'), tmp)

        # delete all configuration options and revert back to defaults
        self.cli_delete(base_path)
        self.cli_commit()

        # validate configuration
        for parameter, parameter_config in conntrack_config.items():
            self.assertEqual(get_sysctl(f'{parameter}'), parameter_config['default_value'])


    def test_conntrack_module_enable(self):
        # conntrack helper modules are disabled by default
        modules = {
            'ftp': {
                'driver': ['nf_nat_ftp', 'nf_conntrack_ftp'],
                'nftables': ['ct helper set "ftp_tcp"']
            },
            'h323': {
                'driver': ['nf_nat_h323', 'nf_conntrack_h323'],
                'nftables': ['ct helper set "ras_udp"',
                             'ct helper set "q931_tcp"']
            },
            'nfs': {
                'nftables': ['ct helper set "rpc_tcp"',
                             'ct helper set "rpc_udp"']
            },
            'pptp': {
                'driver': ['nf_nat_pptp', 'nf_conntrack_pptp'],
                'nftables': ['ct helper set "pptp_tcp"']
            },
            'rtsp': {
                'driver': ['nf_nat_rtsp', 'nf_conntrack_rtsp'],
                'nftables': ['ct helper set "rtsp_tcp"']
            },
            'sip': {
                'driver': ['nf_nat_sip', 'nf_conntrack_sip'],
                'nftables': ['ct helper set "sip_tcp"',
                             'ct helper set "sip_udp"']
            },
            'sqlnet': {
                'nftables': ['ct helper set "tns_tcp"']
            },
            'tftp': {
                'driver': ['nf_nat_tftp', 'nf_conntrack_tftp'],
                'nftables': ['ct helper set "tftp_udp"']
             },
        }

        # load modules
        for module in modules:
            self.cli_set(base_path + ['modules', module])

        # commit changes
        self.cli_commit()

        # verify modules are loaded on the system
        for module, module_options in modules.items():
            if 'driver' in module_options:
                for driver in module_options['driver']:
                    self.assertTrue(os.path.isdir(f'/sys/module/{driver}'))
            if 'nftables' in module_options:
                for rule in module_options['nftables']:
                    self.assertTrue(find_nftables_rule('ip vyos_conntrack', 'VYOS_CT_HELPER', [rule]) != None)

        # unload modules
        for module in modules:
            self.cli_delete(base_path + ['modules', module])

        # commit changes
        self.cli_commit()

        # verify modules are not loaded on the system
        for module, module_options in modules.items():
            if 'driver' in module_options:
                for driver in module_options['driver']:
                    self.assertFalse(os.path.isdir(f'/sys/module/{driver}'))
            if 'nftables' in module_options:
                for rule in module_options['nftables']:
                    self.assertTrue(find_nftables_rule('ip vyos_conntrack', 'VYOS_CT_HELPER', [rule]) == None)

    def test_conntrack_hash_size(self):
        hash_size = '8192'
        hash_size_default = default_value(base_path + ['hash-size'])

        self.cli_set(base_path + ['hash-size', hash_size])

        # commit changes
        self.cli_commit()

        # verify new configuration - only effective after reboot, but
        # a valid config file is sufficient
        tmp = sysctl_read('net.netfilter.nf_conntrack_buckets')
        self.assertIn(hash_size, tmp)

        # Test default value by deleting the configuration
        self.cli_delete(base_path + ['hash-size'])

        # commit changes
        self.cli_commit()

        # verify new configuration - only effective after reboot, but
        # a valid config file is sufficient
        tmp = sysctl_read('net.netfilter.nf_conntrack_buckets')
        self.assertIn(hash_size_default, tmp)

    def test_conntrack_ignore(self):
        address_group = 'conntracktest'
        address_group_member = '192.168.0.1'
        port_single = '53'
        ports_multi = '500,4500'
        ipv6_address_group = 'conntracktest6'
        ipv6_address_group_member = 'dead:beef::1'

        self.cli_set(['firewall', 'group', 'address-group', address_group, 'address', address_group_member])
        self.cli_set(['firewall', 'group', 'ipv6-address-group', ipv6_address_group, 'address', ipv6_address_group_member])

        self.cli_set(base_path + ['ignore', 'ipv4', 'rule', '1', 'source', 'address', '192.0.2.1'])
        self.cli_set(base_path + ['ignore', 'ipv4', 'rule', '1', 'destination', 'address', '192.0.2.2'])
        self.cli_set(base_path + ['ignore', 'ipv4', 'rule', '1', 'destination', 'port', '22'])
        self.cli_set(base_path + ['ignore', 'ipv4', 'rule', '1', 'protocol', 'tcp'])
        self.cli_set(base_path + ['ignore', 'ipv4', 'rule', '1', 'tcp', 'flags', 'syn'])

        self.cli_set(base_path + ['ignore', 'ipv4', 'rule', '2', 'source', 'address', '192.0.2.1'])
        self.cli_set(base_path + ['ignore', 'ipv4', 'rule', '2', 'destination', 'group', 'address-group', address_group])
        self.cli_set(base_path + ['ignore', 'ipv4', 'rule', '2', 'protocol', 'all'])

        self.cli_set(base_path + ['ignore', 'ipv4', 'rule', '3', 'source', 'address', '192.0.2.1'])
        self.cli_set(base_path + ['ignore', 'ipv4', 'rule', '3', 'destination', 'port', ports_multi])
        self.cli_set(base_path + ['ignore', 'ipv4', 'rule', '3', 'protocol', 'udp'])

        self.cli_set(base_path + ['ignore', 'ipv4', 'rule', '4', 'source', 'address', '192.0.2.1'])
        self.cli_set(base_path + ['ignore', 'ipv4', 'rule', '4', 'destination', 'port', port_single])
        self.cli_set(base_path + ['ignore', 'ipv4', 'rule', '4', 'protocol', 'udp'])

        self.cli_set(base_path + ['ignore', 'ipv6', 'rule', '11', 'source', 'address', 'fe80::1'])
        self.cli_set(base_path + ['ignore', 'ipv6', 'rule', '11', 'destination', 'address', 'fe80::2'])
        self.cli_set(base_path + ['ignore', 'ipv6', 'rule', '11', 'destination', 'port', '22'])
        self.cli_set(base_path + ['ignore', 'ipv6', 'rule', '11', 'protocol', 'tcp'])

        self.cli_set(base_path + ['ignore', 'ipv6', 'rule', '12', 'source', 'address', 'fe80::1'])
        self.cli_set(base_path + ['ignore', 'ipv6', 'rule', '12', 'destination', 'group', 'address-group', ipv6_address_group])

        self.cli_set(base_path + ['ignore', 'ipv6', 'rule', '13', 'source', 'address', 'fe80::1'])
        self.cli_set(base_path + ['ignore', 'ipv6', 'rule', '13', 'destination', 'address', '!fe80::3'])

        self.cli_commit()

        nftables_search = [
            ['ip saddr 192.0.2.1', 'ip daddr 192.0.2.2', 'tcp dport 22', 'tcp flags & syn == syn', 'notrack'],
            ['ip saddr 192.0.2.1', 'ip daddr @A_conntracktest', 'notrack'],
            ['ip saddr 192.0.2.1', 'udp dport { 500, 4500 }', 'notrack'],
            ['ip saddr 192.0.2.1', 'udp dport 53', 'notrack']
        ]

        nftables6_search = [
            ['ip6 saddr fe80::1', 'ip6 daddr fe80::2', 'tcp dport 22', 'notrack'],
            ['ip6 saddr fe80::1', 'ip6 daddr @A6_conntracktest6', 'notrack'],
            ['ip6 saddr fe80::1', 'ip6 daddr != fe80::3', 'notrack']
        ]

        self.verify_nftables(nftables_search, 'ip vyos_conntrack')
        self.verify_nftables(nftables6_search, 'ip6 vyos_conntrack')

        self.cli_delete(['firewall'])

    def test_conntrack_timeout_custom(self):
        # No timeout rules configured yet, so there should be no VYOS_CT_TIMEOUT chain or timeout base chains
        # Timeout base chains MUST have priority higher than -200 because conntrack hooks at -200
        prerouting_timeout_chain = [
            ['chain PREROUTING_CT_TIMEOUT {'],
            ['type filter hook prerouting priority'],
            ['jump VYOS_CT_TIMEOUT'],
        ]
        output_timeout_chain = [
            ['chain OUTPUT_CT_TIMEOUT {'],
            ['type filter hook output priority'],
            ['jump VYOS_CT_TIMEOUT'],
        ]

        # None of these chains should exist yet
        self.verify_nftables_chain_exists(
            'ip vyos_conntrack', 'VYOS_CT_TIMEOUT', inverse=True
        )

        self.verify_nftables_chain_exists(
            'ip6 vyos_conntrack', 'VYOS_CT_TIMEOUT', inverse=True
        )

        self.verify_nftables_chain_exists(
            'ip vyos_conntrack', 'PREROUTING_CT_TIMEOUT', inverse=True
        )

        self.verify_nftables_chain_exists(
            'ip6 vyos_conntrack', 'PREROUTING_CT_TIMEOUT', inverse=True
        )

        self.verify_nftables_chain_exists(
            'ip vyos_conntrack', 'OUTPUT_CT_TIMEOUT', inverse=True
        )

        self.verify_nftables_chain_exists(
            'ip6 vyos_conntrack', 'OUTPUT_CT_TIMEOUT', inverse=True
        )

        self.cli_set(base_path + ['timeout', 'custom', 'ipv4', 'rule', '1', 'source', 'address', '192.0.2.1'])
        self.cli_set(base_path + ['timeout', 'custom', 'ipv4', 'rule', '1', 'destination', 'address', '192.0.2.2'])
        self.cli_set(base_path + ['timeout', 'custom', 'ipv4', 'rule', '1', 'destination', 'port', '22'])
        self.cli_set(base_path + ['timeout', 'custom', 'ipv4', 'rule', '1', 'protocol', 'tcp', 'syn-sent', '77'])
        self.cli_set(base_path + ['timeout', 'custom', 'ipv4', 'rule', '1', 'protocol', 'tcp', 'close', '88'])
        self.cli_set(base_path + ['timeout', 'custom', 'ipv4', 'rule', '1', 'protocol', 'tcp', 'established', '99'])

        self.cli_set(base_path + ['timeout', 'custom', 'ipv4', 'rule', '2', 'inbound-interface', 'eth1'])
        self.cli_set(base_path + ['timeout', 'custom', 'ipv4', 'rule', '2', 'source', 'address', '198.51.100.1'])
        self.cli_set(base_path + ['timeout', 'custom', 'ipv4', 'rule', '2', 'protocol', 'udp', 'unreplied', '55'])

        self.cli_commit()

        # We now have IPv4 custom timeout rules, so only the IPv4 table should contain the chains
        self.verify_nftables_chain_exists('ip vyos_conntrack', 'VYOS_CT_TIMEOUT')

        self.verify_nftables_chain_exists(
            'ip6 vyos_conntrack', 'VYOS_CT_TIMEOUT', inverse=True
        )

        self.verify_nftables_chain_exists('ip vyos_conntrack', 'PREROUTING_CT_TIMEOUT')

        self.verify_nftables_chain_exists(
            'ip6 vyos_conntrack', 'PREROUTING_CT_TIMEOUT', inverse=True
        )

        self.verify_nftables_chain_exists('ip vyos_conntrack', 'OUTPUT_CT_TIMEOUT')

        self.verify_nftables_chain_exists(
            'ip6 vyos_conntrack', 'OUTPUT_CT_TIMEOUT', inverse=True
        )

        self.verify_nftables_chain(
            prerouting_timeout_chain, 'ip vyos_conntrack', 'PREROUTING_CT_TIMEOUT'
        )

        self.verify_nftables_chain(
            output_timeout_chain, 'ip vyos_conntrack', 'OUTPUT_CT_TIMEOUT'
        )

        # Verify that IPv4 base chain priority is a number greater than -200
        if not chain_priority_conntrack_compatible(
            'ip vyos_conntrack', 'PREROUTING_CT_TIMEOUT', 'filter', 'prerouting'
        ):
            self.fail(
                'PREROUTING_CT_TIMEOUT base chain must have priority > -200 to read and update conntrack entries'
            )

        if not chain_priority_conntrack_compatible(
            'ip vyos_conntrack', 'OUTPUT_CT_TIMEOUT', 'filter', 'output'
        ):
            self.fail(
                'OUTPUT_CT_TIMEOUT base chain must have priority > -200 to read and update conntrack entries'
            )

        self.cli_set(base_path + ['timeout', 'custom', 'ipv6', 'rule', '1', 'source', 'address', '2001:db8::1'])
        self.cli_set(base_path + ['timeout', 'custom', 'ipv6', 'rule', '1', 'inbound-interface', 'eth2'])
        self.cli_set(base_path + ['timeout', 'custom', 'ipv6', 'rule', '1', 'protocol', 'tcp', 'time-wait', '22'])
        self.cli_set(base_path + ['timeout', 'custom', 'ipv6', 'rule', '1', 'protocol', 'tcp', 'last-ack', '33'])

        self.cli_commit()

        # Now we have both IPv4 and IPv6 custom timeout rules
        # The chains should exist in both the IPv4 and IPv6 tables
        self.verify_nftables_chain_exists('ip vyos_conntrack', 'VYOS_CT_TIMEOUT')
        self.verify_nftables_chain_exists('ip6 vyos_conntrack', 'VYOS_CT_TIMEOUT')
        self.verify_nftables_chain_exists('ip vyos_conntrack', 'PREROUTING_CT_TIMEOUT')
        self.verify_nftables_chain_exists('ip6 vyos_conntrack', 'PREROUTING_CT_TIMEOUT')
        self.verify_nftables_chain_exists('ip vyos_conntrack', 'OUTPUT_CT_TIMEOUT')
        self.verify_nftables_chain_exists('ip6 vyos_conntrack', 'OUTPUT_CT_TIMEOUT')

        self.verify_nftables_chain(
            prerouting_timeout_chain, 'ip vyos_conntrack', 'PREROUTING_CT_TIMEOUT'
        )

        self.verify_nftables_chain(
            prerouting_timeout_chain, 'ip6 vyos_conntrack', 'PREROUTING_CT_TIMEOUT'
        )

        self.verify_nftables_chain(
            output_timeout_chain, 'ip vyos_conntrack', 'OUTPUT_CT_TIMEOUT'
        )

        self.verify_nftables_chain(
            output_timeout_chain, 'ip6 vyos_conntrack', 'OUTPUT_CT_TIMEOUT'
        )

        # Verify that IPv6 base chain priority is a number greater than -200
        if not chain_priority_conntrack_compatible(
            'ip6 vyos_conntrack', 'PREROUTING_CT_TIMEOUT', 'filter', 'prerouting'
        ):
            self.fail(
                'PREROUTING_CT_TIMEOUT base chain must have priority > -200 to read and update conntrack entries'
            )

        if not chain_priority_conntrack_compatible(
            'ip6 vyos_conntrack', 'OUTPUT_CT_TIMEOUT', 'filter', 'output'
        ):
            self.fail(
                'OUTPUT_CT_TIMEOUT base chain must have priority > -200 to read and update conntrack entries'
            )

        # Verify rules are correctly output in nftables
        nftables_search = [
            ['ct timeout ct-timeout-1 {'],
            ['protocol tcp'],
            ['policy = { syn_sent : 1m17s, established : 1m39s, close : 1m28s }'],
            ['ct timeout ct-timeout-2 {'],
            ['protocol udp'],
            ['policy = { unreplied : 55s }'],
            ['chain VYOS_CT_TIMEOUT {'],
            ['ip saddr 192.0.2.1', 'ip daddr 192.0.2.2', 'tcp dport 22', 'ct timeout set "ct-timeout-1"'],
            ['iifname "eth1"', 'meta l4proto udp', 'ip saddr 198.51.100.1', 'ct timeout set "ct-timeout-2"']
        ]

        nftables6_search = [
            ['ct timeout ct-timeout-1 {'],
            ['protocol tcp'],
            ['policy = { last_ack : 33s, time_wait : 22s }'],
            ['chain VYOS_CT_TIMEOUT {'],
            ['iifname "eth2"', 'meta l4proto tcp', 'ip6 saddr 2001:db8::1', 'ct timeout set "ct-timeout-1"']
        ]

        self.verify_nftables(nftables_search, 'ip vyos_conntrack')
        self.verify_nftables(nftables6_search, 'ip6 vyos_conntrack')

        # remove IPv4 custom timeout rules and verify only the IPv6 chains still exist
        self.cli_delete(base_path + ['timeout', 'custom', 'ipv4'])
        self.cli_commit()

        # only the IPv6 chains should remain
        self.verify_nftables_chain_exists(
            'ip vyos_conntrack', 'VYOS_CT_TIMEOUT', inverse=True
        )

        self.verify_nftables_chain_exists('ip6 vyos_conntrack', 'VYOS_CT_TIMEOUT')

        self.verify_nftables_chain_exists(
            'ip vyos_conntrack', 'PREROUTING_CT_TIMEOUT', inverse=True
        )

        self.verify_nftables_chain_exists('ip6 vyos_conntrack', 'PREROUTING_CT_TIMEOUT')

        self.verify_nftables_chain_exists(
            'ip vyos_conntrack', 'OUTPUT_CT_TIMEOUT', inverse=True
        )

        self.verify_nftables_chain_exists('ip6 vyos_conntrack', 'OUTPUT_CT_TIMEOUT')

        self.verify_nftables_chain(
            prerouting_timeout_chain, 'ip6 vyos_conntrack', 'PREROUTING_CT_TIMEOUT'
        )

        self.verify_nftables_chain(
            output_timeout_chain, 'ip6 vyos_conntrack', 'OUTPUT_CT_TIMEOUT'
        )

        # remove custom timeout config and verify all chains are gone once again
        self.cli_delete(base_path + ['timeout'])
        self.cli_commit()

        self.verify_nftables_chain_exists(
            'ip vyos_conntrack', 'VYOS_CT_TIMEOUT', inverse=True
        )

        self.verify_nftables_chain_exists(
            'ip6 vyos_conntrack', 'VYOS_CT_TIMEOUT', inverse=True
        )

        self.verify_nftables_chain_exists(
            'ip vyos_conntrack', 'PREROUTING_CT_TIMEOUT', inverse=True
        )

        self.verify_nftables_chain_exists(
            'ip6 vyos_conntrack', 'PREROUTING_CT_TIMEOUT', inverse=True
        )

        self.verify_nftables_chain_exists(
            'ip vyos_conntrack', 'OUTPUT_CT_TIMEOUT', inverse=True
        )

        self.verify_nftables_chain_exists(
            'ip6 vyos_conntrack', 'OUTPUT_CT_TIMEOUT', inverse=True
        )

        self.cli_delete(['firewall'])

    def test_conntrack_log(self):
        expected_config = {
            'event': {
                'destroy': {},
                'new': {},
                'update': {},
            },
            'queue_size': '10000'
        }
        self.cli_set(base_path + ['log', 'event', 'destroy'])
        self.cli_set(base_path + ['log', 'event', 'new'])
        self.cli_set(base_path + ['log', 'event', 'update'])
        self.cli_set(base_path + ['log', 'queue-size', '10000'])
        self.cli_commit()
        self.assertEqual(expected_config, get_logger_config())
        self.assertEqual('0', get_sysctl('net.netfilter.nf_conntrack_timestamp'))

        for event in ['destroy', 'new', 'update']:
            for proto in ['icmp', 'other', 'tcp', 'udp']:
                self.cli_set(base_path + ['log', 'event', event, proto])
                expected_config['event'][event][proto] = {}
        self.cli_set(base_path + ['log', 'timestamp'])
        expected_config['timestamp'] = {}
        self.cli_commit()

        self.assertEqual(expected_config, get_logger_config())
        self.assertEqual('1', get_sysctl('net.netfilter.nf_conntrack_timestamp'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
