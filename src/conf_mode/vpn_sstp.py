#!/usr/bin/env python3
#
# Copyright (C) 2018-2024 VyOS maintainers and contributors
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
from vyos.configdict import get_accel_dict
from vyos.configverify import verify_pki_certificate
from vyos.configverify import verify_pki_ca_certificate
from vyos.pki import wrap_certificate
from vyos.pki import wrap_private_key
from vyos.template import render
from vyos.utils.process import call
from vyos.utils.network import check_port_availability
from vyos.utils.dict import dict_search
from vyos.accel_ppp_util import verify_accel_ppp_name_servers
from vyos.accel_ppp_util import verify_accel_ppp_wins_servers
from vyos.accel_ppp_util import verify_accel_ppp_authentication
from vyos.accel_ppp_util import verify_accel_ppp_ip_pool
from vyos.accel_ppp_util import get_pools_in_order
from vyos.utils.network import is_listen_port_bind_service
from vyos.utils.file import write_file
from vyos import ConfigError
from vyos import airbag
airbag.enable()

cfg_dir = '/run/accel-pppd'
sstp_conf = '/run/accel-pppd/sstp.conf'
sstp_chap_secrets = '/run/accel-pppd/sstp.chap-secrets'

cert_file_path = os.path.join(cfg_dir, 'sstp-cert.pem')
cert_key_path = os.path.join(cfg_dir, 'sstp-cert.key')
ca_cert_file_path = os.path.join(cfg_dir, 'sstp-ca.pem')


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['vpn', 'sstp']
    if not conf.exists(base):
        return None

    # retrieve common dictionary keys
    sstp = get_accel_dict(conf, base, sstp_chap_secrets, with_pki=True)
    if dict_search('client_ip_pool', sstp):
        # Multiple named pools require ordered values T5099
        sstp['ordered_named_pools'] = get_pools_in_order(dict_search('client_ip_pool', sstp))

    sstp['server_type'] = 'sstp'
    return sstp


def verify(sstp):
    if not sstp:
        return None

    port = sstp.get('port')
    proto = 'tcp'
    if check_port_availability('0.0.0.0', int(port), proto) is not True and \
            not is_listen_port_bind_service(int(port), 'accel-pppd'):
        raise ConfigError(f'"{proto}" port "{port}" is used by another service')

    verify_accel_ppp_authentication(sstp)
    verify_accel_ppp_ip_pool(sstp)
    verify_accel_ppp_name_servers(sstp)
    verify_accel_ppp_wins_servers(sstp)

    if 'ssl' not in sstp:
        raise ConfigError('SSL missing on SSTP config!')

    if 'certificate' not in sstp['ssl']:
        raise ConfigError('SSL certificate missing on SSTP config!')
    verify_pki_certificate(sstp, sstp['ssl']['certificate'])

    if 'ca_certificate' not in sstp['ssl']:
        raise ConfigError('SSL CA certificate missing on SSTP config!')
    verify_pki_ca_certificate(sstp, sstp['ssl']['ca_certificate'])


def generate(sstp):
    if not sstp:
        return None

    # accel-cmd reload doesn't work so any change results in a restart of the daemon
    render(sstp_conf, 'accel-ppp/sstp.config.j2', sstp)

    cert_name = sstp['ssl']['certificate']
    pki_cert = sstp['pki']['certificate'][cert_name]

    ca_cert_name = sstp['ssl']['ca_certificate']
    pki_ca = sstp['pki']['ca'][ca_cert_name]
    write_file(cert_file_path, wrap_certificate(pki_cert['certificate']))
    write_file(cert_key_path, wrap_private_key(pki_cert['private']['key']))
    write_file(ca_cert_file_path, wrap_certificate(pki_ca['certificate']))

    if dict_search('authentication.mode', sstp) == 'local':
        render(sstp_chap_secrets, 'accel-ppp/chap-secrets.config_dict.j2',
               sstp, permission=0o640)
    else:
        if os.path.exists(sstp_chap_secrets):
             os.unlink(sstp_chap_secrets)

    return sstp


def apply(sstp):
    systemd_service = 'accel-ppp@sstp.service'
    if not sstp:
        call(f'systemctl stop {systemd_service}')
        for file in [sstp_chap_secrets, sstp_conf]:
            if os.path.exists(file):
                os.unlink(file)
        return None

    call(f'systemctl reload-or-restart {systemd_service}')


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
