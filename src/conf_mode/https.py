#!/usr/bin/env python3
#
# Copyright (C) 2019-2020 VyOS maintainers and contributors
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

import vyos.defaults
import vyos.certbot_util

from vyos.config import Config
from vyos.defaults import directories as vyos_data_dir
from vyos import ConfigError
from vyos.util import call


config_file = '/etc/nginx/sites-available/default'

default_server_block = {
    'id'        : '',
    'address'   : '*',
    'port'      : '443',
    'name'      : ['_'],
    'api'       : {},
    'vyos_cert' : {},
    'certbot'   : False
}

def get_config():
    server_block_list = []
    conf = Config()
    if not conf.exists('service https'):
        return None
    else:
        conf.set_level('service https')

    if not conf.exists('virtual-host'):
        server_block_list.append(default_server_block)
    else:
        for vhost in conf.list_nodes('virtual-host'):
            server_block = deepcopy(default_server_block)
            server_block['id'] = vhost
            if conf.exists(f'virtual-host {vhost} listen-address'):
                addr = conf.return_value(f'virtual-host {vhost} listen-address')
                server_block['address'] = addr
            if conf.exists(f'virtual-host {vhost} listen-port'):
                port = conf.return_value(f'virtual-host {vhost} listen-port')
                server_block['port'] = port
            if conf.exists(f'virtual-host {vhost} server-name'):
                names = conf.return_values(f'virtual-host {vhost} server-name')
                server_block['name'] = names[:]
            server_block_list.append(server_block)

    vyos_cert_data = {}
    if conf.exists('certificates system-generated-certificate'):
        vyos_cert_data = vyos.defaults.vyos_cert_data
    if vyos_cert_data:
        for block in server_block_list:
            block['vyos_cert'] = vyos_cert_data

    certbot = False
    certbot_domains = []
    if conf.exists('certificates certbot domain-name'):
        certbot_domains = conf.return_values('certificates certbot domain-name')
    if certbot_domains:
        certbot = True
        for domain in certbot_domains:
            sub_list = vyos.certbot_util.choose_server_block(server_block_list,
                                                             domain)
            if sub_list:
                for sb in sub_list:
                    sb['certbot'] = True
                    # certbot organizes certificates by first domain
                    sb['certbot_dir'] = certbot_domains[0]

    api_somewhere = False
    api_data = {}
    if conf.exists('api'):
        api_somewhere = True
        api_data = vyos.defaults.api_data
        if conf.exists('api port'):
            port = conf.return_value('api port')
            api_data['port'] = port
        if conf.exists('api-restrict virtual-host'):
            vhosts = conf.return_values('api-restrict virtual-host')
            api_data['vhost'] = vhosts[:]

    if api_data:
        # we do not want to include 'vhost' key as part of
        # vyos.defaults.api_data, so check for key existence
        vhost_list = api_data.get('vhost')
        if vhost_list is None:
            for block in server_block_list:
                block['api'] = api_data
        else:
            for block in server_block_list:
                if block['id'] in vhost_list:
                    block['api'] = api_data

    https = {'server_block_list' : server_block_list,
             'api_somewhere': api_somewhere,
             'certbot': certbot}
    return https

def verify(https):
    if https is None:
        return None

    if https['certbot']:
        for sb in https['server_block_list']:
            if sb['certbot']:
                return None
        raise ConfigError("At least one 'virtual-host <id> server-name' "
                          "matching the 'certbot domain-name' is required.")
    return None

def generate(https):
    if https is None:
        return None

    # Prepare Jinja2 template loader from files
    tmpl_path = os.path.join(vyos_data_dir['data'], 'templates', 'https')
    fs_loader = FileSystemLoader(tmpl_path)
    env = Environment(loader=fs_loader, trim_blocks=True)

    if 'server_block_list' not in https or not https['server_block_list']:
        https['server_block_list'] = [default_server_block]

    tmpl = env.get_template('nginx.default.tmpl')
    config_text = tmpl.render(https)
    with open(config_file, 'w') as f:
        f.write(config_text)

    return None

def apply(https):
    if https is not None:
        call('sudo systemctl restart nginx.service')
    else:
        call('sudo systemctl stop nginx.service')

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
