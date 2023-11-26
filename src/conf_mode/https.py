#!/usr/bin/env python3
#
# Copyright (C) 2019-2022 VyOS maintainers and contributors
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
import sys
import json

from copy import deepcopy
from time import sleep

import vyos.defaults
import vyos.certbot_util

from vyos.config import Config
from vyos.configdiff import get_config_diff
from vyos.configverify import verify_vrf
from vyos import ConfigError
from vyos.pki import wrap_certificate
from vyos.pki import wrap_private_key
from vyos.template import render
from vyos.utils.process import call
from vyos.utils.process import is_systemd_service_running
from vyos.utils.process import is_systemd_service_active
from vyos.utils.network import check_port_availability
from vyos.utils.network import is_listen_port_bind_service
from vyos.utils.file import write_file

from vyos import airbag
airbag.enable()

config_file = '/etc/nginx/sites-available/default'
systemd_override = r'/run/systemd/system/nginx.service.d/override.conf'
cert_dir = '/etc/ssl/certs'
key_dir = '/etc/ssl/private'
certbot_dir = vyos.defaults.directories['certbot']

api_config_state = '/run/http-api-state'
systemd_service = '/run/systemd/system/vyos-http-api.service'

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
    'api'       : False,
    'vyos_cert' : {},
    'certbot'   : False
}

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['service', 'https']
    if not conf.exists(base):
        return None

    diff = get_config_diff(conf)

    https = conf.get_config_dict(base, get_first_key=True)

    if https:
        https['pki'] = conf.get_config_dict(['pki'], key_mangling=('-', '_'),
                                            no_tag_node_value_mangle=True,
                                            get_first_key=True)

    https['children_changed'] = diff.node_changed_children(base)
    https['api_add_or_delete'] = diff.node_changed_presence(base + ['api'])

    if 'api' not in https:
        return https

    http_api = conf.get_config_dict(base + ['api'], key_mangling=('-', '_'),
                                    no_tag_node_value_mangle=True,
                                    get_first_key=True,
                                    with_recursive_defaults=True)

    if http_api.from_defaults(['graphql']):
        del http_api['graphql']

    # Do we run inside a VRF context?
    vrf_path = ['service', 'https', 'vrf']
    if conf.exists(vrf_path):
        http_api['vrf'] = conf.return_value(vrf_path)

    https['api'] = http_api

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
            for _, vh_conf in https.get('virtual-host', {}).items():
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
            server_block['port'] = data.get('port', '443')
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
        return None

    if 'api' not in https:
        if os.path.exists(systemd_service):
            os.unlink(systemd_service)
    else:
        render(systemd_service, 'https/vyos-http-api.service.j2', https['api'])
        with open(api_config_state, 'w') as f:
            json.dump(https['api'], f, indent=2)

    server_block_list = []

    # organize by vhosts

    vhost_dict = https.get('virtual-host', {})

    if not vhost_dict:
        # no specified virtual hosts (server blocks); use default
        server_block_list.append(default_server_block)
    else:
        for vhost in list(vhost_dict):
            server_block = deepcopy(default_server_block)
            server_block['id'] = vhost
            data = vhost_dict.get(vhost, {})
            server_block['address'] = data.get('listen-address', '*')
            server_block['port'] = data.get('port', '443')
            name = data.get('server-name', ['_'])
            server_block['name'] = name
            allow_client = data.get('allow-client', {})
            server_block['allow_client'] = allow_client.get('address', [])
            server_block_list.append(server_block)

    # get certificate data

    cert_dict = https.get('certificates', {})

    if 'certificate' in cert_dict:
        cert_name = cert_dict['certificate']
        pki_cert = https['pki']['certificate'][cert_name]

        cert_path = os.path.join(cert_dir, f'{cert_name}.pem')
        key_path = os.path.join(key_dir, f'{cert_name}.pem')

        server_cert = str(wrap_certificate(pki_cert['certificate']))
        if 'ca-certificate' in cert_dict:
            ca_cert = cert_dict['ca-certificate']
            server_cert += '\n' + str(wrap_certificate(https['pki']['ca'][ca_cert]['certificate']))

        write_file(cert_path, server_cert)
        write_file(key_path, wrap_private_key(pki_cert['private']['key']))

        vyos_cert_data = {
            'crt': cert_path,
            'key': key_path
        }

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

    if 'api' in list(https):
        vhost_list = https.get('api-restrict', {}).get('virtual-host', [])
        if not vhost_list:
            for block in server_block_list:
                block['api'] = True
        else:
            for block in server_block_list:
                if block['id'] in vhost_list:
                    block['api'] = True

    data = {
        'server_block_list': server_block_list,
        'certbot': certbot
    }

    render(config_file, 'https/nginx.default.j2', data)
    render(systemd_override, 'https/override.conf.j2', https)
    return None

def apply(https):
    # Reload systemd manager configuration
    call('systemctl daemon-reload')
    http_api_service_name = 'vyos-http-api.service'
    https_service_name = 'nginx.service'

    if https is None:
        if is_systemd_service_active(f'{http_api_service_name}'):
            call(f'systemctl stop {http_api_service_name}')
        call(f'systemctl stop {https_service_name}')
        return

    if 'api' in https['children_changed']:
        if 'api' in https:
            if is_systemd_service_running(f'{http_api_service_name}'):
                call(f'systemctl reload {http_api_service_name}')
            else:
                call(f'systemctl restart {http_api_service_name}')
            # Let uvicorn settle before (possibly) restarting nginx
            sleep(1)
        else:
            if is_systemd_service_active(f'{http_api_service_name}'):
                call(f'systemctl stop {http_api_service_name}')

    if (not is_systemd_service_running(f'{https_service_name}') or
        https['api_add_or_delete'] or
        set(https['children_changed']) - set(['api'])):
        call(f'systemctl restart {https_service_name}')

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
