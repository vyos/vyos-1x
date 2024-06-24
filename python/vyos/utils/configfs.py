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
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

import os

def delete_cli_node(cli_path: list):
    from shutil import rmtree
    for config_dir in ['VYATTA_TEMP_CONFIG_DIR', 'VYATTA_CHANGES_ONLY_DIR']:
        tmp = os.path.join(os.environ[config_dir], '/'.join(cli_path))
        # delete CLI node
        if os.path.exists(tmp):
            rmtree(tmp)

def add_cli_node(cli_path: list, value: str=None):
    from vyos.utils.auth import get_current_user
    from vyos.utils.file import write_file

    current_user = get_current_user()
    for config_dir in ['VYATTA_TEMP_CONFIG_DIR', 'VYATTA_CHANGES_ONLY_DIR']:
        # store new value
        tmp = os.path.join(os.environ[config_dir], '/'.join(cli_path))
        write_file(f'{tmp}/node.val', value, user=current_user, group='vyattacfg', mode=0o664)
        # mark CLI node as modified
        if config_dir == 'VYATTA_CHANGES_ONLY_DIR':
            write_file(f'{tmp}/.modified', '', user=current_user, group='vyattacfg', mode=0o664)
