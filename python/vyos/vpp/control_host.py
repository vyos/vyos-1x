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


from pathlib import Path
from re import fullmatch as re_fullmatch
from subprocess import run
from time import sleep

from pyroute2 import IPRoute

from vyos.ethtool import Ethtool
from vyos.ifconfig import EthernetIf
from vyos.vpp.utils import EthtoolGDrvinfo


def pci_rescan(pci_addr: str = '') -> None:
    """Rescan PCI device by removing it and rescan PCI bus

    If PCI address is not defined - just rescan PCI bus

    Args:
        address (str, optional): PCI address of device. Defaults to ''.
    """
    device_file = Path(f'/sys/bus/pci/devices/{pci_addr}/remove')
    if pci_addr:
        if device_file.exists():
            device_file.write_text('1')
            # wait 10 seconds max until device will be removed
            attempts = 100
            while device_file.exists() and attempts:
                attempts -= 1
                sleep(0.1)
            if device_file.exists():
                raise TimeoutError(
                    f'Timeout was reached for removing PCI device {pci_addr}'
                )
        else:
            raise FileNotFoundError(f'PCI device {pci_addr} does not exist')
    rescan_file = Path('/sys/bus/pci/rescan')
    rescan_file.write_text('1')
    if pci_addr:
        # wait 10 seconds max until device will be installed
        attempts = 100
        while not device_file.exists() and attempts:
            attempts -= 1
            sleep(0.1)
        if not device_file.exists():
            raise TimeoutError(
                f'Timeout was reached for installing PCI device {pci_addr}'
            )


def unbind_driver(bus_id: str, device_id: str) -> bool:
    """Unbind a driver from a device

    Args:
        bus_id (str): bus ID (pci, vmbus, etc.)
        device_id (str): device id on the bus (PCI address, VMBus UUID)

    Returns:
        bool: True if a driver has been unbound, False otherwise
    """
    device_resolved: str = (
        Path(f'/sys/bus/{bus_id}/devices/{device_id}').resolve().as_posix()
    )
    if not Path(f'{device_resolved}/driver').exists():
        return False

    Path(f'{device_resolved}/driver/unbind').write_text(device_id)
    return True


def rebind_gve_driver(iface: str, bus_id: str, device_id: str) -> None:
    """
    Rebind a device to the gve kernel driver.

    Args:
        iface (str): Interface name
        bus_id (str): Bus type (pci, vmbus, etc.)
        device_id (str): device id on the bus (PCI address, VMBus UUID)
    """
    set_status(iface, 'down')

    # Unbind the device from its current driver
    unbind_driver(bus_id, device_id)

    # Clear driver override (if set)
    device_path = Path(f'/sys/bus/{bus_id}/devices/{device_id}').resolve()
    (device_path / 'driver_override').write_text('')

    # Bind the device to the gve kernel driver
    Path(f'/sys/bus/{bus_id}/drivers/gve/bind').write_text(device_id)

    set_status(iface, 'up')


def probe_driver(bus_id: str, device_id: str) -> None:
    """Probe driver for a device on a bus

    Args:
        bus_id (str): bus ID (pci, vmbus, etc.)
        device_id (str): device id on the bus (PCI address, VMBus UUID)
    """
    Path(f'/sys/bus/{bus_id}/drivers_probe').write_text(device_id)


def load_kernel_module(module_name: str) -> None:
    """Load a kernel module

    Args:
        module_name (str): module name
    """
    # check if a module already loaded
    if Path(f'/sys/module/{module_name}').exists():
        return

    # execute modprobe with the specified module name
    run(['/usr/sbin/modprobe', '-q', module_name], check=True)


def override_driver(bus_id: str, device_id: str, driver_name: str = '') -> None:
    """Override a driver for a device

    Args:
        bus_id (str): bus ID (pci, vmbus, etc.)
        device_id (str): device id on the bus (PCI address, VMBus UUID)
        driver_name (str, optional): Kernel module (driver) name. Defaults to '' - clear an override.

    Raises:
        FileNotFoundError: A device does not support driver override
        ChildProcessError: Failed to override a driver
    """
    device_resolved: str = (
        Path(f'/sys/bus/{bus_id}/devices/{device_id}').resolve().as_posix()
    )
    # check if a device supports driver override
    if not Path(f'{device_resolved}/driver_override').exists():
        raise FileNotFoundError(f'{device_resolved} does not support driver override')

    if driver_name:
        load_kernel_module(driver_name)

    unbind_driver(bus_id, device_id)

    # vfio-pci requires a different workflow: drivers must be explicitly bound by
    # writing the vendor/device IDs to the vfio-pci `new_id` interface. The kernel
    # does not provide a reliable way to check whether an ID has already been
    # registered, so we simply attempt the write and ignore the FileExistsError.
    # Any other failure is treated as a warning.
    if driver_name == 'vfio-pci':
        vendor: str = Path(f'{device_resolved}/vendor').read_text()
        device: str = Path(f'{device_resolved}/device').read_text()
        try:
            Path('/sys/module/vfio_pci/drivers/pci:vfio-pci/new_id').write_text(
                f'{vendor} {device}'
            )
        except FileExistsError:
            pass
        except Exception as e:
            print(f"Warning: failed to write new_id for vfio-pci: {e}")

    # override a driver
    Path(f'{device_resolved}/driver_override').write_text(f'{driver_name}\n')

    # probe a driver
    probe_driver(bus_id, device_id)

    # check the result
    if not Path(f'{device_resolved}/driver').exists():
        raise ChildProcessError(
            f'Failed to override a driver to {driver_name} for {bus_id}, {device_id}'
        )


def get_bus_name(iface: str) -> str:
    """Get bus name
    Works for PCI, VMbus, maybe something else.
    Does not work for Virtio and other virtual devices
    (however, it does not seem we need this for such kind of devices).

    Args:
        iface (str): interface name

    Returns:
        str: bus name
    """
    device_resolved: Path = Path(f'/sys/class/net/{iface}/device').resolve()

    # Iterate upwards until a `bus` directory is found
    current_path: Path = device_resolved
    while True:
        # Check if a bus info is available
        subsystem_path = Path(f'{current_path}/subsystem')
        if subsystem_path.is_symlink():
            # Read the link to determine the bus type
            bus_path = subsystem_path.resolve()
            # Check if the parent directory is a 'bus' directory in '/sys/bus/'
            if bus_path.parent.name == 'bus':
                # Return only the last name of the path, e.g., 'pci'
                return bus_path.name

        # Move up one directory level
        current_path = current_path.parent
        if current_path == Path('/sys'):
            break  # Stop if we reach the root of /sys without finding a bus type

    return ''  # Return None if no bus type was found


def get_eth_name(dev_id: str) -> str:
    """Find Ethernet interface name by PCI address or UUID

    Args:
        dev_id (str): PCI address or UUID

    Raises:
        FileNotFoundError: no Ethernet interface was found

    Returns:
        str: Ethernet interface name
    """
    # find all PCI devices with eth* names
    net_devs: dict[str, str] = {}
    net_devs_dir = Path('/sys/class/net')
    regex_filter = r'^/sys/devices/pci[\w/:\.]+/(?P<pci_addr>\w+:\w+:\w+\.\w+)/[\w/:\.]+/(?P<iface_name>eth\d+)$'
    for dir in net_devs_dir.iterdir():
        # PCI devices
        real_dir: str = dir.resolve().as_posix()
        re_obj = re_fullmatch(regex_filter, real_dir)
        if re_obj:
            iface_name: str = re_obj.group('iface_name')
            iface_addr: str = re_obj.group('pci_addr')
            net_devs.update({iface_addr: iface_name})
        # UUID devices
        else:
            try:
                bus_type: str = get_bus_name(dir.name)
                iface_addr = EthtoolGDrvinfo(dir.name).bus_info_expand(bus_type)
                net_devs.update({iface_addr: dir.name})
            except FileNotFoundError:
                pass

    # match to provided PCI address or UUID and return a name if found
    if dev_id in net_devs:
        return net_devs[dev_id]
    # raise error if device was not found
    raise FileNotFoundError(
        f'A device with ID {dev_id} not found in ethernet interfaces'
    )


def get_dev_id(iface: str) -> str:
    """Get device ID by its interface name

    Args:
        iface (str): interface name

    Raises:
        FileNotFoundError: no Ethernet interface was found

    Returns:
        str: device ID (PCI address or UUID)
    """
    try:
        # Try to get details via ethtool first
        ethtool_info = EthtoolGDrvinfo(iface)
        # For devices represented by UUID we need to expand them
        # to their full representation
        if ethtool_info.driver == 'hv_netvsc':
            return ethtool_info.bus_info_expand('vmbus')
        return ethtool_info.bus_info
    except Exception:
        # raise error if a device ID was not found
        raise FileNotFoundError(f'Cannot find device ID for interface {iface}')


def get_eth_driver(iface: str) -> str:
    """Find kernel module used for Ethernet interface

    Args:
        iface (str): Ethernet interface name

    Raises:
        FileNotFoundError: no Ethernet interface was found

    Returns:
        str: kernel module name
    """
    driver_dir = Path(f'/sys/class/net/{iface}/device/driver/module')
    # Try to detect via sysfs (works for PCI devices)
    if driver_dir.exists():
        return driver_dir.resolve().name

    # Fallback: use ethtool (works for veth, tun, etc.)
    try:
        return Ethtool(iface).get_driver_name()
    except Exception as error:
        raise Exception(f'Could not determine driver for "{iface}": {error}') from error


def unsafe_noiommu_mode(status: bool) -> None:
    """Control unsafe_noiommu_mode parameter of vfio module

    Args:
        status (bool): Target status

    Raises:
        ChildProcessError: Raised if failed to set unsafe_noiommu_mode
    """
    param_path = Path('/sys/module/vfio/parameters/enable_unsafe_noiommu_mode')
    current_status: str = param_path.read_text().strip()
    target_status: str = 'Y' if status else 'N'
    if current_status != target_status:
        param_path.write_text(target_status)
    if param_path.read_text().strip() != target_status:
        raise ChildProcessError('Failed to set unsafe_noiommu_mode')


def rename_iface(name_old: str, name_new: str) -> None:
    """Rename interface

    Args:
        name_old (str): old name
        name_new (str): new name
    """
    run(['ip', 'link', 'set', name_old, 'down'])
    rename_cmd: list[str] = ['ip', 'link', 'set', name_old, 'name', name_new]
    run(rename_cmd)


def set_promisc(iface_name: str, operation: str) -> None:
    """Set promisc mode for interface

    Args:
        iface_name (str): name of an interface
        operation (str): operation (on, off)
    """
    run(['ip', 'link', 'set', iface_name, 'promisc', operation])


def set_mtu(iface_name: str, mtu: int) -> None:
    """Set MTU  for interface

    Args:
        iface_name (str): name of an interface
        mtu (int): MTU
    """
    run(['ip', 'link', 'set', iface_name, 'mtu', str(mtu)])


def get_eth_mac(iface_name: str) -> str:
    """Get MAC address of an interface

    Args:
        iface_name (str): name of an interface

    Raises:
        FileNotFoundError: interface was not found

    Returns:
        str: MAC address
    """
    dev_addr_path = Path(f'/sys/class/net/{iface_name}/address')
    if dev_addr_path.exists():
        return dev_addr_path.read_text().strip()
    else:
        # raise error if device was not found
        raise FileNotFoundError(f'Interface {iface_name} not found')


def xdp_remove(iface_name: str) -> None:
    """Remove XDP BPF program from an interfce

    Args:
        iface_name (str): name of an interface
    """
    run(['ip', 'link', 'set', iface_name, 'xdp', 'off'])


def set_status(iface_name: str, status: str) -> None:
    """Set interface status

    Args:
        iface_name (str): name of an interface
        status (str): status - "up" or "down"
    """
    run(['ip', 'link', 'set', iface_name, status])


def flush_ip(iface_name: str) -> None:
    """Flush IP addresses from an interface

    Args:
        iface_name (str): name of an interface
    """
    iproute = IPRoute()
    iproute.flush_addr(label=iface_name)


def get_eth_channels(iface_name: str) -> dict:
    """
    Get the current hardware queue counts for channels of an interface using ethtool.

    Args:
        iface_name (str): name of an interface

    Returns:
        dict: Mapping of channel types to their current values:
              - 'rx' (int | None): RX channel count.
              - 'tx' (int | None): TX channel count.
              - 'combined' (int | None): Combined channel count.
              Returns None if the channel type is not supported.
    """
    ethtool = Ethtool(iface_name)

    channels = {}
    for channel in ['rx', 'tx', 'combined']:
        queues_list = ethtool.get_channels(channel)
        channels[channel] = queues_list[-1] if (len(queues_list) == 2) else None

    return channels


def set_eth_channels(iface_name: str, channels: dict) -> None:
    """Configure the number of RX, TX, or combined channels for an interface.

    Args:
        iface_name (str): name of an interface
        channels (dict): channels to set
    """
    interface = EthernetIf(iface_name)
    for channel, value in channels.items():
        if value:
            interface.set_channels(channel, value)
