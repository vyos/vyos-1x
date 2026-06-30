#!/usr/bin/env python3
# Copyright (C) 2024-2026 Perle Systems Limited
# SPDX-License-Identifier: GPL-2.0-or-later
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

"""SNMP trap emitter for the WWAN FSM.

Subscribes to the WWAN AlertBus and emits SNMPv2 NOTIFICATION-TYPE traps
defined in mibs/IGOS-WWAN-MIB.txt by invoking ``snmptrap(1)``.

Run as a small standalone daemon::

    /usr/libexec/vyos/wwan-snmp-traps

Configuration via environment variables (or /etc/default/igos-wwan-snmp-traps):

    IGOS_SNMPTRAP_TARGETS_FILE   — JSON file listing trap destinations, each a
                                   fully-formed snmptrap(1) argv prefix
                                   (version/auth flags + ``proto:host:port``).
                                   Written by service_snmp.py from the VyOS
                                   ``service snmp trap-target`` / ``service snmp
                                   v3 trap-target`` config, so v1/v2c **and**
                                   v3 (authNoPriv/authPriv, trap/inform) targets
                                   are all supported, to any number of sinks.
    IGOS_SNMPTRAP_BIN            — path to snmptrap (default: /usr/bin/snmptrap)
    IGOS_SNMPTRAP_DEDUP_SECONDS  — suppress identical (code/iface/slot) traps
                                   within this window (default: 2; 0 disables)

    Legacy single-target fallback (used only when no targets file is present):
    IGOS_SNMPTRAP_DEST           — destination, e.g. "udp:127.0.0.1:162"
    IGOS_SNMPTRAP_COMMUNITY      — v2c community (default: "public")

Maps WWAN AlertBus codes (see interfaces_wwan_service_manager.py
ALERT_KIND_REGISTRY) to NOTIFICATION-TYPE OIDs from IGOS-WWAN-MIB.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import signal
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger('vyos.wwan.snmp_traps')

# Reuse enum maps, table-entry OID bases, and helpers from the agent so the
# MIB column layout has a single source of truth.
from vyos.utils.wwan.snmp_agent import (  # noqa: E402
    BEARER_ENTRY,
    DATA_LIMIT_ACTION_MAP,
    FAILOVER_ENTRY,
    FSM_STATE_MAP,
    IF_ENTRY,
    ROOT,
    SIM_ENTRY,
    _enum,
    _format_oid,
    _int,
)


# igosWwanMIB notifications — { igosWwanNotifications 0 }
NOTIF_BASE = '.1.3.6.1.4.1.44641.1.2.0'

# igosWwanEventSlot — accessible-for-notify scalar { igosWwanNotifications 1 }.
# Carried as instance .0 in data-limit notifications.
EVENT_SLOT_OID = ROOT + (2, 1)

# AlertBus code → (notification OID, [varbind, ...]).
#
# Each varbind is (column-OID, snmp-type, value-key, scope):
#   * column-OID is the numeric table-column OID (no instance suffix).  Using
#     numeric OIDs means snmptrap(1) does NOT need the IGOS-WWAN-MIB loaded to
#     resolve symbolic names (which silently fails when MIBDIRS is unset).
#   * snmp-type codes: i=Integer, s=OctetString, t=TimeTicks, u=Unsigned32,
#     c=Counter32, C=Counter64, a=IPaddress, o=OID, x=hex-string.
#   * scope selects the index suffix appended at runtime:
#       'if'     -> .<ifIndex>
#       'sim'    -> .<ifIndex>.<slot>
#       'scalar' -> .0
TRAP_MAP: Dict[str, Tuple[str, List[Tuple[Tuple[int, ...], str, str, str]]]] = {
    # igosWwanFsmStateChange (notif .1)
    'WWAN_FSM_FAILED': (
        f'{NOTIF_BASE}.1',
        [
            (IF_ENTRY + (1,), 'i', '_fsm_state_int', 'if'),
            (IF_ENTRY + (8,), 'i', '_active_slot', 'if'),
            (IF_ENTRY + (15,), 's', 'message', 'if'),
        ],
    ),
    # igosWwanFailoverEvent (notif .2)
    'WWAN_SIM_FAILOVER': (
        f'{NOTIF_BASE}.2',
        [
            (FAILOVER_ENTRY + (4,), 'i', '_from_sim', 'if'),
            (FAILOVER_ENTRY + (5,), 'i', '_to_sim', 'if'),
            (FAILOVER_ENTRY + (6,), 'i', '_failover_reason_code', 'if'),
            (IF_ENTRY + (8,), 'i', '_active_slot', 'if'),
        ],
    ),
    'WWAN_SIM_SWITCH': (
        f'{NOTIF_BASE}.2',
        [
            (FAILOVER_ENTRY + (4,), 'i', '_from_sim', 'if'),
            (FAILOVER_ENTRY + (5,), 'i', '_to_sim', 'if'),
            (FAILOVER_ENTRY + (6,), 'i', '_failover_reason_code', 'if'),
            (IF_ENTRY + (8,), 'i', '_active_slot', 'if'),
        ],
    ),
    # igosWwanBearerUp (.4) / igosWwanBearerDown (.5)
    'WWAN_BEARER_UP': (
        f'{NOTIF_BASE}.4',
        [
            (BEARER_ENTRY + (3,), 's', '_ipv4', 'if'),
            (BEARER_ENTRY + (6,), 's', '_ipv6', 'if'),
            (IF_ENTRY + (8,), 'i', '_active_slot', 'if'),
        ],
    ),
    'WWAN_BEARER_DOWN': (
        f'{NOTIF_BASE}.5',
        [
            (SIM_ENTRY + (20,), 's', '_disconnect_cause', 'sim'),
            (IF_ENTRY + (8,), 'i', '_active_slot', 'if'),
        ],
    ),
    # igosWwanDataLimitWarning (.7) / igosWwanDataLimitReached (.8)
    'WWAN_USAGE_WARNING': (
        f'{NOTIF_BASE}.7',
        [
            (EVENT_SLOT_OID, 'i', '_active_slot', 'scalar'),
            (SIM_ENTRY + (26,), 'i', '_pct_used', 'sim'),
            (SIM_ENTRY + (21,), 'C', '_limit_bytes', 'sim'),
        ],
    ),
    'WWAN_USAGE_LIMIT_EXCEEDED': (
        f'{NOTIF_BASE}.8',
        [
            (EVENT_SLOT_OID, 'i', '_active_slot', 'scalar'),
            (SIM_ENTRY + (23,), 'C', '_used_bytes', 'sim'),
            (SIM_ENTRY + (22,), 'i', '_limit_action_code', 'sim'),
        ],
    ),
    # Reconnect attempt — folded into FSM-state-change (notif .1)
    'WWAN_RECONNECT_ATTEMPT': (
        f'{NOTIF_BASE}.1',
        [
            (IF_ENTRY + (1,), 'i', '_fsm_state_int', 'if'),
            (IF_ENTRY + (8,), 'i', '_active_slot', 'if'),
            (IF_ENTRY + (15,), 's', 'message', 'if'),
        ],
    ),
}


FAILOVER_REASON_MAP = {
    'none': 0, 'signal-loss': 1, 'signal_loss': 1,
    'registration-lost': 2, 'registration_lost': 2,
    'registration-flap': 3, 'registration_flap': 3,
    'connect-failure': 4, 'connect_failure': 4,
    'data-limit-reached': 5, 'data_limit_reached': 5, 'usage_limit': 5,
    'hardware-error': 6, 'hardware_error': 6,
    'manual': 7, 'manual_switch': 7, 'manual-switch': 7,
    'failback': 8, 'primary-recovered': 8, 'primary_recovered': 8,
    'sim-absent': 9, 'sim_absent': 9,
}


def _normalize_alert(alert: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten alert payload into a key→string map for varbind lookup.

    Adds a few derived ``_*`` keys used by TRAP_MAP value-keys.
    """
    flat: Dict[str, Any] = dict(alert)
    extra = alert.get('extra') or alert.get('fields') or {}
    if isinstance(extra, dict):
        flat.update(extra)

    flat['_active_slot'] = _int(flat.get('active_sim_slot') or flat.get('to_sim'), 0)
    flat['_from_sim']    = _int(flat.get('from_sim'), 0)
    flat['_to_sim']      = _int(flat.get('to_sim') or flat.get('active_sim_slot'), 0)
    flat['_failover_reason_code'] = _enum(flat.get('reason'), FAILOVER_REASON_MAP, 0)
    flat['_fsm_state_int'] = _enum(flat.get('fsm_state') or flat.get('state'), FSM_STATE_MAP, 0)
    flat['_ipv4'] = str(flat.get('ipv4_address') or flat.get('ipv4') or '')
    flat['_ipv6'] = str(flat.get('ipv6_address') or flat.get('ipv6') or '')
    flat['_disconnect_cause'] = str(flat.get('reason') or flat.get('disconnect_cause') or '')
    flat['_pct_used'] = _int(flat.get('percent_used') or flat.get('pct'), 0)
    flat['_limit_bytes'] = _int(flat.get('limit_bytes') or flat.get('size'), 0)
    flat['_used_bytes']  = _int(flat.get('used_bytes') or flat.get('cumulative_bytes'), 0)
    flat['_limit_action_code'] = _enum(flat.get('action'), DATA_LIMIT_ACTION_MAP, 0)
    return flat


def _build_trap_tail(
    code: str,
    alert: Dict[str, Any],
) -> Optional[List[str]]:
    """Build the version-independent tail of an snmptrap invocation.

    Returns ``[uptime, notif_oid, <varbind triples...>]`` — everything that
    follows the per-target ``proto:host:port`` destination.  The same tail is
    appended to every configured target (v2c, v3, …), so the notification
    payload is identical regardless of transport/auth.  Returns ``None`` when
    the alert code has no mapped notification.
    """
    spec = TRAP_MAP.get(code)
    if not spec:
        return None
    notif_oid, varbinds = spec

    # Trap uptime: time since FSM start if available, else 0.
    uptime_ticks = _int(alert.get('uptime_seconds'), 0) * 100

    tail: List[str] = [str(uptime_ticks), notif_oid]
    flat = _normalize_alert(alert)

    # Resolve ifIndex from the alert's interface.  The AlertBus payload carries
    # ``interface_number`` (an integer N for wwanN); map it to the kernel
    # ifIndex via the ``wwanN`` name so each interface (wwan0, wwan1, …) gets
    # its own distinct index — and so it matches the SNMP agent, which builds
    # its table ifIndex the same way (if_nametoindex on the discovered name).
    # Fall back to an explicit name field if one is ever present.
    import socket as _socket
    if_index = 0
    iface_num = flat.get('interface_number')
    candidates = []
    if iface_num is not None and str(iface_num).lstrip('-').isdigit() and int(iface_num) >= 0:
        candidates.append(f'wwan{int(iface_num)}')
    name_field = str(flat.get('interface') or flat.get('ifname') or '')
    if name_field.startswith('wwan'):
        candidates.append(name_field)
    for cand in candidates:
        try:
            if_index = _socket.if_nametoindex(cand)
            break
        except OSError:
            continue
    slot = _int(flat.get('_active_slot'), 0) or 1

    for col_oid, type_code, key, scope in varbinds:
        if scope == 'scalar':
            inst = col_oid + (0,)
        elif scope == 'sim':
            inst = col_oid + (if_index, slot)
        else:  # 'if'
            inst = col_oid + (if_index,)
        oid_label = _format_oid(inst)
        value = flat.get(key, '')
        if type_code == 's':
            value_str = str(value) if value is not None else ''
            tail += [oid_label, type_code, value_str]
        else:
            tail += [oid_label, type_code, str(_int(value, 0))]
    return tail


class _TargetStore:
    """Holds the set of snmptrap destinations, reloaded on file change.

    Each target is a complete snmptrap(1) argv *prefix* — the version/auth
    flags plus the ``proto:host:port`` destination — rendered by
    service_snmp.py from the VyOS SNMP config.  This keeps the single source
    of truth for how VyOS maps trap-target config to snmptrap flags in the
    conf-mode script (mirroring the snmpd.conf template), so this daemon never
    has to know about communities, engine IDs, or v3 crypto.

    The targets file is re-read whenever its mtime changes, so a ``commit``
    that adds/removes trap-targets takes effect without a hard restart and a
    boot-ordering race (file written after the daemon starts) self-heals.
    """

    def __init__(
        self,
        path: str,
        *,
        legacy_dest: str = '',
        legacy_community: str = 'public',
    ) -> None:
        self._path = path
        self._legacy: Optional[List[str]] = None
        if legacy_dest:
            self._legacy = ['-v', '2c', '-c', legacy_community, legacy_dest]
        self._mtime: Optional[float] = None
        self._targets: List[List[str]] = []
        self.reload()

    def _fallback(self) -> List[List[str]]:
        return [list(self._legacy)] if self._legacy else []

    def reload(self) -> None:
        if not self._path:
            self._targets = self._fallback()
            return
        try:
            mtime = os.stat(self._path).st_mtime
        except OSError:
            self._targets = self._fallback()
            self._mtime = None
            return
        if mtime == self._mtime and self._targets:
            return
        self._mtime = mtime
        try:
            with open(self._path, encoding='utf-8') as f:
                data = json.load(f)
            targets: List[List[str]] = []
            for entry in data.get('targets', []):
                argv = entry.get('argv') if isinstance(entry, dict) else None
                if isinstance(argv, list) and argv:
                    targets.append([str(x) for x in argv])
            self._targets = targets or self._fallback()
        except (OSError, ValueError) as exc:
            logger.warning('Failed to read targets file %s: %s', self._path, exc)
            # Keep the previously-loaded targets on a transient read error.

    def get(self) -> List[List[str]]:
        self.reload()
        return self._targets


# Per-(code, interface, slot) dedup gate — coalesces trap bursts (e.g. a
# registration-flap storm) so we do not spawn a flood of snmptrap processes.
_last_trap_sent: Dict[Tuple[str, str, int], float] = {}


def _dedupe_ok(code: str, ifname: str, slot: int, window: float) -> bool:
    """Return False when an identical trap was sent within *window* seconds."""
    if window <= 0:
        return True
    now = time.monotonic()
    key = (code, ifname, slot)
    last = _last_trap_sent.get(key)
    if last is not None and (now - last) < window:
        return False
    _last_trap_sent[key] = now
    return True


async def _run_snmptrap(binary: str, prefix: List[str], tail: List[str],
                        code: str) -> None:
    """Run one snmptrap invocation to a single target without blocking."""
    args = [binary, *prefix, *tail]
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        logger.warning('snmptrap invocation failed (%s): %s', code, exc)
        return
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        logger.warning('snmptrap timed out (%s)', code)
        return
    if proc.returncode and stderr:
        logger.debug(
            'snmptrap %s rc=%s: %s',
            code,
            proc.returncode,
            stderr.decode(errors='replace').strip(),
        )


async def _send_trap(
    code: str,
    alert: Dict[str, Any],
    *,
    store: '_TargetStore',
    binary: str,
    dedup_window: float,
) -> None:
    flat = _normalize_alert(alert)
    # Dedup key must include the interface so a wwan0 trap never suppresses an
    # identical-code wwan1 trap.  The payload carries ``interface_number``;
    # fall back to a name field only if present.
    iface_id = flat.get('interface_number')
    if iface_id is None:
        iface_id = str(flat.get('interface') or flat.get('ifname') or '')
    iface_key = str(iface_id)
    slot = _int(flat.get('_active_slot'), 0) or 1
    if not _dedupe_ok(code, iface_key, slot, dedup_window):
        logger.debug(
            'Suppressed duplicate trap %s (%s/%s) within %.1fs window',
            code,
            iface_key,
            slot,
            dedup_window,
        )
        return

    tail = _build_trap_tail(code, alert)
    if not tail:
        return

    targets = store.get()
    if not targets:
        logger.debug('No trap targets configured; dropping %s', code)
        return

    # Fan out to every configured target concurrently — one slow or
    # unreachable sink must not delay delivery to the others, nor stall the
    # asyncio event loop driving the AlertBus consumer.
    await asyncio.gather(
        *(_run_snmptrap(binary, prefix, tail, code) for prefix in targets)
    )


# ── Daemon entry point ─────────────────────────────────────────────────────
async def _run() -> int:
    binary = os.environ.get('IGOS_SNMPTRAP_BIN', '/usr/bin/snmptrap')
    if not (binary and (shutil.which(binary) or os.path.exists(binary))):
        logger.error('snmptrap binary not found at %s', binary)
        return 1

    targets_file = os.environ.get('IGOS_SNMPTRAP_TARGETS_FILE', '').strip()
    # Legacy single v2c destination — only used when no targets file is set.
    legacy_dest = os.environ.get('IGOS_SNMPTRAP_DEST', '').strip()
    legacy_community = os.environ.get('IGOS_SNMPTRAP_COMMUNITY', 'public')
    if not targets_file and not legacy_dest:
        logger.error(
            'No trap targets configured (IGOS_SNMPTRAP_TARGETS_FILE and '
            'IGOS_SNMPTRAP_DEST both unset); refusing to start'
        )
        return 1
    store = _TargetStore(
        targets_file,
        legacy_dest=legacy_dest,
        legacy_community=legacy_community,
    )

    try:
        dedup_window = float(os.environ.get('IGOS_SNMPTRAP_DEDUP_SECONDS', '2'))
    except ValueError:
        dedup_window = 2.0

    from vyos.utils.wwan.wwan_client import WWANClient

    stop_event = asyncio.Event()

    def _on_signal(*_):
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _on_signal)
        except (NotImplementedError, RuntimeError):
            pass

    backoff = 1.0
    while not stop_event.is_set():
        try:
            async with WWANClient() as client:

                async def _on_alert(alert: Dict[str, Any]) -> None:
                    code = str(alert.get('code') or '')
                    if not code:
                        return
                    try:
                        await _send_trap(
                            code, alert,
                            store=store, binary=binary,
                            dedup_window=dedup_window,
                        )
                    except Exception as exc:
                        logger.debug('trap dispatch error for %s: %s', code, exc)

                sub_id = client.subscribe_alerts(_on_alert)
                logger.info(
                    'Subscribed to AlertBus (id=%s); forwarding traps to %d '
                    'target(s)', sub_id, len(store.get()),
                )
                backoff = 1.0
                await stop_event.wait()
                client.unsubscribe_alerts(sub_id)
        except Exception as exc:
            if stop_event.is_set():
                break
            logger.warning('AlertBus connection lost (%s); retry in %.1fs',
                           exc, backoff)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=backoff)
            except asyncio.TimeoutError:
                pass
            backoff = min(backoff * 2, 30.0)
    return 0


def main() -> int:
    logging.basicConfig(
        level=os.environ.get('VYOS_WWAN_SNMP_LOG_LEVEL', 'INFO'),
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
        stream=sys.stderr,
    )
    try:
        return asyncio.run(_run())
    except KeyboardInterrupt:
        return 0


if __name__ == '__main__':
    sys.exit(main())
