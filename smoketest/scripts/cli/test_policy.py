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

import os
import unittest

from vyos.util import cmd
from vyos.configsession import ConfigSession
from vyos.configsession import ConfigSessionError

base_path = ['policy']

def getFRRconfig(section):
    return cmd(f'vtysh -c "show run" | sed -n "/^{section}/,/^!/p"')

class TestPolicy(unittest.TestCase):
    def setUp(self):
        self.session = ConfigSession(os.getpid())

    def tearDown(self):
        self.session.delete(base_path)
        self.session.commit()
        del self.session

    def test_access_list(self):
        acl_number = ['50', '150', '1500', '2500']

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
        }

        for acl, acl_config in acls.items():
            acl_base = base_path + ['access-list', acl]
            self.session.set(acl_base + ['description', f'VyOS-ACL-{acl}'])
            if 'rule' not in acl_config:
                continue

            for rule, rule_config in acl_config['rule'].items():
                self.session.set(acl_base + ['rule', rule, 'action', rule_config['action']])
                for direction in ['source', 'destination']:
                    if direction in rule_config:
                        if 'any' in rule_config[direction]:
                            self.session.set(acl_base + ['rule', rule, direction, 'any'])
                        elif 'host' in rule_config[direction]:
                            self.session.set(acl_base + ['rule', rule, direction, 'host', rule_config[direction]['host']])

        self.session.commit()

        config = getFRRconfig('access-list')
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

                self.assertIn(tmp, config)
                seq = int(seq) + 5

if __name__ == '__main__':
    unittest.main(verbosity=2)
