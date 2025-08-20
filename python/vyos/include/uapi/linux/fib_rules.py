# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

FIB_RULE_PERMANENT = 0x00000001
FIB_RULE_INVERT = 0x00000002
FIB_RULE_UNRESOLVED = 0x00000004
FIB_RULE_IIF_DETACHED = 0x00000008
FIB_RULE_DEV_DETACHED = FIB_RULE_IIF_DETACHED
FIB_RULE_OIF_DETACHED = 0x00000010
