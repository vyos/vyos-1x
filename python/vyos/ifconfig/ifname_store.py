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


def ambiguous_keys(devices: list) -> set:
    """Property values carried by more than one device."""
    seen = {}
    for properties in devices:
        for prop in KEY_PROPERTIES:
            value = properties.get(prop, '')
            if value:
                tmp = f'{prop}={value}'
                seen[tmp] = seen.get(tmp, 0) + 1
    return {key for key, count in seen.items() if count > 1}


def hardware_key(properties: dict, ambiguous: set = frozenset()) -> str:
    """The most stable identifier this device offers, as 'PROPERTY=value'.

    A value more than one device carries identifies neither of them, so it is
    passed over for the next one.
    """
    for prop in KEY_PROPERTIES:
        value = properties.get(prop, '')
        if value and f'{prop}={value}' not in ambiguous:
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


def recorded_mac(ifname: str) -> str:
    """The address naming recorded for this name. It outlives a dataplane
    taking the port over, which leaves nothing in sysfs to read it from.
    """
    return load_store().get('hardware', {}).get(ifname, '')


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

    Wireless is skipped too, and not because it is uninteresting: a radio's
    interfaces are created from the configuration on a given phy, and every
    one of them carries that phy's address. They are indistinguishable here,
    so a name recorded against one would be applied to whichever appeared
    next - renaming an interface the operator had just asked for by name.
    Wireless names come from the configuration; nothing to anchor.
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
        if is_wireless(entry.name, sys_class_net):
            continue

        mac = permanent_mac(entry.name, sys_class_net)
        if not mac:
            continue

        devices.append({
            'name': entry.name,
            'mac': mac,
            'wireless': is_wireless(entry.name, sys_class_net),
            'properties': read_properties(entry.name),
        })

    ambiguous = ambiguous_keys([device['properties'] for device in devices])
    for device in devices:
        device['key'] = hardware_key(device['properties'], ambiguous)

    return devices


def empty_store() -> dict:
    return {'version': STORE_VERSION, 'interfaces': {}, 'hardware': {}}


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
                  if isinstance(key, str) and key
                  and not name.startswith('wlan')}

    # the card each name last sat on. Absent from a store written before this
    # was recorded, which just means the first pass has nothing to compare
    # against and reports no replacement - not that nothing changed.
    seen = data.get('hardware')
    hardware = {name: mac for name, mac in seen.items()
                if isinstance(mac, str) and mac and name in interfaces
                } if isinstance(seen, dict) else {}

    return {'version': STORE_VERSION, 'interfaces': interfaces,
            'hardware': hardware}


def encrypted_config_volume() -> bool:
    """Does this image keep its configuration on a LUKS volume?

    Mirrors mount_encrypted_config() in src/init/vyos-router - a container
    named after the running image, below the persistence path. Anything that
    cannot be determined (no persistence, no version file, not a VyOS system
    at all) means there is no volume waiting to be mounted over the config
    directory.
    """
    try:
        from vyos.system.image import get_running_image

        code, out = rc_cmd('/opt/vyatta/sbin/vyos-persistpath')
        if code != 0 or not out.strip():
            return False
        image = get_running_image()
        return bool(image) and (Path(out.strip()) / 'luks' / image).is_file()
    except Exception:
        return False


def config_dir_is_mounted(path: Path = None) -> bool:
    """Will a store written here still be there on the next boot?

    Only an encrypted configuration has a volume which may still be locked:
    a failed TPM/LUKS unlock does not stop the boot, and writing to the
    directory underneath would be masked once the real volume mounts,
    leaving two stores which silently diverge. Everywhere else the directory
    is already the persistent one.

    Deliberately not keyed on '.vyatta_config'. That marker is an
    install-time hint, written by an activation script which runs *after*
    interface naming - so on the first boot of a pre-built image it does not
    exist yet, no store is ever written, and the next boot names the
    hardware from scratch. Removing a card then shifts every name below it
    onto the wrong port (T3871).
    """
    path = path or store_path
    if not encrypted_config_volume():
        return True
    return os.path.ismount(path.parent)


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
    seen = store.get('hardware', {})

    assigned = {}  # final name -> device
    report = {'matched': {}, 'moved': {}, 'replaced': {}, 'bootstrapped': {}}

    # A recorded name stays off-limits even while its slot is empty, so new
    # hardware cannot inherit an absent interface's name and configuration.
    reserved = set(entries)
    remaining = list(devices)

    def claim(device, name, bucket):
        assigned[name] = device
        report[bucket][name] = device['mac']
        remaining.remove(device)

    # the recorded card in its recorded slot. A name with no card on record
    # counts too - a store written before addresses were kept has nothing to
    # disagree with, and this is as certain as it gets.
    for name, key in entries.items():
        for device in remaining:
            if (device_matches(device['properties'], key)
                    and seen.get(name, device['mac']) == device['mac']):
                claim(device, name, 'matched')
                break

    # a card the store already knows about, sitting in this name's slot. The
    # cards were rearranged among themselves, or the map was edited by hand -
    # either way the map is what decides names, so the slot wins and the
    # address on record simply follows.
    known = {mac for mac in seen.values() if mac}
    for name, key in entries.items():
        if name in assigned:
            continue
        for device in remaining:
            if (device_matches(device['properties'], key)
                    and device['mac'] in known):
                claim(device, name, 'matched')
                break

    # the card moved, and nothing the store knows took its place. Its address
    # identifies it, so the name follows the card rather than being handed to
    # a stranger that happens to have landed in the slot it left.
    for name in entries:
        if name in assigned or not seen.get(name):
            continue
        for device in remaining:
            if device['mac'] == seen[name]:
                claim(device, name, 'moved')
                break

    # a different card in the recorded slot: an in-place replacement, or an
    # unrelated card that happened to land there once the original was pulled.
    # Nothing on the device tells those apart, so the slot decides and it is
    # reported and warned about rather than taken silently.
    for name, key in entries.items():
        if name in assigned:
            continue
        for device in remaining:
            if device_matches(device['properties'], key):
                claim(device, name, 'replaced')
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

    # remember which card each name sat on, keeping the last record for an
    # absent one so its eventual replacement is still noticed
    new_hardware = dict(seen)
    for name, device in assigned.items():
        if device['mac']:
            new_hardware[name] = device['mac']

    plan = {device['name']: name for name, device in assigned.items()
            if device['name'] != name}

    return plan, {'version': STORE_VERSION, 'interfaces': new_interfaces,
                  'hardware': new_hardware}, report


LINK_DIR = Path('/etc/systemd/network')
LINK_PREFIX = '10-vyos-'


def render_link(name: str, key: str) -> str:
    """Render a systemd .link file body, matching on the stored property.

    The device type has to match as well, and a radio is 'wlan' - a .link
    naming a type the device is not simply never applies, leaving the
    interface on its probe-order name. resolve() already names by type (see
    _prefix_for()), so the recorded name is what says which.
    """
    return (
        '# Generated by VyOS - do not edit.\n'
        "# Interface names are managed via 'interface-mapping.json'.\n"
        '[Match]\n'
        f"Type={'wlan' if name.startswith('wlan') else 'ether'}\n"
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
        # never for a radio: the key is the phy's address, which every
        # interface created on that phy shares, so the file would rename
        # whichever of them udev saw next
        if key and not name.startswith('wlan'):
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
