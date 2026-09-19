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
#
# Persistent interface name store.
#
# The kernel command line carries net.ifnames=0, so VyOS owns the
# 'ethN'/'wlanN' namespace and has to make its choice survive a reboot. A name
# is mapped to the slot the hardware sits in rather than to a MAC in
# config.boot: the slot is the identity, so a replacement card in that slot is
# simply that interface again.
#
# The key is a single udev property picked from a fallback chain, most stable
# first. udev still computes these under net.ifnames=0 - only the renaming
# policy is disabled.

import json
import os
import re
import tempfile
from pathlib import Path

from vyos.defaults import directories
from vyos.utils.process import rc_cmd
from vyos.utils.permission import get_cfg_group_id

STORE_VERSION = 1

# The real path, not '/config': naming runs before the bind mount is up.
store_path = Path(directories['config']) / 'interface-mapping.json'

# Most stable first: a firmware slot index survives PCI renumbering, a path
# does not. The MAC-derived entry is a last resort for paravirtual buses.
KEY_PROPERTIES = (
    'ID_NET_NAME_ONBOARD',
    'ID_NET_NAME_SLOT',
    'ID_NET_NAME_PATH',
    'ID_PATH',
    'ID_NET_NAME_MAC',
)

_BUS_RANK = {'pci': 0, 'vmbus': 1, 'xen': 2, 'usb': 3}
_BUS_RANK_UNKNOWN = 90

_PCI_BDF = re.compile(r'([0-9a-f]{4}):([0-9a-f]{2}):([0-9a-f]{2})\.([0-9a-f]+)', re.I)
_MAC_RE = re.compile(r'([0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5})')


def hardware_key(properties: dict) -> str:
    """The most stable identifier this device offers, as 'PROPERTY=value'."""
    for prop in KEY_PROPERTIES:
        value = properties.get(prop, '')
        if value:
            return f'{prop}={value}'
    return ''


def device_matches(properties: dict, key: str) -> bool:
    """Does this device carry the property a stored key names?"""
    if not key or '=' not in key:
        return False
    prop, _, value = key.partition('=')
    return properties.get(prop, '') == value


def canonical_sort_key(device: dict) -> tuple:
    """Total order by bus class, physical position then MAC, so it never
    depends on probe order. Only used for hardware not yet in the store.
    """
    properties = device.get('properties') or {}
    path = properties.get('ID_PATH', '')
    rank = _BUS_RANK.get(properties.get('ID_BUS', ''), _BUS_RANK_UNKNOWN)

    # numeric, so 0000:09:00.0 sorts before 0000:10:00.0
    segments = [tuple(int(part, 16) for part in m.groups())
                for m in _PCI_BDF.finditer(path)]

    return (rank, segments, path, device.get('mac') or '')


def permanent_mac(ifname: str, sys_class_net: str = '/sys/class/net') -> str:
    """Permanent hardware address, falling back to the current one when the
    driver cannot report it separately.
    """
    code, out = rc_cmd(f'ethtool -P {ifname}')
    if code == 0:
        m = _MAC_RE.search(out)
        if m and m.group(1) != '00:00:00:00:00:00':
            return m.group(1).lower()

    try:
        return Path(f'{sys_class_net}/{ifname}/address').read_text().strip().lower()
    except OSError:
        return ''


def is_wireless(ifname: str, sys_class_net: str = '/sys/class/net') -> bool:
    """Checked via sysfs, not via the - possibly still probe-order - name."""
    return (Path(sys_class_net) / ifname / 'phy80211').exists()


def read_properties(ifname: str) -> dict:
    """udev properties for an interface."""
    try:
        import pyudev

        context = pyudev.Context()
        device = pyudev.Devices.from_path(context, f'/sys/class/net/{ifname}')
        return dict(device.properties)
    except Exception:
        return {}


def discover_devices(sys_class_net: str = '/sys/class/net') -> list:
    """Every interface backed by independently-addressable hardware.

    Skips virtual interfaces, enslaved ones, SR-IOV virtual functions and
    hypervisor VF datapaths - the latter share another interface's MAC.
    """
    devices = []
    net_dir = Path(sys_class_net)
    if not net_dir.is_dir():
        return devices

    for entry in sorted(net_dir.iterdir()):
        if not (entry / 'device').exists():
            continue
        if (entry / 'master').exists():
            continue
        if (entry / 'device' / 'physfn').exists():
            continue
        if entry.name.startswith('vf_'):
            continue

        mac = permanent_mac(entry.name, sys_class_net)
        if not mac:
            continue

        properties = read_properties(entry.name)
        devices.append({
            'name': entry.name,
            'mac': mac,
            'key': hardware_key(properties),
            'wireless': is_wireless(entry.name, sys_class_net),
            'properties': properties,
        })

    return devices


def empty_store() -> dict:
    return {'version': STORE_VERSION, 'interfaces': {}}


def load_store(path: Path = None) -> dict:
    """A missing, unreadable or outdated store yields an empty one, so
    everything is named from scratch.
    """
    path = path or store_path
    try:
        data = json.loads(path.read_text())
    except (FileNotFoundError, OSError, ValueError):
        return empty_store()

    if not isinstance(data, dict) or data.get('version') != STORE_VERSION:
        return empty_store()
    if not isinstance(data.get('interfaces'), dict):
        return empty_store()

    interfaces = {name: key for name, key in data['interfaces'].items()
                  if isinstance(key, str) and key}
    return {'version': STORE_VERSION, 'interfaces': interfaces}


def config_dir_is_mounted(path: Path = None) -> bool:
    """Is the config directory the real one, or a bare rootfs overlay?

    A failed TPM/LUKS unlock does not stop the boot. Writing to the overlay
    underneath would be masked once the real volume mounts, leaving two
    stores which silently diverge.
    """
    path = path or store_path
    return (path.parent / '.vyatta_config').exists()


def save_store(store: dict, path: Path = None) -> bool:
    """Write atomically, so an interrupted boot leaves no half-written file.

    Returns False without writing on a degraded boot: names are still
    resolved for this boot, they just must not be persisted.
    """
    path = path or store_path
    if not config_dir_is_mounted(path):
        return False

    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f'.{path.name}.')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(store, f, indent=2, sort_keys=True)
            f.write('\n')
        os.chmod(tmp, 0o664)
        try:
            os.chown(tmp, -1, get_cfg_group_id())
        except (OSError, KeyError):
            # not fatal, the store is read by root at boot
            pass
        os.replace(tmp, path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise

    return True


def _prefix_for(device: dict) -> str:
    return 'wlan' if device.get('wireless') else 'eth'


def _next_free(taken: set, prefix: str) -> str:
    index = 0
    while f'{prefix}{index}' in taken:
        index += 1
    return f'{prefix}{index}'


def resolve(devices: list, store: dict) -> tuple:
    """Name every physical interface present this boot.

    Returns (plan, new_store, report); plan is {current: new} for the
    interfaces which have to be renamed. The slot decides the name - nothing
    here looks at the configuration, so there is nothing to guess.
    """
    entries = store.get('interfaces', {})

    assigned = {}  # final name -> device
    report = {'matched': {}, 'bootstrapped': {}}

    # A recorded name stays off-limits even while its slot is empty, so new
    # hardware cannot inherit an absent interface's name and configuration.
    reserved = set(entries)
    remaining = list(devices)

    def claim(device, name, bucket):
        assigned[name] = device
        report[bucket][name] = device['mac']
        remaining.remove(device)

    # whatever card occupies the recorded slot is this interface
    for name, key in entries.items():
        for device in remaining:
            if device_matches(device['properties'], key):
                claim(device, name, 'matched')
                break

    # unknown hardware: lowest free name of its type, in hardware order
    for device in sorted(remaining, key=canonical_sort_key):
        name = _next_free(reserved | set(assigned), _prefix_for(device))
        claim(device, name, 'bootstrapped')

    # keep entries for empty slots - an unplugged card keeps its name
    new_interfaces = dict(entries)
    for name, device in assigned.items():
        if device['key']:
            new_interfaces[name] = device['key']

    plan = {device['name']: name for name, device in assigned.items()
            if device['name'] != name}

    return plan, {'version': STORE_VERSION, 'interfaces': new_interfaces}, report


LINK_DIR = Path('/etc/systemd/network')
LINK_PREFIX = '10-vyos-'


def render_link(name: str, key: str) -> str:
    """Render a systemd .link file body, matching on the stored property."""
    return (
        '# Generated by VyOS - do not edit.\n'
        "# Interface names are managed via 'interface-mapping.json'.\n"
        '[Match]\n'
        'Type=ether\n'
        f'Property={key}\n'
        '\n'
        '[Link]\n'
        f'Name={name}\n'
    )


def sync_link_files(store: dict, link_dir: Path = None) -> list:
    """One .link file per recorded name, so udev applies it as the device is
    added - before anything can observe a probe-order name.
    """
    link_dir = link_dir or LINK_DIR
    link_dir.mkdir(parents=True, exist_ok=True)

    written = {}
    for name, key in store.get('interfaces', {}).items():
        if key:
            written[link_dir / f'{LINK_PREFIX}{name}.link'] = render_link(name, key)

    for path, body in written.items():
        if path.exists() and path.read_text() == body:
            continue
        path.write_text(body)

    # drop stale files, but only our own generated ones
    for existing in link_dir.glob(f'{LINK_PREFIX}*.link'):
        if existing not in written:
            existing.unlink(missing_ok=True)

    return sorted(written)
