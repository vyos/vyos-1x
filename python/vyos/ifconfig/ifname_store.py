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
# ESXi labels its adapters Ethernet0..EthernetN, in "Network adapter N" order
_PORT_LABEL = re.compile(r'^Ethernet(\d+)$')
# sorts after every real label, and must stay an int - canonical_sort_key()
# compares tuples element-wise, so a None here would raise against an int
_LABEL_UNKNOWN = 1 << 30
_VMWARE_PCI_VENDOR = '0x15ad'
# a Hyper-V NIC carries no slot, path or label of its own - only its MAC
_HYPERV_DRIVER = 'hv_netvsc'
_DMI_SYS_VENDOR = Path('/sys/class/dmi/id/sys_vendor')
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
    """Total order by bus class, the hypervisor's adapter order where it says
    so, then physical position and MAC, so it never depends on probe order.
    Only used for hardware not yet in the store.
    """
    properties = device.get('properties') or {}
    path = properties.get('ID_PATH', '')
    rank = _BUS_RANK.get(properties.get('ID_BUS', ''), _BUS_RANK_UNKNOWN)

    # a labelled adapter outranks the PCI address, which on ESXi does not
    # follow the order the adapters were added in. Unlabelled hardware sorts
    # after it: a passthrough NIC is not part of the hypervisor's own set and
    # must not take the first name from it.
    label = device.get('label_index', _LABEL_UNKNOWN)

    # numeric, so 0000:09:00.0 sorts before 0000:10:00.0
    segments = [tuple(int(part, 16) for part in m.groups())
                for m in _PCI_BDF.finditer(path)]

    return (rank, label, segments, path, device.get('mac') or '')


def is_hyperv_nic(device: dict) -> bool:
    properties = device.get('properties') or {}
    return properties.get('ID_NET_DRIVER') == _HYPERV_DRIVER


def _sysfs(path: Path) -> str:
    try:
        return path.read_text().strip()
    except OSError:
        return ''


def is_vmware_nic(ifname: str, sys_class_net: str = '/sys/class/net') -> bool:
    """Whether a NIC is one ESXi presents - vmxnet3 carries VMware's PCI
    vendor, an emulated e1000 carries it as the subsystem vendor.

    The DMI fallback is not redundant: smbios.reflectHost makes a guest report
    the physical host's vendor, and a NIC model whose IDs are not listed here
    would otherwise go unrecognised.
    """
    device = Path(sys_class_net) / ifname / 'device'
    if _VMWARE_PCI_VENDOR in (_sysfs(device / 'vendor'),
                              _sysfs(device / 'subsystem_vendor')):
        return True
    return _sysfs(_DMI_SYS_VENDOR) == 'VMware, Inc.'


def port_label_index(ifname: str, sys_class_net: str = '/sys/class/net') -> int:
    """The hypervisor's adapter number, from the firmware port label.

    ESXi does not lay its adapters out in PCI address order - with four or more
    it places the fourth on a root port which sorts ahead of the first three -
    so the label is the only thing that gives their intended order.

    Returns _LABEL_UNKNOWN when there is no such label. Physical servers label
    ports too, e.g. "NIC1" or "Embedded LOM 1 Port 1", and must not be reordered
    by this.
    """
    m = _PORT_LABEL.match(_sysfs(Path(sys_class_net) / ifname / 'device' / 'label'))
    return int(m.group(1)) if m else _LABEL_UNKNOWN


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


def is_wwan(ifname: str, sys_class_net: str = '/sys/class/net') -> bool:
    """A modem, which the CLI addresses as wwanN. An ethernet port carries no
    DEVTYPE at all, so this is exact - and it is the same property systemd
    matches on in a .link file.
    """
    try:
        uevent = (Path(sys_class_net) / ifname / 'uevent').read_text()
    except OSError:
        return False
    return 'DEVTYPE=wwan' in uevent.split()


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

    Skips virtual interfaces, SR-IOV virtual functions and hypervisor VF
    datapaths - the latter share another interface's MAC.

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
        # a VF datapath is enslaved to the interface it accelerates, which is
        # a device in its own right. A bridge, bond or VRF is not, and its
        # members stay real hardware while they are in it.
        master = entry / 'master'
        if master.exists() and (master / 'device').exists():
            continue
        if (entry / 'device' / 'physfn').exists():
            continue
        if entry.name.startswith('vf_'):
            continue
        if is_wireless(entry.name, sys_class_net):
            continue

        # a modem is given a random address at each probe, so it says nothing
        # about which modem this is - there is nothing here worth recording
        wwan = is_wwan(entry.name, sys_class_net)
        mac = '' if wwan else permanent_mac(entry.name, sys_class_net)
        if not mac and not wwan:
            continue

        devices.append({
            'name': entry.name,
            'mac': mac,
            'wireless': is_wireless(entry.name, sys_class_net),
            'wwan': wwan,
            'label_index': (port_label_index(entry.name, sys_class_net)
                            if is_vmware_nic(entry.name, sys_class_net)
                            else _LABEL_UNKNOWN),
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

    store = {'version': STORE_VERSION, 'interfaces': interfaces, 'hardware': hardware}

    # names whose hardware was missing at the last pass - kept only while
    # there are any, so a store without them reads as it always did
    absent = data.get('absent')
    if isinstance(absent, list):
        absent = sorted({n for n in absent if n in interfaces})
        if absent:
            store['absent'] = absent

    # names whose NIC was a Hyper-V one when last seen - the only names a new
    # Hyper-V NIC may take over. A store without them (written before they
    # were recorded) has none.
    hyperv = data.get('hyperv')
    if isinstance(hyperv, list):
        hyperv = sorted({n for n in hyperv if n in interfaces})
        if hyperv:
            store['hyperv'] = hyperv
    return store


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
    """Write atomically and durably, so a boot cut short leaves either the
    previous names or the new ones, never a half-written file and never a
    rename the disk has not seen.

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
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o664)
        try:
            os.chown(tmp, -1, get_cfg_group_id())
        except (OSError, KeyError):
            # not fatal, the store is read by root at boot
            pass
        os.replace(tmp, path)
        # the rename itself has to reach the disk, or a boot cut short here
        # comes back to the name it had before
        dir_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise

    return True


def _prefix_for(device: dict) -> str:
    if device.get('wwan'):
        return 'wwan'
    return 'wlan' if device.get('wireless') else 'eth'


def _name_fits(name: str, device: dict) -> bool:
    """A name belongs to the namespace the CLI reads it under, so a modem
    can not take an ethernet name nor an ethernet card a modem's.
    """
    return name.startswith(_prefix_for(device))


def _next_free(taken: set, prefix: str) -> str:
    index = 0
    while f'{prefix}{index}' in taken:
        index += 1
    return f'{prefix}{index}'


def resolve(devices: list, store: dict, adopt: bool = True) -> tuple:
    """Name every physical interface present this boot.

    Returns (plan, new_store, report); plan is {current: new} for the
    interfaces which have to be renamed. The slot decides the name - nothing
    here looks at the configuration, so there is nothing to guess.

    adopt=False keeps a vacant Hyper-V name from going to a new NIC, for a
    pass on a running system (see the adoption block below).
    """
    entries = store.get('interfaces', {})
    seen = store.get('hardware', {})

    # a modem an earlier version filed under an ethernet name. The entry still
    # matches it by path, so it would be captured again and stay invisible to
    #'interfaces wwan' - drop it and let it be named as what it is. The name
    # cannot be recognised on its own, and neither can the key: this one reads
    # ID_NET_NAME_PATH=wwp..., but a device falling back to ID_PATH reads
    # usb-... like anything else on that bus.
    misfiled = {name for name, key in entries.items()
                if not name.startswith('wwan')
                and any(d.get('wwan') and device_matches(d['properties'], key)
                        for d in devices)}
    if misfiled:
        entries = {n: k for n, k in entries.items() if n not in misfiled}
        seen = {n: m for n, m in seen.items() if n not in misfiled}

    assigned = {}  # final name -> device
    report = {
        'matched': {},
        'reassigned': {},
        'moved': {},
        'replaced': {},
        'adopted': {},
        'bootstrapped': {},
    }

    # A recorded name stays off-limits even while its slot is empty, so new
    # hardware cannot inherit an absent interface's name and configuration.
    reserved = set(entries)
    remaining = list(devices)
    # what the last pass recorded: names already missing then, and names
    # whose NIC was a Hyper-V one
    missing_before = set(store.get('absent', []))
    hyperv_before = set(store.get('hyperv', []))

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
                    and (not device['mac']
                         or seen.get(name, device['mac']) == device['mac'])
                    and _name_fits(name, device)):
                claim(device, name, 'matched')
                break

    # a card the store already knows about, sitting in this name's slot. The
    # cards were rearranged among themselves, or the map was edited by hand -
    # either way the map is what decides names, so the slot wins and the
    # address on record simply follows. The name changes hands, so it is
    # reported apart from a card which simply stayed where it was.
    known = {mac for mac in seen.values() if mac}
    for name, key in entries.items():
        if name in assigned:
            continue
        for device in remaining:
            if (device_matches(device['properties'], key)
                    and device['mac'] in known
                    and _name_fits(name, device)):
                claim(device, name, 'reassigned')
                break

    # the card moved, and nothing the store knows took its place. Its address
    # identifies it, so the name follows the card rather than being handed to
    # a stranger that happens to have landed in the slot it left.
    for name in entries:
        if name in assigned or not seen.get(name):
            continue
        for device in remaining:
            if device['mac'] == seen[name] and _name_fits(name, device):
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
            if (device_matches(device['properties'], key)
                    and _name_fits(name, device)):
                claim(device, name, 'replaced')
                break

    # a Hyper-V NIC is known by its MAC alone, and one deleted and created
    # again comes back with a new MAC, so nothing on it could match. When one
    # recorded NIC is gone and one new NIC took its place the pairing is not in
    # doubt, and the name goes to it. With more of either it is: the order the
    # NICs come up in here does not say which replaced which, so nothing is
    # handed over and the names stay reserved.
    # Only on the pass the NIC first went missing: a replacement is one change
    # to the VM. A name already missing at the last pass belongs to a NIC that
    # was removed, and a NIC added later is not its replacement.
    # Only at boot: on a running system the configuration under the name is
    # not applied to the NIC that takes it, so the name would point at a port
    # that is down and unaddressed until the next boot. The new NIC gets a new
    # name there, and the vacant one is recorded as missing, so the next boot
    # does not hand it over either.
    # Only a name whose own NIC was a Hyper-V one: a MAC-keyed name can
    # belong to other hardware too, and a store that does not say (written
    # before this was recorded) hands nothing over.
    vacant = [
        name
        for name, key in entries.items()
        if name not in assigned
        and name not in missing_before
        and name in hyperv_before
        and key.startswith('ID_NET_NAME_MAC=')
    ]
    adoptable = [device for device in remaining if is_hyperv_nic(device)]
    if (adopt and len(vacant) == 1 and len(adoptable) == 1
            and _name_fits(vacant[0], adoptable[0])):
        claim(adoptable[0], vacant[0], 'adopted')

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
        else:
            new_hardware.pop(name, None)

    plan = {device['name']: name for name, device in assigned.items()
            if device['name'] != name}

    new_store = {
        'version': STORE_VERSION,
        'interfaces': new_interfaces,
        'hardware': new_hardware,
    }
    absent = sorted(name for name in new_interfaces if name not in assigned)
    if absent:
        new_store['absent'] = absent
    # what each name's NIC was, kept for an absent one like its address
    hyperv = sorted(
        {name for name, device in assigned.items() if is_hyperv_nic(device)}
        | (hyperv_before & set(absent))
    )
    if hyperv:
        new_store['hyperv'] = hyperv

    return plan, new_store, report


LINK_DIR = Path('/etc/systemd/network')
LINK_PREFIX = '10-vyos-'


def _link_type_for(name: str) -> str:
    for prefix in ('wlan', 'wwan'):
        if name.startswith(prefix):
            return prefix
    return 'ether'


def render_link(name: str, key: str, driver: str = '') -> str:
    """Render a systemd .link file body, matching on the stored property.

    The device type has to match as well, and a radio is 'wlan' - a .link
    naming a type the device is not simply never applies, leaving the
    interface on its probe-order name. resolve() already names by type (see
    _prefix_for()), so the recorded name is what says which.

    A MAC is not unique to one interface: an accelerated-networking VF
    carries its NIC's MAC, and matched the NIC's file - udev then tried to
    give the VF the NIC's name. The driver tells them apart.

    Only the first matching file is applied, so this one shadows the address
    policy the distribution ships. Spell it out again, or a device with no
    permanent address - a modem - is left on the random one its driver gave
    it, which is a different address on every boot.
    """
    match_driver = f'Driver={driver}\n' if driver else ''
    return (
        '# Generated by VyOS - do not edit.\n'
        "# Interface names are managed via 'interface-mapping.json'.\n"
        '[Match]\n'
        f'Type={_link_type_for(name)}\n'
        f'Property={key}\n'
        f'{match_driver}'
        '\n'
        '[Link]\n'
        f'Name={name}\n'
        'MACAddressPolicy=persistent\n'
    )


def _pinned_driver(path: Path, key: str) -> str:
    """The driver an existing file already pins for this key, if any"""
    try:
        body = path.read_text()
    except OSError:
        return ''
    if f'Property={key}\n' not in body:
        return ''
    m = re.search(r'^Driver=(\S+)$', body, re.M)
    return m.group(1) if m else ''


def sync_link_files(store: dict, link_dir: Path = None, devices: list = None) -> list:
    """One .link file per recorded name, so udev applies it as the device is
    added - before anything can observe a probe-order name.
    """
    link_dir = link_dir or LINK_DIR
    link_dir.mkdir(parents=True, exist_ok=True)

    # a Hyper-V NIC shares its MAC with its accelerated-networking VF, so
    # its file names the driver too - also when the NIC is keyed on the VMBus
    # path, as a lone one is. A NIC absent this boot cannot say which, and
    # keeps the pin its file already carries.
    drivers = {}
    for device in devices or []:
        key = device.get('key') or ''
        if key and is_hyperv_nic(device):
            drivers[key] = _HYPERV_DRIVER

    written = {}
    for name, key in store.get('interfaces', {}).items():
        # never for a radio: the key is the phy's address, which every
        # interface created on that phy shares, so the file would rename
        # whichever of them udev saw next
        if key and not name.startswith('wlan'):
            path = link_dir / f'{LINK_PREFIX}{name}.link'
            driver = drivers.get(key) or _pinned_driver(path, key)
            written[path] = render_link(name, key, driver)

    for path, body in written.items():
        if path.exists() and path.read_text() == body:
            continue
        path.write_text(body)

    # drop stale files, but only our own generated ones
    for existing in link_dir.glob(f'{LINK_PREFIX}*.link'):
        if existing not in written:
            existing.unlink(missing_ok=True)

    return sorted(written)
