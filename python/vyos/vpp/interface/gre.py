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

from vyos.vpp import VPPControl
from vyos.vpp.interface.interface import Interface


def show():
    """Show GRE interface
    Example:
      from vyos.vpp.interface import gre
      gre.show()
    """
    vpp = VPPControl()
    return vpp.api.gre_tunnel_dump()


class GREInterface(Interface):
    """
    Class representing a GRE (Generic Routing Encapsulation) interface.

    Attributes:
        ifname (str): The interface name.
        source_address (str): The source IP address for the GRE tunnel.
        remote (str): The remote IP address for the GRE tunnel.
        tunnel_type (str): The type of GRE tunnel. Defaults to 'l3'.
        mode (str): The mode of the GRE tunnel. Options are 'point-to-point' and 'point-to-multipoint'. Defaults to 'point-to-point'.
        kernel_interface (str): The associated kernel interface. Defaults to an empty string.
        instance (int): The instance number derived from the interface name.
        vpp (VPPControl): An instance of the VPPControl class for interacting with the VPP API.
    """

    # Mapping of tunnel types https://github.com/FDio/vpp/blob/stable/2406/src/plugins/gre/gre.api#L25-L35
    TUNNEL_TYPE_MAP = {
        'l3': 0,
        'teb': 1,
        'erspan': 2,
    }

    MODE_MAP = {
        'point-to-point': 0,
        'point-to-multipoint': 1,
    }

    def __init__(
        self,
        ifname,
        source_address,
        remote,
        tunnel_type: str = 'l3',
        mode: str = 'point-to-point',
        kernel_interface: str = '',
        state: str = 'up',
    ):
        """
        Initialize a GREInterface instance.

        Args:
            ifname (str): The interface name.
            source_address (str): The source IP address for the GRE tunnel.
            remote (str): The remote IP address for the GRE tunnel.
            mode (str): The mode of the GRE tunnel. Options are 'point-to-point' and 'point-to-multipoint'. Defaults to 'point-to-point'.
            tunnel_type (str): The type of GRE tunnel. Defaults to 'l3'.
            kernel_interface (str): The associated kernel interface. Defaults to an empty string.
            state (str): The state of the interface. Defaults to 'up'.
        """
        super().__init__(ifname)
        self.instance = int(ifname.removeprefix('gre'))
        self.ifname = ifname
        self.src_address = source_address
        self.dst_address = remote
        self.tunnel_type = self.TUNNEL_TYPE_MAP[tunnel_type]
        self.mode = self.MODE_MAP[mode]
        self.kernel_interface = kernel_interface
        self.initial_state = state

    def add(self):
        """Create GRE interface
        https://github.com/FDio/vpp/blob/stable/2406/src/plugins/gre/gre.api
        Example:
            from vyos.vpp.interface import GREInterface
            a = GREInterface(ifname='gre0', source_address='192.0.2.1', remote='203.0.113.25', tunnel_type='l3')
            a.add()
        """
        self.vpp.api.gre_tunnel_add_del(
            is_add=True,
            tunnel={
                'src': self.src_address,
                'dst': self.dst_address,
                'instance': self.instance,
                'mode': self.mode,
                'type': self.tunnel_type,
            },
        )
        # Set interface state
        self.set_state(self.initial_state)

    def delete(self):
        """Delete GRE interface
        Example:
            from vyos.vpp.interface import GREInterface
            a = GREInterface(ifname='gre0', source_address='192.0.2.1', remote='203.0.113.25')
            a.delete()
        """
        return self.vpp.api.gre_tunnel_add_del(
            is_add=False, tunnel={'src': self.src_address, 'dst': self.dst_address}
        )

    def kernel_add(self):
        """Add LCP pair
        Example:
            from vyos.vpp.interface import GREInterface
            a = GREInterface(ifname='gre0', source_address='192.0.2.1', remote='203.0.113.25')
            a.kernel_add()
        """
        self.vpp.lcp_pair_add(self.ifname, self.kernel_interface, 'tun')

    def kernel_delete(self):
        """Delete LCP pair
        Example:
            from vyos.vpp.interface import GREInterface
            a = GREInterface(ifname='gre0', source_address='192.0.2.1', remote='203.0.113.25')
            a.kernel_delete()
        """
        self.vpp.lcp_pair_del(self.ifname, self.kernel_interface)
