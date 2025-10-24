# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

# pylint: disable=import-outside-toplevel

import os
from inspect import stack


def in_config_session():
    """Vyatta bash completion uses the following environment variable for
    indication of the config mode environment, independent of legacy backend
    initialization of Cstore"""
    from os import environ

    return '_OFR_CONFIGURE' in environ


# utility for functions below
def get_caller_name() -> str:
    filename = stack()[2].filename
    return os.path.basename(filename)


# OOB operations used (rarely) to update the session config during commit
# execution of config mode scripts.
# The standard use is for replacing plaintext with encrypted passwords in
# the session config during commit.
def delete_cli_node(cli_path: list):
    from vyos.vyconf_session import VyconfSession
    from vyos.configsession import ConfigSessionError

    pid = os.environ.get('SESSION_PID', '')
    if not pid:
        raise ValueError('Missing env var SESSION_PID')

    script_name = get_caller_name()
    tag_value = os.environ.get('VYOS_TAGNODE_VALUE', None)

    vs = VyconfSession(pid=pid, on_error=ConfigSessionError)
    vs.aux_delete(cli_path, script_name, tag_value)


def add_cli_node(cli_path: list, value: str = None):
    from vyos.vyconf_session import VyconfSession
    from vyos.configsession import ConfigSessionError

    pid = os.environ.get('SESSION_PID', '')
    if not pid:
        raise ValueError('Missing env var SESSION_PID')

    script_name = get_caller_name()
    tag_value = os.environ.get('VYOS_TAGNODE_VALUE', None)

    cli_path = cli_path + [value] if value else cli_path

    vs = VyconfSession(pid=pid, on_error=ConfigSessionError)
    vs.aux_set(cli_path, script_name, tag_value)
