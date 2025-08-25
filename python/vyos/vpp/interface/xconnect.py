# VyOS implementation of VPP bridge interface
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

from vyos.vpp import VPPControl
from vyos.vpp.utils import iftunnel_transform


class XconnectInterface:
    def __init__(
        self,
        ifname: str,
        members: list = [],
        state: str = 'up',
    ):
        self.ifname = ifname
        self.members = members
        self.vpp = VPPControl()
        self.initial_state = state

    def add_l2_xconnect(self):
        """Add l2 cross connect
        Args:
            members (list): The list of the xconnect members
        Example:
            from vyos.vpp.interface import XconnectInterface
            a = XconnectInterface(ifname='xcon0', members=['eth0', 'vxlan0'])
            a.add_l2_xconnect()
        """
        interface_transform_filter = ('vxlan', 'gre')
        first_member = self.members[0]
        second_member = self.members[1]
        # Check if member in required filter to transform 'vxlanX' => 'vxlan_tunnelX'
        if first_member.startswith(interface_transform_filter):
            first_member = iftunnel_transform(first_member)
        if second_member.startswith(interface_transform_filter):
            second_member = iftunnel_transform(second_member)

        member_first_if_index = self.vpp.get_sw_if_index(first_member)
        member_second_if_index = self.vpp.get_sw_if_index(second_member)
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

    def del_l2_xconnect(self):
        """Move l2 cross connect member to mode l3 (delte xconnect)
        Args:
            members (list): The list of the xconnect members
        Example:
            from vyos.vpp.interface import XconnectInterface
            a = XconnectInterface(ifname='xcon0', members=['eth0', 'vxlan0'])
            a.del_l2_xconnect()
        """
        interface_transform_filter = ('vxlan', 'gre')
        first_member = self.members[0]
        second_member = self.members[1]
        # Check if member in required filter to transform 'vxlanX' => 'vxlan_tunnelX'
        if first_member.startswith(interface_transform_filter):
            first_member = iftunnel_transform(first_member)
        if second_member.startswith(interface_transform_filter):
            second_member = iftunnel_transform(second_member)

        member_first_if_index = self.vpp.get_sw_if_index(first_member)
        member_second_if_index = self.vpp.get_sw_if_index(second_member)
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
