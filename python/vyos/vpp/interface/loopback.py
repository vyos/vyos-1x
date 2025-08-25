# VyOS implementation of VPP Loopback interface
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

from vyos.vpp.interface.interface import Interface


class LoopbackInterface(Interface):
    """Interface Loopback"""

    def __init__(self, ifname, kernel_interface: str = '', state: str = 'up'):
        super().__init__(ifname)
        self.instance = int(ifname.removeprefix('lo'))
        self.ifname = f'loop{self.instance}'
        self.kernel_interface = kernel_interface
        self.initial_state = state

    def add(self):
        """Create Loopback interface
        https://github.com/FDio/vpp/blob/stable/2306/src/vnet/interface.api
        Example:
            from vyos.vpp.interface import LoopbackInterface
            a = LoopbackInterface(ifname='lo1')
            a.add()
        """
        self.vpp.api.create_loopback_instance(
            is_specified=True, user_instance=self.instance
        )
        # Set interface state
        self.set_state(self.initial_state)

    def delete(self):
        """Delete Loopback interface
        Example:
            from vyos.vpp.interface import LoopbackInterface
            a = LoopbackInterface(ifname='lo1')
            a.delete()
        """
        loopback_if_index = self.vpp.get_sw_if_index(f'loop{self.instance}')
        return self.vpp.api.delete_loopback(sw_if_index=loopback_if_index)

    def kernel_add(self):
        """Add LCP pair
        Example:
            from vyos.vpp.interface import LoopbackInterface
            a = LoopbackInterface(ifname='lo1')
            a.kernel_add()
        """
        self.vpp.lcp_pair_add(self.ifname, self.kernel_interface)

    def kernel_delete(self):
        """Delete LCP pair
        Example:
            from vyos.vpp.interface import LoopbackInterface
            a = LoopbackInterface(ifname='lo1')
            a.kernel_delete()
        """
        self.vpp.lcp_pair_del(self.ifname, self.kernel_interface)
