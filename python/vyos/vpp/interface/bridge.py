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


class BridgeInterface:
    def __init__(
        self,
        ifname: str,
        flood: bool = True,
        forward: bool = True,
        learn: bool = True,
        uu_flood: bool = True,
        arp_term: bool = False,
    ):
        self.ifname = ifname
        self.interface_suffix = int(self.ifname.replace('br', ''))
        self.flood = flood
        self.forward = forward
        self.learn = learn
        self.uu_flood = uu_flood
        self.arp_term = arp_term
        self.vpp = VPPControl()

    def add(self):
        """Create Bridge interface
        https://github.com/FDio/vpp/blob/stable/2306/src/vnet/l2/l2.api

        Bridge-domain 0 is reserved for the default bridge-domain.

        Example:
            from vyos.vpp.interface import BridgeInterface
            a = BridgeInterface(ifname='br23')
            a.add()
        """
        self.vpp.api.bridge_domain_add_del_v2(
            is_add=True,
            bd_id=self.interface_suffix,
            flood=self.flood,
            forward=self.forward,
            learn=self.learn,
            uu_flood=self.uu_flood,
            arp_term=self.arp_term,
        )

    def delete(self):
        """Delete Bridge interface

        Bridge-members must be detached before deleting the bridge interface.

        Example:
            from vyos.vpp.interface import BridgeInterface
            a = BridgeInterface(ifname='br23')
            a.delete()
        """
        self.vpp.api.bridge_domain_add_del_v2(is_add=False, bd_id=self.interface_suffix)

    def add_member(self, member: str | int, port_type: int = 0):
        """Add member to Bridge interface

        Attaches a VPP interface to the Bridge interface specified by `interface_suffix`.
        The `member` parameter can be either the name (str) or the index (int) of the network
        VPP interface to be added as a member to the bridge.

        Args:
            member (str or int): The name or index of the VPP network interface
                                 to be added as a member to the bridge.
            port_type: 0 - Normal port, 1 - BVI port

        Example:
            from vyos.vpp.interface import BridgeInterface
            a = BridgeInterface(ifname='br23')
            a.add_member(member='eth0')
        """
        bridge_index = self.interface_suffix
        # If the 'member' is an Integer or digit, assume it's an interface index
        if isinstance(member, int):
            member_if_index = member
        elif member.isdigit():
            member_if_index = int(member)
        else:
            member_if_index = self.vpp.get_sw_if_index(member)

        return self.vpp.api.sw_interface_set_l2_bridge(
            rx_sw_if_index=member_if_index, bd_id=bridge_index, port_type=port_type
        )

    def detach_member(self, member: str | int):
        """Detach member from Bridge interface.
        Bridge-domain 0 is reserved for the default bridge-domain.
        The `member` parameter can be either the name (str) or the index (int)
        of the network VPP interface

        Args:
            member (str or int): The name or index of the VPP network interface
                                 to be detached from the bridge.

        Example:
            from vyos.vpp.interface import BridgeInterface
            a = BridgeInterface(ifname='br23')
            a.detach_member(member='eth0')
        """
        # If the 'member' is an Integer or digit, assume it's an interface index
        if isinstance(member, int):
            member_if_index = member
        elif member.isdigit():
            member_if_index = int(member)
        else:
            member_if_index = self.vpp.get_sw_if_index(member)

        return self.vpp.api.sw_interface_set_l2_bridge(
            rx_sw_if_index=member_if_index, bd_id=0, port_type=0
        )
