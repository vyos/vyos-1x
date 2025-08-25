#
# Copyright (C) VyOS Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

from vyos.config import Config


def iface_filter_eth(config: Config, iface: str) -> None:
    """Filter out unsupported config nodes from Ethernet interface config

    Args:
        config (Config): config object
        iface (str): Ethernet interface name to filter
    """
    allowed_nodes: list[str] = [
        'address',
        'description',
        'dhcp-options',
        'dhcpv6-options',
        'disable',
        'eapol',
        'hw-id',
        'ip',
        'ipv6',
        'mtu',
        'redirect',
        'vif',
        'vif-s',
        'vrf',
    ]

    # get list of config nides in a session configuration
    iface_nodes = config._session_config.list_nodes(['interfaces', 'ethernet', iface])

    # clean cached session config
    if False in config._dict_cache:
        del config._dict_cache[False]

    # remove unsupported config nodes
    for cfg_node in iface_nodes:
        if cfg_node not in allowed_nodes:
            config._session_config.delete(['interfaces', 'ethernet', iface, cfg_node])
            print(
                f'WARNING: {cfg_node} option in {iface} settings is not supported by VPP interfaces. It will be ignored.'
            )
