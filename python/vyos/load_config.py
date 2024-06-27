# Copyright 2023-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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

"""This module abstracts the loading of a config file into the running
config. It provides several varieties of loading a config file, from the
legacy version to the developing versions, as a means of offering
alternatives for competing use cases, and a base for profiling the
performance of each.
"""

import sys
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Union, Literal, TypeAlias, get_type_hints, get_args

from vyos.config import Config
from vyos.configtree import ConfigTree, DiffTree
from vyos.configsource import ConfigSourceSession, VyOSError
from vyos.migrate import ConfigMigrate, ConfigMigrateError
from vyos.utils.process import popen, DEVNULL

Variety: TypeAlias = Literal['explicit', 'batch', 'tree', 'legacy']
ConfigObj: TypeAlias = Union[str, ConfigTree]

thismod = sys.modules[__name__]

class LoadConfigError(Exception):
    """Raised when an error occurs loading a config file.
    """

# utility functions

def get_running_config(config: Config) -> ConfigTree:
    return config.get_config_tree(effective=True)

def get_proposed_config(config_file: str = None) -> ConfigTree:
    config_str = Path(config_file).read_text()
    return ConfigTree(config_str)

def check_session(strict: bool, switch: Variety) -> None:
    """Check if we are in a config session, with no uncommitted changes, if
    strict. This is not needed for legacy load, as these checks are
    implicit.
    """

    if switch == 'legacy':
        return

    context = ConfigSourceSession()

    if not context.in_session():
        raise LoadConfigError('not in a config session')

    if strict and context.session_changed():
        raise LoadConfigError('commit or discard changes before loading config')

# methods to call for each variety

# explicit
def diff_to_commands(ctree: ConfigTree, ntree: ConfigTree) -> list:
    """Calculate the diff between the current and proposed config."""
    # Calculate the diff between the current and new config tree
    commands = DiffTree(ctree, ntree).to_commands()
    # on an empty set of 'add' or 'delete' commands, to_commands
    # returns '\n'; prune below
    command_list = commands.splitlines()
    command_list = [c for c in command_list if c]
    return command_list

def set_commands(cmds: list) -> None:
    """Set commands in the config session."""
    if not cmds:
        print('no commands to set')
        return
    error_out = []
    for op in cmds:
        out, rc = popen(f'/opt/vyatta/sbin/my_{op}', shell=True, stderr=DEVNULL)
        if rc != 0:
            error_out.append(out)
            continue
    if error_out:
        out = '\n'.join(error_out)
        raise LoadConfigError(out)

# legacy
class LoadConfig(ConfigSourceSession):
    """A subclass for calling 'loadFile'.
    """
    def load_config(self, file_name):
        return self._run(['/bin/cli-shell-api','loadFile', file_name])

# end methods to call for each variety

def migrate(config_obj: ConfigObj) -> ConfigObj:
    """Migrate a config object to the current version.
    """
    if isinstance(config_obj, ConfigTree):
        config_file = NamedTemporaryFile(delete=False).name
        Path(config_file).write_text(config_obj.to_string())
    else:
        config_file = config_obj

    config_migrate = ConfigMigrate(config_file)
    try:
        config_migrate.run()
    except ConfigMigrateError as e:
        raise LoadConfigError(e) from e
    else:
        if isinstance(config_obj, ConfigTree):
            return ConfigTree(Path(config_file).read_text())
        return config_file
    finally:
        if isinstance(config_obj, ConfigTree):
            Path(config_file).unlink()

def load_explicit(config_obj: ConfigObj):
    """Explicit load from file or configtree.
    """
    config = Config()
    ctree = get_running_config(config)
    if isinstance(config_obj, ConfigTree):
        ntree = config_obj
    else:
        ntree = get_proposed_config(config_obj)
    # Calculate the diff between the current and proposed config
    cmds = diff_to_commands(ctree, ntree)
    # Set the commands in the config session
    set_commands(cmds)

def load_batch(config_obj: ConfigObj):
    # requires legacy backend patch
    raise NotImplementedError('batch loading not implemented')

def load_tree(config_obj: ConfigObj):
    # requires vyconf backend patch
    raise NotImplementedError('tree loading not implemented')

def load_legacy(config_obj: ConfigObj):
    """Legacy load from file or configtree.
    """
    if isinstance(config_obj, ConfigTree):
        config_file = NamedTemporaryFile(delete=False).name
        Path(config_file).write_text(config_obj.to_string())
    else:
        config_file = config_obj

    config = LoadConfig()

    try:
        config.load_config(config_file)
    except VyOSError as e:
        raise LoadConfigError(e) from e
    finally:
        if isinstance(config_obj, ConfigTree):
            Path(config_file).unlink()

def load(config_obj: ConfigObj, strict: bool = True,
         switch: Variety = 'legacy'):
    type_hints = get_type_hints(load)
    switch_choice = get_args(type_hints['switch'])
    if switch not in switch_choice:
        raise ValueError(f'invalid switch: {switch}')

    check_session(strict, switch)

    config_obj = migrate(config_obj)

    func = getattr(thismod, f'load_{switch}')
    func(config_obj)
