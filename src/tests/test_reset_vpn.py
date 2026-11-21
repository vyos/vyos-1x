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

import os
import unittest
from unittest.mock import patch

from vyos.opmode import IncorrectValue

from helper import prepare_module

reset_vpn = prepare_module(
    os.path.join(os.path.dirname(__file__), '../op_mode/reset_vpn.py'), 'reset_vpn'
)


class TestResetVPN(unittest.TestCase):
    @patch.object(reset_vpn, 'run')
    def test_unknown_protocol(self, mock_run):
        with self.assertRaises(IncorrectValue):
            reset_vpn.reset_conn('openvpn')
        mock_run.assert_not_called()

    @patch.object(reset_vpn, 'run')
    def test_known_protocol(self, mock_run):
        reset_vpn.reset_conn('l2tp', username='alice')
        mock_run.assert_called_once_with(
            '/usr/bin/accel-cmd -p 2004 terminate username alice'
        )


if __name__ == '__main__':
    unittest.main()
