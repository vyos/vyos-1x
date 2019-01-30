#!/usr/bin/env python3
#
# Copyright (C) 2018 VyOS maintainers and contributors
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
#
#

import os
import tempfile
import unittest
from unittest import TestCase, mock
import ipaddress
from contextlib import ExitStack 
import textwrap

from vyos import ConfigError
from vyos.config import Config
try:
    from src.conf_mode import ntp
except ModuleNotFoundError:  # for unittest.main()
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
    from src.conf_mode import ntp


class TestNtp(TestCase):

    def test_get_config(self):
        tests = [
            {
                'name': 'empty',
                'config': {
                    'system ntp': None,
                },
                'expected': None,
            },
            {
                'name': 'full-options',
                'config': {
                    'system ntp': 'yes',
                    'allow-clients address': ['192.0.2.0/24'],
                    'listen-address': ['198.51.100.0/24'],
                    'server': ['example.com'],
                    'server example.com noselect': 'yes',
                    'server example.com preempt': 'yes',
                    'server example.com prefer': 'yes',
                },
                'expected': {
                    'allowed_networks': [{
                        'address': ipaddress.ip_address('192.0.2.0'),
                        'netmask': ipaddress.ip_address('255.255.255.0'),
                        'network': '192.0.2.0/24',
                    }],
                    'listen_address': ['198.51.100.0/24'],
                    'servers': [
                        {'name': 'example.com', 'options': ['noselect', 'preempt', 'prefer']}
                    ]
                },
            },
            {
                'name': 'non-options',
                'config': {
                    'system ntp': 'yes',
                    'allow-clients address': ['192.0.2.0/24'],
                    'listen-address': ['198.51.100.0/24'],
                    'server': ['example.com'],
                },
                'expected': {
                    'allowed_networks': [{
                        'address': ipaddress.ip_address('192.0.2.0'),
                        'netmask': ipaddress.ip_address('255.255.255.0'),
                        'network': '192.0.2.0/24',
                    }],
                    'listen_address': ['198.51.100.0/24'],
                    'servers': [
                        {'name': 'example.com', 'options': []}
                    ]
                },
            },
        ]
        for case in tests:
            def mocked_fn(path):
                return case['config'].get(path)

            with self.subTest(msg = case['name']):
                m = {
                    'return_value': mock.Mock(side_effect = mocked_fn),
                    'return_values': mock.Mock(side_effect = mocked_fn),
                    'list_nodes': mock.Mock(side_effect = mocked_fn),
                    'exists': mock.Mock(side_effect = mocked_fn),
                }
                with mock.patch.multiple(Config, **m):
                    actual = ntp.get_config()
                    self.assertEqual(actual, case['expected'])

    def test_verify(self):
        tests = [
            {
                'name': 'none',
                'config': None,
                'expected': None
            },
            {
                'name': 'valid',
                'config': {
                    'allowed_networks': [{
                        'address': ipaddress.ip_address('192.0.2.1'),
                        'netmask': ipaddress.ip_address('255.255.255.0'),
                        'network': '192.0.2.0/24',
                    }],
                    'listen_address': ['198.51.100.0/24'],
                    'servers': [
                        {'name': 'example.com', 'options': ['noselect', 'preempt', 'prefer']}
                    ]
                },
                'expected': None,
            },
            {
                'name': 'not configure servers',
                'config': {
                    'allowed_networks': [{
                        'address': ipaddress.ip_address('192.0.2.1'),
                        'netmask': ipaddress.ip_address('255.255.255.0'),
                        'network': '192.0.2.0/24',
                    }],
                    'servers': []
                },
                'expected': ConfigError,
            },
            {
                'name': 'does not exist in the network',
                'config': {
                    'allowed_networks': [{
                        'address': ipaddress.ip_address('192.0.2.1'),
                        'netmask': ipaddress.ip_address('255.255.255.0'),
                        'network': '192.0.2.0/50', # invalid netmask
                    }],
                    'listen_address': ['198.51.100.0/24'],
                    'servers': [
                        {'name': 'example.com', 'options': []}
                    ]
                },
                'expected': ConfigError,
            },
        ]
        for case in tests:
            with self.subTest(msg = case['name']):
                if case['expected'] is not None:
                    with self.assertRaises(case['expected']):
                        ntp.verify(case['config'])
                else:
                    ntp.verify(case['config'])

    def test_generate(self):
        tests = [
            {
                'name': 'empty',
                'config': None,
                'expected': '',
            },
            {
                'name': 'valid',
                'config': {
                    'allowed_networks': [
                        {
                            'address': ipaddress.ip_address('192.0.2.1'),
                            'netmask': ipaddress.ip_address('255.255.255.0'),
                            'network': '192.0.2.0/24',
                        },
                        {
                            'address': ipaddress.ip_address('198.51.100.1'),
                            'netmask': ipaddress.ip_address('255.255.255.0'),
                            'network': '198.51.100.0/24',
                        },
                    ],
                    'listen_address': ['198.51.100.0/24'],
                    'servers': [
                        {'name': '1.example.com', 'options': ['noselect', 'preempt', 'prefer']},
                        {'name': '2.example.com', 'options': []},
                    ]
                },
                'expected': textwrap.dedent('''
                    ### Autogenerated by ntp.py ###

                    #
                    # Non-configurable defaults
                    #
                    driftfile /var/lib/ntp/ntp.drift
                    # By default, only allow ntpd to query time sources, ignore any incoming requests
                    restrict default noquery nopeer notrap nomodify
                    # Local users have unrestricted access, allowing reconfiguration via ntpdc
                    restrict 127.0.0.1
                    restrict -6 ::1


                    #
                    # Configurable section
                    #

                    # Server configuration for: 1.example.com
                    server 1.example.com iburst noselect preempt prefer

                    # Server configuration for: 2.example.com
                    server 2.example.com iburst 



                    # Client configuration for network: 192.0.2.0/24
                    restrict 192.0.2.1 mask 255.255.255.0 nomodify notrap nopeer
                    
                    # Client configuration for network: 198.51.100.0/24
                    restrict 198.51.100.1 mask 255.255.255.0 nomodify notrap nopeer



                    # NTP should listen on configured addresses only
                    interface ignore wildcard
                    interface listen 198.51.100.0/24

                '''),
            },
        ]

        for case in tests:
            with self.subTest(msg = case['name']):
                with tempfile.NamedTemporaryFile() as fp:
                    ntp.config_file = fp.name

                    ntp.generate(case['config'])
                    actual = fp.file.read().decode('ascii')
                    # print(actual)
                    self.assertEqual(case['expected'], actual)

    def test_apply(self):
        with tempfile.NamedTemporaryFile(delete = False) as fp:
            ntp.config_file = fp.name
            with mock.patch('os.system') as os_system:
                ntp.apply({}) # some configure
                os_system.assert_has_calls([
                    mock.call('sudo systemctl restart ntp.service'),
                ])
                self.assertTrue(os.path.exists(fp.name))
                
                ntp.apply(None) # empty configure
                os_system.assert_has_calls([
                    mock.call('sudo systemctl stop ntp.service'),
                ])
                self.assertFalse(os.path.exists(fp.name))

if __name__ == "__main__":
    unittest.main()
