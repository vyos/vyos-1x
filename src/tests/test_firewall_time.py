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

from vyos.firewall import parse_time

class TestFirewallParseTime(TestCase):
    def test_hour_window(self):
        self.assertEqual(parse_time({'starttime': '08:00', 'stoptime': '17:00'}),
                         'hour "08:00"-"17:00"')

    def test_hour_window_overnight(self):
        self.assertEqual(parse_time({'starttime': '22:00', 'stoptime': '06:00'}),
                         'hour "22:00"-"06:00"')

    def test_hour_start_only(self):
        self.assertEqual(parse_time({'starttime': '01:00'}),
                         'hour "01:00"-"23:59:59"')

    def test_hour_stop_only(self):
        self.assertEqual(parse_time({'stoptime': '17:00'}),
                         'hour "00:00"-"17:00"')

    def test_date_and_time(self):
        self.assertEqual(parse_time({'startdate': '2026-01-01', 'starttime': '08:00:00',
                                     'stopdate': '2026-12-31', 'stoptime': '18:00:00'}),
                         'time >= "2026-01-01 08:00:00" time < "2026-12-31 18:00:00"')

    def test_startdate_with_daily_stoptime(self):
        self.assertEqual(parse_time({'startdate': '2026-01-01', 'stoptime': '18:00'}),
                         'time >= "2026-01-01" hour "00:00"-"18:00"')
