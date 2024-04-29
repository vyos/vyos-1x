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
from vyos.configverify import verify_interface_exists
from vyos.template import render
from vyos.utils.process import call
from vyos.utils.dict import dict_search
from vyos.accel_ppp_util import get_pools_in_order
from vyos.accel_ppp_util import verify_accel_ppp_name_servers
from vyos.accel_ppp_util import verify_accel_ppp_wins_servers
from vyos.accel_ppp_util import verify_accel_ppp_ip_pool
from vyos.accel_ppp_util import verify_accel_ppp_authentication
from vyos import ConfigError
from vyos import airbag
airbag.enable()


ipoe_conf = '/run/accel-pppd/ipoe.conf'
ipoe_chap_secrets = '/run/accel-pppd/ipoe.chap-secrets'


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'ipoe-server']
    if not conf.exists(base):
        return None

    # retrieve common dictionary keys
    ipoe = get_accel_dict(conf, base, ipoe_chap_secrets)

    if dict_search('client_ip_pool', ipoe):
        # Multiple named pools require ordered values T5099
        ipoe['ordered_named_pools'] = get_pools_in_order(dict_search('client_ip_pool', ipoe))

    ipoe['server_type'] = 'ipoe'
    return ipoe


def verify(ipoe):
    if not ipoe:
        return None

    if 'interface' not in ipoe:
        raise ConfigError('No IPoE interface configured')

    for interface, iface_config in ipoe['interface'].items():
        verify_interface_exists(interface, warning_only=True)
        if 'client_subnet' in iface_config and 'vlan' in iface_config:
            raise ConfigError('Option "client-subnet" and "vlan" are mutually exclusive, '
                              'use "client-ip-pool" instead!')

    verify_accel_ppp_authentication(ipoe, local_users=False)
    verify_accel_ppp_ip_pool(ipoe)
    verify_accel_ppp_name_servers(ipoe)
    verify_accel_ppp_wins_servers(ipoe)

    return None


def generate(ipoe):
    if not ipoe:
        return None

    render(ipoe_conf, 'accel-ppp/ipoe.config.j2', ipoe)

    if dict_search('authentication.mode', ipoe) == 'local':
        render(ipoe_chap_secrets, 'accel-ppp/chap-secrets.ipoe.j2',
               ipoe, permission=0o640)
    return None


def apply(ipoe):
    systemd_service = 'accel-ppp@ipoe.service'
    if ipoe == None:
        call(f'systemctl stop {systemd_service}')
        for file in [ipoe_conf, ipoe_chap_secrets]:
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
