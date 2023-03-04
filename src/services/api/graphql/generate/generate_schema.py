#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
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

from schema_from_op_mode import generate_op_mode_definitions
from schema_from_config_session import generate_config_session_definitions
from schema_from_composite import generate_composite_definitions

if __name__ == '__main__':
    generate_op_mode_definitions()
    generate_config_session_definitions()
    generate_composite_definitions()
