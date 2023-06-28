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

from functools import wraps
from pathlib import Path
from re import search as re_search, MULTILINE as re_M
from time import sleep

from vpp_papi import VPPApiClient
from vpp_papi import VPPIOError


class VPPControl:
    """Control VPP network stack
    """

    class _Decorators:
        """Decorators for VPPControl
        """

        @classmethod
        def api_call(cls, decorated_func):

            @wraps(decorated_func)
            def api_safe_wrapper(cls, *args, **kwargs):
                if not cls.vpp_api_client.transport.connected:
                    raise VPPIOError(2, 'VPP API is not connected')
                return decorated_func(cls, *args, **kwargs)

            return api_safe_wrapper

    def __init__(self, attempts: int = 5, interval: int = 1000) -> None:
        """Create VPP API connection

        Args:
            attempts (int, optional): attempts to connect. Defaults to 5.
            interval (int, optional): interval between attempts in ms. Defaults to 1000.

        Raises:
            VPPIOError: Connection to API cannot be established
        """
        self.vpp_api_client = VPPApiClient()
        # connect with interval
        while attempts:
            try:
                attempts -= 1
                self.vpp_api_client.connect('vpp-vyos')
                break
            except (ConnectionRefusedError, FileNotFoundError) as err:
                print(f'VPP API connection timeout: {err}')
                sleep(interval / 1000)
        # raise exception if connection was not successful in the end
        if not self.vpp_api_client.transport.connected:
            raise VPPIOError(2, 'Cannot connect to VPP API')

    def __del__(self) -> None:
        """Disconnect from VPP API (destructor)
        """
        self.disconnect()

    def disconnect(self) -> None:
        """Disconnect from VPP API
        """
        if self.vpp_api_client.transport.connected:
            self.vpp_api_client.disconnect()

    @_Decorators.api_call
    def cli_cmd(self, command: str, return_output: bool = False) -> str:
        """Send raw CLI command

        Args:
            command (str): command to send
            return_output (bool, optional): Return command output. Defaults to False.

        Returns:
            str: output of the command, only if it was successful
        """
        cli_answer = self.vpp_api_client.api.cli_inband(cmd=command)
        if return_output and cli_answer.retval == 0:
            return cli_answer.reply
        return ''

    @_Decorators.api_call
    def get_mac(self, ifname: str) -> str:
        """Find MAC address by interface name in VPP

        Args:
            ifname (str): interface name inside VPP

        Returns:
            str: MAC address
        """
        for iface in self.vpp_api_client.api.sw_interface_dump():
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
        for iface in self.vpp_api_client.api.sw_interface_dump():
            if iface.interface_name == ifname:
                return iface.sw_if_index
        return None

    @_Decorators.api_call
    def lcp_pair_add(self, iface_name_vpp: str, iface_name_kernel: str) -> None:
        """Create LCP interface pair between VPP and kernel

        Args:
            iface_name_vpp (str): interface name in VPP
            iface_name_kernel (str): interface name in kernel
        """
        iface_index = self.get_sw_if_index(iface_name_vpp)
        if iface_index:
            self.vpp_api_client.api.lcp_itf_pair_add_del(
                is_add=True,
                sw_if_index=iface_index,
                host_if_name=iface_name_kernel)

    @_Decorators.api_call
    def lcp_pair_del(self, iface_name_vpp: str, iface_name_kernel: str) -> None:
        """Delete LCP interface pair between VPP and kernel

        Args:
            iface_name_vpp (str): interface name in VPP
            iface_name_kernel (str): interface name in kernel
        """
        iface_index = self.get_sw_if_index(iface_name_vpp)
        if iface_index:
            self.vpp_api_client.api.lcp_itf_pair_add_del(
                is_add=False,
                sw_if_index=iface_index,
                host_if_name=iface_name_kernel)

    @_Decorators.api_call
    def iface_rxmode(self, iface_name: str, rx_mode: str) -> None:
        """Set interface rx-mode in VPP

        Args:
            iface_name (str): interface name in VPP
            rx_mode (str): mode (polling, interrupt, adaptive)
        """
        modes_dict: dict[str, int] = {
            'polling': 1,
            'interrupt': 2,
            'adaptive': 3
        }
        if rx_mode not in modes_dict:
            return
        iface_index = self.get_sw_if_index(iface_name)
        self.vpp_api_client.api.sw_interface_set_rx_mode(
            sw_if_index=iface_index, mode=modes_dict[rx_mode])

    @_Decorators.api_call
    def get_pci_addr(self, ifname: str) -> str:
        """Find PCI address of interface by interface name in VPP

        Args:
            ifname (str): interface name inside VPP

        Returns:
            str: PCI address
        """
        hw_info = self.cli_cmd(f'show hardware-interfaces {ifname}',
                               return_output=True)

        regex_filter = r'^\s+pci: device (?P<device>\w+:\w+) subsystem (?P<subsystem>\w+:\w+) address (?P<address>\w+:\w+:\w+\.\w+) numa (?P<numa>\w+)$'
        re_obj = re_search(regex_filter, hw_info, re_M)

        # return empty string if no interface or no PCI info was found
        if not hw_info or not re_obj:
            return ''

        address = re_obj.groupdict().get('address', '')

        # we need to modify address to math kernel style
        # for example: 0000:06:14.00 -> 0000:06:14.0
        address_chunks: list[str] | Any = address.split('.')
        address_normalized: str = f'{address_chunks[0]}.{int(address_chunks[1])}'

        return address_normalized


class HostControl:
    """Control Linux host
    """

    def pci_rescan(self, address: str = '') -> None:
        """Rescan PCI device by removing it and rescan PCI bus

        If PCI address is not defined - just rescan PCI bus

        Args:
            address (str, optional): PCI address of device. Defaults to ''.
        """
        if address:
            device_file = Path(f'/sys/bus/pci/devices/{address}/remove')
            if device_file.exists():
                device_file.write_text('1')
        rescan_file = Path('/sys/bus/pci/rescan')
        rescan_file.write_text('1')
