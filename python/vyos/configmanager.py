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


import json  # noqa: I001
import logging

from types import ModuleType
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

from vyos.config import Config
from vyos.config import ConfigDict
from vyos.configtree import ConfigTree
from vyos.configtree import DiffTree
from vyos.referencetree import ReferenceTree
from vyos.dependentverify import removed_dependency_value_paths_of_kind
from vyos.dependentverify import dependent_value_paths_of_kind

from vyos.utils.system import load_as_module
from vyos.defaults import directories
from vyos.base import Warning as Warn
from vyos import ConfigError

LOG = logging.getLogger(Path(__file__).stem)
handler = logging.StreamHandler()
formatter = logging.Formatter('(%(name)s): %(message)s')
handler.setFormatter(formatter)
LOG.addHandler(handler)

debug = False

_ = LOG.setLevel(logging.DEBUG) if debug else LOG.setLevel(logging.INFO)


@dataclass
class ConfigDictCache:
    config_dict: ConfigDict = None
    args: list = field(default_factory=list)


@dataclass
class Component:
    module: ModuleType
    name: str
    rdep_error: list = field(default_factory=list)
    rdep_warning: list = field(default_factory=list)
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
        self.diff_tree: DiffTree = None

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
            if not path.exists():
                continue
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
            self.diff_tree = None
        else:
            self.running_config = config.get_config_tree(effective=True)
            self.session_config = config.get_config_tree()
            self.diff_tree = DiffTree(self.running_config, self.session_config)

        if self.cache_config:
            self.clear_cache()

        self.clear_rdep()

        if config is None:
            return

        self.init_rdep()

    def init_rdep(self):
        # pylint: disable=too-many-locals,too-many-branches
        """
        Schema definition for reverse dependency alert:
        alertAttr = attribute alert
        {
            "error" | "warning"
        }

        We are currently only considering reverse dependencies for type
        (kind) 'interface'. Extension for other kinds may be added here.

        The reference tree utils return data of the form outlined below. In
        all cases, the input path is a reference tree path, and consequently
        may define a subtree of the config (due to intermediary tag node);
        thus the return values are lists of (tuples including) actual config
        paths.

        removed_dependency_value_paths: list[tuple[list(values), path]]
        are the values for each path defined by the XML paths of kind
        'interface', which are to be removed in the current commit session.

        dependent_value_paths: dict[alert: list[tuple[list(values), path]]]
        are the (values, path) defined by all XML dependency annotations
        existing in the session tree, indexed by alert type.

        The dependent_value_paths are cross-referenced with the interface
        values scheduled for deletion in removed_dependency_value_paths, and
        the corresponding alert raised in the configmanager verify stage.
        """
        removed_dependency_value_paths = removed_dependency_value_paths_of_kind(
            'interface', self.reference_tree, self.session_config, self.diff_tree
        )

        LOG.debug(f'removed_dependency_value_paths: {removed_dependency_value_paths}')

        if not removed_dependency_value_paths:
            return

        dependent_value_paths = dependent_value_paths_of_kind(
            'interface', self.reference_tree, self.session_config
        )

        LOG.debug(f'dependent_value_paths: {dependent_value_paths}')

        if not dependent_value_paths:
            return

        for vals, path in removed_dependency_value_paths:
            owner = self.reference_tree.get_owner(path)
            if owner is None:
                LOG.error(f'Path {path} has no owner')
                continue
            component_name = Path(owner).stem
            component = self.components.get(component_name)
            LOG.debug(f'owner: {component_name}')

            errors = dependent_value_paths.get('error', [])
            rdep_err = component.rdep_error
            for dependent_vals, dependent_path in errors:
                for v in set(vals) & set(dependent_vals):
                    rdep_err.append(
                        f'\nNode:\n {path + [v]}\nis required by:\n {dependent_path}\n'
                    )

            warnings = dependent_value_paths.get('warning', [])
            rdep_warn = component.rdep_warning
            for dependent_vals, dependent_path in warnings:
                for v in set(vals) & set(dependent_vals):
                    rdep_warn.append(
                        f'removed node:\n {path + [v]}\nis referenced by:\n {dependent_path}\n'
                    )

    def clear_rdep(self):
        for component in self.components.values():
            component.rdep_error = []
            component.rdep_warning = []

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

        if errors := component.rdep_error:
            raise ConfigError('\n'.join(errors))
        if warnings := component.rdep_warning:
            Warn('\n'.join(warnings))

        mod.verify(config_dict)

    def generate(self, script_name: str, config_dict: ConfigDict) -> None:
        component = self.components[script_name]
        mod = component.module

        mod.generate(config_dict)

    def apply(self, script_name: str, config_dict: ConfigDict) -> None:
        component = self.components[script_name]
        mod = component.module

        mod.apply(config_dict)
