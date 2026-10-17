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
import subprocess

from unittest import TestCase

_static_routes_exit_hook = os.path.join(
    os.path.dirname(__file__),
    '../etc/dhcp/dhclient-exit-hooks.d/98-vyos-static-routes-dhclient-hook',
)

ROUTER = '192.0.2.1'
CLASSLESS_ROUTES_A = '24 10 0 0 192 0 2 1'
CLASSLESS_ROUTES_B = '24 10 1 0 192 0 2 1'


class TestStaticRoutesExitHook(TestCase):
    def requests_update(self, **variables):
        # dhclient-script sources the hook - "sudo" is replaced to observe
        # whether an update of the FRR configuration is requested
        script = f'sudo() {{ echo "$@"; }}; source "{_static_routes_exit_hook}"'
        env = {'PATH': os.environ['PATH'], **variables}
        output = subprocess.run(
            ['bash', '-c', script], env=env, capture_output=True, text=True, check=True
        ).stdout
        return 'vyos-request-configd-update' in output

    def test_unchanged_lease(self):
        for reason in ['RENEW', 'REBIND']:
            with self.subTest(reason=reason):
                self.assertFalse(
                    self.requests_update(
                        reason=reason,
                        old_routers=ROUTER,
                        new_routers=ROUTER,
                        old_rfc3442_classless_static_routes=CLASSLESS_ROUTES_A,
                        new_rfc3442_classless_static_routes=CLASSLESS_ROUTES_A,
                    )
                )

    def test_classless_routes_change_with_same_router(self):
        for reason in ['RENEW', 'REBIND']:
            with self.subTest(reason=reason):
                self.assertTrue(
                    self.requests_update(
                        reason=reason,
                        old_routers=ROUTER,
                        new_routers=ROUTER,
                        old_rfc3442_classless_static_routes=CLASSLESS_ROUTES_A,
                        new_rfc3442_classless_static_routes=CLASSLESS_ROUTES_B,
                    )
                )
