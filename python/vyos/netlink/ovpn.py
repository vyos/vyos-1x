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
Creation and inspection of "ovpn" interfaces for OpenVPN data channel offload.

The Kernel module takes the operating mode as a link attribute at creation
time and it can not be changed afterwards. iproute2 has no support for the
link type, so it can only ever create a device in the default point-to-point
mode - which a server then adopts and rejects every client on. Go through
netlink directly instead.
"""

from socket import if_nametoindex

from pyroute2 import IPRoute
from pyroute2.netlink import NLM_F_DUMP
from pyroute2.netlink import NLM_F_REQUEST
from pyroute2.netlink import genlmsg
from pyroute2.netlink import nla
from pyroute2.netlink.generic import GenericNetlinkSocket
from pyroute2.netlink.rtnl.ifinfmsg import ifinfmsg

# uapi: enum ovpn_mode
OVPN_MODE_P2P = 0
OVPN_MODE_MP = 1

# uapi: OVPN_FAMILY_NAME and enum ovpn_nl_commands
OVPN_FAMILY_NAME = 'ovpn'
OVPN_CMD_PEER_GET = 3


class ovpn_data(nla):
    prefix = 'IFLA_'
    nla_map = (
        ('IFLA_OVPN_UNSPEC', 'none'),
        ('IFLA_OVPN_MODE', 'uint8'),
    )


# pyroute2 does not know the link type either, so teach it
ifinfmsg.ifinfo.data_map.setdefault('ovpn', ovpn_data)


class ovpnmsg(genlmsg):
    """OVPN_A_* of the "ovpn" generic netlink family. Only the attributes read
    below are decoded; the rest stay opaque so a Kernel that grows new ones
    does not break the parser."""

    prefix = 'OVPN_A_'
    nla_map = (
        ('OVPN_A_UNSPEC', 'none'),
        ('OVPN_A_IFINDEX', 'uint32'),
        ('OVPN_A_PEER', 'peer'),
        ('OVPN_A_KEYCONF', 'hex'),
    )

    class peer(nla):
        prefix = 'OVPN_A_PEER_'
        nla_map = (
            ('OVPN_A_PEER_UNSPEC', 'none'),
            ('OVPN_A_PEER_ID', 'uint32'),
            ('OVPN_A_PEER_REMOTE_IPV4', 'hex'),
            ('OVPN_A_PEER_REMOTE_IPV6', 'hex'),
            ('OVPN_A_PEER_REMOTE_IPV6_SCOPE_ID', 'hex'),
            ('OVPN_A_PEER_REMOTE_PORT', 'hex'),
            ('OVPN_A_PEER_SOCKET', 'hex'),
            ('OVPN_A_PEER_SOCKET_NETNSID', 'hex'),
            ('OVPN_A_PEER_VPN_IPV4', 'hex'),
            ('OVPN_A_PEER_VPN_IPV6', 'hex'),
            ('OVPN_A_PEER_LOCAL_IPV4', 'hex'),
            ('OVPN_A_PEER_LOCAL_IPV6', 'hex'),
            ('OVPN_A_PEER_LOCAL_PORT', 'hex'),
            ('OVPN_A_PEER_KEEPALIVE_INTERVAL', 'uint32'),
            ('OVPN_A_PEER_KEEPALIVE_TIMEOUT', 'uint32'),
            ('OVPN_A_PEER_DEL_REASON', 'hex'),
            ('OVPN_A_PEER_VPN_RX_BYTES', 'uint64'),
            ('OVPN_A_PEER_VPN_TX_BYTES', 'uint64'),
            ('OVPN_A_PEER_VPN_RX_PACKETS', 'uint64'),
            ('OVPN_A_PEER_VPN_TX_PACKETS', 'uint64'),
            ('OVPN_A_PEER_LINK_RX_BYTES', 'uint64'),
            ('OVPN_A_PEER_LINK_TX_BYTES', 'uint64'),
            ('OVPN_A_PEER_LINK_RX_PACKETS', 'uint64'),
            ('OVPN_A_PEER_LINK_TX_PACKETS', 'uint64'),
        )


def get_ovpn_peers(ifname: str) -> list:
    """The peers the Kernel holds for an "ovpn" interface, as dictionaries of
    the decoded OVPN_A_PEER_* attributes.

    A peer only exists here once OpenVPN's OVPN_CMD_PEER_NEW succeeded, so
    this is the one way to tell an offload that carries traffic from a device
    that merely looks right. The byte counters are the Kernel's own, unlike
    the ones OpenVPN reports, which add its userspace socket accounting.

    OVPN_CMD_PEER_GET carries GENL_ADMIN_PERM, so this needs CAP_NET_ADMIN.
    """
    peers = []
    with GenericNetlinkSocket() as sock:
        sock.bind(OVPN_FAMILY_NAME, ovpnmsg)

        msg = ovpnmsg()
        msg['cmd'] = OVPN_CMD_PEER_GET
        msg['version'] = 1
        msg['attrs'] = [('OVPN_A_IFINDEX', if_nametoindex(ifname))]

        for reply in sock.nlm_request(
            msg, msg_type=sock.prid, msg_flags=NLM_F_REQUEST | NLM_F_DUMP
        ):
            peer = reply.get_attr('OVPN_A_PEER')
            if peer is not None:
                peers.append(dict(peer['attrs']))

    return peers


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
