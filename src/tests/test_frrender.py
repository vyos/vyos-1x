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

from unittest import TestCase
from unittest.mock import patch

import vyos.template

from vyos.defaults import directories
from vyos.frrender import FRRender
from vyos.frrender import get_dhcp_route_interfaces

_templates = os.path.join(os.path.dirname(__file__), '../../data/templates')

ROUTER = '192.0.2.1'
# 10.0.0.0/24 and 10.1.0.0/24 via 192.0.2.1, encoded as dhclient exports them
CLASSLESS_ROUTES_A = '24 10 0 0 192 0 2 1'
CLASSLESS_ROUTES_B = '24 10 1 0 192 0 2 1'


def _dhcp_config(no_default_route=False):
    dhcp_options = {'default_route_distance': '210'}
    if no_default_route:
        dhcp_options['no_default_route'] = {}
    return {'static': {'dhcp': {'eth0': {'dhcp_options': dhcp_options}}}}


class TestGetDhcpRouteInterfaces(TestCase):
    def test_no_default_route_interface(self):
        # An interface opting out of the default route still has its RFC 3442
        # classless static routes rendered, thus it depends on the lease
        dhcp_options = {'default_route_distance': '210', 'no_default_route': {}}
        config = {
            'static': {'dhcp': {'eth0': {'dhcp_options': dhcp_options}}},
            'vrf': {
                'name': {
                    'red': {
                        'protocols': {
                            'static': {'dhcp': {'eth1': {'dhcp_options': dhcp_options}}}
                        }
                    }
                }
            },
        }
        self.assertEqual(get_dhcp_route_interfaces(config), {'eth0', 'eth1'})


class TestFRRenderDhcpChangeDetection(TestCase):
    def setUp(self):
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        self.tmpdir = tmpdir.name

        # Lease files are read from, and the FRR configuration is rendered
        # into, the temporary directory using the templates of this repository
        for patcher in [
            patch.dict(directories, {'isc_dhclient_dir': self.tmpdir}),
            patch.object(vyos.template, 'DEFAULT_TEMPLATE_DIR', _templates),
        ]:
            patcher.start()
            self.addCleanup(patcher.stop)
        vyos.template._get_environment.cache_clear()
        self.addCleanup(vyos.template._get_environment.cache_clear)

        self.frr = FRRender()
        self.frr._frr_conf = os.path.join(self.tmpdir, 'vyos.frr.conf')

    def write_lease(self, routers, classless_routes):
        # Same format as written by 03-vyos-dhclient-hook
        with open(os.path.join(self.tmpdir, 'dhclient_eth0.lease'), 'w') as f:
            f.write('Sun Sep 13 12:00:00 UTC 2026\n')
            f.write(f"new_routers='{routers}'\n")
            f.write(f"new_rfc3442_classless_static_routes='{classless_routes}'\n")

    def rendered(self):
        with open(self.frr._frr_conf) as f:
            return f.read()

    def test_unchanged_lease(self):
        config = _dhcp_config()
        self.write_lease(ROUTER, CLASSLESS_ROUTES_A)
        self.assertTrue(self.frr.generate(config))
        self.assertFalse(self.frr.generate(config))

    def test_classless_routes_change_with_same_router(self):
        config = _dhcp_config()
        self.write_lease(ROUTER, CLASSLESS_ROUTES_A)
        self.assertTrue(self.frr.generate(config))
        self.assertIn(f'route 10.0.0.0/24 {ROUTER} eth0 tag 210', self.rendered())

        self.write_lease(ROUTER, CLASSLESS_ROUTES_B)
        self.assertTrue(self.frr.generate(config))
        self.assertIn(f'route 10.1.0.0/24 {ROUTER} eth0 tag 210', self.rendered())
        self.assertNotIn('10.0.0.0/24', self.rendered())

    def test_classless_routes_change_without_default_route(self):
        # 06-vyos-nodefaultroute clears the router option for such interfaces
        config = _dhcp_config(no_default_route=True)
        self.write_lease('', CLASSLESS_ROUTES_A)
        self.assertTrue(self.frr.generate(config))
        self.assertIn(f'route 10.0.0.0/24 {ROUTER} eth0 tag 210', self.rendered())

        self.write_lease('', CLASSLESS_ROUTES_B)
        self.assertTrue(self.frr.generate(config))
        self.assertIn(f'route 10.1.0.0/24 {ROUTER} eth0 tag 210', self.rendered())
        self.assertNotIn('10.0.0.0/24', self.rendered())
