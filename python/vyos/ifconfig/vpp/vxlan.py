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

from vyos.ifconfig import Interface
from vyos.ifconfig.vpp.interface import VPPInterface


class VPPVXLANInterface(Interface, VPPInterface):
    """Interface VXLAN"""

    def __init__(self, ifname, config):
        self.ifname = ifname
        self.instance = int(ifname.removeprefix('vppvxlan'))
        self.vpp_ifname = f'vxlan_tunnel{self.instance}'

        super().__init__(ifname)
        VPPInterface.__init__(self, self.vpp_ifname)

        self.index = self.vpp.get_sw_if_index(self.vpp_ifname)
        self.src_address = config.get('source_address')
        self.dst_address = config.get('remote')
        self.vni = int(config.get('vni', 0))
        self.state = 'up' if 'disable' not in config else 'down'

    def _create(self):
        pass

    def get_vxlan(self):
        tunnels = self.vpp.api.vxlan_tunnel_dump(sw_if_index=self.index)
        return tunnels[0] if tunnels else None

    def add_vxlan(self):
        """Create VXLAN interface
        https://github.com/FDio/vpp/blob/stable/2306/src/plugins/vxlan/vxlan.api

        Example:
            from vyos.ifconfig.vpp import VPPVXLANInterface
            a = VPPVXLANInterface(ifname='vppvxlan23', config)
            a.add_vxlan()
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
        # Add LCP pair (kernel) interface
        self.kernel_add()
        # Set interface state
        self.set_state(self.state)
        self.set_admin_state(self.state)
        self.index = self.vpp.get_sw_if_index(self.vpp_ifname)

    def delete_vxlan(self):
        """Delete VXLAN interface
        Example:
            from vyos.ifconfig.vpp import VPPVXLANInterface
            a = VPPVXLANInterface(ifname='vppvxlan23', config)
            a.delete_vxlan()
        """
        vxlan = self.get_vxlan()
        if vxlan:
            return self.vpp.api.vxlan_add_del_tunnel_v3(
                is_add=False,
                src_address=vxlan.src_address,
                dst_address=vxlan.dst_address,
                vni=vxlan.vni,
                is_l3=False,
            )

    def kernel_add(self):
        """Add LCP pair
        Example:
            from vyos.ifconfig.vpp import VPPVXLANInterface
            a = VPPVXLANInterface(ifname='vppvxlan23', config)
            a.kernel_add()
        """
        self.vpp.lcp_pair_add(self.vpp_ifname, self.ifname)

    def kernel_delete(self):
        """Delete LCP pair
        Example:
            from vyos.ifconfig.vpp import VPPVXLANInterface
            a = VPPVXLANInterface(ifname='vppvxlan23', config)
            a.kernel_delete()
        """
        self.vpp.lcp_pair_del(self.vpp_ifname, self.ifname)

    def remove(self):
        if self.index:
            # Delete lcp pair interface
            if self.vpp.lcp_pair_find(vpp_name_hw=self.vpp_ifname):
                self.kernel_delete()

            # Delete vxlan interface
            self.delete_vxlan()

    def update(self, config):
        # Add vxlan interface
        self.add_vxlan()

        VPPInterface.update(self, config)

        super().update(config)
