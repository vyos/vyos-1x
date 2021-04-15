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

from sys import exit

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.template import render
from vyos.template import render_to_string
from vyos.util import call
from vyos.util import dict_search
from vyos import ConfigError
from vyos import frr
from vyos import airbag
from pprint import pprint
airbag.enable()

config_file = r'/tmp/policy.frr'
frr_daemon = 'zebra'

DEBUG = os.path.exists('/tmp/policy.debug')
if DEBUG:
    import logging
    lg = logging.getLogger("vyos.frr")
    lg.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    lg.addHandler(ch)

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['npolicy']
    policy = conf.get_config_dict(base, key_mangling=('-', '_'))

    # Bail out early if configuration tree does not exist
    if not conf.exists(base):
        return policy

    pprint(policy)
    exit(1)
    return policy

def verify(policy):
    if not policy:
        return None

    return None

def generate(policy):
    if not policy:
        policy['new_frr_config'] = ''
        return None

    # render(config) not needed, its only for debug
  #  render(config_file, 'frr/policy.frr.tmpl', policy)
  #  policy['new_frr_config'] = render_to_string('frr/policy.frr.tmpl')

    return None

def apply(policy):
    # Save original configuration prior to starting any commit actions
   # frr_cfg = frr.FRRConfig()
   # frr_cfg.load_configuration(frr_daemon)
   # frr_cfg.modify_section(f'ip', '')
   # frr_cfg.add_before(r'(line vty)', policy['new_frr_config'])

    # Debugging
    if DEBUG:
        from pprint import pprint
        print('')
        print('--------- DEBUGGING ----------')
        pprint(dir(frr_cfg))
        print('Existing config:\n')
        for line in frr_cfg.original_config:
            print(line)
        print(f'Replacement config:\n')
        print(f'{policy["new_frr_config"]}')
        print(f'Modified config:\n')
        print(f'{frr_cfg}')

   # frr_cfg.commit_configuration(frr_daemon)

    # If FRR config is blank, rerun the blank commit x times due to frr-reload
    # behavior/bug not properly clearing out on one commit.
   # if policy['new_frr_config'] == '':
   #     for a in range(5):
   #         frr_cfg.commit_configuration(frr_daemon)


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
