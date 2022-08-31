#!/usr/bin/env python3
#
# Copyright (C) 2019-2022 VyOS maintainers and contributors
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
from vyos.util import read_file
from vyos.util import process_named_running

CONFIG_FILE = '/run/powerdns/recursor.conf'
FORWARD_FILE = '/run/powerdns/recursor.forward-zones.conf'
HOSTSD_FILE = '/run/powerdns/recursor.vyos-hostsd.conf.lua'
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

    def test_basic_forwarding(self):
        # Check basic DNS forwarding settings
        cache_size = '20'
        negative_ttl = '120'

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

    def test_dnssec(self):
        # DNSSEC option testing

        for network in allow_from:
            self.cli_set(base_path + ['allow-from', network])
        for address in listen_adress:
            self.cli_set(base_path + ['listen-address', address])

        options = ['off', 'process-no-validate', 'process', 'log-fail', 'validate']
        for option in options:
            self.cli_set(base_path + ['dnssec', option])

            # commit changes
            self.cli_commit()

            tmp = get_config_value('dnssec')
            self.assertEqual(tmp, option)

    def test_external_nameserver(self):
        # Externe Domain Name Servers (DNS) addresses

        for network in allow_from:
            self.cli_set(base_path + ['allow-from', network])
        for address in listen_adress:
            self.cli_set(base_path + ['listen-address', address])

        nameservers = ['192.0.2.1', '192.0.2.2']
        for nameserver in nameservers:
            self.cli_set(base_path + ['name-server', nameserver])

        # commit changes
        self.cli_commit()

        tmp = get_config_value(r'\+.', file=FORWARD_FILE)
        self.assertEqual(tmp, ', '.join(nameservers))

        # Do not use local /etc/hosts file in name resolution
        # default: yes
        tmp = get_config_value('export-etc-hosts')
        self.assertEqual(tmp, 'yes')

    def test_domain_forwarding(self):
        for network in allow_from:
            self.cli_set(base_path + ['allow-from', network])
        for address in listen_adress:
            self.cli_set(base_path + ['listen-address', address])

        domains = ['vyos.io', 'vyos.net', 'vyos.com']
        nameservers = ['192.0.2.1', '192.0.2.2']
        for domain in domains:
            for nameserver in nameservers:
                self.cli_set(base_path + ['domain', domain, 'server', nameserver])

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
            self.assertEqual(tmp, ', '.join(nameservers))

            # Test 'negative trust anchor' flag for the second domain only
            if domain == domains[1]:
                self.assertIn(f'addNTA("{domain}", "static")', hosts_conf)

    def test_no_rfc1918_forwarding(self):
        for network in allow_from:
            self.cli_set(base_path + ['allow-from', network])
        for address in listen_adress:
            self.cli_set(base_path + ['listen-address', address])

        self.cli_set(base_path + ['no-serve-rfc1918'])

        # commit changes
        self.cli_commit()

        # verify configuration
        tmp = get_config_value('serve-rfc1918')
        self.assertEqual(tmp, 'no')

    def test_dns64(self):
        dns_prefix = '64:ff9b::/96'

        for network in allow_from:
            self.cli_set(base_path + ['allow-from', network])
        for address in listen_adress:
            self.cli_set(base_path + ['listen-address', address])

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

if __name__ == '__main__':
    unittest.main(verbosity=2)
