#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
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
from vyos.utils.process import call
from vyos.utils.network import check_port_availability
from vyos.utils.network import is_listen_port_bind_service
from vyos.pki import wrap_certificate
from vyos.pki import wrap_private_key
from vyos.template import render
from vyos import ConfigError
from vyos import airbag
airbag.enable()

load_balancing_dir = '/run/haproxy'
load_balancing_conf_file = f'{load_balancing_dir}/haproxy.cfg'
systemd_service = 'haproxy.service'
systemd_override = r'/run/systemd/system/haproxy.service.d/10-override.conf'


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['load-balancing', 'reverse-proxy']
    lb = conf.get_config_dict(base,
                              get_first_key=True,
                              key_mangling=('-', '_'),
                              no_tag_node_value_mangle=True)

    if lb:
        lb['pki'] = conf.get_config_dict(['pki'], key_mangling=('-', '_'),
                                    get_first_key=True, no_tag_node_value_mangle=True)

    if lb:
        lb = conf.merge_defaults(lb, recursive=True)

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
        if 'server' not in back_config:
            raise ConfigError(f'"{back} server" must be configured!')
        for bk_server, bk_server_conf in back_config['server'].items():
            if 'address' not in bk_server_conf or 'port' not in bk_server_conf:
                raise ConfigError(f'"backend {back} server {bk_server} address and port" must be configured!')

            if {'send_proxy', 'send_proxy_v2'} <= set(bk_server_conf):
                raise ConfigError(f'Cannot use both "send-proxy" and "send-proxy-v2" for server "{bk_server}"')

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

    # SSL Certificates for frontend
    for front, front_config in lb['service'].items():
        if 'ssl' in front_config:

            if 'certificate' in front_config['ssl']:
                cert_name = front_config['ssl']['certificate']
                pki_cert = lb['pki']['certificate'][cert_name]
                cert_file_path = os.path.join(load_balancing_dir, f'{cert_name}.pem')
                cert_key_path = os.path.join(load_balancing_dir, f'{cert_name}.pem.key')

                with open(cert_file_path, 'w') as f:
                    f.write(wrap_certificate(pki_cert['certificate']))

                if 'private' in pki_cert and 'key' in pki_cert['private']:
                    with open(cert_key_path, 'w') as f:
                        f.write(wrap_private_key(pki_cert['private']['key']))

            if 'ca_certificate' in front_config['ssl']:
                ca_name = front_config['ssl']['ca_certificate']
                pki_ca_cert = lb['pki']['ca'][ca_name]
                ca_cert_file_path = os.path.join(load_balancing_dir, f'{ca_name}.pem')

                with open(ca_cert_file_path, 'w') as f:
                    f.write(wrap_certificate(pki_ca_cert['certificate']))

    # SSL Certificates for backend
    for back, back_config in lb['backend'].items():
        if 'ssl' in back_config:

            if 'ca_certificate' in back_config['ssl']:
                ca_name = back_config['ssl']['ca_certificate']
                pki_ca_cert = lb['pki']['ca'][ca_name]
                ca_cert_file_path = os.path.join(load_balancing_dir, f'{ca_name}.pem')

                with open(ca_cert_file_path, 'w') as f:
                    f.write(wrap_certificate(pki_ca_cert['certificate']))

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
