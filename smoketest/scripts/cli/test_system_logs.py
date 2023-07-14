#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
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

# path to logrotate configs
logrotate_atop_file = '/etc/logrotate.d/vyos-atop'
logrotate_rsyslog_file = '/etc/logrotate.d/vyos-rsyslog'
# default values
default_atop_maxsize = '10M'
default_atop_rotate = '10'
default_rsyslog_size = '1M'
default_rsyslog_rotate = '10'

base_path = ['system', 'logs']


def logrotate_config_parse(file_path):
    # read the file
    logrotate_config = read_file(file_path)
    # create regex for parsing options
    regex_options = re.compile(
        r'(^\s+(?P<option_name_script>postrotate|prerotate|firstaction|lastaction|preremove)\n(?P<option_value_script>((?!endscript).)*)\n\s+endscript\n)|(^\s+(?P<option_name>[\S]+)([ \t]+(?P<option_value>\S+))*$)',
        re.M | re.S)
    # create empty dict for config
    logrotate_config_dict = {}
    # fill dictionary with actual config
    for option in regex_options.finditer(logrotate_config):
        option_name = option.group('option_name')
        option_value = option.group('option_value')
        option_name_script = option.group('option_name_script')
        option_value_script = option.group('option_value_script')
        if option_name:
            logrotate_config_dict[option_name] = option_value
        if option_name_script:
            logrotate_config_dict[option_name_script] = option_value_script

    # return config dictionary
    return (logrotate_config_dict)


class TestSystemLogs(VyOSUnitTestSHIM.TestCase):

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

    def test_logs_defaults(self):
        # test with empty section for default values
        self.cli_set(base_path)
        self.cli_commit()

        # read the config file and check content
        logrotate_config_atop = logrotate_config_parse(logrotate_atop_file)
        logrotate_config_rsyslog = logrotate_config_parse(
            logrotate_rsyslog_file)
        self.assertEqual(logrotate_config_atop['maxsize'], default_atop_maxsize)
        self.assertEqual(logrotate_config_atop['rotate'], default_atop_rotate)
        self.assertEqual(logrotate_config_rsyslog['size'], default_rsyslog_size)
        self.assertEqual(logrotate_config_rsyslog['rotate'],
                         default_rsyslog_rotate)

    def test_logs_atop_maxsize(self):
        # test for maxsize option
        self.cli_set(base_path + ['logrotate', 'atop', 'max-size', '50'])
        self.cli_commit()

        # read the config file and check content
        logrotate_config = logrotate_config_parse(logrotate_atop_file)
        self.assertEqual(logrotate_config['maxsize'], '50M')

    def test_logs_atop_rotate(self):
        # test for rotate option
        self.cli_set(base_path + ['logrotate', 'atop', 'rotate', '50'])
        self.cli_commit()

        # read the config file and check content
        logrotate_config = logrotate_config_parse(logrotate_atop_file)
        self.assertEqual(logrotate_config['rotate'], '50')

    def test_logs_rsyslog_size(self):
        # test for size option
        self.cli_set(base_path + ['logrotate', 'messages', 'max-size', '50'])
        self.cli_commit()

        # read the config file and check content
        logrotate_config = logrotate_config_parse(logrotate_rsyslog_file)
        self.assertEqual(logrotate_config['size'], '50M')

    def test_logs_rsyslog_rotate(self):
        # test for rotate option
        self.cli_set(base_path + ['logrotate', 'messages', 'rotate', '50'])
        self.cli_commit()

        # read the config file and check content
        logrotate_config = logrotate_config_parse(logrotate_rsyslog_file)
        self.assertEqual(logrotate_config['rotate'], '50')


if __name__ == '__main__':
    unittest.main(verbosity=2)
