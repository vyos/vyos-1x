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

import sys

from copy import deepcopy

import vyos.defaults
import vyos.certbot_util

from vyos.config import Config
from vyos import ConfigError
from vyos.util import call
from vyos.template import render

from vyos import airbag
airbag.enable()

config_file = '/etc/nginx/sites-available/default'
certbot_dir = vyos.defaults.directories['certbot']

# https config needs to coordinate several subsystems: api, certbot,
# self-signed certificate, as well as the virtual hosts defined within the
# https config definition itself. Consequently, one needs a general dict,
# encompassing the https and other configs, and a list of such virtual hosts
# (server blocks in nginx terminology) to pass to the jinja2 template.
default_server_block = {
    'id'        : '',
    'address'   : '*',
    'port'      : '443',
    'name'      : ['_'],
    'api'       : {},
    'vyos_cert' : {},
    'certbot'   : False
}

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    if not conf.exists('service https'):
        return None

    server_block_list = []
    https_dict = conf.get_config_dict('service https', get_first_key=True)

    # organize by vhosts

    vhost_dict = https_dict.get('virtual-host', {})

    if not vhost_dict:
        # no specified virtual hosts (server blocks); use default
        server_block_list.append(default_server_block)
    else:
        for vhost in list(vhost_dict):
            server_block = deepcopy(default_server_block)
            server_block['id'] = vhost
            data = vhost_dict.get(vhost, {})
            server_block['address'] = data.get('listen-address', '*')
            server_block['port'] = data.get('listen-port', '443')
            name = data.get('server-name', ['_'])
            # XXX: T2636 workaround: convert string to a list with one element
            if not isinstance(name, list):
                name = [name]
            server_block['name'] = name
            server_block_list.append(server_block)

    # get certificate data

    cert_dict = https_dict.get('certificates', {})

        # self-signed certificate

    vyos_cert_data = {}
    if 'system-generated-certificate' in list(cert_dict):
        vyos_cert_data = vyos.defaults.vyos_cert_data
    if vyos_cert_data:
        for block in server_block_list:
            block['vyos_cert'] = vyos_cert_data

        # letsencrypt certificate using certbot

    certbot = False
    cert_domains = cert_dict.get('certbot', {}).get('domain-name', [])
    if cert_domains:
        # XXX: T2636 workaround: convert string to a list with one element
        if not isinstance(cert_domains, list):
            cert_domains = [cert_domains]
        certbot = True
        for domain in cert_domains:
            sub_list = vyos.certbot_util.choose_server_block(server_block_list,
                                                             domain)
            if sub_list:
                for sb in sub_list:
                    sb['certbot'] = True
                    sb['certbot_dir'] = certbot_dir
                    # certbot organizes certificates by first domain
                    sb['certbot_domain_dir'] = cert_domains[0]

    # get api data

    api_set = False
    api_data = {}
    if 'api' in list(https_dict):
        api_set = True
        api_data = vyos.defaults.api_data
    api_settings = https_dict.get('api', {})
    if api_settings:
        port = api_settings.get('port', '')
        if port:
            api_data['port'] = port
        vhosts = https_dict.get('api-restrict', {}).get('virtual-host', [])
        # XXX: T2636 workaround: convert string to a list with one element
        if not isinstance(vhosts, list):
            vhosts = [vhosts]
        if vhosts:
            api_data['vhost'] = vhosts[:]

    if api_data:
        vhost_list = api_data.get('vhost', [])
        if not vhost_list:
            for block in server_block_list:
                block['api'] = api_data
        else:
            for block in server_block_list:
                if block['id'] in vhost_list:
                    block['api'] = api_data

    # return dict for use in template

    https = {'server_block_list' : server_block_list,
             'api_set': api_set,
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

    if 'server_block_list' not in https or not https['server_block_list']:
        https['server_block_list'] = [default_server_block]

    render(config_file, 'https/nginx.default.tmpl', https, trim_blocks=True)

    return None

def apply(https):
    if https is not None:
        call('systemctl restart nginx.service')
    else:
        call('systemctl stop nginx.service')

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
