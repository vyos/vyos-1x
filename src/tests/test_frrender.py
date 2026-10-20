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

from vyos import ConfigError
from vyos import frrender
from vyos.frrender import FRRender

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
