#!/usr/bin/env python3
#
# Copyright (C) 2019-2024 VyOS maintainers and contributors
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
import socket
import sys
import json

from time import sleep

from vyos.base import Warning
from vyos.config import Config
from vyos.config import config_dict_merge
from vyos.configverify import verify_vrf
from vyos.configverify import verify_pki_certificate
from vyos.configverify import verify_pki_ca_certificate
from vyos.configverify import verify_pki_dh_parameters
from vyos.defaults import api_config_state
from vyos.pki import wrap_certificate
from vyos.pki import wrap_private_key
from vyos.pki import wrap_dh_parameters
from vyos.template import render
from vyos.utils.dict import dict_search
from vyos.utils.process import call
from vyos.utils.process import is_systemd_service_active
from vyos.utils.network import check_port_availability
from vyos.utils.network import is_listen_port_bind_service
from vyos.utils.file import write_file
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_file = '/etc/nginx/sites-enabled/default'
systemd_override = r'/run/systemd/system/nginx.service.d/override.conf'
cert_dir = '/run/nginx/certs'

user = 'www-data'
group = 'www-data'

systemd_service_api = '/run/systemd/system/vyos-http-api.service'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['service', 'https']
    if not conf.exists(base):
        return None

    https = conf.get_config_dict(base, get_first_key=True,
                                 key_mangling=('-', '_'),
                                 with_pki=True)

    # store path to API config file for later use in templates
    https['api_config_state'] = api_config_state
    # get fully qualified system hsotname
    https['hostname'] = socket.getfqdn()

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_values = conf.get_config_defaults(**https.kwargs, recursive=True)
    if 'api' not in https or 'graphql' not in https['api']:
        del default_values['api']

    # merge CLI and default dictionary
    https = config_dict_merge(default_values, https)
    return https

def verify(https):
    if https is None:
        return None

    if dict_search('certificates.certificate', https) != None:
        verify_pki_certificate(https, https['certificates']['certificate'])

        tmp = dict_search('certificates.ca_certificate', https)
        if tmp != None: verify_pki_ca_certificate(https, tmp)

        tmp = dict_search('certificates.dh_params', https)
        if tmp != None: verify_pki_dh_parameters(https, tmp, 2048)

    else:
        Warning('No certificate specified, using build-in self-signed certificates. '\
                'Do not use them in a production environment!')

    # Check if server port is already in use by a different appliaction
    listen_address = ['0.0.0.0']
    port = int(https['port'])
    if 'listen_address' in https:
        listen_address = https['listen_address']

    for address in listen_address:
        if not check_port_availability(address, port, 'tcp') and not is_listen_port_bind_service(port, 'nginx'):
            raise ConfigError(f'TCP port "{port}" is used by another service!')

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
            raise ConfigError('At least one HTTPS API key is required unless GraphQL token authentication is enabled!')

        if (not valid_keys_exist) and jwt_auth:
            Warning(f'API keys are not configured: classic (non-GraphQL) API will be unavailable!')

    return None

def generate(https):
    if https is None:
        for file in [systemd_service_api, config_file, systemd_override]:
            if os.path.exists(file):
                os.unlink(file)
        return None

    if 'api' in https:
        render(systemd_service_api, 'https/vyos-http-api.service.j2', https)
        with open(api_config_state, 'w') as f:
            json.dump(https['api'], f, indent=2)
    else:
        if os.path.exists(systemd_service_api):
            os.unlink(systemd_service_api)

    # get certificate data
    if 'certificates' in https and 'certificate' in https['certificates']:
        cert_name = https['certificates']['certificate']
        pki_cert = https['pki']['certificate'][cert_name]

        cert_path = os.path.join(cert_dir, f'{cert_name}_cert.pem')
        key_path = os.path.join(cert_dir, f'{cert_name}_key.pem')

        server_cert = str(wrap_certificate(pki_cert['certificate']))

        # Append CA certificate if specified to form a full chain
        if 'ca_certificate' in https['certificates']:
            ca_cert = https['certificates']['ca_certificate']
            server_cert += '\n' + str(wrap_certificate(https['pki']['ca'][ca_cert]['certificate']))

        write_file(cert_path, server_cert, user=user, group=group, mode=0o644)
        write_file(key_path, wrap_private_key(pki_cert['private']['key']),
                    user=user, group=group, mode=0o600)

        tmp_path = {'cert_path': cert_path, 'key_path': key_path}

        if 'dh_params' in https['certificates']:
            dh_name = https['certificates']['dh_params']
            pki_dh = https['pki']['dh'][dh_name]
            if 'parameters' in pki_dh:
                dh_path = os.path.join(cert_dir, f'{dh_name}_dh.pem')
                write_file(dh_path, wrap_dh_parameters(pki_dh['parameters']),
                           user=user, group=group, mode=0o600)
                tmp_path.update({'dh_file' : dh_path})

        https['certificates'].update(tmp_path)

    render(config_file, 'https/nginx.default.j2', https)
    render(systemd_override, 'https/override.conf.j2', https)
    return None

def apply(https):
    # Reload systemd manager configuration
    call('systemctl daemon-reload')
    http_api_service_name = 'vyos-http-api.service'
    https_service_name = 'nginx.service'

    if https is None:
        if is_systemd_service_active(http_api_service_name):
            call(f'systemctl stop {http_api_service_name}')
        call(f'systemctl stop {https_service_name}')
        return

    if 'api' in https:
        call(f'systemctl reload-or-restart {http_api_service_name}')
        # Let uvicorn settle before (possibly) restarting nginx
        sleep(1)
    elif is_systemd_service_active(http_api_service_name):
        call(f'systemctl stop {http_api_service_name}')

    call(f'systemctl reload-or-restart {https_service_name}')

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
