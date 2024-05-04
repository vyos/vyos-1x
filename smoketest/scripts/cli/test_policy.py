#!/usr/bin/env python3
#
# Copyright (C) 2021-2023 VyOS maintainers and contributors
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

import unittest

from base_vyostest_shim import VyOSUnitTestSHIM

from vyos.configsession import ConfigSessionError
from vyos.utils.process import cmd

base_path = ['policy']

class TestPolicy(VyOSUnitTestSHIM.TestCase):
    def tearDown(self):
        self.cli_delete(base_path)
        self.cli_commit()

    def test_access_list(self):
        acls = {
            '50' : {
                'rule' : {
                    '5' : {
                        'action' : 'permit',
                        'source' : { 'any' : '' },
                    },
                    '10' : {
                        'action' : 'deny',
                        'source' : { 'host' : '1.2.3.4' },
                    },
                },
             },
            '150' : {
                'rule' : {
                    '5' : {
                        'action' : 'permit',
                        'source' : { 'any' : '' },
                        'destination' : { 'host' : '2.2.2.2' },
                    },
                    '10' : {
                        'action' : 'deny',
                        'source' : { 'any' : '' },
                        'destination' : { 'any' : '' },
                    },
                },
            },
            '2000' : {
                'rule' : {
                    '5' : {
                        'action' : 'permit',
                        'destination' : { 'any' : '' },
                        'source' : { 'network' : '10.0.0.0', 'inverse-mask' : '0.255.255.255' },
                    },
                    '10' : {
                        'action' : 'permit',
                        'destination' : { 'any' : '' },
                        'source' : { 'network' : '172.16.0.0', 'inverse-mask' : '0.15.255.255' },
                    },
                    '15' : {
                        'action' : 'permit',
                        'destination' : { 'any' : '' },
                        'source' : { 'network' : '192.168.0.0', 'inverse-mask' : '0.0.255.255' },
                    },
                    '20' : {
                        'action' : 'permit',
                        'destination' : { 'network' : '172.16.0.0', 'inverse-mask' : '0.15.255.255' },
                        'source' : { 'network' : '10.0.0.0', 'inverse-mask' : '0.255.255.255' },
                    },
                    '25' : {
                        'action' : 'deny',
                        'destination' : { 'network' : '192.168.0.0', 'inverse-mask' : '0.0.255.255' },
                        'source' : { 'network' : '172.16.0.0', 'inverse-mask' : '0.15.255.255' },
                    },
                    '30' : {
                        'action' : 'deny',
                        'destination' : { 'any' : '' },
                        'source' : { 'any' : '' },
                    },
                },
            },
        }

        for acl, acl_config in acls.items():
            path = base_path + ['access-list', acl]
            self.cli_set(path + ['description', f'VyOS-ACL-{acl}'])
            if 'rule' not in acl_config:
                continue

            for rule, rule_config in acl_config['rule'].items():
                self.cli_set(path + ['rule', rule, 'action', rule_config['action']])
                for direction in ['source', 'destination']:
                    if direction in rule_config:
                        if 'any' in rule_config[direction]:
                            self.cli_set(path + ['rule', rule, direction, 'any'])
                        if 'host' in rule_config[direction]:
                            self.cli_set(path + ['rule', rule, direction, 'host', rule_config[direction]['host']])
                        if 'network' in rule_config[direction]:
                            self.cli_set(path + ['rule', rule, direction, 'network', rule_config[direction]['network']])
                            self.cli_set(path + ['rule', rule, direction, 'inverse-mask', rule_config[direction]['inverse-mask']])

        self.cli_commit()

        config = self.getFRRconfig('access-list', end='')
        for acl, acl_config in acls.items():
            for rule, rule_config in acl_config['rule'].items():
                tmp = f'access-list {acl} seq {rule}'
                if rule_config['action'] == 'permit':
                    tmp += ' permit'
                else:
                    tmp += ' deny'

                if {'source', 'destination'} <= set(rule_config):
                    tmp += ' ip'

                for direction in ['source', 'destination']:
                    if direction in rule_config:
                        if 'any' in rule_config[direction]:
                            tmp += ' any'
                        if 'host' in rule_config[direction]:
                            # XXX: Some weird side rule from the old vyatta days
                            # possible to clean this up after the vyos-1x migration
                            if int(acl) in range(100, 200) or int(acl) in range(2000, 2700):
                                tmp += ' host'

                            tmp += ' ' + rule_config[direction]['host']
                        if 'network' in rule_config[direction]:
                            tmp += ' ' + rule_config[direction]['network'] + ' ' + rule_config[direction]['inverse-mask']

                self.assertIn(tmp, config)

    def test_access_list6(self):
        acls = {
            '50' : {
                'rule' : {
                    '5' : {
                        'action' : 'permit',
                        'source' : { 'any' : '' },
                    },
                    '10' : {
                        'action' : 'deny',
                        'source' : { 'network' : '2001:db8:10::/48', 'exact-match' : '' },
                    },
                    '15' : {
                        'action' : 'deny',
                        'source' : { 'network' : '2001:db8:20::/48' },
                    },
                },
             },
            '100' : {
                'rule' : {
                    '5' : {
                        'action' : 'deny',
                        'source' : { 'network' : '2001:db8:10::/64', 'exact-match' : '' },
                    },
                    '10' : {
                        'action' : 'deny',
                        'source' : { 'network' : '2001:db8:20::/64', },
                    },
                    '15' : {
                        'action' : 'deny',
                        'source' : { 'network' : '2001:db8:30::/64', 'exact-match' : '' },
                    },
                    '20' : {
                        'action' : 'deny',
                        'source' : { 'network' : '2001:db8:40::/64', 'exact-match' : '' },
                    },
                    '25' : {
                        'action' : 'deny',
                        'source' : { 'any' : '' },
                    },
                },
             },
        }

        for acl, acl_config in acls.items():
            path = base_path + ['access-list6', acl]
            self.cli_set(path + ['description', f'VyOS-ACL-{acl}'])
            if 'rule' not in acl_config:
                continue

            for rule, rule_config in acl_config['rule'].items():
                self.cli_set(path + ['rule', rule, 'action', rule_config['action']])
                for direction in ['source', 'destination']:
                    if direction in rule_config:
                        if 'any' in rule_config[direction]:
                            self.cli_set(path + ['rule', rule, direction, 'any'])
                        if 'network' in rule_config[direction]:
                            self.cli_set(path + ['rule', rule, direction, 'network', rule_config[direction]['network']])
                        if 'exact-match' in rule_config[direction]:
                            self.cli_set(path + ['rule', rule, direction, 'exact-match'])

        self.cli_commit()

        config = self.getFRRconfig('ipv6 access-list', end='')
        for acl, acl_config in acls.items():
            for rule, rule_config in acl_config['rule'].items():
                tmp = f'ipv6 access-list {acl} seq {rule}'
                if rule_config['action'] == 'permit':
                    tmp += ' permit'
                else:
                    tmp += ' deny'

                if {'source', 'destination'} <= set(rule_config):
                    tmp += ' ip'

                for direction in ['source', 'destination']:
                    if direction in rule_config:
                        if 'any' in rule_config[direction]:
                            tmp += ' any'
                        if 'network' in rule_config[direction]:
                            tmp += ' ' + rule_config[direction]['network']
                        if 'exact-match' in rule_config[direction]:
                            tmp += ' exact-match'

                self.assertIn(tmp, config)


    def test_as_path_list(self):
        test_data = {
            'VyOS' : {
                'rule' : {
                    '5' : {
                        'action' : 'permit',
                        'regex'  : '^44501 64502$',
                    },
                    '10' : {
                        'action' : 'permit',
                        'regex'  : '44501|44502|44503',
                    },
                    '15' : {
                        'action' : 'permit',
                        'regex'  : '^44501_([0-9]+_)+',
                    },
                },
            },
            'Customers' : {
                'rule' : {
                    '5' : {
                        'action' : 'permit',
                        'regex'  : '_10_',
                    },
                    '10' : {
                        'action' : 'permit',
                        'regex'  : '_20_',
                    },
                    '15' : {
                        'action' : 'permit',
                        'regex'  : '_30_',
                    },
                    '20' : {
                        'action' : 'deny',
                        'regex'  : '_40_',
                    },
                },
            },
            'bogons' : {
                'rule' : {
                    '5' : {
                        'action' : 'permit',
                        'regex'  : '_0_',
                    },
                    '10' : {
                        'action' : 'permit',
                        'regex'  : '_23456_',
                    },
                    '15' : {
                        'action' : 'permit',
                        'regex'  : '_6449[6-9]_|_65[0-4][0-9][0-9]_|_655[0-4][0-9]_|_6555[0-1]_',
                    },
                    '20' : {
                        'action' : 'permit',
                        'regex'  : '_6555[2-9]_|_655[6-9][0-9]_|_65[6-9][0-9][0-9]_|_6[6-9][0-9][0-9][0-]_|_[7-9][0-9][0-9][0-9][0-9]_|_1[0-2][0-9][0-9][0-9][0-9]_|_130[0-9][0-9][0-9]_|_1310[0-6][0-9]_|_13107[01]_',
                    },
                },
            },
        }

        for as_path, as_path_config in test_data.items():
            path = base_path + ['as-path-list', as_path]
            self.cli_set(path + ['description', f'VyOS-ASPATH-{as_path}'])
            if 'rule' not in as_path_config:
                continue

            for rule, rule_config in as_path_config['rule'].items():
                if 'action' in rule_config:
                    self.cli_set(path + ['rule', rule, 'action', rule_config['action']])
                if 'regex' in rule_config:
                    self.cli_set(path + ['rule', rule, 'regex', rule_config['regex']])

        self.cli_commit()

        config = self.getFRRconfig('bgp as-path access-list', end='')
        for as_path, as_path_config in test_data.items():
            if 'rule' not in as_path_config:
                continue

            for rule, rule_config in as_path_config['rule'].items():
                tmp = f'bgp as-path access-list {as_path} seq {rule}'
                if rule_config['action'] == 'permit':
                    tmp += ' permit'
                else:
                    tmp += ' deny'

                tmp += ' ' + rule_config['regex']

                self.assertIn(tmp, config)

    def test_community_list(self):
        test_data = {
            '100' : {
                'rule' : {
                    '5' : {
                        'action' : 'permit',
                        'regex'  : '.*',
                    },
                },
            },
            '200' : {
                'rule' : {
                    '5' : {
                        'action' : 'deny',
                        'regex'  : '^1:201$',
                    },
                    '10' : {
                        'action' : 'deny',
                        'regex'  : '1:101$',
                    },
                    '15' : {
                        'action' : 'deny',
                        'regex'  : '^1:100$',
                    },
                },
            },
        }

        for comm_list, comm_list_config in test_data.items():
            path = base_path + ['community-list', comm_list]
            self.cli_set(path + ['description', f'VyOS-COMM-{comm_list}'])
            if 'rule' not in comm_list_config:
                continue

            for rule, rule_config in comm_list_config['rule'].items():
                if 'action' in rule_config:
                    self.cli_set(path + ['rule', rule, 'action', rule_config['action']])
                if 'regex' in rule_config:
                    self.cli_set(path + ['rule', rule, 'regex', rule_config['regex']])

        self.cli_commit()

        config = self.getFRRconfig('bgp community-list', end='')
        for comm_list, comm_list_config in test_data.items():
            if 'rule' not in comm_list_config:
                continue

            for rule, rule_config in comm_list_config['rule'].items():
                tmp = f'bgp community-list {comm_list} seq {rule}'
                if rule_config['action'] == 'permit':
                    tmp += ' permit'
                else:
                    tmp += ' deny'

                tmp += ' ' + rule_config['regex']

                self.assertIn(tmp, config)

    def test_extended_community_list(self):
        test_data = {
            'foo' : {
                'rule' : {
                    '5' : {
                        'action' : 'permit',
                        'regex'  : '.*',
                    },
                },
            },
            '200' : {
                'rule' : {
                    '5' : {
                        'action' : 'deny',
                        'regex'  : '^1:201$',
                    },
                    '10' : {
                        'action' : 'deny',
                        'regex'  : '1:101$',
                    },
                    '15' : {
                        'action' : 'deny',
                        'regex'  : '^1:100$',
                    },
                },
            },
        }

        for comm_list, comm_list_config in test_data.items():
            path = base_path + ['extcommunity-list', comm_list]
            self.cli_set(path + ['description', f'VyOS-EXTCOMM-{comm_list}'])
            if 'rule' not in comm_list_config:
                continue

            for rule, rule_config in comm_list_config['rule'].items():
                if 'action' in rule_config:
                    self.cli_set(path + ['rule', rule, 'action', rule_config['action']])
                if 'regex' in rule_config:
                    self.cli_set(path + ['rule', rule, 'regex', rule_config['regex']])

        self.cli_commit()

        config = self.getFRRconfig('bgp extcommunity-list', end='')
        for comm_list, comm_list_config in test_data.items():
            if 'rule' not in comm_list_config:
                continue

            for rule, rule_config in comm_list_config['rule'].items():
                # if the community is not a number but a name, the expanded
                # keyword is used
                expanded = ''
                if not comm_list.isnumeric():
                    expanded = ' expanded'
                tmp = f'bgp extcommunity-list{expanded} {comm_list} seq {rule}'

                if rule_config['action'] == 'permit':
                    tmp += ' permit'
                else:
                    tmp += ' deny'

                tmp += ' ' + rule_config['regex']

                self.assertIn(tmp, config)


    def test_large_community_list(self):
        test_data = {
            'foo' : {
                'rule' : {
                    '5' : {
                        'action' : 'permit',
                        'regex'  : '667:123:100',
                    },
                },
            },
            'bar' : {
                'rule' : {
                    '5' : {
                        'action' : 'permit',
                        'regex'  : '65000:120:10',
                    },
                    '10' : {
                        'action' : 'permit',
                        'regex'  : '65000:120:20',
                    },
                    '15' : {
                        'action' : 'permit',
                        'regex'  : '65000:120:30',
                    },
                },
            },
        }

        for comm_list, comm_list_config in test_data.items():
            path = base_path + ['large-community-list', comm_list]
            self.cli_set(path + ['description', f'VyOS-LARGECOMM-{comm_list}'])
            if 'rule' not in comm_list_config:
                continue

            for rule, rule_config in comm_list_config['rule'].items():
                if 'action' in rule_config:
                    self.cli_set(path + ['rule', rule, 'action', rule_config['action']])
                if 'regex' in rule_config:
                    self.cli_set(path + ['rule', rule, 'regex', rule_config['regex']])

        self.cli_commit()

        config = self.getFRRconfig('bgp large-community-list', end='')
        for comm_list, comm_list_config in test_data.items():
            if 'rule' not in comm_list_config:
                continue

            for rule, rule_config in comm_list_config['rule'].items():
                tmp = f'bgp large-community-list expanded {comm_list} seq {rule}'

                if rule_config['action'] == 'permit':
                    tmp += ' permit'
                else:
                    tmp += ' deny'

                tmp += ' ' + rule_config['regex']

                self.assertIn(tmp, config)


    def test_prefix_list(self):
        test_data = {
            'foo' : {
                'rule' : {
                    '5' : {
                        'action' : 'permit',
                        'prefix'  : '10.0.0.0/8',
                        'ge' : '16',
                        'le' : '24',
                    },
                    '10' : {
                        'action' : 'deny',
                        'prefix'  : '172.16.0.0/12',
                        'ge' : '16',
                    },
                    '15' : {
                        'action' : 'permit',
                        'prefix'  : '192.168.0.0/16',
                    },
                },
            },
            'bar' : {
                'rule' : {
                    '5' : {
                        'action' : 'permit',
                        'prefix'  : '10.0.10.0/24',
                        'ge' : '25',
                        'le' : '26',
                    },
                    '10' : {
                        'action' : 'deny',
                        'prefix'  : '10.0.20.0/24',
                        'le' : '25',
                    },
                    '15' : {
                        'action' : 'permit',
                        'prefix'  : '10.0.25.0/24',
                    },
                },
            },
        }

        for prefix_list, prefix_list_config in test_data.items():
            path = base_path + ['prefix-list', prefix_list]
            self.cli_set(path + ['description', f'VyOS-PFX-LIST-{prefix_list}'])
            if 'rule' not in prefix_list_config:
                continue

            for rule, rule_config in prefix_list_config['rule'].items():
                if 'action' in rule_config:
                    self.cli_set(path + ['rule', rule, 'action', rule_config['action']])
                if 'prefix' in rule_config:
                    self.cli_set(path + ['rule', rule, 'prefix', rule_config['prefix']])
                if 'ge' in rule_config:
                    self.cli_set(path + ['rule', rule, 'ge', rule_config['ge']])
                if 'le' in rule_config:
                    self.cli_set(path + ['rule', rule, 'le', rule_config['le']])

        self.cli_commit()

        config = self.getFRRconfig('ip prefix-list', end='')
        for prefix_list, prefix_list_config in test_data.items():
            if 'rule' not in prefix_list_config:
                continue

            for rule, rule_config in prefix_list_config['rule'].items():
                tmp = f'ip prefix-list {prefix_list} seq {rule}'

                if rule_config['action'] == 'permit':
                    tmp += ' permit'
                else:
                    tmp += ' deny'

                tmp += ' ' + rule_config['prefix']

                if 'ge' in rule_config:
                    tmp += ' ge ' + rule_config['ge']
                if 'le' in rule_config:
                    tmp += ' le ' + rule_config['le']

                self.assertIn(tmp, config)


    def test_prefix_list6(self):
        test_data = {
            'foo' : {
                'rule' : {
                    '5' : {
                        'action' : 'permit',
                        'prefix'  : '2001:db8::/32',
                        'ge' : '40',
                        'le' : '48',
                    },
                    '10' : {
                        'action' : 'deny',
                        'prefix'  : '2001:db8::/32',
                        'ge' : '48',
                    },
                    '15' : {
                        'action' : 'permit',
                        'prefix'  : '2001:db8:1000::/64',
                    },
                },
            },
            'bar' : {
                'rule' : {
                    '5' : {
                        'action' : 'permit',
                        'prefix'  : '2001:db8:100::/40',
                        'ge' : '48',
                    },
                    '10' : {
                        'action' : 'permit',
                        'prefix'  : '2001:db8:200::/40',
                        'ge' : '48',
                    },
                    '15' : {
                        'action' : 'deny',
                        'prefix'  : '2001:db8:300::/40',
                        'le' : '64',
                    },
                },
            },
        }

        for prefix_list, prefix_list_config in test_data.items():
            path = base_path + ['prefix-list6', prefix_list]
            self.cli_set(path + ['description', f'VyOS-PFX-LIST-{prefix_list}'])
            if 'rule' not in prefix_list_config:
                continue

            for rule, rule_config in prefix_list_config['rule'].items():
                if 'action' in rule_config:
                    self.cli_set(path + ['rule', rule, 'action', rule_config['action']])
                if 'prefix' in rule_config:
                    self.cli_set(path + ['rule', rule, 'prefix', rule_config['prefix']])
                if 'ge' in rule_config:
                    self.cli_set(path + ['rule', rule, 'ge', rule_config['ge']])
                if 'le' in rule_config:
                    self.cli_set(path + ['rule', rule, 'le', rule_config['le']])

        self.cli_commit()

        config = self.getFRRconfig('ipv6 prefix-list', end='')
        for prefix_list, prefix_list_config in test_data.items():
            if 'rule' not in prefix_list_config:
                continue

            for rule, rule_config in prefix_list_config['rule'].items():
                tmp = f'ipv6 prefix-list {prefix_list} seq {rule}'

                if rule_config['action'] == 'permit':
                    tmp += ' permit'
                else:
                    tmp += ' deny'

                tmp += ' ' + rule_config['prefix']

                if 'ge' in rule_config:
                    tmp += ' ge ' + rule_config['ge']
                if 'le' in rule_config:
                    tmp += ' le ' + rule_config['le']

                self.assertIn(tmp, config)

    def test_prefix_list_duplicates(self):
        # FRR does not allow to specify the same profix list rule multiple times
        #
        # vyos(config)# ip prefix-list foo seq 10 permit 192.0.2.0/24
        # vyos(config)# ip prefix-list foo seq 20 permit 192.0.2.0/24
        # % Configuration failed.
        # Error type: validation
        # Error description: duplicated prefix list value: 192.0.2.0/24

        # There is also a VyOS verify() function to test this

        prefix = '100.64.0.0/10'
        prefix_list = 'duplicates'
        test_range = range(20, 25)
        path = base_path + ['prefix-list', prefix_list]

        for rule in test_range:
            self.cli_set(path + ['rule', str(rule), 'action', 'permit'])
            self.cli_set(path + ['rule', str(rule), 'prefix', prefix])

        # Duplicate prefixes
        with self.assertRaises(ConfigSessionError):
            self.cli_commit()

        for rule in test_range:
            self.cli_set(path + ['rule', str(rule), 'le', str(rule)])

        self.cli_commit()

        config = self.getFRRconfig('ip prefix-list', end='')
        for rule in test_range:
            tmp = f'ip prefix-list {prefix_list} seq {rule} permit {prefix} le {rule}'
            self.assertIn(tmp, config)
    def test_route_map_community_set(self):
        test_data = {
            "community-configuration": {
                "rule": {
                    "10": {
                        "action": "permit",
                        "set": {
                            "community": {
                                "replace": [
                                    "65000:10",
                                    "65001:11"
                                ]
                            },
                            "extcommunity": {
                                "bandwidth": "200",
                                "rt": [
                                    "65000:10",
                                    "192.168.0.1:11"
                                ],
                                "soo": [
                                    "192.168.0.1:11",
                                    "65000:10"
                                ]
                            },
                            "large-community": {
                                "replace": [
                                    "65000:65000:10",
                                    "65000:65000:11"
                                ]
                            }
                        }
                    },
                    "20": {
                        "action": "permit",
                        "set": {
                            "community": {
                                "add": [
                                    "65000:10",
                                    "65001:11"
                                ]
                            },
                            "extcommunity": {
                                "bandwidth": "200",
                                "bandwidth-non-transitive": {}
                            },
                            "large-community": {
                                "add": [
                                    "65000:65000:10",
                                    "65000:65000:11"
                                ]
                            }
                        }
                    },
                    "30": {
                        "action": "permit",
                        "set": {
                            "community": {
                                "none": {}
                            },
                            "extcommunity": {
                                "none": {}
                            },
                            "large-community": {
                                "none": {}
                            }
                        }
                    }
                }
            }
        }
        for route_map, route_map_config in test_data.items():
            path = base_path + ['route-map', route_map]
            self.cli_set(path + ['description', f'VyOS ROUTE-MAP {route_map}'])
            if 'rule' not in route_map_config:
                continue

            for rule, rule_config in route_map_config['rule'].items():
                if 'action' in rule_config:
                    self.cli_set(path + ['rule', rule, 'action', rule_config['action']])
                if 'set' in rule_config:

                    #Add community in configuration
                    if 'community' in rule_config['set']:
                        if 'none' in rule_config['set']['community']:
                            self.cli_set(path + ['rule', rule, 'set', 'community', 'none'])
                        else:
                            community_path = path + ['rule', rule, 'set', 'community']
                            if 'add' in rule_config['set']['community']:
                                for community_unit in rule_config['set']['community']['add']:
                                    self.cli_set(community_path + ['add', community_unit])
                            if 'replace' in rule_config['set']['community']:
                                for community_unit in rule_config['set']['community']['replace']:
                                    self.cli_set(community_path + ['replace', community_unit])

                    #Add large-community in configuration
                    if 'large-community' in rule_config['set']:
                        if 'none' in rule_config['set']['large-community']:
                            self.cli_set(path + ['rule', rule, 'set', 'large-community', 'none'])
                        else:
                            community_path = path + ['rule', rule, 'set', 'large-community']
                            if 'add' in rule_config['set']['large-community']:
                                for community_unit in rule_config['set']['large-community']['add']:
                                    self.cli_set(community_path + ['add', community_unit])
                            if 'replace' in rule_config['set']['large-community']:
                                for community_unit in rule_config['set']['large-community']['replace']:
                                    self.cli_set(community_path + ['replace', community_unit])

                    #Add extcommunity in configuration
                    if 'extcommunity' in rule_config['set']:
                        if 'none' in rule_config['set']['extcommunity']:
                            self.cli_set(path + ['rule', rule, 'set', 'extcommunity', 'none'])
                        else:
                            if 'bandwidth' in rule_config['set']['extcommunity']:
                                self.cli_set(path + ['rule', rule, 'set', 'extcommunity', 'bandwidth', rule_config['set']['extcommunity']['bandwidth']])
                            if 'bandwidth-non-transitive' in rule_config['set']['extcommunity']:
                                self.cli_set(path + ['rule', rule, 'set','extcommunity', 'bandwidth-non-transitive'])
                            if 'rt' in rule_config['set']['extcommunity']:
                                for community_unit in rule_config['set']['extcommunity']['rt']:
                                    self.cli_set(path + ['rule', rule, 'set', 'extcommunity','rt',community_unit])
                            if 'soo' in rule_config['set']['extcommunity']:
                                for community_unit in rule_config['set']['extcommunity']['soo']:
                                    self.cli_set(path + ['rule', rule, 'set', 'extcommunity','soo',community_unit])
        self.cli_commit()

        for route_map, route_map_config in test_data.items():
            if 'rule' not in route_map_config:
                continue
            for rule, rule_config in route_map_config['rule'].items():
                name = f'route-map {route_map} {rule_config["action"]} {rule}'
                config = self.getFRRconfig(name)
                self.assertIn(name, config)

                if 'set' in rule_config:
                    #Check community
                    if 'community' in rule_config['set']:
                        if 'none' in rule_config['set']['community']:
                            tmp = f'set community none'
                            self.assertIn(tmp, config)
                        if 'replace' in rule_config['set']['community']:
                            values = ' '.join(rule_config['set']['community']['replace'])
                            tmp = f'set community {values}'
                            self.assertIn(tmp, config)
                        if 'add' in rule_config['set']['community']:
                            values = ' '.join(rule_config['set']['community']['add'])
                            tmp = f'set community {values} additive'
                            self.assertIn(tmp, config)
                    #Check large-community
                    if 'large-community' in rule_config['set']:
                        if 'none' in rule_config['set']['large-community']:
                            tmp = f'set large-community none'
                            self.assertIn(tmp, config)
                        if 'replace' in rule_config['set']['large-community']:
                            values = ' '.join(rule_config['set']['large-community']['replace'])
                            tmp = f'set large-community {values}'
                            self.assertIn(tmp, config)
                        if 'add' in rule_config['set']['large-community']:
                            values = ' '.join(rule_config['set']['large-community']['add'])
                            tmp = f'set large-community {values} additive'
                            self.assertIn(tmp, config)
                    #Check extcommunity
                    if 'extcommunity' in rule_config['set']:
                        if 'none' in rule_config['set']['extcommunity']:
                            tmp = 'set extcommunity none'
                            self.assertIn(tmp, config)
                        if 'bandwidth' in rule_config['set']['extcommunity']:
                            values = rule_config['set']['extcommunity']['bandwidth']
                            tmp = f'set extcommunity bandwidth {values}'
                            if 'bandwidth-non-transitive' in rule_config['set']['extcommunity']:
                                tmp = tmp + ' non-transitive'
                            self.assertIn(tmp, config)
                        if 'rt' in rule_config['set']['extcommunity']:
                            values = ' '.join(rule_config['set']['extcommunity']['rt'])
                            tmp = f'set extcommunity rt {values}'
                            self.assertIn(tmp, config)
                        if 'soo' in rule_config['set']['extcommunity']:
                            values = ' '.join(rule_config['set']['extcommunity']['soo'])
                            tmp = f'set extcommunity soo {values}'
                            self.assertIn(tmp, config)

    def test_route_map(self):
        access_list = '50'
        as_path_list = '100'
        test_interface = 'eth0'
        community_list = 'BGP-comm-0815'

        # ext community name only allows alphanumeric characters and no hyphen :/
        # maybe change this if possible in vyos-1x rewrite
        extcommunity_list = 'BGPextcomm123'

        large_community_list = 'bgp-large-community-123456'
        prefix_list = 'foo-pfx-list'
        ipv6_nexthop_address = 'fe80::1'
        local_pref = '300'
        metric = '50'
        peer = '2.3.4.5'
        peerv6 = '2001:db8::1'
        tag = '6542'
        goto = '25'

        ipv4_nexthop_address= '192.0.2.2'
        ipv4_prefix_len= '18'
        ipv6_prefix_len= '122'
        ipv4_nexthop_type= 'blackhole'
        ipv6_nexthop_type= 'blackhole'

        test_data = {
            'foo-map-bar' : {
                'rule' : {
                    '5' : {
                        'action' : 'permit',
                        'continue' : '20',
                    },
                    '10' : {
                        'action' : 'permit',
                        'call' : 'complicated-configuration',
                    },
                },
            },
            'a-matching-rule-0815': {
                'rule' : {
                    '5' : {
                        'action' : 'deny',
                        'match' : {
                            'as-path' : as_path_list,
                            'rpki-invalid': '',
                            'tag': tag,
                        },
                    },
                    '10' : {
                        'action' : 'permit',
                        'match' : {
                            'community' : community_list,
                            'interface' : test_interface,
                            'rpki-not-found': '',
                        },
                    },
                    '15' : {
                        'action' : 'permit',
                        'match' : {
                            'extcommunity' : extcommunity_list,
                            'rpki-valid': '',
                        },
                        'on-match' : {
                            'next' : '',
                        },
                    },
                    '20' : {
                        'action' : 'permit',
                        'match' : {
                            'ip-address-acl': access_list,
                            'ip-nexthop-acl': access_list,
                            'ip-route-source-acl': access_list,
                            'ipv6-address-acl': access_list,
                            'origin-incomplete' : '',
                        },
                        'on-match' : {
                            'goto' : goto,
                        },
                    },
                    '25' : {
                        'action' : 'permit',
                        'match' : {
                            'ip-address-pfx': prefix_list,
                            'ip-nexthop-pfx': prefix_list,
                            'ip-route-source-pfx': prefix_list,
                            'ipv6-address-pfx': prefix_list,
                            'origin-igp': '',
                        },
                    },
                    '30' : {
                        'action' : 'permit',
                        'match' : {
                            'ipv6-nexthop-address' : ipv6_nexthop_address,
                            'ipv6-nexthop-access-list' : access_list,
                            'ipv6-nexthop-prefix-list' : prefix_list,
                            'ipv6-nexthop-type' : ipv6_nexthop_type,
                            'ipv6-address-pfx-len' : ipv6_prefix_len,
                            'large-community' : large_community_list,
                            'local-pref' : local_pref,
                            'metric': metric,
                            'origin-egp': '',
                            'peer' : peer,
                        },
                    },

                    '31' : {
                        'action' : 'permit',
                        'match' : {
                            'peer' : peerv6,
                        },
                    },

                    '40' : {
                        'action' : 'permit',
                        'match' : {
                            'ip-nexthop-addr' : ipv4_nexthop_address,
                            'ip-address-pfx-len' : ipv4_prefix_len,
                        },
                    },
                    '42' : {
                        'action' : 'deny',
                        'match' : {
                            'ip-nexthop-plen' : ipv4_prefix_len,
                        },
                    },
                    '44' : {
                        'action' : 'permit',
                        'match' : {
                            'ip-nexthop-type' : ipv4_nexthop_type,
                        },
                    },
                },
            },
            'complicated-configuration' : {
                'rule' : {
                    '10' : {
                        'action' : 'deny',
                        'set' : {
                            'aggregator-as'           : '1234567890',
                            'aggregator-ip'           : '10.255.255.0',
                            'as-path-exclude'         : '1234',
                            'as-path-prepend'         : '1234567890 987654321',
                            'as-path-prepend-last-as' : '5',
                            'atomic-aggregate'        : '',
                            'distance'                : '110',
                            'ipv6-next-hop-global'    : '2001::1',
                            'ipv6-next-hop-local'     : 'fe80::1',
                            'ip-next-hop'             : '192.168.1.1',
                            'local-preference'        : '500',
                            'metric'                  : '150',
                            'metric-type'             : 'type-1',
                            'origin'                  : 'incomplete',
                            'l3vpn'                   : '',
                            'originator-id'           : '172.16.10.1',
                            'src'                     : '100.0.0.1',
                            'tag'                     : '65530',
                            'weight'                  : '2',
                        },
                    },
                },
            },
            'bandwidth-configuration' : {
                'rule' : {
                    '10' : {
                        'action' : 'deny',
                        'set' : {
                            'as-path-prepend'     : '100 100',
                            'distance'            : '200',
                            'extcommunity-bw'     : 'num-multipaths',
                        },
                    },
                },
            },
            'evpn-configuration' : {
                'rule' : {
                    '10' : {
                        'action' : 'permit',
                        'match' : {
                            'evpn-default-route'  : '',
                            'evpn-rd'             : '100:300',
                            'evpn-route-type'     : 'prefix',
                            'evpn-vni'            : '1234',
                        },
                    },
                    '20' : {
                        'action' : 'permit',
                        'set' : {
                            'as-path-exclude'     : 'all',
                            'evpn-gateway-ipv4'   : '192.0.2.99',
                            'evpn-gateway-ipv6'   : '2001:db8:f00::1',
                        },
                    },
                },
            },
            'match-protocol' : {
                'rule' : {
                    '10' : {
                        'action' : 'permit',
                        'match' : {
                            'protocol'  : 'static',
                        },
                    },
                    '20' : {
                        'action' : 'permit',
                        'match' : {
                            'protocol'   : 'bgp',
                        },
                    },
                },
            },
            'relative-metric' : {
                'rule' : {
                    '10' : {
                        'action' : 'permit',
                        'match' : {
                            'ip-nexthop-addr' : ipv4_nexthop_address,
                        },
                        'set' : {
                            'metric' : '+10',
                        },
                    },
                    '20' : {
                        'action' : 'permit',
                        'match' : {
                            'ip-nexthop-addr' : ipv4_nexthop_address,
                        },
                        'set' : {
                            'metric' : '-20',
                        },
                    },
                    '30': {
                        'action': 'permit',
                        'match': {
                            'ip-nexthop-addr': ipv4_nexthop_address,
                        },
                        'set': {
                            'metric': 'rtt',
                        },
                    },
                    '40': {
                        'action': 'permit',
                        'match': {
                            'ip-nexthop-addr': ipv4_nexthop_address,
                        },
                        'set': {
                            'metric': '+rtt',
                        },
                    },
                    '50': {
                        'action': 'permit',
                        'match': {
                            'ip-nexthop-addr': ipv4_nexthop_address,
                        },
                        'set': {
                            'metric': '-rtt',
                        },
                    },
                },
            },
        }

        self.cli_set(['policy', 'access-list', access_list, 'rule', '10', 'action', 'permit'])
        self.cli_set(['policy', 'access-list', access_list, 'rule', '10', 'source', 'host', '1.1.1.1'])
        self.cli_set(['policy', 'access-list6', access_list, 'rule', '10', 'action', 'permit'])
        self.cli_set(['policy', 'access-list6', access_list, 'rule', '10', 'source', 'network', '2001:db8::/32'])

        self.cli_set(['policy', 'as-path-list', as_path_list, 'rule', '10', 'action', 'permit'])
        self.cli_set(['policy', 'as-path-list', as_path_list, 'rule', '10', 'regex', '64501 64502'])
        self.cli_set(['policy', 'community-list', community_list, 'rule', '10', 'action', 'deny'])
        self.cli_set(['policy', 'community-list', community_list, 'rule', '10', 'regex', '65432'])
        self.cli_set(['policy', 'extcommunity-list', extcommunity_list, 'rule', '10', 'action', 'deny'])
        self.cli_set(['policy', 'extcommunity-list', extcommunity_list, 'rule', '10', 'regex', '65000'])
        self.cli_set(['policy', 'large-community-list', large_community_list, 'rule', '10', 'action', 'permit'])
        self.cli_set(['policy', 'large-community-list', large_community_list, 'rule', '10', 'regex', '100:200:300'])

        self.cli_set(['policy', 'prefix-list', prefix_list, 'rule', '10', 'action', 'permit'])
        self.cli_set(['policy', 'prefix-list', prefix_list, 'rule', '10', 'prefix', '192.0.2.0/24'])
        self.cli_set(['policy', 'prefix-list6', prefix_list, 'rule', '10', 'action', 'permit'])
        self.cli_set(['policy', 'prefix-list6', prefix_list, 'rule', '10', 'prefix', '2001:db8::/32'])

        for route_map, route_map_config in test_data.items():
            path = base_path + ['route-map', route_map]
            self.cli_set(path + ['description', f'VyOS ROUTE-MAP {route_map}'])
            if 'rule' not in route_map_config:
                continue

            for rule, rule_config in route_map_config['rule'].items():
                if 'action' in rule_config:
                    self.cli_set(path + ['rule', rule, 'action', rule_config['action']])

                if 'call' in rule_config:
                    self.cli_set(path + ['rule', rule, 'call', rule_config['call']])

                if 'continue' in rule_config:
                    self.cli_set(path + ['rule', rule, 'continue', rule_config['continue']])

                if 'match' in rule_config:
                    if 'as-path' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'as-path', rule_config['match']['as-path']])
                    if 'community' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'community', 'community-list', rule_config['match']['community']])
                        self.cli_set(path + ['rule', rule, 'match', 'community', 'exact-match'])
                    if 'evpn-default-route' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'evpn', 'default-route'])
                    if 'evpn-rd' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'evpn', 'rd', rule_config['match']['evpn-rd']])
                    if 'evpn-route-type' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'evpn', 'route-type', rule_config['match']['evpn-route-type']])
                    if 'evpn-vni' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'evpn', 'vni', rule_config['match']['evpn-vni']])
                    if 'extcommunity' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'extcommunity', rule_config['match']['extcommunity']])
                    if 'interface' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'interface', rule_config['match']['interface']])
                    if 'ip-address-acl' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'ip', 'address', 'access-list', rule_config['match']['ip-address-acl']])
                    if 'ip-address-pfx' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'ip', 'address', 'prefix-list', rule_config['match']['ip-address-pfx']])
                    if 'ip-address-pfx-len' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'ip', 'address', 'prefix-len', rule_config['match']['ip-address-pfx-len']])
                    if 'ip-nexthop-acl' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'ip', 'nexthop', 'access-list', rule_config['match']['ip-nexthop-acl']])
                    if 'ip-nexthop-pfx' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'ip', 'nexthop', 'prefix-list', rule_config['match']['ip-nexthop-pfx']])
                    if 'ip-nexthop-addr' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'ip', 'nexthop', 'address', rule_config['match']['ip-nexthop-addr']])
                    if 'ip-nexthop-plen' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'ip', 'nexthop', 'prefix-len', rule_config['match']['ip-nexthop-plen']])
                    if 'ip-nexthop-type' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'ip', 'nexthop', 'type', rule_config['match']['ip-nexthop-type']])
                    if 'ip-route-source-acl' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'ip', 'route-source', 'access-list', rule_config['match']['ip-route-source-acl']])
                    if 'ip-route-source-pfx' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'ip', 'route-source', 'prefix-list', rule_config['match']['ip-route-source-pfx']])
                    if 'ipv6-address-acl' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'ipv6', 'address', 'access-list', rule_config['match']['ipv6-address-acl']])
                    if 'ipv6-address-pfx' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'ipv6', 'address', 'prefix-list', rule_config['match']['ipv6-address-pfx']])
                    if 'ipv6-address-pfx-len' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'ipv6', 'address', 'prefix-len', rule_config['match']['ipv6-address-pfx-len']])
                    if 'ipv6-nexthop-address' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'ipv6', 'nexthop', 'address', rule_config['match']['ipv6-nexthop-address']])
                    if 'ipv6-nexthop-access-list' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'ipv6', 'nexthop', 'access-list', rule_config['match']['ipv6-nexthop-access-list']])
                    if 'ipv6-nexthop-prefix-list' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'ipv6', 'nexthop', 'prefix-list', rule_config['match']['ipv6-nexthop-prefix-list']])
                    if 'ipv6-nexthop-type' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'ipv6', 'nexthop', 'type', rule_config['match']['ipv6-nexthop-type']])
                    if 'large-community' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'large-community', 'large-community-list', rule_config['match']['large-community']])
                    if 'local-pref' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'local-preference', rule_config['match']['local-pref']])
                    if 'metric' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'metric', rule_config['match']['metric']])
                    if 'origin-igp' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'origin', 'igp'])
                    if 'origin-egp' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'origin', 'egp'])
                    if 'origin-incomplete' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'origin', 'incomplete'])
                    if 'peer' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'peer', rule_config['match']['peer']])
                    if 'rpki-invalid' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'rpki', 'invalid'])
                    if 'rpki-not-found' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'rpki', 'notfound'])
                    if 'rpki-valid' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'rpki', 'valid'])
                    if 'protocol' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'protocol', rule_config['match']['protocol']])
                    if 'tag' in rule_config['match']:
                        self.cli_set(path + ['rule', rule, 'match', 'tag', rule_config['match']['tag']])

                if 'on-match' in rule_config:
                    if 'goto' in rule_config['on-match']:
                        self.cli_set(path + ['rule', rule, 'on-match', 'goto', rule_config['on-match']['goto']])
                    if 'next' in rule_config['on-match']:
                        self.cli_set(path + ['rule', rule, 'on-match', 'next'])

                if 'set' in rule_config:
                    if 'aggregator-as' in rule_config['set']:
                        self.cli_set(path + ['rule', rule, 'set', 'aggregator', 'as', rule_config['set']['aggregator-as']])
                    if 'aggregator-ip' in rule_config['set']:
                        self.cli_set(path + ['rule', rule, 'set', 'aggregator', 'ip', rule_config['set']['aggregator-ip']])
                    if 'as-path-exclude' in rule_config['set']:
                        self.cli_set(path + ['rule', rule, 'set', 'as-path', 'exclude', rule_config['set']['as-path-exclude']])
                    if 'as-path-prepend' in rule_config['set']:
                        self.cli_set(path + ['rule', rule, 'set', 'as-path', 'prepend', rule_config['set']['as-path-prepend']])
                    if 'atomic-aggregate' in rule_config['set']:
                        self.cli_set(path + ['rule', rule, 'set', 'atomic-aggregate'])
                    if 'distance' in rule_config['set']:
                        self.cli_set(path + ['rule', rule, 'set', 'distance', rule_config['set']['distance']])
                    if 'ipv6-next-hop-global' in rule_config['set']:
                        self.cli_set(path + ['rule', rule, 'set', 'ipv6-next-hop', 'global', rule_config['set']['ipv6-next-hop-global']])
                    if 'ipv6-next-hop-local' in rule_config['set']:
                        self.cli_set(path + ['rule', rule, 'set', 'ipv6-next-hop', 'local', rule_config['set']['ipv6-next-hop-local']])
                    if 'ip-next-hop' in rule_config['set']:
                        self.cli_set(path + ['rule', rule, 'set', 'ip-next-hop', rule_config['set']['ip-next-hop']])
                    if 'l3vpn' in rule_config['set']:
                        self.cli_set(path + ['rule', rule, 'set', 'l3vpn-nexthop', 'encapsulation', 'gre'])
                    if 'local-preference' in rule_config['set']:
                        self.cli_set(path + ['rule', rule, 'set', 'local-preference', rule_config['set']['local-preference']])
                    if 'metric' in rule_config['set']:
                        self.cli_set(path + ['rule', rule, 'set', 'metric', rule_config['set']['metric']])
                    if 'metric-type' in rule_config['set']:
                        self.cli_set(path + ['rule', rule, 'set', 'metric-type', rule_config['set']['metric-type']])
                    if 'origin' in rule_config['set']:
                        self.cli_set(path + ['rule', rule, 'set', 'origin', rule_config['set']['origin']])
                    if 'originator-id' in rule_config['set']:
                        self.cli_set(path + ['rule', rule, 'set', 'originator-id', rule_config['set']['originator-id']])
                    if 'src' in rule_config['set']:
                        self.cli_set(path + ['rule', rule, 'set', 'src', rule_config['set']['src']])
                    if 'tag' in rule_config['set']:
                        self.cli_set(path + ['rule', rule, 'set', 'tag', rule_config['set']['tag']])
                    if 'weight' in rule_config['set']:
                        self.cli_set(path + ['rule', rule, 'set', 'weight', rule_config['set']['weight']])
                    if 'evpn-gateway-ipv4' in rule_config['set']:
                        self.cli_set(path + ['rule', rule, 'set', 'evpn', 'gateway', 'ipv4', rule_config['set']['evpn-gateway-ipv4']])
                    if 'evpn-gateway-ipv6' in rule_config['set']:
                        self.cli_set(path + ['rule', rule, 'set', 'evpn', 'gateway', 'ipv6', rule_config['set']['evpn-gateway-ipv6']])

        self.cli_commit()

        for route_map, route_map_config in test_data.items():
            if 'rule' not in route_map_config:
                continue
            for rule, rule_config in route_map_config['rule'].items():
                name = f'route-map {route_map} {rule_config["action"]} {rule}'
                config = self.getFRRconfig(name)
                self.assertIn(name, config)

                if 'call' in rule_config:
                    tmp = 'call ' + rule_config['call']
                    self.assertIn(tmp, config)

                if 'continue' in rule_config:
                    tmp = 'on-match goto ' + rule_config['continue']
                    self.assertIn(tmp, config)

                if 'match' in rule_config:
                    if 'as-path' in rule_config['match']:
                        tmp = 'match as-path ' + rule_config['match']['as-path']
                        self.assertIn(tmp, config)
                    if 'community' in rule_config['match']:
                        tmp = f'match community {rule_config["match"]["community"]} exact-match'
                        self.assertIn(tmp, config)
                    if 'evpn-default-route' in rule_config['match']:
                        tmp = f'match evpn default-route'
                        self.assertIn(tmp, config)
                    if 'evpn-rd' in rule_config['match']:
                        tmp = f'match evpn rd {rule_config["match"]["evpn-rd"]}'
                        self.assertIn(tmp, config)
                    if 'evpn-route-type' in rule_config['match']:
                        tmp = f'match evpn route-type {rule_config["match"]["evpn-route-type"]}'
                        self.assertIn(tmp, config)
                    if 'evpn-vni' in rule_config['match']:
                        tmp = f'match evpn vni {rule_config["match"]["evpn-vni"]}'
                        self.assertIn(tmp, config)
                    if 'extcommunity' in rule_config['match']:
                        tmp = f'match extcommunity {rule_config["match"]["extcommunity"]}'
                        self.assertIn(tmp, config)
                    if 'interface' in rule_config['match']:
                        tmp = f'match interface {rule_config["match"]["interface"]}'
                        self.assertIn(tmp, config)
                    if 'ip-address-acl' in rule_config['match']:
                        tmp = f'match ip address {rule_config["match"]["ip-address-acl"]}'
                        self.assertIn(tmp, config)
                    if 'ip-address-pfx' in rule_config['match']:
                        tmp = f'match ip address prefix-list {rule_config["match"]["ip-address-pfx"]}'
                        self.assertIn(tmp, config)
                    if 'ip-address-pfx-len' in rule_config['match']:
                        tmp = f'match ip address prefix-len {rule_config["match"]["ip-address-pfx-len"]}'
                        self.assertIn(tmp, config)
                    if 'ip-nexthop-acl' in rule_config['match']:
                        tmp = f'match ip next-hop {rule_config["match"]["ip-nexthop-acl"]}'
                        self.assertIn(tmp, config)
                    if 'ip-nexthop-pfx' in rule_config['match']:
                        tmp = f'match ip next-hop prefix-list {rule_config["match"]["ip-nexthop-pfx"]}'
                        self.assertIn(tmp, config)
                    if 'ip-nexthop-addr' in rule_config['match']:
                        tmp = f'match ip next-hop address {rule_config["match"]["ip-nexthop-addr"]}'
                        self.assertIn(tmp, config)
                    if 'ip-nexthop-plen' in rule_config['match']:
                        tmp = f'match ip next-hop prefix-len {rule_config["match"]["ip-nexthop-plen"]}'
                        self.assertIn(tmp, config)
                    if 'ip-nexthop-type' in rule_config['match']:
                        tmp = f'match ip next-hop type {rule_config["match"]["ip-nexthop-type"]}'
                        self.assertIn(tmp, config)
                    if 'ip-route-source-acl' in rule_config['match']:
                        tmp = f'match ip route-source {rule_config["match"]["ip-route-source-acl"]}'
                        self.assertIn(tmp, config)
                    if 'ip-route-source-pfx' in rule_config['match']:
                        tmp = f'match ip route-source prefix-list {rule_config["match"]["ip-route-source-pfx"]}'
                        self.assertIn(tmp, config)
                    if 'ipv6-address-acl' in rule_config['match']:
                        tmp = f'match ipv6 address {rule_config["match"]["ipv6-address-acl"]}'
                        self.assertIn(tmp, config)
                    if 'ipv6-address-pfx' in rule_config['match']:
                        tmp = f'match ipv6 address prefix-list {rule_config["match"]["ipv6-address-pfx"]}'
                        self.assertIn(tmp, config)
                    if 'ipv6-address-pfx-len' in rule_config['match']:
                        tmp = f'match ipv6 address prefix-len {rule_config["match"]["ipv6-address-pfx-len"]}'
                        self.assertIn(tmp, config)
                    if 'ipv6-nexthop-address' in rule_config['match']:
                        tmp = f'match ipv6 next-hop address {rule_config["match"]["ipv6-nexthop-address"]}'
                        self.assertIn(tmp, config)
                    if 'ipv6-nexthop-access-list' in rule_config['match']:
                        tmp = f'match ipv6 next-hop {rule_config["match"]["ipv6-nexthop-access-list"]}'
                        self.assertIn(tmp, config)
                    if 'ipv6-nexthop-prefix-list' in rule_config['match']:
                        tmp = f'match ipv6 next-hop prefix-list {rule_config["match"]["ipv6-nexthop-prefix-list"]}'
                        self.assertIn(tmp, config)
                    if 'ipv6-nexthop-type' in rule_config['match']:
                        tmp = f'match ipv6 next-hop type {rule_config["match"]["ipv6-nexthop-type"]}'
                        self.assertIn(tmp, config)
                    if 'large-community' in rule_config['match']:
                        tmp = f'match large-community {rule_config["match"]["large-community"]}'
                        self.assertIn(tmp, config)
                    if 'local-pref' in rule_config['match']:
                        tmp = f'match local-preference {rule_config["match"]["local-pref"]}'
                        self.assertIn(tmp, config)
                    if 'metric' in rule_config['match']:
                        tmp = f'match metric {rule_config["match"]["metric"]}'
                        self.assertIn(tmp, config)
                    if 'origin-igp' in rule_config['match']:
                        tmp = f'match origin igp'
                        self.assertIn(tmp, config)
                    if 'origin-egp' in rule_config['match']:
                        tmp = f'match origin egp'
                        self.assertIn(tmp, config)
                    if 'origin-incomplete' in rule_config['match']:
                        tmp = f'match origin incomplete'
                        self.assertIn(tmp, config)
                    if 'peer' in rule_config['match']:
                        tmp = f'match peer {rule_config["match"]["peer"]}'
                        self.assertIn(tmp, config)
                    if 'protocol' in rule_config['match']:
                        tmp = f'match source-protocol {rule_config["match"]["protocol"]}'
                        self.assertIn(tmp, config)
                    if 'rpki-invalid' in rule_config['match']:
                        tmp = f'match rpki invalid'
                        self.assertIn(tmp, config)
                    if 'rpki-not-found' in rule_config['match']:
                        tmp = f'match rpki notfound'
                        self.assertIn(tmp, config)
                    if 'rpki-valid' in rule_config['match']:
                        tmp = f'match rpki valid'
                        self.assertIn(tmp, config)
                    if 'tag' in rule_config['match']:
                        tmp = f'match tag {rule_config["match"]["tag"]}'
                        self.assertIn(tmp, config)

                if 'on-match' in rule_config:
                    if 'goto' in rule_config['on-match']:
                        tmp = f'on-match goto {rule_config["on-match"]["goto"]}'
                        self.assertIn(tmp, config)
                    if 'next' in rule_config['on-match']:
                        tmp = f'on-match next'
                        self.assertIn(tmp, config)

                if 'set' in rule_config:
                    tmp = ' set '
                    if 'aggregator-as' in rule_config['set']:
                        tmp += 'aggregator as ' + rule_config['set']['aggregator-as']
                    elif 'aggregator-ip' in rule_config['set']:
                        tmp += ' ' + rule_config['set']['aggregator-ip']
                    elif 'as-path-exclude' in rule_config['set']:
                        tmp += 'as-path exclude ' + rule_config['set']['as-path-exclude']
                    elif 'as-path-prepend' in rule_config['set']:
                        tmp += 'as-path prepend ' + rule_config['set']['as-path-prepend']
                    elif 'as-path-prepend-last-as' in rule_config['set']:
                        tmp += 'as-path prepend last-as' + rule_config['set']['as-path-prepend-last-as']
                    elif 'atomic-aggregate' in rule_config['set']:
                        tmp += 'atomic-aggregate'
                    elif 'distance' in rule_config['set']:
                        tmp += 'distance ' + rule_config['set']['distance']
                    elif 'ip-next-hop' in rule_config['set']:
                        tmp += 'ip next-hop ' + rule_config['set']['ip-next-hop']
                    elif 'ipv6-next-hop-global' in rule_config['set']:
                        tmp += 'ipv6 next-hop global ' + rule_config['set']['ipv6-next-hop-global']
                    elif 'ipv6-next-hop-local' in rule_config['set']:
                        tmp += 'ipv6 next-hop local ' + rule_config['set']['ipv6-next-hop-local']
                    elif 'l3vpn' in rule_config['set']:
                        tmp += 'l3vpn next-hop encapsulation gre'
                    elif 'local-preference' in rule_config['set']:
                        tmp += 'local-preference ' + rule_config['set']['local-preference']
                    elif 'metric' in rule_config['set']:
                        tmp += 'metric ' + rule_config['set']['metric']
                    elif 'metric-type' in rule_config['set']:
                        tmp += 'metric-type ' + rule_config['set']['metric-type']
                    elif 'origin' in rule_config['set']:
                        tmp += 'origin ' + rule_config['set']['origin']
                    elif 'originator-id' in rule_config['set']:
                        tmp += 'originator-id ' + rule_config['set']['originator-id']
                    elif 'src' in rule_config['set']:
                        tmp += 'src ' + rule_config['set']['src']
                    elif 'tag' in rule_config['set']:
                        tmp += 'tag ' + rule_config['set']['tag']
                    elif 'weight' in rule_config['set']:
                        tmp += 'weight ' + rule_config['set']['weight']
                    elif 'vpn-gateway-ipv4' in rule_config['set']:
                        tmp += 'evpn gateway ipv4 ' + rule_config['set']['vpn-gateway-ipv4']
                    elif 'vpn-gateway-ipv6' in rule_config['set']:
                        tmp += 'evpn gateway ipv6 ' + rule_config['set']['vpn-gateway-ipv6']

                    self.assertIn(tmp, config)


    # Test set table for some sources
    def test_table_id(self):
        path = base_path + ['local-route']

        sources = ['203.0.113.1', '203.0.113.2']
        rule = '50'
        table = '23'
        for src in sources:
            self.cli_set(path + ['rule', rule, 'set', 'table', table])
            self.cli_set(path + ['rule', rule, 'source', 'address', src])

        self.cli_commit()

        original = """
        50:	from 203.0.113.1 lookup 23
        50:	from 203.0.113.2 lookup 23
        """
        tmp = cmd('ip rule show prio 50')

        self.assertEqual(sort_ip(tmp), sort_ip(original))

    # Test set table for fwmark
    def test_fwmark_table_id(self):
        path = base_path + ['local-route']

        fwmk = '24'
        rule = '101'
        table = '154'

        self.cli_set(path + ['rule', rule, 'set', 'table', table])
        self.cli_set(path + ['rule', rule, 'fwmark', fwmk])

        self.cli_commit()

        original = """
        101:    from all fwmark 0x18 lookup 154
        """
        tmp = cmd('ip rule show prio 101')

        self.assertEqual(sort_ip(tmp), sort_ip(original))

    # Test set table for destination
    def test_destination_table_id(self):
        path = base_path + ['local-route']

        dst = '203.0.113.1'
        rule = '102'
        table = '154'

        self.cli_set(path + ['rule', rule, 'set', 'table', table])
        self.cli_set(path + ['rule', rule, 'destination', 'address', dst])

        self.cli_commit()

        original = """
        102:    from all to 203.0.113.1 lookup 154
        """
        tmp = cmd('ip rule show prio 102')

        self.assertEqual(sort_ip(tmp), sort_ip(original))

    # Test set table for destination and protocol
    def test_protocol_destination_table_id(self):
        path = base_path + ['local-route']

        dst = '203.0.113.12'
        rule = '85'
        table = '104'
        proto = 'tcp'

        self.cli_set(path + ['rule', rule, 'set', 'table', table])
        self.cli_set(path + ['rule', rule, 'destination', 'address', dst])
        self.cli_set(path + ['rule', rule, 'protocol', proto])

        self.cli_commit()

        original = """
        85:	from all to 203.0.113.12 ipproto tcp lookup 104
        """
        tmp = cmd('ip rule show prio 85')

        self.assertEqual(sort_ip(tmp), sort_ip(original))

    # Test set table for destination, source, protocol, fwmark and port
    def test_protocol_port_address_fwmark_table_id(self):
        path = base_path + ['local-route']

        dst = '203.0.113.5'
        src_list = ['203.0.113.1', '203.0.113.2']
        rule = '23'
        fwmark = '123456'
        table = '123'
        new_table = '111'
        proto = 'udp'
        new_proto = 'tcp'
        src_port = '5555'
        dst_port = '8888'

        self.cli_set(path + ['rule', rule, 'set', 'table', table])
        self.cli_set(path + ['rule', rule, 'destination', 'address', dst])
        self.cli_set(path + ['rule', rule, 'source', 'port', src_port])
        self.cli_set(path + ['rule', rule, 'protocol', proto])
        self.cli_set(path + ['rule', rule, 'fwmark', fwmark])
        self.cli_set(path + ['rule', rule, 'destination', 'port', dst_port])
        for src in src_list:
            self.cli_set(path + ['rule', rule, 'source', 'address', src])

        self.cli_commit()

        original = """
        23:	from 203.0.113.1 to 203.0.113.5 fwmark 0x1e240 ipproto udp sport 5555 dport 8888 lookup 123
        23:	from 203.0.113.2 to 203.0.113.5 fwmark 0x1e240 ipproto udp sport 5555 dport 8888 lookup 123
        """
        tmp = cmd(f'ip rule show prio {rule}')

        self.assertEqual(sort_ip(tmp), sort_ip(original))

        # Change table and protocol, delete fwmark and source port
        self.cli_delete(path + ['rule', rule, 'fwmark'])
        self.cli_delete(path + ['rule', rule, 'source', 'port'])
        self.cli_set(path + ['rule', rule, 'set', 'table', new_table])
        self.cli_set(path + ['rule', rule, 'protocol', new_proto])

        self.cli_commit()

        original = """
        23:	from 203.0.113.1 to 203.0.113.5 ipproto tcp dport 8888 lookup 111
        23:	from 203.0.113.2 to 203.0.113.5 ipproto tcp dport 8888 lookup 111
        """
        tmp = cmd(f'ip rule show prio {rule}')

        self.assertEqual(sort_ip(tmp), sort_ip(original))

    # Test set table for sources with fwmark
    def test_fwmark_sources_table_id(self):
        path = base_path + ['local-route']

        sources = ['203.0.113.11', '203.0.113.12']
        fwmk = '23'
        rule = '100'
        table = '150'
        for src in sources:
            self.cli_set(path + ['rule', rule, 'set', 'table', table])
            self.cli_set(path + ['rule', rule, 'source', 'address', src])
            self.cli_set(path + ['rule', rule, 'fwmark', fwmk])

        self.cli_commit()

        original = """
        100:	from 203.0.113.11 fwmark 0x17 lookup 150
        100:	from 203.0.113.12 fwmark 0x17 lookup 150
        """
        tmp = cmd('ip rule show prio 100')

        self.assertEqual(sort_ip(tmp), sort_ip(original))

    # Test set table for sources with iif
    def test_iif_sources_table_id(self):
        path = base_path + ['local-route']

        sources = ['203.0.113.11', '203.0.113.12']
        iif = 'lo'
        rule = '100'
        table = '150'

        self.cli_set(path + ['rule', rule, 'set', 'table', table])
        self.cli_set(path + ['rule', rule, 'inbound-interface', iif])
        for src in sources:
            self.cli_set(path + ['rule', rule, 'source', 'address', src])

        self.cli_commit()

        # Check generated configuration
        # Expected values
        original = """
        100:	from 203.0.113.11 iif lo lookup 150
        100:	from 203.0.113.12 iif lo lookup 150
        """
        tmp = cmd('ip rule show prio 100')

        self.assertEqual(sort_ip(tmp), sort_ip(original))

    # Test set table for sources and destinations with fwmark
    def test_fwmark_sources_destination_table_id(self):
        path = base_path + ['local-route']

        sources = ['203.0.113.11', '203.0.113.12']
        destinations = ['203.0.113.13', '203.0.113.15']
        fwmk = '23'
        rule = '103'
        table = '150'
        for src in sources:
            for dst in destinations:
                self.cli_set(path + ['rule', rule, 'set', 'table', table])
                self.cli_set(path + ['rule', rule, 'source', 'address', src])
                self.cli_set(path + ['rule', rule, 'destination', 'address', dst])
                self.cli_set(path + ['rule', rule, 'fwmark', fwmk])

        self.cli_commit()

        original = """
        103:	from 203.0.113.11 to 203.0.113.13 fwmark 0x17 lookup 150
        103:	from 203.0.113.11 to 203.0.113.15 fwmark 0x17 lookup 150
        103:	from 203.0.113.12 to 203.0.113.13 fwmark 0x17 lookup 150
        103:	from 203.0.113.12 to 203.0.113.15 fwmark 0x17 lookup 150
        """
        tmp = cmd('ip rule show prio 103')

        self.assertEqual(sort_ip(tmp), sort_ip(original))

    # Test set table ipv6 for some sources ipv6
    def test_ipv6_table_id(self):
        path = base_path + ['local-route6']

        sources = ['2001:db8:123::/48', '2001:db8:126::/48']
        rule = '50'
        table = '23'
        for src in sources:
            self.cli_set(path + ['rule', rule, 'set', 'table', table])
            self.cli_set(path + ['rule', rule, 'source', 'address', src])

        self.cli_commit()

        original = """
        50:	from 2001:db8:123::/48 lookup 23
        50:	from 2001:db8:126::/48 lookup 23
        """
        tmp = cmd('ip -6 rule show prio 50')

        self.assertEqual(sort_ip(tmp), sort_ip(original))

    # Test set table for fwmark ipv6
    def test_fwmark_ipv6_table_id(self):
        path = base_path + ['local-route6']

        fwmk = '24'
        rule = '100'
        table = '154'

        self.cli_set(path + ['rule', rule, 'set', 'table', table])
        self.cli_set(path + ['rule', rule, 'fwmark', fwmk])

        self.cli_commit()

        original = """
        100:    from all fwmark 0x18 lookup 154
        """
        tmp = cmd('ip -6 rule show prio 100')

        self.assertEqual(sort_ip(tmp), sort_ip(original))

    # Test set table for destination ipv6
    def test_destination_ipv6_table_id(self):
        path = base_path + ['local-route6']

        dst = '2001:db8:1337::/126'
        rule = '101'
        table = '154'

        self.cli_set(path + ['rule', rule, 'set', 'table', table])
        self.cli_set(path + ['rule', rule, 'destination', 'address', dst])

        self.cli_commit()

        original = """
        101:    from all to 2001:db8:1337::/126 lookup 154
        """
        tmp = cmd('ip -6 rule show prio 101')

        self.assertEqual(sort_ip(tmp), sort_ip(original))

    # Test set table for sources with fwmark ipv6
    def test_fwmark_sources_ipv6_table_id(self):
        path = base_path + ['local-route6']

        sources = ['2001:db8:1338::/126', '2001:db8:1339::/126']
        fwmk = '23'
        rule = '102'
        table = '150'
        for src in sources:
            self.cli_set(path + ['rule', rule, 'set', 'table', table])
            self.cli_set(path + ['rule', rule, 'source', 'address', src])
            self.cli_set(path + ['rule', rule, 'fwmark', fwmk])

        self.cli_commit()

        original = """
        102:	from 2001:db8:1338::/126 fwmark 0x17 lookup 150
        102:	from 2001:db8:1339::/126 fwmark 0x17 lookup 150
        """
        tmp = cmd('ip -6 rule show prio 102')

        self.assertEqual(sort_ip(tmp), sort_ip(original))

    # Test set table for sources with iif ipv6
    def test_iif_sources_ipv6_table_id(self):
        path = base_path + ['local-route6']

        sources = ['2001:db8:1338::/126', '2001:db8:1339::/126']
        iif = 'lo'
        rule = '102'
        table = '150'
        for src in sources:
            self.cli_set(path + ['rule', rule, 'set', 'table', table])
            self.cli_set(path + ['rule', rule, 'source', 'address', src])
            self.cli_set(path + ['rule', rule, 'inbound-interface', iif])

        self.cli_commit()

        # Check generated configuration
        # Expected values
        original = """
        102:	from 2001:db8:1338::/126 iif lo lookup 150
        102:	from 2001:db8:1339::/126 iif lo lookup 150
        """
        tmp = cmd('ip -6 rule show prio 102')

        self.assertEqual(sort_ip(tmp), sort_ip(original))

    # Test set table for sources and destinations with fwmark ipv6
    def test_fwmark_sources_destination_ipv6_table_id(self):
        path = base_path + ['local-route6']

        sources = ['2001:db8:1338::/126', '2001:db8:1339::/56']
        destinations = ['2001:db8:13::/48', '2001:db8:16::/48']
        fwmk = '23'
        rule = '103'
        table = '150'
        for src in sources:
            for dst in destinations:
                self.cli_set(path + ['rule', rule, 'set', 'table', table])
                self.cli_set(path + ['rule', rule, 'source', 'address', src])
                self.cli_set(path + ['rule', rule, 'destination', 'address', dst])
                self.cli_set(path + ['rule', rule, 'fwmark', fwmk])

        self.cli_commit()

        original = """
        103:	from 2001:db8:1338::/126 to 2001:db8:13::/48 fwmark 0x17 lookup 150
        103:	from 2001:db8:1338::/126 to 2001:db8:16::/48 fwmark 0x17 lookup 150
        103:	from 2001:db8:1339::/56 to 2001:db8:13::/48 fwmark 0x17 lookup 150
        103:	from 2001:db8:1339::/56 to 2001:db8:16::/48 fwmark 0x17 lookup 150
        """
        tmp = cmd('ip -6 rule show prio 103')

        self.assertEqual(sort_ip(tmp), sort_ip(original))

    # Test delete table for sources and destination with fwmark ipv4/ipv6
    def test_delete_ipv4_ipv6_table_id(self):
        path = base_path + ['local-route']
        path_v6 = base_path + ['local-route6']

        sources = ['203.0.113.0/24', '203.0.114.5']
        destinations = ['203.0.112.0/24', '203.0.116.5']
        sources_v6 = ['2001:db8:1338::/126', '2001:db8:1339::/56']
        destinations_v6 = ['2001:db8:13::/48', '2001:db8:16::/48']
        fwmk = '23'
        rule = '103'
        table = '150'
        for src in sources:
            for dst in destinations:
                self.cli_set(path + ['rule', rule, 'set', 'table', table])
                self.cli_set(path + ['rule', rule, 'source', 'address', src])
                self.cli_set(path + ['rule', rule, 'destination', 'address', dst])
                self.cli_set(path + ['rule', rule, 'fwmark', fwmk])

        for src in sources_v6:
            for dst in destinations_v6:
                self.cli_set(path_v6 + ['rule', rule, 'set', 'table', table])
                self.cli_set(path_v6 + ['rule', rule, 'source', 'address', src])
                self.cli_set(path_v6 + ['rule', rule, 'destination', 'address', dst])
                self.cli_set(path_v6 + ['rule', rule, 'fwmark', fwmk])

        self.cli_commit()

        original = """
        103:	from 203.0.113.0/24 to 203.0.116.5 fwmark 0x17 lookup 150
        103:	from 203.0.114.5 to 203.0.112.0/24 fwmark 0x17 lookup 150
        103:	from 203.0.114.5 to 203.0.116.5 fwmark 0x17 lookup 150
        103:	from 203.0.113.0/24 to 203.0.112.0/24 fwmark 0x17 lookup 150
        """
        original_v6 = """
        103:	from 2001:db8:1338::/126 to 2001:db8:16::/48 fwmark 0x17 lookup 150
        103:	from 2001:db8:1339::/56 to 2001:db8:13::/48 fwmark 0x17 lookup 150
        103:	from 2001:db8:1339::/56 to 2001:db8:16::/48 fwmark 0x17 lookup 150
        103:	from 2001:db8:1338::/126 to 2001:db8:13::/48 fwmark 0x17 lookup 150
        """
        tmp = cmd('ip rule show prio 103')
        tmp_v6 = cmd('ip -6 rule show prio 103')

        self.assertEqual(sort_ip(tmp), sort_ip(original))
        self.assertEqual(sort_ip(tmp_v6), sort_ip(original_v6))

        self.cli_delete(path)
        self.cli_delete(path_v6)
        self.cli_commit()

        tmp = cmd('ip rule show prio 103')
        tmp_v6 = cmd('ip -6 rule show prio 103')

        self.assertEqual(sort_ip(tmp), [])
        self.assertEqual(sort_ip(tmp_v6), [])

    # Test multiple commits ipv4
    def test_multiple_commit_ipv4_table_id(self):
        path = base_path + ['local-route']

        sources = ['192.0.2.1', '192.0.2.2']
        destination = '203.0.113.25'
        rule = '105'
        table = '151'
        self.cli_set(path + ['rule', rule, 'set', 'table', table])
        for src in sources:
            self.cli_set(path + ['rule', rule, 'source', 'address', src])

        self.cli_commit()

        original_first = """
        105:	from 192.0.2.1 lookup 151
        105:	from 192.0.2.2 lookup 151
        """
        tmp = cmd('ip rule show prio 105')

        self.assertEqual(sort_ip(tmp), sort_ip(original_first))

        # Create second commit with added destination
        self.cli_set(path + ['rule', rule, 'destination', 'address', destination])
        self.cli_commit()

        original_second = """
        105:	from 192.0.2.1 to 203.0.113.25 lookup 151
        105:	from 192.0.2.2 to 203.0.113.25 lookup 151
        """
        tmp = cmd('ip rule show prio 105')

        self.assertEqual(sort_ip(tmp), sort_ip(original_second))

    def test_frr_individual_remove_T6283_T6250(self):
        path = base_path + ['route-map']
        route_maps = ['RMAP-1', 'RMAP_2']
        seq = '10'
        base_local_preference = 300
        base_table = 50

        # T6250
        local_preference = base_local_preference
        table = base_table
        for route_map in route_maps:
            self.cli_set(path + [route_map, 'rule', seq, 'action', 'permit'])
            self.cli_set(path + [route_map, 'rule', seq, 'set', 'table', str(table)])
            self.cli_set(path + [route_map, 'rule', seq, 'set', 'local-preference', str(local_preference)])
            local_preference += 20
            table += 5

        self.cli_commit()

        local_preference = base_local_preference
        table = base_table
        for route_map in route_maps:
            config = self.getFRRconfig(f'route-map {route_map} permit {seq}', end='')
            self.assertIn(f' set local-preference {local_preference}', config)
            self.assertIn(f' set table {table}', config)
            local_preference += 20
            table += 5

        for route_map in route_maps:
            self.cli_delete(path + [route_map, 'rule', '10', 'set', 'table'])
            # we explicitly commit multiple times to be as vandal as possible to the system
            self.cli_commit()

        local_preference = base_local_preference
        for route_map in route_maps:
            config = self.getFRRconfig(f'route-map {route_map} permit {seq}', end='')
            self.assertIn(f' set local-preference {local_preference}', config)
            local_preference += 20

        # T6283
        seq = '20'
        prepend = '100 100 100'
        for route_map in route_maps:
            self.cli_set(path + [route_map, 'rule', seq, 'action', 'permit'])
            self.cli_set(path + [route_map, 'rule', seq, 'set', 'as-path', 'prepend', prepend])

        self.cli_commit()

        for route_map in route_maps:
            config = self.getFRRconfig(f'route-map {route_map} permit {seq}', end='')
            self.assertIn(f' set as-path prepend {prepend}', config)

        for route_map in route_maps:
            self.cli_delete(path + [route_map, 'rule', seq, 'set'])
            # we explicitly commit multiple times to be as vandal as possible to the system
            self.cli_commit()

        for route_map in route_maps:
            config = self.getFRRconfig(f'route-map {route_map} permit {seq}', end='')
            self.assertNotIn(f' set', config)

def sort_ip(output):
    o = '\n'.join([' '.join(line.strip().split()) for line in output.strip().splitlines()])
    o = o.splitlines()
    o.sort()
    return o

if __name__ == '__main__':
    unittest.main(verbosity=2)
