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

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.template import render
from vyos.util import cmd
from vyos.util import dict_search
from vyos.template import bracketize_ipv6
from vyos.template import is_ipv6
from vyos.template import is_ipv4
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

lvs_config = '/tmp/ipvsadm.rules'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    
    base = ['load-balancing', 'inbound', 'ipvsadm']
    conf = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
    
    if 'rule' in conf:
        default_values = defaults(base + ['rule'])
        for rule in conf['rule']:
            conf['rule'][rule] = dict_merge(default_values, conf['rule'][rule])
    
    return conf

def verify(config):
    if 'rule' not in config:
        return None
    
    ip_type = None
    virtual_server_list = []
    vip_list = []
    for rule, rule_config in config['rule'].items():
        if 'disable' in rule_config:
            continue
            
        err_msg = f'Configuration error in rule {rule}: '
        if 'virtual_address' not in rule_config or 'port' not in rule_config:
            raise ConfigError(f'{err_msg} The virtual server IP and port must exist!')
            
        virtual_ip = rule_config['virtual_address']
        virtual_port = rule_config['port']
        virtual_server = f'{bracketize_ipv6(virtual_ip)}:{virtual_port}'
        
        if virtual_server not in virtual_server_list:
            virtual_server_list.append(virtual_server)
        else:
            raise ConfigError(f'{err_msg} Do not allow duplicate virtual servers!')
        
        if virtual_ip not in vip_list:
            vip_list.append(virtual_ip)
        if 'backend' in rule_config:
            for backend, backend_config in rule_config['backend'].items():
                if 'disable' in backend_config:
                    return None
                
                if backend in vip_list:
                    raise ConfigError(f'{err_msg} Back end server cannot use VIP (virtual server IP) with address {backend}!')
                
                if is_ipv4(virtual_ip) and not is_ipv4(backend) or is_ipv6(virtual_ip) and not is_ipv6(backend):
                    raise ConfigError(f'{err_msg} The back-end server with IP {virtual_ip} and \
                        the virtual server with IP {backend} have different address families!')
            
        if not {'algorithm', 'mode'} <= set(rule_config):
            raise ConfigError(f'{err_msg} mode and algorithm must be configured!')

def generate(config):
    if not config:
        return None
    
    render(lvs_config, 'load-balancing/ipvsadm.rules.tmpl', config, permission=0o644)

def apply(config):
    
    if not config:
        cmd(f'ipvsadm -C')
        if os.path.isfile(lvs_config):
            os.unlink(lvs_config)
        return None
    
    if os.path.isfile(lvs_config):
        cmd(f'ipvsadm -R < {lvs_config}')

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
