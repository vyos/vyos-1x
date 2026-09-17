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

from unittest import TestCase
from unittest.mock import patch

import src.op_mode.show_wwan as show_wwan

class TestShowWWANDetail(TestCase):
    # T7487: 'show interfaces wwan <if> detail' used to derive the modem
    # index straight from the interface name (mmcli --modem ${4#wwan}).
    # These pin down that show_detail() instead uses whatever modem
    # get_wwan_modem_ports() resolves - so a regression back to deriving
    # the index from the interface name would fail these even though the
    # interface name and the mocked modem index happen to look similar.

    @patch('src.op_mode.show_wwan.call')
    @patch('src.op_mode.show_wwan.get_wwan_modem_ports')
    def test_show_detail_uses_resolved_modem_not_interface_number(self, mock_get_ports, mock_call):
        # Mismatched on purpose: interface 'wwan0' is owned by modem '7',
        # not modem '0' - a naive interface.lstrip('wwan') would call
        # mmcli against modem 0 instead.
        mock_get_ports.return_value = ('7', ['cdc-wdm7 (qmi)', 'wwan0 (net)'])
        mock_call.return_value = 0

        rc = show_wwan.show_detail('wwan0')

        mock_call.assert_called_once_with('mmcli --modem 7')
        self.assertEqual(rc, 0)

    @patch('src.op_mode.show_wwan.call')
    @patch('src.op_mode.show_wwan.get_wwan_modem_ports')
    def test_show_detail_no_modem_found(self, mock_get_ports, mock_call):
        mock_get_ports.return_value = (None, [])

        rc = show_wwan.show_detail('wwan0')

        mock_call.assert_not_called()
        self.assertEqual(rc, 1)

    @patch('src.op_mode.show_wwan.call')
    @patch('src.op_mode.show_wwan.get_wwan_modem_ports')
    def test_show_detail_propagates_mmcli_exit_status(self, mock_get_ports, mock_call):
        mock_get_ports.return_value = ('1', ['cdc-wdm1 (qmi)', 'wwan0 (net)'])
        mock_call.return_value = 2

        rc = show_wwan.show_detail('wwan0')

        self.assertEqual(rc, 2)
