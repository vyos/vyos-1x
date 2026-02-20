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


class VPPBondInterface(Interface, VPPInterface):
    def __init__(self, ifname, config):
        self.ifname = ifname
        self.instance = int(ifname.removeprefix('vppbond'))
        self.vpp_ifname = f'BondEthernet{self.instance}'

        # Initialize Interface (kernel) and VPP part
        super().__init__(ifname)
        VPPInterface.__init__(self, self.vpp_ifname)

        self.index = self.vpp.get_sw_if_index(self.vpp_ifname)
        self.state = 'up' if 'disable' not in config else 'down'
        self.mode = config.get('mode')
        self.load_balance = config.get('hash_policy')
        self.mac = config.get('mac')

    def _create(self):
        pass

    def add_bond(self):
        """Create Bond interface
        https://github.com/FDio/vpp/blob/stable/2306/src/vnet/bonding/bond.api
        Example:
            from vyos.ifconfig.vpp import VPPBondInterface
            a = BondInterface(ifname='vppbond0', config)
            a.add_bond()
        """
        # Create interface 'BondEthernetX'
        create_args = {
            'id': self.instance,
            'mode': self.mode,
            'lb': self.load_balance,
        }
        if self.mac:
            create_args.update({'use_custom_mac': True, 'mac_address': self.mac})
        self.vpp.api.bond_create2(**create_args)
        # Add LCP pair (kernel) interface
        self.kernel_add()
        # Set interface state
        self.set_state(self.state)
        self.set_admin_state(self.state)
        self.index = self.vpp.get_sw_if_index(self.vpp_ifname)

    def delete_bond(self):
        """Delete Bond interface
        Example:
            from vyos.ifconfig.vpp import VPPBondInterface
            a = VPPBondInterface(ifname='vppbond0', config)
            a.delete_bond()
        """
        self.vpp.api.bond_delete(sw_if_index=self.index)

    def add_member(self, interface):
        """Add member to Bond interface
        Example:
            from vyos.ifconfig.vpp import VPPBondInterface
            a = VPPBondInterface(ifname='vppbond0', config)
            a.add_member(interface='eth0')
        """
        member_if_index = self.vpp.get_sw_if_index(interface)
        self.vpp.api.bond_add_member(
            bond_sw_if_index=self.index, sw_if_index=member_if_index
        )
        self.vpp.api.sw_interface_set_promisc(
            sw_if_index=member_if_index, promisc_on=True
        )

    def detach_member(self, interface):
        """Detach member from Bond interface
        Example:
            from vyos.ifconfig.vpp import VPPBondInterface
            a = VPPBondInterface(ifname='vppbond0')
            a.detach_member(interface='eth0')
        """
        member_if_index = self.vpp.get_sw_if_index(interface)
        self.vpp.api.bond_detach_member(sw_if_index=member_if_index)

    def get_members(self):
        members = []
        tmp = self.vpp.api.sw_member_interface_dump(sw_if_index=self.index)
        for member in tmp:
            members.append(member.interface_name)
        return members

    def kernel_add(self):
        """Add LCP pair
        Example:
            from vyos.ifconfig.vpp import VPPBondInterface
            a = VPPBondInterface(ifname='vppbond0')
            a.kernel_add()
        """
        self.vpp.lcp_pair_add(self.vpp_ifname, self.ifname)

    def kernel_delete(self):
        """Delete LCP pair
        Example:
            from vyos.ifconfig.vpp import VPPBondInterface
            a = VPPBondInterface(ifname='vppbond0')
            a.kernel_delete()
        """
        self.vpp.lcp_pair_del(self.vpp_ifname, self.ifname)

    def remove(self):
        if self.index:
            # Detach all existing members
            members = self.get_members()
            for member in members:
                self.detach_member(interface=member)

            # Delete lcp pair interface
            if self.vpp.lcp_pair_find(vpp_name_hw=self.vpp_ifname):
                self.kernel_delete()

            # Delete bonding interface
            self.delete_bond()

    def update(self, config):
        # Add bond interface
        self.add_bond()

        # Add members to bond
        for member in config.get('member', {}).get('interface', []):
            self.add_member(interface=member)

        # Set rx-mode
        rx_mode = config.get('vpp_settings', {}).get('interface_rx_mode')
        if rx_mode:
            self.set_rx_mode(rx_mode)

        # Apply all settings to the lcp pair (kernel) interface
        super().update(config)
