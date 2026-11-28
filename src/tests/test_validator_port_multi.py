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
import tempfile
import unittest
from unittest.mock import patch

from helper import prepare_module

port_multi = prepare_module(
    os.path.join(os.path.dirname(__file__), '../validators/port-multi'), 'port_multi'
)

SERVICES = """\
# Network services, Internet style
tcpmux\t\t1/tcp\t\t\t\t# TCP port service multiplexer
echo\t\t7/tcp
echo\t\t7/udp
ssh\t\t22/tcp\t\t\t\t# SSH Remote Login Protocol
smtp\t\t25/tcp\t\tmail
"""


class TestPortMulti(unittest.TestCase):
    def test_get_services(self):
        with tempfile.NamedTemporaryFile('w') as f:
            f.write(SERVICES)
            f.flush()
            with patch.object(port_multi, 'services_file', f.name):
                services = port_multi.get_services()
        self.assertEqual(services, ['tcpmux', 'echo', 'ssh', 'smtp', 'mail'])
