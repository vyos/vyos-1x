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

from sys import exit

from vyos.config import Config
from vyos.configdep import call_dependents, set_dependents
from vyos.configdict import get_accel_dict
from vyos.template import render
from vyos.utils.process import call
from vyos.utils.dict import dict_search
from vyos.accel_ppp_util import verify_accel_ppp_name_servers
from vyos.accel_ppp_util import verify_accel_ppp_wins_servers
from vyos.accel_ppp_util import verify_accel_ppp_authentication
from vyos.accel_ppp_util import verify_accel_ppp_ip_pool
from vyos.accel_ppp_util import get_pools_in_order
from vyos import ConfigError

from vyos import airbag
airbag.enable()


l2tp_conf = '/run/accel-pppd/l2tp.conf'
l2tp_chap_secrets = '/run/accel-pppd/l2tp.chap-secrets'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['vpn', 'l2tp', 'remote-access']

    set_dependents('ipsec', conf)

    if not conf.exists(base):
        return None

    # retrieve common dictionary keys
    l2tp = get_accel_dict(conf, base, l2tp_chap_secrets)
    if dict_search('client_ip_pool', l2tp):
        # Multiple named pools require ordered values T5099
        l2tp['ordered_named_pools'] = get_pools_in_order(
            dict_search('client_ip_pool', l2tp))
    l2tp['server_type'] = 'l2tp'
    return l2tp


def verify(l2tp):
    if not l2tp:
        return None

    verify_accel_ppp_authentication(l2tp)
    verify_accel_ppp_ip_pool(l2tp)
    verify_accel_ppp_name_servers(l2tp)
    verify_accel_ppp_wins_servers(l2tp)

    return None


def generate(l2tp):
    if not l2tp:
        return None

    render(l2tp_conf, 'accel-ppp/l2tp.config.j2', l2tp)

    if dict_search('authentication.mode', l2tp) == 'local':
        render(l2tp_chap_secrets, 'accel-ppp/chap-secrets.config_dict.j2',
               l2tp, permission=0o640)

    return None


def apply(l2tp):
    if not l2tp:
        call('systemctl stop accel-ppp@l2tp.service')
        for file in [l2tp_chap_secrets, l2tp_conf]:
            if os.path.exists(file):
                os.unlink(file)
    else:
        call('systemctl restart accel-ppp@l2tp.service')

    call_dependents()


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)

    except ConfigError as e:
        print(e)
        exit(1)
