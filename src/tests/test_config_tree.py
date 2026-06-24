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
#
#

import os
import json
import time
import threading
import unittest
from unittest import TestCase

from vyos.configtree import ConfigTree
from vyos.referencetree import ReferenceTree
from vyos.derivedtree import subtree_from_list_of_partial_paths


class TestInitialSetup(TestCase):
    def setUp(self):
        with open('data/config.boot.default') as f:
            config_str = f.read()
            self.ct = ConfigTree(config_str)

        self.thread_exception = None
        self.orig_excepthook = threading.excepthook

        def custom_hook(args):
            self.thread_exception = args.exc_value

        threading.excepthook = custom_hook

    def tearDown(self):
        threading.excepthook = self.orig_excepthook

        if self.thread_exception:
            raise self.thread_exception

    def test_subtree_from_partial(self):
        reftree = ReferenceTree(cache_file='data/reftree.cache')

        # workaround since configtree.list_nodes does not take an empty path
        d = json.loads(self.ct.to_json())
        top_nodes = list(d)
        paths = [s.split() for s in top_nodes]

        reassemble = subtree_from_list_of_partial_paths(
            self.ct, paths, reference_tree=reftree
        )

        self.assertEqual(self.ct, reassemble)

    def test_cache_io(self):
        config_cache = '/tmp/config.cache'

        self.ct.write_cache(config_cache)
        ct_cached = ConfigTree(internal=config_cache)
        os.unlink(config_cache)

        self.assertEqual(self.ct, ct_cached)

    def test_cache_io_thread(self):
        config_cache = '/tmp/config.cache'

        def task():
            time.sleep(0.1)
            self.ct.write_cache(config_cache)
            ct_cached = ConfigTree(internal=config_cache)
            os.unlink(config_cache)

            self.assertEqual(self.ct, ct_cached)

        t = threading.Thread(target=task)
        t.start()
        t.join()


if __name__ == '__main__':
    unittest.main()
