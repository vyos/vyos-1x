#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
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
import re
import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.firewall import find_nftables_rule
from vyos.util import cmd
from vyos.util import read_file

base_path = ['system', 'conntrack']

def get_sysctl(parameter):
    tmp = parameter.replace(r'.', r'/')
    return read_file(f'/proc/sys/{tmp}')

class TestSystemConntrack(VyOSUnitTestSHIM.TestCase):
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
            'net.netfilter.nf_conntrack_icmp_timeout' :{
                'cli'           : ['timeout', 'icmp'],
                'test_value'    : '180',
                'default_value' : '30',
            },
            'net.netfilter.nf_conntrack_generic_timeout' :{
                'cli'           : ['timeout', 'other'],
                'test_value'    : '1200',
                'default_value' : '600',
            },
            'net.netfilter.nf_conntrack_tcp_timeout_close_wait' :{
                'cli'           : ['timeout', 'tcp', 'close-wait'],
                'test_value'    : '30',
                'default_value' : '60',
            },
            'net.netfilter.nf_conntrack_tcp_timeout_close' :{
                'cli'           : ['timeout', 'tcp', 'close'],
                'test_value'    : '20',
                'default_value' : '10',
            },
            'net.netfilter.nf_conntrack_tcp_timeout_established' :{
                'cli'           : ['timeout', 'tcp', 'established'],
                'test_value'    : '1000',
                'default_value' : '432000',
            },
            'net.netfilter.nf_conntrack_tcp_timeout_fin_wait' :{
                'cli'           : ['timeout', 'tcp', 'fin-wait'],
                'test_value'    : '240',
                'default_value' : '120',
            },
            'net.netfilter.nf_conntrack_tcp_timeout_last_ack' :{
                'cli'           : ['timeout', 'tcp', 'last-ack'],
                'test_value'    : '300',
                'default_value' : '30',
            },
            'net.netfilter.nf_conntrack_tcp_timeout_syn_recv' :{
                'cli'           : ['timeout', 'tcp', 'syn-recv'],
                'test_value'    : '100',
                'default_value' : '60',
            },
            'net.netfilter.nf_conntrack_tcp_timeout_syn_sent' :{
                'cli'           : ['timeout', 'tcp', 'syn-sent'],
                'test_value'    : '300',
                'default_value' : '120',
            },
            'net.netfilter.nf_conntrack_tcp_timeout_time_wait' :{
                'cli'           : ['timeout', 'tcp', 'time-wait'],
                'test_value'    : '303',
                'default_value' : '120',
            },
            'net.netfilter.nf_conntrack_udp_timeout' :{
                'cli'           : ['timeout', 'udp', 'other'],
                'test_value'    : '90',
                'default_value' : '30',
            },
            'net.netfilter.nf_conntrack_udp_timeout_stream' :{
                'cli'           : ['timeout', 'udp', 'stream'],
                'test_value'    : '200',
                'default_value' : '180',
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
            'ftp' : {
                'driver' : ['nf_nat_ftp', 'nf_conntrack_ftp'],
            },
            'h323' : {
                'driver' : ['nf_nat_h323', 'nf_conntrack_h323'],
            },
            'nfs' : {
                'nftables' : ['ct helper set "rpc_tcp"',
                              'ct helper set "rpc_udp"']
            },
            'pptp' : {
                'driver' : ['nf_nat_pptp', 'nf_conntrack_pptp'],
             },
            'sip' : {
                'driver' : ['nf_nat_sip', 'nf_conntrack_sip'],
             },
            'sqlnet' : {
                'nftables' : ['ct helper set "tns_tcp"']
            },
            'tftp' : {
                'driver' : ['nf_nat_tftp', 'nf_conntrack_tftp'],
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
                    self.assertTrue(find_nftables_rule('raw', 'VYOS_CT_HELPER', [rule]) != None)

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
                    self.assertTrue(find_nftables_rule('raw', 'VYOS_CT_HELPER', [rule]) == None)

    def test_conntrack_hash_size(self):
        hash_size = '65536'
        hash_size_default = '32768'

        self.cli_set(base_path + ['hash-size', hash_size])

        # commit changes
        self.cli_commit()

        # verify new configuration - only effective after reboot, but
        # a valid config file is sufficient
        tmp = read_file('/etc/modprobe.d/vyatta_nf_conntrack.conf')
        self.assertIn(hash_size, tmp)

        # Test default value by deleting the configuration
        self.cli_delete(base_path + ['hash-size'])

        # commit changes
        self.cli_commit()

        # verify new configuration - only effective after reboot, but
        # a valid config file is sufficient
        tmp = read_file('/etc/modprobe.d/vyatta_nf_conntrack.conf')
        self.assertIn(hash_size_default, tmp)

if __name__ == '__main__':
    unittest.main(verbosity=2)
