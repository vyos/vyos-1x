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

from unittest import TestCase
from vyos.base import ConfigError
from vyos.config_path_resolver import resolve_config_path
from vyos.config_path_resolver import resolve_apply_paths
from vyos.config_path_resolver import apply_group_paths
from vyos.config_path_resolver import refresh_apply_path_groups
from vyos.config_path_resolver import DictConfig

tree = {
    'protocols': {
        'bgp': {
            'neighbor': {
                '62.141.40.144': {},
                '62.141.40.145': {},
            },
            'address-family': {
                'ipv4-unicast': {
                    'network': ['185.137.128.0/22', '10.0.0.0/8'],
                }
            },
        }
    },
    'vrf': {
        'name': {
            'CUST1': {'protocols': {'bgp': {'neighbor': {'10.1.1.1': {}}}}},
            'CUST2': {'protocols': {'bgp': {'neighbor': {'10.2.2.2': {}}}}},
        }
    },
}


class TestConfigPathResolver(TestCase):
    def setUp(self):
        self.conf = DictConfig(tree)

    def test_terminal_tag_node(self):
        # TestConfigPathResolver: terminal path resolves via list_nodes()
        result = resolve_config_path(self.conf, 'protocols bgp neighbor')
        self.assertEqual(result, ['62.141.40.144', '62.141.40.145'])

    def test_terminal_leaf_node(self):
        # TestConfigPathResolver: terminal path falls back to return_values()
        # when the terminal segment has no tag-node children
        result = resolve_config_path(
            self.conf, 'protocols bgp address-family ipv4-unicast network'
        )
        self.assertEqual(result, ['185.137.128.0/22', '10.0.0.0/8'])

    def test_wildcard_expansion(self):
        # TestConfigPathResolver: "*" fans out across every instance of the
        # tag node at that position
        result = resolve_config_path(self.conf, 'vrf name * protocols bgp neighbor')
        self.assertEqual(sorted(result), ['10.1.1.1', '10.2.2.2'])

    def test_nonexistent_path(self):
        # TestConfigPathResolver: a path that doesn't exist resolves to an
        # empty list, not an error
        result = resolve_config_path(self.conf, 'protocols static route')
        self.assertEqual(result, [])

    def test_resolve_apply_paths_dedup_and_order(self):
        # TestConfigPathResolver: values from multiple paths are merged,
        # deduplicated, and keep first-seen order
        result = resolve_apply_paths(
            self.conf,
            [
                'protocols bgp neighbor',
                'vrf name * protocols bgp neighbor',
                'protocols bgp neighbor',
            ],
        )
        self.assertEqual(
            result,
            [
                '62.141.40.144',
                '62.141.40.145',
                '10.1.1.1',
                '10.2.2.2',
            ],
        )

    def test_resolve_apply_paths_accepts_valid_values(self):
        # TestConfigPathResolver: a passing is_valid callback does not
        # affect the resolved result
        result = resolve_apply_paths(
            self.conf, ['protocols bgp neighbor'], is_valid=lambda v: True
        )
        self.assertEqual(result, ['62.141.40.144', '62.141.40.145'])

    def test_resolve_apply_paths_rejects_invalid_value(self):
        # TestConfigPathResolver: apply-path values never went through a
        # CLI <validator/>, so resolve_apply_paths must reject a value that
        # fails the caller-supplied validator instead of returning it
        with self.assertRaises(ValueError) as ctx:
            resolve_apply_paths(
                self.conf,
                ['protocols bgp neighbor'],
                is_valid=lambda v: v != '62.141.40.144',
            )
        self.assertEqual(ctx.exception.args[0], '62.141.40.144')

    def test_apply_group_paths_merges_derived_members(self):
        # TestConfigPathResolver: derived values are appended to a group's
        # existing, manually configured members
        groups = {
            'network_group': {
                'smoketest_derived': {
                    'network': ['172.16.200.0/24'],
                    'apply_path': ['protocols bgp address-family ipv4-unicast network'],
                }
            }
        }
        apply_group_paths(groups, self.conf)
        self.assertEqual(
            groups['network_group']['smoketest_derived']['network'],
            ['172.16.200.0/24', '185.137.128.0/22', '10.0.0.0/8'],
        )

    def test_apply_group_paths_no_groups_is_a_noop(self):
        # TestConfigPathResolver: called with no groups at all, nothing to do
        apply_group_paths(None, self.conf)
        apply_group_paths({}, self.conf)

    def test_apply_group_paths_rejects_invalid_derived_value(self):
        # TestConfigPathResolver: a derived value that fails the group
        # type's validator raises ConfigError, naming the offending group
        groups = {
            'address_group': {
                'smoketest_bad': {
                    'address': ['10.0.0.1'],
                    # resolves to VRF names ("CUST1", "CUST2"), not addresses
                    'apply_path': ['vrf name'],
                }
            }
        }
        with self.assertRaisesRegex(ConfigError, 'resolved invalid'):
            apply_group_paths(groups, self.conf)

    def test_apply_group_paths_rejects_non_canonical_network(self):
        # TestConfigPathResolver: a derived network-group value with host
        # bits set (e.g. an interface address copied verbatim) is not a
        # canonical network and must be rejected, not rendered as-is
        conf = DictConfig(
            {'interfaces': {'eth0': {'address': ['203.0.113.5/24']}}}
        )
        groups = {
            'network_group': {
                'smoketest_bad': {
                    'network': [],
                    'apply_path': ['interfaces eth0 address'],
                }
            }
        }
        with self.assertRaisesRegex(ConfigError, 'resolved invalid'):
            apply_group_paths(groups, conf)

    def test_refresh_apply_path_groups_builds_v4_and_v6_sets(self):
        # TestConfigPathResolver: only groups with an apply-path show up in
        # the result, named with their nftables set prefix
        groups = {
            'network_group': {
                'smoketest_derived': {
                    'network': ['172.16.200.0/24'],
                    'apply_path': ['protocols bgp address-family ipv4-unicast network'],
                },
                'smoketest_manual_only': {
                    'network': ['172.16.201.0/24'],
                },
            },
            'address_group': {
                'smoketest_addr': {
                    'apply_path': ['vrf name * protocols bgp neighbor'],
                }
            },
        }
        sets = refresh_apply_path_groups(groups, self.conf)
        self.assertEqual(
            sets,
            {
                'v4': {
                    'N_smoketest_derived': [
                        '172.16.200.0/24',
                        '185.137.128.0/22',
                        '10.0.0.0/8',
                    ],
                    'A_smoketest_addr': ['10.1.1.1', '10.2.2.2'],
                },
                'v6': {},
            },
        )

    def test_refresh_apply_path_groups_no_groups(self):
        # TestConfigPathResolver: no "group" node configured at all
        sets = refresh_apply_path_groups(None, self.conf)
        self.assertEqual(sets, {'v4': {}, 'v6': {}})
