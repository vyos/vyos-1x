# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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
from unittest.mock import patch

from vyos.utils.io import ask_yes_no


class TestVyOSUtilsIO(unittest.TestCase):
    def test_ask_yes_no_non_interactive_returns_default_without_reading_stdin(self):
        # T9185: on a non-TTY stdin (e.g. a non-interactive vbash session),
        # input() raises EOFError immediately and forever; ask_yes_no() must
        # return the default straight away instead of ever looping on input().
        with patch('sys.stdin') as mock_stdin:
            mock_stdin.isatty.return_value = False
            with patch('builtins.input') as mock_input:
                self.assertTrue(ask_yes_no('Proceed?', default=True))
                self.assertFalse(ask_yes_no('Proceed?', default=False))
                mock_input.assert_not_called()

    def test_ask_yes_no_interactive_reads_input(self):
        with patch('sys.stdin') as mock_stdin:
            mock_stdin.isatty.return_value = True
            with patch('builtins.input', return_value='y'):
                self.assertTrue(ask_yes_no('Proceed?', default=False))
            with patch('builtins.input', return_value='n'):
                self.assertFalse(ask_yes_no('Proceed?', default=True))
            with patch('builtins.input', return_value=''):
                self.assertTrue(ask_yes_no('Proceed?', default=True))
                self.assertFalse(ask_yes_no('Proceed?', default=False))


if __name__ == '__main__':
    unittest.main()
