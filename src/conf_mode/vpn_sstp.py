#!/usr/bin/env python3
#
# Copyright (C) 2018-2022 VyOS maintainers and contributors
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
from vyos.configdict import dict_merge
from vyos.configverify import verify_accel_ppp_base_service
from vyos.pki import wrap_certificate
from vyos.pki import wrap_private_key
from vyos.template import render
from vyos.util import call
from vyos.util import check_port_availability
from vyos.util import dict_search
from vyos.util import is_listen_port_bind_service
from vyos.util import write_file
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
    sstp = get_accel_dict(conf, base, sstp_chap_secrets)
    if sstp:
        sstp['pki'] = conf.get_config_dict(['pki'], key_mangling=('-', '_'),
                                           get_first_key=True,
                                           no_tag_node_value_mangle=True)

    return sstp

def verify(sstp):
    if not sstp:
        return None

    port = sstp.get('port')
    proto = 'tcp'
    if check_port_availability('0.0.0.0', int(port), proto) is not True and \
            not is_listen_port_bind_service(int(port), 'accel-pppd'):
        raise ConfigError(f'"{proto}" port "{port}" is used by another service')

    verify_accel_ppp_base_service(sstp)

    if 'client_ip_pool' not in sstp and 'client_ipv6_pool' not in sstp:
        raise ConfigError('Client IP subnet required')

    #
    # SSL certificate checks
    #
    if not sstp['pki']:
        raise ConfigError('PKI is not configured')

    if 'ssl' not in sstp:
        raise ConfigError('SSL missing on SSTP config')

    ssl = sstp['ssl']

    # CA
    if 'ca_certificate' not in ssl:
        raise ConfigError('SSL CA certificate missing on SSTP config')

    ca_name = ssl['ca_certificate']

    if ca_name not in sstp['pki']['ca']:
        raise ConfigError('Invalid CA certificate on SSTP config')

    if 'certificate' not in sstp['pki']['ca'][ca_name]:
        raise ConfigError('Missing certificate data for CA certificate on SSTP config')

    # Certificate
    if 'certificate' not in ssl:
        raise ConfigError('SSL certificate missing on SSTP config')

    cert_name = ssl['certificate']

    if cert_name not in sstp['pki']['certificate']:
        raise ConfigError('Invalid certificate on SSTP config')

    pki_cert = sstp['pki']['certificate'][cert_name]

    if 'certificate' not in pki_cert:
        raise ConfigError('Missing certificate data for certificate on SSTP config')

    if 'private' not in pki_cert or 'key' not in pki_cert['private']:
        raise ConfigError('Missing private key for certificate on SSTP config')

    if 'password_protected' in pki_cert['private']:
        raise ConfigError('Encrypted private key is not supported on SSTP config')

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
    if not sstp:
        call('systemctl stop accel-ppp@sstp.service')
        for file in [sstp_chap_secrets, sstp_conf]:
            if os.path.exists(file):
                os.unlink(file)

        return None

    call('systemctl restart accel-ppp@sstp.service')


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
