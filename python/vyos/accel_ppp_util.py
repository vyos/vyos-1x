# Copyright 2023-2024 VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

# The sole purpose of this module is to hold common functions used in
# all kinds of implementations to verify the CLI configuration.
# It is started by migrating the interfaces to the new get_config_dict()
# approach which will lead to a lot of code that can be reused.

# NOTE: imports should be as local as possible to the function which
# makes use of it!

from vyos import ConfigError
from vyos.base import Warning
from vyos.utils.dict import dict_search

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
        if "next_pool" not in pool_config or not pool_config["next_pool"]:
            pools.insert(0, {pool: pool_config})
        else:
            unresolved_pools[pool] = pool_config

    while unresolved_pools:
        resolved_pools = []

        for pool, pool_config in unresolved_pools.items():
            next_pool_name = pool_config["next_pool"]

            if any(p for p in pools if next_pool_name in p):
                index = next(
                    (i for i, p in enumerate(pools) if next_pool_name in p), None
                )
                pools.insert(index + 1, {pool: pool_config})
                resolved_pools.append(pool)
            elif next_pool_name in unresolved_pools:
                # next pool not yet resolved
                pass
            else:
                raise ConfigError(
                    f"Pool '{next_pool_name}' not defined in configuration data"
                )

        if not resolved_pools:
            raise ConfigError("Circular reference in configuration data")

        for pool in resolved_pools:
            unresolved_pools.pop(pool)

    return pools


def verify_accel_ppp_name_servers(config):
    if "name_server_ipv4" in config:
        if len(config["name_server_ipv4"]) > 2:
            raise ConfigError(
                "Not more then two IPv4 DNS name-servers " "can be configured"
            )
    if "name_server_ipv6" in config:
        if len(config["name_server_ipv6"]) > 3:
            raise ConfigError(
                "Not more then three IPv6 DNS name-servers " "can be configured"
            )


def verify_accel_ppp_wins_servers(config):
    if 'wins_server' in config and len(config['wins_server']) > 2:
        raise ConfigError(
            'Not more then two WINS name-servers can be configured')


def verify_accel_ppp_authentication(config, local_users=True):
    """
    Common helper function which must be used by all Accel-PPP services based
    on get_config_dict()
    """
    # vertify auth settings
    if local_users and dict_search("authentication.mode", config) == "local":
        if (
            dict_search("authentication.local_users", config) is None
            or dict_search("authentication.local_users", config) == {}
        ):
            raise ConfigError(
                "Authentication mode local requires local users to be configured!"
            )

        for user in dict_search("authentication.local_users.username", config):
            user_config = config["authentication"]["local_users"]["username"][user]

            if "password" not in user_config:
                raise ConfigError(f'Password required for local user "{user}"')

            if "rate_limit" in user_config:
                # if up/download is set, check that both have a value
                if not {"upload", "download"} <= set(user_config["rate_limit"]):
                    raise ConfigError(
                        f'User "{user}" has rate-limit configured for only one '
                        "direction but both upload and download must be given!"
                    )

    elif dict_search("authentication.mode", config) == "radius":
        if not dict_search("authentication.radius.server", config):
            raise ConfigError("RADIUS authentication requires at least one server")

        for server in dict_search("authentication.radius.server", config):
            radius_config = config["authentication"]["radius"]["server"][server]
            if "key" not in radius_config:
                raise ConfigError(f'Missing RADIUS secret key for server "{server}"')

    if dict_search("server_type", config) == 'ipoe' and dict_search(
            "authentication.mode", config) == "local":
        if not dict_search("authentication.interface", config):
            raise ConfigError(
                "Authentication mode local requires authentication interface to be configured!"
            )
        for interface in dict_search("authentication.interface", config):
            user_config = config["authentication"]["interface"][interface]
            if "mac" not in user_config:
                raise ConfigError(
                    f'Users MAC addreses are not configured for interface "{interface}"')

    if dict_search('authentication.radius.dynamic_author.server', config):
        if not dict_search('authentication.radius.dynamic_author.key', config):
            raise ConfigError('DAE/CoA server key required!')


def verify_accel_ppp_ip_pool(vpn_config):
    """
    Common helper function which must be used by Accel-PPP
    services (pptp, l2tp, sstp, pppoe) to verify client-ip-pool
    and client-ipv6-pool
    """
    if dict_search("client_ip_pool", vpn_config):
        for pool_name, pool_config in vpn_config["client_ip_pool"].items():
            next_pool = dict_search(f"next_pool", pool_config)
            if next_pool:
                if next_pool not in vpn_config["client_ip_pool"]:
                    raise ConfigError(
                        f'Next pool "{next_pool}" does not exist')
                if not dict_search(f"range", pool_config):
                    raise ConfigError(
                        f'Pool "{pool_name}" does not contain range but next-pool exists'
                    )
    if not dict_search("gateway_address", vpn_config):
        Warning("IPv4 Server requires gateway-address to be configured!")

    default_pool = dict_search("default_pool", vpn_config)
    if default_pool:
        if not dict_search('client_ip_pool',
                           vpn_config) or default_pool not in dict_search(
                'client_ip_pool', vpn_config):
            raise ConfigError(f'Default pool "{default_pool}" does not exists')

    if 'client_ipv6_pool' in vpn_config:
        for ipv6_pool, ipv6_pool_config in vpn_config['client_ipv6_pool'].items():
            if 'delegate' in ipv6_pool_config and 'prefix' not in ipv6_pool_config:
                raise ConfigError(
                    f'IPv6 delegate-prefix requires IPv6 prefix to be configured in "{ipv6_pool}"!')

    if dict_search('authentication.mode', vpn_config) in ['local', 'noauth']:
        if not dict_search('client_ip_pool', vpn_config) and not dict_search(
                'client_ipv6_pool', vpn_config):
            if dict_search('server_type', vpn_config) == 'ipoe':
                if 'interface' in vpn_config:
                    for interface, interface_config in vpn_config['interface'].items():
                        if dict_search('client_subnet', interface_config):
                            break
                    else:
                        raise ConfigError(
                            'Local auth and noauth mode requires local client-ip-pool \
                             or client-ipv6-pool or client-subnet to be configured!')
            else:
                raise ConfigError(
                    "Local auth mode requires local client-ip-pool \
                    or client-ipv6-pool to be configured!")

        if dict_search('client_ip_pool', vpn_config) and not dict_search(
                'default_pool', vpn_config):
            Warning("'default-pool' is not defined")
        if dict_search('client_ipv6_pool', vpn_config) and not dict_search(
                'default_ipv6_pool', vpn_config):
            Warning("'default-ipv6-pool' is not defined")
