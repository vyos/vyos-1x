# VyOS implementation of VPP GRE interface
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


class VPPGREInterface(Interface, VPPInterface):
    """
    Class representing a GRE (Generic Routing Encapsulation) interface.
    """

    # Mapping of tunnel types https://github.com/FDio/vpp/blob/stable/2406/src/plugins/gre/gre.api#L25-L35
    TUNNEL_TYPE_MAP = {
        'l3': 0,
        'teb': 1,
        'erspan': 2,
    }

    MODE_MAP = {
        'point-to-point': 0,
        # 'point-to-multipoint': 1,
    }

    def __init__(self, ifname, config):
        self.ifname = ifname
        self.instance = int(ifname.removeprefix('vppgre'))
        self.vpp_ifname = f'gre{self.instance}'

        # Initialize Interface (kernel) and VPP part
        super().__init__(ifname)
        VPPInterface.__init__(self, self.vpp_ifname)

        self.index = self.vpp.get_sw_if_index(self.vpp_ifname)
        self.state = 'up' if 'disable' not in config else 'down'
        self.src_address = config.get('source_address')
        self.dst_address = config.get('remote')
        self.tunnel_type = self.TUNNEL_TYPE_MAP.get(config.get('tunnel_type'), 0)
        self.mode = self.MODE_MAP['point-to-point']
        self.key = int(config.get('key', 0))

    def _create(self):
        pass

    def get_gre(self):
        tunnels = self.vpp.api.gre_tunnel_dump_v2(sw_if_index=self.index)
        return tunnels if tunnels else None

    def add_gre(self):
        """Create GRE interface
        https://github.com/FDio/vpp/blob/stable/2406/src/plugins/gre/gre.api
        Example:
            from vyos.ifconfig.vpp import VPPGREInterface
            a = VPPGREInterface(ifname='vppgre0', config)
            a.add_gre()
        """
        self.vpp.api.gre_tunnel_add_del_v2(
            is_add=True,
            tunnel={
                'src': self.src_address,
                'dst': self.dst_address,
                'instance': self.instance,
                'mode': self.mode,
                'type': self.tunnel_type,
                'key': self.key,
            },
        )
        # Add LCP pair (kernel) interface
        self.kernel_add()
        # Set interface state
        self.set_state(self.state)
        self.set_admin_state(self.state)
        self.index = self.vpp.get_sw_if_index(self.vpp_ifname)

    def delete_gre(self):
        """Delete GRE interface
        Example:
            from vyos.ifconfig.vpp import VPPGREInterface
            a = VPPGREInterface(ifname='vppgre0', config)
            a.delete_gre()
        """
        gre = self.get_gre()
        if gre:
            return self.vpp.api.gre_tunnel_add_del_v2(
                is_add=False,
                tunnel={
                    'src': gre.tunnel.src,
                    'dst': gre.tunnel.dst,
                    'key': gre.tunnel.key,
                },
            )

    def kernel_add(self):
        """Add LCP pair
        Example:
            from vyos.ifconfig.vpp import VPPGREInterface
            a = VPPGREInterface(ifname='vppgre0', config)
            a.kernel_add()
        """
        self.vpp.lcp_pair_add(self.vpp_ifname, self.ifname, 'tun')

    def kernel_delete(self):
        """Delete LCP pair
        Example:
            from vyos.ifconfig.vpp import VPPGREInterface
            a = VPPGREInterface(ifname='vppgre0', config)
            a.kernel_delete()
        """
        self.vpp.lcp_pair_del(self.vpp_ifname, self.ifname)

    def remove(self):
        if self.index:
            # Delete lcp pair interface
            if self.vpp.lcp_pair_find(vpp_name_hw=self.vpp_ifname):
                self.kernel_delete()

            # Delete gre interface
            self.delete_gre()

    def update(self, config):
        # Add gre interface
        self.add_gre()

        # Apply VPP-specific interface settings
        VPPInterface.update(self, config)

        super().update(config)
