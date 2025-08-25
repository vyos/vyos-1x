# VyOS implementation of VPP VXLAN interface
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
from vyos.vpp.interface.interface import Interface


def show():
    """Show VXLAN interface
    Example:
      from vyos.vpp.interface import vxlan
      vxlan.show()
    """
    vpp = VPPControl()
    return vpp.api.vxlan_tunnel_dump()


class VXLANInterface(Interface):
    """Interface VXLAN"""

    def __init__(
        self,
        ifname,
        source_address,
        remote,
        vni,
        kernel_interface: str = '',
        state: str = 'up',
    ):
        super().__init__(ifname)
        self.instance = int(ifname.removeprefix('vxlan'))
        self.ifname = f'vxlan_tunnel{self.instance}'
        self.src_address = source_address
        self.dst_address = remote
        self.vni = vni
        self.kernel_interface = kernel_interface
        self.initial_state = state

    def add(self):
        """Create VXLAN interface
        https://github.com/FDio/vpp/blob/stable/2306/src/plugins/vxlan/vxlan.api

        Example:
            from vyos.vpp.interface import VXLANInterface
            a = VXLANInterface(ifname='vxlan23', source_address='192.0.2.1', remote='203.0.113.23', vni=23)
            a.add()
        """
        self.vpp.api.vxlan_add_del_tunnel_v3(
            is_add=True,
            src_address=self.src_address,
            dst_address=self.dst_address,
            vni=self.vni,
            instance=self.instance,
            decap_next_index=1,
            is_l3=False,
        )
        # Set interface state
        self.set_state(self.initial_state)

    def delete(self):
        """Delete VXLAN interface
        Example:
            from vyos.vpp.interface import VXLANInterface
            a = VXLANInterface(ifname='vxlan23', source_address='192.0.2.1', remote='203.0.113.23', vni=23)
            a.delete()
        """
        return self.vpp.api.vxlan_add_del_tunnel_v3(
            is_add=False,
            src_address=self.src_address,
            dst_address=self.dst_address,
            vni=self.vni,
            is_l3=False,
        )

    def kernel_add(self):
        """Add LCP pair
        Example:
            from vyos.vpp.interface import VXLANInterface
            a = VXLANInterface(ifname='vxlan23', source_address='192.0.2.1', remote='203.0.113.23', vni=23, kernel_interface='vpptap10')
            a.kernel_add()
        """
        self.vpp.lcp_pair_add(self.ifname, self.kernel_interface)

    def kernel_delete(self):
        """Delete LCP pair
        Example:
            from vyos.vpp.interface import VXLANInterface
            a = VXLANInterface(ifname='vxlan23', source_address='192.0.2.1', remote='203.0.113.23', vni=23)
            a.kernel_delete()
        """
        self.vpp.lcp_pair_del(self.ifname, self.kernel_interface)
