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
import re
import fileinput

def read_vyatta_versions(config_file):
    config_file_versions = {}

    with open(config_file, 'r') as config_file_handle:
        for config_line in config_file_handle:
            if re.match(r'/\* === vyatta-config-version:.+=== \*/$', config_line):
                if not re.match(r'/\* === vyatta-config-version:\s+"([\w,-]+@\d+:)+([\w,-]+@\d+)"\s+=== \*/$', config_line):
                    raise ValueError("malformed configuration string: "
                            "{}".format(config_line))

                for pair in re.findall(r'([\w,-]+)@(\d+)', config_line):
                    config_file_versions[pair[0]] = int(pair[1])


    return config_file_versions

def read_vyos_versions(config_file):
    config_file_versions = {}

    with open(config_file, 'r') as config_file_handle:
        for config_line in config_file_handle:
            if re.match(r'// vyos-config-version:.+', config_line):
                if not re.match(r'// vyos-config-version:\s+"([\w,-]+@\d+:)+([\w,-]+@\d+)"\s*', config_line):
                    raise ValueError("malformed configuration string: "
                            "{}".format(config_line))

                for pair in re.findall(r'([\w,-]+)@(\d+)', config_line):
                    config_file_versions[pair[0]] = int(pair[1])

    return config_file_versions

def remove_versions(config_file):
    """
    Remove old version string.
    """
    for line in fileinput.input(config_file, inplace=True):
        if re.match(r'/\* Warning:.+ \*/$', line):
            continue
        if re.match(r'/\* === vyatta-config-version:.+=== \*/$', line):
            continue
        if re.match(r'/\* Release version:.+ \*/$', line):
            continue
        if re.match('// vyos-config-version:.+', line):
            continue
        if re.match('// Warning:.+', line):
            continue
        if re.match('// Release version:.+', line):
            continue
        sys.stdout.write(line)

def format_versions_string(config_versions):
    cfg_keys = list(config_versions.keys())
    cfg_keys.sort()

    component_version_strings = []

    for key in cfg_keys:
        cfg_vers = config_versions[key]
        component_version_strings.append('{}@{}'.format(key, cfg_vers))

    separator = ":"
    component_version_string = separator.join(component_version_strings)

    return component_version_string

def write_vyatta_versions_foot(config_file, component_version_string,
                                 os_version_string):
    if config_file:
        with open(config_file, 'a') as config_file_handle:
            config_file_handle.write('/* Warning: Do not remove the following line. */\n')
            config_file_handle.write('/* === vyatta-config-version: "{}" === */\n'.format(component_version_string))
            config_file_handle.write('/* Release version: {} */\n'.format(os_version_string))
    else:
        sys.stdout.write('/* Warning: Do not remove the following line. */\n')
        sys.stdout.write('/* === vyatta-config-version: "{}" === */\n'.format(component_version_string))
        sys.stdout.write('/* Release version: {} */\n'.format(os_version_string))

def write_vyos_versions_foot(config_file, component_version_string,
                               os_version_string):
    if config_file:
        with open(config_file, 'a') as config_file_handle:
            config_file_handle.write('// Warning: Do not remove the following line.\n')
            config_file_handle.write('// vyos-config-version: "{}"\n'.format(component_version_string))
            config_file_handle.write('// Release version: {}\n'.format(os_version_string))
    else:
        sys.stdout.write('// Warning: Do not remove the following line.\n')
        sys.stdout.write('// vyos-config-version: "{}"\n'.format(component_version_string))
        sys.stdout.write('// Release version: {}\n'.format(os_version_string))

