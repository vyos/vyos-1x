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
    base = ['qos']
    if not conf.exists(base):
        return None

    qos = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)

    if 'policy' in qos:
        for policy in qos['policy']:
            # CLI mangles - to _ for better Jinja2 compatibility - do we need
            # Jinja2 here?
            policy = policy.replace('-','_')

            default_values = defaults(base + ['policy', policy])

            # class is another tag node which requires individual handling
            class_default_values = defaults(base + ['policy', policy, 'class'])
            if 'class' in default_values:
                del default_values['class']

            for p_name, p_config in qos['policy'][policy].items():
                qos['policy'][policy][p_name] = dict_merge(
                    default_values, qos['policy'][policy][p_name])

                if 'class' in p_config:
                    for p_class in p_config['class']:
                        qos['policy'][policy][p_name]['class'][p_class] = dict_merge(
                            class_default_values, qos['policy'][policy][p_name]['class'][p_class])

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
