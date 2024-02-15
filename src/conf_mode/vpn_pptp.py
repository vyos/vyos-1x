#!/usr/bin/env python3
#
# Copyright (C) 2018-2023 VyOS maintainers and contributors
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
from vyos.template import render
from vyos.utils.process import call
from vyos.utils.dict import dict_search
from vyos.accel_ppp_util import verify_accel_ppp_name_servers
from vyos.accel_ppp_util import verify_accel_ppp_wins_servers
from vyos.accel_ppp_util import verify_accel_ppp_authentication
from vyos.accel_ppp_util import verify_accel_ppp_ip_pool
from vyos.accel_ppp_util import get_pools_in_order
from vyos import ConfigError
from vyos.configdict import get_accel_dict

from vyos import airbag
airbag.enable()

pptp_conf = '/run/accel-pppd/pptp.conf'
pptp_chap_secrets = '/run/accel-pppd/pptp.chap-secrets'


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['vpn', 'pptp', 'remote-access']
    if not conf.exists(base):
        return None

    # retrieve common dictionary keys
    pptp = get_accel_dict(conf, base, pptp_chap_secrets)

    if dict_search('client_ip_pool', pptp):
        # Multiple named pools require ordered values T5099
        pptp['ordered_named_pools'] = get_pools_in_order(
            dict_search('client_ip_pool', pptp))
    pptp['chap_secrets_file'] = pptp_chap_secrets
    pptp['server_type'] = 'pptp'
    return pptp


def verify(pptp):
    if not pptp:
        return None

    verify_accel_ppp_authentication(pptp)
    verify_accel_ppp_ip_pool(pptp)
    verify_accel_ppp_name_servers(pptp)
    verify_accel_ppp_wins_servers(pptp)


def generate(pptp):
    if not pptp:
        return None

    render(pptp_conf, 'accel-ppp/pptp.config.j2', pptp)

    if dict_search('authentication.mode', pptp) == 'local':
        render(pptp_chap_secrets, 'accel-ppp/chap-secrets.config_dict.j2',
               pptp, permission=0o640)

    return None


def apply(pptp):
    if not pptp:
        call('systemctl stop accel-ppp@pptp.service')
        for file in [pptp_conf, pptp_chap_secrets]:
            if os.path.exists(file):
                os.unlink(file)

        return None

    call('systemctl restart accel-ppp@pptp.service')


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
