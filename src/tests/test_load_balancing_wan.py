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

from helper import prepare_module

wlb = prepare_module(
    os.path.join(os.path.dirname(__file__), '../conf_mode/load-balancing_wan.py'),
    'load_balancing_wan',
)


class TestLoadBalancingWan(unittest.TestCase):
    def test_empty_group_warning(self):
        lb = {
            'interface_health': {'eth0': {'nexthop': 'dhcp'}},
            'rule': {
                '10': {
                    'interface': {'eth0': {}},
                    'source': {'group': {'address_group': 'EMPTY'}},
                }
            },
            'firewall_group': {'address_group': {'EMPTY': {}}},
        }
        with patch('vyos.base.print') as mock_print:
            wlb.verify(lb)
        self.assertIn(
            'address-group "EMPTY" has no members!', str(mock_print.call_args_list)
        )
