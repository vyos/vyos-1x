#!/bin/bash
#
# Copyright (C) VyOS maintainers and contributors
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
# This script is completion helper to list all configured SRv6 locators that
# are visible to FRR

seg6LocatorsJson=$(vtysh -c 'show segment-routing srv6 locator json')
echo "$(echo "$seg6LocatorsJson" | jq -r '[.locators[].name][]')"
