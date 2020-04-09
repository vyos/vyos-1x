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
from copy import deepcopy
from jinja2 import FileSystemLoader, Environment

from netifaces import interfaces
from vyos.config import Config
from vyos.defaults import directories as vyos_data_dir
from vyos import ConfigError
from vyos.util import call


config_file = r'/etc/igmpproxy.conf'

default_config_data = {
    'disable': False,
    'disable_quickleave': False,
    'interfaces': [],
}

def get_config():
    igmp_proxy = deepcopy(default_config_data)
    conf = Config()
    base = ['protocols', 'igmp-proxy']
    if not conf.exists(base):
        return None
    else:
        conf.set_level(base)

    # Network interfaces to listen on
    if conf.exists(['disable']):
        igmp_proxy['disable'] = True

    # Option to disable "quickleave"
    if conf.exists(['disable-quickleave']):
        igmp_proxy['disable_quickleave'] = True

    for intf in conf.list_nodes(['interface']):
        conf.set_level(base + ['interface', intf])
        interface = {
            'name': intf,
            'alt_subnet': [],
            'role': 'downstream',
            'threshold': '1',
            'whitelist': []
        }

        if conf.exists(['alt-subnet']):
            interface['alt_subnet'] = conf.return_values(['alt-subnet'])

        if conf.exists(['role']):
            interface['role'] = conf.return_value(['role'])

        if conf.exists(['threshold']):
            interface['threshold'] = conf.return_value(['threshold'])

        if conf.exists(['whitelist']):
            interface['whitelist'] = conf.return_values(['whitelist'])

        # Append interface configuration to global configuration list
        igmp_proxy['interfaces'].append(interface)

    return igmp_proxy

def verify(igmp_proxy):
    # bail out early - looks like removal from running config
    if igmp_proxy is None:
        return None

    # bail out early - service is disabled
    if igmp_proxy['disable']:
        return None

    # at least two interfaces are required, one upstream and one downstream
    if len(igmp_proxy['interfaces']) < 2:
        raise ConfigError('Must define an upstream and at least 1 downstream interface!')

    upstream = 0
    for interface in igmp_proxy['interfaces']:
        if interface['name'] not in interfaces():
            raise ConfigError('Interface "{}" does not exist'.format(interface['name']))
        if "upstream" == interface['role']:
            upstream += 1

    if upstream == 0:
        raise ConfigError('At least 1 upstream interface is required!')
    elif upstream > 1:
        raise ConfigError('Only 1 upstream interface allowed!')

    return None

def generate(igmp_proxy):
    # bail out early - looks like removal from running config
    if igmp_proxy is None:
        return None

    # bail out early - service is disabled, but inform user
    if igmp_proxy['disable']:
        print('Warning: IGMP Proxy will be deactivated because it is disabled')
        return None

    # Prepare Jinja2 template loader from files
    tmpl_path = os.path.join(vyos_data_dir['data'], 'templates', 'igmp-proxy')
    fs_loader = FileSystemLoader(tmpl_path)
    env = Environment(loader=fs_loader)

    tmpl = env.get_template('igmpproxy.conf.tmpl')
    config_text = tmpl.render(igmp_proxy)
    with open(config_file, 'w') as f:
        f.write(config_text)

    return None

def apply(igmp_proxy):
    if igmp_proxy is None or igmp_proxy['disable']:
         # IGMP Proxy support is removed in the commit
         call('sudo systemctl stop igmpproxy.service')
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
