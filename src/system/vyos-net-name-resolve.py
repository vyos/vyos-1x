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
# Boot-time maintenance of the interface mapping store (T3871).
#
# The store is rendered into systemd .link files, so udev does the actual
# naming as each device is added. What is left here is what udev cannot do:
# name hardware the store has never seen, record it, and re-render.
#
# Nothing here reads the configuration - a name is a property of the
# hardware, not of what happens to be configured on it.

import json
import logging
import logging.handlers
import time
from pathlib import Path

from vyos.ifconfig.ifname_store import device_matches
from vyos.ifconfig.ifname_store import discover_devices
from vyos.ifconfig.ifname_store import load_store
from vyos.ifconfig.ifname_store import resolve
from vyos.ifconfig.ifname_store import save_store
from vyos.ifconfig.ifname_store import sync_link_files
from vyos.system.image import is_running_as_container
from vyos.utils.process import run

# bounded wait for known hardware to appear
HARDWARE_WAIT_TIMEOUT = 10
HARDWARE_WAIT_POLL = 0.25

# unknown hardware has no specific device to wait for, so N identical
# snapshots stand in for "probing has finished"
HARDWARE_SETTLE_TIMEOUT = 10
HARDWARE_SETTLE_STABLE_POLLS = 3

status_file = Path('/run/vyos-net-name-resolve.json')

logger = logging.getLogger()


def _snapshot(devices: list) -> set:
    return {(d['name'], d['mac']) for d in devices}


def _unmatched(keys: set, devices: list) -> set:
    """Recorded slots that no device present this boot occupies."""
    return {key for key in keys
            if not any(device_matches(d['properties'], key) for d in devices)}


def wait_for_hardware(known_keys: set, timeout: float = HARDWARE_WAIT_TIMEOUT,
                      poll: float = HARDWARE_WAIT_POLL) -> tuple:
    """Poll until every slot the store knows is filled, or until timeout."""
    deadline = time.monotonic() + timeout
    devices = discover_devices()
    while True:
        missing = _unmatched(known_keys, devices)
        if not missing or time.monotonic() >= deadline:
            return devices, missing
        time.sleep(poll)
        devices = discover_devices()


def wait_for_settle(initial: list, timeout: float = HARDWARE_SETTLE_TIMEOUT,
                    poll: float = HARDWARE_WAIT_POLL,
                    stable_polls: int = HARDWARE_SETTLE_STABLE_POLLS) -> list:
    """Poll until the set of interfaces stops changing, or until timeout.
    Used before naming hardware the store has never seen, where there is no
    specific MAC to wait for.
    """
    deadline = time.monotonic() + timeout
    devices = initial
    stable = 1 if devices else 0
    while stable < stable_polls and time.monotonic() < deadline:
        time.sleep(poll)
        seen = discover_devices()
        stable = stable + 1 if _snapshot(seen) == _snapshot(devices) else 1
        devices = seen
    return devices


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
    """Stage every interface under a scratch name derived from its ifindex
    before assigning the final ones, so the batch cannot collide on a
    permutation or a cycle. Only new hardware reaches this - udev has already
    named everything the store knows.
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
            # still under the scratch name - do not report it as renamed
            del applied[old]
            run(f'ip link set dev {tmp} up')

    return applied


def write_status(store: dict, devices: list, applied: dict, report: dict,
                 persisted: bool) -> None:
    """Publish what this pass decided, to warn about and to inspect later."""
    absent = _unmatched(set(store['interfaces'].values()), devices)
    status = {
        'interfaces': dict(sorted(store['interfaces'].items())),
        'missing': {
            name: key for name, key in sorted(store['interfaces'].items())
            if key in absent
        },
        'renamed': applied,
        # everything recognised from the store, however it was recognised
        'matched': {**report.get('matched', {}),
                    **report.get('moved', {}),
                    **report.get('replaced', {})},
        # the card was found in a different slot - certain, it is the same card
        'moved': report.get('moved', {}),
        # a different card took the slot - the one case that needs verifying
        'matched_by_path': report.get('replaced', {}),
        'new_hardware': report.get('bootstrapped', {}),
        'persisted': persisted,
    }
    try:
        status_file.write_text(json.dumps(status, indent=2))
    except OSError as e:
        logger.error(f'could not write status file: {e}')


def main():
    if is_running_as_container():
        # a container owns no NIC - its veth pairs have no backing bus device
        logger.info('running inside a container - skipping interface naming')
        return

    store = load_store()
    known = set(store['interfaces'].values())

    devices, _missing = wait_for_hardware(known)

    if not store['interfaces'] or any(
            not any(device_matches(d['properties'], k) for k in known)
            for d in devices):
        # unknown hardware present - let slower drivers finish registering
        # so a merely late NIC is not treated as new
        devices = wait_for_settle(devices)

    absent = _unmatched(known, devices)
    for name, key in sorted(store['interfaces'].items()):
        if key in absent:
            logger.warning(
                f"'{name}' ({key}) did not appear within "
                f'{HARDWARE_WAIT_TIMEOUT}s - hardware may be missing, still '
                'initializing, or its driver failed to load. Its name stays '
                'reserved.'
            )

    plan, store, report = resolve(devices, store)

    for name, mac in sorted(report.get('bootstrapped', {}).items()):
        logger.info(f"new hardware {mac} named '{name}'")

    # A card which took over a slot also took over the addresses configured
    # under that name. vyos-router says so for a boot, but a card swapped on
    # a running system is only ever seen here.
    for name, mac in sorted(report.get('replaced', {}).items()):
        logger.warning(
            f"'{name}' was matched to new hardware {mac} by slot - verify it "
            'is the port you expect before relying on its configuration'
        )
    applied = safe_bulk_rename(plan)

    persisted = save_store(store)
    if persisted:
        # render so udev applies the names on the next boot
        try:
            sync_link_files(store)
        except OSError as e:
            logger.error(f'could not write .link files: {e}')
    else:
        logger.warning(
            'the configuration volume is not mounted - interface names were '
            'resolved for this boot but could not be persisted'
        )

    write_status(store, devices, applied, report, persisted)


if __name__ == '__main__':
    syslog_handler = logging.handlers.SysLogHandler(address='/dev/log')
    formatter = logging.Formatter(f'{Path(__file__).name}: %(message)s')
    syslog_handler.setFormatter(formatter)

    logger.addHandler(syslog_handler)
    logger.setLevel(logging.DEBUG)

    main()
