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
from netifaces import interfaces

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.template import render
from vyos.util import call
from vyos.util import dict_search
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_file = r'/etc/igmpproxy.conf'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['protocols', 'igmp-proxy']
    igmp_proxy = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)

    if 'interface' in igmp_proxy:
        # T2665: we must add the tagNode defaults individually until this is
        # moved to the base class
        default_values = defaults(base + ['interface'])
        for interface in igmp_proxy['interface']:
            igmp_proxy['interface'][interface] = dict_merge(default_values,
                igmp_proxy['interface'][interface])


    if conf.exists(['protocols', 'igmp']):
        igmp_proxy.update({'igmp_configured': ''})

    if conf.exists(['protocols', 'pim']):
        igmp_proxy.update({'pim_configured': ''})

    return igmp_proxy

def verify(igmp_proxy):
    # bail out early - looks like removal from running config
    if not igmp_proxy or 'disable' in igmp_proxy:
        return None

    if 'igmp_configured' in igmp_proxy or 'pim_configured' in igmp_proxy:
        raise ConfigError('Can not configure both IGMP proxy and PIM '\
                          'at the same time')

    # at least two interfaces are required, one upstream and one downstream
    if 'interface' not in igmp_proxy or len(igmp_proxy['interface']) < 2:
        raise ConfigError('Must define exactly one upstream and at least one ' \
                          'downstream interface!')

    upstream = 0
    for interface, config in igmp_proxy['interface'].items():
        if interface not in interfaces():
            raise ConfigError(f'Interface "{interface}" does not exist')
        if dict_search('role', config) == 'upstream':
            upstream += 1

    if upstream == 0:
        raise ConfigError('At least 1 upstream interface is required!')
    elif upstream > 1:
        raise ConfigError('Only 1 upstream interface allowed!')

    return None

def generate(igmp_proxy):
    # bail out early - looks like removal from running config
    if not igmp_proxy:
        return None

    # bail out early - service is disabled, but inform user
    if 'disable' in igmp_proxy:
        print('WARNING: IGMP Proxy will be deactivated because it is disabled')
        return None

    render(config_file, 'igmp-proxy/igmpproxy.conf.tmpl', igmp_proxy)

    return None

def apply(igmp_proxy):
    if not igmp_proxy or 'disable' in igmp_proxy:
         # IGMP Proxy support is removed in the commit
         call('systemctl stop igmpproxy.service')
         if os.path.exists(config_file):
             os.unlink(config_file)
    else:
        call('systemctl restart igmpproxy.service')

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
