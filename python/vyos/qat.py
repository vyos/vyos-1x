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
import re

from vyos.utils.file import read_file
from vyos.utils.process import rc_cmd

# Intel vendor ID, as it appears in /sys/bus/pci/devices/*/vendor
PCI_VENDOR_ID_INTEL = '0x8086'

# PCI device ID -> chipset name, for the QAT drivers VyOS ships.
PCI_DEVICE_IDS = {
    '0x0435': 'DH895',
    '0x18ee': 'QAT_200XX',
    '0x19e2': 'C3xx',
    '0x37c8': 'C62x',
    '0x37c9': 'C62xvf',
    '0x6f54': 'D15xx',
}

PCI_DEVICES_PATH = '/sys/bus/pci/devices'
PROC_CRYPTO = '/proc/crypto'
ADF_CTL = '/usr/sbin/adf_ctl'

# A device line of "adf_ctl status":
#  qat_dev0 - type: c3xxx,  inst_id: 0,  node_id: 0,  bsf: 0000:01:00.0,
#  #accel: 3 #engines: 6 state: up
ADF_CTL_DEVICE = re.compile(
    r'^\s*(?P<name>qat_dev\d+) - type: (?P<type>[^,]+),'
    r'.*\bbsf: (?P<address>[^,]+),.*\bstate: (?P<state>\w+)',
    re.MULTILINE,
)


def _read_sysfs(path):
    return read_file(path, defaultonfailure=None)


def find_devices() -> list:
    """Return the QAT devices present on the PCI bus.

    Each entry carries the PCI address, the chipset name and the kernel driver
    bound to the device (None when no driver is bound).
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
            }
        )

    return devices


# Device states reported by get_device_state()
DEVICE_STATE_NO_DRIVER = 'no driver bound'
DEVICE_STATE_NOT_STARTED = 'not started'
DEVICE_STATE_STARTED = 'started'
DEVICE_STATE_UNKNOWN = 'unknown'

ADF_CTL_STATES = {'up': DEVICE_STATE_STARTED, 'down': DEVICE_STATE_NOT_STARTED}


def canonical_pci_address(address: str) -> str:
    """Return a PCI address in the sysfs form, for example 0000:06:00.0.

    Intel's QAT documentation also shows status output with 06:00:0, which has
    no domain. Anything unparsable is returned unchanged.
    """
    fields = re.split(r'[:.]', address.strip())
    if len(fields) == 3:
        fields.insert(0, '0')
    try:
        domain, bus, device, function = (int(field, 16) for field in fields)
    except ValueError:
        return address
    return f'{domain:04x}:{bus:02x}:{device:02x}.{function:x}'


def parse_adf_ctl_status(output: str) -> list:
    """Return the devices listed in "adf_ctl status" output as dictionaries.

    The address is converted to the sysfs form.
    """
    devices = []
    for match in ADF_CTL_DEVICE.finditer(output):
        device = match.groupdict()
        device['address'] = canonical_pci_address(device['address'])
        devices.append(device)
    return devices


def get_driver_status() -> list:
    """Return the devices reported by "adf_ctl status".

    Empty when the driver cannot be queried.
    """
    _, output = rc_cmd(f'{ADF_CTL} status')
    return parse_adf_ctl_status(output)


def get_device_state(device: dict, driver_status: list) -> str:
    """Return the state of a device returned by find_devices().

    driver_status is the list returned by get_driver_status(). Only the driver
    knows whether a device is started: its debugfs directory outlives a stop.
    """
    if device['driver'] is None:
        return DEVICE_STATE_NO_DRIVER

    address = canonical_pci_address(device['address'])
    for entry in driver_status:
        if entry['address'] == address:
            return ADF_CTL_STATES.get(entry['state'], DEVICE_STATE_UNKNOWN)

    return DEVICE_STATE_UNKNOWN


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
