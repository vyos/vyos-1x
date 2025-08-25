# VyOS implementation of VPP Wireguard interface
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


class WireguardInterface:
    """Interface Wireguard"""

    def __init__(self, ifname, listen_port=51820, kernel_interface: str = ''):
        self.instance = int(ifname.removeprefix('wg'))
        self.ifname = ifname
        self.listen_port = listen_port
        self.kernel_interface = kernel_interface
        self.vpp = VPPControl()

    def add(self):
        """Create Wireguard interface
        https://github.com/FDio/vpp/blob/stable/2306/src/plugins/wireguard/wireguard.api
        Example:
            from vyos.vpp.interface import WireguardInterface
            a = WireguardInterface(ifname='wg5', listen_port=51820, generate_key=True)
            a.add()
        """
        self.vpp.api.wireguard_interface_create(
            generate_key=True,
            interface={'user_instance': self.instance, 'listen_port': self.listen_port},
        )
        if self.kernel_interface:
            self.vpp.lcp_pair_add(self.ifname, self.kernel_interface, 'tun')

    def delete(self):
        """Delete Wireguard interface
        Example:
            from vyos.vpp.interface import WireguardInterface
            a = WireguardInterface(ifname='wg5')
            a.delete()
        """
        wg_if_index = self.vpp.get_sw_if_index(f'wg{self.instance}')
        return self.vpp.api.wireguard_interface_delete(sw_if_index=wg_if_index)
