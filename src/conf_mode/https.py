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
from vyos.configverify import verify_vrf
from vyos import ConfigError
from vyos.util import call
from vyos.template import render

from vyos import airbag
airbag.enable()

config_file = '/etc/nginx/sites-available/default'
systemd_override = r'/etc/systemd/system/nginx.service.d/override.conf'
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

<<<<<<< HEAD
    if not conf.exists('service https'):
=======
    base = ['service', 'https']
    if not conf.exists(base):
        return None

    https = conf.get_config_dict(base, get_first_key=True)

    if https:
        https['pki'] = conf.get_config_dict(['pki'], key_mangling=('-', '_'),
                                get_first_key=True, no_tag_node_value_mangle=True)

    return https

def verify(https):
    from vyos.utils.dict import dict_search

    if https is None:
        return None

    if 'certificates' in https:
        certificates = https['certificates']

        if 'certificate' in certificates:
            if not https['pki']:
                raise ConfigError("PKI is not configured")

            cert_name = certificates['certificate']

            if cert_name not in https['pki']['certificate']:
                raise ConfigError("Invalid certificate on https configuration")

            pki_cert = https['pki']['certificate'][cert_name]

            if 'certificate' not in pki_cert:
                raise ConfigError("Missing certificate on https configuration")

            if 'private' not in pki_cert or 'key' not in pki_cert['private']:
                raise ConfigError("Missing certificate private key on https configuration")

        if 'certbot' in https['certificates']:
            vhost_names = []
            for vh, vh_conf in https.get('virtual-host', {}).items():
                vhost_names += vh_conf.get('server-name', [])
            domains = https['certificates']['certbot'].get('domain-name', [])
            domains_found = [domain for domain in domains if domain in vhost_names]
            if not domains_found:
                raise ConfigError("At least one 'virtual-host <id> server-name' "
                              "matching the 'certbot domain-name' is required.")

    server_block_list = []

    # organize by vhosts
    vhost_dict = https.get('virtual-host', {})

    if not vhost_dict:
        # no specified virtual hosts (server blocks); use default
        server_block_list.append(default_server_block)
    else:
        for vhost in list(vhost_dict):
            server_block = deepcopy(default_server_block)
            data = vhost_dict.get(vhost, {})
            server_block['address'] = data.get('listen-address', '*')
            server_block['port'] = data.get('listen-port', '443')
            server_block_list.append(server_block)

    for entry in server_block_list:
        _address = entry.get('address')
        _address = '0.0.0.0' if _address == '*' else _address
        _port = entry.get('port')
        proto = 'tcp'
        if check_port_availability(_address, int(_port), proto) is not True and \
                not is_listen_port_bind_service(int(_port), 'nginx'):
            raise ConfigError(f'"{proto}" port "{_port}" is used by another service')

    verify_vrf(https)

    # Verify API server settings, if present
    if 'api' in https:
        keys = dict_search('api.keys.id', https)
        gql_auth_type = dict_search('api.graphql.authentication.type', https)

        # If "api graphql" is not defined and `gql_auth_type` is None,
        # there's certainly no JWT auth option, and keys are required
        jwt_auth = (gql_auth_type == "token")

        # Check for incomplete key configurations in every case
        valid_keys_exist = False
        if keys:
            for k in keys:
                if 'key' not in keys[k]:
                    raise ConfigError(f'Missing HTTPS API key string for key id "{k}"')
                else:
                    valid_keys_exist = True

        # If only key-based methods are enabled,
        # fail the commit if no valid key configurations are found
        if (not valid_keys_exist) and (not jwt_auth):
            raise ConfigError('At least one HTTPS API key is required unless GraphQL token authentication is enabled')

    return None

def generate(https):
    if https is None:
>>>>>>> 8c450ea7f (https api: T5772: check if keys are configured)
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
        if vhosts:
            api_data['vhost'] = vhosts[:]
        if 'socket' in list(api_settings):
            api_data['socket'] = True

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

    vrf_path = ['service', 'https', 'vrf']
    if conf.exists(vrf_path):
        https['vrf'] = conf.return_value(vrf_path)

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

    verify_vrf(https)
    return None

def generate(https):
    if https is None:
        return None

    if 'server_block_list' not in https or not https['server_block_list']:
        https['server_block_list'] = [default_server_block]

    render(config_file, 'https/nginx.default.tmpl', https)
    render(systemd_override, 'https/override.conf.tmpl', https)

    return None

def apply(https):
    # Reload systemd manager configuration
    call('systemctl daemon-reload')
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
