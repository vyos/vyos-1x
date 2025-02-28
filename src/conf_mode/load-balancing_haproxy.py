#!/usr/bin/env python3
#
# Copyright (C) 2023-2024 VyOS maintainers and contributors
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
from shutil import rmtree

from vyos.config import Config
from vyos.configverify import verify_pki_certificate
from vyos.configverify import verify_pki_ca_certificate
from vyos.utils.dict import dict_search
from vyos.utils.process import call
from vyos.utils.network import check_port_availability
from vyos.utils.network import is_listen_port_bind_service
from vyos.pki import find_chain
from vyos.pki import load_certificate
from vyos.pki import load_private_key
from vyos.pki import encode_certificate
from vyos.pki import encode_private_key
from vyos.template import render
from vyos.utils.file import write_file
from vyos import ConfigError
from vyos import airbag
airbag.enable()

load_balancing_dir = '/run/haproxy'
load_balancing_conf_file = f'{load_balancing_dir}/haproxy.cfg'
systemd_service = 'haproxy.service'
systemd_override = '/run/systemd/system/haproxy.service.d/10-override.conf'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['load-balancing', 'haproxy']
    if not conf.exists(base):
        return None
    lb = conf.get_config_dict(base,
                              get_first_key=True,
                              key_mangling=('-', '_'),
                              no_tag_node_value_mangle=True,
                              with_recursive_defaults=True,
                              with_pki=True)

    return lb

def verify(lb):
    if not lb:
        return None

    if 'backend' not in lb or 'service' not in lb:
        raise ConfigError(f'"service" and "backend" must be configured!')

    for front, front_config in lb['service'].items():
        if 'port' not in front_config:
            raise ConfigError(f'"{front} service port" must be configured!')

        # Check if bind address:port are used by another service
        tmp_address = front_config.get('address', '0.0.0.0')
        tmp_port = front_config['port']
        if check_port_availability(tmp_address, int(tmp_port), 'tcp') is not True and \
                not is_listen_port_bind_service(int(tmp_port), 'haproxy'):
            raise ConfigError(f'"TCP" port "{tmp_port}" is used by another service')

    for back, back_config in lb['backend'].items():
        if 'http_check' in back_config:
            http_check = back_config['http_check']
            if 'expect' in http_check and 'status' in http_check['expect'] and 'string' in http_check['expect']:
                raise ConfigError(f'"expect status" and "expect string" can not be configured together!')

        if 'health_check' in back_config:
            if back_config['mode'] != 'tcp':
                raise ConfigError(f'backend "{back}" can only be configured with {back_config["health_check"]} ' +
                                  f'health-check whilst in TCP mode!')
            if 'http_check' in back_config:
                raise ConfigError(f'backend "{back}" cannot be configured with both http-check and health-check!')

        if 'server' not in back_config:
            raise ConfigError(f'"{back} server" must be configured!')

        for bk_server, bk_server_conf in back_config['server'].items():
            if 'address' not in bk_server_conf or 'port' not in bk_server_conf:
                raise ConfigError(f'"backend {back} server {bk_server} address and port" must be configured!')

            if {'send_proxy', 'send_proxy_v2'} <= set(bk_server_conf):
                raise ConfigError(f'Cannot use both "send-proxy" and "send-proxy-v2" for server "{bk_server}"')

        if 'ssl' in back_config:
            if {'no_verify', 'ca_certificate'} <= set(back_config['ssl']):
                raise ConfigError(f'backend {back} cannot have both ssl options no-verify and ca-certificate set!')

    # Check if http-response-headers are configured in any frontend/backend where mode != http
    for group in ['service', 'backend']:
        for config_name, config in lb[group].items():
            if 'http_response_headers' in config and config['mode'] != 'http':
                raise ConfigError(f'{group} {config_name} must be set to http mode to use http_response_headers!')

    for front, front_config in lb['service'].items():
        for cert in dict_search('ssl.certificate', front_config) or []:
            verify_pki_certificate(lb, cert)

    for back, back_config in lb['backend'].items():
        tmp = dict_search('ssl.ca_certificate', back_config)
        if tmp: verify_pki_ca_certificate(lb, tmp)


def generate(lb):
    if not lb:
        # Delete /run/haproxy/haproxy.cfg
        config_files = [load_balancing_conf_file, systemd_override]
        for file in config_files:
            if os.path.isfile(file):
                os.unlink(file)
        # Delete old directories
        if os.path.isdir(load_balancing_dir):
            rmtree(load_balancing_dir, ignore_errors=True)

        return None

    # Create load-balance dir
    if not os.path.isdir(load_balancing_dir):
        os.mkdir(load_balancing_dir)

    loaded_ca_certs = {load_certificate(c['certificate'])
        for c in lb['pki']['ca'].values()} if 'ca' in lb['pki'] else {}

    # SSL Certificates for frontend
    for front, front_config in lb['service'].items():
        if 'ssl' not in front_config:
            continue

        if 'certificate' in front_config['ssl']:
            cert_names = front_config['ssl']['certificate']

            for cert_name in cert_names:
                pki_cert = lb['pki']['certificate'][cert_name]
                cert_file_path = os.path.join(load_balancing_dir, f'{cert_name}.pem')
                cert_key_path = os.path.join(load_balancing_dir, f'{cert_name}.pem.key')

                loaded_pki_cert = load_certificate(pki_cert['certificate'])
                cert_full_chain = find_chain(loaded_pki_cert, loaded_ca_certs)

                write_file(cert_file_path,
                   '\n'.join(encode_certificate(c) for c in cert_full_chain))

                if 'private' in pki_cert and 'key' in pki_cert['private']:
                    loaded_key = load_private_key(pki_cert['private']['key'], passphrase=None, wrap_tags=True)
                    key_pem = encode_private_key(loaded_key, passphrase=None)
                    write_file(cert_key_path, key_pem)

    # SSL Certificates for backend
    for back, back_config in lb['backend'].items():
        if 'ssl' not in back_config:
            continue

        if 'ca_certificate' in back_config['ssl']:
            ca_name = back_config['ssl']['ca_certificate']
            ca_cert_file_path = os.path.join(load_balancing_dir, f'{ca_name}.pem')
            ca_chains = []

            pki_ca_cert = lb['pki']['ca'][ca_name]
            loaded_ca_cert = load_certificate(pki_ca_cert['certificate'])
            ca_full_chain = find_chain(loaded_ca_cert, loaded_ca_certs)
            ca_chains.append('\n'.join(encode_certificate(c) for c in ca_full_chain))
            write_file(ca_cert_file_path, '\n'.join(ca_chains))

    render(load_balancing_conf_file, 'load-balancing/haproxy.cfg.j2', lb)
    render(systemd_override, 'load-balancing/override_haproxy.conf.j2', lb)

    return None

def apply(lb):
    call('systemctl daemon-reload')
    if not lb:
        call(f'systemctl stop {systemd_service}')
    else:
        call(f'systemctl reload-or-restart {systemd_service}')

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
