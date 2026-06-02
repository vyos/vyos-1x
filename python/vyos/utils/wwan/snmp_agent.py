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

"""SNMP pass-persist agent for IGOS-WWAN-MIB.

Implements the read-only object set defined in mibs/IGOS-WWAN-MIB.txt for the
VyOS enhanced WWAN subsystem.  Fetches live status from the WWAN FSM via
:class:`WWANClientSync` and serves SNMP GET/GETNEXT requests on stdin/stdout
using the net-snmp ``pass_persist`` protocol.

Wire-up in /etc/snmp/snmpd.conf::

    pass_persist .1.3.6.1.4.1.44641.1  /usr/libexec/vyos/wwan-snmp-agent

Tables implemented (read-only):

* igosWwanIfTable        (.1.3.6.1.4.1.44641.1.1.1.1)
* igosWwanSimTable       (.1.3.6.1.4.1.44641.1.1.2.1)
* igosWwanRadioTable     (.1.3.6.1.4.1.44641.1.1.3.1)
* igosWwanBearerTable    (.1.3.6.1.4.1.44641.1.1.4.1)
* igosWwanFailoverTable  (.1.3.6.1.4.1.44641.1.1.5.1)

PD and IP-passthrough tables are reserved (not yet populated).
"""

from __future__ import annotations

import logging
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger('vyos.wwan.snmp_agent')


# ── OID layout ──────────────────────────────────────────────────────────────
ROOT = (1, 3, 6, 1, 4, 1, 44641, 1)            # igosWwanMIB
OBJ  = ROOT + (1,)                              # igosWwanObjects

IF_ENTRY       = OBJ + (1, 1, 1)                # .interface.ifTable.entry
SIM_ENTRY      = OBJ + (2, 1, 1)
RADIO_ENTRY    = OBJ + (3, 1, 1)
BEARER_ENTRY   = OBJ + (4, 1, 1)
FAILOVER_ENTRY = OBJ + (5, 1, 1)

# Refresh cadence — guards against snmpwalk hammering D-Bus.
CACHE_TTL_SECONDS = float(os.environ.get('VYOS_WWAN_SNMP_CACHE_TTL', '5'))


# ── Type tags used by net-snmp pass_persist ────────────────────────────────
T_INT       = 'INTEGER'
T_GAUGE     = 'Gauge32'
T_COUNTER64 = 'Counter64'
T_TIMETICKS = 'TimeTicks'
T_STRING    = 'STRING'
T_IPADDR    = 'IPADDRESS'
T_OID       = 'OBJECTID'


# ── Enum mappings (mirror IGOS-WWAN-MIB textual conventions) ───────────────
FSM_STATE_MAP = {
    'unknown': 0, 'disabled': 1, 'initializing': 2, 'sim_ready': 3,
    'registering': 4, 'registered': 5, 'connecting': 6, 'connected': 7,
    'disconnecting': 8, 'failed': 9, 'retry_backoff': 10, 'hardware_reset': 11,
}

RAT_MAP = {
    'unknown': 0, 'gsm': 1, 'gprs': 2, 'edge': 3, 'umts': 4,
    'hspa': 5, 'hspa+': 6, 'hspa_plus': 6, 'lte': 7, 'lte-a': 8,
    'lte_advanced': 8, '5gnr-nsa': 9, 'nr5g_nsa': 9, '5gnr': 10, 'nr5g_sa': 10,
}

REG_STATE_MAP = {
    'unknown': 0, 'idle': 1, 'not-registered': 1, 'searching': 2,
    'home': 3, 'registered': 3, 'roaming': 4, 'denied': 5,
    'emergency': 6,
}

SIM_STATE_MAP = {
    'unknown': 0, 'absent': 1, 'pin-locked': 2, 'puk-locked': 3,
    'ready': 4, 'active': 5, 'disabled': 6, 'error': 7,
}

DATA_LIMIT_ACTION_MAP = {
    'none': 0, 'disable': 1, 'sim-failover': 2, 'sim-failover-sticky': 3,
}

CONNECTION_MODE_MAP = {
    'always-on': 1, 'connect-on-demand': 2, 'dial-on-demand': 3,
}

NETWORK_MODE_MAP = {
    'auto': 1, 'lte': 2, '5g': 3, 'nr5g': 3, '3g': 4, 'umts': 4, '2g': 5, 'gsm': 5,
}

AUTH_TYPE_MAP = {'none': 1, 'pap': 2, 'chap': 3, 'both': 4}
PDP_TYPE_MAP  = {'ipv4': 1, 'ipv6': 2, 'ipv4v6': 3}

APN_SOURCE_MAP = {
    'configured': 1, 'last-connected': 2, 'last_connected': 2,
    'android-db': 3, 'android_db': 3, 'network': 4, 'network-assigned': 4,
    'network_assigned': 4, 'unknown': 5,
}


def _enum(value: Any, mapping: Dict[str, int], default: int = 0) -> int:
    if value is None:
        return default
    key = str(value).strip().lower().replace(' ', '-')
    return mapping.get(key, mapping.get(key.replace('-', '_'), default))


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _str(value: Any, default: str = '') -> str:
    if value is None:
        return default
    return str(value)


def _bool_truthvalue(value: Any) -> int:
    """SNMPv2-TC TruthValue: true(1), false(2)."""
    return 1 if bool(value) else 2


# ── Interface discovery ────────────────────────────────────────────────────
def _discover_interfaces() -> List[Tuple[int, str, int]]:
    """Return list of (interface_number, ifname, ifIndex) tuples."""
    out: List[Tuple[int, str, int]] = []
    sys_net = Path('/sys/class/net')
    if not sys_net.is_dir():
        return out
    for entry in sorted(sys_net.iterdir()):
        name = entry.name
        if not name.startswith('wwan'):
            continue
        suffix = name[len('wwan'):]
        if not suffix.isdigit():
            continue
        try:
            if_index = socket.if_nametoindex(name)
        except OSError:
            continue
        out.append((int(suffix), name, if_index))
    return out


# ── Status collection ──────────────────────────────────────────────────────
class _StatusCache:
    """Caches per-interface status dicts to throttle D-Bus traffic."""

    def __init__(self, ttl: float = CACHE_TTL_SECONDS) -> None:
        self.ttl = max(0.5, float(ttl))
        self._stamp: float = 0.0
        self._snapshot: Dict[int, Dict[str, Any]] = {}
        self._client = None  # lazy

    def _get_client(self):
        if self._client is None:
            from vyos.utils.wwan.wwan_client import WWANClientSync
            self._client = WWANClientSync()
        return self._client

    def get(self) -> Dict[int, Dict[str, Any]]:
        now = time.monotonic()
        if (now - self._stamp) < self.ttl and self._snapshot:
            return self._snapshot
        snapshot: Dict[int, Dict[str, Any]] = {}
        client = self._get_client()
        for if_num, name, if_index in _discover_interfaces():
            try:
                status = client.get_status(if_num)
            except Exception as exc:
                logger.debug('get_status(%s) failed: %s', if_num, exc)
                status = {}
            status.setdefault('_ifname', name)
            status.setdefault('_ifindex', if_index)
            status.setdefault('_interface_number', if_num)
            snapshot[if_index] = status
        self._snapshot = snapshot
        self._stamp = now
        return snapshot


# ── OID tree builder ───────────────────────────────────────────────────────
def _now_ts_to_dateandtime(ts: Optional[float]) -> str:
    """Convert a UNIX epoch (or None) to an SNMPv2-TC DateAndTime string.

    pass_persist STRING values are simple ASCII; emit ISO-8601 which most NMS
    tools accept and parse without complaint.
    """
    if not ts:
        return ''
    try:
        return time.strftime('%Y-%m-%dT%H:%M:%S%z', time.localtime(float(ts)))
    except (TypeError, ValueError):
        return ''


def _build_if_row(if_index: int, st: Dict[str, Any]) -> Iterable[Tuple[Tuple[int, ...], str, str]]:
    base = IF_ENTRY
    primary = _int(st.get('configured_sim_slot'), 1)
    active  = _int(st.get('active_sim_slot'), primary)
    sticky  = bool(st.get('failback_suppressed_by_connection_failure', False))

    yield base + (1, if_index),  T_INT,    str(_enum(st.get('fsm_state'), FSM_STATE_MAP))
    yield base + (2, if_index),  T_STRING, _str(st.get('modem_manufacturer'))
    yield base + (3, if_index),  T_STRING, _str(st.get('modem_model'))
    yield base + (4, if_index),  T_STRING, _str(st.get('modem_firmware') or st.get('modem_firmware_revision'))
    yield base + (5, if_index),  T_STRING, _str(st.get('modem_hardware_revision'))
    yield base + (6, if_index),  T_STRING, _str(st.get('modem_imei'))
    yield base + (7, if_index),  T_INT,    str(primary or 1)
    yield base + (8, if_index),  T_INT,    str(active or primary or 1)
    yield base + (9, if_index),  T_INT,    str(_bool_truthvalue(sticky))
    yield base + (10, if_index), T_INT,    str(_enum(st.get('connection_mode'), CONNECTION_MODE_MAP, 1))
    yield base + (11, if_index), T_INT,    str(_enum(st.get('network_mode'), NETWORK_MODE_MAP, 1))
    yield base + (12, if_index), T_INT,    str(_int(st.get('mtu'), 1420))
    yield base + (13, if_index), T_TIMETICKS, str(_int(st.get('fsm_state_uptime_seconds'), 0) * 100)
    yield base + (14, if_index), T_STRING, _now_ts_to_dateandtime(st.get('last_event_time'))
    yield base + (15, if_index), T_STRING, _str(st.get('last_event_description'))


def _build_sim_rows(if_index: int, st: Dict[str, Any]) -> Iterable[Tuple[Tuple[int, ...], str, str]]:
    base = SIM_ENTRY
    active = _int(st.get('active_sim_slot'))
    for slot in (1, 2):
        present = bool(st.get(f'sim_slot_{slot}_present', False))
        is_active = (slot == active and active != 0)
        # Field 1 (slot) is the index — not emitted as a value.
        # State: prefer dedicated per-slot if present, else infer from active slot.
        slot_state_raw = st.get(f'sim_slot_{slot}_state')
        if slot_state_raw:
            sim_state = _enum(slot_state_raw, SIM_STATE_MAP, 0)
        elif not present:
            sim_state = SIM_STATE_MAP['absent']
        elif is_active:
            sim_state = SIM_STATE_MAP['active']
        else:
            sim_state = SIM_STATE_MAP['ready']

        if is_active:
            iccid = _str(st.get('sim_iccid')) or _str(st.get(f'sim_slot_{slot}_iccid'))
            imsi  = _str(st.get('sim_imsi'))  or _str(st.get(f'sim_slot_{slot}_imsi'))
            opname = _str(st.get('operator_name')) or _str(st.get(f'sim_slot_{slot}_operator'))
            opcode = _str(st.get('operator_code')) or _str(st.get(f'sim_slot_{slot}_mcc_mnc'))
            apn = _str(st.get('connected_apn'))
            apn_src = _enum(st.get('apn_source'), APN_SOURCE_MAP, 5)
            reg_state = _enum(st.get('registration_state'), REG_STATE_MAP, 0)
            roaming = _bool_truthvalue(reg_state == REG_STATE_MAP['roaming'])
        else:
            iccid = _str(st.get(f'sim_slot_{slot}_iccid'))
            imsi  = _str(st.get(f'sim_slot_{slot}_imsi'))
            opname = _str(st.get(f'sim_slot_{slot}_operator'))
            opcode = _str(st.get(f'sim_slot_{slot}_mcc_mnc'))
            apn = ''
            apn_src = APN_SOURCE_MAP['unknown']
            reg_state = REG_STATE_MAP['unknown']
            roaming = _bool_truthvalue(False)

        roaming_allowed = _bool_truthvalue(
            not bool(st.get(f'sim_slot_{slot}_roaming_disabled', False))
        )
        msisdn = _str(st.get(f'sim_slot_{slot}_msisdn')) or (
            _str(st.get('modem_phone_number')) if is_active else ''
        )

        # Data-limit fields: live config exposes only the active slot;
        # inactive slot values fall back to per-slot config keys if present.
        if is_active:
            dl_size   = _int(st.get('active_data_limit_size'), 0)
            dl_action = _enum(st.get('active_data_limit_action'), DATA_LIMIT_ACTION_MAP, 0)
            dl_billing = _int(st.get('active_data_limit_billing_date'), 1)
            dl_used_cycle = _int(st.get('cumulative_bytes'), 0)
        else:
            dl_size   = _int(st.get(f'sim_slot_{slot}_data_limit_size'), 0)
            dl_action = _enum(st.get(f'sim_slot_{slot}_data_limit_action'), DATA_LIMIT_ACTION_MAP, 0)
            dl_billing = _int(st.get(f'sim_slot_{slot}_data_limit_billing_date'), 1)
            dl_used_cycle = _int(st.get(f'sim_slot_{slot}_cycle_bytes'), 0)
        dl_used_total = _int(st.get(f'sim_slot_{slot}_total_bytes'), dl_used_cycle if is_active else 0)
        if dl_size > 0:
            dl_pct = max(0, min(200, int(round(dl_used_cycle * 100.0 / dl_size))))
        else:
            dl_pct = 0

        idx = (if_index, slot)
        # Column numbers come from IGOS-WWAN-MIB SEQUENCE order (skipping col 1 = INDEX).
        yield base + (2, *idx),  T_INT,       str(sim_state)
        yield base + (3, *idx),  T_INT,       str(_bool_truthvalue(is_active))
        yield base + (4, *idx),  T_STRING,    iccid
        yield base + (5, *idx),  T_STRING,    imsi
        yield base + (6, *idx),  T_STRING,    msisdn
        yield base + (7, *idx),  T_STRING,    opcode
        yield base + (8, *idx),  T_STRING,    opname
        yield base + (9, *idx),  T_INT,       str(roaming)
        yield base + (10, *idx), T_INT,       str(roaming_allowed)
        yield base + (11, *idx), T_STRING,    apn
        yield base + (12, *idx), T_INT,       str(apn_src)
        yield base + (13, *idx), T_INT,       str(_enum(st.get(f'sim_slot_{slot}_auth_type'), AUTH_TYPE_MAP, 1))
        yield base + (14, *idx), T_INT,       str(_enum(st.get(f'sim_slot_{slot}_pdp_type'), PDP_TYPE_MAP, 3))
        yield base + (15, *idx), T_INT,       str(reg_state)
        yield base + (16, *idx), T_COUNTER64, str(_int(st.get(f'sim_slot_{slot}_connect_attempts'), 0))
        yield base + (17, *idx), T_COUNTER64, str(_int(st.get(f'sim_slot_{slot}_connect_failures'), 0))
        yield base + (18, *idx), T_STRING,    _now_ts_to_dateandtime(st.get(f'sim_slot_{slot}_last_connect_time'))
        yield base + (19, *idx), T_STRING,    _now_ts_to_dateandtime(st.get(f'sim_slot_{slot}_last_disconnect_time'))
        yield base + (20, *idx), T_STRING,    _str(st.get(f'sim_slot_{slot}_last_disconnect_cause'))
        yield base + (21, *idx), T_COUNTER64, str(dl_size)
        yield base + (22, *idx), T_INT,       str(dl_action)
        yield base + (23, *idx), T_COUNTER64, str(dl_used_cycle)
        yield base + (24, *idx), T_COUNTER64, str(dl_used_total)
        yield base + (25, *idx), T_INT,       str(dl_billing)
        yield base + (26, *idx), T_INT,       str(dl_pct)


def _build_radio_row(if_index: int, st: Dict[str, Any]) -> Iterable[Tuple[Tuple[int, ...], str, str]]:
    base = RADIO_ENTRY
    bars_pct = _int(st.get('signal_percent'), 0)
    bars = max(0, min(5, int(round(bars_pct / 20.0)))) if bars_pct else 0
    yield base + (1, if_index),  T_INT,    str(_enum(st.get('access_technology_name') or st.get('signal_technology'), RAT_MAP))
    yield base + (2, if_index),  T_STRING, _str(st.get('current_bands') or st.get('active_band'))
    yield base + (3, if_index),  T_INT,    str(bars)
    yield base + (4, if_index),  T_INT,    str(_int(st.get('signal_rssi') or st.get('signal_dbm'), 0))
    yield base + (5, if_index),  T_INT,    str(_int(st.get('signal_rsrp'), 0))
    yield base + (6, if_index),  T_INT,    str(_int(st.get('signal_rsrq'), 0))
    yield base + (7, if_index),  T_INT,    str(_int(st.get('signal_snr') or st.get('signal_sinr'), 0))
    yield base + (8, if_index),  T_INT,    str(_int(st.get('signal_ecio'), 0))
    yield base + (9, if_index),  T_GAUGE,  str(_int(st.get('cell_id'), 0))
    yield base + (10, if_index), T_INT,    str(_int(st.get('pci'), 0))
    yield base + (11, if_index), T_INT,    str(_int(st.get('tac') or st.get('lac'), 0))
    yield base + (12, if_index), T_INT,    str(_int(st.get('earfcn'), 0))
    yield base + (13, if_index), T_GAUGE,  str(_int(st.get('nr_arfcn'), 0))


def _build_bearer_row(if_index: int, st: Dict[str, Any]) -> Iterable[Tuple[Tuple[int, ...], str, str]]:
    base = BEARER_ENTRY
    connected = _enum(st.get('fsm_state'), FSM_STATE_MAP) == FSM_STATE_MAP['connected']
    v4 = _str(st.get('ipv4_address'))
    v6 = _str(st.get('ipv6_address'))
    v4_type = 1 if v4 else 0
    v6_type = 2 if v6 else 0
    yield base + (1, if_index),  T_INT,       str(_bool_truthvalue(connected))
    yield base + (2, if_index),  T_INT,       str(v4_type)
    yield base + (3, if_index),  T_STRING,    v4
    yield base + (4, if_index),  T_STRING,    _str(st.get('ipv4_gateway'))
    yield base + (5, if_index),  T_INT,       str(v6_type)
    yield base + (6, if_index),  T_STRING,    v6
    yield base + (7, if_index),  T_INT,       str(_int(st.get('ipv6_prefix_length'), 128 if v6 else 0))
    yield base + (8, if_index),  T_STRING,    _str(st.get('ipv6_gateway'))
    yield base + (9, if_index),  T_STRING,    _str(st.get('dns_primary') or st.get('ipv4_dns_primary'))
    yield base + (10, if_index), T_STRING,    _str(st.get('dns_secondary') or st.get('ipv4_dns_secondary'))
    yield base + (11, if_index), T_STRING,    _now_ts_to_dateandtime(st.get('last_connect_time'))
    yield base + (12, if_index), T_TIMETICKS, str(_int(st.get('session_duration_seconds'), 0) * 100)
    yield base + (13, if_index), T_COUNTER64, str(_int(st.get('session_rx_bytes'), 0))
    yield base + (14, if_index), T_COUNTER64, str(_int(st.get('session_tx_bytes'), 0))


def _build_failover_row(if_index: int, st: Dict[str, Any]) -> Iterable[Tuple[Tuple[int, ...], str, str]]:
    base = FAILOVER_ENTRY
    yield base + (1, if_index),  T_INT,       str(_bool_truthvalue(not st.get('sim_failover_disabled', False)))
    yield base + (2, if_index),  T_INT,       str(_bool_truthvalue(not st.get('sim_failback_disabled', False)))
    yield base + (3, if_index),  T_INT,       str(_bool_truthvalue(st.get('failover_in_progress', False)))
    yield base + (4, if_index),  T_INT,       str(_int(st.get('last_failover_from_slot'), 0))
    yield base + (5, if_index),  T_INT,       str(_int(st.get('last_failover_to_slot'), 0))
    yield base + (6, if_index),  T_INT,       str(_int(st.get('last_failover_reason_code'), 0))
    yield base + (7, if_index),  T_STRING,    _now_ts_to_dateandtime(st.get('last_failover_time'))
    yield base + (8, if_index),  T_COUNTER64, str(_int(st.get('failover_count'), 0))
    yield base + (9, if_index),  T_COUNTER64, str(_int(st.get('failback_count'), 0))
    yield base + (10, if_index), T_INT,       str(_int(st.get('failover_cooldown_remain'), 0))
    yield base + (11, if_index), T_INT,       str(_int(st.get('registration_flap_count'), 0))
    yield base + (12, if_index), T_INT,       str(_int(st.get('registration_flap_window_seconds'), 360))


def _build_oid_tree(snapshot: Dict[int, Dict[str, Any]]) -> List[Tuple[Tuple[int, ...], str, str]]:
    rows: List[Tuple[Tuple[int, ...], str, str]] = []
    for if_index in sorted(snapshot.keys()):
        st = snapshot[if_index]
        rows.extend(_build_if_row(if_index, st))
        rows.extend(_build_sim_rows(if_index, st))
        rows.extend(_build_radio_row(if_index, st))
        rows.extend(_build_bearer_row(if_index, st))
        rows.extend(_build_failover_row(if_index, st))
    rows.sort(key=lambda r: r[0])
    return rows


# ── pass_persist protocol ──────────────────────────────────────────────────
def _parse_oid(text: str) -> Optional[Tuple[int, ...]]:
    text = text.strip().lstrip('.')
    if not text:
        return None
    try:
        return tuple(int(p) for p in text.split('.'))
    except ValueError:
        return None


def _format_oid(oid: Tuple[int, ...]) -> str:
    return '.' + '.'.join(str(p) for p in oid)


class PassPersistAgent:
    """Implements net-snmp pass_persist for the WWAN MIB subtree."""

    def __init__(self) -> None:
        self.cache = _StatusCache()
        self._tree: List[Tuple[Tuple[int, ...], str, str]] = []
        self._tree_stamp: float = 0.0

    def _refresh_tree(self) -> None:
        now = time.monotonic()
        if (now - self._tree_stamp) < CACHE_TTL_SECONDS and self._tree:
            return
        try:
            snapshot = self.cache.get()
            self._tree = _build_oid_tree(snapshot)
        except Exception as exc:
            logger.warning('Failed to refresh OID tree: %s', exc)
            self._tree = []
        self._tree_stamp = now

    def handle_get(self, oid: Tuple[int, ...]) -> Optional[Tuple[Tuple[int, ...], str, str]]:
        self._refresh_tree()
        for entry in self._tree:
            if entry[0] == oid:
                return entry
            if entry[0] > oid:
                break
        return None

    def handle_getnext(self, oid: Tuple[int, ...]) -> Optional[Tuple[Tuple[int, ...], str, str]]:
        self._refresh_tree()
        for entry in self._tree:
            if entry[0] > oid:
                return entry
        return None

    def run(self) -> None:
        in_stream  = sys.stdin
        out_stream = sys.stdout

        def emit(*lines: str) -> None:
            out_stream.write('\n'.join(lines) + '\n')
            out_stream.flush()

        while True:
            cmd = in_stream.readline()
            if not cmd:
                return
            cmd = cmd.strip()
            if cmd == 'PING':
                emit('PONG')
                continue
            if cmd in ('get', 'getnext'):
                oid_line = in_stream.readline()
                if not oid_line:
                    return
                oid = _parse_oid(oid_line)
                if oid is None or oid[:len(ROOT)] != ROOT:
                    emit('NONE')
                    continue
                try:
                    result = (self.handle_get(oid) if cmd == 'get'
                              else self.handle_getnext(oid))
                except Exception as exc:
                    logger.warning('agent error on %s: %s', cmd, exc)
                    result = None
                if result is None:
                    emit('NONE')
                else:
                    res_oid, res_type, res_value = result
                    emit(_format_oid(res_oid), res_type, res_value)
                continue
            if cmd == 'set':
                # Drain the two follow-up lines (TYPE, VALUE) and refuse.
                in_stream.readline()
                in_stream.readline()
                in_stream.readline()
                emit('not-writable')
                continue
            if cmd == '':
                continue
            # Unknown verb — terminate cleanly.
            return


def main() -> int:
    logging.basicConfig(
        level=os.environ.get('VYOS_WWAN_SNMP_LOG_LEVEL', 'WARNING'),
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
        stream=sys.stderr,
    )
    PassPersistAgent().run()
    return 0


if __name__ == '__main__':
    sys.exit(main())
