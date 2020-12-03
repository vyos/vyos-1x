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
from vyos.configdict import node_changed
from vyos import ConfigError
from vyos.util import call
from vyos.template import render
from vyos.template import render_to_string
from vyos import frr
from vyos import airbag
airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['protocols', 'isis']

    isis = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)

    return isis

def verify(isis):
    # bail out early - looks like removal from running config
    if not isis:
        return None

    for process, isis_config in isis.items():
        # If more then one isis process is defined (Frr only supports one)
        # http://docs.frrouting.org/en/latest/isisd.html#isis-router
        if len(isis) > 1:
            raise ConfigError('Only one isis process can be definded')

        # If network entity title (net) not defined
        if 'net' not in isis_config:
            raise ConfigError('ISIS net format iso is mandatory!')

        # If interface not set
        if 'interface' not in isis_config:
            raise ConfigError('ISIS interface is mandatory!')

        # If md5 and plaintext-password set at the same time
        if 'area_password' in isis_config:
            if {'md5', 'plaintext_password'} <= set(isis_config['encryption']):
                raise ConfigError('Can not use both md5 and plaintext-password for ISIS area-password!')

        # If one param from deley set, but not set others
        if 'spf_delay_ietf' in isis_config:
            required_timers = ['holddown', 'init_delay', 'long_delay', 'short_delay', 'time_to_learn']
            exist_timers = []
            for elm_timer in required_timers:
                if elm_timer in isis_config['spf_delay_ietf']:
                    exist_timers.append(elm_timer)

            exist_timers = set(required_timers).difference(set(exist_timers))
            if len(exist_timers) > 0:
                raise ConfigError('All types of delay must be specified: ' + ', '.join(exist_timers).replace('_', '-'))

        # If Redistribute set, but level don't set
        if 'redistribute' in isis_config:
            proc_level = isis_config.get('level','').replace('-','_')
            for proto, proto_config in isis_config.get('redistribute', {}).get('ipv4', {}).items():
                if 'level_1' not in proto_config and 'level_2' not in proto_config:
                    raise ConfigError('Redistribute level-1 or level-2 should be specified in \"protocols isis {} redistribute ipv4 {}\"'.format(process, proto))
            for redistribute_level in proto_config.keys():
                if proc_level and proc_level != 'level_1_2' and proc_level != redistribute_level:
                    raise ConfigError('\"protocols isis {0} redistribute ipv4 {2} {3}\" cannot be used with \"protocols isis {0} level {1}\"'.format(process, proc_level, proto, redistribute_level))

    return None

def generate(isis):
    if not isis:
        isis['new_frr_config'] = ''
        return None

    # only one ISIS process is supported, so we can directly send the first key
    # of the config dict
    process = list(isis.keys())[0]
    isis[process]['process'] = process

    isis['new_frr_config'] = render_to_string('frr/isis.frr.tmpl',
                                              isis[process])

    return None

def apply(isis):
    # Save original configuration prior to starting any commit actions
    frr_cfg = frr.FRRConfig()
    frr_cfg.load_configuration(daemon='isisd')
    frr_cfg.modify_section(r'interface \S+', '')
    frr_cfg.modify_section(f'router isis \S+', '')
    frr_cfg.add_before(r'(ip prefix-list .*|route-map .*|line vty)', isis['new_frr_config'])
    frr_cfg.commit_configuration(daemon='isisd')

    # If FRR config is blank, rerun the blank commit x times due to frr-reload
    # behavior/bug not properly clearing out on one commit.
    if isis['new_frr_config'] == '':
        for a in range(5):
            frr_cfg.commit_configuration(daemon='isisd')

    # Debugging
    '''
    print('')
    print('--------- DEBUGGING ----------')
    print(f'Existing config:\n{frr_cfg["original_config"]}\n\n')
    print(f'Replacement config:\n{isis["new_frr_config"]}\n\n')
    print(f'Modified config:\n{frr_cfg["modified_config"]}\n\n')
   '''

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
