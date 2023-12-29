#!/usr/bin/env python3
#
# Copyright (C) 2019-2023 VyOS maintainers and contributors
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

from vyos.utils.file import read_file

RESOLV_CONF = '/etc/resolv.conf'

name_servers = ['192.0.2.10', '2001:db8:1::100']
domain_name = 'vyos.net'
domain_search = ['vyos.net', 'vyos.io']

base_path_nameserver = ['system', 'name-server']
base_path_domainname = ['system', 'domain-name']
base_path_domainsearch = ['system', 'domain-search']

def get_name_servers():
    resolv_conf = read_file(RESOLV_CONF)
    return re.findall(r'\n?nameserver\s+(.*)', resolv_conf)

def get_domain_name():
    resolv_conf = read_file(RESOLV_CONF)
    res = re.findall(r'\n?domain\s+(.*)', resolv_conf)
    return res[0] if res else None

def get_domain_searches():
    resolv_conf = read_file(RESOLV_CONF)
    res = re.findall(r'\n?search\s+(.*)', resolv_conf)
    return res[0].split() if res else []

class TestSystemResolvConf(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestSystemResolvConf, cls).setUpClass()
       # Clear out current configuration to allow running this test on a live system
        cls.cli_delete(cls, base_path_nameserver)
        cls.cli_delete(cls, base_path_domainname)
        cls.cli_delete(cls, base_path_domainsearch)

    def tearDown(self):
        # Delete test entries servers
        self.cli_delete(base_path_nameserver)
        self.cli_delete(base_path_domainname)
        self.cli_delete(base_path_domainsearch)
        self.cli_commit()

    def test_nameserver(self):
        # Check if server is added to resolv.conf
        for s in name_servers:
            self.cli_set(base_path_nameserver + [s])
        self.cli_commit()

        for s in get_name_servers():
            self.assertTrue(s in name_servers)

        # Test if a deleted server disappears from resolv.conf
        for s in name_servers:
          self.cli_delete(base_path_nameserver + [s])
        self.cli_commit()

        for s in get_name_servers():
            self.assertTrue(s not in name_servers)

    def test_domainname(self):
        # Check if domain-name is added to resolv.conf
        self.cli_set(base_path_domainname + [domain_name])
        self.cli_commit()

        self.assertEqual(get_domain_name(), domain_name)

        # Test if domain-name disappears from resolv.conf
        self.cli_delete(base_path_domainname + [domain_name])
        self.cli_commit()

        self.assertTrue(get_domain_name() is None)

    def test_domainsearch(self):
        # Check if domain-search is added to resolv.conf
        for s in domain_search:
            self.cli_set(base_path_domainsearch + [s])
        self.cli_commit()

        for s in get_domain_searches():
            self.assertTrue(s in domain_search)

        # Test if domain-search disappears from resolv.conf
        for s in domain_search:
            self.cli_delete(base_path_domainsearch + [s])
        self.cli_commit()

        for s in get_domain_searches():
            self.assertTrue(s not in domain_search)

if __name__ == '__main__':
    unittest.main(verbosity=2)
