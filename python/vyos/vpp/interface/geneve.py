# VyOS implementation of Geneve interface
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


def show():
    """Show Geneve interface
    Example:
      from vyos.vpp.interface import geneve
      geneve.show()
    """
    vpp = VPPControl()
    return vpp.api.geneve_tunnel_dump()


class GeneveInterface:
    def __init__(self, ifname, source_address, remote, vni, kernel_interface: str = ''):
        self.instance = int(ifname.removeprefix('geneve'))
        self.ifname = f'geneve_tunnel{self.instance}'
        self.src_address = source_address
        self.dst_address = remote
        self.vni = vni
        self.kernel_interface = kernel_interface
        self.vpp = VPPControl()

    def add(self):
        """Create Geneve interface
        https://github.com/FDio/vpp/blob/stable/2306/src/plugins/geneve/geneve.api

        Example:
            from vyos.vpp.interface import GeneveInterface
            a = GeneveInterface(ifname='geneve25', source_address='192.0.2.1', remote='203.0.113.25', vni=25)
            a.add()
        """
        return self.vpp.api.geneve_add_del_tunnel2(
            is_add=True,
            local_address=self.src_address,
            remote_address=self.dst_address,
            vni=self.vni,
            l3_mode=False,
        )

    def delete(self):
        """Delete Geneve interface
        Example:
            from vyos.vpp.interface import GeneveInterface
            a = GeneveInterface(ifname='vxlan25', source_address='192.0.2.1', remote='203.0.113.25', vni=25)
            a.delete()
        """
        return self.vpp.api.geneve_add_del_tunnel2(
            is_add=False,
            local_address=self.src_address,
            remote_address=self.dst_address,
            vni=self.vni,
            l3_mode=False,
        )

    def kernel_add(self):
        """Add LCP pair
        Example:
            from vyos.vpp.interface import GeneveInterface
            a = GeneveInterface(ifname='vxlan25', source_address='192.0.2.1', remote='203.0.113.25', vni=25)
            a.kernel_add()
        """
        self.vpp.lcp_pair_add(self.ifname, self.kernel_interface, 'tun')

    def kernel_delete(self):
        """Delete LCP pair
        Example:
            from vyos.vpp.interface import GeneveInterface
            a = GeneveInterface(ifname='vxlan25', source_address='192.0.2.1', remote='203.0.113.25', vni=25)
            a.kernel_delete()
        """
        self.vpp.lcp_pair_del(self.ifname, self.kernel_interface)
