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

from copy import deepcopy
from sys import exit

from vyos.config import Config
from vyos.configdict import get_accel_dict
from vyos.configdict import is_node_changed
from vyos.configverify import verify_interface_exists
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

    if dict_search('client_ip_pool', pppoe):
        # Multiple named pools require ordered values T5099
        pppoe['ordered_named_pools'] = get_pools_in_order(dict_search('client_ip_pool', pppoe))

    # reload-or-restart does not implemented in accel-ppp
    # use this workaround until it will be implemented
    # https://phabricator.accel-ppp.org/T3
    conditions = [is_node_changed(conf, base + ['client-ip-pool']),
                  is_node_changed(conf, base + ['client-ipv6-pool']),
                  is_node_changed(conf, base + ['interface'])]
    if any(conditions):
        pppoe.update({'restart_required': {}})
    pppoe['server_type'] = 'pppoe'
    return pppoe

def verify_pado_delay(pppoe):
    if 'pado_delay' in pppoe:
        pado_delay = deepcopy(pppoe['pado_delay'])

        if 'disable' in pado_delay and 'sessions' not in pado_delay['disable']:
            raise ConfigError(
                'Number of sessions must be specified for "pado-delay disable"'
            )

        delays_without_sessions = [delay for delay, session in pado_delay.items() if not session]
        if len(delays_without_sessions) > 1:
            raise ConfigError(
                f'Cannot add more then ONE pado-delay without sessions, '
                f'but {len(delays_without_sessions)} were set'
            )

        if 'disable' in pado_delay:
            # need to sort delays by sessions to verify if there is no delay
            # for sessions after disabling
            if delays_without_sessions:
                pado_delay.pop(delays_without_sessions[0], None)
            sorted_pado_delay = sorted(pado_delay.items(), key=lambda k_v: k_v[1]['sessions'])
            last_delay = sorted_pado_delay[-1]

            if last_delay[0] != 'disable':
                raise ConfigError(
                    f'Cannot add pado-delay after disabled sessions, but '
                    f'"pado-delay {last_delay[0]} sessions {last_delay[1]["sessions"]}" was set'
                )

def verify(pppoe):
    if not pppoe:
        return None

    verify_accel_ppp_authentication(pppoe)
    verify_accel_ppp_ip_pool(pppoe)
    verify_accel_ppp_name_servers(pppoe)
    verify_accel_ppp_wins_servers(pppoe)
    verify_pado_delay(pppoe)

    if 'interface' not in pppoe:
        raise ConfigError('At least one listen interface must be defined!')

    # Check is interface exists in the system
    for interface in pppoe['interface']:
        verify_interface_exists(interface)

    return None


def generate(pppoe):
    if not pppoe:
        return None

    render(pppoe_conf, 'accel-ppp/pppoe.config.j2', pppoe)

    if dict_search('authentication.mode', pppoe) == 'local':
        render(pppoe_chap_secrets, 'accel-ppp/chap-secrets.config_dict.j2',
               pppoe, permission=0o640)
    return None


def apply(pppoe):
    systemd_service = 'accel-ppp@pppoe.service'
    if not pppoe:
        call(f'systemctl stop {systemd_service}')
        for file in [pppoe_conf, pppoe_chap_secrets]:
            if os.path.exists(file):
                os.unlink(file)
        return None

    if 'restart_required' in pppoe:
        call(f'systemctl restart {systemd_service}')
    else:
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
