# Copyright 2019 VyOS maintainers and contributors <maintainers@vyos.io>
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

import sys
import os
import subprocess
import vyos.version
import vyos.defaults
import vyos.systemversions as systemversions
import vyos.formatversions as formatversions

class MigratorError(Exception):
    pass

class Migrator(object):
    def __init__(self, config_file, force=False, set_vintage=None):
        self._config_file = config_file
        self._force = force
        self._set_vintage = set_vintage
        self._config_file_vintage = None
        self._changed = False

    def read_config_file_versions(self):
        """
        Get component versions from config file footer and set vintage;
        return empty dictionary if config string is missing.
        """
        cfg_file = self._config_file
        component_versions = {}

        cfg_versions = formatversions.read_vyatta_versions(cfg_file)

        if cfg_versions:
            self._config_file_vintage = 'vyatta'
            component_versions = cfg_versions

        cfg_versions = formatversions.read_vyos_versions(cfg_file)

        if cfg_versions:
            self._config_file_vintage = 'vyos'
            component_versions = cfg_versions

        return component_versions

    def update_vintage(self):
        old_vintage = self._config_file_vintage

        if self._set_vintage:
            self._config_file_vintage = self._set_vintage

        if not self._config_file_vintage:
            self._config_file_vintage = vyos.defaults.cfg_vintage

        if self._config_file_vintage not in ['vyatta', 'vyos']:
            raise MigratorError("Unknown vintage.")

        if self._config_file_vintage == old_vintage:
            return False
        else:
            return True

    def run_migration_scripts(self, config_file_versions, system_versions):
        """
        Run migration scripts iteratively, until config file version equals
        system component version.
        """
        cfg_versions = config_file_versions
        sys_versions = system_versions

        sys_keys = list(sys_versions.keys())
        sys_keys.sort()

        rev_versions = {}

        for key in sys_keys:
            sys_ver = sys_versions[key]
            if key in cfg_versions:
                cfg_ver = cfg_versions[key]
            else:
                cfg_ver = 0

            migrate_script_dir = os.path.join(
                    vyos.defaults.directories['migrate'], key)

            while cfg_ver < sys_ver:
                next_ver = cfg_ver + 1

                migrate_script = os.path.join(migrate_script_dir,
                        '{}-to-{}'.format(cfg_ver, next_ver))

                try:
                    subprocess.check_output([migrate_script,
                        self._config_file])
                except FileNotFoundError:
                    pass
                except subprocess.CalledProcessError as err:
                    print("Called process error: {}.".format(err))
                    sys.exit(1)

                cfg_ver = next_ver

            rev_versions[key] = cfg_ver

        return rev_versions

    def write_config_file_versions(self, cfg_versions):
        """
        Write new versions string.
        """
        versions_string = formatversions.format_versions_string(cfg_versions)

        os_version_string = vyos.version.get_version()

        if self._config_file_vintage == 'vyatta':
            formatversions.write_vyatta_versions_foot(self._config_file,
                                                      versions_string,
                                                      os_version_string)

        if self._config_file_vintage == 'vyos':
            formatversions.write_vyos_versions_foot(self._config_file,
                                                    versions_string,
                                                    os_version_string)

    def run(self):
        """
        Gather component versions from config file and system.
        Run migration scripts.
        Update vintage ('vyatta' or 'vyos'), if needed.
        If changed, remove old versions string from config file, and
            write new versions string.
        """
        cfg_file = self._config_file

        cfg_versions = self.read_config_file_versions()
        if self._force:
            # This will force calling all migration scripts:
            cfg_versions = {}

        sys_versions = systemversions.get_system_versions()

        rev_versions = self.run_migration_scripts(cfg_versions, sys_versions)

        if rev_versions != cfg_versions:
            self._changed = True

        if self.update_vintage():
            self._changed = True

        if not self._changed:
            return

        formatversions.remove_versions(cfg_file)

        self.write_config_file_versions(rev_versions)

    def config_changed(self):
        return self._changed

class VirtualMigrator(Migrator):
    def __init__(self, config_file, vintage='vyos'):
        super().__init__(config_file, set_vintage = vintage)

    def run(self):
        cfg_file = self._config_file

        cfg_versions = self.read_config_file_versions()
        if not cfg_versions:
            raise MigratorError("Config file has no version information;"
                                " virtual migration not possible.")

        if self.update_vintage():
            self._changed = True

        if not self._changed:
            return

        formatversions.remove_versions(cfg_file)

        self.write_config_file_versions(cfg_versions)

