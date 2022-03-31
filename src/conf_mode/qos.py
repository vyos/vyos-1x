#!/usr/bin/env python3
#
# Copyright (C) 2022 VyOS maintainers and contributors
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
# along with this program. If not, see <http://www.gnu.org/licenses/>.

from sys import exit

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['traffic-policy']
    if not conf.exists(base):
        return None

    qos = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)

    for traffic_policy in ['drop-tail', 'fair-queue', 'fq-codel', 'limiter',
                           'network-emulator', 'priority-queue', 'random-detect',
                           'rate-control', 'round-robin', 'shaper', 'shaper-hfsc']:
        traffic_policy_us = traffic_policy.replace('-','_')
        # Individual policy type not present on CLI - no need to blend in
        # any default values
        if traffic_policy_us not in qos:
            continue

        default_values = defaults(base + [traffic_policy_us])

        # class is another tag node which requires individual handling
        class_default_values = defaults(base + [traffic_policy_us, 'class'])
        if 'class' in default_values:
            del default_values['class']

        for policy, policy_config in qos[traffic_policy_us].items():
            qos[traffic_policy_us][policy] = dict_merge(
                default_values, qos[traffic_policy_us][policy])

            if 'class' in policy_config:
                for policy_class in policy_config['class']:
                    qos[traffic_policy_us][policy]['class'][policy_class] = dict_merge(
                        class_default_values, qos[traffic_policy_us][policy]['class'][policy_class])

    import pprint
    pprint.pprint(qos)
    return qos

def verify(qos):
    if not qos:
        return None

    # network policy emulator
    # reorder rerquires delay to be set

    raise ConfigError('123')
    return None

def generate(qos):
    return None

def apply(qos):
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
