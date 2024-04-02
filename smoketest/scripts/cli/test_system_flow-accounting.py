#!/usr/bin/env python3
#
# Copyright (C) 2021-2024 VyOS maintainers and contributors
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
from vyos.template import bracketize_ipv6
from vyos.utils.process import cmd
from vyos.utils.process import process_named_running
from vyos.utils.file import read_file

PROCESS_NAME = 'uacctd'
base_path = ['system', 'flow-accounting']

uacctd_conf = '/run/pmacct/uacctd.conf'

class TestSystemFlowAccounting(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestSystemFlowAccounting, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        # after service removal process must no longer run
        self.assertTrue(process_named_running(PROCESS_NAME))

        self.cli_delete(base_path)
        self.cli_commit()

        # after service removal process must no longer run
        self.assertFalse(process_named_running(PROCESS_NAME))

    def test_basic(self):
        buffer_size = '5' # MiB
        syslog = 'all'

        self.cli_set(base_path + ['buffer-size', buffer_size])
        self.cli_set(base_path + ['syslog-facility', syslog])

        # You need to configure at least one interface for flow-accounting
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        for interface in Section.interfaces('ethernet'):
            self.cli_set(base_path + ['interface', interface])

        # commit changes
        self.cli_commit()

        # verify configuration
        nftables_output = cmd('sudo nft list chain raw VYOS_PREROUTING_HOOK').splitlines()
        for interface in Section.interfaces('ethernet'):
            rule_found = False
            ifname_search = f'iifname "{interface}"'

            for nftables_line in nftables_output:
                if 'FLOW_ACCOUNTING_RULE' in nftables_line and ifname_search in nftables_line:
                    self.assertIn('group 2', nftables_line)
                    self.assertIn('snaplen 128', nftables_line)
                    self.assertIn('queue-threshold 100', nftables_line)
                    rule_found = True
                    break

            self.assertTrue(rule_found)

        uacctd = read_file(uacctd_conf)
        # circular queue size - buffer_size
        tmp = int(buffer_size) *1024 *1024
        self.assertIn(f'plugin_pipe_size: {tmp}', uacctd)
        # transfer buffer size - recommended value from pmacct developers 1/1000 of pipe size
        tmp = int(buffer_size) *1024 *1024
        # do an integer division
        tmp //= 1000
        self.assertIn(f'plugin_buffer_size: {tmp}', uacctd)

        # when 'disable-imt' is not configured on the CLI it must be present
        self.assertIn(f'imt_path: /tmp/uacctd.pipe', uacctd)
        self.assertIn(f'imt_mem_pools_number: 169', uacctd)
        self.assertIn(f'syslog: {syslog}', uacctd)
        self.assertIn(f'plugins: memory', uacctd)

    def test_sflow(self):
        sampling_rate = '4000'
        source_address = '192.0.2.1'
        dummy_if = 'dum3841'
        agent_address = '192.0.2.2'

        sflow_server = {
            '1.2.3.4' : { },
            '5.6.7.8' : { 'port' : '6000' },
        }

        self.cli_set(['interfaces', 'dummy', dummy_if, 'address', agent_address + '/32'])
        self.cli_set(['interfaces', 'dummy', dummy_if, 'address', source_address + '/32'])
        self.cli_set(base_path + ['disable-imt'])

        # You need to configure at least one interface for flow-accounting
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        for interface in Section.interfaces('ethernet'):
            self.cli_set(base_path + ['interface', interface])


        # You need to configure at least one sFlow or NetFlow protocol, or not
        # set "disable-imt" for flow-accounting
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(base_path + ['sflow', 'agent-address', agent_address])
        self.cli_set(base_path + ['sflow', 'sampling-rate', sampling_rate])
        self.cli_set(base_path + ['sflow', 'source-address', source_address])
        for server, server_config in sflow_server.items():
            self.cli_set(base_path + ['sflow', 'server', server])
            if 'port' in server_config:
                self.cli_set(base_path + ['sflow', 'server', server, 'port', server_config['port']])

        # commit changes
        self.cli_commit()

        uacctd = read_file(uacctd_conf)

        # when 'disable-imt' is not configured on the CLI it must be present
        self.assertNotIn(f'imt_path: /tmp/uacctd.pipe', uacctd)
        self.assertNotIn(f'imt_mem_pools_number: 169', uacctd)
        self.assertNotIn(f'plugins: memory', uacctd)

        for server, server_config in sflow_server.items():
            plugin_name = server.replace('.', '-')
            if 'port' in server_config:
                self.assertIn(f'sfprobe_receiver[sf_{plugin_name}]: {server}', uacctd)
            else:
                self.assertIn(f'sfprobe_receiver[sf_{plugin_name}]: {server}:6343', uacctd)

            self.assertIn(f'sfprobe_agentip[sf_{plugin_name}]: {agent_address}', uacctd)
            self.assertIn(f'sampling_rate[sf_{plugin_name}]: {sampling_rate}', uacctd)
            self.assertIn(f'sfprobe_source_ip[sf_{plugin_name}]: {source_address}', uacctd)

        self.cli_delete(['interfaces', 'dummy', dummy_if])

    def test_sflow_ipv6(self):
        sampling_rate = '100'
        sflow_server = {
            '2001:db8::1' : { },
            '2001:db8::2' : { 'port' : '6000' },
        }

        self.cli_set(base_path + ['disable-imt'])

        # You need to configure at least one interface for flow-accounting
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        for interface in Section.interfaces('ethernet'):
            self.cli_set(base_path + ['interface', interface])


        # You need to configure at least one sFlow or NetFlow protocol, or not
        # set "disable-imt" for flow-accounting
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        self.cli_set(base_path + ['sflow', 'sampling-rate', sampling_rate])
        for server, server_config in sflow_server.items():
            self.cli_set(base_path + ['sflow', 'server', server])
            if 'port' in server_config:
                self.cli_set(base_path + ['sflow', 'server', server, 'port', server_config['port']])

        # commit changes
        self.cli_commit()

        uacctd = read_file(uacctd_conf)

        # when 'disable-imt' is not configured on the CLI it must be present
        self.assertNotIn(f'imt_path: /tmp/uacctd.pipe', uacctd)
        self.assertNotIn(f'imt_mem_pools_number: 169', uacctd)
        self.assertNotIn(f'plugins: memory', uacctd)

        for server, server_config in sflow_server.items():
            tmp_srv = server
            tmp_srv = tmp_srv.replace(':', '-')

            if 'port' in server_config:
                self.assertIn(f'sfprobe_receiver[sf_{tmp_srv}]: {bracketize_ipv6(server)}', uacctd)
            else:
                self.assertIn(f'sfprobe_receiver[sf_{tmp_srv}]: {bracketize_ipv6(server)}:6343', uacctd)
            self.assertIn(f'sampling_rate[sf_{tmp_srv}]: {sampling_rate}', uacctd)

    def test_netflow(self):
        engine_id = '33'
        max_flows = '667'
        sampling_rate = '100'
        source_address = '192.0.2.1'
        dummy_if = 'dum3842'
        agent_address = '192.0.2.10'
        version = '10'
        tmo_expiry = '120'
        tmo_flow = '1200'
        tmo_icmp = '60'
        tmo_max = '50000'
        tmo_tcp_fin = '100'
        tmo_tcp_generic = '120'
        tmo_tcp_rst = '99'
        tmo_udp = '10'

        netflow_server = {
            '11.22.33.44' : { },
            '55.66.77.88' : { 'port' : '6000' },
            '2001:db8::1' : { },
        }

        self.cli_set(['interfaces', 'dummy', dummy_if, 'address', agent_address + '/32'])
        self.cli_set(['interfaces', 'dummy', dummy_if, 'address', source_address + '/32'])

        for interface in Section.interfaces('ethernet'):
            self.cli_set(base_path + ['interface', interface])

        self.cli_set(base_path + ['netflow', 'engine-id', engine_id])
        self.cli_set(base_path + ['netflow', 'max-flows', max_flows])
        self.cli_set(base_path + ['netflow', 'sampling-rate', sampling_rate])
        self.cli_set(base_path + ['netflow', 'source-address', source_address])
        self.cli_set(base_path + ['netflow', 'version', version])

        # timeouts
        self.cli_set(base_path + ['netflow', 'timeout', 'expiry-interval', tmo_expiry])
        self.cli_set(base_path + ['netflow', 'timeout', 'flow-generic', tmo_flow])
        self.cli_set(base_path + ['netflow', 'timeout', 'icmp', tmo_icmp])
        self.cli_set(base_path + ['netflow', 'timeout', 'max-active-life', tmo_max])
        self.cli_set(base_path + ['netflow', 'timeout', 'tcp-fin', tmo_tcp_fin])
        self.cli_set(base_path + ['netflow', 'timeout', 'tcp-generic', tmo_tcp_generic])
        self.cli_set(base_path + ['netflow', 'timeout', 'tcp-rst', tmo_tcp_rst])
        self.cli_set(base_path + ['netflow', 'timeout', 'udp', tmo_udp])

        # You need to configure at least one netflow server
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        for server, server_config in netflow_server.items():
            self.cli_set(base_path + ['netflow', 'server', server])
            if 'port' in server_config:
                self.cli_set(base_path + ['netflow', 'server', server, 'port', server_config['port']])

        # commit changes
        self.cli_commit()

        uacctd = read_file(uacctd_conf)

        tmp = []
        for server, server_config in netflow_server.items():
            tmp_srv = server
            tmp_srv = tmp_srv.replace('.', '-')
            tmp_srv = tmp_srv.replace(':', '-')
            tmp.append(f'nfprobe[nf_{tmp_srv}]')
        tmp.append('memory')
        self.assertIn('plugins: ' + ','.join(tmp), uacctd)

        for server, server_config in netflow_server.items():
            tmp_srv = server
            tmp_srv = tmp_srv.replace('.', '-')
            tmp_srv = tmp_srv.replace(':', '-')

            self.assertIn(f'nfprobe_engine[nf_{tmp_srv}]: {engine_id}', uacctd)
            self.assertIn(f'nfprobe_maxflows[nf_{tmp_srv}]: {max_flows}', uacctd)
            self.assertIn(f'sampling_rate[nf_{tmp_srv}]: {sampling_rate}', uacctd)
            self.assertIn(f'nfprobe_source_ip[nf_{tmp_srv}]: {source_address}', uacctd)
            self.assertIn(f'nfprobe_version[nf_{tmp_srv}]: {version}', uacctd)

            if 'port' in server_config:
                self.assertIn(f'nfprobe_receiver[nf_{tmp_srv}]: {bracketize_ipv6(server)}', uacctd)
            else:
                self.assertIn(f'nfprobe_receiver[nf_{tmp_srv}]: {bracketize_ipv6(server)}:2055', uacctd)

            self.assertIn(f'nfprobe_timeouts[nf_{tmp_srv}]: expint={tmo_expiry}:general={tmo_flow}:icmp={tmo_icmp}:maxlife={tmo_max}:tcp.fin={tmo_tcp_fin}:tcp={tmo_tcp_generic}:tcp.rst={tmo_tcp_rst}:udp={tmo_udp}', uacctd)


        self.cli_delete(['interfaces', 'dummy', dummy_if])

if __name__ == '__main__':
    unittest.main(verbosity=2)
