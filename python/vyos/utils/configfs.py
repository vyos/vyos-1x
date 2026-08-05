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
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

# pylint: disable=import-outside-toplevel

import os
from typing import TYPE_CHECKING

from vyos.utils.backend import vyconf_backend
from vyos.utils.boot import boot_configuration_complete

if TYPE_CHECKING:
    from vyos.config import Config

# The official tools for making legacy-backend CLI changes from within an
# active session/commit - the same ones ConfigSession.set()/.delete() use.
# A prior implementation wrote directly into VYATTA_TEMP_CONFIG_DIR/
# VYATTA_CHANGES_ONLY_DIR instead: those writes land on disk, but a
# subsequent cli-shell-api showConfig call does not pick them up within the
# same session, since cli-shell-api consults its own reference/index state,
# which only these tools update correctly.
MY_SET = '/opt/vyatta/sbin/my_set'
MY_DELETE = '/opt/vyatta/sbin/my_delete'


def _legacy_env():
    """Environment for invoking my_set/my_delete from within a script that
    is itself running as part of an active commit (so VYATTA_TEMP_CONFIG_DIR/
    VYATTA_CHANGES_ONLY_DIR/etc. are already set in os.environ), but that
    may be missing the static vyatta_*/vyos_* path variables a real
    interactive shell normally provides via profile sourcing - e.g. when
    invoked from within the vyos-configd daemon, which does not source
    those profiles. Confirmed to be required: without it, my_set fails
    trying to run "$vyatta_datadir/.../validate-value" with an empty
    vyatta_datadir.
    """
    from vyos.configsession import inject_vyos_env

    return inject_vyos_env(os.environ.copy())


def _run_legacy_cli_tool(cmd: list, cli_path: list, verb: str):
    import subprocess

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True,
                        env=_legacy_env())
    except subprocess.CalledProcessError as e:
        raise ValueError(f'Unable to {verb} CLI node {cli_path}: '
                          f'{e.stderr or e.stdout}') from e


def delete_cli_node(cli_path: list, config: 'Config' = None):
    """Delete cli_path from the active session/commit.

    If config (the Config instance the calling script is using) is given,
    also reflect the deletion in its own in-memory session tree, so a
    dependent invoked later in the same commit via that same Config
    instance observes it immediately - see Config.sync_local_delete().
    """
    if vyconf_backend() and boot_configuration_complete():
        # pylint: disable=redefined-outer-name
        from vyos.utils.session import delete_cli_node

        delete_cli_node(cli_path)
    else:
        _run_legacy_cli_tool([MY_DELETE] + cli_path, cli_path, 'delete')

    if config is not None:
        config.sync_local_delete(cli_path)


def add_cli_node(cli_path: list, value: str = None, config: 'Config' = None):
    """Set cli_path to value in the active session/commit.

    If config (the Config instance the calling script is using) is given,
    also reflect the change in its own in-memory session tree, so a
    dependent invoked later in the same commit via that same Config
    instance observes it immediately - see Config.sync_local_set().
    """
    if vyconf_backend() and boot_configuration_complete():
        # pylint: disable=redefined-outer-name
        from vyos.utils.session import add_cli_node

        add_cli_node(cli_path, value)
    else:
        cmd = [MY_SET] + cli_path
        if value:
            cmd = cmd + [value]
        _run_legacy_cli_tool(cmd, cli_path, 'set')

    if config is not None:
        config.sync_local_set(cli_path, value)
