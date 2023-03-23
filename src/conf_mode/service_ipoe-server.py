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
import jmespath

from sys import exit

from vyos.config import Config
from vyos.configdict import get_accel_dict
from vyos.configverify import verify_accel_ppp_base_service
from vyos.configverify import verify_interface_exists
from vyos.template import render
from vyos.util import call
from vyos.util import dict_search
from vyos import ConfigError
from vyos import airbag
airbag.enable()


ipoe_conf = '/run/accel-pppd/ipoe.conf'
ipoe_chap_secrets = '/run/accel-pppd/ipoe.chap-secrets'


def get_pools_in_order(data: dict) -> list:
    """Return a list of dictionaries representing pool data in the order
    in which they should be allocated. Pool must be defined before we can
    use it with 'next-pool' option.

    Args:
        data: A dictionary of pool data, where the keys are pool names and the
        values are dictionaries containing the 'subnet' key and the optional
        'next_pool' key.

    Returns:
        list: A list of dictionaries

    Raises:
        ValueError: If a 'next_pool' key references a pool name that
                    has not been defined.
        ValueError: If a circular reference is found in the 'next_pool' keys.

    Example:
        config_data = {
        ... 'first-pool': {
        ... 'next_pool': 'second-pool',
        ... 'subnet': '192.0.2.0/25'
        ... },
        ... 'second-pool': {
        ... 'next_pool': 'third-pool',
        ... 'subnet': '203.0.113.0/25'
        ... },
        ... 'third-pool': {
        ... 'subnet': '198.51.100.0/24'
        ... },
        ... 'foo': {
        ... 'subnet': '100.64.0.0/24',
        ... 'next_pool': 'second-pool'
        ... }
        ... }

        % get_pools_in_order(config_data)
        [{'third-pool': {'subnet': '198.51.100.0/24'}},
        {'second-pool': {'next_pool': 'third-pool', 'subnet': '203.0.113.0/25'}},
        {'first-pool': {'next_pool': 'second-pool', 'subnet': '192.0.2.0/25'}},
        {'foo': {'next_pool': 'second-pool', 'subnet': '100.64.0.0/24'}}]
    """
    pools = []
    unresolved_pools = {}

    for pool, pool_config in data.items():
        if 'next_pool' not in pool_config:
            pools.insert(0, {pool: pool_config})
        else:
            unresolved_pools[pool] = pool_config

    while unresolved_pools:
        resolved_pools = []

        for pool, pool_config in unresolved_pools.items():
            next_pool_name = pool_config['next_pool']

            if any(p for p in pools if next_pool_name in p):
                index = next(
                    (i for i, p in enumerate(pools) if next_pool_name in p),
                    None)
                pools.insert(index + 1, {pool: pool_config})
                resolved_pools.append(pool)
            elif next_pool_name in unresolved_pools:
                # next pool not yet resolved
                pass
            else:
                raise ValueError(
                    f"Pool '{next_pool_name}' not defined in configuration data"
                )

        if not resolved_pools:
            raise ValueError("Circular reference in configuration data")

        for pool in resolved_pools:
            unresolved_pools.pop(pool)

    return pools


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

    if jmespath.search('client_ip_pool.name', ipoe):
        dict_named_pools = jmespath.search('client_ip_pool.name', ipoe)
        # Multiple named pools require ordered values T5099
        ipoe['ordered_named_pools'] = get_pools_in_order(dict_named_pools)
        # T5099 'next-pool' option
        if jmespath.search('client_ip_pool.name.*.next_pool', ipoe):
            for pool, pool_config in ipoe['client_ip_pool']['name'].items():
                if 'next_pool' in pool_config:
                    ipoe['first_named_pool'] = pool
                    ipoe['first_named_pool_subnet'] = pool_config
                    break

    return ipoe


def verify(ipoe):
    if not ipoe:
        return None

    if 'interface' not in ipoe:
        raise ConfigError('No IPoE interface configured')

    for interface, iface_config in ipoe['interface'].items():
        verify_interface_exists(interface)
        if 'client_subnet' in iface_config and 'vlan' in iface_config:
            raise ConfigError('Option "client-subnet" incompatible with "vlan"!'
                              'Use "ipoe client-ip-pool" instead.')

    #verify_accel_ppp_base_service(ipoe, local_users=False)
    # IPoE server does not have 'gateway' option in the CLI
    # we cannot use configverify.py verify_accel_ppp_base_service for ipoe-server

    if dict_search('authentication.mode', ipoe) == 'radius':
        if not dict_search('authentication.radius.server', ipoe):
            raise ConfigError('RADIUS authentication requires at least one server')

        for server in dict_search('authentication.radius.server', ipoe):
            radius_config = ipoe['authentication']['radius']['server'][server]
            if 'key' not in radius_config:
                raise ConfigError(f'Missing RADIUS secret key for server "{server}"')

    if 'client_ipv6_pool' in ipoe:
        if 'delegate' in ipoe['client_ipv6_pool'] and 'prefix' not in ipoe['client_ipv6_pool']:
            raise ConfigError('IPoE IPv6 deletate-prefix requires IPv6 prefix to be configured!')

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
