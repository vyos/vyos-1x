#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
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
import re
import sys
from tempfile import NamedTemporaryFile

from vyos.config import Config
from vyos.remote import urlc
from vyos.component_version import system_footer
from vyos.defaults import directories

DEFAULT_CONFIG_PATH = os.path.join(directories['config'], 'config.boot')
remote_save = None

if len(sys.argv) > 1:
    save_file = sys.argv[1]
else:
    save_file = DEFAULT_CONFIG_PATH

if re.match(r'\w+:/', save_file):
    try:
        remote_save = urlc(save_file)
    except ValueError as e:
        sys.exit(e)

config = Config()
ct = config.get_config_tree(effective=True)

write_file = save_file if remote_save is None else NamedTemporaryFile(delete=False).name
with open(write_file, 'w') as f:
    # config_tree is None before boot configuration is complete;
    # automated saves should check boot_configuration_complete
    if ct is not None:
        f.write(ct.to_string())
    f.write("\n")
    f.write(system_footer())

if remote_save is not None:
    try:
        remote_save.upload(write_file)
    finally:
        os.remove(write_file)
