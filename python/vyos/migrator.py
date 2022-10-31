# Copyright 2019-2022 VyOS maintainers and contributors <maintainers@vyos.io>
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
import json
import subprocess
import vyos.defaults
import vyos.component_version as component_version

class MigratorError(Exception):
    pass

class Migrator(object):
    def __init__(self, config_file, force=False, set_vintage='vyos'):
        self._config_file = config_file
        self._force = force
        self._set_vintage = set_vintage
        self._config_file_vintage = None
        self._log_file = None
        self._changed = False

    def read_config_file_versions(self):
        """
        Get component versions from config file footer and set vintage;
        return empty dictionary if config string is missing.
        """
        cfg_file = self._config_file
        component_versions = {}

        cfg_versions = component_version.from_file(cfg_file, vintage='vyatta')

        if cfg_versions:
            self._config_file_vintage = 'vyatta'
            component_versions = cfg_versions

        cfg_versions = component_version.from_file(cfg_file, vintage='vyos')

        if cfg_versions:
            self._config_file_vintage = 'vyos'
            component_versions = cfg_versions

        return component_versions

    def update_vintage(self):
        old_vintage = self._config_file_vintage

        if self._set_vintage:
            self._config_file_vintage = self._set_vintage

        if self._config_file_vintage not in ['vyatta', 'vyos']:
            raise MigratorError("Unknown vintage.")

        if self._config_file_vintage == old_vintage:
            return False
        else:
            return True

    def open_log_file(self):
        """
        Open log file for migration, catching any error.
        Note that, on boot, migration takes place before the canonical log
        directory is created, hence write to the config file directory.
        """
        self._log_file = os.path.join(vyos.defaults.directories['config'],
                                      'vyos-migrate.log')
        # on creation, allow write permission for cfg_group;
        # restore original umask on exit
        mask = os.umask(0o113)
        try:
            log = open('{0}'.format(self._log_file), 'w')
            log.write("List of executed migration scripts:\n")
        except Exception as e:
            os.umask(mask)
            print("Logging error: {0}".format(e))
            return None

        os.umask(mask)
        return log

    def run_migration_scripts(self, config_file_versions, system_versions):
        """
        Run migration scripts iteratively, until config file version equals
        system component version.
        """
        log = self.open_log_file()

        cfg_versions = config_file_versions
        sys_versions = system_versions

        sys_keys = list(sys_versions.keys())
        sys_keys.sort()

        # XXX 'bgp' needs to follow 'quagga':
        if 'bgp' in sys_keys and 'quagga' in sys_keys:
            sys_keys.insert(sys_keys.index('quagga'),
                            sys_keys.pop(sys_keys.index('bgp')))

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
                    subprocess.check_call([migrate_script,
                        self._config_file])
                except FileNotFoundError:
                    pass
                except Exception as err:
                    print("\nMigration script error: {0}: {1}."
                          "".format(migrate_script, err))
                    sys.exit(1)

                if log:
                    try:
                        log.write('{0}\n'.format(migrate_script))
                    except Exception as e:
                        print("Error writing log: {0}".format(e))

                cfg_ver = next_ver

            rev_versions[key] = cfg_ver

        if log:
            log.close()

        return rev_versions

    def write_config_file_versions(self, cfg_versions):
        """
        Write new versions string.
        """
        if self._config_file_vintage == 'vyatta':
            component_version.write_version_footer(cfg_versions,
                                                   self._config_file,
                                                   vintage='vyatta')

        if self._config_file_vintage == 'vyos':
            component_version.write_version_footer(cfg_versions,
                                                   self._config_file,
                                                   vintage='vyos')

    def save_json_record(self, component_versions: dict):
        """
        Write component versions to a json file
        """
        mask = os.umask(0o113)
        version_file = vyos.defaults.component_version_json
        try:
            with open(version_file, 'w') as f:
                f.write(json.dumps(component_versions, indent=2, sort_keys=True))
        except OSError:
            pass
        finally:
            os.umask(mask)

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

        sys_versions = component_version.from_system()

        # save system component versions in json file for easy reference
        self.save_json_record(sys_versions)

        rev_versions = self.run_migration_scripts(cfg_versions, sys_versions)

        if rev_versions != cfg_versions:
            self._changed = True

        if self.update_vintage():
            self._changed = True

        if not self._changed:
            return

        component_version.remove_footer(cfg_file)

        self.write_config_file_versions(rev_versions)

    def config_changed(self):
        return self._changed

class VirtualMigrator(Migrator):
    def run(self):
        cfg_file = self._config_file

        cfg_versions = self.read_config_file_versions()
        if not cfg_versions:
            return

        if self.update_vintage():
            self._changed = True

        if not self._changed:
            return

        component_version.remove_footer(cfg_file)

        self.write_config_file_versions(cfg_versions)

