#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
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
from vyos.util import cmd

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
                    '10' : {
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
                    '10' : {
                        'action' : 'permit',
                        'destination' : { 'any' : '' },
                        'source' : { 'network' : '10.0.0.0', 'inverse-mask' : '0.255.255.255' },
                    },
                    '20' : {
                        'action' : 'permit',
                        'destination' : { 'any' : '' },
                        'source' : { 'network' : '172.16.0.0', 'inverse-mask' : '0.15.255.255' },
                    },
                    '30' : {
                        'action' : 'permit',
                        'destination' : { 'any' : '' },
                        'source' : { 'network' : '192.168.0.0', 'inverse-mask' : '0.0.255.255' },
                    },
                    '50' : {
                        'action' : 'permit',
                        'destination' : { 'network' : '172.16.0.0', 'inverse-mask' : '0.15.255.255' },
                        'source' : { 'network' : '10.0.0.0', 'inverse-mask' : '0.255.255.255' },
                    },
                    '60' : {
                        'action' : 'deny',
                        'destination' : { 'network' : '192.168.0.0', 'inverse-mask' : '0.0.255.255' },
                        'source' : { 'network' : '172.16.0.0', 'inverse-mask' : '0.15.255.255' },
                    },
                    '70' : {
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
            seq = '5'
            for rule, rule_config in acl_config['rule'].items():
                tmp = f'access-list {acl} seq {seq}'
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
                            tmp += ' ' + rule_config[direction]['host']
                        if 'network' in rule_config[direction]:
                            tmp += ' ' + rule_config[direction]['network'] + ' ' + rule_config[direction]['inverse-mask']

                self.assertIn(tmp, config)
                seq = int(seq) + 5

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
                    '10' : {
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
                    '100' : {
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
            seq = '5'
            for rule, rule_config in acl_config['rule'].items():
                tmp = f'ipv6 access-list {acl} seq {seq}'
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
                seq = int(seq) + 5


    def test_as_path_list(self):
        test_data = {
            'VyOS' : {
                'rule' : {
                    '10' : {
                        'action' : 'permit',
                        'regex'  : '^44501 64502$',
                    },
                    '20' : {
                        'action' : 'permit',
                        'regex'  : '44501|44502|44503',
                    },
                    '30' : {
                        'action' : 'permit',
                        'regex'  : '^44501_([0-9]+_)+',
                    },
                },
            },
            'Customers' : {
                'rule' : {
                    '10' : {
                        'action' : 'permit',
                        'regex'  : '_10_',
                    },
                    '20' : {
                        'action' : 'permit',
                        'regex'  : '_20_',
                    },
                    '30' : {
                        'action' : 'permit',
                        'regex'  : '_30_',
                    },
                    '30' : {
                        'action' : 'deny',
                        'regex'  : '_40_',
                    },
                },
            },
            'bogons' : {
                'rule' : {
                    '10' : {
                        'action' : 'permit',
                        'regex'  : '_0_',
                    },
                    '20' : {
                        'action' : 'permit',
                        'regex'  : '_23456_',
                    },
                    '30' : {
                        'action' : 'permit',
                        'regex'  : '_6449[6-9]_|_65[0-4][0-9][0-9]_|_655[0-4][0-9]_|_6555[0-1]_',
                    },
                    '30' : {
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
                tmp = f'bgp as-path access-list {as_path}'
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
                    '4' : {
                        'action' : 'permit',
                        'regex'  : '.*',
                    },
                },
            },
            '200' : {
                'rule' : {
                    '1' : {
                        'action' : 'deny',
                        'regex'  : '^1:201$',
                    },
                    '2' : {
                        'action' : 'deny',
                        'regex'  : '1:101$',
                    },
                    '3' : {
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
                    '4' : {
                        'action' : 'permit',
                        'regex'  : '.*',
                    },
                },
            },
            '200' : {
                'rule' : {
                    '1' : {
                        'action' : 'deny',
                        'regex'  : '^1:201$',
                    },
                    '2' : {
                        'action' : 'deny',
                        'regex'  : '1:101$',
                    },
                    '3' : {
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
                    '10' : {
                        'action' : 'permit',
                        'regex'  : '667:123:100',
                    },
                },
            },
            'bar' : {
                'rule' : {
                    '10' : {
                        'action' : 'permit',
                        'regex'  : '65000:120:10',
                    },
                    '20' : {
                        'action' : 'permit',
                        'regex'  : '65000:120:20',
                    },
                    '30' : {
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
                    '10' : {
                        'action' : 'permit',
                        'prefix'  : '10.0.0.0/8',
                        'ge' : '16',
                        'le' : '24',
                    },
                    '20' : {
                        'action' : 'deny',
                        'prefix'  : '172.16.0.0/12',
                        'ge' : '16',
                    },
                    '30' : {
                        'action' : 'permit',
                        'prefix'  : '192.168.0.0/16',
                    },
                },
            },
            'bar' : {
                'rule' : {
                    '10' : {
                        'action' : 'permit',
                        'prefix'  : '10.0.10.0/24',
                        'ge' : '25',
                        'le' : '26',
                    },
                    '20' : {
                        'action' : 'deny',
                        'prefix'  : '10.0.20.0/24',
                        'le' : '25',
                    },
                    '25' : {
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
                    '10' : {
                        'action' : 'permit',
                        'prefix'  : '2001:db8::/32',
                        'ge' : '40',
                        'le' : '48',
                    },
                    '20' : {
                        'action' : 'deny',
                        'prefix'  : '2001:db8::/32',
                        'ge' : '48',
                    },
                    '30' : {
                        'action' : 'permit',
                        'prefix'  : '2001:db8:1000::/64',
                    },
                },
            },
            'bar' : {
                'rule' : {
                    '10' : {
                        'action' : 'permit',
                        'prefix'  : '2001:db8:100::/40',
                        'ge' : '48',
                    },
                    '20' : {
                        'action' : 'permit',
                        'prefix'  : '2001:db8:200::/40',
                        'ge' : '48',
                    },
                    '25' : {
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


    # Test set table for some sources
    def test_table_id(self):
        path = base_path + ['local-route']

        sources = ['203.0.113.1', '203.0.113.2']
        rule = '50'
        table = '23'
        for src in sources:
            self.cli_set(path + ['rule', rule, 'set', 'table', table])
            self.cli_set(path + ['rule', rule, 'source', src])

        self.cli_commit()

        # Check generated configuration

        # Expected values
        original = """
        50:	from 203.0.113.1 lookup 23
        50:	from 203.0.113.2 lookup 23
        """
        tmp = cmd('ip rule show prio 50')
        original = original.split()
        tmp = tmp.split()

        self.assertEqual(tmp, original)

    # Test set table for fwmark
    def test_fwmark_table_id(self):
        path = base_path + ['local-route']

        fwmk = '24'
        rule = '101'
        table = '154'

        self.cli_set(path + ['rule', rule, 'set', 'table', table])
        self.cli_set(path + ['rule', rule, 'fwmark', fwmk])

        self.cli_commit()

        # Check generated configuration

        # Expected values
        original = """
        101:    from all fwmark 0x18 lookup 154
        """
        tmp = cmd('ip rule show prio 101')
        original = original.split()
        tmp = tmp.split()

        self.assertEqual(tmp, original)

    # Test set table for sources with fwmark
    def test_fwmark_sources_table_id(self):
        path = base_path + ['local-route']

        sources = ['203.0.113.11', '203.0.113.12']
        fwmk = '23'
        rule = '100'
        table = '150'
        for src in sources:
            self.cli_set(path + ['rule', rule, 'set', 'table', table])
            self.cli_set(path + ['rule', rule, 'source', src])
            self.cli_set(path + ['rule', rule, 'fwmark', fwmk])

        self.cli_commit()

        # Check generated configuration

        # Expected values
        original = """
        100:	from 203.0.113.11 fwmark 0x17 lookup 150
        100:	from 203.0.113.12 fwmark 0x17 lookup 150
        """
        tmp = cmd('ip rule show prio 100')
        original = original.split()
        tmp = tmp.split()

        self.assertEqual(tmp, original)

if __name__ == '__main__':
    unittest.main(verbosity=2)
