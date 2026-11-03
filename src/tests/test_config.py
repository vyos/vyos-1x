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

from unittest import TestCase
from unittest.mock import MagicMock

from vyos.config import Config
from vyos.configsource import ConfigSourceSession


class TestPathAttrFunc(TestCase):
    def _call_func(self, func_name):
        mock_config_source = MagicMock(spec=ConfigSourceSession)
        mock_config_source.get_configtree_tuple.return_value = (None, None)
        config = Config(config_source=mock_config_source)

        func = getattr(config, func_name)
        func(['some', 'path'])
        mock_config_source.set_level.assert_called_once()

        args, _ = mock_config_source.set_level.call_args
        return args[0]

    def test_is_multi_level_arg(self):
        res = self._call_func('is_multi')
        self.assertEqual(type(res), list)

    def test_is_tag_level_arg(self):
        res = self._call_func('is_tag')
        self.assertEqual(type(res), list)

    def test_is_leaf_level_arg(self):
        res = self._call_func('is_leaf')
        self.assertEqual(type(res), list)
