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

"""
Intel QuickAssist Technology (QAT) device discovery.

The QAT kernel modules are autoloaded from the PCI modalias and the device is
brought up by the driver itself. Neither of those depends on the "system
acceleration qat" configuration node, so the state of a QAT device must be read
from the kernel and can never be inferred from the configuration session.
"""

import os

from glob import glob

from vyos.utils.file import read_file

# Intel vendor ID, as it appears in /sys/bus/pci/devices/*/vendor
PCI_VENDOR_ID_INTEL = '0x8086'

# PCI device ID -> chipset name, for the QAT drivers VyOS ships.
# Keep in sync with verify() in src/conf_mode/system_acceleration.py.
PCI_DEVICE_IDS = {
    '0x0435': 'DH895',
    '0x18ee': 'QAT_200XX',
    '0x19e2': 'C3xx',
    '0x37c8': 'C62x',
    '0x37c9': 'C62xvf',
    '0x6f54': 'D15xx',
}

PCI_DEVICES_PATH = '/sys/bus/pci/devices'
DEBUGFS_PATH = '/sys/kernel/debug'
PROC_CRYPTO = '/proc/crypto'


def _read_sysfs(path):
    return read_file(path, defaultonfailure=None)


def get_debugfs_path(address: str):
    """Return the debugfs directory the QAT driver created for a PCI device.

    The directory is named qat_<type>_<pci address>, where <type> depends on
    which driver bound the device. Match on the address so that the type does
    not have to be known in advance. Returns None when no such directory
    exists, which is the case while the device has not been started.
    """
    found = glob(os.path.join(DEBUGFS_PATH, f'qat_*_{address}'))
    return found[0] if found else None


def find_devices() -> list:
    """Return the QAT devices present on the PCI bus.

    Each entry carries the PCI address, the chipset name, the kernel driver
    bound to the device (None when no driver is bound) and the debugfs
    directory created by that driver (None when the device has not started).
    """
    devices = []

    if not os.path.isdir(PCI_DEVICES_PATH):
        return devices

    for address in sorted(os.listdir(PCI_DEVICES_PATH)):
        device_path = os.path.join(PCI_DEVICES_PATH, address)

        if _read_sysfs(os.path.join(device_path, 'vendor')) != PCI_VENDOR_ID_INTEL:
            continue

        device_id = _read_sysfs(os.path.join(device_path, 'device'))
        if device_id not in PCI_DEVICE_IDS:
            continue

        driver = None
        driver_link = os.path.join(device_path, 'driver')
        if os.path.islink(driver_link):
            try:
                driver = os.path.basename(os.readlink(driver_link))
            except FileNotFoundError:
                # The device can be unbound between the two calls. Report it
                # as unbound rather than aborting the whole scan.
                pass

        devices.append(
            {
                'address': address,
                'chipset': PCI_DEVICE_IDS[device_id],
                'driver': driver,
                'debugfs': get_debugfs_path(address),
            }
        )

    return devices


# Device states reported by get_device_state()
DEVICE_STATE_NO_DRIVER = 'no driver bound'
DEVICE_STATE_NOT_STARTED = 'not started'
DEVICE_STATE_STARTED = 'started'
DEVICE_STATE_UNKNOWN = 'unknown'


def debugfs_mounted() -> bool:
    """Return True when debugfs is mounted.

    The QAT driver reports per-device state below it. Without debugfs a bound
    device cannot be told apart from a started one, so report the difference
    rather than guessing.
    """
    return os.path.ismount(DEBUGFS_PATH)


def get_device_state(device: dict) -> str:
    """Return the state of a device returned by find_devices()."""
    if device['driver'] is None:
        return DEVICE_STATE_NO_DRIVER
    if device['debugfs'] is not None:
        return DEVICE_STATE_STARTED
    if not debugfs_mounted():
        return DEVICE_STATE_UNKNOWN
    return DEVICE_STATE_NOT_STARTED


def _parse_proc_crypto(data: str):
    """Yield the entries of /proc/crypto as dictionaries."""
    for block in data.split('\n\n'):
        entry = {}
        for line in block.splitlines():
            key, separator, value = line.partition(':')
            if separator:
                entry[key.strip()] = value.strip()
        if entry:
            yield entry


def get_crypto_algorithms() -> list:
    """Return the kernel crypto framework algorithms served by a QAT driver.

    A non-empty result means QAT is registered with the kernel crypto API, and
    therefore that in-kernel users of it - IPsec ESP among them - may have
    their cryptographic operations offloaded to the QAT device, whether or not
    "system acceleration qat" is configured. This is what the --enable-qat-lkcf
    build option of the Intel driver turns on.
    """
    crypto = read_file(PROC_CRYPTO, defaultonfailure=None)
    if crypto is None:
        return []

    return [
        entry
        for entry in _parse_proc_crypto(crypto)
        if 'qat' in entry.get('driver', '') or 'qat' in entry.get('module', '')
    ]
