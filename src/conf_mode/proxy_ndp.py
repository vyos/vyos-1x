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
        
    base = ['service', 'proxy-ndp']
    
    if not conf.exists(base):
        return None
    else:
        conf.set_level(base)
        
    ndp_proxy = conf.get_config_dict([], key_mangling=('-', '_'), get_first_key=True)
    
    for interface in ndp_proxy['interface']:
        if 'router' not in ndp_proxy['interface'][interface]:
            ndp_proxy['interface'][interface]['router'] = 'yes'
        if 'ttl' not in ndp_proxy['interface'][interface]:
            ndp_proxy['interface'][interface]['ttl'] = 30000
        if 'timeout' not in ndp_proxy['interface'][interface]:
            ndp_proxy['interface'][interface]['timeout'] = 500
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
            continue;
        if interface not in interfaces():
            raise ConfigError('Interface "{}" does not exist'.format(interface))
        if len(ndp_proxy['interface'][interface]['prefix']) < 1:
            raise ConfigError('No rules have been set for this interface!')
        for prefix in ndp_proxy['interface'][interface]['prefix']:
            if ndp_proxy['interface'][interface]['prefix'][prefix]['mode'] not in ['iface','auto','static']:
                raise ConfigError('Illegal running mode in interface "{interface}" and prefix "{prefix}"'.format(interface=interface['name'],prefix=prefix['prefix']))
            if ndp_proxy['interface'][interface]['prefix'][prefix]['mode'] == 'iface' and 'iface' not in ndp_proxy['interface'][interface]['prefix'][prefix]:
                raise ConfigError('In iface running mode, an interface must be specified in interface "{interface}" and prefix "{prefix}"'.format(interface=interface,prefix=prefix))
    return None
            
def generate(ndp_proxy):
    # bail out early - looks like removal from running config
    if ndp_proxy is None:
        return None
    # bail out early - service is disabled, but inform user
    if 'disable' in ndp_proxy:
        print('Warning: NDP Proxy will be deactivated because it is disabled')
        return None
    else:
        render(config_file, 'proxy-ndp/ndppd.conf.tmpl', ndp_proxy)
        return None
    
def apply(ndp_proxy):
    if ndp_proxy is None or 'disable' in ndp_proxy:
         # NDP Proxy support is removed in the commit
         for interface in interfaces():
             call(f'echo 0 > /proc/sys/net/ipv6/conf/{interface}/proxy_ndp')
         call('systemctl stop ndppd.service')
    else:
        for interface in ndp_proxy['interface']:
            if 'disable' in interface:
                call(f'echo 0 > /proc/sys/net/ipv6/conf/{interface}/proxy_ndp')
            else:
                call(f'echo 1 > /proc/sys/net/ipv6/conf/{interface}/proxy_ndp')
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
