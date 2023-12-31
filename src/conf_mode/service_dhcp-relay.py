#!/usr/bin/env python3
#
# Copyright (C) 2018-2020 VyOS maintainers and contributors
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

from vyos.base import Warning
from vyos.config import Config
from vyos.template import render
from vyos.base import Warning
from vyos.utils.process import call
from vyos.utils.dict import dict_search
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_file = r'/run/dhcp-relay/dhcrelay.conf'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'dhcp-relay']
    if not conf.exists(base):
        return None

    relay = conf.get_config_dict(base, key_mangling=('-', '_'),
                                 get_first_key=True,
                                 with_recursive_defaults=True)

    return relay

def verify(relay):
    # bail out early - looks like removal from running config
    if not relay or 'disable' in relay:
        return None

    if 'lo' in (dict_search('interface', relay) or []):
        raise ConfigError('DHCP relay does not support the loopback interface.')

    if 'server' not in relay :
        raise ConfigError('No DHCP relay server(s) configured.\n' \
                          'At least one DHCP relay server required.')

    if 'interface' in relay:
        Warning('DHCP relay interface is DEPRECATED - please use upstream-interface and listen-interface instead!')
        if 'upstream_interface' in relay or 'listen_interface' in relay:
            raise ConfigError('<interface> configuration is not compatible with upstream/listen interface')
        else:
            Warning('<interface> is going to be deprecated.\n'  \
                    'Please use <listen-interface> and <upstream-interface>')

    if 'upstream_interface' in relay and 'listen_interface' not in relay:
        raise ConfigError('No listen-interface configured')
    if 'listen_interface' in relay and 'upstream_interface' not in relay:
        raise ConfigError('No upstream-interface configured')

    return None

def generate(relay):
    # bail out early - looks like removal from running config
    if not relay or 'disable' in relay:
        return None

    render(config_file, 'dhcp-relay/dhcrelay.conf.j2', relay)
    return None

def apply(relay):
    # bail out early - looks like removal from running config
    service_name = 'isc-dhcp-relay.service'
    if not relay or 'disable' in relay:
        call(f'systemctl stop {service_name}')
        if os.path.exists(config_file):
            os.unlink(config_file)
        return None

    call(f'systemctl restart {service_name}')

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
