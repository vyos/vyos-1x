# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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
# You should have received a copy of the GNU Lesser General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>.

"""
Creation of "ovpn" interfaces for OpenVPN data channel offload.

The Kernel module takes the operating mode as a link attribute at creation
time and it can not be changed afterwards. iproute2 has no support for the
link type, so it can only ever create a device in the default point-to-point
mode - which a server then adopts and rejects every client on. Go through
netlink directly instead.
"""

from pyroute2 import IPRoute
from pyroute2.netlink import nla
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg

# uapi: enum ovpn_mode
OVPN_MODE_P2P = 0
OVPN_MODE_MP = 1


class ovpn_data(nla):
    prefix = 'IFLA_'
    nla_map = (
        ('IFLA_OVPN_UNSPEC', 'none'),
        ('IFLA_OVPN_MODE', 'uint8'),
    )


# pyroute2 does not know the link type either, so teach it
ifinfmsg.ifinfo.data_map.setdefault('ovpn', ovpn_data)


def get_ovpn_mode(ifname: str):
    """Operating mode of an "ovpn" interface, or None when the interface is
    missing or of any other type. iproute2 has no decoder for the attribute,
    so this is the only way to tell a multipoint device from a point-to-point
    one - and adopting the wrong one makes OpenVPN reject every peer."""
    with IPRoute() as ipr:
        links = ipr.get_links(ifname=ifname)

    if not links:
        return None
    info = links[0].get_attr('IFLA_LINKINFO')
    if info is None or info.get_attr('IFLA_INFO_KIND') != 'ovpn':
        return None
    data = info.get_attr('IFLA_INFO_DATA')
    return None if data is None else data.get_attr('IFLA_OVPN_MODE')


def add_ovpn_interface(ifname: str, multipoint: bool) -> None:
    """Create an "ovpn" interface, multipoint for servers and point-to-point
    for everything else - matching what OpenVPN would ask for itself."""
    mode = OVPN_MODE_MP if multipoint else OVPN_MODE_P2P
    with IPRoute() as ipr:
        ipr.link('add', ifname=ifname, kind='ovpn', ovpn_mode=mode)

    # the attribute is silently dropped if pyroute2 ever stops recognising the
    # link type, and the Kernel then quietly falls back to point-to-point
    if get_ovpn_mode(ifname) != mode:
        raise ValueError(f'Could not set operating mode on interface {ifname}')
