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


def deps_xconnect_dict(conf) -> dict[str, list[str]]:
    """Get a dict of all xconnect interface members:

        keys: members

        values: xconnect interfaces

    Args:
        conf (config): VyOS config object

    Returns:
        dict[str, list[str]]: dict of members
    """
    xconn_members_dict: dict[str, list[str]] = {}
    config = conf.get_config_dict(
        ['vpp', 'interfaces', 'xconnect'],
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
    )

    for xconn_name, xconn_config in config.items():
        for member_name in xconn_config.get('member', {}).get('interface', []):
            xconn_ifaces_list = xconn_members_dict.get(xconn_name, [])
            xconn_ifaces_list.append(xconn_name)
            xconn_members_dict.update({member_name: xconn_ifaces_list})

    return xconn_members_dict


def deps_bridge_dict(conf) -> dict[str, list[str]]:
    """Get a dict of all bridge interface members:

        keys: members

        values: bridge interfaces

    Args:
        conf (config): VyOS config object

    Returns:
        dict[str, list[str]]: dict of members
    """
    bridge_members_dict: dict[str, list[str]] = {}
    config = conf.get_config_dict(
        ['vpp', 'interfaces', 'bridge'],
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
    )

    for bridge_name, bridge_config in config.items():
        for member_name in bridge_config.get('member', {}).get('interface', []):
            bridge_ifaces_list = bridge_members_dict.get(bridge_name, [])
            bridge_ifaces_list.append(bridge_name)
            bridge_members_dict.update({member_name: bridge_ifaces_list})

    return bridge_members_dict
