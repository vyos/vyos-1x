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
from vyos.util import dict_search
from vyos import ConfigError
from vyos import airbag
airbag.enable()

pppoe_conf = r'/run/accel-pppd/pppoe.conf'
pppoe_chap_secrets = r'/run/accel-pppd/pppoe.chap-secrets'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'pppoe-server']
    if not conf.exists(base):
        return None

    # retrieve common dictionary keys
    pppoe = get_accel_dict(conf, base, pppoe_chap_secrets)
    return pppoe

def verify(pppoe):
    if not pppoe:
        return None

    verify_accel_ppp_base_service(pppoe)

    if 'wins_server' in pppoe and len(pppoe['wins_server']) > 2:
        raise ConfigError('Not more then two IPv4 WINS name-servers can be configured')

    if 'interface' not in pppoe:
        raise ConfigError('At least one listen interface must be defined!')

    # local ippool and gateway settings config checks
    if not (dict_search('client_ip_pool.subnet', pppoe) or
           (dict_search('client_ip_pool.start', pppoe) and
            dict_search('client_ip_pool.stop', pppoe))):
        print('Warning: No PPPoE client pool defined')

    if dict_search('authentication.radius.dynamic_author.server', pppoe):
        if not dict_search('authentication.radius.dynamic_author.key', pppoe):
            raise ConfigError('DA/CoE server key required!')

    return None


def generate(pppoe):
    if not pppoe:
        return None

    render(pppoe_conf, 'accel-ppp/pppoe.config.tmpl', pppoe)

    if dict_search('authentication.mode', pppoe) == 'local':
        render(pppoe_chap_secrets, 'accel-ppp/chap-secrets.config_dict.tmpl',
               pppoe, permission=0o640)
    else:
        if os.path.exists(pppoe_chap_secrets):
            os.unlink(pppoe_chap_secrets)

    return None


def apply(pppoe):
    if not pppoe:
        call('systemctl stop accel-ppp@pppoe.service')
        for file in [pppoe_conf, pppoe_chap_secrets]:
            if os.path.exists(file):
                os.unlink(file)

        return None

    call('systemctl restart accel-ppp@pppoe.service')

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
