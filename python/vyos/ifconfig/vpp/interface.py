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


class VPPInterface:
    def __init__(self, vpp_ifname):
        self.vpp_ifname = vpp_ifname
        self.vpp = VPPControl()

    def set_state(self, state: str):
        """Set interface state to UP or DOWN
        Args:
            state (str): The state of the interface. Options are 'up' and 'down'.
        Example:
            from vyos.interface.vpp import VPPInterface
            a = VPPInterface(vpp_ifname='eth0')
            a.set_state(state='up')
        """
        if state not in ['up', 'down']:
            raise ValueError(f"Invalid state: {state}")
        state_flag = 1 if state == 'up' else 0
        if_index = self.vpp.get_sw_if_index(self.vpp_ifname)
        self.vpp.api.sw_interface_set_flags(sw_if_index=if_index, flags=state_flag)

    def get_state(self):
        """Get interface state
        Example:
            from vyos.interface.vpp import VPPInterface
            a = VPPInterface(vpp_ifname='eth0')
            a.get_state()
        """
        if_index = self.vpp.get_sw_if_index(self.vpp_ifname)
        return self.vpp.api.sw_interface_dump(sw_if_index=if_index)[0]['flags']

    def set_rx_mode(self, rx_mode):
        lcp_pair = self.vpp.lcp_pair_find(vpp_name_hw=self.vpp_ifname)
        if lcp_pair:
            lcp_name = lcp_pair.get('vpp_name_kernel')
            if lcp_name:
                self.vpp.iface_rxmode(lcp_name, rx_mode)
