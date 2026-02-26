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

from collections.abc import Callable
from functools import wraps
from re import search as re_search, MULTILINE as re_M
from systemd import journal
from time import sleep
from typing import TypeVar, ParamSpec, Literal

from vpp_papi import VPPApiClient
from vpp_papi import VPPIOError, VPPValueError

# define types for static type checkers
AnyType = TypeVar('AnyType')
AnyParam = ParamSpec('AnyParam')


class VPPControl:
    """Control VPP network stack"""

    class _Decorators:
        """Decorators for VPPControl"""

        @classmethod
        def api_call(
            cls, decorated_func: Callable[AnyParam, AnyType]
        ) -> Callable[AnyParam, AnyType]:
            """Check if API is connected before API call

            Args:
                decorated_func: function to decorate

            Raises:
                VPPIOError: Connection to API is not established
            """

            @wraps(decorated_func)
            def api_safe_wrapper(
                cls, *args: AnyParam.args, **kwargs: AnyParam.kwargs
            ) -> AnyType:
                if not cls.connected:
                    raise VPPIOError(2, 'VPP API is not connected')
                return decorated_func(cls, *args, **kwargs)

            return api_safe_wrapper

        @classmethod
        def check_retval(
            cls, decorated_func: Callable[AnyParam, AnyType]
        ) -> Callable[AnyParam, AnyType]:
            """Check retval from API response

            Args:
                decorated_func: function to decorate

            Raises:
                VPPValueError: raised when retval is not 0
            """

            @wraps(decorated_func)
            def check_retval_wrapper(
                cls, *args: AnyParam.args, **kwargs: AnyParam.kwargs
            ) -> AnyType:
                return_value = decorated_func(cls, *args, **kwargs)
                if not return_value.retval == 0:
                    raise VPPValueError(f'VPP API call failed: {return_value.retval}')
                return return_value

            return check_retval_wrapper

    def __init__(self, attempts: int = 5, interval: int = 1000) -> None:
        """Create VPP API connection

        Args:
            attempts (int, optional): attempts to connect. Defaults to 5.
            interval (int, optional): interval between attempts in ms. Defaults to 1000.

        Raises:
            VPPIOError: Connection to API cannot be established
        """
        self.__vpp_api_client = VPPApiClient()
        # connect with interval
        while attempts:
            try:
                attempts -= 1
                self.__vpp_api_client.connect('vpp-vyos')
                break
            except (ConnectionRefusedError, FileNotFoundError) as err:
                error_message = f'VPP API connection timeout: {err}'
                journal.send(error_message, priority=journal.LOG_ERR)
                sleep(interval / 1000)
        # raise exception if connection was not successful in the end
        if not self.__vpp_api_client.transport.connected:
            raise VPPIOError(2, 'Cannot connect to VPP API')

    def __del__(self) -> None:
        """Disconnect from VPP API (destructor)"""
        self.disconnect()

    def disconnect(self) -> None:
        """Disconnect from VPP API"""
        if self.__vpp_api_client.transport.connected:
            self.__vpp_api_client.disconnect()

    @_Decorators.check_retval
    @_Decorators.api_call
    def cli_cmd(self, command: str):
        """Send raw CLI command

        Args:
            command (str): command to send

        Returns:
            vpp_papi.vpp_serializer.cli_inband_reply: CLI reply class
        """
        return self.__vpp_api_client.api.cli_inband(cmd=command)

    @_Decorators.api_call
    def get_mac(self, ifname: str) -> str:
        """Find MAC address by interface name in VPP

        Args:
            ifname (str): interface name inside VPP

        Returns:
            str: MAC address
        """
        for iface in self.__vpp_api_client.api.sw_interface_dump():
            if iface.interface_name == ifname:
                return iface.l2_address.mac_string
        return ''

    @_Decorators.api_call
    def get_sw_if_index(self, ifname: str) -> int | None:
        """Find interface index by interface name in VPP

        Args:
            ifname (str): interface name inside VPP

        Returns:
            int | None: Interface index or None (if was not fount)
        """
        for iface in self.__vpp_api_client.api.sw_interface_dump():
            if iface.interface_name == ifname:
                return iface.sw_if_index
        return None

    @_Decorators.api_call
    def get_interface_name(self, index: int) -> str | None:
        """Find interface name by interface index in VPP

        Args:
            index (int): interface index inside VPP

        Returns:
            str | None: Interface name or None (if was not found)
        """
        for iface in self.__vpp_api_client.api.sw_interface_dump():
            if iface.sw_if_index == index:
                return iface.interface_name
        return None

    @_Decorators.check_retval
    @_Decorators.api_call
    def lcp_pair_add(
        self,
        iface_name_vpp: str,
        iface_name_kernel: str,
        iface_type: Literal['tun', 'tap', ''] = '',
    ) -> None:
        """Create LCP interface pair between VPP and kernel

        Args:
            iface_name_vpp (str): interface name in VPP
            iface_name_kernel (str): interface name in kernel
            iface_type (Literal['tun', 'tap', ''], optional): Use explicit interface type in kernel. Defaults to ''.
        """
        iface_index = self.get_sw_if_index(iface_name_vpp)
        if iface_index:
            api_call_args: dict[str, bool | int | str] = {
                'is_add': True,
                'sw_if_index': iface_index,
                'host_if_name': iface_name_kernel,
            }
            if iface_type:
                iface_type_resolve = {'tun': 1, 'tap': 0}
                api_call_args['host_if_type'] = iface_type_resolve[iface_type]
            return self.__vpp_api_client.api.lcp_itf_pair_add_del_v2(**api_call_args)

    @_Decorators.check_retval
    @_Decorators.api_call
    def lcp_pair_del(self, iface_name_vpp: str, iface_name_kernel: str) -> None:
        """Delete LCP interface pair between VPP and kernel

        Args:
            iface_name_vpp (str): interface name in VPP
            iface_name_kernel (str): interface name in kernel
        """
        iface_index = self.get_sw_if_index(iface_name_vpp)
        if iface_index:
            return self.__vpp_api_client.api.lcp_itf_pair_add_del_v2(
                is_add=False, sw_if_index=iface_index, host_if_name=iface_name_kernel
            )

    @_Decorators.api_call
    def lcp_pair_find(
        self,
        kernel_name: str = '',
        vpp_index_hw: int | None = None,
        vpp_index_kernel: int | None = None,
        vpp_name_hw: str = '',
        vpp_name_kernel: str = '',
    ) -> dict[str, str | int] | None:
        """Find LCP pair details

        Args:
            kernel_name (str, optional): Interface name in the kernel. Defaults to ''.
            vpp_index_hw (int | None, optional): Interface index in VPP (hardware). Defaults to None.
            vpp_index_kernel (int | None, optional): Interface index in VPP (kernel). Defaults to None.
            vpp_name_hw (str, optional): Interface name in VPP (hardware). Defaults to ''.
            vpp_name_kernel (str, optional): Interface name in VPP (to kernel). Defaults to ''.

        Returns:
            dict[str, str | int] | None: LCP pair details
        """
        filter_dict = {}
        for filter_name, filter_value in locals().items():
            if filter_value:
                filter_dict[filter_name] = filter_value

        # Get list of pairs
        lcp_pairs = self.lcp_pairs_list()

        # Check each pair
        for pair in lcp_pairs:
            pair_found = False
            # For each item provided in function arguments
            for filter_name, filter_value in filter_dict.items():
                # Stop if filter value is not as in a current pair
                if filter_name in pair and pair[filter_name] != filter_value:
                    pair_found = False
                    break
                # Set flag to True and check the next filter value
                pair_found = True

            if pair_found:
                return pair

        return None

    @_Decorators.api_call
    def lcp_pairs_list(self) -> list[dict[str, str | int]]:
        """List all LCP pairs

        Returns:
            list[dict[str, str | int]]: LCP pairs details
        """
        lcp_pairs_details = []

        lcp_pairs = self.__vpp_api_client.api.lcp_itf_pair_get()[1]
        vpp_ifaces = self.__vpp_api_client.api.sw_interface_dump()
        for pair in lcp_pairs:
            pair_details = {
                'kernel_name': pair.host_if_name,
                'vpp_index_hw': pair.phy_sw_if_index,
                'vpp_index_kernel': pair.host_sw_if_index,
            }
            for vpp_iface in vpp_ifaces:
                if vpp_iface.sw_if_index == pair_details['vpp_index_hw']:
                    pair_details['vpp_name_hw'] = vpp_iface.interface_name
                if vpp_iface.sw_if_index == pair_details['vpp_index_kernel']:
                    pair_details['vpp_name_kernel'] = vpp_iface.interface_name

            lcp_pairs_details.append(pair_details)

        return lcp_pairs_details

    @_Decorators.check_retval
    @_Decorators.api_call
    def lcp_resync(self) -> None:
        """Resynchronize objects between kernel and VPP via Netlink

        This clears all routes in VPP configured by LCP and re-creates them
        based on the current state of the kernel.
        """
        return self.__vpp_api_client.api.lcp_nl_resync()

    @_Decorators.check_retval
    @_Decorators.api_call
    def iface_rxmode(self, iface_name: str, rx_mode: str) -> None:
        """Set interface rx-mode in VPP

        Args:
            iface_name (str): interface name in VPP
            rx_mode (str): mode (polling, interrupt, adaptive)
        """
        modes_dict: dict[str, int] = {'polling': 1, 'interrupt': 2, 'adaptive': 3}
        if rx_mode not in modes_dict:
            raise VPPValueError(f'Mode {rx_mode} is not known')
        iface_index = self.get_sw_if_index(iface_name)
        return self.__vpp_api_client.api.sw_interface_set_rx_mode(
            sw_if_index=iface_index, mode=modes_dict[rx_mode]
        )

    @_Decorators.api_call
    def get_pci_addr(self, ifname: str) -> str:
        """Find PCI address of interface by interface name in VPP

        Args:
            ifname (str): interface name inside VPP

        Returns:
            str: PCI address
        """
        hw_info = self.cli_cmd(f'show hardware-interfaces {ifname}').reply

        regex_filter = r'^\s+pci: device (?P<device>\w+:\w+) subsystem (?P<subsystem>\w+:\w+) address (?P<address>\w+:\w+:\w+\.\w+) numa (?P<numa>\w+)$'
        re_obj = re_search(regex_filter, hw_info, re_M)

        # return empty string if no interface or no PCI info was found
        if not hw_info or not re_obj:
            return ''

        address = re_obj.groupdict().get('address', '')

        # we need to modify address to match kernel style
        # for example: 0000:06:14.00 -> 0000:06:14.0
        address_chunks: list[str] = address.split('.')
        address_normalized: str = f'{address_chunks[0]}.{int(address_chunks[1])}'

        return address_normalized

    @_Decorators.check_retval
    @_Decorators.api_call
    def xdp_iface_create(
        self,
        host_if: str,
        name: str,
        rxq_num: int = 65535,
        rxq_size: int = 0,
        txq_size: int = 0,
        mode: Literal['auto', 'copy', 'zero-copy'] = 'auto',
        flags: Literal['no_syscall_lock', ''] = '',
    ) -> None:
        """Create XDP interface

        Args:
            host_if (str): name of an interface in kernel
            name (str): name of an interface in VPP
            rxq_num (int, optional): Number of receive queues to connect to. Defaults to 0 (all).
            rxq_size (int, optional): Size of receive queue. Defaults to 0.
            txq_size (int, optional): Size of tranceive queue. Defaults to 0.
            mode (Literal['auto', 'copy', 'zero-copy', optional): Zero-copy mode. Defaults to 'auto'.
            flags (Literal['no_syscall_lock', ''], optional): Syscall lock mode. Defaults to ''.
        """
        api_call_args: dict[str, int | str] = {
            'host_if': host_if,
            'name': name,
            'rxq_num': rxq_num,
            'rxq_size': rxq_size,
            'txq_size': txq_size,
        }
        if mode != 'auto':
            mode_resolve: dict[str, int] = {'auto': 0, 'copy': 1, 'zero-copy': 2}
            api_call_args['mode'] = mode_resolve[mode]
        if flags == 'no_syscall_lock':
            api_call_args['flags'] = 1
        return self.__vpp_api_client.api.af_xdp_create_v3(**api_call_args)

    @_Decorators.check_retval
    @_Decorators.api_call
    def xdp_iface_delete(self, iface_name_vpp: str) -> None:
        """Delete XDP interface

        Args:
            iface_name_vpp (str): Name of an interface in VPP
        """
        iface_index = self.get_sw_if_index(iface_name_vpp)
        if iface_index:
            api_call_args: dict[str, int] = {'sw_if_index': iface_index}
            return self.__vpp_api_client.api.af_xdp_delete(**api_call_args)

    @_Decorators.check_retval
    @_Decorators.api_call
    def set_iface_mac(self, iface_name_vpp: str, mac_address: str) -> None:
        """Set MAC address of an interface

        Args:
            iface_name_vpp (str): Name of an interface in VPP
            mac_address (str): MAC address
        """
        iface_index = self.get_sw_if_index(iface_name_vpp)
        api_call_args: dict[str, str | int] = {
            'sw_if_index': iface_index,
            'mac_address': mac_address,
        }
        return self.__vpp_api_client.api.sw_interface_set_mac_address(**api_call_args)

    @_Decorators.check_retval
    @_Decorators.api_call
    def set_iface_mtu(self, iface_name_vpp: str, mtu: int) -> None:
        """Set MTU for interface

        Args:
            iface_name_vpp (str): Name of an interface in VPP
            mtu (int): MTU
        """
        iface_index = self.get_sw_if_index(iface_name_vpp)
        api_call_args: dict[str, str | int] = {'sw_if_index': iface_index, 'mtu': mtu}
        return self.__vpp_api_client.api.hw_interface_set_mtu(**api_call_args)

    @_Decorators.api_call
    def get_sw_if_dev_type(self, ifname: str) -> int | None:
        """Find interface device type by interface name in VPP

        Args:
            ifname (str): interface name inside VPP

        Returns:
            int | None: Interface device type or None (if was not fount)
        """
        for iface in self.__vpp_api_client.api.sw_interface_dump():
            if iface.interface_name == ifname:
                return iface.interface_dev_type
        return None


    @property
    def connected(self) -> bool:
        """Check if VPP API is connected

        Returns:
            bool: True if connected, False if not
        """
        return self.__vpp_api_client.transport.connected

    @property
    @_Decorators.api_call
    def api(self):
        """Call API

        Returns:
            Callable[AnyParam, AnyType]: API functions
        """
        return self.__vpp_api_client.api

    @_Decorators.api_call
    def map_pppoe_interface(self, ifname: str, is_add: bool) -> None:
        """Create or delete PPPoE mapping between data-plain and control-plane interfaces

        Args:
            ifname (str): name of an interface in kernel
            is_add (bool): create or delete mapping
        """
        vpp_pair = self.lcp_pair_find(kernel_name=ifname)
        if vpp_pair:
            vpp_pair_name = vpp_pair['vpp_name_kernel']
            self.__vpp_api_client.api.pppoe_add_del_cp(
                dp_sw_if_index=self.get_sw_if_index(ifname),
                cp_sw_if_index=self.get_sw_if_index(vpp_pair_name),
                is_add=is_add,
            )

    @_Decorators.api_call
    def enable_dhcp_client(self, ifname: str) -> None:
        """Enable DHCP client detection on a given interface

        Args:
            ifname (str): name of an interface in kernel
        """
        iface_index = self.get_sw_if_index(ifname)
        feature_is_enabled = self.__vpp_api_client.api.feature_is_enabled(
            sw_if_index=iface_index,
            feature_name='ip4-dhcp-client-detect',
            arc_name='ip4-unicast',
        )
        if not feature_is_enabled.is_enabled:
            self.__vpp_api_client.api.dhcp_client_detect_enable_disable(
                sw_if_index=iface_index,
                enable=True,
            )

    @_Decorators.api_call
    def disable_dhcp_client(self, ifname: str) -> None:
        """Disable DHCP client detection on a given interface

        Args:
            ifname (str): name of an interface in kernel
        """
        self.__vpp_api_client.api.dhcp_client_detect_enable_disable(
            sw_if_index=self.get_sw_if_index(ifname),
            enable=False,
        )

    @_Decorators.api_call
    def enable_icmpv6_ra_punt(self, ifname: str) -> None:
        """Enable ip6-icmp-ra-punt feature on a given interface for both ip6-unicast and ip6-multicast arcs.

        This ensures that IPv6 ICMP Router Advertisements (RA) are punted to the host, which is typically required
        for features such as DHCPv6 client operation.

        Args:
            ifname (str): name of an interface in kernel
        """
        iface_index = self.get_sw_if_index(ifname)
        for arc_name in ['ip6-unicast', 'ip6-multicast']:
            feature_is_enabled = self.__vpp_api_client.api.feature_is_enabled(
                sw_if_index=iface_index,
                feature_name='ip6-icmp-ra-punt',
                arc_name=arc_name,
            )

            if not feature_is_enabled.is_enabled:
                self.__vpp_api_client.api.feature_enable_disable(
                    sw_if_index=iface_index,
                    enable=True,
                    arc_name=arc_name,
                    feature_name='ip6-icmp-ra-punt',
                )

    @_Decorators.api_call
    def disable_icmpv6_ra_punt(self, ifname: str) -> None:
        """Disable ip6-icmp-ra-punt feature on a given interface

        Args:
            ifname (str): name of an interface in kernel
        """
        for arc_name in ['ip6-unicast', 'ip6-multicast']:
            self.__vpp_api_client.api.feature_enable_disable(
                sw_if_index=self.get_sw_if_index(ifname),
                enable=False,
                arc_name=arc_name,
                feature_name='ip6-icmp-ra-punt',
            )
