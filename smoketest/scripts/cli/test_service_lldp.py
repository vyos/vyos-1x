#!/usr/bin/env python3
#
# Copyright (C) 2022-2024 VyOS maintainers and contributors
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
from vyos.utils.process import process_named_running
from vyos.utils.file import read_file
from vyos.version import get_version_data

PROCESS_NAME = 'lldpd'
LLDPD_CONF = '/etc/lldpd.d/01-vyos.conf'
base_path = ['service', 'lldp']
mgmt_if = 'dum83513'
mgmt_addr = ['1.2.3.4', '1.2.3.5']

class TestServiceLLDP(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        # call base-classes classmethod
        super(TestServiceLLDP, cls).setUpClass()

        # create a test interfaces
        for addr in mgmt_addr:
            cls.cli_set(cls, ['interfaces', 'dummy', mgmt_if, 'address', addr + '/32'])

        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    @classmethod
    def tearDownClass(cls):
        cls.cli_delete(cls, ['interfaces', 'dummy', mgmt_if])
        super(TestServiceLLDP, cls).tearDownClass()

    def tearDown(self):
        # service must be running after it was configured
        self.assertTrue(process_named_running(PROCESS_NAME))

        # delete/stop LLDP service
        self.cli_delete(base_path)
        self.cli_commit()

        # service is no longer allowed to run after it was removed
        self.assertFalse(process_named_running(PROCESS_NAME))

    def test_01_lldp_basic(self):
        self.cli_set(base_path)
        self.cli_commit()

        config = read_file(LLDPD_CONF)
        version_data = get_version_data()
        version = version_data['version']
        self.assertIn(f'configure system platform VyOS', config)
        self.assertIn(f'configure system description "VyOS {version}"', config)

    def test_02_lldp_mgmt_address(self):
        for addr in mgmt_addr:
            self.cli_set(base_path + ['management-address', addr])
        self.cli_commit()

        config = read_file(LLDPD_CONF)
        self.assertIn(f'configure system ip management pattern {",".join(mgmt_addr)}', config)

    def test_03_lldp_interfaces(self):
        for interface in Section.interfaces('ethernet'):
            if not '.' in interface:
                self.cli_set(base_path + ['interface', interface])

        # commit changes
        self.cli_commit()

        # verify configuration
        config = read_file(LLDPD_CONF)

        interface_list = []
        for interface in Section.interfaces('ethernet'):
            if not '.' in interface:
                interface_list.append(interface)
        tmp = ','.join(interface_list)
        self.assertIn(f'configure system interface pattern "{tmp}"', config)

    def test_04_lldp_all_interfaces(self):
        self.cli_set(base_path + ['interface', 'all'])
        # commit changes
        self.cli_commit()

        # verify configuration
        config = read_file(LLDPD_CONF)
        self.assertIn(f'configure system interface pattern "*"', config)

    def test_05_lldp_location(self):
        interface = 'eth0'
        elin = '1234567890'
        self.cli_set(base_path + ['interface', interface, 'location', 'elin', elin])

        # commit changes
        self.cli_commit()

        # verify configuration
        config = read_file(LLDPD_CONF)

        self.assertIn(f'configure ports {interface} med location elin "{elin}"', config)
        self.assertIn(f'configure system interface pattern "{interface}"', config)

    def test_06_lldp_snmp(self):
        self.cli_set(base_path + ['snmp'])

        # verify - can not start lldp snmp without snmp beeing configured
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(['service', 'snmp'])
        self.cli_commit()

        # SNMP required process to be started with -x option
        tmp = read_file('/etc/default/lldpd')
        self.assertIn('-x', tmp)

        self.cli_delete(['service', 'snmp'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
