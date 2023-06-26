# Copyright 2023 VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

from vyos.util import call


def lcp_create_host_interface(ifname):
    """LCP reprepsents a connection point between VPP dataplane
    and the host stack
    """
    return call(f'vppctl lcp create {ifname} host-if {ifname}')


def set_interface_rx_mode(ifname, mode):
    """Rx mode"""
    return call(f'sudo vppctl set interface rx-mode {ifname} {mode}')
