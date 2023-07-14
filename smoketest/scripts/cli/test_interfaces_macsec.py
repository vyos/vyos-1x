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

import os
import re
import unittest

from base_interfaces_test import BasicInterfaceTest
from netifaces import interfaces

from vyos.configsession import ConfigSessionError
from vyos.ifconfig import Section
from vyos.utils.process import cmd
from vyos.utils.file import read_file
from vyos.utils.network import get_interface_config
from vyos.utils.process import process_named_running

PROCESS_NAME = 'wpa_supplicant'

def get_config_value(interface, key):
    tmp = read_file(f'/run/wpa_supplicant/{interface}.conf')
    tmp = re.findall(r'\n?{}=(.*)'.format(key), tmp)
    return tmp[0]

def get_cipher(interface):
    tmp = get_interface_config(interface)
    return tmp['linkinfo']['info_data']['cipher_suite'].lower()

class MACsecInterfaceTest(BasicInterfaceTest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._base_path = ['interfaces', 'macsec']
        cls._options = { 'macsec0': ['source-interface eth0', 'security cipher gcm-aes-128'] }

        # if we have a physical eth1 interface, add a second macsec instance
        if 'eth1' in Section.interfaces('ethernet'):
            macsec = { 'macsec1': [f'source-interface eth1', 'security cipher gcm-aes-128'] }
            cls._options.update(macsec)

        cls._interfaces = list(cls._options)
        # call base-classes classmethod
        super(MACsecInterfaceTest, cls).setUpClass()

    def tearDown(self):
        super().tearDown()
        self.assertFalse(process_named_running(PROCESS_NAME))

    def test_macsec_encryption(self):
        # MACsec can be operating in authentication and encryption mode - both
        # using different mandatory settings, lets test encryption as the basic
        # authentication test has been performed using the base class tests

        mak_cak = '232e44b7fda6f8e2d88a07bf78a7aff4'
        mak_ckn = '40916f4b23e3d548ad27eedd2d10c6f98c2d21684699647d63d41b500dfe8836'
        replay_window = '64'

        for interface, option_value in self._options.items():
            for option in option_value:
                if option.split()[0] == 'source-interface':
                    src_interface = option.split()[1]

                self.cli_set(self._base_path + [interface] + option.split())

            # Encrypt link
            self.cli_set(self._base_path + [interface, 'security', 'encrypt'])

            # check validate() - Physical source interface MTU must be higher then our MTU
            self.cli_set(self._base_path + [interface, 'mtu', '1500'])
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
            self.cli_delete(self._base_path + [interface, 'mtu'])

            # check validate() - MACsec security keys mandartory when encryption is enabled
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
            self.cli_set(self._base_path + [interface, 'security', 'mka', 'cak', mak_cak])

            # check validate() - MACsec security keys mandartory when encryption is enabled
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
            self.cli_set(self._base_path + [interface, 'security', 'mka', 'ckn', mak_ckn])

            self.cli_set(self._base_path + [interface, 'security', 'replay-window', replay_window])

            # final commit of settings
            self.cli_commit()

            tmp = get_config_value(src_interface, 'macsec_integ_only')
            self.assertIn("0", tmp)

            tmp = get_config_value(src_interface, 'mka_cak')
            self.assertIn(mak_cak, tmp)

            tmp = get_config_value(src_interface, 'mka_ckn')
            self.assertIn(mak_ckn, tmp)

            # check that the default priority of 255 is programmed
            tmp = get_config_value(src_interface, 'mka_priority')
            self.assertIn("255", tmp)

            tmp = get_config_value(src_interface, 'macsec_replay_window')
            self.assertIn(replay_window, tmp)

            tmp = read_file(f'/sys/class/net/{interface}/mtu')
            self.assertEqual(tmp, '1460')

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_macsec_gcm_aes_128(self):
        src_interface = 'eth0'
        interface = 'macsec1'
        cipher = 'gcm-aes-128'
        self.cli_set(self._base_path + [interface])

        # check validate() - source interface is mandatory
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(self._base_path + [interface, 'source-interface', src_interface])

        # check validate() - cipher is mandatory
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(self._base_path + [interface, 'security', 'cipher', cipher])

        # final commit and verify
        self.cli_commit()
        self.assertIn(interface, interfaces())
        self.assertIn(interface, interfaces())
        self.assertEqual(cipher, get_cipher(interface))

        # check that we use the new macsec_csindex option (T4537)
        tmp = get_config_value(src_interface, 'macsec_csindex')
        self.assertIn("0", tmp)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_macsec_gcm_aes_256(self):
        src_interface = 'eth0'
        interface = 'macsec4'
        cipher = 'gcm-aes-256'
        self.cli_set(self._base_path + [interface])

        # check validate() - source interface is mandatory
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(self._base_path + [interface, 'source-interface', src_interface])

        # check validate() - cipher is mandatory
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()
        self.cli_set(self._base_path + [interface, 'security', 'cipher', cipher])

        # final commit and verify
        self.cli_commit()
        self.assertIn(interface, interfaces())
        self.assertEqual(cipher, get_cipher(interface))

        # check that we use the new macsec_csindex option (T4537)
        tmp = get_config_value(src_interface, 'macsec_csindex')
        self.assertIn("1", tmp)

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

    def test_macsec_source_interface(self):
        # Ensure source-interface can bot be part of any other bond or bridge

        base_bridge = ['interfaces', 'bridge', 'br200']
        base_bond = ['interfaces', 'bonding', 'bond200']

        for interface, option_value in self._options.items():
            for option in option_value:
                self.cli_set(self._base_path + [interface] + option.split())
                if option.split()[0] == 'source-interface':
                    src_interface = option.split()[1]

            self.cli_set(base_bridge + ['member', 'interface', src_interface])
            # check validate() - Source interface must not already be a member of a bridge
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
            self.cli_delete(base_bridge)

            self.cli_set(base_bond + ['member', 'interface', src_interface])
            # check validate() - Source interface must not already be a member of a bridge
            with self.assertRaises(ConfigSessionError):
                self.cli_commit()
            self.cli_delete(base_bond)

            # final commit and verify
            self.cli_commit()
            self.assertIn(interface, interfaces())

        # Check for running process
        self.assertTrue(process_named_running(PROCESS_NAME))

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=True)

