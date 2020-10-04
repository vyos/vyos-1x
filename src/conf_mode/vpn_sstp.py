#!/usr/bin/env python3
#
# Copyright (C) 2018-2020 VyOS maintainers and contributors
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
from vyos.configverify import verify_accel_ppp_base_service
from vyos.template import render
from vyos.util import call
from vyos.util import vyos_dict_search
from vyos import ConfigError
from vyos import airbag
airbag.enable()

sstp_conf = '/run/accel-pppd/sstp.conf'
sstp_chap_secrets = '/run/accel-pppd/sstp.chap-secrets'

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
    return sstp

def verify(sstp):
    if not sstp:
        return None

    verify_accel_ppp_base_service(sstp)

    if not sstp['client_ip_pool']:
        raise ConfigError('Client IP subnet required')

    #
    # SSL certificate checks
    #
    tmp = vyos_dict_search('ssl.ca_cert_file', sstp)
    if not tmp:
        raise ConfigError(f'SSL CA certificate file required!')
    else:
        if not os.path.isfile(tmp):
            raise ConfigError(f'SSL CA certificate "{tmp}" does not exist!')

    tmp = vyos_dict_search('ssl.cert_file', sstp)
    if not tmp:
        raise ConfigError(f'SSL public key file required!')
    else:
        if not os.path.isfile(tmp):
            raise ConfigError(f'SSL public key "{tmp}" does not exist!')

    tmp = vyos_dict_search('ssl.key_file', sstp)
    if not tmp:
        raise ConfigError(f'SSL private key file required!')
    else:
        if not os.path.isfile(tmp):
            raise ConfigError(f'SSL private key "{tmp}" does not exist!')

def generate(sstp):
    if not sstp:
        return None

    # accel-cmd reload doesn't work so any change results in a restart of the daemon
    render(sstp_conf, 'accel-ppp/sstp.config.tmpl', sstp, trim_blocks=True)

    if vyos_dict_search('authentication.mode', sstp) == 'local':
        render(sstp_chap_secrets, 'accel-ppp/chap-secrets.config_dict.tmpl',
               sstp, trim_blocks=True, permission=0o640)
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
