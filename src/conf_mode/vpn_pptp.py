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
    auth_mode = dict_search('authentication.mode', pptp)
    if auth_mode == 'local':
        if not dict_search('authentication.local_users', pptp):
            raise ConfigError(
                'PPTP local auth mode requires local users to be configured!')

        for user in dict_search('authentication.local_users.username', pptp):
            user_config = pptp['authentication']['local_users']['username'][
                user]
            if 'password' not in user_config:
                raise ConfigError(f'Password required for local user "{user}"')

    elif auth_mode == 'radius':
        if not dict_search('authentication.radius.server', pptp):
            raise ConfigError(
                'RADIUS authentication requires at least one server')
        for server in dict_search('authentication.radius.server', pptp):
            radius_config = pptp['authentication']['radius']['server'][server]
            if 'key' not in radius_config:
                raise ConfigError(
                    f'Missing RADIUS secret key for server "{server}"')

    if auth_mode == 'local' or auth_mode == 'noauth':
        if not dict_search('client_ip_pool', pptp):
            raise ConfigError(
                'PPTP local auth mode requires local client-ip-pool '
                'to be configured!')

    verify_accel_ppp_ip_pool(pptp)

    if 'name_server' in pptp:
        if len(pptp['name_server']) > 2:
            raise ConfigError(
                'Not more then two IPv4 DNS name-servers can be configured'
            )

    if 'wins_server' in pptp and len(pptp['wins_server']) > 2:
        raise ConfigError(
            'Not more then two WINS name-servers can be configured')


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
