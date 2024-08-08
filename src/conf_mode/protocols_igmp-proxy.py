#!/usr/bin/env python3
#
# Copyright (C) 2018-2024 VyOS maintainers and contributors
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
from vyos.configverify import verify_interface_exists
from vyos.template import render
from vyos.utils.process import call
from vyos.utils.dict import dict_search
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
    igmp_proxy = conf.get_config_dict(base, key_mangling=('-', '_'),
                                      get_first_key=True,
                                      with_defaults=True)

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
        verify_interface_exists(igmp_proxy, interface)
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
        Warning('IGMP Proxy will be deactivated because it is disabled')
        return None

    render(config_file, 'igmp-proxy/igmpproxy.conf.j2', igmp_proxy)

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
