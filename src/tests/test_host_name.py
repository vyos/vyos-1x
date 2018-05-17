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

from vyos import ConfigError
try:
    from src.conf_mode import host_name
except ModuleNotFoundError:  # for unittest.main()
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
    from src.conf_mode import host_name


class TestHostName(TestCase):

    def test_get_config(self):
        tests = [
            {'name': 'empty_hostname_and_domain',
             'host-name': '',
             'domain-name': '',
             'expected': {"hostname": 'vyos', "domain": '', "fqdn": 'vyos'}},
            {'name': 'empty_hostname',
             'host-name': '',
             'domain-name': 'localdomain',
             'expected': {"hostname": 'vyos', "domain": 'localdomain', "fqdn": 'vyos.localdomain'}},
            {'name': 'has_hostname',
             'host-name': 'router',
             'domain-name': '',
             'expected': {"hostname": 'router', "domain": '', "fqdn": 'router'}},
            {'name': 'has_hostname_and_domain',
             'host-name': 'router',
             'domain-name': 'localdomain',
             'expected': {"hostname": 'router', "domain": 'localdomain', "fqdn": 'router.localdomain'}},
        ]
        for t in tests:
            def mocked_return_value(path, default=None):
                return t[path.split()[1]]

            with self.subTest(msg=t['name'], hostname=t['host-name'], domain=t['domain-name'], expected=t['expected']):
                with mock.patch('vyos.config.Config.return_value', side_effect=mocked_return_value):
                    actual = host_name.get_config()
                    self.assertEqual(actual, t['expected'])


    def test_verify(self):
        tests = [
            {'name': 'valid_hostname',
             'config': {"hostname": 'vyos', "domain": 'localdomain', "fqdn": 'vyos.localdomain'},
             'expected': None},
            {'name': 'invalid_hostname',
             'config': {"hostname": 'vyos..', "domain": '', "fqdn": ''},
             'expected': ConfigError},
            {'name': 'invalid_hostname_length',
             'config': {"hostname": 'a'*64, "domain": '', "fqdn": ''},
             'expected': ConfigError}
        ]
        for t in tests:
            with self.subTest(msg=t['name'], config=t['config'], expected=t['expected']):
                if t['expected'] is not None:
                    with self.assertRaises(t['expected']):
                        host_name.verify(t['config'])
                else:
                    host_name.verify(t['config'])

    def test_generate(self):
        tests = [
            {'name': 'has_old_entry',
             'has_old_entry': True,
             'config': {"hostname": 'router', "domain": 'localdomain', "fqdn": 'router.localdomain'},
             'expected': ['127.0.1.1', 'router.localdomain']},
            {'name': 'no_old_entry',
             'has_old_entry': False,
             'config': {"hostname": 'router', "domain": 'localdomain', "fqdn": 'router.localdomain'},
             'expected': ['127.0.1.1', 'router.localdomain']},
        ]
        for t in tests:
            with self.subTest(msg=t['name'], config=t['config'], has_old_entry=t['has_old_entry'],  expected=t['expected']):
                m = mock.MagicMock(return_value=b'debian')
                with mock.patch('subprocess.check_output', m):
                    host_name.hosts_file = tempfile.mkstemp()[1]
                    if t['has_old_entry']:
                        with open(host_name.hosts_file, 'w') as f:
                            f.writelines(['\n127.0.1.1 {} # VyOS entry'.format('debian')])
                    host_name.generate(t['config'])
                    if len(t['expected']) > 0:
                        self.assertTrue(os.path.isfile(host_name.hosts_file))
                        with open(host_name.hosts_file) as f:
                            actual = f.read()
                            self.assertEqual(
                                t['expected'], actual.splitlines()[1].split()[0:2])
                        os.remove(host_name.hosts_file)
                    else:
                        self.assertFalse(os.path.isfile(host_name.hosts_file))


    def test_apply(self):
        tests = [
            {'name': 'valid_hostname',
             'config': {"hostname": 'router', "domain": 'localdomain', "fqdn": 'vyos.localdomain'},
             'expected': [mock.call('hostnamectl set-hostname vyos.localdomain'),
                          mock.call('systemctl restart rsyslog.service')]}
        ]
        for t in tests:
            with self.subTest(msg=t['name'], c=t['config'], expected=t['expected']):
                with mock.patch('os.system') as os_system:
                    host_name.apply(t['config'])
                    os_system.assert_has_calls(t['expected'])


if __name__ == "__main__":
    unittest.main()
