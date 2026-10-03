#!/usr/bin/env python3
#
# Copyright (C) VyOS Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import typing
from pathlib import Path

from vyos import opmode
from vyos import http_api_client as http
from vyos.utils.file import read_json
from vyos.utils.dict import dict_to_paths
from vyos.utils.list import list_contains_sublist
from vyos.utils.config import get_saved_config_tree
from vyos.configtree import ConfigTree
from vyos.configtree import ConfigTreeError
from vyos.configtree import DiffTree
from vyos.config import Config
from vyos.derivedtree import apply_exclusion_list
from vyos.derivedtree import DerivedTreeError
from vyos.defaults import config_sync_exclusion_list

CONFIG_FILE = Path('/run/config_sync_conf.conf')


def _normalize_section(section: typing.Optional[str]) -> list:
    """Convert optional CLI section argument to config tree path list"""

    if not section:
        return []

    # Section can be passed as a single string token ('interfaces ethernet')
    return list(section.split())


def _read_json_config() -> dict:
    """Read config-sync service runtime JSON file"""

    if not CONFIG_FILE.exists():
        raise opmode.UnconfiguredObject('Config-sync service is not configured')

    return read_json(CONFIG_FILE, defaultonfailure={})


def _load_config_sync_sections() -> list:
    """Load sections from config-sync service runtime JSON file"""

    cfg = _read_json_config()
    sections = cfg.get('section', {})

    return list(dict_to_paths(sections)) if sections else []


def _load_config_sync_settings() -> dict:
    # pylint: disable=use-dict-literal
    """Load remote API settings from config-sync service runtime JSON file"""

    cfg = _read_json_config()
    secondary = cfg.get('secondary', {})
    address = secondary.get('address')
    key = secondary.get('key')
    port = int(secondary.get('port', 443))
    timeout = int(secondary.get('timeout')) if secondary.get('timeout') else None
    # config-sync talks to a remote secondary over HTTPS. TLS verification is
    # off by default because secondary nodes typically present a self-signed
    # certificate; an operator can opt in (True, or a CA bundle path) once the
    # runtime config exposes it. TODO: surface as a proper CLI knob
    # (set service config-sync secondary verify-tls / ca-certificate).
    verify_tls = secondary.get('verify_tls', False)

    if not address or not key:
        raise opmode.UnconfiguredObject(
            'Config-sync is not fully configured: missing secondary address/key'
        )

    return dict(
        host=address, key=key, port=port, timeout=timeout, verify_tls=verify_tls
    )


class ConfigSyncDiffManager:
    def __init__(self):
        api_settings = _load_config_sync_settings()
        self._client = http.ApiClient(http.ApiClientConfig(**api_settings))

        self._config = Config()
        self.running_config = self._config.get_config_tree(effective=True)
        self.session_config = self._config.get_config_tree(effective=False)

    def _get_remote_config_tree(self, section_path: list = None) -> ConfigTree:
        # pylint: disable=redefined-outer-name
        """
        Retrieve remote config (or subtree) as ConfigTree via HTTPS API.

        Note: Endpoint name is expected to be available on remote VyOS instance.
        """

        payload = {
            'configFormat': 'raw',
            'op': 'showConfig',
            'path': section_path or [],
        }

        try:
            resp_data = self._client.post('retrieve', payload, raise_on_error=False)
        except http.ApiError as e:
            raise opmode.InternalError(f'Remote API failed: {e}') from e

        error = (resp_data.get('error') or resp_data.get('detail') or '').strip()
        if error:
            ignored_errors = ('configuration under specified path is empty',)
            if error.lower() not in ignored_errors:
                raise opmode.InternalError(
                    f'Remote API responded with an error: {error}'
                )

        config_raw = resp_data.get('data') or ''
        try:
            return ConfigTree(config_raw)
        except ConfigTreeError as e:
            raise opmode.InternalError(f'Unable to build remote ConfigTree: {e}') from e

    def _get_exclude_list(self) -> list[list[str]]:
        # add as instance method, for future access to CLI settings from self.Config
        exclude_file = Path(config_sync_exclusion_list)
        if not exclude_file.exists():
            raise opmode.InternalError('Config-sync exclusion list file not available')

        return read_json(exclude_file, defaultonfailure=[])

    def _format_remote_diff(self, diff_tree: DiffTree, path: list, commands: bool):
        add_tree = diff_tree.add
        del_tree = diff_tree.delete
        command_prefix = ' '.join(path)

        result_lines = []
        if commands:
            # Process the deleted elements into command format and filter based on prefix (path)
            for line in del_tree.to_commands(op='delete').splitlines():
                if line.startswith(f'delete {command_prefix}'):
                    result_lines.append(line)

            # Process the added elements into command format and filter based on prefix (path)
            for line in add_tree.to_commands(op='set').splitlines():
                if line.startswith(f'set {command_prefix}'):
                    result_lines.append(line)
        else:
            with_node = len(path) > 1
            # Retrieve subtrees for the specified path from both added and deleted trees
            del_tree = del_tree.get_subtree(path, with_node=with_node)
            add_tree = add_tree.get_subtree(path, with_node=with_node)

            # Convert the subtrees to string lines for further processing
            del_tree_lines = str(del_tree).splitlines()
            add_tree_lines = str(add_tree).splitlines()

            # Format the lines with a prefix ('-', '+') and filter out empty lines
            del_lines = [f'- {l}' for l in del_tree_lines if l.strip()]  # noqa: E741
            add_lines = [f'+ {l}' for l in add_tree_lines if l.strip()]  # noqa: E741

            if del_lines or add_lines:
                # Adjust command prefix if a node is present in the path
                command_prefix = ' '.join(path[:-1]) if with_node else command_prefix
                if command_prefix:
                    result_lines.append(f'[{command_prefix}]')

                # Combine both deleted and added lines and process them
                result_lines.extend(del_lines + add_lines)

        # Join the result lines into a single string, excluding empty lines
        return '\n'.join((line for line in result_lines if line.strip()))

    def remote_compare(
        self,
        source: str,
        remote_tree: ConfigTree,
        path: typing.Optional[list] = None,
        commands: bool = False,
    ) -> str:
        # pylint: disable=redefined-outer-name
        """
        Compares a local configuration tree with a remote
        configuration tree based on the specified source ('running', 'candidate', 'saved').
        """
        path = path or []

        # Determine the correct local configuration tree based on the 'source' parameter
        if source == 'running':
            local_tree = self.running_config
        elif source == 'candidate':
            local_tree = self.session_config
        elif source == 'saved':
            try:
                local_tree = get_saved_config_tree()
            except ConfigTreeError as e:
                raise opmode.InternalError(str(e)) from e
        else:
            raise opmode.IncorrectValue(
                'Invalid source, must be one of: running, candidate, saved'
            )

        exclude_list = self._get_exclude_list()

        try:
            masked_local = apply_exclusion_list(local_tree, exclude_list)
            masked_remote = apply_exclusion_list(remote_tree, exclude_list)
        except DerivedTreeError as e:
            raise opmode.InternalError(str(e)) from e

        try:
            diff_tree = DiffTree(masked_remote, masked_local)
        except ConfigTreeError as e:
            raise opmode.InternalError(str(e)) from e

        return self._format_remote_diff(diff_tree, path, commands)

    def get_sync_diff(
        self,
        source: str,
        sections: list,
        commands: typing.Optional[bool] = False,
    ) -> str:
        """Returns differences between local config and remote config for a given sections"""

        results = []
        remote_tree = self._get_remote_config_tree()
        for section_path in sections:
            result = self.remote_compare(
                source,
                remote_tree,
                path=section_path,
                commands=commands,
            )

            result = result.strip()
            if result:
                results.append(result)

        return '\n'.join(results)


def show_sync_diff(
    raw: bool,
    source: typing.Optional[str],
    section: typing.Optional[str],
    commands: typing.Optional[bool],
) -> str:
    """Show differences between local config and remote config for a given section.

    Args:
        raw: unused (op-mode convention); output is always text.
        source: local source config: running/candidate/saved.
        section: optional top-level section to diff (e.g. "nat", "system time-zone").
        commands: flag which indicates format of output.

    Returns:
        Diff output (string). Empty diff is rendered as "no changes".
    """
    _ = raw  # op-mode framework passes it; keep signature consistent

    source = source or 'running'
    selected_section = _normalize_section(section)

    configured_sections = _load_config_sync_sections()
    if selected_section:
        if not list_contains_sublist(configured_sections, selected_section):
            raise opmode.UnconfiguredObject(
                f"Config-sync is not configured for '{section}' section. "
                f"Use 'set service config-sync section {section}' for this."
            )
        sections = [selected_section]
    else:
        sections = configured_sections

    manager = ConfigSyncDiffManager()
    output = manager.get_sync_diff(source, sections, commands=commands)

    return output if output else 'No changes between local and remote configuration'


if __name__ == '__main__':
    try:
        res = opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, opmode.Error) as e:
        print(e)
        sys.exit(1)
