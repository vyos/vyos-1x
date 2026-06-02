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

    IGOS_SNMPTRAP_DEST       — destination, e.g. "udp:127.0.0.1:162"  (required)
    IGOS_SNMPTRAP_COMMUNITY  — v2c community (default: "public")
    IGOS_SNMPTRAP_BIN        — path to snmptrap (default: /usr/bin/snmptrap)

Maps WWAN AlertBus codes (see interfaces_wwan_service_manager.py
ALERT_KIND_REGISTRY) to NOTIFICATION-TYPE OIDs from IGOS-WWAN-MIB.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import signal
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger('vyos.wwan.snmp_traps')


# igosWwanMIB notifications — { igosWwanNotifications 0 }
NOTIF_BASE = '.1.3.6.1.4.1.44641.1.2.0'

# AlertBus code → notification OID + ordered (name, type, value-key) tuples
# describing the varbinds the trap should carry.
#
# Type codes are SNMP CLI types: i=Integer, s=OctetString, t=TimeTicks,
# u=Unsigned32, c=Counter32, C=Counter64, a=IPaddress, o=OID, x=hex-string.
TRAP_MAP: Dict[str, Tuple[str, List[Tuple[str, str, str, str]]]] = {
    # Each varbind tuple is (mib-object-name, snmp-type, value-key, scope).
    # ``scope`` selects the index suffix appended at runtime:
    #   'if'     -> .<ifIndex>
    #   'sim'    -> .<ifIndex>.<slot>
    #   'scalar' -> .0
    # igosWwanFsmStateChange (notif .1)
    'WWAN_FSM_FAILED': (
        f'{NOTIF_BASE}.1',
        [
            ('igosWwanIfFsmState',              'i', '_fsm_state_int',  'if'),
            ('igosWwanIfActiveSlot',            'i', '_active_slot',    'if'),
            ('igosWwanIfLastEventDescription',  's', 'message',         'if'),
        ],
    ),
    # igosWwanFailoverEvent (notif .2)
    'WWAN_SIM_FAILOVER': (
        f'{NOTIF_BASE}.2',
        [
            ('igosWwanFailoverLastFromSlot', 'i', '_from_sim',              'if'),
            ('igosWwanFailoverLastToSlot',   'i', '_to_sim',                'if'),
            ('igosWwanFailoverLastReason',   'i', '_failover_reason_code',  'if'),
            ('igosWwanIfActiveSlot',         'i', '_active_slot',           'if'),
        ],
    ),
    'WWAN_SIM_SWITCH': (
        f'{NOTIF_BASE}.2',
        [
            ('igosWwanFailoverLastFromSlot', 'i', '_from_sim',              'if'),
            ('igosWwanFailoverLastToSlot',   'i', '_to_sim',                'if'),
            ('igosWwanFailoverLastReason',   'i', '_failover_reason_code',  'if'),
            ('igosWwanIfActiveSlot',         'i', '_active_slot',           'if'),
        ],
    ),
    # igosWwanBearerUp (.4) / igosWwanBearerDown (.5)
    'WWAN_BEARER_UP': (
        f'{NOTIF_BASE}.4',
        [
            ('igosWwanBearerIpv4Addr', 's', '_ipv4',         'if'),
            ('igosWwanBearerIpv6Addr', 's', '_ipv6',         'if'),
            ('igosWwanIfActiveSlot',   'i', '_active_slot',  'if'),
        ],
    ),
    'WWAN_BEARER_DOWN': (
        f'{NOTIF_BASE}.5',
        [
            ('igosWwanSimLastDisconnectCause', 's', '_disconnect_cause', 'sim'),
            ('igosWwanIfActiveSlot',           'i', '_active_slot',      'if'),
        ],
    ),
    # igosWwanDataLimitWarning (.7) / igosWwanDataLimitReached (.8)
    'WWAN_USAGE_WARNING': (
        f'{NOTIF_BASE}.7',
        [
            ('igosWwanEventSlot',           'i', '_active_slot', 'scalar'),
            ('igosWwanSimDataPercentUsed',  'i', '_pct_used',    'sim'),
            ('igosWwanSimDataLimitBytes',   'C', '_limit_bytes', 'sim'),
        ],
    ),
    'WWAN_USAGE_LIMIT_EXCEEDED': (
        f'{NOTIF_BASE}.8',
        [
            ('igosWwanEventSlot',              'i', '_active_slot',       'scalar'),
            ('igosWwanSimDataUsedCycleBytes',  'C', '_used_bytes',        'sim'),
            ('igosWwanSimDataLimitAction',     'i', '_limit_action_code', 'sim'),
        ],
    ),
    # Reconnect attempt — folded into FSM-state-change (notif .1)
    'WWAN_RECONNECT_ATTEMPT': (
        f'{NOTIF_BASE}.1',
        [
            ('igosWwanIfFsmState',              'i', '_fsm_state_int', 'if'),
            ('igosWwanIfActiveSlot',            'i', '_active_slot',   'if'),
            ('igosWwanIfLastEventDescription',  's', 'message',        'if'),
        ],
    ),
}


# Reuse enum maps from snmp_agent.
from vyos.utils.wwan.snmp_agent import (  # noqa: E402
    DATA_LIMIT_ACTION_MAP,
    FSM_STATE_MAP,
    _enum,
    _int,
)

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


def _build_snmptrap_args(
    code: str,
    alert: Dict[str, Any],
    *,
    dest: str,
    community: str,
    binary: str,
) -> Optional[List[str]]:
    spec = TRAP_MAP.get(code)
    if not spec:
        return None
    notif_oid, varbinds = spec

    # Trap uptime: time since FSM start if available, else 0.
    uptime_ticks = _int(alert.get('uptime_seconds'), 0) * 100

    args: List[str] = [
        binary, '-v', '2c', '-c', community, dest,
        str(uptime_ticks),
        notif_oid,
    ]
    flat = _normalize_alert(alert)

    # Resolve ifIndex from the alert's interface name (best-effort).
    ifname = str(flat.get('interface') or flat.get('ifname') or '')
    if_index = 0
    if ifname:
        try:
            import socket as _socket
            if_index = _socket.if_nametoindex(ifname)
        except OSError:
            if_index = 0
    slot = _int(flat.get('_active_slot'), 0) or 1

    for name, type_code, key, scope in varbinds:
        if scope == 'scalar':
            suffix = '.0'
        elif scope == 'sim':
            suffix = f'.{if_index}.{slot}'
        else:  # 'if'
            suffix = f'.{if_index}'
        oid_label = f'IGOS-WWAN-MIB::{name}{suffix}'
        value = flat.get(key, '')
        if type_code == 's':
            value_str = str(value) if value is not None else ''
            args += [oid_label, type_code, value_str]
        else:
            args += [oid_label, type_code, str(_int(value, 0))]
    return args


def _send_trap(
    code: str,
    alert: Dict[str, Any],
    *,
    dest: str,
    community: str,
    binary: str,
) -> None:
    args = _build_snmptrap_args(
        code, alert, dest=dest, community=community, binary=binary,
    )
    if not args:
        return
    try:
        subprocess.run(
            args, check=False, timeout=5,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning('snmptrap invocation failed (%s): %s', code, exc)


# ── Daemon entry point ─────────────────────────────────────────────────────
async def _run() -> int:
    dest = os.environ.get('IGOS_SNMPTRAP_DEST', '').strip()
    if not dest:
        logger.error('IGOS_SNMPTRAP_DEST not set; refusing to start')
        return 1
    community = os.environ.get('IGOS_SNMPTRAP_COMMUNITY', 'public')
    binary = os.environ.get('IGOS_SNMPTRAP_BIN', '/usr/bin/snmptrap')
    if not (binary and (shutil.which(binary) or os.path.exists(binary))):
        logger.error('snmptrap binary not found at %s', binary)
        return 1

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
                def _on_alert(alert: Dict[str, Any]) -> None:
                    code = str(alert.get('code') or '')
                    if not code:
                        return
                    try:
                        _send_trap(
                            code, alert,
                            dest=dest, community=community, binary=binary,
                        )
                    except Exception as exc:
                        logger.debug('trap dispatch error for %s: %s', code, exc)

                sub_id = client.subscribe_alerts(_on_alert)
                logger.info('Subscribed to AlertBus (id=%s); forwarding traps to %s',
                            sub_id, dest)
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
