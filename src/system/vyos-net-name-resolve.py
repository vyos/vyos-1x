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
#
# The pass runs in three stages: move interfaces to their configured hw-id
# names (compute_rename_plan), let hw-id-less config nodes reclaim their
# own hardware (match_pending_nodes), then name whatever is left
# (compute_bootstrap_plan). Each rule here was added for a specific field
# report; the reasoning lives in the test that pins it, in
# src/tests/test_net_name_resolve.py, where it cannot drift unnoticed.

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
    """{'ethernet': names, 'wireless': names} for config.boot nodes with
    no 'hw-id' leaf - the "NIC replaced" remediation deletes only the
    hw-id, keeping the node and its address for the same port to reclaim.

    They have no known MAC by definition, so they cannot go in
    get_configfile_interfaces()' MAC-keyed dict; match_pending_nodes()
    tries to pair them with hardware instead.
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


def pending_names(pending: dict) -> set:
    """Every pending node name, both types together."""
    if not pending:
        return set()
    return pending.get('ethernet', set()) | pending.get('wireless', set())


def get_permanent_mac(ifname: str, sys_class_net: str = '/sys/class/net') -> str:
    """Best-effort permanent hardware address of an interface.

    Falls back to the interface's current address when the driver cannot
    report a permanent one (ethtool -P).

    sys_class_net redirects the sysfs fallback only; the ethtool branch
    always queries the real host.
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
    """{kernel_name: mac} for interfaces backed by a real bus device -
    excludes lo, bridges, bonds, VLANs, veth, tunnels and the like.

    Also excludes anything enslaved to another netdev (master symlink),
    which covers Azure VF datapath interfaces: acceleration children of
    their synthetic parent, never hw-id naming candidates.  T8329
    """
    interfaces = {}
    net_dir = Path(sys_class_net)
    if not net_dir.is_dir():
        return interfaces

    for entry in net_dir.iterdir():
        if not (entry / 'device').exists():
            logger.debug(
                f"skipping '{entry.name}': no backing device in sysfs"
            )
            continue
        if (entry / 'master').exists():
            logger.debug(
                f"skipping '{entry.name}': interface is enslaved via master link"
            )
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
    """Poll until discover_physical_interfaces() repeats stable_polls
    times, or timeout. Stands in for "hardware stopped appearing" when
    there is no specific MAC to wait for.
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
    """Wireless check by phy80211 symlink, never by name - the name may
    still be a provisional one at this point.
    """
    return (Path(sys_class_net) / name / 'phy80211').exists()


PCI_BDF_RE = re.compile(r'^([0-9a-f]{4}):([0-9a-f]{2}):([0-9a-f]{2})\.([0-9a-f])$')

# No real hop-count can reach this - reserves it as a sort-last sentinel
# for interfaces whose bus topology can't be determined (a device symlink
# that doesn't exist/resolve, or a bus with no PCI ancestor at all).
PCIE_DISTANCE_UNKNOWN = 999

# Every field at its maximum, so it sorts after any real address. It must
# not be the empty tuple: that would sort FIRST.
PCIE_ADDRESS_UNKNOWN = ((0xffff, 0xff, 0xff, 0xf),)


def _device_bdfs(name: str, sys_class_net: str = '/sys/class/net') -> list:
    """Ordered (domain, bus, device, function) tuples for every PCI segment
    on the interface's resolved 'device' symlink, root complex first.
    Non-PCI hops (virtioN, usbN, ...) don't match and are skipped, so
    virtio's device->virtioN->PCI-parent indirection needs no special
    case; multi-function siblings differ only in the last function field.

    Returns an empty list if the symlink is missing/unresolvable or the
    resolved path has no PCI BDF segment at all. pcie_distance() and
    pcie_address() both derive from this, so they cannot disagree.
    """
    device_link = Path(sys_class_net) / name / 'device'
    try:
        resolved = device_link.resolve(strict=True)
    except (OSError, RuntimeError):
        return []

    bdfs = []
    for part in resolved.parts:
        m = PCI_BDF_RE.match(part)
        if m:
            bdfs.append(tuple(int(g, 16) for g in m.groups()))
    return bdfs


def pcie_distance(name: str, sys_class_net: str = '/sys/class/net') -> int:
    """Number of PCI segments on the interface's resolved sysfs path, i.e.
    hop depth from the root complex. See _device_bdfs().

    PCIE_DISTANCE_UNKNOWN (sorts last) when the path has no PCI segment at
    all - rarer than it looks, since a USB NIC still resolves through its
    xHCI controller and reports an ordinary depth.
    """
    return len(_device_bdfs(name, sys_class_net)) or PCIE_DISTANCE_UNKNOWN


def pcie_address(name: str, sys_class_net: str = '/sys/class/net') -> tuple:
    """The interface's PCI path as a tuple of BDF tuples, see
    _device_bdfs(). A bus ADDRESS rather than a depth, so it separates two
    devices at the same depth - the usual case in a VM, where the
    hypervisor allocates a slot per NIC in attach order.

    PCIE_ADDRESS_UNKNOWN (sorts last) when there is no PCI segment.
    """
    return tuple(_device_bdfs(name, sys_class_net)) or PCIE_ADDRESS_UNKNOWN


def canonical_sort_key(mac: str, name: str) -> tuple:
    """The single hardware order this script names by. Both
    compute_bootstrap_plan() and match_pending_nodes() use it; if they
    disagreed, one would contradict the other's names.

    Distance leads so an onboard NIC does not sort after add-in cards.
    Within a distance the PCI address decides, giving real slot order
    rather than MAC magnitude, which says nothing about wiring. MAC is the
    last-resort tie-break and the only guaranteed-unique part, so the
    order is total.  T3871
    """
    return (pcie_distance(name), pcie_address(name), mac)


def find_available(names: set, prefix: str, floor: int = None) -> str:
    """Lowest free '<prefix><n>' not in `names`, scanning up from `floor`.

    floor=None starts at the lowest index already present, so an existing
    block of names is only ever extended or hole-filled. Bootstrap naming
    passes floor=0 instead, because a slot below every present index is
    still genuinely free and must be reusable.
    """
    if floor is None:
        indexes = [int(name[len(prefix):]) for name in names
                   if name.startswith(prefix) and name[len(prefix):].isdigit()]
        floor = min(indexes, default=0)

    n = floor
    while f'{prefix}{n}' in names:
        n += 1
    return f'{prefix}{n}'


def compute_rename_plan(configured: dict, current: dict, pending: dict = None) -> dict:
    """{from_name: to_name} moving every interface to its configured hw-id
    name, evicting whatever squats on one so the owner can take it.
    """
    plan = {}
    current_by_mac = {mac: name for name, mac in current.items()}
    target_owner_mac = {name: mac for mac, name in configured.items()}

    for mac, target in configured.items():
        source = current_by_mac.get(mac)
        if source and source != target:
            plan[source] = target

    unchanged = set(current) - set(plan)
    # every configured target is reserved even if its hardware is absent
    # this boot, or a squatter moved there would need moving again the
    # moment it appears. Pending names likewise: their address and
    # description are live and must not go to an unrelated squatter.
    reserved = set(configured.values()) | pending_names(pending)

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


def unmatched_candidates(configured: dict, current: dict) -> list:
    """[(mac, name)] for physical interfaces with no configured hw-id -
    the pool both bootstrap naming and pending-node matching draw from.

    Deliberately includes squatters already being evicted from a
    configured name: hiding them here would let one collect a permanent
    hw-id without ever facing the ambiguity checks.  T3871
    """
    return [(mac, name) for name, mac in current.items()
            if mac not in configured]


def node_name_order(name: str) -> tuple:
    """Numeric, not lexical, name order - 'eth2' before 'eth10'. A name
    with no trailing digits has no position and sorts last.
    """
    m = re.search(r'(\d+)$', name)
    return (0, int(m.group(1)), name) if m else (1, 0, name)


def match_pending_nodes(pending: dict, candidates: list,
                         rules: dict = None) -> dict:
    """Pair this boot's unconfigured candidates with pending (hw-id-less)
    config nodes, one type at a time. The first rule that applies wins;
    if neither does, nothing of that type is matched:

      1. exact cover - as many candidates of this type as pending nodes
      2. name cover  - exactly as many candidates carrying a pending node
                       name as there are pending nodes

    Both pair the same way: nodes by index, hardware by
    canonical_sort_key(). Rule 1 must stay first - a current name only
    SELECTS candidates, it never decides which node one gets, because
    src/udev/vyos_net_name hands out provisional names in probe order
    without reading config.boot.

    Both rules are cardinality-strict: a wrong pairing moves one port's
    address and description onto another port, so ambiguity is logged and
    left pending rather than guessed. Anything that had a permutation to
    get wrong is warned about.

    Fills rules['topology'|'name'] with the nodes each rule resolved.
    Returns {mac: node_name}. See TestMatchPendingNodes for the field
    reports behind each rule.  T3871
    """
    grouped = {'ethernet': [], 'wireless': []}
    for mac, name in candidates:
        group = 'wireless' if is_wireless_interface(name) else 'ethernet'
        grouped[group].append((mac, name))

    if rules is not None:
        rules.setdefault('topology', set())
        rules.setdefault('name', set())

    matched = {}

    def pair(intf_type, nodes, hardware, rule):
        targets = sorted(nodes, key=node_name_order)
        hardware = sorted(hardware, key=lambda c: canonical_sort_key(*c))
        for target, (mac, _name) in zip(targets, hardware):
            matched[mac] = target

        # one node and one candidate selected by name leave no permutation
        # to get wrong, but the selection itself was still a guess - only
        # a lone exact cover is free of both, and only it goes unreported
        if rule == 'name' or len(targets) > 1:
            if rules is not None:
                rules[rule] |= set(targets)
            pairs = ', '.join(
                f"{target} <- {mac} (pci {pcie_address(name)}, now '{name}')"
                for target, (mac, name) in zip(targets, hardware)
            )
            how = ('carry the pending node names this boot'
                   if rule == 'name' else
                   f"exactly cover this boot's unconfigured {intf_type} "
                   'hardware')
            logger.warning(
                f'{len(targets)} pending {intf_type} node(s) - the '
                f'candidates that {how} were paired with them in PCI slot '
                f'order: {pairs} - verify this matches how the ports are '
                'actually wired'
            )

    for intf_type, nodes in pending.items():
        if not nodes:
            continue
        cands = grouped.get(intf_type, [])

        if cands and len(nodes) == len(cands):
            pair(intf_type, nodes, cands, 'topology')
            continue

        by_name = [(mac, name) for mac, name in cands if name in nodes]
        if by_name and len(by_name) == len(nodes):
            pair(intf_type, nodes, by_name, 'name')
            continue

        cand_desc = ', '.join(f"'{name}' ({mac})" for mac, name in cands) or 'none'
        logger.warning(
            f'{len(nodes)} pending {intf_type} node(s) '
            f"({', '.join(sorted(nodes, key=node_name_order))}) and "
            f'{len(cands)} unconfigured {intf_type} candidate(s) this '
            f'boot ({cand_desc}), of which {len(by_name)} carry a pending '
            'node name - neither an exact cover nor a name cover, leaving '
            'pending rather than guessing'
        )

    return matched


def compute_bootstrap_plan(configured: dict, current: dict, existing_plan: dict,
                            pending: dict = None,
                            reclaimed: dict = None) -> dict:
    """{from_name: to_name} for hardware with no configured hw-id, named
    in canonical_sort_key() order per type - so a first boot is as
    deterministic as an hw-id boot, since vyos-interface-rescan.py freezes
    these names into config.boot exactly as it would a real hw-id match.

    A name is off-limits only while something holds it: a configured hw-id
    target, a pending node name, or a reclaim target. A plain numeric gap
    left by deleting a whole node has no holder and is backfilled.

    This pass may never fill a pending name - only match_pending_nodes()
    may, and only under a rule that reports what it did.

    Squatters that existing_plan is evicting ARE candidates here, but
    their provisional eviction target is deliberately not reserved; only
    a rightful owner's target is.  T3871
    """
    plan = {}
    reclaimed = reclaimed or {}
    candidates = unmatched_candidates(configured, current)
    candidates = [(mac, name) for mac, name in candidates
                  if mac not in reclaimed]
    if not candidates:
        return plan

    candidate_names = {name for _, name in candidates}
    # a plan entry sourced from one of our own candidates is a squatter's
    # provisional eviction, recomputed below - not a real reservation
    rightful_movers = {src: target for src, target in existing_plan.items()
                        if src not in candidate_names}
    # a rightful mover's source name is vacated by safe_bulk_rename()'s
    # scratch phase before any target is claimed, so it is not taken
    taken = (set(current) - candidate_names - set(rightful_movers)) \
        | set(rightful_movers.values()) | pending_names(pending) \
        | set(reclaimed.values())

    for mac, name in sorted(candidates, key=lambda c: canonical_sort_key(*c)):
        prefix = 'wlan' if is_wireless_interface(name) else 'eth'
        new_name = find_available(taken, prefix, floor=0)
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
    """Two-phase rename via per-ifindex scratch names, so any permutation
    or cycle in the plan applies safely - a direct from->to rename fails
    when the target is still held by another interface in the same batch.
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
    """Leave {name: mac} hints under vyos_udev_dir for interfaces with no
    hw-id yet, so vyos-interface-rescan.py can populate config.boot; drop
    hints that are stale or no longer needed.
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
                  candidates: list = None, rules: dict = None) -> None:
    """Write /run/vyos-net-name-resolve.json.

    candidates is the full unmatched_candidates() list from this boot, so
    a node left unresolved for lack of hardware is diagnosable from this
    one file: 'pending_unresolved' says what needed a match,
    'unconfigured_candidates' says what was in the running for one.

    rules splits `reclaimed` by how each match was reached, so a guess
    stays visible as one - see match_pending_nodes(). src/init/vyos-router
    turns these keys into boot-time warnings.
    """
    pending = pending or {}
    reclaimed = reclaimed or {}
    candidates = candidates or []
    rules = rules or {}
    all_pending = pending_names(pending)
    status = {
        'configured': configured,
        'found': sorted(found.values()),
        'missing': {mac: configured[mac] for mac in sorted(missing)},
        'renamed': plan,
        'pending_unresolved': sorted(all_pending - set(reclaimed.values())),
        'reclaimed': reclaimed,
        'reclaimed_by_topology': sorted(rules.get('topology', ())),
        'reclaimed_by_name': sorted(rules.get('name', ())),
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

    all_pending = pending_names(pending)

    reclaimed = {}
    reclaim_rules = {}
    candidates = []
    if all_pending or any(mac not in configured for mac in current.values()):
        # a pending node forces the settle wait even when nothing looks
        # unconfigured yet - its hardware may still be probing
        current = wait_for_settle(current)
        if configured:
            # slow hw-id hardware may have turned up during that wait
            missing = set(configured) - set(current.values())
            plan = compute_rename_plan(configured, current, pending)

        # let hardware reclaim the pending node whose address and
        # description it should keep, rather than bootstrap-naming it to a
        # bare node and orphaning that config. `rules` records which
        # matches were guesses, all the way out to the boot console.
        candidates = unmatched_candidates(configured, current)
        reclaimed = match_pending_nodes(pending, candidates,
                                         rules=reclaim_rules)
        candidate_by_mac = dict(candidates)
        for mac, target in reclaimed.items():
            name = candidate_by_mac[mac]
            if name != target:
                plan[name] = target
            logger.info(
                f"reclaiming pending node '{target}' for hw-id '{mac}' "
                'this boot'
            )

        # name whatever is left in canonical order rather than leaving it
        # on a racy udev-time name; unmatched pending names stay reserved
        plan.update(compute_bootstrap_plan(
            configured, current, plan, pending=pending,
            reclaimed=reclaimed))

    applied = safe_bulk_rename(plan)

    final_current = discover_physical_interfaces()
    for name in sorted(all_pending - set(reclaimed.values())):
        logger.warning(
            f"pending node '{name}' still has no hw-id after this boot's "
            'naming pass'
        )

    # `configured` is deliberately not merged with `reclaimed`: that mac
    # has no hw-id in config.boot yet and still needs a hint under its new
    # name for vyos-interface-rescan.py to write one into the existing node
    sync_rescan_hints(final_current, configured, set(applied.keys()))
    write_status(configured, current, missing, applied,
                 pending=pending, reclaimed=reclaimed, candidates=candidates,
                 rules=reclaim_rules)


if __name__ == '__main__':
    syslog_handler = logging.handlers.SysLogHandler(address='/dev/log')
    formatter = logging.Formatter(f'{Path(__file__).name}: %(message)s')
    syslog_handler.setFormatter(formatter)

    logger.addHandler(syslog_handler)
    logger.setLevel(logging.DEBUG)

    main()
