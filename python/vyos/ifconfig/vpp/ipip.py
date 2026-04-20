# VyOS implementation of VPP IPIP interface
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


class VPPIPIPInterface(Interface, VPPInterface):
    def __init__(self, ifname, config):
        self.ifname = ifname
        self.instance = int(ifname.removeprefix('vppipip'))
        self.vpp_ifname = self.ifname.removeprefix('vpp')

        # Initialize Interface (kernel) and VPP part
        super().__init__(ifname)
        VPPInterface.__init__(self, self.vpp_ifname)

        self.index = self.vpp.get_sw_if_index(self.vpp_ifname)
        self.src_address = config.get('source_address')
        self.dst_address = config.get('remote')
        self.state = 'up' if 'disable' not in config else 'down'

    def _create(self):
        pass

    def add_ipip(self):
        """Create IPIP interface
        https://github.com/FDio/vpp/blob/stable/2310/src/vnet/ipip/ipip.api
        Example:
            from vyos.ifconfig.vpp import VPPIPIPInterface
            a = VPPIPIPInterface(ifname='vppipip0', config)
            a.add_ipip()
        """
        self.vpp.api.ipip_add_tunnel(
            tunnel={
                'src': self.src_address,
                'dst': self.dst_address,
                'instance': self.instance,
            },
        )
        # Add LCP pair (kernel) interface
        self.kernel_add()
        # Set interface state
        self.set_state(self.state)
        self.set_admin_state(self.state)
        self.index = self.vpp.get_sw_if_index(self.vpp_ifname)

    def delete_ipip(self):
        """Delete IPIP interface
        Example:
            from vyos.ifconfig.vpp import VPPIPIPInterface
            a = VPPIPIPInterface(ifname='vppipip0', config)
            a.delete_ipip()
        """
        return self.vpp.api.ipip_del_tunnel(sw_if_index=self.index)

    def kernel_add(self):
        """Add LCP pair
        Example:
            from vyos.ifconfig.vpp import VPPIPIPInterface
            a = VPPIPIPInterface(ifname='vppipip0', config)
            a.kernel_add()
        """
        self.vpp.lcp_pair_add(self.vpp_ifname, self.ifname, 'tun')

    def kernel_delete(self):
        """Delete LCP pair
        Example:
            from vyos.ifconfig.vpp import VPPIPIPInterface
            a = VPPIPIPInterface(ifname='vppipip0', config)
            a.kernel_delete()
        """
        self.vpp.lcp_pair_del(self.vpp_ifname, self.ifname)

    def remove(self):
        if self.index:
            # Delete lcp pair interface
            if self.vpp.lcp_pair_find(vpp_name_hw=self.vpp_ifname):
                self.kernel_delete()

            # Delete ipip interface
            self.delete_ipip()

    def update(self, config):
        # Add ipip interface
        self.add_ipip()

        # Apply VPP-specific interface settings
        VPPInterface.update(self, config)

        # Apply all settings to the lcp pair (kernel) interface
        super().update(config)
