#!/usr/bin/env python3
#
# Copyright (C) 2020-2021 VyOS maintainers and contributors
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

from sys import exit

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.configdict import node_changed
from vyos.configdict import leaf_node_changed
from vyos.template import render
from vyos.util import call
from vyos import ConfigError
from vyos import airbag
airbag.enable()


def get_config(config=None):

    if config:
        conf = config
    else:
        conf = Config()
    base = ['policy', 'local-route']
    pbr = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)

    # delete policy local-route
    dict = {}
    tmp = node_changed(conf, ['policy', 'local-route', 'rule'], key_mangling=('-', '_'))
    if tmp:
        for rule in (tmp or []):
            src = leaf_node_changed(conf, ['policy', 'local-route', 'rule', rule, 'source'])
            fwmk = leaf_node_changed(conf, ['policy', 'local-route', 'rule', rule, 'fwmark'])
            if src:
                dict = dict_merge({'rule_remove' : {rule : {'source' : src}}}, dict)
                pbr.update(dict)
            if fwmk:
                dict = dict_merge({'rule_remove' : {rule : {'fwmark' : fwmk}}}, dict)
                pbr.update(dict)

    # delete policy local-route rule x source x.x.x.x
    # delete policy local-route rule x fwmark x
    if 'rule' in pbr:
        for rule in pbr['rule']:
            src = leaf_node_changed(conf, ['policy', 'local-route', 'rule', rule, 'source'])
            fwmk = leaf_node_changed(conf, ['policy', 'local-route', 'rule', rule, 'fwmark'])
            if src:
                dict = dict_merge({'rule_remove' : {rule : {'source' : src}}}, dict)
                pbr.update(dict)
            if fwmk:
                dict = dict_merge({'rule_remove' : {rule : {'fwmark' : fwmk}}}, dict)
                pbr.update(dict)

    return pbr

def verify(pbr):
    # bail out early - looks like removal from running config
    if not pbr:
        return None

    if 'rule' in pbr:
        for rule in pbr['rule']:
            if 'source' not in pbr['rule'][rule] and 'fwmark' not in pbr['rule'][rule]:
                raise ConfigError('Source address or fwmark is required!')
            else:
                if 'set' not in pbr['rule'][rule] or 'table' not in pbr['rule'][rule]['set']:
                    raise ConfigError('Table set is required!')

    return None

def generate(pbr):
    if not pbr:
        return None

    return None

def apply(pbr):
    if not pbr:
        return None

    # Delete old rule if needed
    if 'rule_remove' in pbr:
        for rule in pbr['rule_remove']:
            if 'source' in pbr['rule_remove'][rule]:
                for src in pbr['rule_remove'][rule]['source']:
                    call(f'ip rule del prio {rule} from {src}')
            if 'fwmark' in  pbr['rule_remove'][rule]:
                for fwmk in pbr['rule_remove'][rule]['fwmark']:
                    call(f'ip rule del prio {rule} from all fwmark {fwmk}')

    # Generate new config
    if 'rule' in pbr:
        for rule in pbr['rule']:
            table = pbr['rule'][rule]['set']['table']
            # Only source in the rule
            # set policy local-route rule 100 source '203.0.113.1'
            if 'source' in pbr['rule'][rule] and not 'fwmark' in pbr['rule'][rule]:
                for src in pbr['rule'][rule]['source']:
                    call(f'ip rule add prio {rule} from {src} lookup {table}')
            # Only fwmark in the rule
            # set policy local-route rule 101 fwmark '23'
            if 'fwmark' in pbr['rule'][rule] and not 'source' in pbr['rule'][rule]:
                fwmk = pbr['rule'][rule]['fwmark']
                call(f'ip rule add prio {rule} from all fwmark {fwmk} lookup {table}')
            # Source and fwmark in the rule
            # set policy local-route rule 100 source '203.0.113.1'
            # set policy local-route rule 100 fwmark '23'
            if 'source' in pbr['rule'][rule] and 'fwmark' in pbr['rule'][rule]:
                fwmk = pbr['rule'][rule]['fwmark']
                for src in pbr['rule'][rule]['source']:
                    call(f'ip rule add prio {rule} from {src} fwmark {fwmk} lookup {table}')

    return None

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
