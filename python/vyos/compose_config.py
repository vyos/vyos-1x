# Copyright 2024 VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>.

"""This module allows iterating over function calls to modify an existing
config.
"""

from pathlib import Path
from typing import TypeAlias, Union, Callable

from vyos.configtree import ConfigTree
from vyos.configtree import deep_copy as ct_deep_copy
from vyos.utils.system import load_as_module

ConfigObj: TypeAlias = Union[str, ConfigTree]

class ComposeConfigError(Exception):
    """Raised when an error occurs modifying a config object.
    """

class ComposeConfig:
    """Apply function to config tree: for iteration over functions or files.
    """
    def __init__(self, config_obj: ConfigObj, checkpoint_file=None):
        if isinstance(config_obj, ConfigTree):
            self.config_tree = config_obj
        else:
            self.config_tree = ConfigTree(config_obj)

        self.checkpoint = self.config_tree
        self.checkpoint_file = checkpoint_file

    def apply_func(self, func: Callable):
        """Apply the function to the config tree.
        """
        if not callable(func):
            raise ComposeConfigError(f'{func.__name__} is not callable')

        if self.checkpoint_file is not None:
            self.checkpoint = ct_deep_copy(self.config_tree)

        try:
            func(self.config_tree)
        except Exception as e:
            self.config_tree = self.checkpoint
            raise ComposeConfigError(e) from e

    def apply_file(self, func_file: str, func_name: str):
        """Apply named function from file.
        """
        try:
            mod_name = Path(func_file).stem.replace('-', '_')
            mod = load_as_module(mod_name, func_file)
            func = getattr(mod, func_name)
        except Exception as e:
            raise ComposeConfigError(f'Error with {func_file}: {e}') from e

        try:
            self.apply_func(func)
        except ComposeConfigError as e:
            raise ComposeConfigError(f'Error in {func_file}: {e}') from e

    def to_string(self, with_version=False) -> str:
        """Return the rendered config tree.
        """
        return self.config_tree.to_string(no_version=not with_version)

    def write(self, config_file: str, with_version=False):
        """Write the config tree to a file.
        """
        config_str = self.to_string(with_version=with_version)
        Path(config_file).write_text(config_str)
