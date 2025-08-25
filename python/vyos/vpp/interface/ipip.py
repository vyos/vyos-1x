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

from vyos.vpp import VPPControl
from vyos.vpp.interface.interface import Interface


def show():
    """Show IPIP interface
    Example:
      from vyos.vpp.interface import ipip
      ipip.show()
    """
    vpp = VPPControl()
    return vpp.api.ipip_tunnel_dump()


class IPIPInterface(Interface):
    def __init__(
        self,
        ifname,
        source_address,
        remote,
        kernel_interface: str = '',
        state: str = 'up',
    ):
        super().__init__(ifname)
        self.instance = int(ifname.removeprefix('ipip'))
        self.ifname = ifname
        self.src_address = source_address
        self.dst_address = remote
        self.kernel_interface = kernel_interface
        self.initial_state = state

    def add(self):
        """Create IPIP interface
        https://github.com/FDio/vpp/blob/stable/2310/src/vnet/ipip/ipip.api
        Example:
            from vyos.vpp.interface import IPIPInterface
            a = IPIPInterface(ifname='ipip0', source_address='192.0.2.1', remote='192.0.2.5')
            a.add()
        """
        self.vpp.api.ipip_add_tunnel(
            tunnel={
                'src': self.src_address,
                'dst': self.dst_address,
                'instance': self.instance,
            },
        )
        # Set interface state
        self.set_state(self.initial_state)

    def delete(self):
        """Delete IPIP interface
        Example:
            from vyos.vpp.interface import IPIPInterface
            a = IPIPInterface(ifname='ipip0', source_address='192.0.2.1', remote='192.0.2.5')
            a.delete()
        """
        ipip_if_index = self.vpp.get_sw_if_index(f'ipip{self.instance}')
        return self.vpp.api.ipip_del_tunnel(sw_if_index=ipip_if_index)

    def kernel_add(self):
        """Add LCP pair
        Example:
            from vyos.vpp.interface import IPIPInterface
            a = IPIPInterface(ifname='ipip0', source_address='192.0.2.1', remote='192.0.2.5')
            a.kernel_add()
        """
        self.vpp.lcp_pair_add(self.ifname, self.kernel_interface, 'tun')

    def kernel_delete(self):
        """Delete LCP pair
        Example:
            from vyos.vpp.interface import IPIPInterface
            a = IPIPInterface(ifname='ipip0', source_address='192.0.2.1', remote='192.0.2.5')
            a.kernel_delete()
        """
        self.vpp.lcp_pair_del(self.ifname, self.kernel_interface)
