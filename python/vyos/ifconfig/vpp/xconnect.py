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

from vyos.ifconfig.vpp.interface import VPPInterface
from vyos.vpp.utils import iftunnel_transform


def _transform_members(members):
    """
    Transform interface names to VPP names for xconnect operations.

    Args:
        members (list of str): List of two interface names.

    Returns:
        tuple: Transformed first and second interface names.
    """
    interface_transform_filter = ('vxlan',)
    first_member = members[0].removeprefix('vpp')
    second_member = members[1].removeprefix('vpp')

    # Check if member in required filter to transform 'vxlanX' => 'vxlan_tunnelX'
    if first_member.startswith(interface_transform_filter):
        first_member = iftunnel_transform(first_member)
    if second_member.startswith(interface_transform_filter):
        second_member = iftunnel_transform(second_member)

    return first_member, second_member


class VPPXconnectInterface(VPPInterface):
    def __init__(self, ifname):
        self.vpp_ifname = ifname

        super().__init__(self.vpp_ifname)

    def add_l2_xconnect(self, first, second):
        """Add l2 cross connect
        Example:
            from vyos.ifconfig.vpp import VPPXconnectInterface
            a = VPPXconnectInterface(ifname='vppxcon0')
            a.add_l2_xconnect(first, second)
        """
        member_first_if_index = self.vpp.get_sw_if_index(first)
        member_second_if_index = self.vpp.get_sw_if_index(second)
        self.vpp.api.sw_interface_set_l2_xconnect(
            rx_sw_if_index=member_first_if_index,
            tx_sw_if_index=member_second_if_index,
            enable=True,
        )
        self.vpp.api.sw_interface_set_l2_xconnect(
            rx_sw_if_index=member_second_if_index,
            tx_sw_if_index=member_first_if_index,
            enable=True,
        )

    def del_l2_xconnect(self, first, second):
        """Move l2 cross connect member to mode l3 (delete xconnect)
        Example:
            from vyos.ifconfig.vpp import VPPXconnectInterface
            a = VPPXconnectInterface(ifname='vppxcon0')
            a.del_l2_xconnect(first, second)
        """
        member_first_if_index = self.vpp.get_sw_if_index(first)
        member_second_if_index = self.vpp.get_sw_if_index(second)
        self.vpp.api.sw_interface_set_l2_xconnect(
            rx_sw_if_index=member_first_if_index,
            tx_sw_if_index=member_second_if_index,
            enable=False,
        )
        self.vpp.api.sw_interface_set_l2_xconnect(
            rx_sw_if_index=member_second_if_index,
            tx_sw_if_index=member_first_if_index,
            enable=False,
        )

    def remove(self, members):
        first, second = _transform_members(members)
        self.del_l2_xconnect(first, second)

    def update(self, config):
        members = config['member']['interface']
        first, second = _transform_members(members)
        self.add_l2_xconnect(first, second)
