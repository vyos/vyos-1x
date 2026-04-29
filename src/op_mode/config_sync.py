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
from vyos.configtree import ConfigTree
from vyos.configtree import ConfigTreeError
from vyos.config_mgmt import ConfigMgmt
from vyos.config_mgmt import ConfigMgmtError

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
    """Load remote API settings from config-sync service runtime JSON file"""

    cfg = _read_json_config()
    secondary = cfg.get('secondary', {})
    address = secondary.get('address')
    key = secondary.get('key')
    port = int(secondary.get('port', 443))
    timeout = int(secondary.get('timeout')) if secondary.get('timeout') else None

    if not address or not key:
        raise opmode.UnconfiguredObject(
            'Config-sync is not fully configured: missing secondary address/key'
        )

    return dict(host=address, key=key, port=port, timeout=timeout)


class ConfigSyncDiffManager:
    def __init__(self):
        api_settings = _load_config_sync_settings()
        self._client = http.ApiClient(http.ApiClientConfig(**api_settings))

        self._config_mgmt = ConfigMgmt()

    def _get_remote_config_tree(self, section_path: list = None) -> ConfigTree:
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
            try:
                result = self._config_mgmt.remote_compare(
                    source,
                    remote_tree,
                    path=section_path,
                    commands=commands,
                )
            except ConfigMgmtError as e:
                raise opmode.InternalError(str(e)) from e

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
