#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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
    tmp = node_changed(conf, ['policy', 'local-route', 'rule'])
    if tmp:
        for rule in (tmp or []):
            src = leaf_node_changed(conf, ['policy', 'local-route', 'rule', rule, 'source'])
            if src:
                dict = dict_merge({'rule_remove' : {rule : {'source' : src}}}, dict)
                pbr.update(dict)

    # delete policy local-route rule x source x.x.x.x
    if 'rule' in pbr:
        for rule in pbr['rule']:
            src = leaf_node_changed(conf, ['policy', 'local-route', 'rule', rule, 'source'])
            if src:
                dict = dict_merge({'rule_remove' : {rule : {'source' : src}}}, dict)
                pbr.update(dict)

    return pbr

def verify(pbr):
    # bail out early - looks like removal from running config
    if not pbr:
        return None

    if 'rule' in pbr:
        for rule in pbr['rule']:
            if 'source' not in pbr['rule'][rule]:
                raise ConfigError('Source address required!')
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
            for src in pbr['rule_remove'][rule]['source']:
                call(f'ip rule del prio {rule} from {src}')

    # Generate new config
    if 'rule' in pbr:
        for rule in pbr['rule']:
            table = pbr['rule'][rule]['set']['table']
            if pbr['rule'][rule]['source']:
                for src in pbr['rule'][rule]['source']:
                    call(f'ip rule add prio {rule} from {src} lookup {table}')

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
