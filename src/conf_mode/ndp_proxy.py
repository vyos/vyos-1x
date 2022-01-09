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
from copy import deepcopy

from netifaces import interfaces
from vyos.config import Config
from vyos import ConfigError
from vyos.util import call
from vyos.xml import defaults
from vyos.configdict import dict_merge
from vyos.template import render

from vyos import airbag

config_file = r'/run/ndppd/ndppd.conf'

airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['service', 'ndp-proxy']

    if not conf.exists(base):
        return None
    else:
        conf.set_level(base)

    ndp_proxy = conf.get_config_dict([], key_mangling=('-', '_'), get_first_key=True)

    if 'interface' not in ndp_proxy:
        ndp_proxy['interface'] = []

    for interface in ndp_proxy['interface']:
        if 'router' not in ndp_proxy['interface'][interface]:
            ndp_proxy['interface'][interface]['router'] = 'yes'
        if 'timeout' not in ndp_proxy['interface'][interface]:
            ndp_proxy['interface'][interface]['timeout'] = 500
        if 'ttl' not in ndp_proxy['interface'][interface]:
            ndp_proxy['interface'][interface]['ttl'] = 30000
        if 'prefix' not in ndp_proxy['interface'][interface]:
            ndp_proxy['interface'][interface]['prefix'] = []
        for prefix in ndp_proxy['interface'][interface]['prefix']:
            if 'mode' not in ndp_proxy['interface'][interface]['prefix'][prefix]:
                ndp_proxy['interface'][interface]['prefix'][prefix]['mode'] = 'static'

    return ndp_proxy

def verify(ndp_proxy):
    # bail out early - looks like removal from running config
    if ndp_proxy is None:
        return None
    # bail out early - service is disabled
    if 'disable' in ndp_proxy:
        return None
    for interface in ndp_proxy['interface']:
        if 'disable' in ndp_proxy['interface'][interface]:
            continue
        if interface not in interfaces():
            raise ConfigError(f'Interface "{interface}" does not exist')
        if len(ndp_proxy['interface'][interface]['prefix']) < 1:
            raise ConfigError(f'No rules have been set for interface "{interface}"')
        for prefix in ndp_proxy['interface'][interface]['prefix']:
            mode = ndp_proxy['interface'][interface]['prefix'][prefix]['mode']
            if mode not in ['iface', 'auto', 'static']:
                raise ConfigError(f'Mode "{mode}" for interface "{interface}" and prefix "{prefix}" not supported')
            if mode == 'iface' and 'iface' not in ndp_proxy['interface'][interface]['prefix'][prefix]:
                raise ConfigError(f'In iface mode, "iface" must be set for interface "{interface}" and prefix "{prefix}"')
    return None

def generate(ndp_proxy):
    # bail out early - looks like removal from running config
    if ndp_proxy is None:
        return None
    elif 'disable' in ndp_proxy:
        # bail out early - service is disabled, but inform user
        print('Warning: NDP Proxy will be deactivated because it is disabled')
        return None
    else:
        render(config_file, 'ndppd/ndppd.conf.tmpl', ndp_proxy)
        return None

def apply(ndp_proxy):
    if ndp_proxy is None or 'disable' in ndp_proxy:
        call('systemctl stop ndppd.service')
        if os.path.isfile(config_file):
            os.unlink(config_file)
        return
    call('systemctl restart ndppd.service')


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)