#!/usr/bin/env python3
#
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

import unittest

from base_interfaces_test import BasicInterfaceTest
from base_interfaces_test import is_mirrored_to
from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError


class DummyInterfaceTest(BasicInterfaceTest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._base_path = ['interfaces', 'dummy']
        cls._interfaces = ['dum435', 'dum8677', 'dum0931', 'dum089']
        cls._mirror_interfaces = ['eth0']
        # call base-classes classmethod
        super(DummyInterfaceTest, cls).setUpClass()

    def test_mirror_redirect_target_delete(self):
        # T9491: a mirror or redirect target must not be deleted while still
        # in use, otherwise the source interface fails to load on next boot
        target = 'dum9491'

        # Target first, in its own commit, so the sources never see it missing
        self.cli_set(self._base_path + [target])
        self.cli_commit()

        self.cli_set(self._base_path + ['dum435', 'mirror', 'ingress', target])
        self.cli_set(self._base_path + ['dum0931', 'mirror', 'egress', target])
        self.cli_set(self._base_path + ['dum089', 'redirect', target])
        self.cli_commit()

        # Check ingress (qdisc ffff:) and egress (qdisc 1:) mirror filters
        self.assertTrue(is_mirrored_to('dum435', target, 'ffff'))
        self.assertTrue(is_mirrored_to('dum0931', target, '1'))

        # Deleting the target while it is still in use must be refused
        self.cli_delete(self._base_path + [target])
        with self.assertRaises(ConfigSessionError) as cm:
            self.cli_commit()
        self.assertIn('is required by', str(cm.exception))

        # The target delete from above is still pending - removing all of its
        # sources in the same commit makes it valid
        self.cli_delete(self._base_path + ['dum435'])
        self.cli_delete(self._base_path + ['dum0931'])
        self.cli_delete(self._base_path + ['dum089'])
        self.cli_commit()


if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
