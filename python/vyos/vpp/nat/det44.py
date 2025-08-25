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


class Det44:
    def __init__(self):
        self.vpp = VPPControl()

    def enable_det44_plugin(self):
        """Enable DET44 plugin
        Example:
            from vyos.vpp.nat import Det44
            det44 = Det44()
            det44.enable_det44_plugin()
        https://github.com/FDio/vpp/blob/stable/2410/src/plugins/nat/det44/det44.api
        """
        self.vpp.api.det44_plugin_enable_disable(enable=True)

    def disable_det44_plugin(self):
        """Disable DET44 plugin"""
        self.vpp.api.det44_plugin_enable_disable(enable=False)

    def add_det44_interface_outside(self, interface_out):
        """Add DET44 outside interface"""
        self.vpp.api.det44_interface_add_del_feature(
            sw_if_index=self.vpp.get_sw_if_index(interface_out),
            is_inside=False,
            is_add=True,
        )

    def delete_det44_interface_outside(self, interface_out):
        """Delete DET44 outside interface"""
        self.vpp.api.det44_interface_add_del_feature(
            sw_if_index=self.vpp.get_sw_if_index(interface_out),
            is_inside=False,
            is_add=False,
        )

    def add_det44_interface_inside(self, interface_in):
        """Add DET44 inside interface"""
        self.vpp.api.det44_interface_add_del_feature(
            sw_if_index=self.vpp.get_sw_if_index(interface_in),
            is_inside=True,
            is_add=True,
        )

    def delete_det44_interface_inside(self, interface_in):
        """Delete DET44 inside interface"""
        self.vpp.api.det44_interface_add_del_feature(
            sw_if_index=self.vpp.get_sw_if_index(interface_in),
            is_inside=True,
            is_add=False,
        )

    def add_det44_mapping(self, in_addr, in_plen, out_addr, out_plen):
        """Add DET44 mapping"""
        self.vpp.api.det44_add_del_map(
            in_addr=in_addr,
            in_plen=in_plen,
            out_addr=out_addr,
            out_plen=out_plen,
            is_add=True,
        )

    def delete_det44_mapping(self, in_addr, in_plen, out_addr, out_plen):
        """Delete DET44 mapping"""
        self.vpp.api.det44_add_del_map(
            in_addr=in_addr,
            in_plen=in_plen,
            out_addr=out_addr,
            out_plen=out_plen,
            is_add=False,
        )

    def set_det44_timeouts(
        self, icmp: int, udp: int, tcp_established: int, tcp_transitory: int
    ):
        """Set DET44 timeouts
        Args:
            tcp_established (int): TCP established timeout
            tcp_transitory (int): TCP transitory timeout
            udp (int): UDP timeout
            icmp (int): ICMP timeout
        """
        self.vpp.api.det44_set_timeouts(
            icmp=icmp,
            udp=udp,
            tcp_established=tcp_established,
            tcp_transitory=tcp_transitory,
        )
