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

from vyos.vpp.control_host import set_promisc
from vyos.vpp.interface.interface import Interface


class BondInterface(Interface):
    def __init__(
        self,
        ifname,
        mode: str = '',
        load_balance: int = 0,
        mac: str = '',
        kernel_interface: str = '',
        state: str = 'up',
    ):
        super().__init__(ifname)
        self.instance = int(ifname.removeprefix('bond'))
        self.ifname = f'BondEthernet{self.instance}'
        self.mode = mode
        self.load_balance = load_balance
        self.mac = mac
        self.kernel_interface = kernel_interface
        self.state = state

    def add(self):
        """Create Bond interface
        https://github.com/FDio/vpp/blob/stable/2306/src/vnet/bonding/bond.api
        Example:
            from vyos.vpp.interface import BondInterface
            a = BondInterface(ifname='bond0', mode=5)
            a.add()
        """
        # Create interface 'bondX'
        create_args = {
            'id': self.instance,
            'mode': self.mode,
            'lb': self.load_balance,
        }
        if self.mac:
            create_args.update({'use_custom_mac': True, 'mac_address': self.mac})
        self.vpp.api.bond_create2(**create_args)
        if self.kernel_interface:
            self.vpp.lcp_pair_add(self.ifname, self.kernel_interface)
        # Set interface state
        self.set_state(self.state)

    def delete(self):
        """Delete Bond interface
        Example:
            from vyos.vpp.interface import BondInterface
            a = BondInterface(ifname='bond0')
            a.delete()
        """
        bond_if_index = self.vpp.get_sw_if_index(self.ifname)
        self.vpp.api.bond_delete(sw_if_index=bond_if_index)

    def add_member(self, interface):
        """Add member to Bond interface
        Example:
            from vyos.vpp.interface import BondInterface
            a = BondInterface(ifname='bond0')
            a.add_member(interface='eth0')
        """
        bond_if_index = self.vpp.get_sw_if_index(f'BondEthernet{self.instance}')
        member_if_index = self.vpp.get_sw_if_index(interface)
        member_if_type = self.vpp.get_sw_if_dev_type(interface)
        self.vpp.api.bond_add_member(
            bond_sw_if_index=bond_if_index, sw_if_index=member_if_index
        )
        self.vpp.api.sw_interface_set_promisc(
            sw_if_index=member_if_index, promisc_on=True
        )
        if member_if_type == 'AF_XDP interface':
            set_promisc(f'defunct_{interface}', 'on')

    def detach_member(self, interface):
        """Detach member from Bond interface
        Example:
            from vyos.vpp.interface import BondInterface
            a = BondInterface(ifname='bond0')
            a.detach_member(interface='eth0')
        """
        member_if_index = self.vpp.get_sw_if_index(interface)
        self.vpp.api.bond_detach_member(sw_if_index=member_if_index)

    def kernel_add(self):
        """Add LCP pair
        Example:
            from vyos.vpp.interface import BondInterface
            a = BondInterface(ifname='bond0', mode=5)
            a.kernel_add()
        """
        self.vpp.lcp_pair_add(self.ifname, self.kernel_interface)

    def kernel_delete(self):
        """Delete LCP pair
        Example:
            from vyos.vpp.interface import BondInterface
            a = BondInterface(ifname='bond0', mode=5)
            a.kernel_delete()
        """
        self.vpp.lcp_pair_del(self.ifname, self.kernel_interface)

    def lcp_pair_exists(self):
        """Check if LCP pair exists"""
        return bool(self.vpp.lcp_pair_find(self.kernel_interface))
