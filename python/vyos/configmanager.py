# Copyright (C) VyOS Inc.
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
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

import json

from types import ModuleType
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

from vyos.config import Config
from vyos.config import ConfigDict
from vyos.configtree import ConfigTree
from vyos.referencetree import ReferenceTree
from vyos.utils.system import load_as_module
from vyos.defaults import directories


@dataclass
class ConfigDictCache:
    config_dict: ConfigDict = None
    args: list = field(default_factory=list)


@dataclass
class Component:
    module: ModuleType
    name: str
    cache: ConfigDictCache = None


class ConfigManagerError(Exception):
    pass


class ConfigManager:
    # pylint: disable=attribute-defined-outside-init
    def __init__(self, reference_tree: ReferenceTree = None, cache_config: bool = True):
        self.reference_tree = reference_tree or ReferenceTree()
        self.cache_config = cache_config

        self.config: Config = None
        self.running_config: ConfigTree = None
        self.session_config: ConfigTree = None

        self.components = self.init_components()

    @staticmethod
    def init_components():
        # pylint: disable=raise-missing-from
        data_dir = directories['data']
        configd_include_file = Path(data_dir).joinpath('configd-include.json')
        config_scripts_dir = directories['conf_mode']
        try:
            include_str = Path(configd_include_file).read_text()
        except OSError as e:
            raise ConfigManagerError(e)
        try:
            include_list = json.loads(include_str)
        except json.JSONDecodeError as e:
            raise ConfigManagerError(e)

        components = {}
        for file in include_list:
            path = Path(config_scripts_dir).joinpath(file)
            file_stem = Path(file).stem
            name = file_stem.replace('-', '_')

            module = load_as_module(name, path)

            components[file_stem] = Component(module, name)

        return components

    def set_config(self, config: Config):
        self.config = config

        if config is None:
            self.running_config = None
            self.session_config = None
        else:
            self.running_config = config.get_config_tree(effective=True)
            self.session_config = config.get_config_tree()
            setattr(config, 'manager', self)

        if self.cache_config:
            self.clear_cache()

    def clear_cache(self):
        for component in self.components.values():
            component.cache = None

    def get_config(self, script_name: str, args: list) -> ConfigDict:
        component = self.components[script_name]
        mod = component.module
        mod.argv = args

        config = self.config
        res = mod.get_config(config)

        if self.cache_config:
            component.cache = ConfigDictCache(res, args)

        return res

    def verify(self, script_name: str, config_dict: ConfigDict) -> None:
        component = self.components[script_name]
        mod = component.module

        mod.verify(config_dict)

    def generate(self, script_name: str, config_dict: ConfigDict) -> None:
        component = self.components[script_name]
        mod = component.module

        mod.generate(config_dict)

    def apply(self, script_name: str, config_dict: ConfigDict) -> None:
        component = self.components[script_name]
        mod = component.module

        mod.apply(config_dict)
