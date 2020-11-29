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

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.template import render
from vyos.util import call
from vyos.util import dict_search
from vyos.xml import defaults
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

    relay = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_values = defaults(base)
    relay = dict_merge(default_values, relay)

    return relay

def verify(relay):
    # bail out early - looks like removal from running config
    if not relay:
        return None

    if 'lo' in (dict_search('interface', relay) or []):
        raise ConfigError('DHCP relay does not support the loopback interface.')

    if 'server' not in relay :
        raise ConfigError('No DHCP relay server(s) configured.\n' \
                          'At least one DHCP relay server required.')

    return None

def generate(relay):
    # bail out early - looks like removal from running config
    if not relay:
        return None

    render(config_file, 'dhcp-relay/dhcrelay.conf.tmpl', relay)
    return None

def apply(relay):
    # bail out early - looks like removal from running config
    if not relay:
        call('systemctl stop isc-dhcp-relay.service')
        if os.path.exists(config_file):
            os.unlink(config_file)
        return None

    call('systemctl restart isc-dhcp-relay.service')

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
