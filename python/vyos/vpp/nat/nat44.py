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


# NAT44 flags
NAT_IS_NONE = 0x00
NAT_IS_TWICE_NAT = 0x01
NAT_IS_SELF_TWICE_NAT = 0x02
NAT_IS_OUT2IN_ONLY = 0x04
NAT_IS_ADDR_ONLY = 0x08
NAT_IS_OUTSIDE = 0x10
NAT_IS_INSIDE = 0x20

NO_INTERFACE = 0xFFFFFFFF


class Nat44:
    def __init__(self):
        self.vpp = VPPControl()

    def enable_nat44_ed(self):
        """Enable NAT44 endpoint dependent plugin
        Example:
            from vyos.vpp.nat import Nat44
            nat44 = Nat44()
            nat44.enable_nat44_ed()
        https://github.com/FDio/vpp/blob/stable/2410/src/plugins/nat/nat44-ed/nat44_ed.api
        """
        self.vpp.api.nat44_ed_plugin_enable_disable(enable=True)

    def disable_nat44_ed(self):
        """Disable NAT44 endpoint dependent plugin"""
        self.vpp.api.nat44_ed_plugin_enable_disable(enable=False)

    def enable_nat44_ei(self):
        """Enable NAT44 endpoint independent plugin
        Example:
            from vyos.vpp.nat import Nat44
            nat44 = Nat44()
            nat44.enable_nat44_ei()
        """
        self.vpp.api.nat44_ei_plugin_enable_disable(enable=True)

    def add_nat44_interface_inside(self, interface_in):
        """Add NAT44 interface"""
        self.vpp.api.nat44_interface_add_del_feature(
            flags=NAT_IS_INSIDE,
            sw_if_index=self.vpp.get_sw_if_index(interface_in),
            is_add=True,
        )

    def delete_nat44_interface_inside(self, interface_in):
        """Delete NAT44 interface"""
        self.vpp.api.nat44_interface_add_del_feature(
            flags=NAT_IS_INSIDE,
            sw_if_index=self.vpp.get_sw_if_index(interface_in),
            is_add=False,
        )

    def add_nat44_interface_outside(self, interface_out):
        """Add NAT44 interface"""
        self.vpp.api.nat44_interface_add_del_feature(
            flags=NAT_IS_OUTSIDE,
            sw_if_index=self.vpp.get_sw_if_index(interface_out),
            is_add=True,
        )

    def delete_nat44_interface_outside(self, interface_out):
        """Delete NAT44 interface"""
        self.vpp.api.nat44_interface_add_del_feature(
            flags=NAT_IS_OUTSIDE,
            sw_if_index=self.vpp.get_sw_if_index(interface_out),
            is_add=False,
        )

    def add_nat44_address_range(self, addresses, twice_nat):
        """Add NAT44 address range"""
        if '-' not in addresses:
            first_ip_address = last_ip_address = addresses
        else:
            first_ip_address, last_ip_address = addresses.split('-')
        self.vpp.api.nat44_add_del_address_range(
            flags=NAT_IS_TWICE_NAT if twice_nat else NAT_IS_NONE,
            first_ip_address=first_ip_address,
            last_ip_address=last_ip_address,
            is_add=True,
        )

    def delete_nat44_address_range(self, addresses, twice_nat):
        """Delete NAT44 address range"""
        if '-' not in addresses:
            first_ip_address = last_ip_address = addresses
        else:
            first_ip_address, last_ip_address = addresses.split('-')
        self.vpp.api.nat44_add_del_address_range(
            flags=NAT_IS_TWICE_NAT if twice_nat else NAT_IS_NONE,
            first_ip_address=first_ip_address,
            last_ip_address=last_ip_address,
            is_add=False,
        )

    def add_nat44_interface_address(self, interface, twice_nat):
        """Add NAT44 interface address"""
        self.vpp.api.nat44_add_del_interface_addr(
            flags=NAT_IS_TWICE_NAT if twice_nat else NAT_IS_NONE,
            sw_if_index=self.vpp.get_sw_if_index(interface),
            is_add=True,
        )

    def delete_nat44_interface_address(self, interface, twice_nat):
        """Delete NAT44 interface address"""
        self.vpp.api.nat44_add_del_interface_addr(
            flags=NAT_IS_TWICE_NAT if twice_nat else NAT_IS_NONE,
            sw_if_index=self.vpp.get_sw_if_index(interface),
            is_add=False,
        )

    def add_nat44_static_mapping(
        self,
        local_ip,
        external_ip,
        local_port,
        external_port,
        protocol,
        twice_nat,
        self_twice_nat,
        out2in,
        pool_ip,
    ):
        """Add NAT44 static mapping"""
        flags = NAT_IS_ADDR_ONLY if not (protocol or local_port) else NAT_IS_NONE
        flags |= NAT_IS_TWICE_NAT if twice_nat else 0
        flags |= NAT_IS_SELF_TWICE_NAT if self_twice_nat else 0
        flags |= NAT_IS_OUT2IN_ONLY if out2in else 0
        self.vpp.api.nat44_add_del_static_mapping_v2(
            local_ip_address=local_ip,
            external_ip_address=external_ip,
            protocol=protocol,
            local_port=local_port,
            external_port=external_port,
            match_pool=True if pool_ip else False,
            pool_ip_address=pool_ip if pool_ip else '',
            flags=flags,
            is_add=True,
        )

    def delete_nat44_static_mapping(
        self,
        local_ip,
        external_ip,
        local_port,
        external_port,
        protocol,
        twice_nat,
        self_twice_nat,
        out2in,
        pool_ip,
    ):
        """Delete NAT44 static mapping"""
        flags = NAT_IS_ADDR_ONLY if not (protocol or local_port) else NAT_IS_NONE
        flags |= NAT_IS_TWICE_NAT if twice_nat else 0
        flags |= NAT_IS_SELF_TWICE_NAT if self_twice_nat else 0
        flags |= NAT_IS_OUT2IN_ONLY if out2in else 0
        self.vpp.api.nat44_add_del_static_mapping_v2(
            local_ip_address=local_ip,
            external_ip_address=external_ip,
            protocol=protocol,
            local_port=local_port,
            external_port=external_port,
            match_pool=True if pool_ip else False,
            pool_ip_address=pool_ip if pool_ip else '',
            flags=flags,
            is_add=False,
        )

    def add_nat44_identity_mapping(self, ip_address, protocol, port, interface):
        """Add NAT44 identity mapping"""
        self.vpp.api.nat44_add_del_identity_mapping(
            ip_address=ip_address,
            protocol=protocol,
            port=port,
            sw_if_index=(
                self.vpp.get_sw_if_index(interface) if interface else NO_INTERFACE
            ),
            flags=NAT_IS_ADDR_ONLY if not (protocol or port) else NAT_IS_NONE,
            is_add=True,
        )

    def delete_nat44_identity_mapping(self, ip_address, protocol, port, interface):
        """Delete NAT44 identity mapping"""
        self.vpp.api.nat44_add_del_identity_mapping(
            ip_address=ip_address,
            protocol=protocol,
            port=port,
            sw_if_index=(
                self.vpp.get_sw_if_index(interface) if interface else NO_INTERFACE
            ),
            flags=NAT_IS_ADDR_ONLY if not (protocol or port) else NAT_IS_NONE,
            is_add=False,
        )

    def set_nat_timeouts(self, icmp, udp, tcp_established, tcp_transitory):
        """Set NAT timeouts"""
        self.vpp.api.nat_set_timeouts(
            icmp=icmp,
            udp=udp,
            tcp_established=tcp_established,
            tcp_transitory=tcp_transitory,
        )

    def enable_ipfix(self):
        """Enable NAT44 IPFIX logging"""
        self.vpp.api.nat44_ei_ipfix_enable_disable(enable=True)
