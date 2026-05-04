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
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

from pyroute2.netlink import genlmsg
from pyroute2.netlink import nla
from pyroute2.netlink import NLM_F_REQUEST
from pyroute2.netlink.exceptions import NetlinkError
from pyroute2.netlink.generic import GenericNetlinkSocket
from pyroute2.netlink.generic.ethtool import ETHTOOL_GENL_NAME
from pyroute2.netlink.generic.ethtool import ETHTOOL_GENL_VERSION
from pyroute2.netlink.generic.ethtool import ethtoolheader

# Netlink message type for tsinfo (from Linux kernel uapi/linux/ethtool_netlink.h)
ETHTOOL_MSG_TSINFO_GET = 0x19

# Operation not supported error code from the kernel (95 decimal)
EOPNOTSUPP = 0x5F

# HWTSTAMP_FILTER_* types from <linux/net_tstamp.h>
# Each enum value N maps to bit (1 << N) in the rx_filters bitmask.
# 'ptp' is a combined mask of all PTP-related filter variants.
HWTSTAMP_FILTER = {
    'all': 1 << 1,  # HWTSTAMP_FILTER_ALL
    'ntp': 1 << 15,  # HWTSTAMP_FILTER_NTP_ALL
    'ptp': (1 << 3)  # HWTSTAMP_FILTER_PTP_V1_L4_EVENT
    | (1 << 4)  # HWTSTAMP_FILTER_PTP_V1_L4_SYNC
    | (1 << 5)  # HWTSTAMP_FILTER_PTP_V1_L4_DELAY_REQ
    | (1 << 6)  # HWTSTAMP_FILTER_PTP_V2_L4_EVENT
    | (1 << 7)  # HWTSTAMP_FILTER_PTP_V2_L4_SYNC
    | (1 << 8)  # HWTSTAMP_FILTER_PTP_V2_L4_DELAY_REQ
    | (1 << 9)  # HWTSTAMP_FILTER_PTP_V2_L2_EVENT
    | (1 << 10)  # HWTSTAMP_FILTER_PTP_V2_L2_SYNC
    | (1 << 11)  # HWTSTAMP_FILTER_PTP_V2_L2_DELAY_REQ
    | (1 << 12)  # HWTSTAMP_FILTER_PTP_V2_EVENT
    | (1 << 13)  # HWTSTAMP_FILTER_PTP_V2_SYNC
    | (1 << 14),  # HWTSTAMP_FILTER_PTP_V2_DELAY_REQ
}


class ethtool_bitset_bit(nla):
    """Single bit entry inside a verbose ethtool bitset."""

    nla_map = (
        ('ETHTOOL_A_BITSET_BIT_UNSPEC', 'none'),
        ('ETHTOOL_A_BITSET_BIT_INDEX', 'uint32'),
        ('ETHTOOL_A_BITSET_BIT_NAME', 'asciiz'),
        ('ETHTOOL_A_BITSET_BIT_VALUE', 'flag'),
    )


class ethtool_bitset_bits(nla):
    """Container layer for nesting bit entries in a verbose ethtool bitset."""

    ethtool_bitset_bit = ethtool_bitset_bit
    nla_map = (
        ('ETHTOOL_A_BITSET_BIT_UNSPEC', 'none'),
        ('ETHTOOL_A_BITSET_BIT', 'ethtool_bitset_bit'),
    )


class ethtool_bitset(nla):
    """Ethtool verbose bitset NLA structure.

    The kernel returns the verbose form by default (ETHTOOL_A_BITSET_BITS nested entries).
    ETHTOOL_A_BITSET_VALUE and ETHTOOL_A_BITSET_MASK are listed for positional completeness
    only — they are not read by this implementation.
    """

    ethtool_bitset_bits = ethtool_bitset_bits
    nla_map = (
        ('ETHTOOL_A_BITSET_UNSPEC', 'none'),
        ('ETHTOOL_A_BITSET_NOMASK', 'flag'),
        ('ETHTOOL_A_BITSET_SIZE', 'uint32'),
        ('ETHTOOL_A_BITSET_BITS', 'ethtool_bitset_bits'),
        ('ETHTOOL_A_BITSET_VALUE', 'binary'),
        ('ETHTOOL_A_BITSET_MASK', 'binary'),
    )


class ethtool_tsinfo_msg(genlmsg):
    """Netlink message structure for ETHTOOL_MSG_TSINFO_GET.

    nla_map indices are strictly positional — all attributes up to the last needed index must be
    listed. Intermediate unused attributes are typed 'hex' to skip full NLA decoding.
    Reference: https://docs.kernel.org/networking/ethtool-netlink.html#tsinfo-get
    """

    ethtoolheader = ethtoolheader
    ethtool_bitset = ethtool_bitset
    nla_map = (
        ('ETHTOOL_A_TSINFO_UNSPEC', 'none'),
        ('ETHTOOL_A_TSINFO_HEADER', 'ethtoolheader'),
        ('ETHTOOL_A_TSINFO_TIMESTAMPING', 'hex'),
        ('ETHTOOL_A_TSINFO_TX_TYPES', 'hex'),
        ('ETHTOOL_A_TSINFO_RX_FILTERS', 'ethtool_bitset'),
    )


GeneralNetlinkError = NetlinkError


class TsInfoError(Exception):
    """Custom exception for timestamp info retrieval errors."""

    pass


def _bitset_to_int(attr) -> int:
    """Reconstruct an integer bitmask from a verbose ethtool_bitset NLA."""
    if attr is None:
        return 0
    bits_attr = attr.get_attr('ETHTOOL_A_BITSET_BITS')
    if bits_attr is None:
        return 0
    bitmask = 0
    for bit in bits_attr.get_attrs('ETHTOOL_A_BITSET_BIT'):
        index = bit.get_attr('ETHTOOL_A_BITSET_BIT_INDEX')
        if index is not None:
            bitmask |= 1 << index
    return bitmask


class TsInfoNetlink(GenericNetlinkSocket):
    """Hardware timestamp info queries using pyroute2 with netlink support."""

    def __init__(self, ifname: str):
        super().__init__()
        self._bound = False
        self._ifname = ifname

    def _ensure_bound(self):
        """Bind netlink socket to the generic ethtool family structure if not already active."""
        if not self._bound:
            self.bind(ETHTOOL_GENL_NAME, ethtool_tsinfo_msg)
            self._bound = True

    def get_rx_filters(self) -> set:
        """
        Query supported hardware timestamp receive filters for the interface.

        Returns:
            A set of supported filter names ('all', 'ntp', 'ptp'), or an empty set
            if the driver or interface lacks hardware timestamping support.

        Example:
            >>> with TsInfoNetlink('eth0') as ts:
            ...     print(ts.get_rx_filters())
            {'ptp'}
        """
        self._ensure_bound()

        msg = ethtool_tsinfo_msg()
        msg['cmd'] = ETHTOOL_MSG_TSINFO_GET
        msg['version'] = ETHTOOL_GENL_VERSION
        msg['attrs'].append(
            (
                'ETHTOOL_A_TSINFO_HEADER',
                {'attrs': [['ETHTOOL_A_HEADER_DEV_NAME', self._ifname]]},
            )
        )

        try:
            response = self.nlm_request(
                msg, msg_type=self.prid, msg_flags=NLM_F_REQUEST
            )
        except NetlinkError as e:
            if e.code == EOPNOTSUPP:
                return set()
            raise

        if not response:
            return set()

        bitmask = _bitset_to_int(response[0].get_attr('ETHTOOL_A_TSINFO_RX_FILTERS'))
        return {name for name, mask in HWTSTAMP_FILTER.items() if bitmask & mask}


def get_hw_timestamp_filters(ifname: str) -> set:
    """
    Get supported hardware timestamp receive filter names for an interface.

    Args:
        ifname: Target network interface string (e.g., 'eth0').

    Returns:
        A set of supported human-readable filters, or an empty set on error/lack of support.
    """
    try:
        with TsInfoNetlink(ifname) as ts:
            return ts.get_rx_filters()
    except (NetlinkError, OSError):
        return set()
