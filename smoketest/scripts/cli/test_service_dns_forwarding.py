#!/usr/bin/env python3
#
# Copyright (C) 2019-2024 VyOS maintainers and contributors
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
import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.template import bracketize_ipv6
from vyos.utils.file import read_file
from vyos.utils.process import process_named_running

PDNS_REC_RUN_DIR = '/run/pdns-recursor'
CONFIG_FILE = f'{PDNS_REC_RUN_DIR}/recursor.conf'
FORWARD_FILE = f'{PDNS_REC_RUN_DIR}/recursor.forward-zones.conf'
HOSTSD_FILE = f'{PDNS_REC_RUN_DIR}/recursor.vyos-hostsd.conf.lua'
PROCESS_NAME= 'pdns_recursor'

base_path = ['service', 'dns', 'forwarding']

allow_from = ['192.0.2.0/24', '2001:db8::/32']
listen_adress = ['127.0.0.1', '::1']

def get_config_value(key, file=CONFIG_FILE):
    tmp = read_file(file)
    tmp = re.findall(r'\n{}=+(.*)'.format(key), tmp)
    return tmp[0]

class TestServicePowerDNS(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestServicePowerDNS, cls).setUpClass()
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

        # Delete DNS forwarding configuration
        self.cli_delete(base_path)
        self.cli_commit()

        # Check for running process
        self.assertFalse(process_named_running(PROCESS_NAME))

    def setUp(self):
        # forward to base class
        super().setUp()
        for network in allow_from:
            self.cli_set(base_path + ['allow-from', network])
        for address in listen_adress:
            self.cli_set(base_path + ['listen-address', address])

    def test_basic_forwarding(self):
        # Check basic DNS forwarding settings
        cache_size = '20'
        negative_ttl = '120'

        # remove code from setUp() as in this test-case we validate the proper
        # handling of assertions when specific CLI nodes are missing
        self.cli_delete(base_path)

        self.cli_set(base_path + ['cache-size', cache_size])
        self.cli_set(base_path + ['negative-ttl', negative_ttl])

        # check validate() - allow from must be defined
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        for network in allow_from:
            self.cli_set(base_path + ['allow-from', network])

        # check validate() - listen-address must be defined
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        for address in listen_adress:
            self.cli_set(base_path + ['listen-address', address])

        # configure DNSSEC
        self.cli_set(base_path + ['dnssec', 'validate'])

        # Do not use local /etc/hosts file in name resolution
        self.cli_set(base_path + ['ignore-hosts-file'])

        # commit changes
        self.cli_commit()

        # Check configured cache-size
        tmp = get_config_value('max-cache-entries')
        self.assertEqual(tmp, cache_size)

        # Networks allowed to query this server
        tmp = get_config_value('allow-from')
        self.assertEqual(tmp, ','.join(allow_from))

        # Addresses to listen for DNS queries
        tmp = get_config_value('local-address')
        self.assertEqual(tmp, ','.join(listen_adress))

        # Maximum amount of time negative entries are cached
        tmp = get_config_value('max-negative-ttl')
        self.assertEqual(tmp, negative_ttl)

        # Do not use local /etc/hosts file in name resolution
        tmp = get_config_value('export-etc-hosts')
        self.assertEqual(tmp, 'no')

        # RFC1918 addresses are looked up by default
        tmp = get_config_value('serve-rfc1918')
        self.assertEqual(tmp, 'yes')

        # verify default port configuration
        tmp = get_config_value('local-port')
        self.assertEqual(tmp, '53')

    def test_dnssec(self):
        # DNSSEC option testing
        options = ['off', 'process-no-validate', 'process', 'log-fail', 'validate']
        for option in options:
            self.cli_set(base_path + ['dnssec', option])

            # commit changes
            self.cli_commit()

            tmp = get_config_value('dnssec')
            self.assertEqual(tmp, option)

    def test_external_nameserver(self):
        # Externe Domain Name Servers (DNS) addresses
        nameservers = {'192.0.2.1': {}, '192.0.2.2': {'port': '53'}, '2001:db8::1': {'port': '853'}}
        for h,p in nameservers.items():
            if 'port' in p:
                self.cli_set(base_path + ['name-server', h, 'port', p['port']])
            else:
                self.cli_set(base_path + ['name-server', h])

        # commit changes
        self.cli_commit()

        tmp = get_config_value(r'\+.', file=FORWARD_FILE)
        canonical_entries = [(lambda h, p: f"{bracketize_ipv6(h)}:{p['port'] if 'port' in p else 53}")(h, p)
                             for (h, p) in nameservers.items()]
        self.assertEqual(tmp, ', '.join(canonical_entries))

        # Do not use local /etc/hosts file in name resolution
        # default: yes
        tmp = get_config_value('export-etc-hosts')
        self.assertEqual(tmp, 'yes')

    def test_domain_forwarding(self):
        domains = ['vyos.io', 'vyos.net', 'vyos.com']
        nameservers = {'192.0.2.1': {}, '192.0.2.2': {'port': '53'}, '2001:db8::1': {'port': '853'}}
        for domain in domains:
            for h,p in nameservers.items():
                if 'port' in p:
                    self.cli_set(base_path + ['domain', domain, 'name-server', h, 'port', p['port']])
                else:
                    self.cli_set(base_path + ['domain', domain, 'name-server', h])

            # Test 'recursion-desired' flag for only one domain
            if domain == domains[0]:
                self.cli_set(base_path + ['domain', domain, 'recursion-desired'])

            # Test 'negative trust anchor' flag for the second domain only
            if domain == domains[1]:
                self.cli_set(base_path + ['domain', domain, 'addnta'])

        # commit changes
        self.cli_commit()

        # Test configured name-servers
        hosts_conf = read_file(HOSTSD_FILE)
        for domain in domains:
            # Test 'recursion-desired' flag for the first domain only
            if domain == domains[0]: key =f'\+{domain}'
            else: key =f'{domain}'
            tmp = get_config_value(key, file=FORWARD_FILE)
            canonical_entries = [(lambda h, p: f"{bracketize_ipv6(h)}:{p['port'] if 'port' in p else 53}")(h, p)
                        for (h, p) in nameservers.items()]
            self.assertEqual(tmp, ', '.join(canonical_entries))

            # Test 'negative trust anchor' flag for the second domain only
            if domain == domains[1]:
                self.assertIn(f'addNTA("{domain}", "static")', hosts_conf)

    def test_no_rfc1918_forwarding(self):
        self.cli_set(base_path + ['no-serve-rfc1918'])

        # commit changes
        self.cli_commit()

        # verify configuration
        tmp = get_config_value('serve-rfc1918')
        self.assertEqual(tmp, 'no')

    def test_dns64(self):
        dns_prefix = '64:ff9b::/96'
        # Check dns64-prefix - must be prefix /96
        self.cli_set(base_path + ['dns64-prefix', '2001:db8:aabb::/64'])
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(base_path + ['dns64-prefix', dns_prefix])

        # commit changes
        self.cli_commit()

        # verify dns64-prefix configuration
        tmp = get_config_value('dns64-prefix')
        self.assertEqual(tmp, dns_prefix)

    def test_exclude_throttle_adress(self):
        exclude_throttle_adress_examples = [
            '192.168.128.255',
            '10.0.0.0/25',
            '2001:db8:85a3:8d3:1319:8a2e:370:7348',
            '64:ff9b::/96'
        ]
        for exclude_throttle_adress in exclude_throttle_adress_examples:
            self.cli_set(base_path + ['exclude-throttle-address', exclude_throttle_adress])

        # commit changes
        self.cli_commit()

        # verify dont-throttle-netmasks configuration
        tmp = get_config_value('dont-throttle-netmasks')
        self.assertEqual(tmp, ','.join(exclude_throttle_adress_examples))

    def test_serve_stale_extension(self):
        server_stale = '20'
        self.cli_set(base_path + ['serve-stale-extension', server_stale])
        # commit changes
        self.cli_commit()
        # verify configuration
        tmp = get_config_value('serve-stale-extensions')
        self.assertEqual(tmp, server_stale)

    def test_listening_port(self):
        # We can listen on a different port compared to '53' but only one at a time
        for port in ['10053', '10054']:
            self.cli_set(base_path + ['port', port])
            # commit changes
            self.cli_commit()
            # verify local-port configuration
            tmp = get_config_value('local-port')
            self.assertEqual(tmp, port)

    def test_ecs_add_for(self):
        options = ['0.0.0.0/0', '!10.0.0.0/8', 'fc00::/7', '!fe80::/10']
        for param in options:
            self.cli_set(base_path + ['options', 'ecs-add-for', param])

        # commit changes
        self.cli_commit()
        # verify ecs_add_for configuration
        tmp = get_config_value('ecs-add-for')
        self.assertEqual(tmp, ','.join(options))

    def test_ecs_ipv4_bits(self):
        option_value = '24'
        self.cli_set(base_path + ['options', 'ecs-ipv4-bits', option_value])
        # commit changes
        self.cli_commit()
        # verify ecs_ipv4_bits configuration
        tmp = get_config_value('ecs-ipv4-bits')
        self.assertEqual(tmp, option_value)

    def test_edns_subnet_allow_list(self):
        options = ['192.0.2.1/32', 'example.com', 'fe80::/10']
        for param in options:
            self.cli_set(base_path + ['options', 'edns-subnet-allow-list', param])

        # commit changes
        self.cli_commit()

        # verify edns_subnet_allow_list configuration
        tmp = get_config_value('edns-subnet-allow-list')
        self.assertEqual(tmp, ','.join(options))

    def test_multiple_ns_records(self):
        test_zone = 'example.com'
        self.cli_set(base_path + ['authoritative-domain', test_zone, 'records', 'ns', 'test', 'target', f'ns1.{test_zone}'])
        self.cli_set(base_path + ['authoritative-domain', test_zone, 'records', 'ns', 'test', 'target', f'ns2.{test_zone}'])
        self.cli_commit()
        zone_config = read_file(f'{PDNS_REC_RUN_DIR}/zone.{test_zone}.conf')
        self.assertRegex(zone_config, fr'test\s+\d+\s+NS\s+ns1\.{test_zone}\.')
        self.assertRegex(zone_config, fr'test\s+\d+\s+NS\s+ns2\.{test_zone}\.')


if __name__ == '__main__':
    unittest.main(verbosity=2)
