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

import ctypes
import os
import socket
from fcntl import ioctl
from pathlib import Path
from struct import pack


mem_shift = {'K': 10, 'k': 10, 'M': 20, 'm': 20, 'G': 30, 'g': 30}


def iftunnel_transform(iface: str) -> str:
    """Transform interface name from `xxxNN` to `xxx_tunnelNN`

    Args:
        iface (str): original interface name

    Raises:
        ValueError: Raised if an interface name does not start with a alpha and ends with decimal digit

    Returns:
        str: Transformed interface name
    """
    # Check format
    if not iface[0].isascii() or not iface[-1].isdecimal():
        raise ValueError(f'Wrong interface name format: {iface}')
    # Transform
    iface_type: str = iface.rstrip('0123456789')
    iface_num: str = iface.removeprefix(iface_type)
    # Return transformed
    return f'{iface_type}_tunnel{iface_num}'


def cli_ifaces_list(config_instance, mode: str = 'candidate') -> list[str]:
    """List of all VPP interfaces (CLI names)

    Args:
        config_instance (VyOS Config): VyOS Config instance
        mode (str, optional): `candidate` or `running`. Defaults to 'candidate'.

    Returns:
        list[str]: list of interfaces
    """

    effective_mode: bool = True if mode == 'running' else False

    # Read a config
    config = config_instance.get_config_dict(
        ['vpp'],
        key_mangling=('-', '_'),
        effective=effective_mode,
        get_first_key=True,
        no_tag_node_value_mangle=True,
        with_recursive_defaults=True,
    )

    vpp_ifaces: list[str] = []

    # Get a list of Ethernet interfaces
    for iface in config.get('settings', {}).get('interface', {}).keys():
        vpp_ifaces.append(iface)

    # Get a list of VPP interfaces
    for iface_type in config.get('interfaces', {}).keys():
        for iface in config.get('interfaces', {}).get(iface_type, {}).keys():
            vpp_ifaces.append(iface)

    return vpp_ifaces


def cli_ethernet_with_vifs_ifaces(config_instance) -> list[str]:
    """List of all VPP Ethernet interfaces with VIFs

    Args:
        config_instance (VyOS Config): VyOS Config instance

    Returns:
        list[str]: list of interfaces
    """
    from vyos.configdict import get_interface_dict

    # Read a config
    config = config_instance.get_config_dict(
        ['vpp'],
        key_mangling=('-', '_'),
        get_first_key=True,
        no_tag_node_value_mangle=True,
        with_recursive_defaults=True,
    )

    ifaces: list[str] = []

    # Get a list of Ethernet interfaces
    for iface in config.get('settings', {}).get('interface', {}).keys():
        ifaces.append(iface)

    # Add Ethernet interfaces with VIFs
    for iface in ifaces:
        _, iface_config = get_interface_dict(
            config_instance, ['interfaces', 'ethernet'], ifname=iface
        )
        ifaces.extend([f'{iface}.{vif}' for vif in iface_config.get('vif', {})])
        ifaces.extend([f'{iface}.{vif_s}' for vif_s in iface_config.get('vif_s', {})])

    return ifaces


def vpp_ifaces_list(vpp_api) -> list[dict]:
    """List interfaces in VPP

    Args:
        vpp_api (_type_): VPP API object

    Returns:
        list[dict]: list of dictionaries with interfaces
    """
    ifaces_list: list[dict] = []
    sw_ifaces_dump = vpp_api.sw_interface_dump()
    while sw_ifaces_dump:
        iface_details = sw_ifaces_dump.pop()
        ifaces_list.append(iface_details._asdict())

    return ifaces_list


def vpp_ip_addresses_by_index(vpp_api, index: str) -> list[str]:
    """List of IP addresses for interface by its index in VPP

    Args:
        vpp_api (_type_): VPP API object
        index (str): interface index in vpp

    Returns:
        list[str]: list of IP addresses
    """
    ip_addresses_list: list[dict] = []
    ip_address_dump = vpp_api.ip_address_dump(sw_if_index=index)
    while ip_address_dump:
        ip_address_details = ip_address_dump.pop()
        ip_addresses_list.append(str(ip_address_details._asdict().get('prefix')))
    return ip_addresses_list


def vpp_ifaces_stats(
    iface_name: str = '',
) -> dict[str, dict[str, int | dict[str, int]]]:
    from re import compile as re_compile
    from vpp_papi import vpp_stats

    def total_value(val_list: vpp_stats.SimpleList) -> int | dict[str, int]:
        """Helper for aggregation stats from multiple workers

        Args:
            val_list (vpp_stats.SimpleList): list of stats for all workers

        Returns:
            int | dict[str, int]: Summary stats
        """
        # if all items are int return their sum
        if all(isinstance(value, int) for value in val_list):
            return sum(val_list)
        # if all items are tuple
        if all(isinstance(value, tuple) for value in val_list):
            combined_stats = {}
            # process individual workers
            for worker_stats in val_list:
                packets, octets = worker_stats
                sum_packets = combined_stats.get('packets', 0) + packets
                sum_octets = combined_stats.get('octets', 0) + octets
                combined_stats = {'packets': sum_packets, 'bytes': sum_octets}
            return combined_stats

        # items are something unknown, just return what we received
        return val_list

    stats = vpp_stats.VPPStats()

    ifaces_stats: dict[str, dict[str, int | dict[str, int]]] = {}

    # prepare parser for stats output
    regex_parser = re_compile(r'^/interfaces/(?P<iface>[^/]+)/(?P<param>[^/]+)')
    # get list of available stats and dump them
    stats_list: list[str] = stats.ls([f'^/interfaces/{iface_name}'])
    stats_dump: list[dict[str, int]] = stats.dump(stats_list)

    # parse outputs and convert it to a dictionary
    for stats_key, stats_value in stats_dump.items():
        parsed_key = regex_parser.search(stats_key).groupdict()
        iface_name = parsed_key['iface']
        param = parsed_key['param']
        stats_item = {param: total_value(stats_value)}
        if iface_name in ifaces_stats:
            ifaces_stats[iface_name].update(stats_item)
        else:
            ifaces_stats[iface_name] = stats_item

    return ifaces_stats


def cli_ifaces_lcp_kernel_list(
    config_instance, mode: str = 'candidate'
) -> list[tuple[str, str]]:
    """List of all VPP kernel-interfaces (CLI names, attached VPP interfaces)

    Args:
        config_instance (VyOS Config): VyOS Config instance
        mode (str, optional): `candidate` or `running`. Defaults to 'candidate'.

    Returns:
        list[tuple[str, str]]: list of interfaces ([(vpp_iface, kernel_iface)])
    """

    effective_mode: bool = True if mode == 'running' else False

    # Read a config
    config = config_instance.get_config_dict(
        ['vpp'],
        key_mangling=('-', '_'),
        effective=effective_mode,
        get_first_key=True,
        no_tag_node_value_mangle=True,
        with_recursive_defaults=True,
    )

    lcp_kernel_ifaces: list[tuple[str, str]] = []

    # Get a list with kernel interfaces
    for ifaces_list in config.get('interfaces', {}).values():
        for iface_name, iface_settings in ifaces_list.items():
            if 'kernel_interface' in iface_settings:
                lcp_kernel_ifaces.append(
                    (iface_name, iface_settings['kernel_interface'])
                )

    return lcp_kernel_ifaces


def get_default_hugepage_size() -> int:
    """
    Retrieve the system's default huge page size.
    :return: The default huge page size in bytes.
    """
    page_size = None
    try:
        # default huge page size
        memfd = os.memfd_create('tmp', os.MFD_HUGETLB)
        st = os.fstat(memfd)
        page_size = st.st_blksize
        os.close(memfd)
    except OSError:
        pass

    return page_size


def get_default_page_size() -> int:
    """
    Retrieve the system's default page size.
    :return: The default page size in bytes.
    """
    return os.sysconf('SC_PAGESIZE')


def get_hugepage_sizes() -> list[int]:
    """
    Retrieve all available huge page sizes from the system.
    :return: A list of huge page sizes in bytes.
    """
    huge_sizes = []
    path = '/sys/kernel/mm/hugepages/'
    try:
        entries = os.listdir(path)
        for entry in entries:
            if entry.startswith('hugepages-'):
                try:
                    size_kb = int(entry.replace('hugepages-', '').replace('kB', ''))
                    huge_sizes.append(size_kb << 10)  # Convert KB to bytes
                except ValueError:
                    pass
    except FileNotFoundError:
        pass

    return huge_sizes


def human_memory_to_bytes(value: str) -> int:
    """
    Convert a human-readable vpp memory format (K, M, G) to a byte value.

    :param value: The string memory size in vpp human-readable format.
    :return: A int representing the value.
    """
    try:
        return int(value)
    except ValueError:
        return int(value[:-1]) << mem_shift[value[-1]]


def bytes_to_human_memory(value: int, unit: str) -> str | None:
    """
    Convert a byte value to a human-readable format (K, M, G).

    :param value: The size in bytes.
    :param unit: The unit to convert to ('K', 'M', 'G').
    :return: A string representing the value in the specified unit, or None if zero.
    """
    val = value >> mem_shift[unit]
    return f'{val}{unit}' if val else None


def human_page_memory_to_bytes(value: str) -> int:
    """
    Convert a human-readable vpp page size format to a byte value.

    :param value: The string memory size in vpp human-readable format.
    :return: A int representing the value.
    """
    default = {
        'default': get_default_page_size,
        'default-hugepage': get_default_hugepage_size,
    }
    try:
        return default[value]()
    except KeyError:
        return human_memory_to_bytes(value)


class EthtoolGDrvinfo:
    """Return interface details like `ethtol -i` does"""

    # TODO
    # this probably need to be replaced with a code generator
    # like ctypeslib or C extension
    class EthtoolDrvinfo(ctypes.Structure):
        _fields_ = [
            ('cmd', ctypes.c_uint32),
            ('driver', ctypes.c_char * 32),  # Driver short name
            ('version', ctypes.c_char * 32),  # Driver version
            ('fw_version', ctypes.c_char * 32),  # Firmware version
            # Be careful: bus info can be longer than 32 chars and thus truncated
            ('bus_info', ctypes.c_char * 32),  # Bus info.
            ('erom_version', ctypes.c_char * 32),  # Expansion ROM version
            ('reserved2', ctypes.c_char * 12),  # Reserved for future use
            ('n_priv_flags', ctypes.c_uint32),  # Number of private flags
            ('n_stats', ctypes.c_uint32),  # Number of U64 stats
            ('testinfo_len', ctypes.c_uint32),  # Test info length
            ('eedump_len', ctypes.c_uint32),  # EEPROM dump length
            ('regdump_len', ctypes.c_uint32),  # Register dump length
        ]

    def __init__(self, iface: str):
        # Constants for ethtool
        SIOCETHTOOL = 0x8946  # pretend to be ethtool
        ETHTOOL_GDRVINFO = 0x00000003  # Command to get driver info

        # Create a dummy socket
        sockfd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Prepare the request for getting driver info
        drvinfo = self.EthtoolDrvinfo(cmd=ETHTOOL_GDRVINFO)
        ifreq: bytes = pack('16sP', iface.encode('utf-8'), ctypes.addressof(drvinfo))

        # Make an ioctl call to get the driver info
        try:
            ioctl(sockfd, SIOCETHTOOL, ifreq)
        except OSError:
            raise FileNotFoundError(f'There is no Ethernet device: {iface}')

        # Close the socket
        sockfd.close()

        # save the information
        self.driver: str = drvinfo.driver.decode('utf-8').strip('\x00')
        self.version: str = drvinfo.version.decode('utf-8').strip('\x00')
        self.fw_version: str = drvinfo.fw_version.decode('utf-8').strip('\x00')
        self.bus_info: str = drvinfo.bus_info.decode('utf-8').strip('\x00')
        self.erom_version: str = drvinfo.erom_version.decode('utf-8').strip('\x00')
        self.reserved2: str = drvinfo.reserved2.decode('utf-8').strip('\x00')
        self.n_priv_flags: int = drvinfo.n_priv_flags
        self.testinfo_len: int = drvinfo.testinfo_len
        self.eedump_len: int = drvinfo.eedump_len
        self.regdump_len: int = drvinfo.regdump_len

    def bus_info_expand(self, bus_name: str) -> str:
        bus_path = Path(f'/sys/bus/{bus_name}/devices').glob(f'{self.bus_info}*')
        dev_ids = list(bus_path)
        if not dev_ids:
            raise FileNotFoundError(
                f'No matching IDs on the bus: {self.bus_info} on {bus_name}'
            )
        if len(dev_ids) > 1:
            raise FileNotFoundError(
                f'There are more than one matching IDs on the bus: {dev_ids} on {bus_name}'
            )
        return dev_ids[0].name
