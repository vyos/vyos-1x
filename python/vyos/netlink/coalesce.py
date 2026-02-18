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
from pyroute2.netlink import NLM_F_ACK
from pyroute2.netlink import NLM_F_REQUEST
from pyroute2.netlink.exceptions import NetlinkError
from pyroute2.netlink.generic import GenericNetlinkSocket
from pyroute2.netlink.generic.ethtool import ETHTOOL_GENL_NAME
from pyroute2.netlink.generic.ethtool import ETHTOOL_GENL_VERSION
from pyroute2.netlink.generic.ethtool import ethtoolheader

# Netlink message types for coalesce (from Linux kernel)
ETHTOOL_MSG_COALESCE_GET = 0x13
ETHTOOL_MSG_COALESCE_SET = 0x14

# Error codes from the kernel
EINVAL = 0x16  # Invalid argument
EOPNOTSUPP = 0x5F  # Operation not supported

# Mapping between Python attribute names and netlink attribute names, types
# https://docs.kernel.org/networking/ethtool-netlink.html#coalesce-get
# https://git.kernel.org/pub/scm/network/ethtool/ethtool.git/tree/netlink/coalesce.c
COALESCE_NL_ATTRS = {
    'adaptive_rx': 'ETHTOOL_A_COALESCE_USE_ADAPTIVE_RX',
    'adaptive_tx': 'ETHTOOL_A_COALESCE_USE_ADAPTIVE_TX',
    'cqe_mode_rx': 'ETHTOOL_A_COALESCE_USE_CQE_MODE_RX',
    'cqe_mode_tx': 'ETHTOOL_A_COALESCE_USE_CQE_MODE_TX',
    'pkt_rate_high': 'ETHTOOL_A_COALESCE_PKT_RATE_HIGH',
    'pkt_rate_low': 'ETHTOOL_A_COALESCE_PKT_RATE_LOW',
    'rx_frame_high': 'ETHTOOL_A_COALESCE_RX_MAX_FRAMES_HIGH',
    'rx_frame_low': 'ETHTOOL_A_COALESCE_RX_MAX_FRAMES_LOW',
    'rx_frames': 'ETHTOOL_A_COALESCE_RX_MAX_FRAMES',
    'rx_frames_irq': 'ETHTOOL_A_COALESCE_RX_MAX_FRAMES_IRQ',
    'rx_usecs': 'ETHTOOL_A_COALESCE_RX_USECS',
    'rx_usecs_high': 'ETHTOOL_A_COALESCE_RX_USECS_HIGH',
    'rx_usecs_irq': 'ETHTOOL_A_COALESCE_RX_USECS_IRQ',
    'rx_usecs_low': 'ETHTOOL_A_COALESCE_RX_USECS_LOW',
    'sample_interval': 'ETHTOOL_A_COALESCE_RATE_SAMPLE_INTERVAL',
    'stats_block_usecs': 'ETHTOOL_A_COALESCE_STATS_BLOCK_USECS',
    'tx_aggr_max_bytes': 'ETHTOOL_A_COALESCE_TX_AGGR_MAX_BYTES',
    'tx_aggr_max_frames': 'ETHTOOL_A_COALESCE_TX_AGGR_MAX_FRAMES',
    'tx_aggr_time_usecs': 'ETHTOOL_A_COALESCE_TX_AGGR_TIME_USECS',
    'tx_frame_high': 'ETHTOOL_A_COALESCE_TX_MAX_FRAMES_HIGH',
    'tx_frame_low': 'ETHTOOL_A_COALESCE_TX_MAX_FRAMES_LOW',
    'tx_frames': 'ETHTOOL_A_COALESCE_TX_MAX_FRAMES',
    'tx_frames_irq': 'ETHTOOL_A_COALESCE_TX_MAX_FRAMES_IRQ',
    'tx_usecs': 'ETHTOOL_A_COALESCE_TX_USECS',
    'tx_usecs_high': 'ETHTOOL_A_COALESCE_TX_USECS_HIGH',
    'tx_usecs_irq': 'ETHTOOL_A_COALESCE_TX_USECS_IRQ',
    'tx_usecs_low': 'ETHTOOL_A_COALESCE_TX_USECS_LOW',
}


class ethtool_coalesce_msg(genlmsg):
    """Netlink message structure for coalesce parameters."""

    ethtoolheader = ethtoolheader

    # https://docs.kernel.org/networking/ethtool-netlink.html#coalesce-get
    nla_map = (
        ('ETHTOOL_A_COALESCE_UNSPEC', 'none'),
        ('ETHTOOL_A_COALESCE_HEADER', 'ethtoolheader'),
        ('ETHTOOL_A_COALESCE_RX_USECS', 'uint32'),
        ('ETHTOOL_A_COALESCE_RX_MAX_FRAMES', 'uint32'),
        ('ETHTOOL_A_COALESCE_RX_USECS_IRQ', 'uint32'),
        ('ETHTOOL_A_COALESCE_RX_MAX_FRAMES_IRQ', 'uint32'),
        ('ETHTOOL_A_COALESCE_TX_USECS', 'uint32'),
        ('ETHTOOL_A_COALESCE_TX_MAX_FRAMES', 'uint32'),
        ('ETHTOOL_A_COALESCE_TX_USECS_IRQ', 'uint32'),
        ('ETHTOOL_A_COALESCE_TX_MAX_FRAMES_IRQ', 'uint32'),
        ('ETHTOOL_A_COALESCE_STATS_BLOCK_USECS', 'uint32'),
        ('ETHTOOL_A_COALESCE_USE_ADAPTIVE_RX', 'uint8'),
        ('ETHTOOL_A_COALESCE_USE_ADAPTIVE_TX', 'uint8'),
        ('ETHTOOL_A_COALESCE_PKT_RATE_LOW', 'uint32'),
        ('ETHTOOL_A_COALESCE_RX_USECS_LOW', 'uint32'),
        ('ETHTOOL_A_COALESCE_RX_MAX_FRAMES_LOW', 'uint32'),
        ('ETHTOOL_A_COALESCE_TX_USECS_LOW', 'uint32'),
        ('ETHTOOL_A_COALESCE_TX_MAX_FRAMES_LOW', 'uint32'),
        ('ETHTOOL_A_COALESCE_PKT_RATE_HIGH', 'uint32'),
        ('ETHTOOL_A_COALESCE_RX_USECS_HIGH', 'uint32'),
        ('ETHTOOL_A_COALESCE_RX_MAX_FRAMES_HIGH', 'uint32'),
        ('ETHTOOL_A_COALESCE_TX_USECS_HIGH', 'uint32'),
        ('ETHTOOL_A_COALESCE_TX_MAX_FRAMES_HIGH', 'uint32'),
        ('ETHTOOL_A_COALESCE_RATE_SAMPLE_INTERVAL', 'uint32'),
        ('ETHTOOL_A_COALESCE_USE_CQE_MODE_TX', 'uint8'),
        ('ETHTOOL_A_COALESCE_USE_CQE_MODE_RX', 'uint8'),
        ('ETHTOOL_A_COALESCE_TX_AGGR_MAX_BYTES', 'uint32'),
        ('ETHTOOL_A_COALESCE_TX_AGGR_MAX_FRAMES', 'uint32'),
        ('ETHTOOL_A_COALESCE_TX_AGGR_TIME_USECS', 'uint32'),
    )

    @classmethod
    def get_nl_attr_type(cls, nl_attr: str) -> str:
        """Returns type of attribute using declared 'nla_map' field"""

        for nla_name, nla_type in cls.nla_map:
            if nla_name == nl_attr:
                return nla_type

        raise ValueError(f'Unknown netlink attribute name: {nl_attr}')


GeneralNetlinkError = NetlinkError


class CoalesceError(Exception):
    """Base exception for coalesce operations"""

    pass


class CoalesceNotSupportedParam(CoalesceError):
    """Raised when a coalesce parameter is not supported for modification"""

    pass


class CoalesceNotSupportedOperation(CoalesceError):
    """Raised when a coalesce operation is not supported by NIC driver"""

    pass


class CoalesceInvalidValue(CoalesceError):
    """Raised when a coalesce parameter value is invalid"""

    pass


class CoalesceNetlink(GenericNetlinkSocket):
    """
    Interface coalesce management using `pyroute2` with netlink support.

    This class provides functions to read and set interface coalesce parameters
    using the ethtool netlink interface, which properly handles "unsupported" values
    (shown as `n/a` in `ethtool --show-coalesce` output).

    IMPORTANT: The kernel's ethtool netlink interface returns coalesce parameters
    that have non-zero values, but this does NOT mean they are modifiable. The
    driver may impose additional constraints:

     1. Some parameters are read-only (e.g., `rx_usecs` may be reported but not settable)
     2. Some parameters only accept specific values (e.g., `rx_frames` may only accept 1)
     3. The `supported_coalesce_params` bitmask in the driver determines what's truly
        supported, but this is not directly queryable via netlink.

    When setting parameters fails with EOPNOTSUPP (0x5F) or EINVAL (0x16), it typically
    means the parameter is not modifiable or the value is not accepted by the driver.
    """

    def __init__(self, ifname: str):
        super().__init__()
        self._bound = False
        self._ifname = ifname

    def _ensure_bound(self):
        """Ensure the socket is bound to the ethtool generic netlink family"""

        if not self._bound:
            self.bind(ETHTOOL_GENL_NAME, ethtool_coalesce_msg)
            self._bound = True

    def _get_dev_header(self):
        """Create device header for netlink message"""

        return {'attrs': [['ETHTOOL_A_HEADER_DEV_NAME', self._ifname]]}

    def get_coalesce(self):
        """
        Get coalesce parameters for an interface using netlink.

        Example:
            >>> cn = CoalesceNetlink('eth0')
            >>> coalesce = cn.get_coalesce()
            >>> print(coalesce)
            {'rx_usecs': 3, 'rx_frames': None, 'tx_usecs': None, ... }
        """
        self._ensure_bound()

        msg = ethtool_coalesce_msg()
        msg['cmd'] = ETHTOOL_MSG_COALESCE_GET
        msg['version'] = ETHTOOL_GENL_VERSION
        msg['attrs'].append(('ETHTOOL_A_COALESCE_HEADER', self._get_dev_header()))

        try:
            response = self.nlm_request(
                msg, msg_type=self.prid, msg_flags=NLM_F_REQUEST
            )
        except NetlinkError as e:
            if e.code == EOPNOTSUPP:
                raise CoalesceNotSupportedOperation(
                    f'Coalesce operation for {self._ifname} not supported by driver'
                ) from e
            raise

        if not response:
            raise CoalesceError(f'No response for coalesce get on {self._ifname}')

        nl_msg = response[0]

        # Parse response - only include attributes that were returned
        # (unsupported attributes won't be in the response)
        result = {}
        for py_attr, nl_attr in COALESCE_NL_ATTRS.items():
            value = nl_msg.get_attr(nl_attr)  # Will be None if not present/supported

            if value is not None:
                nl_type = ethtool_coalesce_msg.get_nl_attr_type(nl_attr)

                # Convert to boolean value if it is 'uint8' type
                if nl_type == 'uint8':
                    value = bool(value)

            result[py_attr] = value

        return result

    def set_coalesce(self, **kwargs):
        """
        Set coalesce parameters for an interface using netlink.

        Only the parameters that are explicitly passed will be set.
        Unsupported parameters will raise an error from the kernel.

        Args:
            **kwargs: Coalesce parameters to set.  Valid keys are:
                - rx_usecs, rx_frames, rx_usecs_irq, rx_frames_irq
                - tx_usecs, tx_frames, tx_usecs_irq, tx_frames_irq
                - stats_block_usecs
                - adaptive_rx, adaptive_tx
                - pkt_rate_low, pkt_rate_high
                - rx_usecs_low, rx_frame_low, tx_usecs_low, tx_frame_low
                - rx_usecs_high, rx_frame_high, tx_usecs_high, tx_frame_high
                - sample_interval
                - cqe_mode_tx, cqe_mode_rx
                - tx_aggr_max_bytes, tx_aggr_max_frames, tx_aggr_time_usecs

        Example:
            >>> cn = CoalesceNetlink('eth0')
            >>> cn.set_coalesce(rx_usecs=10, tx_usecs=10)
        """
        self._ensure_bound()

        msg = ethtool_coalesce_msg()
        msg['cmd'] = ETHTOOL_MSG_COALESCE_SET
        msg['version'] = ETHTOOL_GENL_VERSION
        msg['attrs'].append(('ETHTOOL_A_COALESCE_HEADER', self._get_dev_header()))

        # Add only the parameters that were explicitly provided
        for py_attr, value in kwargs.items():
            if py_attr not in COALESCE_NL_ATTRS:
                raise CoalesceInvalidValue(f'Unknown coalesce parameter: {py_attr}')

            if value is not None:
                nl_attr = COALESCE_NL_ATTRS[py_attr]
                nl_type = ethtool_coalesce_msg.get_nl_attr_type(nl_attr)

                # Convert values to 'uint' type
                if nl_type.startswith('uint'):
                    value = int(value)

                msg['attrs'].append((nl_attr, value))

        try:
            self.nlm_request(
                msg, msg_type=self.prid, msg_flags=NLM_F_REQUEST | NLM_F_ACK
            )
        except NetlinkError as e:
            params_str = ', '.join(
                '='.join([k.replace('_', '-'), str(v)]) for k, v in kwargs.items()
            )

            if e.code == EOPNOTSUPP:
                raise CoalesceNotSupportedParam(
                    f'Parameter(s) not supported for modification on '
                    f'{self._ifname}: {params_str}'
                ) from e
            elif e.code == EINVAL:
                raise CoalesceInvalidValue(
                    f'Invalid value for coalesce parameter(s) on '
                    f'{self._ifname}: {params_str}'
                ) from e
            raise


def get_coalesce(ifname) -> dict:
    """
    Get coalesce parameters for an interface.

    This is a convenience function that creates a CoalesceNetlink instance,
    gets the coalesce parameters, and closes the socket.

    Args:
        ifname: Interface name (e.g., 'eth0')

    Returns:
        dict: Coalesce parameters with None for unsupported values.
    """
    with CoalesceNetlink(ifname) as cn:
        return cn.get_coalesce()


def set_coalesce(ifname, **kwargs):
    """
    Set coalesce parameters for an interface.

    This is a convenience function that creates a CoalesceNetlink instance,
    sets the coalesce parameters, and closes the socket.

    Args:
        ifname: Interface name (e.g., 'eth0')
        **kwargs: Coalesce parameters to set.
    """
    with CoalesceNetlink(ifname) as cn:
        cn.set_coalesce(**kwargs)


def get_all_params(boolean: bool = None) -> tuple:
    """
    Get all available parameters by the Linux kernel.

    This is a function that gets the coalesce parameters
    which are available by implementation and the Linux kernel.

    Args:
        boolean: Filter parameters and return only/without boolean types.

    Returns:
        tuple: All coalesce parameters
    """

    params = list(COALESCE_NL_ATTRS.keys())

    def _param_is_bool(p):
        nl_type = ethtool_coalesce_msg.get_nl_attr_type(COALESCE_NL_ATTRS[p])
        return nl_type == 'uint8'

    if boolean is not None:
        boolean_params = list(filter(_param_is_bool, params))

        if boolean:
            # Use only boolean parameters
            params = boolean_params
        else:
            # Use other parameters except booleans
            for boolean_param in boolean_params:
                params.remove(boolean_param)

    return tuple(params)
