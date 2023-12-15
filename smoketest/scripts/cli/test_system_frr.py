#!/usr/bin/env python3
#
# Copyright (C) 2021-2023 VyOS maintainers and contributors
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

config_file = '/etc/frr/daemons'
base_path = ['system', 'frr']

def daemons_config_parse(daemons_config):
    # create regex for parsing daemons options
    regex_daemon_config = re.compile(
        r'^(?P<daemon_name>\w+)_options="(?P<daemon_options>.*)"$', re.M)
    # create empty dict for config
    daemons_config_dict = {}
    # fill dictionary with actual config
    for daemon in regex_daemon_config.finditer(daemons_config):
        daemon_name = daemon.group('daemon_name')
        daemon_options = daemon.group('daemon_options')
        daemons_config_dict[daemon_name] = daemon_options.lstrip()

    # return daemons config
    return (daemons_config_dict)


class TestSystemFRR(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestSystemFRR, cls).setUpClass()

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

    def test_frr_snmp_multipledaemons(self):
        # test SNMP integration for multiple daemons
        test_daemon_names = ['ospfd', 'bgpd']
        for test_daemon_name in test_daemon_names:
            self.cli_set(base_path + ['snmp', test_daemon_name])
        self.cli_commit()

        # read the config file and check content
        daemons_config = read_file(config_file)
        daemons_config_dict = daemons_config_parse(daemons_config)
        # prepare regex for matching SNMP integration
        regex_snmp = re.compile(r'^.* -M snmp.*$')
        for (daemon_name, daemon_options) in daemons_config_dict.items():
            snmp_enabled = regex_snmp.match(daemon_options)
            if daemon_name in test_daemon_names:
                self.assertTrue(snmp_enabled)
            else:
                self.assertFalse(snmp_enabled)

    def test_frr_snmp_add_remove(self):
        # test enabling and disabling of SNMP integration
        test_daemon_names = ['ospfd', 'bgpd']
        for test_daemon_name in test_daemon_names:
            self.cli_set(base_path + ['snmp', test_daemon_name])
        self.cli_commit()

        self.cli_delete(base_path)
        self.cli_commit()

        # read the config file and check content
        daemons_config = read_file(config_file)
        daemons_config_dict = daemons_config_parse(daemons_config)
        # prepare regex for matching SNMP integration
        regex_snmp = re.compile(r'^.* -M snmp.*$')
        for test_daemon_name in test_daemon_names:
            snmp_enabled = regex_snmp.match(
                daemons_config_dict[test_daemon_name])
            self.assertFalse(snmp_enabled)

    def test_frr_snmp_empty(self):
        # test empty config section
        self.cli_set(base_path + ['snmp'])
        self.cli_commit()

        # read the config file and check content
        daemons_config = read_file(config_file)
        daemons_config_dict = daemons_config_parse(daemons_config)
        # prepare regex for matching SNMP integration
        regex_snmp = re.compile(r'^.* -M snmp.*$')
        for daemon_options in daemons_config_dict.values():
            snmp_enabled = regex_snmp.match(daemon_options)
            self.assertFalse(snmp_enabled)

    def test_frr_bmp(self):
        # test BMP
        self.cli_set(base_path + ['bmp'])
        self.cli_commit()

        # read the config file and check content
        daemons_config = read_file(config_file)
        daemons_config_dict = daemons_config_parse(daemons_config)
        # prepare regex
        regex_bmp = re.compile(r'^.* -M bmp.*$')
        bmp_enabled = regex_bmp.match(daemons_config_dict['bgpd'])
        self.assertTrue(bmp_enabled)

    def test_frr_irdp(self):
        # test IRDP
        self.cli_set(base_path + ['irdp'])
        self.cli_commit()

        # read the config file and check content
        daemons_config = read_file(config_file)
        daemons_config_dict = daemons_config_parse(daemons_config)
        # prepare regex
        regex_irdp = re.compile(r'^.* -M irdp.*$')
        irdp_enabled = regex_irdp.match(daemons_config_dict['zebra'])
        self.assertTrue(irdp_enabled)

    def test_frr_bmp_and_snmp(self):
        # test empty config section
        self.cli_set(base_path + ['bmp'])
        self.cli_set(base_path + ['snmp', 'bgpd'])
        self.cli_commit()

        # read the config file and check content
        daemons_config = read_file(config_file)
        daemons_config_dict = daemons_config_parse(daemons_config)
        # prepare regex
        regex_snmp = re.compile(r'^.* -M bmp.*$')
        regex_snmp = re.compile(r'^.* -M snmp.*$')
        bmp_enabled = regex_snmp.match(daemons_config_dict['bgpd'])
        snmp_enabled = regex_snmp.match(daemons_config_dict['bgpd'])
        self.assertTrue(bmp_enabled)
        self.assertTrue(snmp_enabled)

    def test_frr_file_descriptors(self):
        file_descriptors = '4096'

        self.cli_set(base_path + ['descriptors', file_descriptors])
        self.cli_commit()

        # read the config file and check content
        daemons_config = read_file(config_file)
        self.assertIn(f'MAX_FDS={file_descriptors}', daemons_config)

if __name__ == '__main__':
    unittest.main(verbosity=2)
