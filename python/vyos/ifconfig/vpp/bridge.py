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
from vyos.utils.dict import dict_search
from vyos.vpp.utils import iftunnel_transform


class VPPBridgeInterface(VPPInterface):
    def __init__(self, ifname):
        self.instance = int(ifname.removeprefix('vppbr'))
        self.vpp_ifname = f'br{self.instance}'

        super().__init__(self.vpp_ifname)

    def add(self):
        """Create Bridge interface
        https://github.com/FDio/vpp/blob/stable/2306/src/vnet/l2/l2.api

        Bridge-domain 0 is reserved for the default bridge-domain.

        Example:
            from vyos.ifconfig.vpp import VPPBridgeInterface
            a = VPPBridgeInterface(ifname='br23')
            a.add()
        """
        self.vpp.api.bridge_domain_add_del_v2(
            is_add=True,
            bd_id=self.instance,
            flood=True,
            forward=True,
            learn=True,
            uu_flood=True,
            arp_term=False,
        )

    def delete(self):
        """Delete Bridge interface

        Bridge-members must be detached before deleting the bridge interface.

        Example:
            from vyos.ifconfig.vpp import VPPBridgeInterface
            a = VPPBridgeInterface(ifname='br23')
            a.delete()
        """
        self.vpp.api.bridge_domain_add_del_v2(is_add=False, bd_id=self.instance)

    def get_members(self):
        bridge = self.vpp.api.bridge_domain_dump(bd_id=self.instance)[0]
        members = []
        for member in bridge.sw_if_details:
            members.append(member.sw_if_index)
        return members

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
            from vyos.ifconfig.vpp import VPPBridgeInterface
            a = VPPBridgeInterface(ifname='br23')
            a.add_member(member='eth0')
        """
        member_if_index = self.vpp.get_sw_if_index(member)
        return self.vpp.api.sw_interface_set_l2_bridge(
            rx_sw_if_index=member_if_index, bd_id=self.instance, port_type=port_type
        )

    def detach_member(self, member: int):
        """Detach member from Bridge interface.
        Bridge-domain 0 is reserved for the default bridge-domain.
        The `member` parameter can be either the name (str) or the index (int)
        of the network VPP interface

        Args:
            member (str or int): The name or index of the VPP network interface
                                 to be detached from the bridge.

        Example:
            from vyos.ifconfig.vpp import VPPBridgeInterface
            a = VPPBridgeInterface(ifname='br23')
            a.detach_member(member='eth0')
        """
        # enable=0, 0 = Enable L3 mode
        return self.vpp.api.sw_interface_set_l2_bridge(
            rx_sw_if_index=member, bd_id=0, port_type=0, enable=0
        )

    def remove(self):
        if self.vpp.api.bridge_domain_dump(bd_id=self.instance):
            # Detach all existing members
            members = self.get_members()
            for member in members:
                self.detach_member(member=member)

            # Delete bridge interface
            self.delete()

    def update(self, config):
        # Add bridge interface
        self.add()

        # Add members to bridge
        for member, member_config in dict_search(
            'member.interface', config, {}
        ).items():
            member = member.removeprefix('vpp')
            if member.startswith('vxlan'):
                member = iftunnel_transform(member)
            elif member.startswith('lo'):
                # interface name in VPP is loopX
                member = member.replace('lo', 'loop')
            elif member.startswith('bond'):
                # interface name in VPP is BondEthernetX
                member = member.replace('bond', 'BondEthernet')
            port = 1 if 'bvi' in member_config else 0
            self.add_member(member=member, port_type=port)
