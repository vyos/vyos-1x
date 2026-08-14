#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Single authoritative pass that enforces "interfaces/{ethernet,wireless}/
# */hw-id" from config.boot onto the live system. It runs once, after udev
# has settled, and decides names from a fully-formed view of the hardware
# instead of reacting to individual "add" uevents.
#
# The old udev-time approach (src/udev/vyos_net_name, invoked straight from
# a udev rule) decided the final, hw-id based name from a single sysfs
# snapshot taken at the moment one interface's "add" event was evaluated.
# On systems with several different NIC vendors/drivers that snapshot is
# unreliable: the DRIVERS attribute walk-up and the interface's permanent
# MAC address are not guaranteed to be populated yet, and neither gets a
# second chance since each uevent is only evaluated once. This script
# sidesteps that by re-reading live state after hardware has had time to
# settle, and by verifying/repairing the outcome rather than guessing once.

import json
import logging
import logging.handlers
import re
import tempfile
import time
from pathlib import Path
from sys import exit

from vyos.configtree import ConfigTree
from vyos.defaults import directories
from vyos.migrate import ConfigMigrate
from vyos.utils.process import rc_cmd
from vyos.utils.process import run

# Bounded wait for all configured hw-id hardware to appear. NICs needing a
# longer firmware/link-training window are rare enough that this has not
# been exposed as a CLI knob yet.
HARDWARE_WAIT_TIMEOUT = 10
HARDWARE_WAIT_POLL = 0.25

# Bounded wait for hardware without a configured hw-id to settle before
# bootstrap-naming it. There is no specific MAC to wait for here, so
# "N consecutive identical snapshots" stands in for "hardware has stopped
# registering/renaming interfaces".
HARDWARE_SETTLE_TIMEOUT = 10
HARDWARE_SETTLE_STABLE_POLLS = 3

config_path = '/opt/vyatta/etc/config/config.boot'
vyos_udev_dir = directories['vyos_udev_dir']
status_file = Path('/run/vyos-net-name-resolve.json')

logger = logging.getLogger()


def _load_config_boot() -> ConfigTree:
    """Parse config.boot into a ConfigTree, migrating stale syntax if
    needed. Returns None if there is no persisted config yet (livecd/ISO).
    """
    if not Path(config_path).is_file():
        return None

    try:
        config_file = Path(config_path).read_text()
    except OSError as e:
        logger.critical(f'OSError {e}')
        exit(1)

    try:
        return ConfigTree(config_file)
    except Exception:
        try:
            logger.debug('updating component version string syntax')
            # this will update the component version string syntax,
            # required for updates 1.2 --> 1.3/1.4
            with tempfile.NamedTemporaryFile() as fp:
                Path(fp.name).write_text(config_file)
                config_migrate = ConfigMigrate(fp.name)
                if config_migrate.syntax_update_needed():
                    config_migrate.update_syntax()
                    config_migrate.write_config()
                config_file = Path(fp.name).read_text()

            return ConfigTree(config_file)
        except Exception as e:
            logger.critical(f'ConfigTree error: {e}')
            exit(1)


def get_configfile_interfaces() -> dict:
    """Read hw-id -> name mapping for ethernet/wireless from config.boot"""
    interfaces: dict = {}

    config = _load_config_boot()
    if config is None:
        return interfaces

    for base in (['interfaces', 'ethernet'], ['interfaces', 'wireless']):
        if not config.exists(base):
            continue
        for intf in config.list_nodes(base):
            path = base + [intf, 'hw-id']
            if not config.exists(path):
                logger.warning(f"no 'hw-id' entry for {intf}")
                continue
            hwid = config.return_value(path).lower()
            if hwid in interfaces:
                logger.warning(
                    f'multiple entries for {hwid}: {interfaces[hwid]}, {intf}'
                )
                continue
            interfaces[hwid] = intf

    logger.debug(f'config file entries: {interfaces}')
    return interfaces


def get_pending_hwid_nodes() -> dict:
    """Interface nodes that exist under interfaces/{ethernet,wireless} in
    config.boot but have no 'hw-id' leaf - e.g. the documented "NIC
    replaced" remediation (`delete interfaces ethernet eth1 hw-id`)
    intentionally leaves the node (and its other settings, like address)
    in place, expecting the SAME node to receive a fresh hw-id. These
    names have no known MAC yet - that is the point - so they cannot be
    folded into get_configfile_interfaces()'s MAC-keyed dict; they are
    surfaced here, grouped by type, so main() can try to match them to
    this boot's unconfigured hardware (see match_pending_nodes()).
    """
    pending = {'ethernet': set(), 'wireless': set()}

    config = _load_config_boot()
    if config is None:
        return pending

    for intf_type, base in (('ethernet', ['interfaces', 'ethernet']),
                             ('wireless', ['interfaces', 'wireless'])):
        if not config.exists(base):
            continue
        for intf in config.list_nodes(base):
            if not config.exists(base + [intf, 'hw-id']):
                pending[intf_type].add(intf)

    return pending


def get_permanent_mac(ifname: str, sys_class_net: str = '/sys/class/net') -> str:
    """Best-effort permanent hardware address of an interface.

    Falls back to the interface's current address if the driver does not
    support reporting a permanent address separately (ethtool -P).

    sys_class_net is overridable for testing against a fake sysfs tree.
    """
    code, out = rc_cmd(f'ethtool -P {ifname}')
    if code == 0:
        m = re.search(r'([0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5})', out)
        if m and m.group(1) != '00:00:00:00:00:00':
            return m.group(1).lower()

    try:
        return Path(f'{sys_class_net}/{ifname}/address').read_text().strip().lower()
    except OSError:
        return ''


def discover_physical_interfaces(sys_class_net: str = '/sys/class/net') -> dict:
    """Return {kernel_name: mac} for every interface backed by a real bus
    device - excludes lo, bridges, bonds, VLANs, veth, tunnels, etc.

    sys_class_net is overridable for testing against a fake sysfs tree.
    """
    interfaces = {}
    net_dir = Path(sys_class_net)
    if not net_dir.is_dir():
        return interfaces

    for entry in net_dir.iterdir():
        if not (entry / 'device').exists():
            continue
        mac = get_permanent_mac(entry.name, sys_class_net)
        if mac:
            interfaces[entry.name] = mac

    return interfaces


def wait_for_hardware(configured_macs: set, timeout: float = HARDWARE_WAIT_TIMEOUT,
                       poll: float = HARDWARE_WAIT_POLL) -> tuple:
    """Poll until every configured hw-id has shown up, or until timeout"""
    deadline = time.monotonic() + timeout
    current = discover_physical_interfaces()
    while True:
        missing = configured_macs - set(current.values())
        if not missing or time.monotonic() >= deadline:
            return current, missing
        time.sleep(poll)
        current = discover_physical_interfaces()


def wait_for_settle(initial: dict, timeout: float = HARDWARE_SETTLE_TIMEOUT,
                     poll: float = HARDWARE_WAIT_POLL,
                     stable_polls: int = HARDWARE_SETTLE_STABLE_POLLS) -> dict:
    """Poll until discover_physical_interfaces() returns the same snapshot
    stable_polls times in a row, or until timeout. Used before bootstrap-
    naming hardware that has no configured hw-id to wait for by MAC.
    """
    deadline = time.monotonic() + timeout
    current = initial
    stable = 1 if current else 0
    while stable < stable_polls and time.monotonic() < deadline:
        time.sleep(poll)
        seen = discover_physical_interfaces()
        stable = stable + 1 if seen == current else 1
        current = seen
    return current


def is_wireless_interface(name: str, sys_class_net: str = '/sys/class/net') -> bool:
    """Race-free wireless check: existence of the phy80211 symlink, not the
    interface's current (possibly still cosmetic/pre-bootstrap) name.
    """
    return (Path(sys_class_net) / name / 'phy80211').exists()


PCI_BDF_RE = re.compile(r'^[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9a-f]$')

# No real hop-count can reach this - reserves it as a sort-last sentinel
# for interfaces whose bus topology can't be determined (USB NICs, or a
# device symlink that doesn't exist/resolve).
PCIE_DISTANCE_UNKNOWN = 999


def pcie_distance(name: str, sys_class_net: str = '/sys/class/net') -> int:
    """Approximate PCIe bus distance from the root complex - counts PCI
    domain:bus:device.function segments (e.g. 0000:00:1f.6) in the fully
    resolved sysfs path of the interface's 'device' symlink. Non-PCI hops
    (virtioN, usbN, the net/<ifname> tail, ...) simply don't match and are
    skipped, so virtio's device->virtioN->real-PCI-parent indirection
    needs no special-casing. Multi-function siblings at the same slot
    contribute exactly one matching segment each, so they are not
    double-counted relative to their shared depth.

    Returns PCIE_DISTANCE_UNKNOWN (sorts after every real hop-count) if
    the 'device' symlink is missing/unresolvable, or the resolved path
    has no PCI BDF segment at all (e.g. a USB NIC).
    """
    device_link = Path(sys_class_net) / name / 'device'
    try:
        resolved = device_link.resolve(strict=True)
    except (OSError, RuntimeError):
        return PCIE_DISTANCE_UNKNOWN

    hops = sum(1 for part in resolved.parts if PCI_BDF_RE.match(part))
    return hops if hops > 0 else PCIE_DISTANCE_UNKNOWN


def find_available(names: set, prefix: str) -> str:
    """Find the lowest free index for a given interface name prefix"""
    index_list = []
    for name in names:
        if not name.startswith(prefix):
            continue
        suffix = name[len(prefix):]
        if suffix.isdigit():
            index_list.append(int(suffix))

    if not index_list:
        return f'{prefix}0'

    index_list.sort()
    # find 'holes' in list, if any
    missing = sorted(set(range(index_list[0], index_list[-1])) - set(index_list))
    if missing:
        return f'{prefix}{missing[0]}'

    return f'{prefix}{index_list[-1] + 1}'


def find_next_available(names: set, prefix: str, floor: int = 0) -> str:
    """Find the lowest free index for a prefix, scanning up from floor.

    Unlike find_available(), this always starts the scan at floor (0 by
    default) rather than at the lowest index already present in `names` -
    used for bootstrap naming, where a gap must be backfillable even when
    it sits below every other index currently in `names` (e.g. `names`
    contains only 'eth5' and 'eth9', but 'eth0'..'eth4' and 'eth6'..'eth8'
    are genuinely free). A slot only stays unavailable here because it is
    explicitly present in `names` - the caller decides what belongs there
    (configured hw-id targets, pending nodes, ...), not this function.
    """
    n = floor
    while f'{prefix}{n}' in names:
        n += 1
    return f'{prefix}{n}'


def compute_rename_plan(configured: dict, current: dict, pending: dict = None) -> dict:
    """Build {from_name: to_name} for every interface that needs to move to
    its CLI hw-id name. Also relocates any interface that currently squats
    on a name owned by a different hw-id, so the rightful owner can take it.
    """
    plan = {}
    current_by_mac = {mac: name for name, mac in current.items()}
    target_owner_mac = {name: mac for mac, name in configured.items()}

    for mac, target in configured.items():
        source = current_by_mac.get(mac)
        if source and source != target:
            plan[source] = target

    unchanged = set(current) - set(plan)
    # every configured target is reserved, even one whose hw-id hasn't
    # shown up yet this boot (missing/faulty/slow driver) - a squatter must
    # never be relocated onto a name that hardware still owns, or it would
    # just need relocating again the moment that hardware actually appears.
    # A pending (hw-id-less but still-configured) node name is reserved the
    # same way: it may be about to be reclaimed by the exact NIC that just
    # vacated it (see match_pending_nodes()), and even when it isn't, its
    # other settings (address, description, ...) are still live in
    # config.boot and must not be handed to an unrelated squatter.
    reserved = set(configured.values())
    if pending:
        reserved |= pending.get('ethernet', set()) | pending.get('wireless', set())

    for name, mac in current.items():
        if name in plan:
            continue
        owner_mac = target_owner_mac.get(name)
        if owner_mac is not None and owner_mac != mac:
            prefix = re.sub(r'\d+$', '', name) or name
            taken = unchanged | set(plan.values()) | set(plan.keys()) | reserved
            new_name = find_available(taken, prefix)
            plan[name] = new_name
            unchanged.discard(name)

    return plan


def unmatched_candidates(configured: dict, current: dict, existing_plan: dict) -> list:
    """Physical interfaces this boot with no configured hw-id - the pool
    both ordinary bootstrap naming and pending-node reclaim matching draw
    from. This deliberately INCLUDES squatters compute_rename_plan() is
    already evicting from a configured target name: excluding them here
    let their mac skip match_pending_nodes() entirely, so an unconfigured
    NIC that happened to be squatting on someone else's hw-id slot could
    silently get a permanent, possibly-ambiguous hw-id via ordinary
    bootstrap naming instead of being reclaimed or held back like any
    other unconfigured candidate. Their eviction destination from
    existing_plan still stands as the fallback - match_pending_nodes()
    (via main()'s reclaim loop) or compute_bootstrap_plan() only override
    it, they never leave a squatter un-evicted.
    """
    return [(mac, name) for name, mac in current.items()
            if mac not in configured]


def compute_bootstrap_plan(configured: dict, current: dict, existing_plan: dict) -> dict:
    """Build {from_name: to_name} for physical interfaces that have no
    configured hw-id at all, assigning them a canonical name within their
    type group (ethernet/wireless) ordered by PCIe distance from the root
    complex first and MAC address as a tie-break, instead of leaving them
    at whatever name the racy udev-time fast path produced. Ordering by
    topology rather than raw MAC magnitude means an onboard/directly
    CPU-attached NIC isn't sorted after add-in cards just because its MAC
    happens to be numerically higher. This is what makes a box's very
    first boot - before any hw-id exists - just as deterministic as every
    boot after hw-id is written (PCIe wiring and MAC are both static
    hardware properties), since the name assigned here gets frozen into
    config.boot by vyos-interface-rescan.py the same way a real hw-id
    match would.

    A pending node's name (hw-id deleted, node kept - see
    get_pending_hwid_nodes()) is treated as just another available slot
    here, exactly like a numeric gap - not reserved for it specifically.
    That is what lets a pending node recover its OWN original hardware
    whenever it and some other now-unclaimed NIC become free in the same
    boot (e.g. a different interface's config was fully deleted at the
    same time): PCIe distance and MAC are static per-NIC properties, so
    the relative sort order among any subset of NICs is identical on
    every boot. Removing whichever NICs stay configured from that fixed
    order leaves the rest in the same relative order they always had -
    which, since a box's very first boot assigns names by this exact
    sort, is precisely each one's original slot. No pending-node-specific
    matching logic is needed for this to hold; it falls out of sorting
    the same way every time. main() attributes a resulting name back to
    a "reclaim" after the fact by checking it against `pending`'s node
    names - see there.

    existing_plan is the hw-id based plan already computed by
    compute_rename_plan(): its RIGHTFUL-OWNER targets (an interface moving
    to its own configured hw-id name) are reserved so a bootstrap name can
    never collide with a configured one. A squatter compute_rename_plan()
    is evicting from a configured target IS still bootstrap candidacy here
    (see unmatched_candidates()) - its OWN eviction destination is only a
    provisional fallback that this function is about to recompute for it
    from scratch, so that value must not also count as "taken" (it would
    needlessly block a lower slot the unified ascending fill might
    otherwise give it, or another candidate, once real).

    A numeric slot is only ever off-limits here because a real, currently
    configured hw-id target still occupies or reserves it. A gap left by
    fully deleting an interface's config, or a pending node whose hw-id
    alone was deleted, carry no such reservation and are freely (and
    identically) backfilled - there is no remaining signal in config.boot
    to treat those two cases differently, and either way the admin's own
    action is what freed the slot.
    """
    plan = {}
    candidates = unmatched_candidates(configured, current, existing_plan)
    if not candidates:
        return plan

    candidate_names = {name for _, name in candidates}
    # a plan entry whose source IS one of this function's own candidates
    # is a squatter's provisional eviction fallback, about to be
    # recomputed below - only a rightful-owner move's target is a real,
    # authoritative reservation
    rightful_movers = {src: target for src, target in existing_plan.items()
                        if src not in candidate_names}
    # a rightful mover's CURRENT (source) name looks occupied right now,
    # but safe_bulk_rename()'s two-phase scratch-name staging vacates it
    # before any target name is actually claimed - so it must not count
    # as taken here either, or a candidate that belongs there (e.g. a
    # pending node whose name happens to be some other configured mac's
    # racy cosmetic position this boot) gets pushed to a fresh slot
    # instead for no reason.
    taken = (set(current) - candidate_names - set(rightful_movers)) \
        | set(rightful_movers.values())

    for mac, name in sorted(candidates, key=lambda c: (pcie_distance(c[1]), c[0])):
        prefix = 'wlan' if is_wireless_interface(name) else 'eth'
        new_name = find_next_available(taken, prefix)
        taken.add(new_name)
        if new_name != name:
            plan[name] = new_name

    return plan


def get_ifindex(name: str) -> str:
    try:
        return Path(f'/sys/class/net/{name}/ifindex').read_text().strip()
    except OSError:
        return name


def rename_interface(old: str, new: str) -> bool:
    run(f'ip link set dev {old} down')
    code = run(f'ip link set dev {old} name {new}')
    if code != 0:
        logger.error(f"failed to rename '{old}' -> '{new}' (exit {code})")
        return False
    logger.info(f"renamed '{old}' -> '{new}'")
    return True


def safe_bulk_rename(plan: dict) -> dict:
    """Two-phase rename: stage every interface via a unique scratch name
    (derived from its ifindex, which is always unique) before assigning
    final names. This makes the whole batch collision-proof regardless of
    permutations/cycles between current and target names - a straight
    from->to rename can fail if the target name is still held by another
    interface earlier/later in the same plan.
    """
    if not plan:
        return {}

    applied = {}
    scratch = {}
    for old, target in plan.items():
        tmp = f'vyeth{get_ifindex(old)}'
        if rename_interface(old, tmp):
            scratch[tmp] = (old, target)
            applied[old] = target

    for tmp, (old, target) in scratch.items():
        if rename_interface(tmp, target):
            run(f'ip link set dev {target} up')
        else:
            # still sitting under the scratch name, not the target - don't
            # report it as renamed, and don't leave it down indefinitely
            del applied[old]
            run(f'ip link set dev {tmp} up')

    return applied


def sync_rescan_hints(current_state: dict, configured: dict,
                       stale_names: set = frozenset()) -> None:
    """Leave a hint under vyos_udev_dir for every interface that has no
    hw-id configured yet, so vyos-interface-rescan.py can auto-populate
    config.boot. Remove stale/no-longer-hw-id-needed hints.
    """
    try:
        Path(vyos_udev_dir).mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.critical(f'error creating rescan hint directory: {e}')
        return

    for name, mac in current_state.items():
        hint = Path(vyos_udev_dir) / name
        if mac in configured:
            hint.unlink(missing_ok=True)
        else:
            try:
                hint.write_text(mac)
            except OSError as e:
                logger.error(f'could not write rescan hint for {name}: {e}')

    for old_name in stale_names:
        if old_name not in current_state:
            (Path(vyos_udev_dir) / old_name).unlink(missing_ok=True)


def write_status(configured: dict, found: dict, missing: set, plan: dict,
                  pending: dict = None, reclaimed: dict = None,
                  candidates: list = None) -> None:
    """candidates is the full unmatched_candidates() list evaluated this
    boot (before reclaim/bootstrap assignment) - surfaced here so a
    pending node left unresolved for lack of hardware is self-diagnosable
    from this one file: 'pending_unresolved' names what needed a match,
    'unconfigured_candidates' names every physical interface that was in
    the running for one, without needing a separate `ip -br link show` or
    `show configuration commands` to reconstruct the same picture by hand.
    """
    pending = pending or {}
    reclaimed = reclaimed or {}
    candidates = candidates or []
    all_pending = pending.get('ethernet', set()) | pending.get('wireless', set())
    status = {
        'configured': configured,
        'found': sorted(found.values()),
        'missing': {mac: configured[mac] for mac in sorted(missing)},
        'renamed': plan,
        'pending_unresolved': sorted(all_pending - set(reclaimed.values())),
        'reclaimed': reclaimed,
        'unconfigured_candidates': {name: mac for mac, name in candidates},
    }
    try:
        status_file.write_text(json.dumps(status, indent=2))
    except OSError as e:
        logger.error(f'could not write status file: {e}')


def main():
    configured = get_configfile_interfaces()
    pending = get_pending_hwid_nodes()

    if configured:
        current, missing = wait_for_hardware(set(configured))
        for mac in sorted(missing):
            logger.warning(
                f"hw-id '{mac}' configured as '{configured[mac]}' was not found "
                f'within {HARDWARE_WAIT_TIMEOUT}s - hardware may be missing, '
                'still initializing, or its driver failed to load'
            )
        plan = compute_rename_plan(configured, current, pending)
    else:
        logger.info('no hw-id configured yet')
        current, missing, plan = discover_physical_interfaces(), set(), {}

    all_pending = pending.get('ethernet', set()) | pending.get('wireless', set())

    candidates = []
    if all_pending or any(mac not in configured for mac in current.values()):
        # bootstrap-name whatever has no hw-id match, deterministically by
        # PCIe distance and MAC, instead of leaving it at its racy cosmetic
        # udev-time name - this is what vyos-interface-rescan.py will
        # freeze into config.boot. A NIC that just lost its hw-id (the
        # documented "delete hw-id to force regeneration" remediation)
        # competes for this same ascending fill exactly like a numeric
        # gap does - see compute_bootstrap_plan() for why that recovers
        # its own original hardware rather than an arbitrary one.
        #
        # The `all_pending` half of this condition matters even when
        # `current` (from wait_for_hardware() above, bounded only on
        # already-CONFIGURED macs) shows nothing unconfigured yet: on a
        # system with several different NIC vendors/drivers, the exact
        # hardware a pending node needs can simply not have finished
        # probing at this snapshot. Without this, wait_for_settle() below
        # would never even run, giving that slower hardware zero extra
        # time to appear before this boot gives up on the pending node.
        current = wait_for_settle(current)
        candidates = unmatched_candidates(configured, current, plan)
        plan.update(compute_bootstrap_plan(configured, current, plan))

    # attribute any candidate that landed on a pending node's name back to
    # that node - so its rescan hint lands there and vyos-interface-
    # rescan.py can write the real hw-id into the node's existing settings
    # (address, description, ...) - and warn about any pending node still
    # without a hw-id after this pass (a candidate may have existed and
    # landed on a lower-numbered unrelated slot instead - this is not
    # necessarily a hardware shortage).
    reclaimed = {}
    for mac, name in candidates:
        final_name = plan.get(name, name)
        if final_name in all_pending:
            reclaimed[mac] = final_name
            logger.info(
                f"reclaiming pending node '{final_name}' for hw-id '{mac}' "
                'this boot'
            )
    for name in sorted(all_pending - set(reclaimed.values())):
        logger.warning(
            f"pending node '{name}' still has no hw-id after this boot's "
            'naming pass'
        )

    applied = safe_bulk_rename(plan)

    final_current = discover_physical_interfaces()
    # configured is passed unmutated (not merged with `reclaimed`): the
    # reclaimed mac still has no real hw-id in config.boot yet, so it must
    # still get a rescan hint under its (now reclaimed) name, letting
    # vyos-interface-rescan.py write the hw-id into the existing node.
    sync_rescan_hints(final_current, configured, set(applied.keys()))
    write_status(configured, current, missing, applied,
                 pending=pending, reclaimed=reclaimed, candidates=candidates)


if __name__ == '__main__':
    syslog_handler = logging.handlers.SysLogHandler(address='/dev/log')
    formatter = logging.Formatter(f'{Path(__file__).name}: %(message)s')
    syslog_handler.setFormatter(formatter)

    logger.addHandler(syslog_handler)
    logger.setLevel(logging.DEBUG)

    main()
