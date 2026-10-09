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
from vyos.configtree import get_lib
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

    def test_concurrent_parse_threads(self):
        # libvyosconfig is not safe for concurrent entry; without the lock in
        # vyos.configtree, parsing from several threads at once corrupts the
        # parser state and crashes the process with SIGSEGV.
        config_str = self.ct.to_string()
        deadline = time.time() + 5

        def task():
            while time.time() < deadline:
                ct = ConfigTree(config_str)
                self.assertEqual(self.ct, ct)
                del ct

        threads = [threading.Thread(target=task) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    def test_parse_error_per_thread(self):
        # The library reports errors through one global buffer. Each thread
        # must see the error for its own failed call, not text left behind by
        # another thread's call.
        config_str = self.ct.to_string()
        invalid_str = 'interfaces {\n    ethernet eth0 {\n        address \n'
        deadline = time.time() + 5

        def valid_task():
            while time.time() < deadline:
                ConfigTree(config_str)

        def invalid_task():
            while time.time() < deadline:
                with self.assertRaisesRegex(ValueError, 'Syntax error'):
                    ConfigTree(invalid_str)

        threads = [
            threading.Thread(target=valid_task),
            threading.Thread(target=invalid_task),
            threading.Thread(target=valid_task),
            threading.Thread(target=invalid_task),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    def test_parse_error_survives_destroy(self):
        # ConfigTree.__del__ can call destroy between a failed call and the
        # caller's get_error(); that must not replace the captured error.
        config_str = self.ct.to_string().encode()
        lib = get_lib()
        deadline = time.time() + 5

        def valid_task():
            while time.time() < deadline:
                ConfigTree(config_str.decode())

        def error_task():
            while time.time() < deadline:
                tree = lib.from_string(config_str)
                self.assertIsNotNone(tree)
                self.assertIsNone(lib.from_string(b'interfaces {\n    address \n'))
                lib.destroy(tree)
                self.assertIn('Syntax error', lib.get_error().decode())

        threads = [
            threading.Thread(target=valid_task),
            threading.Thread(target=error_task),
            threading.Thread(target=valid_task),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()


if __name__ == '__main__':
    unittest.main()
