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

from vyos import ConfigError
from vyos import frrender
from vyos.defaults import directories
from vyos.frrender import FRRender
from vyos.frrender import drop_conflicting_discard_routes
from vyos.frrender import get_dhcp_route_interfaces

# generate() only renders known protocols, so this renders an empty file but
# still differs from the empty cache of a new instance
config = {'smoketest': {'key': 'value'}}


class TestFRRenderCache(TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)

        applied = patch.object(
            frrender, 'frr_applied_config_file', os.path.join(tmp.name, 'applied')
        )
        applied.start()
        self.addCleanup(applied.stop)

        # a failed reload waits two seconds before the next try
        sleep = patch.object(frrender, 'sleep')
        sleep.start()
        self.addCleanup(sleep.stop)

        # exit codes of frr-reload.py --test and frr-reload.py --reload
        self.rc = {'test': 0, 'reload': 0}

        def rc_cmd(cmdline):
            return self.rc['test' if '--test' in cmdline else 'reload'], 'smoketest'

        rc = patch.object(frrender, 'rc_cmd', side_effect=rc_cmd)
        rc.start()
        self.addCleanup(rc.stop)

        self.frr = FRRender()
        self.frr._frr_conf = os.path.join(tmp.name, 'frr.conf')

    def test_applied_configuration_is_cached(self):
        self.assertTrue(self.frr.generate(config))
        self.frr.apply()
        self.assertFalse(self.frr.generate(config))

    def test_rendered_but_not_applied_configuration_is_not_cached(self):
        self.assertTrue(self.frr.generate(config))
        self.assertTrue(self.frr.generate(config))

    def test_failed_reload_test_is_not_cached(self):
        self.rc['test'] = 1
        self.assertTrue(self.frr.generate(config))
        with self.assertRaises(ConfigError):
            self.frr.apply()
        self.assertTrue(self.frr.generate(config))

    def test_failed_reload_is_not_cached(self):
        self.rc['reload'] = 1
        self.assertTrue(self.frr.generate(config))
        with self.assertRaises(ConfigError):
            self.frr.apply()
        self.assertTrue(self.frr.generate(config))

    def test_retry_after_failure_is_applied(self):
        self.rc['reload'] = 1
        self.assertTrue(self.frr.generate(config))
        with self.assertRaises(ConfigError):
            self.frr.apply()

        # FRR is back, the same commit must reach it now
        self.rc['reload'] = 0
        self.assertTrue(self.frr.generate(config))
        self.frr.apply()
        self.assertFalse(self.frr.generate(config))

    def test_failed_reload_forgets_the_applied_configuration(self):
        # A is applied, the reload of B fails partway. FRR may run a part of B,
        # so going back to A must reload FRR
        self.assertTrue(self.frr.generate(config))
        self.frr.apply()
        self.assertFalse(self.frr.generate(config))

        self.rc['reload'] = 1
        self.assertTrue(self.frr.generate({'smoketest': {'key': 'other'}}))
        with self.assertRaises(ConfigError):
            self.frr.apply()

        self.rc['reload'] = 0
        self.assertTrue(self.frr.generate(config))
        self.frr.apply()
        self.assertFalse(self.frr.generate(config))

    def test_failed_reload_test_keeps_the_applied_configuration(self):
        # frr-reload.py --test changes nothing, FRR still runs A and going back
        # to A needs no reload
        self.assertTrue(self.frr.generate(config))
        self.frr.apply()

        self.rc['test'] = 1
        self.assertTrue(self.frr.generate({'smoketest': {'key': 'other'}}))
        with self.assertRaises(ConfigError):
            self.frr.apply()

        self.assertFalse(self.frr.generate(config))

    def test_reload_succeeding_on_the_last_try_is_applied(self):
        tries = []

        def rc_cmd(cmdline):
            if '--test' in cmdline:
                return 0, 'smoketest'
            tries.append(cmdline)
            return (0 if len(tries) == 5 else 1), 'smoketest'

        with patch.object(frrender, 'rc_cmd', side_effect=rc_cmd):
            self.assertTrue(self.frr.generate(config))
            self.frr.apply()
        self.assertEqual(len(tries), 5)
        self.assertFalse(self.frr.generate(config))


class TestDropConflictingDiscardRoutes(TestCase):
    def drop(self, lines):
        output, messages = drop_conflicting_discard_routes('\n'.join(lines))
        return output.splitlines(), messages

    def test_no_conflict(self):
        lines = ['!',
                 'ip route 0.0.0.0/0 blackhole 200',
                 'ip route 0.0.0.0/0 pppoe0 tag 210 ',
                 'ip route 10.0.0.0/8 blackhole',
                 'ip route 10.0.0.0/8 192.0.2.1 tag 5 10',
                 'ip mroute 224.1.0.0/24 eth0 1',
                 '!']
        self.assertEqual(self.drop(lines), (lines, []))

    def test_pppoe_default_route(self):
        # rendered without a distance, so both use distance 1
        output, messages = self.drop(['ip route 0.0.0.0/0 blackhole',
                                      'ip route 0.0.0.0/0 pppoe0 tag 210 '])
        self.assertEqual(output, ['ip route 0.0.0.0/0 pppoe0 tag 210 '])
        self.assertEqual(len(messages), 1)
        self.assertIn('"ip route 0.0.0.0/0 blackhole"', messages[0])

    def test_dhcp_default_route_distance(self):
        output, _ = self.drop(['ip route 0.0.0.0/0 reject tag 5 210',
                               'ip route 0.0.0.0/0 192.0.2.1 eth0 tag 210 210'])
        self.assertEqual(output, ['ip route 0.0.0.0/0 192.0.2.1 eth0 tag 210 210'])

    def test_explicit_default_distance(self):
        output, _ = self.drop(['ipv6 route ::/0 blackhole 1',
                               'ipv6 route ::/0 pppoe0 tag 210 '])
        self.assertEqual(output, ['ipv6 route ::/0 pppoe0 tag 210 '])

    def test_vrf(self):
        # the default route of an interface in a VRF is rendered into it, with
        # a double space after "ip"
        lines = ['vrf red',
                 ' ip route 0.0.0.0/0 blackhole 210',
                 ' ip  route 0.0.0.0/0 192.0.2.1 eth1 tag 210 210',
                 'exit-vrf',
                 '!',
                 'ip route 0.0.0.0/0 blackhole 210']
        output, messages = self.drop(lines)
        self.assertEqual(output, [lines[0], lines[2], lines[3], lines[4], lines[5]])
        self.assertIn('in VRF "red"', messages[0])

    def test_table(self):
        lines = ['ip route 0.0.0.0/0 blackhole table 100',
                 'ip route 0.0.0.0/0 192.0.2.1 eth0 table 100',
                 'ip route 0.0.0.0/0 blackhole table 200',
                 'ip route 0.0.0.0/0 pppoe0 tag 210 ']
        output, messages = self.drop(lines)
        self.assertEqual(output, lines[1:])
        self.assertIn('in table 100', messages[0])

    def test_options(self):
        # option values must not be taken for the distance
        lines = ['ip route 10.0.0.0/8 blackhole tag 20',
                 'ip route 10.0.0.0/8 192.0.2.1 bfd multi-hop source 192.0.2.10 '
                 'profile 20 nexthop-vrf blue',
                 'ip route 10.1.0.0/16 blackhole 20',
                 'ip route 10.1.0.0/16 eth0 tag 20 30']
        output, _ = self.drop(lines)
        self.assertEqual(output, lines[1:])

    def test_spelling(self):
        # FRR stores both as the same route
        output, _ = self.drop(['ipv6 route 2001:db8::/32 blackhole',
                               'ipv6 route 2001:0db8::1/32 2001:db8::1'])
        self.assertEqual(output, ['ipv6 route 2001:0db8::1/32 2001:db8::1'])

    def test_only_discard_routes(self):
        lines = ['ip route 10.0.0.0/8 blackhole', 'ip route 10.0.0.0/8 reject 5']
        self.assertEqual(self.drop(lines), (lines, []))


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

        # generate() only reports an unchanged configuration once apply()
        # had FRR take it
        for patcher in [
            patch.object(
                frrender,
                'frr_applied_config_file',
                os.path.join(self.tmpdir, 'applied'),
            ),
            patch.object(frrender, 'rc_cmd', return_value=(0, 'smoketest')),
        ]:
            patcher.start()
            self.addCleanup(patcher.stop)

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
        self.frr.apply()
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
