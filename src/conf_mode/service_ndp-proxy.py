#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
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
from vyos.configverify import verify_interface_exists
from vyos.utils.process import call
from vyos.template import render
from vyos import ConfigError
from vyos import airbag
airbag.enable()

systemd_service = 'ndppd.service'
ndppd_config = '/run/ndppd/ndppd.conf'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'ndp-proxy']
    if not conf.exists(base):
        return None

    ndpp = conf.get_config_dict(base, key_mangling=('-', '_'),
                                get_first_key=True,
                                with_recursive_defaults=True)

    return ndpp

def verify(ndpp):
    if not ndpp:
        return None

    if 'interface' in ndpp:
        for interface, interface_config in ndpp['interface'].items():
            verify_interface_exists(interface)

            if 'rule' in interface_config:
                for rule, rule_config in interface_config['rule'].items():
                    if rule_config['mode'] == 'interface' and 'interface' not in rule_config:
                        raise ConfigError(f'Rule "{rule}" uses interface mode but no interface defined!')

                    if rule_config['mode'] != 'interface' and 'interface' in rule_config:
                        if interface_config['mode'] != 'interface' and 'interface' in interface_config:
                            raise ConfigError(f'Rule "{rule}" does not use interface mode, thus interface can not be defined!')

    return None

def generate(ndpp):
    if not ndpp:
        return None

    render(ndppd_config, 'ndppd/ndppd.conf.j2', ndpp)
    return None

def apply(ndpp):
    if not ndpp:
        call(f'systemctl stop {systemd_service}')
        if os.path.isfile(ndppd_config):
            os.unlink(ndppd_config)
        return None

    call(f'systemctl reload-or-restart {systemd_service}')
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
