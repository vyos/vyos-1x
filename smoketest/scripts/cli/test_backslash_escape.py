#!/usr/bin/env python3
#
# Copyright (C) 2024 VyOS maintainers and contributors
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
from vyos.configtree import ConfigTree

base_path = ['interfaces', 'ethernet', 'eth0', 'description']

cases_word = [r'fo\o', r'fo\\o', r'foço\o', r'foço\\o']
# legacy CLI output quotes only if whitespace present; this is a notable
# difference that confounds the translation legacy -> modern, hence
# determines the regex used in function replace_backslash
cases_phrase = [r'some fo\o', r'some fo\\o', r'some foço\o', r'some foço\\o']

case_save_config = '/tmp/smoketest-case-save'

class TestBackslashEscape(VyOSUnitTestSHIM.TestCase):
    def test_backslash_escape_word(self):
        for case in cases_word:
            self.cli_set(base_path + [case])
            self.cli_commit()
            # save_config tests translation though subsystems:
            # legacy output -> config -> configtree -> file
            self._session.save_config(case_save_config)
            # reload to configtree and confirm:
            with open(case_save_config) as f:
                config_string = f.read()
            ct = ConfigTree(config_string)
            res = ct.return_value(base_path)
            self.assertEqual(case, res, msg=res)
            print(f'description: {res}')
            self.cli_delete(base_path)
            self.cli_commit()

    def test_backslash_escape_phrase(self):
        for case in cases_phrase:
            self.cli_set(base_path + [case])
            self.cli_commit()
            # save_config tests translation though subsystems:
            # legacy output -> config -> configtree -> file
            self._session.save_config(case_save_config)
            # reload to configtree and confirm:
            with open(case_save_config) as f:
                config_string = f.read()
            ct = ConfigTree(config_string)
            res = ct.return_value(base_path)
            self.assertEqual(case, res, msg=res)
            print(f'description: {res}')
            self.cli_delete(base_path)
            self.cli_commit()

if __name__ == '__main__':
    unittest.main(verbosity=2)
