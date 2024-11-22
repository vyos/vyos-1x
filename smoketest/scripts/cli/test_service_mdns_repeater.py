#!/usr/bin/env python3
#
# Copyright (C) 2020-2023 VyOS maintainers and contributors
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

from configparser import ConfigParser
from vyos.configsession import ConfigSessionError
from vyos.utils.process import process_named_running
from vyos.xml_ref import default_value

base_path = ['service', 'mdns', 'repeater']
intf_base = ['interfaces', 'dummy']
config_file = '/run/avahi-daemon/avahi-daemon.conf'

class TestServiceMDNSrepeater(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestServiceMDNSrepeater, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

        cls.cli_set(cls, intf_base + ['dum10', 'address', '192.0.2.1/30'])
        cls.cli_set(cls, intf_base + ['dum10', 'ipv6', 'address', 'no-default-link-local'])
        cls.cli_set(cls, intf_base + ['dum20', 'address', '192.0.2.5/30'])
        cls.cli_set(cls, intf_base + ['dum20', 'address', '2001:db8:0:2::5/64'])
        cls.cli_set(cls, intf_base + ['dum30', 'address', '192.0.2.9/30'])
        cls.cli_set(cls, intf_base + ['dum30', 'address', '2001:db8:0:2::9/64'])
        cls.cli_set(cls, intf_base + ['dum40', 'address', '2001:db8:0:2::11/64'])

        cls.cli_commit(cls)

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, intf_base + ['dum10'])
        cls.cli_delete(cls, intf_base + ['dum20'])
        cls.cli_delete(cls, intf_base + ['dum30'])
        cls.cli_delete(cls, intf_base + ['dum40'])

        cls.cli_commit(cls)

    def tearDown(self):
        # Check for running process
        self.assertTrue(process_named_running('avahi-daemon'))

        self.cli_delete(base_path)
        self.cli_commit()

        # Check that there is no longer a running process
        self.assertFalse(process_named_running('avahi-daemon'))

    def test_service_dual_stack(self):
        # mDNS browsing domains in addition to the default one (local)
        domains = ['dom1.home.arpa', 'dom2.home.arpa']

        # mDNS services to be repeated
        services = ['_ipp._tcp', '_smb._tcp', '_ssh._tcp']

        self.cli_set(base_path + ['ip-version', 'both'])
        self.cli_set(base_path + ['interface', 'dum20'])
        self.cli_set(base_path + ['interface', 'dum30'])

        for domain in domains:
            self.cli_set(base_path + ['browse-domain', domain])

        for service in services:
            self.cli_set(base_path + ['allow-service', service])

        self.cli_commit()

        # Validate configuration values
        conf = ConfigParser(delimiters='=')
        conf.read(config_file)

        self.assertEqual(conf['server']['use-ipv4'], 'yes')
        self.assertEqual(conf['server']['use-ipv6'], 'yes')
        self.assertEqual(conf['server']['allow-interfaces'], 'dum20, dum30')
        self.assertEqual(conf['server']['browse-domains'], ', '.join(domains))
        self.assertEqual(conf['reflector']['enable-reflector'], 'yes')
        self.assertEqual(conf['reflector']['reflect-filters'], ', '.join(services))

    def test_service_ipv4(self):
        # partcipating interfaces should have IPv4 addresses
        self.cli_set(base_path + ['ip-version', 'ipv4'])
        self.cli_set(base_path + ['interface', 'dum10'])
        self.cli_set(base_path + ['interface', 'dum40'])

        # exception is raised if partcipating interfaces do not have IPv4 address
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(base_path + ['interface', 'dum40'])
        self.cli_set(base_path + ['interface', 'dum20'])
        self.cli_commit()

        # Validate configuration values
        conf = ConfigParser(delimiters='=')
        conf.read(config_file)

        self.assertEqual(conf['server']['use-ipv4'], 'yes')
        self.assertEqual(conf['server']['use-ipv6'], 'no')
        self.assertEqual(conf['server']['allow-interfaces'], 'dum10, dum20')
        self.assertEqual(conf['reflector']['enable-reflector'], 'yes')

    def test_service_ipv6(self):
        # partcipating interfaces should have IPv6 addresses
        self.cli_set(base_path + ['ip-version', 'ipv6'])
        self.cli_set(base_path + ['interface', 'dum10'])
        self.cli_set(base_path + ['interface', 'dum30'])

        # exception is raised if partcipating interfaces do not have IPv4 address
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_delete(base_path + ['interface', 'dum10'])
        self.cli_set(base_path + ['interface', 'dum40'])
        self.cli_commit()

        # Validate configuration values
        conf = ConfigParser(delimiters='=')
        conf.read(config_file)

        self.assertEqual(conf['server']['use-ipv4'], 'no')
        self.assertEqual(conf['server']['use-ipv6'], 'yes')
        self.assertEqual(conf['server']['allow-interfaces'], 'dum30, dum40')
        self.assertEqual(conf['reflector']['enable-reflector'], 'yes')

    def test_service_max_cache_entries(self):
        cli_default_max_cache = default_value(base_path + ['cache-entries'])
        self.cli_set(base_path)

        # Need at least two interfaces
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(base_path + ['interface', 'dum20'])

        # Need at least two interfaces
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(base_path + ['interface', 'dum30'])

        self.cli_commit()

        # Validate configuration values
        conf = ConfigParser(delimiters='=')
        conf.read(config_file)
        self.assertEqual(conf['server']['cache-entries-max'], cli_default_max_cache)

        # Set max cache entries
        cache_entries = '1234'
        self.cli_set(base_path + ['cache-entries', cache_entries])

        self.cli_commit()

        # Validate configuration values
        conf = ConfigParser(delimiters='=')
        conf.read(config_file)

        self.assertEqual(conf['server']['cache-entries-max'], cache_entries)

if __name__ == '__main__':
    unittest.main(verbosity=2)
