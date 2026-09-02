#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

from vyos.base import ConfigError
from vyos.utils.network import is_valid_ipv4_address_or_range
from vyos.utils.network import is_valid_ipv6_address_or_range
from vyos.utils.network import is_valid_ipv4_network
from vyos.utils.network import is_valid_ipv6_network


def resolve_config_path(conf, path_str):
    """Resolve a space-separated configuration path into the list of
    values found at that path in the given (candidate) configuration.

    A "*" segment expands every instance of the tag node at that position
    (e.g. every configured VRF name), continuing the remainder of the path
    under each instance. The terminal segment is resolved as every child
    name of a tag node (e.g. every configured BGP neighbor address) if it
    has any, otherwise as the values of a multi-value leaf node.
    """
    return _walk(conf, [], path_str.split())


def _walk(conf, base, remaining):
    if not remaining:
        nodes = conf.list_nodes(base)
        if nodes:
            return nodes
        return conf.return_values(base)

    head, *rest = remaining
    if head == '*':
        result = []
        for instance in conf.list_nodes(base):
            result.extend(_walk(conf, base + [instance], rest))
        return result

    return _walk(conf, base + [head], rest)


def resolve_apply_paths(conf, path_list, is_valid=None):
    """Resolve a list of apply-path strings and return the deduplicated,
    order-preserving union of every value they resolve to.

    apply-path values never go through CLI-level <validator/> checks, since
    they are not entered on the CLI. If "is_valid" is given, every resolved
    value is checked against it; the first value that fails raises
    ValueError(value).
    """
    seen = set()
    result = []
    for path_str in path_list:
        for value in resolve_config_path(conf, path_str):
            if is_valid is not None and not is_valid(value):
                raise ValueError(value)
            if value not in seen:
                seen.add(value)
                result.append(value)
    return result


# Group types whose membership can be derived from another part of the
# configuration via "apply-path": the leaf they hold their members in, the
# nftables set name prefix used for that group type in the vyos_filter table,
# and the validator a derived value must pass (CLI-level <validator/> checks
# are not run for apply-path derived values, as they never go through the CLI)
apply_path_group_types = {
    'address_group': ('address', 'A_', is_valid_ipv4_address_or_range),
    'ipv6_address_group': ('address', 'A6_', is_valid_ipv6_address_or_range),
    'network_group': ('network', 'N_', is_valid_ipv4_network),
    'ipv6_network_group': ('network', 'N6_', is_valid_ipv6_network),
}


def apply_group_paths(groups, conf):
    """Merge every apply-path derived value into its group's member list, in
    place. "groups" is a firewall group config dict (the "group" node under
    "firewall")."""
    if not groups:
        return

    for group_type, (member_key, _prefix, is_valid) in apply_path_group_types.items():
        group_dict = groups.get(group_type)
        if not group_dict:
            continue

        for group_name, group_conf in group_dict.items():
            apply_path = group_conf.get('apply_path')
            if not apply_path:
                continue

            existing = group_conf.get(member_key, [])
            merged = list(existing)
            seen = set(existing)
            try:
                derived = resolve_apply_paths(conf, apply_path, is_valid)
            except ValueError as e:
                raise ConfigError(
                    f'apply-path on {group_type} "{group_name}" '
                    f'resolved invalid {member_key} "{e}"'
                ) from e
            for value in derived:
                if value not in seen:
                    seen.add(value)
                    merged.append(value)
            group_conf[member_key] = merged


def refresh_apply_path_groups(groups, conf):
    """Re-resolve every apply-path derived group in "groups" (a firewall
    group config dict) and return the nftables sets it affects, as
    {'v4': {set_name: [values]}, 'v6': {set_name: [values]}}.

    Used to push apply-path derived group membership into the already-running
    nftables ruleset without a full firewall commit, e.g. after a change to
    an apply-path's source (such as a routing protocol) that leaves the
    firewall section itself untouched.
    """
    apply_group_paths(groups, conf)

    sets = {'v4': {}, 'v6': {}}
    for group_type, (member_key, prefix, _is_valid) in apply_path_group_types.items():
        version = 'v6' if group_type.startswith('ipv6_') else 'v4'
        for group_name, group_conf in (groups or {}).get(group_type, {}).items():
            if not group_conf.get('apply_path'):
                continue
            sets[version][f'{prefix}{group_name}'] = group_conf.get(member_key, [])
    return sets


class DictConfig:
    """Minimal Config-like view over a plain config dict, exposing only the
    list_nodes()/return_values() primitives resolve_config_path() relies on.

    Lets op-mode callers walk arbitrary apply-path targets from a dict
    obtained via vyos.configquery.op_mode_config_dict(), instead of paying
    for a session-backed vyos.config.Config() just to get the same two
    primitives.
    """

    def __init__(self, tree):
        self.tree = tree

    def _get(self, path):
        node = self.tree
        for p in path:
            if not isinstance(node, dict) or p not in node:
                return None
            node = node[p]
        return node

    def list_nodes(self, path):
        node = self._get(path)
        return list(node.keys()) if isinstance(node, dict) else []

    def return_values(self, path):
        node = self._get(path)
        return node if isinstance(node, list) else []
