# Copyright 2019-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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

import os
import re
import json
import logging
from pathlib import Path
from grp import getgrnam

from vyos.component_version import VersionInfo
from vyos.component_version import version_info_from_system
from vyos.component_version import version_info_from_file
from vyos.component_version import version_info_copy
from vyos.component_version import version_info_prune_component
from vyos.compose_config import ComposeConfig
from vyos.compose_config import ComposeConfigError
from vyos.configtree import ConfigTree
from vyos.defaults import directories as default_dir
from vyos.defaults import component_version_json


log_file = Path(default_dir['config']).joinpath('vyos-migrate.log')

class ConfigMigrateError(Exception):
    """Raised on error in config migration."""

class ConfigMigrate:
    # pylint: disable=too-many-instance-attributes
    # the number is reasonable in this case
    def __init__(self, config_file: str, force=False,
                 output_file: str = None, checkpoint_file: str = None):
        self.config_file: str = config_file
        self.force: bool = force
        self.system_version: VersionInfo = version_info_from_system()
        self.file_version: VersionInfo = version_info_from_file(self.config_file)
        self.compose = None
        self.output_file = output_file
        self.checkpoint_file = checkpoint_file
        self.logger = None
        self.config_modified = True

        if self.file_version is None:
            raise ConfigMigrateError(f'failed to read config file {self.config_file}')

    def migration_needed(self) -> bool:
        return self.system_version.component != self.file_version.component

    def release_update_needed(self) -> bool:
        return self.system_version.release != self.file_version.release

    def syntax_update_needed(self) -> bool:
        return self.system_version.vintage != self.file_version.vintage

    def update_release(self):
        """
        Update config file release version.
        """
        self.file_version.update_release(self.system_version.release)

    def update_syntax(self):
        """
        Update config file syntax.
        """
        self.file_version.update_syntax()

    @staticmethod
    def normalize_config_body(version_info: VersionInfo):
        """
        This is an interim workaround for the cosmetic issue of node
        ordering when composing operations on the internal config_tree:
        ordering is performed on parsing, hence was maintained in the old
        system which would parse/write on each application of a migration
        script (~200). Here, we will take the cost of one extra parsing to
        reorder before save, for easier review.
        """
        if not version_info.config_body_is_none():
            ct = ConfigTree(version_info.config_body)
            version_info.update_config_body(ct.to_string())

    def write_config(self):
        if self.output_file is not None:
            config_file = self.output_file
        else:
            config_file = self.config_file

        try:
            self.file_version.write(config_file)
        except ValueError as e:
            raise ConfigMigrateError(f'failed to write {config_file}: {e}') from e

    def init_logger(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        fh = ConfigMigrate.group_perm_file_handler(log_file,
                                                   group='vyattacfg',
                                                   mode='w')
        fh.setLevel(logging.INFO)
        fh_formatter = logging.Formatter('%(message)s')
        fh.setFormatter(fh_formatter)
        self.logger.addHandler(fh)
        ch = logging.StreamHandler()
        ch.setLevel(logging.WARNING)
        ch_formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(ch_formatter)
        self.logger.addHandler(ch)

    @staticmethod
    def group_perm_file_handler(filename, group=None, mode='a'):
        # pylint: disable=consider-using-with
        if group is None:
            return logging.FileHandler(filename, mode)
        gid = getgrnam(group).gr_gid
        if not os.path.exists(filename):
            open(filename, 'a').close()
            os.chown(filename, -1, gid)
            os.chmod(filename, 0o664)
        return logging.FileHandler(filename, mode)

    @staticmethod
    def sort_function():
        """
        Define sort function for migration files as tuples (n, m) for file
        n-to-m.
        """
        numbers = re.compile(r'(\d+)')
        def func(p: Path):
            parts = numbers.split(p.stem)
            return list(map(int, parts[1::2]))
        return func

    @staticmethod
    def file_ext(file_path: Path) -> str:
        """
        Return an identifier from file name for checkpoint file extension.
        """
        return f'{file_path.parent.stem}_{file_path.stem}'

    def run_migration_scripts(self):
        """
        Call migration files iteratively.
        """
        os.environ['VYOS_MIGRATION'] = '1'

        self.init_logger()
        self.logger.info("List of applied migration modules:")

        components = list(self.system_version.component)
        components.sort()

        # T4382: 'bgp' needs to follow 'quagga':
        if 'bgp' in components and 'quagga' in components:
            components.insert(components.index('quagga'),
                              components.pop(components.index('bgp')))

        revision: VersionInfo = version_info_copy(self.file_version)
        # prune retired, for example, zone-policy
        version_info_prune_component(revision, self.system_version)

        migrate_dir = Path(default_dir['migrate'])
        sort_func = ConfigMigrate.sort_function()

        for key in components:
            p = migrate_dir.joinpath(key)
            script_list = list(p.glob('*-to-*'))
            script_list = sorted(script_list, key=sort_func)

            if not self.file_version.component_is_none() and not self.force:
                start = self.file_version.component.get(key, 0)
                script_list = list(filter(lambda x, st=start: sort_func(x)[0] >= st,
                                          script_list))

            if not script_list: # no applicable migration scripts
                revision.update_component(key, self.system_version.component[key])
                continue

            for file in script_list:
                f = file.as_posix()
                self.logger.info(f'applying {f}')
                try:
                    self.compose.apply_file(f, func_name='migrate')
                except ComposeConfigError as e:
                    self.logger.error(e)
                    if self.checkpoint_file:
                        check = f'{self.checkpoint_file}_{ConfigMigrate.file_ext(file)}'
                        revision.update_config_body(self.compose.to_string())
                        ConfigMigrate.normalize_config_body(revision)
                        revision.write(check)
                    break
                else:
                    revision.update_component(key, sort_func(file)[1])

        revision.update_config_body(self.compose.to_string())
        ConfigMigrate.normalize_config_body(revision)
        self.file_version = version_info_copy(revision)

        if revision.component != self.system_version.component:
            raise ConfigMigrateError(f'incomplete migration: check {log_file} for error')

        del os.environ['VYOS_MIGRATION']

    def save_json_record(self):
        """
        Write component versions to a json file
        """
        version_file = component_version_json

        try:
            with open(version_file, 'w') as f:
                f.write(json.dumps(self.system_version.component,
                                   indent=2, sort_keys=True))
        except OSError:
            pass

    def load_config(self):
        """
        Instantiate a ComposeConfig object with the config string.
        """

        self.compose = ComposeConfig(self.file_version.config_body, self.checkpoint_file)

    def run(self):
        """
        If migration needed, run migration scripts and update config file.
        If only release version update needed, update release version.
        """
        # save system component versions in json file for reference
        self.save_json_record()

        if not self.migration_needed():
            if self.release_update_needed():
                self.update_release()
                self.write_config()
            else:
                self.config_modified = False
            return

        if self.syntax_update_needed():
            self.update_syntax()
            self.write_config()

        self.load_config()

        self.run_migration_scripts()

        self.update_release()
        self.write_config()

    def run_script(self, test_script: str):
        """
        Run a single migration script. For testing this simply provides the
        body for loading and writing the result; the component string is not
        updated.
        """

        self.load_config()
        self.init_logger()

        os.environ['VYOS_MIGRATION'] = '1'

        try:
            self.compose.apply_file(test_script, func_name='migrate')
        except ComposeConfigError as e:
            self.logger.error(f'config-migration error in {test_script}: {e}')
        else:
            self.file_version.update_config_body(self.compose.to_string())

        del os.environ['VYOS_MIGRATION']

        self.write_config()
