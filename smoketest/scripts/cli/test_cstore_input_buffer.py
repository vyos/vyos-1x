#!/usr/bin/env python3
#
# Copyright (C) VyOS Inc.
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
import unittest

from base_vyostest_shim import VyOSUnitTestSHIM
from vyos.configsession import ConfigSessionError
from vyos.configtree import ConfigTree

base_path = ['system', 'login', 'banner']
value_path = base_path + ['pre-login']
marker_path = base_path + ['post-login']

# MAX_PATH_COMP_SIZE in vyatta-cfg cstore
max_value_size = 8192
error_message = f'exceeds the maximum length of {max_value_size} characters'

# the config file parser used to grow its buffer by 4096 bytes once, no matter
# how long the value was, and corrupted the heap on anything longer (T9623)
value_sizes = [4095, 4096, 4097, 6380, max_value_size]

save_file = '/tmp/smoketest-cstore-input-buffer'
reload_file = '/tmp/smoketest-cstore-input-buffer-reload'

class TestCstoreInputBuffer(VyOSUnitTestSHIM.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestCstoreInputBuffer, cls).setUpClass()
        # ensure we can also run this test on a live system - so lets clean
        # out the current configuration :)
        cls.cli_delete(cls, base_path)

    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()
        for file in [save_file, reload_file]:
            if os.path.exists(file):
                os.remove(file)
        # always forward to base class
        super().tearDown()

    def assertSetRejected(self, path):
        with self.assertRaises(ConfigSessionError) as e:
            self.cli_set(path)
        self.assertIn(error_message, ' '.join(str(e.exception).split()))

    def test_value_size_limit(self):
        self.cli_set(value_path + ['A' * max_value_size])
        self.cli_commit()

        self.assertSetRejected(value_path + ['B' * (max_value_size + 1)])
        self.assertSetRejected(value_path + ['B' * 100000])
        # tag node names are bound by the same limit
        self.assertSetRejected(['interfaces', 'dummy', 'b' * (max_value_size + 1)])

        # the rejected set must leave the committed value alone
        self.cli_commit()
        self._session.save_config(save_file)
        with open(save_file) as f:
            ct = ConfigTree(f.read())
        self.assertEqual('A' * max_value_size, ct.return_value(value_path))

    def test_value_save_load(self):
        for size in value_sizes:
            value = 'A' * size
            self.cli_set(value_path + [value])
            self.cli_commit()
            self._session.save_config(save_file)

            self.cli_delete(base_path)
            self.cli_commit()

            # same code path as "load" in configuration mode
            self._session.migrate_and_load_config(save_file)
            self.cli_commit()

            self._session.save_config(reload_file)
            with open(reload_file) as f:
                ct = ConfigTree(f.read())
            self.assertEqual(value, ct.return_value(value_path), msg=f'size {size}')

            self.cli_delete(base_path)
            self.cli_commit()

    def test_oversized_value_in_file(self):
        self.cli_set(value_path + ['A' * max_value_size])
        self.cli_set(marker_path + ['smoketest'])
        self.cli_commit()
        self._session.save_config(save_file)

        # a hand edited file is the only way past "set"
        with open(save_file) as f:
            config = f.read()
        self.assertIn('A' * max_value_size, config)
        config = config.replace('A' * max_value_size, 'A' * (max_value_size + 1))
        with open(save_file, 'w') as f:
            f.write(config)

        self.cli_delete(base_path)
        self.cli_commit()

        # only the oversized node is dropped, the remainder of the file loads
        self._session.migrate_and_load_config(save_file)
        self.cli_commit()

        self._session.save_config(reload_file)
        with open(reload_file) as f:
            ct = ConfigTree(f.read())
        self.assertFalse(ct.exists(value_path))
        self.assertEqual('smoketest', ct.return_value(marker_path))

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=VyOSUnitTestSHIM.TestCase.debug_on())
