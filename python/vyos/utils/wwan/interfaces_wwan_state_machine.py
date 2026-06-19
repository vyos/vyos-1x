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

import asyncio
import time
import os
import re
import json
import shutil
import datetime
import ipaddress
import socket
import struct
import logging
from enum import Enum
from collections import deque
from dbus_next.aio import MessageBus  # pylint: disable=import-error
from dbus_next.message import Message  # pylint: disable=import-error
from dbus_next.errors import DBusError  # pylint: disable=import-error
from dbus_next import Variant  # pylint: disable=import-error
from automaton import machines  # pylint: disable=import-error
from vyos.utils.wwan.interfaces_wwan_util import modem_reset
from vyos.utils.wwan import interfaces_wwan_diag as wwan_diag
from vyos.utils.wwan.sim_controller import make_sim_controller

# Check if Android APN lookup library is available
try:
    import apnscripts.apn_lookup_run  # noqa: F401  # pylint: disable=unused-import,import-error
    APN_LOOKUP_AVAILABLE = True
except ImportError:
    APN_LOOKUP_AVAILABLE = False

from vyos.utils.wwan.wwan_utilities import (
    extract_apn_field, convert_android_auth_type,
    convert_android_apns
)
from vyos.utils.wwan.wwan_configuration import ConfigurationLoader
from vyos.utils.wwan.apn_discovery import APNDiscovery
from vyos.utils.wwan.connection_manager import ConnectionManager
from vyos.utils.wwan.state_transition_manager import StateTransitionManager
from vyos.utils.wwan.interfaces_wwan_passthrough import PassthroughManager
from vyos.utils.wwan.interfaces_wwan_bridging_radvd import BridgingRadvdManager

from vyos.utils.wwan.wwan_logging import setup_logging, reconfigure_logging


logger = setup_logging(__name__, "wwan-fsm")

# Constants
MODEM_MANAGER_SERVICE = "org.freedesktop.ModemManager1"
MODEM_MANAGER_PATH = "/org/freedesktop/ModemManager1"
MODEM_INTERFACE = "org.freedesktop.ModemManager1.Modem"
OBJECT_MANAGER_INTERFACE = "org.freedesktop.DBus.ObjectManager"
BEARER_INTERFACE = "org.freedesktop.ModemManager1.Bearer"
SIMPLE_INTERFACE = "org.freedesktop.ModemManager1.Modem.Simple"
MESSAGING_INTERFACE = "org.freedesktop.ModemManager1.Modem.Messaging"
SMS_INTERFACE = "org.freedesktop.ModemManager1.Sms"

# ── SMS flat-file storage ───────────────────────────────────────────────────
SMS_STORAGE_DIR = "/var/lib/wwan/sms"
SMS_MAX_MESSAGES = 100

# ── APN state persistence ────────────────────────────────────────────────────
# Survives service restarts and reboots so the last-connected APN is retried
# first on the next boot without re-running the full discovery cascade.
APN_STATE_DIR = "/var/lib/wwan/apn"

# ── Central defaults ────────────────────────────────────────────────────────
# Single source of truth for configuration defaults.  Every code path that
# needs a fallback value should reference these dicts rather than hard-coding
# its own magic constants.

DEFAULT_DATA_CONFIG = {
    'data_limit_size': 0,              # bytes; 0 = no limit
    'data_limit_action': 'none',       # none | disable | sim-failover | sim-failover-sticky
    'data_limit_warning': [],           # list of pct thresholds (e.g. [75, 90, 95]); empty = no warnings
    'data_limit_billing_date': 1,      # day of month (1-28)
}

DEFAULT_CONNECTIVITY_CONFIG = {
    'enabled': True,
    'interval': 60,                    # seconds between tests (min 30)
    'timeout': 10,                     # per-ping timeout (min 5)
    'retry_count': 3,                  # pings per test (min 1)
    'failure_threshold': 2,            # consecutive failures before recovery (min 1)
    'test_ipv4': True,
    'test_ipv6': False,
    'require_both': False,             # require both v4 + v6 to pass
    'ipv4_targets': ['8.8.8.8', '1.1.1.1'],
    'ipv6_targets': ['2001:4860:4860::8888', '2606:4700:4700::1111'],
}

# ── Signal strength averaging for LED indicator ──────────────────────────────
class SignalStrengthTracker:
    """Tracks rolling-window average of signal strength with change detection.

    Maintains a FIFO history of signal samples (in dBm) and detects when the
    signal "level bin" changes to trigger periodic LED indicator updates.
    Uses 8 levels (0-7) like smartphone signal bars for fine-grained
    indication.  All thresholds are on the 3GPP RSRP coverage scale; every
    reading is normalized to RSRP by ``_to_rsrp_scale`` (RSRP used as-is, RSSI
    shifted ~20 dB) before classification, so one consistent ruler applies no
    matter which metric the modem reported:
      - 0: No signal     (< -125 dBm or no reading)
      - 1: Barely usable (-125 to -116 dBm)
      - 2: Very poor     (-115 to -109 dBm)
      - 3: Weak          (-108 to -103 dBm)
      - 4: Fair          (-102 to -96 dBm)
      - 5: Good          (-95 to -86 dBm)
      - 6: Very good     (-85 to -76 dBm)
      - 7: Excellent     (>= -75 dBm)
    """

    def __init__(self, window_size: int = 12, led_callback=None):
        """
        Args:
            window_size: number of samples to average (default 12 = ~60s @ 5s MM refresh)
            led_callback: async callable(level_int, avg_dbm, detail_dict) triggered on level change
                - level_int: 0-7 (no signal to maximum)
                - avg_dbm: rolling average in dBm (or None if no samples yet)
                - detail_dict: full signal detail from MM (rssi, rsrp, rsrq, snr, technology)
        """
        self.window_size = max(1, int(window_size))
        self.led_callback = led_callback
        self.samples: deque = deque(maxlen=self.window_size)
        self.current_level = None  # Current level: 0-7
        self.last_update_time = 0

    @staticmethod
    def _to_rsrp_scale(signal_dbm, signal_detail) -> float:
        """Normalize a reading to the RSRP scale so one ruler fits every RAT.

        RSRP is the 3GPP per-resource-element coverage metric and is used as
        the canonical scale.  RSSI (wideband, reported by 2G/3G and as the LTE
        fallback) sits roughly 20 dB ABOVE RSRP for the same conditions, so an
        RSSI reading is shifted down ~20 dB to land on the RSRP ruler.  Returns
        None when nothing usable is available.
        """
        RSSI_TO_RSRP_OFFSET = 20  # RSSI is ~20 dB higher than RSRP

        def _num(value):
            try:
                if value is None or value == '':
                    return None
                return float(value)
            except (TypeError, ValueError):
                return None

        detail = signal_detail or {}
        technology = (detail.get('technology') or '').upper()
        rsrp = _num(detail.get('rsrp'))
        rssi = _num(detail.get('rssi'))

        # Prefer a real RSRP reading (LTE / 5G-NR) verbatim.
        if rsrp is not None:
            return rsrp
        # Only RSSI exposed (2G/3G, or LTE without RSRP) -> shift onto RSRP.
        if rssi is not None:
            return rssi - RSSI_TO_RSRP_OFFSET
        # No per-metric detail: treat the collapsed value as RSSI-like for
        # LTE/5G (the extractor is RSSI-first there); leave others as-is.
        if signal_dbm is None:
            return None
        if technology in ('LTE', '5G NR', 'NR5G', '5G'):
            return signal_dbm - RSSI_TO_RSRP_OFFSET
        return signal_dbm

    def _classify_level(self, avg_dbm: float) -> int:
        """Classify a normalized RSRP-scale dBm into an 8-level band.

        The input MUST already be normalized by ``_to_rsrp_scale`` so a single
        set of thresholds is valid regardless of the reported metric.  Bands
        follow the 3GPP RSRP coverage convention (see class docstring).
        """
        if avg_dbm is None or avg_dbm < -125:
            return 0  # No signal
        if avg_dbm < -115:
            return 1  # Barely usable
        if avg_dbm < -108:
            return 2  # Very poor
        if avg_dbm < -102:
            return 3  # Weak
        if avg_dbm < -95:
            return 4  # Fair
        if avg_dbm < -85:
            return 5  # Good
        if avg_dbm < -75:
            return 6  # Very good
        return 7  # Excellent / maximum

    async def update(self, signal_dbm: float, signal_detail: dict = None) -> None:
        """Add a new signal sample and check for level change; trigger LED if changed.

        The incoming reading is first normalized to the RSRP scale (RSRP as-is,
        RSSI shifted ~20 dB) so the rolling average and level bands are computed
        on one consistent ruler regardless of which metric the modem reported.
        """
        norm_dbm = self._to_rsrp_scale(signal_dbm, signal_detail)
        if norm_dbm is None:
            return

        self.samples.append(norm_dbm)
        avg_dbm = sum(self.samples) / len(self.samples)
        new_level = self._classify_level(avg_dbm)

        if (new_level != self.current_level or
            time.monotonic() - self.last_update_time > 10.0):  # Also update every 10s
            self.current_level = new_level
            self.last_update_time = time.monotonic()

            level_names = ['no-signal', 'barely-usable', 'very-poor', 'weak', 'fair', 'good', 'very-good', 'excellent']
            level_name = level_names[new_level] if 0 <= new_level < len(level_names) else 'unknown'

            logger.info(
                f"Signal level: {level_name} [{new_level}/7] "
                f"(avg={avg_dbm:.1f} dBm, samples={len(self.samples)})",
                extra={'level': new_level, 'avg_dbm': avg_dbm, 'level_name': level_name}
            )

            if self.led_callback:
                try:
                    if hasattr(self.led_callback, '__call__'):
                        result = self.led_callback(
                            new_level,
                            round(avg_dbm, 1),
                            signal_detail or {}
                        )
                        if hasattr(result, '__await__'):
                            await result
                except Exception as e:
                    logger.warning(f"LED callback failed: {e}")

    def get_current_level(self) -> tuple[int, float]:
        """Return (level, avg_dbm) — level is 0-7, avg_dbm is rolling average or None."""
        if not self.samples:
            return (0, None)
        avg = sum(self.samples) / len(self.samples)
        return (self.current_level or 0, round(avg, 1))

    def reset(self) -> None:
        """Clear history (e.g., on SIM switch or reconnection)."""
        self.samples.clear()
        self.current_level = None
        self.last_update_time = 0

# Enums for clarity
class ModemState(str, Enum):
    INITIAL = "INITIAL"
    SCANNING = "SCANNING"
    MODEM_FOUND = "MODEM_FOUND"
    WAITING_FOR_CONFIG = "WAITING_FOR_CONFIG"
    CONFIGURING = "CONFIGURING"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    DISCONNECTING = "DISCONNECTING"
    DISCONNECTED = "DISCONNECTED"
    WAITING_FOR_SIM = "WAITING_FOR_SIM"
    FAILED = "FAILED"
    # SIM switch states
    SIM_SWITCHING = "SIM_SWITCHING"
    SIM_DISCONNECTING = "SIM_DISCONNECTING"
    SIM_DISABLING = "SIM_DISABLING"
    SIM_ENABLING = "SIM_ENABLING"
    SIM_RECONFIGURING = "SIM_RECONFIGURING"
    REGISTERED_IDLE = "REGISTERED_IDLE"  # Registered on network, no bearer (connect-on-demand)
    # Usage monitoring states
    USAGE_MONITORING = "USAGE_MONITORING"
    USAGE_THRESHOLD = "USAGE_THRESHOLD"
    USAGE_RESETTING = "USAGE_RESETTING"

class ModemEvent(str, Enum):
    START_SCAN = "start_scan"
    MODEM_FOUND = "modem_found"
    WAIT_FOR_CONFIG = "wait_for_config"
    CONFIG_UPDATE = "config_update"
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    DISCONNECTED = "disconnected"
    SIM_MISSING = "sim_missing"
    SIM_LOCKED = "sim_locked"
    CONNECTION_FAILED = "connection_failed"
    RECONFIGURE = "reconfigure"
    SIM_READY = "sim_ready"
    CONNECTED = "connected"
    USAGE_LIMIT_EXCEEDED = "usage_limit_exceeded"
    # SIM switch events
    SWITCH_SIM = "switch_sim"
    SIM_DISCONNECTED = "sim_disconnected"
    SIM_DISABLED = "sim_disabled"
    SIM_SWITCHED = "sim_switched"
    SIM_ENABLED = "sim_enabled"
    SIM_SWITCH_COMPLETE = "sim_switch_complete"
    ENTER_IDLE = "enter_idle"  # Transition to REGISTERED_IDLE (connect-on-demand)
    # Usage monitoring events
    START_USAGE_MONITORING = "start_usage_monitoring"
    RESET_USAGE = "reset_usage"

class ModemStateMachine:
    modem_state_machines = {}

    def __init__(self, interface_number: int, bus: MessageBus, alert_emitter=None):
        self.interface_number = interface_number
        self.bus = bus
        self.alert_emitter = alert_emitter
        self.proxy = None
        self.config = None
        self._previous_config = None        # Track previous config for selective disconnection
        self.modem_path = None
        self.bearer_path = None
        self.user_disconnected = False
        # Persistent desired-bearer-state for on-demand modes.  Unlike
        # connect_requested (a transient queue cleared once acted upon), this
        # records the operator's standing intent: once a connect is issued in
        # connect-on-demand mode the bearer must behave like always-on
        # (auto-reconnect on failure) and be re-established after a service
        # crash/restart, until an explicit disconnect is issued.  Persisted in
        # __runtime_state__ and restored before config is applied.
        self.bearer_requested = False
        self._shutting_down = False         # Set by shutdown() to suppress recovery
        self._airplane_mode_requested = False  # Set when disable=true is applied
        self._airplane_mode_active = False     # True once SetPowerState(LOW) succeeded
        # Timers/tasks referenced by _admin_disable() →
        # _stop_network_interface_monitoring() before any config is applied.
        # _apply_parsed_configuration() re-initializes these to None as well,
        # but admin-disable can fire on cold start before that ever runs.
        self._bearer_disconnect_timer = None
        self._registration_debounce_timer = None
        self._ip_monitoring_task = None
        self._signal_poll_task = None
        self.usage_monitor_task = None
        # Egress-filter / MSS-clamp state also referenced during teardown
        self._ipv6_egress_filter_active = False
        self._ipv4_egress_filter_active = False
        self._fsm_mss_clamp_v4_active = False
        self._fsm_mss_clamp_v6_active = False
        self._current_bearer_ipv4 = None
        self._current_bearer_ipv6 = None
        self._current_bearer_ipv6_prefix = None
        # interface_management_enabled gates _set_interface_down(), which the
        # _teardown_downstream_features() path calls.  monitor_ip_changes
        # gates _start_network_interface_monitoring().  Both default to the
        # standard "we manage the link" behavior; _apply_parsed_configuration
        # overrides them from the parsed config.
        self.interface_management_enabled = True
        self.monitor_ip_changes = False
        # _dhcpv6_pd_enabled is read by _remove_ipv6_egress_filter().  That
        # function is gated on _ipv6_egress_filter_active=True (which is
        # already False on cold start), but pre-init defensively anyway.
        self._dhcpv6_pd_enabled = False
        self.current_active_sim = None      # Track actual active SIM
        self.config_active_sim = None       # Track configured active SIM
        self.sim_switch_reason = None       # Track why SIM was switched
        self.target_sim_slot = None         # Track target SIM during switch
        self.previous_sim_slot = None        # Track original SIM for rollback on switch failure

        # Track consecutive APN cascade failures on the current SIM before allowing
        # failover — honours sim_failover_connect_retries config
        self.initial_connection_failure_count = 0

        # SIM failover cooldown tracking to prevent ping-pong
        self.last_failover_time = 0          # Timestamp of last SIM failover
        self.failover_count = 0              # Number of failovers since last stable connection
        self.lifetime_failover_count = 0     # Total failovers since boot (never reset by stable connection)
        self.failover_cooldown_seconds = 600 # 10 minute cooldown between failovers (carrier-friendly)
        self.max_failovers_before_backoff = 3 # Max failovers before extended backoff
        self.failover_backoff_seconds = 3600 # 1 hour extended backoff after max failovers (carrier-friendly)

        # Signal-loss SIM-failover tracking — timestamp when the active SIM's
        # signal first dropped continuously below the configured sim-failover
        # signal-threshold.  Reset to None whenever signal recovers or a
        # failover attempt fires.  When the continuous below-threshold duration
        # reaches sim_failover_signal_loss_timer, _monitor_signal_strength
        # triggers _handle_signal_loss_failover().
        self._signal_failover_below_since = None

        # Connectivity recovery tracking for SIM escalation
        self.connectivity_recovery_attempts = 0  # Consecutive recovery attempts on same SIM
        self.max_recovery_before_sim_switch = 3  # Attempts before escalating to SIM switch
        self.disconnection_recovery_attempts = 0  # Consecutive bearer-drop recovery attempts on same SIM

        # SIM failback tracking — automatically return to primary SIM when possible
        self.is_on_failover_sim = False          # True when running on non-primary SIM after failover
        self.primary_sim_slot = None             # Configured primary_sim_slot (set from config)
        self.failback_task = None                # Periodic failback check task
        self.failback_suppressed_by_data_limit = False  # Sticky failover: suppress failback until billing reset
        self._sticky_failover_timestamp = None            # When sticky hold was activated
        self.failback_suppressed_by_connection_failure = False  # Suppress failback when primary SIM's APN cascade failed
        # Anti-flap protection — SIM 1 must be CONTINUOUSLY present for
        # sim_failback_stability_time seconds before failback fires.  A user
        # repeatedly cycling the SIM resets this timestamp on every removal,
        # so flapping cards never trigger failback.
        self._primary_first_seen_present_ts = None  # When SIM 1 first reappeared in this on-failover session
        self._last_failback_time = 0.0              # Cooldown anchor — prevents rapid failover/failback ping-pong

        # SIM change tracking for worldwide operation
        self.last_known_sim_info = None     # Store SIM info from last successful connection
        self.sim_changed = False            # Flag to indicate SIM card change detected
        self.connected_apn = self._restore_connected_apn()   # Last successful APN (persisted across reboots)
        self.requested_apn = ''             # APN name we asked MM to connect with (this session)
        self.negotiated_apn = ''            # APN the carrier actually activated (read over QMI)
        self.current_sim_path = None        # Last observed Modem.Sim object path
        # Debounce noisy Sim path churn during modem reboot/re-enumeration.
        # This is intentionally narrow: it only suppresses rapid duplicate
        # or immediate flip-flop A→B→A events in a short window.
        self._sim_path_change_last_ts = 0.0
        self._sim_path_change_last_from = None
        self._sim_path_change_last_to = None
        self._sim_path_change_debounce_seconds = 5.0

        # Since-boot operational counters for bearer / recovery visibility.
        self.bearer_disconnect_count = 0    # Number of bearer-down events since boot
        self.registration_loss_count = 0    # Number of bearer losses surfacing as REGISTERED
        self.reconnect_attempt_count = 0    # Automatic bearer re-establishment attempts since boot
        self.reconnect_success_count = 0    # Successful reconnects after downtime since boot
        self.sim_switch_count = 0           # Runtime SIM slot changes since boot
        # Dedupe so a single switch is not counted twice when both the
        # reset-based switch executor and the PrimarySimSlot PropertiesChanged
        # signal report the same slot change.
        self._last_sim_switch_key = None    # (from_slot, to_slot) of last recorded switch
        self._last_sim_switch_ts = 0.0      # Timestamp of last recorded switch
        # Baseline for per-SIM usage accounting — cumulative bytes persisted
        # before the current bearer session began.  Lets us flush in-flight
        # session usage to the outgoing SIM before a switch without double
        # counting against what monitor_data_usage() already persisted.
        self._usage_baseline_bytes = None   # Cumulative bytes at start of current session
        self._usage_baseline_slot = None    # Slot the baseline was captured for
        # Last-known live session byte count, refreshed on every successful
        # bearer Stats read (monitor loop + status builder).  Lets the flush
        # salvage usage even when the modem is already gone (e.g. modem_removed
        # failover), where the bearer can no longer be read directly.
        self._last_session_bytes = 0
        self._last_session_slot = None
        self.total_bearer_downtime_seconds = 0  # Accumulated bearer downtime since boot
        self._bearer_down_since = None      # Timestamp when current downtime window started
        self.last_disconnect_time = 0       # Timestamp of last bearer drop / disconnect
        self.last_disconnect_reason = ''    # Human-readable reason for last bearer loss
        self._disconnect_reason_override = None  # Temporary reason set before DISCONNECT

        # Per-slot SIM identity cache — stores physical SIM details (IMSI, ICCID,
        # operator) for each slot as we observe them.  ModemManager only exposes
        # full details for the active SIM, so we cache what we learn whenever a
        # slot becomes active.  The inactive slot's ICCID may be readable from
        # its D-Bus object even when not powered.
        self.sim_slot_info_cache = {}       # {slot_number: {imsi, iccid, operator, mcc_mnc}}

        # ICCID lock state — set by _validate_sim_iccid()
        self.iccid_mismatch = False         # True when inserted SIM doesn't match configured ICCID

        # Reset cooldown tracking to prevent cascading failures
        self.last_reset_time = 0            # Timestamp of last hardware reset
        self.reset_cooldown_seconds = 300   # 5 minute cooldown between resets
        self.hardware_reset_enabled = True
        self.max_hardware_resets = 3
        self.hardware_reset_attempts = 0

        # Service-initiated modem operations tracking (improved reset-aware)
        self.service_initiated_disable = False  # Flag to prevent false SIM missing detection
        self.reset_operation_in_progress = False  # Track reset operations across re-enumeration
        self.initial_configuration_in_progress = False  # Prevent handlers from racing with initial config
        self._initial_config_task = None    # Track active config task for cancellation on modem removal
        self.reset_grace_period_end = 0     # Timestamp when reset grace period ends
        self.reset_timeout_task = None      # Task to clear reset flag on timeout
        self.registration_handling_in_progress = False  # Prevent concurrent registration handling tasks
        self._registration_loss_timer = None    # Initialize registration loss timer
        self._registration_flap_timestamps = []  # Timestamps of registration loss events for flap detection
        self._registration_flap_failover_triggered = False  # Whether flap detection has triggered a failover
        self.connect_requested = False      # Queued connect from D-Bus client, honored when FSM is ready
        self.connection_mode = 'always-on'   # 'always-on' | 'connect-on-demand' | 'dial-on-demand'
        self.last_scan_results = []          # Cached network scan results for status reporting
        # A configuration that arrives while the FSM is in a transitional state
        # (CONNECTING / DISCONNECTING / SIM_*) cannot be reconfigured in place —
        # apply_config() only stores it.  This flag records that a deferred
        # reconfigure is owed so it is applied once the FSM settles into a
        # stable state (otherwise an active-slot band/APN/etc. change is
        # silently dropped: the modem is never disabled and the new bands are
        # never written).
        self._pending_reconfigure = False

        # Failed-state periodic retry — automatically reattempt connection from
        # FAILED state using exponential backoff.  Covers data-plan top-up,
        # monthly rollover, carrier provisioning delay, and transient errors.
        self._failed_retry_task = None       # Background asyncio task
        self._failed_retry_attempt = 0       # Current attempt number for backoff calc
        self._failed_retry_enabled = True    # Overridden by config in _apply_parsed_configuration
        self._failed_retry_intervals = [600, 1800, 3600, 7200]  # 10, 30, 60, 120 min (carrier-friendly)
        self._failed_retry_max_interval = 7200  # Cap at 2 hr (carrier-friendly)
        # Companion watcher: polls SimSlots every 30s while FAILED with
        # sim-missing — MM does not signal SIM appearance in non-active slots.
        self._sim_missing_watch_task = None
        self._failed_retry_escalation_threshold = 3  # Disable/enable cycle after N failures (0=never)

        # Modem removal flag — lets CancelledError handlers log the right reason
        self._modem_removed = False

        # SIM switch in-progress flag — suppresses modem-removed handler during
        # expected modem disappearance caused by SetPrimarySimSlot (Telit LN920
        # resets the USB device when switching SIM slots)
        self._sim_switch_in_progress = False

        # SIM failover reentrancy guard — prevents multiple concurrent failover
        # attempts when the SIM is rapidly inserted/removed ("nasty user" scenario).
        # Protected via asyncio.Lock so only one failover runs at a time.
        self._sim_failover_lock = asyncio.Lock()
        self._sim_failover_in_progress = False

        # FAILED-state investigation debounce — the same pre-existing FAILED
        # condition can be observed by two independent startup paths:
        # _configure_modem_initial() Step 0a (when config is already present)
        # and _dispatch_initial_modem_state() (the synthesized cold-attach
        # event). Without a guard both run the reason investigation +
        # SIM-failover attempt, producing duplicate log lines. Suppress a
        # repeat investigation of the same reason within a short window.
        self._last_failed_investigation_ts = 0.0
        self._last_failed_investigation_reason = None

        # SIM PIN/PUK unlock safety — try only once per boot cycle
        self._pin_unlock_attempted = False    # True after first PIN attempt (success or failure)
        self._puk_unlock_attempted = False    # True after first PUK attempt (success or failure)
        self._pin_unlock_failed = False       # True if PIN unlock failed (wrong PIN)
        self._puk_unlock_failed = False       # True if PUK unlock failed (wrong PUK)
        self._sim_permanently_locked = False  # True if PUK retries exhausted — SIM destroyed
        self._pin_retries_remaining = -1      # Last known PIN retries (-1 = unknown)
        self._puk_retries_remaining = -1      # Last known PUK retries (-1 = unknown)

        # Connection failure tracking — records WHY the modem is in FAILED state
        # so status queries and operators can see the reason without digging through logs.
        # Cleared on successful connection or when new configuration is applied.
        self.last_failure_reason = ''         # Human-readable failure description
        self.last_failure_time = 0            # Timestamp of when failure occurred
        self.last_failed_apn = ''             # The APN name that was last tried when failure occurred
        self.configured_apn_rejected = False  # True when the user's explicitly configured APN was rejected

        # ── IPv6 bridging (carrier /64 → single downstream LAN) state ──
        # Not DHCPv6 PD: we just copy the carrier-supplied prefix verbatim
        # to one downstream LAN interface.  For real DHCPv6 PD, use the
        # standard VyOS 'dhcpv6-options pd' tree (dhcp6c-driven).
        self._bridging_config = {'enabled': False, 'interface': ''}
        self._bridging_applied = {}        # {iface: {'prefix','addr','prefix_len'}}
        self._bridging_pending = set()     # iface names not yet present
        self._bridging_netlink_task = None
        self._bridging_reconciliation_task = None
        self._bridging_reconciliation_interval = 10
        self._bridging_carrier_prefix = None      # IPv6Network
        self._bridging_carrier_prefix_len = None  # int
        self._bridging_bearer_addr = None         # bearer's own /128 (excluded from LAN host bit)
        self._bridging_saved_sysctls = {}         # {path: original_value} for teardown
        self._bridging_proxy_entries = set()      # IPv6 addrs proxied on the wwan side
        self._bridging_ndp_task = None            # neighbor-watch task on the LAN side
        # FSM-owned radvd for SLAAC + RDNSS on the bridged LAN.  Tracks the
        # carrier prefix automatically so the operator does not have to
        # hardcode it in `service router-advert`.
        self._bridging_radvd = BridgingRadvdManager(self.interface_number)

        # ── IPv6 management-address (FSM-stamped <prefix>::host-id on wwanN) ──
        # Default-on whenever the bearer has IPv6 and ip-passthrough is not
        # set.  Stamps a stable host address inside the carrier prefix on
        # the WWAN interface itself and installs an FSM-owned ip6tables
        # drop chain so all inbound to that address is dropped except for
        # user-permitted ports / sources.  Refreshed from raw_config in
        # _load_configuration().
        self._mgmt_addr_config = {
            'enabled': True, 'host_id': '::1',
            'permit_tcp': [], 'permit_udp': [], 'permit_source': [],
        }
        self._mgmt_addr_applied = None       # currently-applied address string
        self._mgmt_addr_prefix_len = None    # currently-applied carrier prefix len
        self._mgmt_addr_chain_active = False # ip6tables INPUT jump installed?

        # IP Passthrough manager (DOCSIS-modem-style single-host handoff).
        # Instantiated ONCE here at FSM construction so its internal state
        # (_last_v4 / _last_v6 / _last_v6_prefix) survives config reloads —
        # otherwise a SIM-swap-driven config refresh would wipe _last_v6
        # and the v6-gone deprecation-RA burst would never fire when the
        # new bearer has no IPv6, leaving Windows clients on the old SLAAC
        # address until its previously-advertised preferred lifetime expires.
        self._passthrough = PassthroughManager(self.interface_number)

        # Signal strength monitoring for LED indicators
        # Tracks rolling-window average and triggers LED callback on level changes
        # using 8 levels. Window set to 12 samples ≈ 60 seconds @ 5s MM refresh.
        self.signal_tracker = SignalStrengthTracker(
            window_size=12,
            led_callback=self._update_signal_led
        )

        # Initialize configuration loader
        self.config_loader = ConfigurationLoader(interface_number)
        self.parsed_config = None  # Will store WWANConfiguration object

        # Initialize APN discovery
        self.apn_discovery = APNDiscovery(interface_number)

        # Initialize connection manager
        self.connection_manager = ConnectionManager(interface_number)

        # Initialize state transition manager
        self.transition_manager = StateTransitionManager()

        self.machine = machines.FiniteMachine()
        self._setup_states()
        self._setup_transitions()
        self.machine.default_start_state = ModemState.INITIAL
        self.machine.initialize()
        ModemStateMachine.modem_state_machines[f"wwan{self.interface_number}"] = self

        # SIM-slot control strategy. Capability-driven from the active
        # pinmap: a board that declares a ``sim_select`` GPIO uses an
        # external SIM mux (GPIO-mux mode); otherwise SIM switching is
        # delegated to ModemManager (historical default). Never raises —
        # falls back to the ModemManager-managed controller on any error.
        self.sim_controller = make_sim_controller(self)

    def _setup_states(self):
        for state in ModemState:
            self.machine.add_state(state.value)

    def _setup_transitions(self):
        """Setup transitions using new StateTransitionManager"""
        # Get transitions from the data-driven manager
        transitions = self.transition_manager.get_all_transitions()

        # Convert state/event names to enum values and add to machine
        for from_state, to_state, event in transitions:
            from_state_enum = getattr(ModemState, from_state)
            to_state_enum = getattr(ModemState, to_state)
            event_enum = getattr(ModemEvent, event)
            self.machine.add_transition(from_state_enum.value, to_state_enum.value, event_enum.value)

        # Log transition statistics
        stats = self.transition_manager.get_statistics()
        logger.info("State transitions configured using data-driven approach",
                   extra={'interface_number': self.interface_number,
                          'total_transitions': stats['total_transitions'],
                          'unique_states': stats['unique_states'],
                          'unique_events': stats['unique_events'],
                          'transition_groups': stats['total_groups']})

    async def initialize(self):
        if not self.bus:
            logger.warning("No D-Bus bus available, skipping initialization",
                          extra={'interface_number': self.interface_number})
            return

        logger.info("Initializing FSM", extra={'interface_number': self.interface_number})

        # Setup ModemManager signal monitoring for instant modem detection
        await self.setup_modem_manager_monitoring()

        # GPIO-mux SIM presence is independent of ModemManager and the
        # modem itself — seed the presence model from the SIM_DETECT lines
        # (edges only report *changes*, so the initial state must be
        # sampled) and start the debounced detect watcher. No-op for the
        # ModemManager-managed controller.
        try:
            await self.sim_controller.sample_initial()
            self.sim_controller.start_watch()
        except Exception as e:
            logger.warning(f"SIM controller watcher init failed: {e}",
                          extra={'interface_number': self.interface_number})

        self.transition(ModemEvent.START_SCAN)
        # Start modem scanning as a background task instead of blocking
        self._safe_create_task(self.scan_for_modem())

    def _safe_create_task(self, coro, name=None):
        """Create an asyncio task with exception logging to prevent silent failures.

        All background tasks should use this instead of raw asyncio.create_task()
        so that unhandled exceptions are logged rather than silently swallowed.
        """
        task = asyncio.create_task(coro, name=name)
        task.add_done_callback(self._task_exception_handler)
        return task

    def _task_exception_handler(self, task):
        """Log exceptions from background tasks instead of letting them vanish."""
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error(f"Background task '{task.get_name()}' failed: {exc}",
                        extra={'interface_number': self.interface_number,
                               'task_name': task.get_name(),
                               'exception': str(exc)})

    def _emit_alert(self, alert_type: str, severity: str, message: str, **extra_fields):
        """Emit a normalized alert envelope through the manager-owned alert bus."""
        if not self.alert_emitter:
            return

        payload = {
            'source': 'wwan-fsm',
            'type': alert_type,
            'severity': severity,
            'message': message,
            'interface_number': self.interface_number,
            'fsm_state': self.machine.current_state if hasattr(self, 'machine') else 'unknown',
        }
        if extra_fields:
            payload.update(extra_fields)

        try:
            self.alert_emitter(payload)
        except Exception as e:
            logger.debug(f"Alert emit failed (non-fatal): {e}",
                        extra={'interface_number': self.interface_number,
                               'alert_type': alert_type})

    def _is_reset_allowed(self) -> bool:
        """Check if hardware reset is allowed (not in cooldown period)"""
        if not self.hardware_reset_enabled:
            logger.warning("Hardware reset blocked - feature disabled by configuration",
                          extra={'interface_number': self.interface_number})
            return False

        if self.hardware_reset_attempts >= self.max_hardware_resets:
            logger.warning("Hardware reset blocked - max attempts reached",
                          extra={'interface_number': self.interface_number,
                                 'attempts': self.hardware_reset_attempts,
                                 'max_attempts': self.max_hardware_resets})
            return False

        current_time = time.time()
        time_since_last_reset = current_time - self.last_reset_time

        if time_since_last_reset < self.reset_cooldown_seconds:
            remaining_cooldown = self.reset_cooldown_seconds - time_since_last_reset
            logger.warning(f"Hardware reset blocked by cooldown - {remaining_cooldown:.1f}s remaining",
                          extra={'interface_number': self.interface_number,
                                'last_reset': self.last_reset_time,
                                'cooldown_seconds': self.reset_cooldown_seconds})
            return False
        return True

    def _record_reset(self):
        """Record that a hardware reset was performed"""
        self.last_reset_time = time.time()
        self.hardware_reset_attempts += 1
        # Start reset grace period to prevent false SIM missing detection
        self.reset_operation_in_progress = True
        self.reset_grace_period_end = time.time() + 60  # 60 second grace period after reset
        logger.info(f"Hardware reset recorded, next reset allowed after {self.reset_cooldown_seconds}s cooldown",
                   extra={'interface_number': self.interface_number,
                          'reset_time': self.last_reset_time,
                          'grace_period_end': self.reset_grace_period_end,
                          'hardware_reset_attempts': self.hardware_reset_attempts,
                          'max_hardware_resets': self.max_hardware_resets})

    def _is_in_reset_grace_period(self) -> bool:
        """Check if we're still in the grace period after a reset operation"""
        current_time = time.time()

        if self.reset_operation_in_progress and current_time < self.reset_grace_period_end:
            remaining = self.reset_grace_period_end - current_time
            logger.debug(f"Still in reset grace period - {remaining:.1f}s remaining",
                        extra={'interface_number': self.interface_number})
            return True
        elif self.reset_operation_in_progress and current_time >= self.reset_grace_period_end:
            # Grace period expired, clear the flag
            logger.info("Reset grace period expired, resuming normal SIM monitoring",
                       extra={'interface_number': self.interface_number})
            self.reset_operation_in_progress = False
            self.service_initiated_disable = False  # Also clear the old flag
            return False

        return False

    # ------------------------------------------------------------------
    # Failed-state periodic retry (exponential backoff)
    # ------------------------------------------------------------------
    def _start_failed_retry(self):
        """Launch background retry loop when FSM enters FAILED.

        Uses exponential backoff (5, 10, 20, 30, 30, 30 ... min) to
        reattempt the APN connection cascade.  Covers:
        - Data plan topped up / monthly rollover
        - Carrier provisioning delay for new SIM
        - Transient network-side errors
        """
        if not self._failed_retry_enabled:
            logger.info("Failed-state retry disabled by configuration",
                       extra={'interface_number': self.interface_number})
            return
        self._cancel_failed_retry()  # Prevent duplicate tasks
        self._failed_retry_attempt = 0
        self._failed_retry_task = self._safe_create_task(
            self._failed_retry_loop(), name='failed_retry_loop')
        # Also start a fast SIM-reinsertion watcher.  When the modem is
        # FAILED with sim-missing, MM does not generate state changes
        # when a SIM appears in the *non-active* slot — so we must poll
        # SimSlots on a tighter cadence than the failed-retry backoff.
        self._sim_missing_watch_task = self._safe_create_task(
            self._sim_missing_watch_loop(), name='sim_missing_watch_loop')
        logger.info("Started failed-state periodic retry",
                   extra={'interface_number': self.interface_number,
                          'intervals': self._failed_retry_intervals})

    def _cancel_failed_retry(self):
        """Cancel a running failed-state retry task (if any)."""
        if self._failed_retry_task and not self._failed_retry_task.done():
            self._failed_retry_task.cancel()
            logger.info("Cancelled failed-state retry task",
                       extra={'interface_number': self.interface_number,
                              'attempt_reached': self._failed_retry_attempt})
        self._failed_retry_task = None
        watch = getattr(self, '_sim_missing_watch_task', None)
        if watch and not watch.done():
            watch.cancel()
        self._sim_missing_watch_task = None

    async def _sim_missing_watch_loop(self):
        """Poll SimSlots while in FAILED with sim-missing/sim-error.

        MM only signals state changes when the *active* slot's SIM
        comes/goes.  If the user re-inserts a SIM into a non-active
        slot, the modem stays in FAILED forever and no D-Bus signal
        fires.  Poll SimSlots every 30s and trigger sim-missing
        failover whenever we detect a SIM in any slot.
        """
        try:
            poll_interval = 30
            while self.machine.current_state == ModemState.FAILED.value:
                await asyncio.sleep(poll_interval)
                if self.machine.current_state != ModemState.FAILED.value:
                    return
                if self._sim_switch_in_progress or self._sim_failover_in_progress:
                    continue
                # GPIO-mux: the modem can't see the non-selected slot and
                # doesn't reliably report sim-missing, so presence comes
                # from the SIM_DETECT model.  If any slot other than the
                # one we're parked on now has a SIM, attempt failover.
                if self.sim_controller.is_gpio_mux:
                    try:
                        active = (self.current_active_sim
                                  or (self.config or {}).get('primary_sim_slot', 1))
                        present = await self.sim_controller.present_slots()
                        if any(s != active for s in present):
                            logger.info(
                                "sim-missing watch (GPIO): alternate SIM "
                                "present — triggering failover",
                                extra={'interface_number': self.interface_number,
                                       'present_slots': sorted(present),
                                       'active_slot': active})
                            await self._handle_sim_missing_failover()
                    except Exception as e:
                        logger.debug(
                            f"sim-missing watch (GPIO) poll error: {e}",
                            extra={'interface_number': self.interface_number})
                    continue
                if not self.proxy:
                    continue
                try:
                    props = self.proxy.get_interface(
                        "org.freedesktop.DBus.Properties")
                    state_v = await props.call_get(MODEM_INTERFACE, "State")
                    mm_state = state_v.value
                    if mm_state != -1:
                        # No longer FAILED at MM level — let normal handlers run
                        continue
                    sfr_v = await props.call_get(
                        MODEM_INTERFACE, "StateFailedReason")
                    failed_reason = sfr_v.value if hasattr(sfr_v, 'value') else sfr_v
                    if failed_reason not in (2, 3):  # not sim-missing/sim-error
                        continue
                    # Check whether ANY slot now has a SIM
                    sim_slots_v = await props.call_get(
                        MODEM_INTERFACE, "SimSlots")
                    sim_slots = sim_slots_v.value
                    have_sim = any(p and p != '/' for p in sim_slots)
                    if not have_sim:
                        continue
                    logger.info(
                        "sim-missing watch: SIM detected in a slot — "
                        "triggering failover rescan",
                        extra={'interface_number': self.interface_number,
                               'sim_slots': list(sim_slots)})
                    await self._handle_sim_missing_failover()
                except Exception as e:
                    logger.debug(
                        f"sim-missing watch poll error: {e}",
                        extra={'interface_number': self.interface_number})
        except asyncio.CancelledError:
            logger.debug("sim-missing watch loop cancelled",
                        extra={'interface_number': self.interface_number})
        except Exception as e:
            logger.error(f"sim-missing watch loop error: {e}",
                        extra={'interface_number': self.interface_number})

    async def _failed_retry_loop(self):
        """Periodically reattempt connection from FAILED state.

        Each cycle:
          1. Sleep for the current backoff interval.
          2. Verify we are still in FAILED (exit if state changed).
          3. Transition FAILED → CONNECTING via CONNECT event.
          4. Call apply_modem_configuration() for a full APN cascade.
          5. If still not connected, CONNECTION_FAILED puts us back in
             FAILED and the loop continues with increased backoff.
        """
        try:
            while self.machine.current_state == ModemState.FAILED.value:
                # Determine backoff interval
                if self._failed_retry_attempt < len(self._failed_retry_intervals):
                    interval = self._failed_retry_intervals[self._failed_retry_attempt]
                else:
                    interval = self._failed_retry_max_interval
                self._failed_retry_attempt += 1

                logger.info(
                    f"Failed-state retry #{self._failed_retry_attempt} "
                    f"scheduled in {interval}s",
                    extra={'interface_number': self.interface_number,
                           'attempt': self._failed_retry_attempt,
                           'interval_seconds': interval})

                await asyncio.sleep(interval)

                # Re-check — state may have changed while sleeping
                if self.machine.current_state != ModemState.FAILED.value:
                    logger.info(
                        "FSM left FAILED during retry wait — aborting retry loop",
                        extra={'interface_number': self.interface_number,
                               'current_state': self.machine.current_state})
                    return

                # Honor a standing user disconnect.  In connect-on-demand /
                # dial-on-demand the operator may have issued a disconnect
                # while we were stuck in FAILED; we must not auto-reconnect
                # behind their back.  Stop retrying and stay down until an
                # explicit connect arrives (which clears user_disconnected).
                if self.user_disconnected and self.connection_mode in (
                        'connect-on-demand', 'dial-on-demand'):
                    logger.info(
                        "User disconnect active — stopping failed-state retry "
                        "loop; will stay down until an explicit connect",
                        extra={'interface_number': self.interface_number,
                               'connection_mode': self.connection_mode})
                    return

                # Verify modem is still accessible and registered
                if not self.proxy:
                    logger.warning(
                        "No modem proxy — skipping retry, will try next interval",
                        extra={'interface_number': self.interface_number})
                    continue

                try:
                    props = self.proxy.get_interface(
                        "org.freedesktop.DBus.Properties")
                    mm_state_variant = await props.call_get(
                        MODEM_INTERFACE, "State")
                    mm_state = mm_state_variant.value
                except Exception as e:
                    logger.warning(
                        f"Cannot read modem state for retry: {e}",
                        extra={'interface_number': self.interface_number})
                    continue

                if mm_state < 6:  # DISABLED or worse — modem not ready
                    # Special case: modem stuck in FAILED with sim-missing /
                    # sim-error.  When the user re-inserts a SIM into the
                    # *non-active* slot, MM does NOT change state (active
                    # slot is still empty), so no PropertiesChanged signal
                    # fires and the FSM would otherwise wait the full backoff
                    # before noticing.  Re-scan SimSlots here and trigger
                    # failover if a SIM has appeared in any slot.
                    if mm_state == -1:
                        try:
                            sfr_v = await props.call_get(
                                MODEM_INTERFACE, "StateFailedReason")
                            failed_reason = sfr_v.value if hasattr(sfr_v, 'value') else sfr_v
                        except Exception:
                            failed_reason = 0
                        if failed_reason in (2, 3):  # sim-missing / sim-error
                            logger.info(
                                "Failed-state retry: modem in FAILED with "
                                "sim-missing/sim-error — rescanning SimSlots "
                                "for re-inserted SIM",
                                extra={'interface_number': self.interface_number,
                                       'failed_reason': failed_reason})
                            try:
                                await self._handle_sim_missing_failover()
                            except Exception as e:
                                logger.debug(
                                    f"sim-missing rescan failover error: {e}",
                                    extra={'interface_number': self.interface_number})
                            continue
                    logger.info(
                        f"Modem not ready (state {mm_state}), "
                        "deferring retry to next interval",
                        extra={'interface_number': self.interface_number,
                               'modem_state': mm_state})
                    continue

                # Attempt connection — first clear any stale bearer context.
                # Carrier-side EPS context deactivation (e.g. esm-sync-up-with-nw)
                # leaves a stale bearer in ModemManager that will cause repeated
                # Simple.Connect() failures unless explicitly disconnected first.
                logger.info(
                    f"Failed-state retry #{self._failed_retry_attempt}: "
                    "clearing stale bearer before reconnect",
                    extra={'interface_number': self.interface_number,
                           'modem_state': mm_state,
                           'attempt': self._failed_retry_attempt})

                try:
                    simple_iface = self.proxy.get_interface(SIMPLE_INTERFACE)
                    if self.bearer_path:
                        await simple_iface.call_disconnect(self.bearer_path)
                        self.bearer_path = None
                        logger.info("Disconnected stale bearer for retry",
                                   extra={'interface_number': self.interface_number})
                    else:
                        # No bearer path — disconnect all bearers on this modem
                        await simple_iface.call_disconnect('/')
                        logger.info("Disconnected all bearers for retry (no bearer path)",
                                   extra={'interface_number': self.interface_number})
                    await asyncio.sleep(2)
                except Exception as disc_e:
                    logger.debug(f"Bearer disconnect before retry (non-fatal): {disc_e}",
                                extra={'interface_number': self.interface_number})

                # Escalate: on 3rd+ consecutive failure, cycle disable/enable to
                # force a complete EPS detach/reattach.  This clears network-side
                # state that Simple.Disconnect alone cannot reset.
                if self._failed_retry_escalation_threshold > 0 and self._failed_retry_attempt >= self._failed_retry_escalation_threshold:
                    logger.warning(
                        f"Failed-state retry #{self._failed_retry_attempt}: "
                        "escalating to modem disable/enable cycle",
                        extra={'interface_number': self.interface_number})
                    try:
                        modem_iface = self.proxy.get_interface(MODEM_INTERFACE)
                        await modem_iface.call_enable(False)
                        await asyncio.sleep(5)
                        await modem_iface.call_enable(True)
                        await asyncio.sleep(5)
                        logger.info("Modem disable/enable cycle complete",
                                   extra={'interface_number': self.interface_number})
                    except Exception as cycle_e:
                        logger.warning(
                            f"Modem disable/enable cycle failed: {cycle_e}",
                            extra={'interface_number': self.interface_number})

                # Re-apply band / network-mode configuration before the
                # reconnect.  apply_modem_configuration() only runs the
                # registration gate + APN cascade — it never re-writes the
                # allowed-band set.  A modem that dropped into FAILED while
                # camped on a single dead band (e.g. eutran-8 after a SIM
                # switch whose registration attempt timed out) will otherwise
                # stay parked on that band across every retry and never attach,
                # because nothing forces a fresh PLMN/cell scan.  Re-writing the
                # active SIM's bands (and nudging re-registration) here is the
                # programmatic equivalent of `mmcli --set-allowed-bands`, which
                # is what recovers the link by hand.  Anchored on
                # current_active_sim so a post-failover slot uses its own bands.
                try:
                    await self._configure_supported_bands()
                    await self._configure_network_mode()
                    await self._force_network_reregistration('failed_retry')
                except Exception as band_e:
                    logger.warning(
                        f"Failed-state retry band/mode re-apply failed (non-fatal): {band_e}",
                        extra={'interface_number': self.interface_number})

                # Clear stale failure reason before retry
                self.last_failure_reason = ''
                self.last_failed_apn = ''
                self.configured_apn_rejected = False

                # FAILED → CONNECTING
                self.transition(ModemEvent.CONNECT)
                await self.apply_modem_configuration()

                # Give connection time to establish
                await asyncio.sleep(10)

                # Check result
                if self.machine.current_state == ModemState.CONNECTED.value:
                    logger.info(
                        f"Failed-state retry #{self._failed_retry_attempt} "
                        "succeeded — connected",
                        extra={'interface_number': self.interface_number})
                    return

                if self.machine.current_state != ModemState.FAILED.value:
                    logger.info(
                        "FSM moved to %s after retry — exiting retry loop",
                        self.machine.current_state,
                        extra={'interface_number': self.interface_number})
                    return

                # Still FAILED — loop continues with next backoff
                logger.warning(
                    f"Failed-state retry #{self._failed_retry_attempt} "
                    "did not succeed, will retry",
                    extra={'interface_number': self.interface_number})

        except asyncio.CancelledError:
            logger.info("Failed-state retry loop cancelled",
                       extra={'interface_number': self.interface_number})
        except Exception as e:
            logger.error(f"Failed-state retry loop error: {e}",
                        extra={'interface_number': self.interface_number})

    async def setup_modem_manager_monitoring(self):
        """Setup ModemManager signal monitoring for instant modem add/remove detection"""
        try:
            logger.info("Setting up ModemManager signal monitoring",
                       extra={'interface_number': self.interface_number})

            # Get ObjectManager proxy for ModemManager
            introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, MODEM_MANAGER_PATH)
            self.object_manager_proxy = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, MODEM_MANAGER_PATH, introspect)
            object_manager = self.object_manager_proxy.get_interface(OBJECT_MANAGER_INTERFACE)

            # Set up signal handlers for hardware add/remove events
            object_manager.on_interfaces_removed(self.on_modem_removed)
            self.interfaces_removed_handler = self.on_modem_removed

            object_manager.on_interfaces_added(self.on_modem_added)
            self.interfaces_added_handler = self.on_modem_added

            logger.info("ModemManager signal monitoring active",
                       extra={'interface_number': self.interface_number})

        except Exception as e:
            logger.error(f"Failed to setup ModemManager signal monitoring: {e}",
                        extra={'interface_number': self.interface_number})

    async def on_modem_removed(self, path, interfaces):
        """Handle modem removal signal - instant detection of hardware disconnection"""
        try:
            logger.debug(f"ModemManager signal: modem removed at {path}",
                        extra={'interface_number': self.interface_number,
                               'removed_path': path,
                               'current_modem_path': self.modem_path})

            # Check if this is our current modem
            if hasattr(self, 'modem_path') and self.modem_path and path == self.modem_path:

                # During SIM switch, modem disappearance is EXPECTED (Telit LN920
                # resets when SetPrimarySimSlot is called).  Clear the proxy but
                # do NOT transition to SCANNING — the SIM switch code will rescan
                # for the modem itself once the hardware comes back.
                if self._sim_switch_in_progress:
                    logger.info("Modem disappeared during SIM switch (expected hardware reset)",
                               extra={'interface_number': self.interface_number,
                                      'modem_path': path})
                    # Tear down passthrough so dnsmasq stops re-advertising
                    # the old carrier v6 prefix to the LAN.  Without this,
                    # the previous bearer's RA stream keeps refreshing the
                    # SLAAC address on the downstream host the entire time
                    # the modem is gone (and through any subsequent v4-only
                    # bearer if the deprecation path never re-runs).
                    try:
                        if self._passthrough.cfg.is_active():
                            await self._passthrough.teardown()
                    except Exception as pt_err:
                        logger.warning("IP passthrough teardown failed during SIM switch: %s",
                                      pt_err,
                                      extra={'interface_number': self.interface_number})
                    # Invalidate the proxy — it points to a stale D-Bus path
                    self.proxy = None
                    self.modem_path = None
                    self.bearer_path = None
                    return   # ← skip all the normal removal cleanup / state change

                logger.warning("Current modem removed via signal, transitioning to scanning",
                              extra={'interface_number': self.interface_number,
                                     'modem_path': path})

                # Set removal flag so CancelledError handlers log the right reason
                self._modem_removed = True

                # Store original state for logging
                original_state = self.machine.current_state

                if original_state in [ModemState.CONNECTED.value,
                                      ModemState.USAGE_MONITORING.value,
                                      ModemState.DISCONNECTING.value]:
                    # Salvage the active SIM's in-flight session usage before we
                    # drop the bearer reference.  The live bearer is usually
                    # already gone here, so the flush falls back to the cached
                    # session bytes captured by the monitor loop / status build.
                    try:
                        await self._flush_active_usage('modem_removed')
                    except Exception as flush_err:
                        logger.debug(f"Usage flush on modem removal failed (non-fatal): {flush_err}",
                                    extra={'interface_number': self.interface_number})
                    self._record_bearer_down('modem_removed')

                # Tear down passthrough immediately on modem removal so
                # dnsmasq stops emitting RAs that refresh the old carrier
                # v6 prefix on the downstream host.  The bearer-disconnect
                # timer below would normally do this, but it gets cancelled
                # at the end of this handler when the modem is gone — so
                # without an explicit teardown here the LAN host keeps
                # SLAAC'ing the dead carrier prefix for hours.
                try:
                    if self._passthrough.cfg.is_active():
                        await self._passthrough.teardown()
                except Exception as pt_err:
                    logger.warning("IP passthrough teardown failed on modem removal: %s",
                                  pt_err,
                                  extra={'interface_number': self.interface_number})

                # Clean up current modem references
                self.proxy = None
                self.modem_path = None
                self.bearer_path = None

                # Cancel any ongoing initial configuration task
                if hasattr(self, '_initial_config_task') and self._initial_config_task and not self._initial_config_task.done():
                    self._initial_config_task.cancel()
                    self._initial_config_task = None
                    logger.info("Cancelled in-progress initial configuration due to modem removal",
                               extra={'interface_number': self.interface_number})
                self.initial_configuration_in_progress = False

                # Cancel ALL ongoing tasks and timers for prompt cleanup
                if hasattr(self, 'usage_monitor_task') and self.usage_monitor_task and not self.usage_monitor_task.done():
                    self.usage_monitor_task.cancel()
                    logger.info("Cancelled usage monitoring task due to modem removal",
                               extra={'interface_number': self.interface_number})
                if hasattr(self, 'failback_task') and self.failback_task and not self.failback_task.done():
                    self.failback_task.cancel()
                    self.failback_task = None
                    logger.info("Cancelled failback monitor due to modem removal",
                               extra={'interface_number': self.interface_number})

                # Cancel bearer disconnect timer (no point waiting if modem is gone)
                if hasattr(self, '_bearer_disconnect_timer') and self._bearer_disconnect_timer and not self._bearer_disconnect_timer.done():
                    self._bearer_disconnect_timer.cancel()
                    self._bearer_disconnect_timer = None
                    logger.info("Cancelled bearer disconnect timer due to modem removal",
                               extra={'interface_number': self.interface_number})

                # Cancel registration debounce timer (modem gone, debounce is moot)
                if hasattr(self, '_registration_debounce_timer') and self._registration_debounce_timer and not self._registration_debounce_timer.done():
                    self._registration_debounce_timer.cancel()
                    self._registration_debounce_timer = None
                    logger.info("Cancelled registration debounce timer due to modem removal",
                               extra={'interface_number': self.interface_number})

                # Cancel connectivity monitoring (ping tests are pointless without modem)
                if hasattr(self, 'connectivity_monitor_task') and self.connectivity_monitor_task and not self.connectivity_monitor_task.done():
                    self.connectivity_monitor_task.cancel()
                    self.connectivity_monitor_task = None
                    logger.info("Cancelled connectivity monitoring due to modem removal",
                               extra={'interface_number': self.interface_number})

                # Cancel IP monitoring task
                if hasattr(self, '_ip_monitoring_task') and self._ip_monitoring_task and not self._ip_monitoring_task.done():
                    self._ip_monitoring_task.cancel()
                    self._ip_monitoring_task = None
                    logger.info("Cancelled IP monitoring due to modem removal",
                               extra={'interface_number': self.interface_number})

                # Set interface DOWN immediately (modem is gone, don't wait)
                try:
                    await self._set_interface_down()
                    logger.info("Interface set DOWN immediately due to modem removal",
                               extra={'interface_number': self.interface_number})
                except Exception as e:
                    logger.debug(f"Could not set interface DOWN on removal (may already be down): {e}",
                                extra={'interface_number': self.interface_number})

                # For hardware removal, force transition to SCANNING from ANY state
                # With the enhanced transition table, we can go directly to SCANNING from any state
                try:
                    logger.info(f"Transitioning from {original_state} to SCANNING due to hardware removal",
                               extra={'interface_number': self.interface_number})
                    self.transition(ModemEvent.START_SCAN)
                except Exception as e:
                    logger.warning(f"Could not transition to scanning from {original_state}: {e}",
                                 extra={'interface_number': self.interface_number})
                    # Force state reset as last resort
                    logger.info("Force setting state to SCANNING",
                               extra={'interface_number': self.interface_number})
                    self.machine.set_state(ModemState.SCANNING)  # pylint: disable=no-member

                # Start scanning again (don't await - let it run in background)
                self._safe_create_task(self.scan_for_modem())

        except Exception as e:
            logger.error(f"Error handling modem removal signal: {e}",
                        extra={'interface_number': self.interface_number})

    async def on_modem_added(self, path, interfaces):
        """Handle modem addition signal - can potentially speed up modem detection"""
        try:
            logger.debug(f"ModemManager signal: modem added at {path}",
                        extra={'interface_number': self.interface_number,
                               'added_path': path})

            # Only process if we're currently scanning for a modem
            if self.machine.current_state == ModemState.SCANNING.value:
                logger.info("New modem detected via signal while scanning",
                           extra={'interface_number': self.interface_number,
                                  'modem_path': path})
                # The ongoing scan will pick this up naturally

        except Exception as e:
            logger.error(f"Error handling modem addition signal: {e}",
                        extra={'interface_number': self.interface_number})

    async def scan_for_modem(self):
        """
        Continuously scan for modem using Device property with exponential backoff.
        Never gives up - handles hot-plug modems and modem resets.
        """
        INITIAL_SCAN_INTERVAL = 5   # Start checking every 5 seconds
        MAX_SCAN_INTERVAL = 60      # Maximum 60 seconds between scans
        MAX_FAST_SCANS = 12         # Fast scans for first minute (12 * 5 = 60s)

        current_interval = INITIAL_SCAN_INTERVAL
        scan_count = 0

        logger.info("Starting continuous modem scan using Device property",
                   extra={'interface_number': self.interface_number,
                          'target_modem_id': f"modem{self.interface_number}",
                          'initial_interval': INITIAL_SCAN_INTERVAL,
                          'max_interval': MAX_SCAN_INTERVAL})

        while True:  # Scan forever until modem found
            scan_count += 1

            try:
                msg = Message(
                    destination=MODEM_MANAGER_SERVICE,
                    path=MODEM_MANAGER_PATH,
                    interface=OBJECT_MANAGER_INTERFACE,
                    member="GetManagedObjects"
                )
                reply = await self.bus.call(msg)

                if reply.message_type.name != "METHOD_RETURN":
                    logger.error("D-Bus GetManagedObjects failed",
                               extra={'interface_number': self.interface_number,
                                      'scan_count': scan_count})
                    await asyncio.sleep(current_interval)
                    continue

                managed_objects = reply.body[0]
                paths = [
                    path for path, interfaces in managed_objects.items()
                    if MODEM_INTERFACE in interfaces
                ]

                if paths:
                    logger.debug("Found modem paths during scan",
                               extra={'interface_number': self.interface_number,
                                      'paths': str(paths),
                                      'scan_count': scan_count})

                    for path in paths:
                        try:
                            introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, path)
                            proxy = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, path, introspect)
                            props = proxy.get_interface("org.freedesktop.DBus.Properties")

                            # Use Device property for modem matching (contains "modem0", "modem1", etc.)
                            device_variant = await props.call_get(MODEM_INTERFACE, "Device")
                            physdev_uid = device_variant.value  # Extract string from Variant
                            target_modem_id = f"modem{self.interface_number}"

                            logger.debug("Checking modem identity",
                                       extra={'interface_number': self.interface_number,
                                              'modem_path': path,
                                              'physdev_uid': physdev_uid,
                                              'target_modem_id': target_modem_id,
                                              'scan_count': scan_count})

                            logger.debug(f"Comparing device '{physdev_uid}' with target '{target_modem_id}'",
                                        extra={'interface_number': self.interface_number})

                            if physdev_uid == target_modem_id:
                                # MODEM FOUND! Get additional info for logging
                                device_variant = await props.call_get(MODEM_INTERFACE, "Device")
                                device = device_variant.value

                                self.proxy = proxy
                                self.modem_path = path

                                # Set proxy for connection manager
                                self.connection_manager.set_proxy(proxy)

                                # Enable signal monitoring for accurate dBm readings
                                await self._enable_signal_monitoring()

                                # Clear modem removal flag now that we have a modem again
                                self._modem_removed = False

                                logger.info("Modem found and matched by Device property",
                                           extra={'interface_number': self.interface_number,
                                                  'modem_path': path,
                                                  'device': device,
                                                  'physdev_uid': physdev_uid,
                                                  'scan_count': scan_count,
                                                  'total_scan_time': scan_count * current_interval})

                                # Get modem state to log it
                                await self._log_initial_modem_state()

                                # Only transition if not already in MODEM_FOUND state
                                if self.machine.current_state != ModemState.MODEM_FOUND.value:
                                    self.transition(ModemEvent.MODEM_FOUND)

                                # Always call on_modem_found to check for config and proceed
                                logger.debug("About to call on_modem_found()",
                                           extra={'interface_number': self.interface_number})
                                try:
                                    await self.on_modem_found()
                                    logger.debug("on_modem_found() completed successfully",
                                               extra={'interface_number': self.interface_number})
                                except Exception as e:
                                    logger.error(f"on_modem_found() failed: {e}",
                                               extra={'interface_number': self.interface_number})
                                    # Continue with scan despite on_modem_found error
                                return  # EXIT - Modem found successfully

                        except Exception as e:
                            logger.debug(f"Could not get Device property for modem at {path}: {e}",
                                        extra={'interface_number': self.interface_number,
                                               'scan_count': scan_count})
                            continue
                else:
                    logger.debug("No modems found in ModemManager",
                               extra={'interface_number': self.interface_number,
                                      'scan_count': scan_count})

            except Exception as e:
                logger.error(f"Scan error: {e}",
                            extra={'interface_number': self.interface_number,
                                   'scan_count': scan_count})

            # BACKOFF LOGIC: Start fast, then slow down for efficiency
            if scan_count <= MAX_FAST_SCANS:
                # Fast scanning for first minute - modem might be initializing
                next_interval = INITIAL_SCAN_INTERVAL
                logger.debug(f"Fast scan mode: next scan in {next_interval} seconds",
                            extra={'interface_number': self.interface_number,
                                   'scan_count': scan_count,
                                   'target_modem_id': f"modem{self.interface_number}"})
            else:
                # Exponential backoff after first minute, but cap at maximum
                current_interval = min(current_interval * 1.2, MAX_SCAN_INTERVAL)  # Gentle 1.2x increase
                next_interval = current_interval
                logger.info(f"Long-term scan mode: next scan in {next_interval:.1f} seconds",
                           extra={'interface_number': self.interface_number,
                                  'scan_count': scan_count,
                                  'target_modem_id': f"modem{self.interface_number}"})

            await asyncio.sleep(next_interval)

            # Periodic status update for long-running scans
            if scan_count % 20 == 0:  # Every 20 scans
                total_time = scan_count * INITIAL_SCAN_INTERVAL if scan_count <= MAX_FAST_SCANS else \
                            MAX_FAST_SCANS * INITIAL_SCAN_INTERVAL + (scan_count - MAX_FAST_SCANS) * current_interval
                logger.info(f"Still scanning for modem - {scan_count} attempts over {total_time/60:.1f} minutes",
                           extra={'interface_number': self.interface_number,
                                  'target_modem_id': f"modem{self.interface_number}",
                                  'scan_count': scan_count})

    async def _log_initial_modem_state(self):
        """Log the initial state of the found modem with enhanced dual-SIM info"""
        try:
            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")

            # Get basic modem state
            state_variant = await props.call_get(MODEM_INTERFACE, "State")
            state = state_variant.value  # Extract value from Variant
            state_names = {
                -1: "FAILED", 0: "UNKNOWN", 1: "INITIALIZING", 2: "LOCKED",
                3: "DISABLED", 4: "DISABLING", 5: "ENABLING", 6: "ENABLED",
                7: "SEARCHING", 8: "REGISTERED", 9: "DISCONNECTING", 10: "CONNECTING", 11: "CONNECTED"
            }
            state_name = state_names.get(state, f"UNKNOWN({state})")

            # Get basic modem info
            try:
                device_variant = await props.call_get(MODEM_INTERFACE, "Device")
                physdev_uid = device_variant.value  # Extract string from Variant
                device = device_variant.value
                manufacturer_variant = await props.call_get(MODEM_INTERFACE, "Manufacturer")
                manufacturer = manufacturer_variant.value
                model_variant = await props.call_get(MODEM_INTERFACE, "Model")
                model = model_variant.value

                # Get SIM slot information and initialize tracking
                sim_slots = []
                try:
                    # Get number of SIM slots
                    sim_slot_count_variant = await props.call_get(MODEM_INTERFACE, "SimSlots")
                    sim_slot_count = sim_slot_count_variant.value
                    primary_sim_slot_variant = await props.call_get(MODEM_INTERFACE, "PrimarySimSlot")
                    primary_sim_slot = primary_sim_slot_variant.value

                    # Initialize SIM tracking
                    self.current_active_sim = primary_sim_slot

                    logger.info("Modem has multiple SIM slots",
                               extra={'interface_number': self.interface_number,
                                      'sim_slot_count': len(sim_slot_count),
                                      'primary_sim_slot': primary_sim_slot,
                                      'current_active_sim': self.current_active_sim})

                    # Check each SIM slot
                    for slot_path in sim_slot_count:
                        if slot_path and slot_path != '/':  # Valid SIM path
                            try:
                                sim_introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, slot_path)
                                sim_proxy = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, slot_path, sim_introspect)
                                sim_props = sim_proxy.get_interface("org.freedesktop.DBus.Properties")

                                # Get SIM details
                                sim_interface = "org.freedesktop.ModemManager1.Sim"
                                imsi_variant = await sim_props.call_get(sim_interface, "Imsi")
                                imsi = imsi_variant.value
                                operator_name_variant = await sim_props.call_get(sim_interface, "OperatorName")
                                operator_name = operator_name_variant.value
                                sim_identifier_variant = await sim_props.call_get(sim_interface, "SimIdentifier")
                                sim_identifier = sim_identifier_variant.value

                                sim_slots.append({
                                    'path': slot_path,
                                    'imsi': imsi or 'Unknown',
                                    'operator': operator_name or 'Unknown',
                                    'sim_id': sim_identifier or 'Unknown'
                                })

                            except Exception as sim_e:
                                logger.debug(f"Could not get details for SIM at {slot_path}: {sim_e}",
                                            extra={'interface_number': self.interface_number})
                                sim_slots.append({
                                    'path': slot_path,
                                    'imsi': 'Error',
                                    'operator': 'Error',
                                    'sim_id': 'Error'
                                })
                        else:
                            sim_slots.append({
                                'path': 'Empty',
                                'imsi': 'No SIM',
                                'operator': 'No SIM',
                                'sim_id': 'No SIM'
                            })

                except Exception as e:
                    logger.debug(f"Could not get SIM slot information: {e}",
                                extra={'interface_number': self.interface_number})
                    # Fallback - try single SIM path
                    try:
                        sim_path_variant = await props.call_get(MODEM_INTERFACE, "Sim")
                        sim_path = sim_path_variant.value
                        sim_slots = [{'path': str(sim_path) if sim_path else 'None'}]
                        self.current_active_sim = 1  # Default to slot 1 for single SIM
                    except Exception:
                        sim_slots = [{'path': 'Unknown'}]
                        self.current_active_sim = 1

                # Get signal quality if available
                # SignalQuality is (uint32 percent, bool recently_updated)
                signal_quality = None
                try:
                    signal_quality_variant = await props.call_get(MODEM_INTERFACE, "SignalQuality")
                    sq = signal_quality_variant.value
                    signal_quality = sq[0] if isinstance(sq, (list, tuple)) and sq else sq
                except Exception:
                    pass

                # Get registration state if available
                registration_state = None
                try:
                    registration_state_variant = await props.call_get(MODEM_INTERFACE, "AccessTechnologies")
                    registration_state = registration_state_variant.value
                except Exception:
                    pass

                logger.info("Modem initial state with dual-SIM details",
                           extra={'interface_number': self.interface_number,
                                  'modem_state': state_name,
                                  'physdev_uid': physdev_uid,
                                  'device': device,
                                  'manufacturer': manufacturer or 'Unknown',
                                  'model': model or 'Unknown',
                                  'sim_slots': sim_slots,
                                  'signal_quality': signal_quality,
                                  'registration_state': registration_state,
                                  'current_active_sim': self.current_active_sim})

            except Exception as e:
                logger.info("Modem initial state (basic)",
                           extra={'interface_number': self.interface_number,
                                  'modem_state': state_name,
                                  'error': str(e)})

        except Exception as e:
            logger.warning(f"Could not get initial modem state: {e}",
                          extra={'interface_number': self.interface_number})

    async def on_modem_found(self):
        if not self.proxy:
            return

        # Set up a single PropertiesChanged handler for all interfaces on this proxy.
        # dbus_next delivers all PropertiesChanged signals through one callback;
        # registering multiple callbacks on the same interface may replace or
        # stack depending on the version, so we use one dispatcher instead.
        try:
            modem_properties_iface = self.proxy.get_interface("org.freedesktop.DBus.Properties")
            modem_properties_iface.on_properties_changed(self._dispatch_properties_changed)
            logger.info("PropertiesChanged signal monitoring enabled (Modem + 3GPP)",
                       extra={'interface_number': self.interface_number})
        except Exception as e:
            logger.error(f"Failed to set up signal handlers: {e}",
                        extra={'interface_number': self.interface_number})

        logger.info("Modem signal handlers registered - checking for configuration",
                   extra={'interface_number': self.interface_number,
                          'current_state': self.machine.current_state,
                          'has_config': bool(self.config)})

        # Always transition to WAITING_FOR_CONFIG first (valid from MODEM_FOUND)
        self.transition(ModemEvent.WAIT_FOR_CONFIG)

        # If config says the interface is admin-disabled, drive the
        # modem to airplane mode now and stop — don't run the initial
        # configuration cascade.  Covers the cold-start case where the
        # FSM service restarted with cached `interface_disabled=True`.
        if getattr(self, '_admin_disabled', False) or (
                self.config and self.config.get('interface_disabled')):
            logger.info("Interface is admin-disabled — driving modem to airplane mode",
                       extra={'interface_number': self.interface_number})
            self._admin_disabled = True
            self.user_disconnected = True
            self._safe_create_task(self._enter_airplane_mode())
            # Still synthesize an initial state read so observability
            # works, but don't run the connection cascade.
            self._safe_create_task(self._dispatch_initial_modem_state())
            return

        # Check if config was already applied before modem was found
        if self.config:
            logger.info("Configuration already available, applying immediately",
                       extra={'interface_number': self.interface_number,
                              'config_keys': list(self.config.keys())})
            # Now transition to CONFIGURING (valid from WAITING_FOR_CONFIG)
            self.transition(ModemEvent.CONFIG_UPDATE)
            self._initial_config_task = self._safe_create_task(self._configure_modem_initial())

        # Start periodic SIM check if we transition to WAITING_FOR_SIM
        if self.machine.current_state == ModemState.WAITING_FOR_SIM.value:
            self._safe_create_task(self._periodic_sim_check())

        # Synthesize a state event for the modem's CURRENT state.  The
        # PropertiesChanged signal only fires on *transitions*, so if the
        # modem is already sitting in FAILED (e.g. SIM was pulled before
        # the FSM started, or vyos-wwan-state-machine was restarted while
        # the modem was already in `state=failed reason=sim-missing`), our
        # SIM-failover handler never fires.  Re-read State and dispatch it
        # so the existing handle_modem_event() recovery path runs at boot.
        self._safe_create_task(self._dispatch_initial_modem_state())

    async def _dispatch_initial_modem_state(self):
        """Re-read modem State at startup and feed it to handle_modem_event.

        Covers the case where the modem is already in FAILED/UNKNOWN when
        we attach — no D-Bus StateChanged signal will fire for that
        pre-existing condition, so we must observe and act on it
        ourselves.  Waits briefly for any in-flight initial configuration
        so SIM-failover logic has a populated config to consult.
        """
        try:
            if self._initial_config_task is not None:
                try:
                    await asyncio.wait_for(
                        asyncio.shield(self._initial_config_task), timeout=30.0)
                except (asyncio.TimeoutError, Exception):
                    pass  # proceed regardless of config-task outcome

            if not self.proxy:
                return
            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
            state_v = await props.call_get(MODEM_INTERFACE, "State")
            state = state_v.value if hasattr(state_v, 'value') else state_v

            # Only synthesize for actionable initial states; routine
            # states (ENABLED/SEARCHING/REGISTERED/...) will be driven
            # naturally by the FSM as configuration progresses.
            if state in (-1, 0):
                logger.warning(
                    "Modem already in FAILED/UNKNOWN at attach — "
                    "synthesizing state event so recovery (e.g. SIM "
                    "failover) runs without waiting for a transition",
                    extra={'interface_number': self.interface_number,
                           'mm_state': state})
                self._last_modem_state = state

                # The handle_modem_event() FAILED branch suppresses
                # itself when *we* triggered the disable/reset.  For a
                # synthesized cold-attach event that's by definition not
                # the case, so clear those guards before dispatching;
                # otherwise the event is silently swallowed and
                # SIM-failover never runs.  (See also the matching
                # cleanup in the _configure_modem_initial except branch.)
                if (self.service_initiated_disable
                        or self.reset_operation_in_progress
                        or self._is_in_reset_grace_period()):
                    logger.info(
                        "Clearing stale service-disable/reset guards "
                        "before synthesizing FAILED state event",
                        extra={'interface_number': self.interface_number,
                               'service_initiated_disable':
                                   self.service_initiated_disable,
                               'reset_operation_in_progress':
                                   self.reset_operation_in_progress,
                               'reset_grace_period_remaining':
                                   max(0, self.reset_grace_period_end
                                       - time.time())})
                    self.service_initiated_disable = False
                    self.reset_operation_in_progress = False
                    self.reset_grace_period_end = 0

                self.handle_modem_event(state, None)
        except Exception as e:
            logger.debug(
                f"Initial state dispatch failed: {e}",
                extra={'interface_number': self.interface_number})

    def _dispatch_properties_changed(self, interface_name, changed_properties, invalidated_properties):
        """Unified PropertiesChanged dispatcher.

        Routes signals to the appropriate handler based on D-Bus interface name.
        """
        self._handle_modem_properties_changed(interface_name, changed_properties, invalidated_properties)
        self.handle_3gpp_properties(interface_name, changed_properties, invalidated_properties)

    def _handle_modem_properties_changed(self, interface_name, changed_properties, invalidated_properties):
        """Handle ModemManager PropertiesChanged D-Bus signal for State changes"""
        try:
            # Only process signals from the Modem interface
            if interface_name != "org.freedesktop.ModemManager1.Modem":
                return

            # Debug: Show exactly what we received
            logger.debug(f"PropertiesChanged signal: interface={interface_name}, "
                        f"changed={list(changed_properties.keys()) if changed_properties else 'None'}",
                       extra={'interface_number': self.interface_number})

            # Check if State property changed
            if changed_properties and 'State' in changed_properties:
                new_state = changed_properties['State'].value

                # Get current state for comparison (if available)
                old_state = getattr(self, '_last_modem_state', None)
                self._last_modem_state = new_state

                # Convert state numbers to readable names
                old_state_name = self._get_state_name(old_state) if old_state else "unknown"
                new_state_name = self._get_state_name(new_state)

                logger.info("🔄 ModemManager State change detected",
                           extra={'interface_number': self.interface_number,
                                  'old_state': f"{old_state} ({old_state_name})" if old_state else "unknown",
                                  'new_state': f"{new_state} ({new_state_name})"})

                # Call the existing FSM handler which will handle state transitions
                self.handle_modem_event(new_state, None)
            else:
                # Log other property changes for debugging
                if changed_properties:
                    logger.debug(f"Other modem properties changed: {list(changed_properties.keys())}",
                               extra={'interface_number': self.interface_number})

        except Exception as e:
            logger.error(f"Error handling modem properties changed signal: {e}",
                        extra={'interface_number': self.interface_number})

    def _get_state_name(self, state_value):
        """Convert ModemManager state number to readable name"""
        # ModemManager state values from the D-Bus API
        state_map = {
            -1: "FAILED",
            0: "UNKNOWN",
            1: "INITIALIZING",
            2: "LOCKED",
            3: "DISABLED",
            4: "DISABLING",
            5: "ENABLING",
            6: "ENABLED",
            7: "SEARCHING",
            8: "REGISTERED",
            9: "DISCONNECTING",
            10: "CONNECTING",
            11: "CONNECTED"
        }
        return state_map.get(state_value, f"UNKNOWN_STATE_{state_value}")

    def _get_registration_state_name(self, reg_state):
        """Convert 3GPP registration state number to readable name"""
        # 3GPP registration state values from ModemManager D-Bus API
        reg_state_map = {
            0: "IDLE",           # Not registered, not searching
            1: "HOME",           # Registered on home network
            2: "SEARCHING",      # Not registered, but searching
            3: "DENIED",         # Registration denied
            4: "UNKNOWN",        # Unknown registration state
            5: "ROAMING"         # Registered on roaming network
        }
        return reg_state_map.get(reg_state, f"UNKNOWN_REG_STATE_{reg_state}")

    def handle_modem_properties(self, interface_name, changed_properties, invalidated_properties):
        """Handle modem property changes (signal strength, operator, etc.)"""
        logger.info("Modem properties changed",
                   extra={'interface_number': self.interface_number,
                          'interface': interface_name,
                          'changed_properties': list(changed_properties.keys())})

        # Handle specific property changes
        # SignalQuality is (uint32 percent, bool recently_updated)
        if 'SignalQuality' in changed_properties:
            sq = changed_properties['SignalQuality'].value
            signal_percent = sq[0] if isinstance(sq, (list, tuple)) and sq else sq
            logger.info("Signal strength changed",
                       extra={'interface_number': self.interface_number,
                              'signal_percent': signal_percent})

        # Handle SIM slot changes
        if 'PrimarySimSlot' in changed_properties:
            new_sim = changed_properties['PrimarySimSlot'].value
            old_sim = self.current_active_sim
            self.current_active_sim = new_sim

            if old_sim != new_sim:
                self._record_sim_switch(
                    old_sim,
                    new_sim,
                    self.sim_switch_reason or 'runtime_slot_change',
                )
                logger.info("Active SIM changed",
                           extra={'interface_number': self.interface_number,
                                  'from_sim': old_sim,
                                  'to_sim': new_sim,
                                  'config_sim': self.config_active_sim,
                                  'auto_switch': new_sim != self.config_active_sim})

                # If this wasn't our requested switch, it was automatic
                if new_sim != self.config_active_sim:
                    self.sim_switch_reason = 'automatic_failover'
                    logger.warning("Automatic SIM failover detected",
                                  extra={'interface_number': self.interface_number,
                                         'new_sim': new_sim,
                                         'config_sim': self.config_active_sim,
                                         'sim_switch_reason': self.sim_switch_reason})

        # Handle runtime active-SIM object changes (can happen when an
        # operator flips SIM mux + modem reset out-of-band, without using
        # ModemManager SetPrimarySimSlot). In that scenario PrimarySimSlot
        # may remain unchanged while the actual SIM identity changes.
        if 'Sim' in changed_properties:
            new_sim_path = changed_properties['Sim'].value
            old_sim_path = getattr(self, 'current_sim_path', None)
            self.current_sim_path = new_sim_path

            if old_sim_path and old_sim_path != new_sim_path:
                now_ts = time.time()
                debounce_window = getattr(
                    self, '_sim_path_change_debounce_seconds', 5.0)
                last_ts = getattr(self, '_sim_path_change_last_ts', 0.0)
                last_from = getattr(self, '_sim_path_change_last_from', None)
                last_to = getattr(self, '_sim_path_change_last_to', None)

                same_edge = (last_from == old_sim_path and last_to == new_sim_path)
                flip_flop_edge = (last_from == new_sim_path and last_to == old_sim_path)
                in_window = (now_ts - last_ts) < debounce_window

                if in_window and (same_edge or flip_flop_edge):
                    logger.debug(
                        "Ignoring noisy rapid Sim path churn during debounce window",
                        extra={'interface_number': self.interface_number,
                               'old_sim_path': old_sim_path,
                               'new_sim_path': new_sim_path,
                               'debounce_seconds': debounce_window,
                               'age_seconds': round(now_ts - last_ts, 3)})
                    return

                self._sim_path_change_last_ts = now_ts
                self._sim_path_change_last_from = old_sim_path
                self._sim_path_change_last_to = new_sim_path

                logger.warning("Active SIM object changed at runtime — invalidating SIM/APN cache",
                              extra={'interface_number': self.interface_number,
                                     'old_sim_path': old_sim_path,
                                     'new_sim_path': new_sim_path,
                                     'active_slot': self.current_active_sim})

                # Force fresh SIM/APN discovery on next connection attempt.
                self.last_known_sim_info = {}
                self.connected_apn = None
                self._clear_persisted_apn()
                self.sim_changed = True

    def handle_3gpp_properties(self, interface_name, changed_properties, invalidated_properties):
        """Handle 3GPP network property changes"""
        # Only process signals from the 3GPP interface
        if interface_name != "org.freedesktop.ModemManager1.Modem.Modem3gpp":
            return

        logger.info("🌐 3GPP properties changed",
                   extra={'interface_number': self.interface_number,
                          'changed_properties': list(changed_properties.keys()) if changed_properties else 'None'})

        # Handle registration state changes
        if changed_properties and 'RegistrationState' in changed_properties:
            reg_state = changed_properties['RegistrationState'].value
            reg_state_name = self._get_registration_state_name(reg_state)
            logger.info("📡 Registration state changed",
                       extra={'interface_number': self.interface_number,
                              'registration_state': f"{reg_state} ({reg_state_name})"})

            # Enhanced interface management: Consider both bearer AND registration state
            # Prevent concurrent registration handling to avoid D-Bus feedback loops
            if not self.registration_handling_in_progress:
                self._safe_create_task(self._handle_registration_state_change(reg_state, reg_state_name))
            else:
                logger.debug("Registration state change ignored - handling already in progress",
                           extra={'interface_number': self.interface_number,
                                  'registration_state': f"{reg_state} ({reg_state_name})"})

    def _handle_connected_registration_drop(self, mm_state, reason='registration_loss'):
        """Recover when a CONNECTED modem falls below REGISTERED.

        ModemManager only emits the ``CONNECTED → REGISTERED`` ("bearer lost
        but still camped") transition for some deactivations.  When the modem
        instead drops straight to ``SEARCHING`` (7) or ``ENABLED`` (6) — e.g.
        the active ``supported-bands`` set no longer matches any serving cell,
        or coverage was lost — there is no camped cell and the bearer is dead.
        These sub-registered states had no CONNECTED-state handler, so the FSM
        used to stay stuck reporting CONNECTED with no signal and never
        recover.

        Mirrors the ``CONNECTED → REGISTERED`` recovery: stamp the disconnect
        reason, stop interface monitoring, transition to DISCONNECTING and kick
        the standard disconnection-recovery path (which re-waits for
        registration and reconnects, or fails over / parks FAILED).
        """
        if self.user_disconnected:
            logger.info("Modem dropped below REGISTERED while CONNECTED but user "
                       "requested disconnect — not auto-recovering",
                       extra={'interface_number': self.interface_number,
                              'modem_state': mm_state})
            return
        if self.initial_configuration_in_progress:
            logger.debug("Modem dropped below REGISTERED during initial config — "
                        "deferring to config flow",
                        extra={'interface_number': self.interface_number,
                               'modem_state': mm_state})
            return
        self._disconnect_reason_override = reason
        logger.warning("Modem dropped to %s while FSM CONNECTED — registration "
                      "lost, triggering reconnection",
                      'SEARCHING' if mm_state == 7 else 'ENABLED',
                      extra={'interface_number': self.interface_number,
                             'modem_state': mm_state,
                             'fsm_state': self.machine.current_state})
        try:
            self._safe_create_task(self._stop_network_interface_monitoring())
        except RuntimeError:
            pass
        self.transition(ModemEvent.DISCONNECT)
        self._safe_create_task(self.handle_disconnection_recovery())

    async def _finalize_connected_from_signal(self):
        """Finalise a connection that reached CONNECTED via the MM state-11 signal.

        This is the async counterpart to the connected-side bringup in the
        inline ``_configure_modem_initial`` success block, used by the
        fresh-rebuild retry path (failed-retry loop → apply_modem_configuration
        → APN cascade), where the FSM advances to CONNECTED through
        ``handle_modem_event`` rather than inline.

        Applies bearer IP behind the same data-path gate: if the bearer
        registered but cannot route (a dead path that survives the patient
        link-up retry), ``_apply_bearer_ip_or_fail`` tears the session down,
        drives CONNECTION_FAILED and offers SIM failover, and we stop here so
        the dead SIM is not finalised as CONNECTED.  On the normal (good) path
        the first apply succeeds immediately, so there is no added latency.
        """
        # The FSM may have already moved on (e.g. a fast disconnect) by the
        # time this task runs — only finalise if we are still CONNECTED.
        if self.machine.current_state not in (ModemState.CONNECTED.value,
                                              ModemState.USAGE_MONITORING.value):
            logger.debug("Skipping connected finalise — FSM no longer CONNECTED",
                        extra={'interface_number': self.interface_number,
                               'current_state': self.machine.current_state})
            return

        if not await self._apply_bearer_ip_or_fail('modem_state_connected'):
            return

        # Start network interface management
        try:
            if self.ensure_link_up_on_connect:
                self._safe_create_task(self._ensure_interface_up())
            self._safe_create_task(self._start_network_interface_monitoring())
        except RuntimeError:
            # No event loop running (e.g., during tests) - ignore
            pass

        # Reset failover counters — connection is stable
        self._reset_failover_counters()
        self._record_bearer_up('modem_state_connected')
        self._ensure_usage_monitoring_started('handle_modem_event')

        # Start connectivity monitoring (ping tests) if configured
        self._safe_create_task(self.start_connectivity_monitoring())

        # Start failback monitor if we're on the failover SIM
        self._start_failback_monitor()

    def handle_modem_event(self, mm_state, _):
        """Handle ModemManager state changes with enhanced hot-swap support"""
        logger.info("Modem state changed",
                   extra={'interface_number': self.interface_number,
                          'modem_state': mm_state,
                          'current_fsm_state': self.machine.current_state})

        current_fsm_state = self.machine.current_state

        # ── Suppress modem state events during SIM switch ────────────
        # When a SIM switch is in progress the modem will cycle through
        # DISABLED → LOCKED → ENABLED → SEARCHING → REGISTERED states.
        # None of these should trigger failover, insertion checks, or
        # connection attempts — the SIM switch flow handles everything.
        if self._sim_switch_in_progress:
            logger.debug(f"Modem state {mm_state} ignored during SIM switch",
                        extra={'interface_number': self.interface_number,
                               'modem_state': mm_state})
            return

        # Enhanced SIM hot-swap detection
        if mm_state == 2:  # LOCKED (SIM missing or PIN required)
            if current_fsm_state in [ModemState.CONFIGURING.value, ModemState.CONNECTING.value,
                                    ModemState.CONNECTED.value, ModemState.USAGE_MONITORING.value]:
                # Distinguish between PIN-locked and actually missing SIM
                self._safe_create_task(self._handle_locked_state_detection())

        elif mm_state == 3:  # DISABLED
            if current_fsm_state in [ModemState.CONFIGURING.value, ModemState.CONNECTING.value,
                                    ModemState.CONNECTED.value, ModemState.FAILED.value,
                                    ModemState.USAGE_MONITORING.value, ModemState.DISCONNECTED.value,
                                    ModemState.REGISTERED_IDLE.value, ModemState.DISCONNECTING.value]:
                # Don't trigger SIM missing if this is service-initiated or we're in reset grace period
                if not self.service_initiated_disable and not self._is_in_reset_grace_period():
                    self._cancel_failed_retry()  # SIM event supersedes retry
                    self.transition(ModemEvent.SIM_MISSING)
                    self._safe_create_task(self._handle_sim_missing_failover())
                else:
                    if self.service_initiated_disable:
                        logger.debug("Modem disabled by service (gentle reset) - not triggering SIM failover",
                                   extra={'interface_number': self.interface_number})
                    else:
                        logger.debug("Modem disabled during reset grace period - not triggering SIM failover",
                                   extra={'interface_number': self.interface_number})
            elif current_fsm_state == ModemState.WAITING_FOR_SIM.value:
                # Check if SIM was inserted while waiting
                self._safe_create_task(self._check_sim_insertion())

        elif mm_state == 6:  # ENABLED - Could indicate SIM insertion
            if current_fsm_state in [ModemState.WAITING_FOR_SIM.value,
                                     ModemState.FAILED.value]:
                # SIM might have been inserted (or re-inserted after eject/insert cycle).
                # NOTE: Do NOT cancel the failed-retry here. A bare
                # `searching -> enabled` MM transition happens on every
                # carrier-search loop iteration when registration is
                # impossible (e.g. SIM requires a band the modem does not
                # support). The insertion gate in `_check_sim_insertion`
                # compares the current SIM identifier to the last-known
                # one and only cancels the retry / resumes configuration
                # when the SIM identity actually changed.
                logger.info("Modem enabled while in %s - checking for SIM insertion",
                           current_fsm_state,
                           extra={'interface_number': self.interface_number})
                self._safe_create_task(self._handle_potential_sim_insertion())
            elif current_fsm_state == ModemState.CONFIGURING.value:
                # Modem enabled successfully during configuration - can proceed
                logger.info("Modem enabled, continuing configuration",
                           extra={'interface_number': self.interface_number})
                # Don't transition - let configuration continue
            elif current_fsm_state in [ModemState.CONNECTED.value,
                                       ModemState.USAGE_MONITORING.value]:
                # CONNECTED → ENABLED: registration dropped below SEARCHING — the
                # modem lost the network entirely (deeper drop than SEARCHING).
                # Treat as a registration loss and recover, but only when this
                # is NOT a service-initiated disable / reset window (those are
                # the legitimate ways the service itself takes the modem down
                # to ENABLED during reconfiguration).
                if (not self.service_initiated_disable
                        and not self._is_in_reset_grace_period()):
                    self._handle_connected_registration_drop(mm_state)
                else:
                    logger.debug("Modem dropped to ENABLED while CONNECTED during "
                                "service-initiated disable / reset — not recovering",
                                extra={'interface_number': self.interface_number})

        elif mm_state == 7:  # SEARCHING
            if current_fsm_state == ModemState.CONFIGURING.value:
                if self.initial_configuration_in_progress:
                    logger.debug("Modem searching during initial config - skipping state transition (managed by config flow)",
                               extra={'interface_number': self.interface_number,
                                      'reason': 'initial_configuration_in_progress'})
                else:
                    # Modem searching for network - configuration working
                    logger.info("Modem searching for network",
                               extra={'interface_number': self.interface_number})
                    # Transition to CONNECTING state
                    self.transition(ModemEvent.CONNECT)

            elif current_fsm_state in [ModemState.CONNECTED.value,
                                       ModemState.USAGE_MONITORING.value]:
                # CONNECTED → SEARCHING: the modem lost its serving cell and is
                # re-scanning (e.g. the active supported-bands set was changed
                # to a band the current cell does not use, coverage was lost, or
                # the carrier dropped registration without passing through
                # REGISTERED/DISCONNECTING).  Unlike CONNECTED → REGISTERED
                # there is no camped cell, so the bearer is effectively dead.
                # Without this branch the FSM would stay CONNECTED with no
                # signal and never recover.
                self._handle_connected_registration_drop(mm_state)

        elif mm_state == 8:  # REGISTERED
            if current_fsm_state in [ModemState.CONNECTING.value, ModemState.CONFIGURING.value]:
                if self.initial_configuration_in_progress:
                    logger.info("Modem registered during initial config - skipping connection (managed by config flow)",
                               extra={'interface_number': self.interface_number,
                                      'reason': 'initial_configuration_in_progress'})
                else:
                    # Successfully registered to network - ready for connection
                    logger.info("Modem registered to network, ready for connection",
                               extra={'interface_number': self.interface_number})
                    # Trigger connection configuration
                    self._safe_create_task(self.apply_modem_configuration())

            elif current_fsm_state == ModemState.WAITING_FOR_SIM.value:
                # Some platforms don't expose a SIM-eject hardware signal.
                # After out-of-band power-cycle + SIM replacement we may jump
                # directly to REGISTERED; treat that as SIM-ready and restart
                # full initial configuration flow.
                logger.info("Modem registered while waiting for SIM - resuming initial configuration",
                           extra={'interface_number': self.interface_number,
                                  'fsm_state': current_fsm_state})
                self.transition(ModemEvent.SIM_READY)
                self._safe_create_task(self._configure_modem_initial())

            elif current_fsm_state in [ModemState.DISCONNECTED.value,
                                       ModemState.REGISTERED_IDLE.value,
                                       ModemState.FAILED.value]:
                # Out-of-band modem power cycles / SIM mux changes can land us in
                # REGISTERED while FSM is stale (DISCONNECTED/IDLE/FAILED).
                # Re-enter APN flow unless policy says to stay idle.
                if (self.connection_mode == 'connect-on-demand'
                        and not self.bearer_requested):
                    # No standing connect request — park idle (SMS available).
                    if current_fsm_state == ModemState.DISCONNECTED.value:
                        logger.info("Modem registered in connect-on-demand mode - entering REGISTERED_IDLE",
                                   extra={'interface_number': self.interface_number,
                                          'fsm_state': current_fsm_state,
                                          'connection_mode': self.connection_mode})
                        self.transition(ModemEvent.RECONFIGURE)
                        self.transition(ModemEvent.ENTER_IDLE)
                elif self.user_disconnected:
                    logger.info("Modem registered but user requested disconnect - not auto-connecting",
                               extra={'interface_number': self.interface_number,
                                      'fsm_state': current_fsm_state,
                                      'connection_mode': self.connection_mode})
                else:
                    logger.info("Modem registered with stale FSM state - restarting APN connection cascade",
                               extra={'interface_number': self.interface_number,
                                      'fsm_state': current_fsm_state,
                                      'connection_mode': self.connection_mode})
                    if current_fsm_state == ModemState.FAILED.value:
                        self.transition(ModemEvent.RECONFIGURE)
                    self.transition(ModemEvent.CONNECT)
                    self._safe_create_task(self.apply_modem_configuration())

            elif current_fsm_state in [ModemState.CONNECTED.value, ModemState.USAGE_MONITORING.value]:
                # Modem dropped from CONNECTED to REGISTERED without going through
                # DISCONNECTING (state 9).  This can happen with "Regular deactivation"
                # where the carrier drops the bearer but the modem stays registered.
                if not self.user_disconnected:
                    self._disconnect_reason_override = 'registration_loss'
                    logger.warning("Modem dropped to REGISTERED while FSM CONNECTED — bearer lost, triggering reconnection",
                                  extra={'interface_number': self.interface_number,
                                         'modem_state': mm_state,
                                         'fsm_state': current_fsm_state})
                    try:
                        self._safe_create_task(self._stop_network_interface_monitoring())
                    except RuntimeError:
                        pass
                    self.transition(ModemEvent.DISCONNECT)
                    self._safe_create_task(self.handle_disconnection_recovery())

            elif current_fsm_state == ModemState.DISCONNECTING.value:
                # Safety net: FSM already transitioned to DISCONNECTING (from
                # the bearer D-Bus signal) but handle_disconnection_recovery
                # may have returned early because MM was still at state 11.
                # Now MM has caught up and says REGISTERED — kick recovery.
                if not self.user_disconnected:
                    logger.warning(
                        "Modem REGISTERED while FSM DISCONNECTING — "
                        "recovery may have stalled, re-triggering",
                        extra={'interface_number': self.interface_number,
                               'modem_state': mm_state,
                               'fsm_state': current_fsm_state})
                    self._safe_create_task(self.handle_disconnection_recovery())

        elif mm_state == 9:  # DISCONNECTING
            if current_fsm_state in [ModemState.CONNECTED.value, ModemState.USAGE_MONITORING.value]:
                # Connection being terminated - stop network interface monitoring and trigger enhanced reconnection
                self._disconnect_reason_override = 'modemmanager_disconnecting'
                logger.warning("ModemManager disconnecting - starting enhanced reconnection",
                              extra={'interface_number': self.interface_number})
                try:
                    self._safe_create_task(self._stop_network_interface_monitoring())
                except RuntimeError:
                    # No event loop running (e.g., during tests) - ignore
                    pass
                self.transition(ModemEvent.DISCONNECT)
                # Start enhanced reconnection immediately
                self._safe_create_task(self.handle_disconnection_recovery())

        elif mm_state == 10:  # CONNECTING
            if current_fsm_state == ModemState.CONNECTING.value:
                # Modem is attempting connection - wait for result
                logger.info("Modem attempting connection",
                           extra={'interface_number': self.interface_number})
                # Don't transition - wait for CONNECTED or failure

        elif mm_state == 11:  # CONNECTED
            if current_fsm_state == ModemState.CONNECTING.value:
                if self.initial_configuration_in_progress:
                    logger.info("Modem connected during initial config - skipping transition (managed by config flow)",
                               extra={'interface_number': self.interface_number,
                                      'reason': 'initial_configuration_in_progress'})
                else:
                    # Transition to CONNECTED and stay there to listen for disconnects
                    logger.info("Modem connected successfully, staying in CONNECTED state",
                               extra={'interface_number': self.interface_number})
                    self.transition(ModemEvent.CONNECTED)

                    # Finalise the connection — including a data-path validation
                    # gate — off the event-loop.  This is the fresh-rebuild
                    # retry path (failed-retry loop → apply_modem_configuration →
                    # APN cascade), which reaches CONNECTED via this MM signal
                    # rather than the inline _configure_modem_initial success
                    # block.  Mirror that block's gate so a registered-but-
                    # unroutable SIM does not stay declared CONNECTED here either.
                    self._safe_create_task(self._finalize_connected_from_signal())

            elif current_fsm_state == ModemState.CONNECTED.value:
                # Already connected - connection is stable
                logger.info("Already in CONNECTED state - connection stable",
                           extra={'interface_number': self.interface_number})


        elif mm_state in [-1, 0]:  # FAILED or UNKNOWN
            # Don't trigger anything if this is service-initiated or we're in
            # a reset/SIM-switch grace period — those flows already drive
            # state transitions explicitly.
            if (self.service_initiated_disable
                    or self._is_in_reset_grace_period()
                    or self._sim_switch_in_progress
                    or self._sim_failover_in_progress):
                logger.debug(
                    "Modem FAILED/UNKNOWN state ignored "
                    "(service-initiated or grace period active)",
                    extra={'interface_number': self.interface_number,
                           'mm_state': mm_state})
                return

            # Inspect StateFailedReason — if the modem failed because the
            # SIM disappeared (e.g. user pulled SIM1 while running), the
            # generic CONNECTION_FAILED path will not trigger SIM failover.
            # Route through the dedicated sim-missing failover handler so
            # slot-2 can take over automatically.
            logger.error("Modem entered failed/unknown state",
                        extra={'interface_number': self.interface_number,
                               'mm_state': mm_state,
                               'fsm_state': current_fsm_state})
            self._safe_create_task(self._handle_failed_state_event(mm_state))

        else:
            # States 1 (INITIALIZING), 4 (DISABLING), 5 (ENABLING) - informational only
            logger.debug(f"Modem state {mm_state} - no FSM action needed",
                        extra={'interface_number': self.interface_number,
                               'mm_state': mm_state})

    def transition(self, event: ModemEvent):
        """Enhanced transition with user disconnect tracking"""
        current_state = getattr(self.machine, 'current_state', '')

        # Ignore duplicate no-op events generated by overlapping modem/config flows.
        if event == ModemEvent.CONNECT and current_state == ModemState.CONNECTING.value:
            logger.info("Duplicate connect event ignored - already connecting",
                       extra={'interface_number': self.interface_number,
                              'event': event.value,
                              'current_state': current_state})
            self.connect_requested = False
            return

        if event == ModemEvent.CONNECTED and current_state == ModemState.CONNECTED.value:
            logger.info("Duplicate connected event ignored - already connected",
                       extra={'interface_number': self.interface_number,
                              'event': event.value,
                              'current_state': current_state})
            return

        # Track user-initiated disconnects and stop network interface monitoring
        if event == ModemEvent.DISCONNECT:
            # Check if this is from user or ModemManager
            if current_state in [ModemState.CONNECTED.value, ModemState.USAGE_MONITORING.value]:
                # Stop network interface monitoring when leaving connected state
                try:
                    self._safe_create_task(self._stop_network_interface_monitoring())
                except RuntimeError:
                    # No event loop running (e.g., during tests) - ignore
                    pass
                # NOTE: Do NOT set user_disconnected here — network-initiated
                # drops (bearer lost, carrier detach-reattach, etc.) also fire
                # DISCONNECT events.  Only the explicit user/admin disconnect
                # path should set this flag.  See _handle_admin_disconnect().
                disconnect_reason = self._disconnect_reason_override or (
                    'user_disconnect' if self.user_disconnected else 'bearer_disconnect'
                )
                self._record_bearer_down(
                    disconnect_reason,
                    registration_lost=(disconnect_reason == 'registration_loss'),
                )
                self._disconnect_reason_override = None
                logger.info("DISCONNECT event processed",
                           extra={'interface_number': self.interface_number,
                                  'current_state': current_state,
                                  'user_disconnected': self.user_disconnected})

        elif event == ModemEvent.ENTER_IDLE:
            # On-demand disconnect path: drop bearer but keep registration.
            # Treat this as intentional/normal (not a failure path) and stop
            # connected-state monitoring without forcing Linux link down.
            if current_state in [ModemState.CONNECTED.value, ModemState.USAGE_MONITORING.value]:
                try:
                    self._safe_create_task(self._stop_network_interface_monitoring())
                except RuntimeError:
                    # No event loop running (e.g., during tests) - ignore
                    pass
                # Actually tear down the data bearer at the ModemManager
                # level.  Without this the FSM would report REGISTERED_IDLE
                # (get_bearer_status -> "disconnected") while the real bearer
                # stayed up — mmcli still shows connected and traffic still
                # flows.  Scheduling the async teardown keeps FSM state and
                # the live modem in sync.
                try:
                    self._safe_create_task(self._disconnect_bearer())
                except RuntimeError:
                    # No event loop running (e.g., during tests) - ignore
                    pass
                self._record_bearer_down('enter_idle')
                logger.info("ENTER_IDLE event processed",
                           extra={'interface_number': self.interface_number,
                                  'current_state': current_state,
                                  'user_disconnected': self.user_disconnected,
                                  'connection_mode': self.connection_mode})

        elif event == ModemEvent.CONNECT:
            # Clear user disconnect flag when user requests connection
            if self.user_disconnected:
                logger.info("User-initiated connect, clearing disconnect flag",
                           extra={'interface_number': self.interface_number})
                self.user_disconnected = False
            # Clear queued connect flag — we're executing it now
            self.connect_requested = False

        # Call original transition logic
        try:
            old_state = self.machine.current_state
            self.machine.process_event(event.value)
            new_state = self.machine.current_state

            logger.info("State transition",
                       extra={'interface_number': self.interface_number,
                              'event': event.value,
                              'current_state': new_state,
                              'previous_state': old_state})

            # On-demand reconnect driver.  REGISTERED_IDLE → CONNECTING only
            # happens via an explicit user connect (connect()/connect_bearer()).
            # The modem is already REGISTERED at the MM level, so no new MM
            # state-change signal will fire to drive the connection — we must
            # kick apply_modem_configuration() ourselves.  This is the fast
            # path: the last-connected APN is reused (PRIORITY 1.5 in
            # apply_modem_configuration), so reconnection skips discovery.
            if (event == ModemEvent.CONNECT
                    and old_state == ModemState.REGISTERED_IDLE.value
                    and new_state == ModemState.CONNECTING.value):
                self._safe_create_task(self.apply_modem_configuration())

            # Policy: clear LED (OFF) in no-connection states so stale bars
            # from previous bearer sessions are not shown.
            if new_state in [
                ModemState.WAITING_FOR_SIM.value,
                ModemState.DISCONNECTED.value,
                ModemState.FAILED.value,
            ]:
                self._safe_create_task(
                    self._clear_signal_led(reason=f"fsm_state:{new_state}")
                )

            # Log detailed failure info when entering FAILED state
            if new_state == ModemState.FAILED.value and old_state != ModemState.FAILED.value:
                logger.error("Modem entered FAILED state",
                            extra={'interface_number': self.interface_number,
                                   'failure_reason': self.last_failure_reason or 'unspecified',
                                   'failed_apn': self.last_failed_apn or 'none',
                                   'configured_apn_rejected': self.configured_apn_rejected,
                                   'trigger_event': event.value,
                                   'from_state': old_state})
                self._emit_alert(
                    alert_type='fsm_failed',
                    severity='error',
                    message='FSM entered FAILED state',
                    from_state=old_state,
                    trigger_event=event.value,
                    failure_reason=self.last_failure_reason or 'unspecified',
                    failed_apn=self.last_failed_apn or '',
                    configured_apn_rejected=bool(self.configured_apn_rejected),
                )
                # Take the data session down on entry to FAILED.  A failed
                # connection attempt can leave a stale/degraded bearer up
                # (e.g. a band-mismatched SIM that registers and gets a
                # half-working IPv4-only bearer MM still reports as Connected).
                # Nothing else tears it down until the failed-retry timer's
                # first cycle ("clearing stale bearer before reconnect"), which
                # may be up to the first retry interval (e.g. 600s) away — so
                # the phantom session lingers.  _disconnect_bearer() is
                # idempotent (unconditional Simple.Disconnect('/') sweep) and a
                # safe no-op when the modem is already idle, so it is always
                # correct here regardless of how FAILED was reached.
                self._safe_create_task(self._disconnect_bearer())
                # Start periodic retry from FAILED state — but not if the
                # retry loop itself caused the re-entry (it manages its own
                # continuation).
                current_task = asyncio.current_task()
                if current_task is not self._failed_retry_task:
                    self._start_failed_retry()

            # Cancel retry task when leaving FAILED state
            # (but not when the retry loop itself triggers the transition)
            if old_state == ModemState.FAILED.value and new_state != ModemState.FAILED.value:
                current_task = asyncio.current_task()
                if current_task is not self._failed_retry_task:
                    self._cancel_failed_retry()

            # Apply any configuration that was deferred because it arrived while
            # the FSM was mid-transition (CONNECTING / DISCONNECTING / SIM_*).
            # apply_config() only stored it; now that we have settled into a
            # stable state, run the reconfigure so an active-slot band/APN/etc.
            # change performs its full disable→set→enable restart instead of
            # being silently dropped.
            _settle_states = (
                ModemState.CONNECTED.value,
                ModemState.USAGE_MONITORING.value,
                ModemState.REGISTERED_IDLE.value,
                ModemState.DISCONNECTED.value,
                ModemState.FAILED.value,
            )
            if self._pending_reconfigure and new_state in _settle_states:
                self._pending_reconfigure = False
                logger.info("Applying configuration deferred during transition",
                           extra={'interface_number': self.interface_number,
                                  'settled_state': new_state})
                self._safe_create_task(self._apply_deferred_reconfigure())
        except Exception as e:
            logger.error(f"FSM transition error on event '{event.value}': {e}",
                        extra={'interface_number': self.interface_number,
                               'event': event.value,
                               'current_state': self.machine.current_state})

            # Handle invalid transitions from FAILED state by attempting recovery
            if self.machine.current_state == ModemState.FAILED.value:
                if event == ModemEvent.CONNECTION_FAILED:
                    # Already in FAILED state, no need to transition again
                    logger.info("Already in FAILED state, ignoring CONNECTION_FAILED event",
                               extra={'interface_number': self.interface_number})
                else:
                    # For other events from FAILED state, try to recover via RECONFIGURE
                    try:
                        logger.info("Attempting recovery from FAILED state via RECONFIGURE",
                                   extra={'interface_number': self.interface_number,
                                          'failed_event': event.value})
                        self.machine.process_event(ModemEvent.RECONFIGURE.value)
                    except Exception as recovery_error:
                        logger.error(f"Failed to recover from FAILED state: {recovery_error}",
                                    extra={'interface_number': self.interface_number})

    async def _apply_deferred_reconfigure(self):
        """Run a reconfigure that was deferred while the FSM was mid-transition.

        Mirrors the stable-state reconfigure branch of ``apply_config()``: the
        new configuration is already stored in ``self.config`` (with the prior
        config preserved in ``self._previous_config`` for the diff), so here we
        only need to clear stale failure tracking, fire ``RECONFIGURE`` to move
        the FSM into ``CONFIGURING``, and run ``_reconfigure_modem()`` — which
        compares old vs new and performs a full disable→set-bands→enable restart
        when an active-slot band/APN/pdp/roaming/SIM/network-mode parameter
        changed.

        Runs as its own task (scheduled from ``transition()``), so the
        ``RECONFIGURE`` transition below is not reentrant with the transition
        that triggered it.
        """
        # Only meaningful from a stable state that supports RECONFIGURE.  If the
        # FSM has already moved on (e.g. another transition fired first), skip —
        # the flag will have been re-set by any newer queued config.
        if self.machine.current_state not in (
                ModemState.CONNECTED.value,
                ModemState.USAGE_MONITORING.value,
                ModemState.REGISTERED_IDLE.value,
                ModemState.DISCONNECTED.value,
                ModemState.FAILED.value,
                ModemState.CONFIGURING.value):
            logger.info("Deferred reconfigure skipped — FSM no longer in a "
                       "stable state",
                       extra={'interface_number': self.interface_number,
                              'current_state': self.machine.current_state})
            return

        logger.info("Running deferred reconfigure after transition settled",
                   extra={'interface_number': self.interface_number,
                          'current_state': self.machine.current_state})

        # Cancel failed-state retry — new config supersedes it
        self._cancel_failed_retry()
        # Clear failure tracking — new configuration means a fresh attempt
        self.last_failure_reason = ''
        self.last_failure_time = 0
        self.last_failed_apn = ''
        self.configured_apn_rejected = False
        if self.failback_suppressed_by_connection_failure:
            logger.info("New configuration received — lifting failback "
                       "suppression for primary SIM",
                       extra={'interface_number': self.interface_number})
            self.failback_suppressed_by_connection_failure = False

        self.transition(ModemEvent.RECONFIGURE)
        await self._reconfigure_modem()

    def apply_config(self, config: dict):
        """Apply configuration - handles all states properly"""
        # ── Admin disable / enable transitions ──────────────────────────────
        was_disabled = getattr(self, '_admin_disabled', False)
        is_disabled = config.get('interface_disabled', False)

        if is_disabled:
            # Store config and flag; skip normal state processing
            if hasattr(self, 'config') and self.config:
                self._previous_config = self.config.copy()
            self.config = config
            self._admin_disabled = True
            if not was_disabled:
                logger.info("Interface administratively disabled",
                           extra={'interface_number': self.interface_number})
                self.user_disconnected = True
                self._safe_create_task(self._admin_disable())
            else:
                logger.info("Interface remains disabled, configuration stored",
                           extra={'interface_number': self.interface_number})
            return

        if was_disabled and not is_disabled:
            self._admin_disabled = False
            self.user_disconnected = False
            logger.info("Interface re-enabled from admin-disabled state",
                       extra={'interface_number': self.interface_number})
            # Exit airplane mode (PowerState LOW → ON) before falling
            # through to the normal apply path.  Scheduled as a task so
            # the apply_config sync entry-point isn't blocked; the normal
            # path's _ensure_modem_enabled also handles LOW→ON
            # defensively if this hasn't completed in time.
            if self._airplane_mode_requested or self._airplane_mode_active:
                self._safe_create_task(self._exit_airplane_mode_if_needed())
            # Fall through to normal apply logic — will trigger
            # RECONFIGURE or initial config depending on current state.

        # ── Normal configuration path ───────────────────────────────────────
        # Store previous config for selective disconnection logic
        if hasattr(self, 'config') and self.config:
            self._previous_config = self.config.copy()

        self.config = config

        # 🔄 Extract configuration loading using safe extraction framework
        self._load_configuration_safe(config)

        primary_sim_slot = config.get('primary_sim_slot', 1)
        # Track the configured primary SIM for failback decisions
        if self.primary_sim_slot is None:
            self.primary_sim_slot = primary_sim_slot
        logger.info("Configuration applied",
                   extra={'interface_number': self.interface_number,
                          'config_keys': list(config.keys()) if config else [],
                          'active_sim': primary_sim_slot,
                          'connectivity_monitoring': config.get('connectivity_monitoring', {}).get('enabled', True),
                          'enhanced_reconnection': self.enhanced_reconnection,
                          'signal_threshold_rssi': getattr(self, 'reconnection_signal_threshold_rssi', -85),
                          'signal_threshold_rsrp': getattr(self, 'reconnection_signal_threshold_rsrp', -105),
                          'current_state': self.machine.current_state})


        current = self.machine.current_state

        # Handle configuration based on current state
        if current == ModemState.WAITING_FOR_CONFIG.value:
            # Ready to configure immediately
            self.transition(ModemEvent.CONFIG_UPDATE)
            self._initial_config_task = self._safe_create_task(self._configure_modem_initial())

        elif current == ModemState.SCANNING.value:
            # Store config, will apply when modem found
            # Also honour any queued connect request
            self.connect_requested = True
            logger.info("Config stored, will apply when modem is found (connect queued)",
                       extra={'interface_number': self.interface_number})

        elif current in (
            ModemState.CONFIGURING.value,
            ModemState.CONNECTED.value,
            ModemState.DISCONNECTED.value,
            ModemState.FAILED.value,
            ModemState.REGISTERED_IDLE.value
        ):
            # Cancel failed-state retry — new config supersedes it
            self._cancel_failed_retry()
            # Clear failure tracking — new configuration means a fresh attempt
            self.last_failure_reason = ''
            self.last_failure_time = 0
            self.last_failed_apn = ''
            self.configured_apn_rejected = False
            # Lift failback suppression — the user may have fixed the primary
            # SIM's APN/parameters so failback should be allowed again.
            if self.failback_suppressed_by_connection_failure:
                logger.info("New configuration received — lifting failback "
                           "suppression for primary SIM",
                           extra={'interface_number': self.interface_number})
                self.failback_suppressed_by_connection_failure = False
            if current == ModemState.FAILED.value:
                logger.info("New configuration received while in FAILED state — "
                           "retrying connection",
                           extra={'interface_number': self.interface_number})
            # Normal reconfiguration — applied now, so clear any deferred-
            # reconfigure debt from an earlier mid-transition config.
            self._pending_reconfigure = False
            self.transition(ModemEvent.RECONFIGURE)
            self._safe_create_task(self._reconfigure_modem())

        elif current in (
            ModemState.SIM_SWITCHING.value,
            ModemState.SIM_DISCONNECTING.value,
            ModemState.SIM_DISABLING.value,
            ModemState.SIM_ENABLING.value,
            ModemState.SIM_RECONFIGURING.value
        ):
            # Config change during SIM switch - queue for after switch completes
            logger.info("Configuration queued - SIM switch in progress",
                       extra={'interface_number': self.interface_number,
                              'current_state': current})
            # Config is stored; a deferred reconfigure is owed once the SIM
            # switch settles so any active-slot band/APN change is actually
            # written to the modem (full disable→set→enable restart).
            self._pending_reconfigure = True

        elif current in (
            ModemState.CONNECTING.value,
            ModemState.DISCONNECTING.value
        ):
            # Config change during connection transition - queue for completion
            logger.info("Configuration queued - connection transition in progress",
                       extra={'interface_number': self.interface_number,
                              'current_state': current})
            # Config is stored; a deferred reconfigure is owed once the
            # transition settles.  Without this an active-slot band/APN change
            # committed mid-transition is silently dropped — the modem is never
            # disabled and the new bands are never written.
            self._pending_reconfigure = True

        else:
            # Unknown/unhandled state
            logger.warning("Configuration applied in unhandled state",
                          extra={'interface_number': self.interface_number,
                                 'current_state': current})

    def _load_configuration_safe(self, config: dict):
        """Load and parse configuration using new ConfigurationLoader"""
        # Load configuration using new loader
        self.parsed_config = self.config_loader.load_configuration(config)

        # Validate configuration
        if not self.config_loader.validate_configuration(self.parsed_config):
            logger.error("Configuration validation failed",
                        extra={'interface_number': self.interface_number})
            return

        # Apply parsed configuration to instance variables
        self._apply_parsed_configuration()

        # Handle connectivity monitoring normalization
        if 'connectivity_monitoring' in config:
            config['connectivity_monitoring'] = self._normalize_connectivity_config(
                config['connectivity_monitoring']
            )

        # Log configuration applied
        primary_sim_slot = config.get('primary_sim_slot', 1)
        logger.info("Configuration applied",
                   extra={'interface_number': self.interface_number,
                          'config_keys': list(config.keys()) if config else [],
                          'active_sim': primary_sim_slot,
                          'connectivity_monitoring': config.get('connectivity_monitoring', {}).get('enabled', True),
                          'enhanced_reconnection': self.parsed_config.enhanced_reconnection.enabled,
                          'signal_threshold_rssi': self.parsed_config.enhanced_reconnection.signal_threshold_rssi,
                          'signal_threshold_rsrp': self.parsed_config.enhanced_reconnection.signal_threshold_rsrp,
                          'current_state': self.machine.current_state})

    def _apply_parsed_configuration(self):
        """Apply parsed configuration to instance variables consumed by the rest of the FSM."""
        # Logging sink + level are applied process-wide so all WWAN modules
        # follow the same output destination policy.
        raw_log_level = str(self.parsed_config.raw_config.get('log_level', 'info')).upper()
        log_level = getattr(logging, raw_log_level, logging.INFO)
        self.log_level = raw_log_level.lower()
        self.log_sink = self.parsed_config.raw_config.get('log_sink', 'both')
        applied_sink = reconfigure_logging(sink=self.log_sink, level=log_level)

        logger.info("Applied logging output configuration",
                   extra={'interface_number': self.interface_number,
                          'log_level': self.log_level,
                          'log_sink': applied_sink})

        # Enhanced reconnection configuration
        self.enhanced_reconnection = self.parsed_config.enhanced_reconnection.enabled
        self.reconnection_signal_threshold_rssi = self.parsed_config.enhanced_reconnection.signal_threshold_rssi
        self.reconnection_signal_threshold_rsrp = self.parsed_config.enhanced_reconnection.signal_threshold_rsrp
        self.enhanced_reconnection_max_retries = self.parsed_config.enhanced_reconnection.max_retries
        self.retry_interval_good_signal = self.parsed_config.enhanced_reconnection.retry_interval_good_signal
        self.retry_interval_poor_signal = self.parsed_config.enhanced_reconnection.retry_interval_poor_signal
        self.max_wait_for_signal = self.parsed_config.enhanced_reconnection.max_wait_for_signal
        self.signal_check_interval = self.parsed_config.enhanced_reconnection.signal_check_interval
        self.normal_monitoring_interval = self.parsed_config.enhanced_reconnection.normal_monitoring_interval
        self.signal_strength_buffer = self.parsed_config.enhanced_reconnection.signal_strength_buffer

        # Interface management configuration
        self.interface_management = self.parsed_config.raw_config.get('interface_management', {})
        self.interface_management_enabled = self.parsed_config.interface_management.enabled
        self.bearer_disconnect_delay = self.parsed_config.interface_management.bearer_disconnect_delay
        self.registration_recovery_delay = self.parsed_config.interface_management.registration_recovery_delay
        self.registration_flap_count = self.parsed_config.interface_management.registration_flap_count
        self.registration_flap_window = self.parsed_config.interface_management.registration_flap_window
        self.ip_change_delay = self.parsed_config.interface_management.ip_change_delay
        self.ensure_link_up_on_connect = self.parsed_config.interface_management.ensure_link_up_on_connect
        self.monitor_bearer_state = self.parsed_config.interface_management.monitor_bearer_state
        self.monitor_ip_changes = self.parsed_config.interface_management.monitor_ip_changes
        self.interface_up_timeout = self.parsed_config.interface_management.interface_up_timeout

        # Initialize network interface management state
        self._bearer_disconnect_timer = None
        self._registration_debounce_timer = None
        self._last_known_ip = None
        self._ip_monitoring_task = None

        # Source address enforcement state — prevents stale-source packets
        # from leaking to carriers that enforce source validation (e.g. Verizon)
        self._current_bearer_ipv4 = None      # Last applied IPv4 address (bare, no prefix)
        self._current_bearer_ipv6 = None      # Last applied IPv6 address (bare, no prefix)
        self._current_bearer_ipv6_prefix = None  # e.g. '64' — length of the carrier prefix
        self._ipv6_egress_filter_active = False  # True when ip6tables whitelist chain is installed
        self._ipv4_egress_filter_active = False  # True when iptables whitelist chain is installed
        self._fsm_mss_clamp_v4_active = False    # FSM-owned mangle/FORWARD TCPMSS rule (v4)
        self._fsm_mss_clamp_v6_active = False    # FSM-owned mangle/FORWARD TCPMSS rule (v6)

        # DHCPv6 PD configured upstream — gates DHCPv6 client (UDP/546) in
        # the IPv6 egress hygiene chain.  When False, the chain drops
        # outbound DHCPv6 to keep idle bearers free of forbidden chatter.
        self._dhcpv6_pd_enabled = bool(
            self.parsed_config.raw_config.get('dhcpv6_pd_enabled', False)
        )

        # IP Passthrough manager: instantiated once in __init__ so its
        # _last_v4 / _last_v6 / _last_v6_prefix survive config reloads
        # (see comment at construction site).  Do NOT re-create it here.
        if not hasattr(self, '_passthrough') or self._passthrough is None:
            self._passthrough = PassthroughManager(self.interface_number)

        # Connection mode: always-on | connect-on-demand | dial-on-demand
        self.connection_mode = self.parsed_config.raw_config.get('connection_mode', 'always-on')

        # Connection and registration timers
        self.connection_timeout = float(self.parsed_config.raw_config.get('connection_timeout', 120))
        self.registration_timeout = float(self.parsed_config.raw_config.get('registration_timeout', 180))

        # Hardware reset controls
        self.hardware_reset_enabled = bool(self.parsed_config.raw_config.get('hardware_reset_enabled', True))
        self.max_hardware_resets = int(self.parsed_config.raw_config.get('max_hardware_resets', 3))
        self.reset_cooldown_seconds = int(self.parsed_config.raw_config.get('hardware_reset_cooldown', 300))

        logger.info("Applied timeout/reset runtime configuration",
               extra={'interface_number': self.interface_number,
                  'connection_timeout': self.connection_timeout,
                  'registration_timeout': self.registration_timeout,
                  'hardware_reset_enabled': self.hardware_reset_enabled,
                  'max_hardware_resets': self.max_hardware_resets,
                  'hardware_reset_cooldown': self.reset_cooldown_seconds})

        # Failed-state periodic retry configuration
        self._failed_retry_enabled = self.parsed_config.failed_retry.enabled
        self._failed_retry_intervals = list(self.parsed_config.failed_retry.intervals)
        self._failed_retry_max_interval = self.parsed_config.failed_retry.max_interval
        self._failed_retry_escalation_threshold = self.parsed_config.failed_retry.escalation_threshold

        # Bearer D-Bus signal monitoring state
        self._bearer_proxy = None
        self._bearer_interface = None

        # IPv6 bridging configuration
        self._bridging_config = self.parsed_config.raw_config.get(
            'ipv6_bridging', {'enabled': False, 'interface': ''}
        )
        self._bridging_reconciliation_interval = int(
            self._bridging_config.get('reconciliation_interval', 10)
        )
        if self._bridging_config.get('enabled') and self._bridging_config.get('interface'):
            logger.info("IPv6 bridging enabled → %s, reconciliation interval %ds",
                       self._bridging_config['interface'],
                       self._bridging_reconciliation_interval,
                       extra={'interface_number': self.interface_number})

        # IPv6 management-address (FSM-stamped <prefix>::host-id on wwanN)
        self._mgmt_addr_config = self.parsed_config.raw_config.get(
            'ipv6_management_address',
            {'enabled': True, 'host_id': '::1',
             'permit_tcp': [], 'permit_udp': [], 'permit_source': []},
        )
        if self._mgmt_addr_config.get('enabled'):
            logger.info(
                "IPv6 management-address enabled (host-id %s, permit-tcp %s, "
                "permit-udp %s, permit-source %s)",
                self._mgmt_addr_config.get('host_id', '::1'),
                self._mgmt_addr_config.get('permit_tcp') or [],
                self._mgmt_addr_config.get('permit_udp') or [],
                self._mgmt_addr_config.get('permit_source') or [],
                extra={'interface_number': self.interface_number},
            )

    async def _configure_modem_initial(self):
        """Initial modem configuration - configure SIM/bands/carrier BEFORE network operations"""
        try:
            # Guard against overlapping config tasks (e.g., rapid SIM cycling)
            if self.initial_configuration_in_progress:
                logger.warning("Initial configuration already in progress - aborting duplicate",
                             extra={'interface_number': self.interface_number})
                return

            # Prevent registration/bearer handlers from racing with this configuration flow
            self.initial_configuration_in_progress = True

            logger.info("Starting initial modem configuration",
                       extra={'interface_number': self.interface_number})

            # Step 0: Check if modem is already in an active state (abnormal for service startup)
            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
            state_variant = await props.call_get(MODEM_INTERFACE, "State")
            state = state_variant.value

            # Step 0a: If the modem is already in FAILED state at attach
            # time, do NOT walk the configure → enable → connect cascade.
            # On a FAILED modem the Modem.Simple D-Bus interface is not
            # exposed, so any later Simple.Connect() call dies with
            # `interface not found … Modem.Simple` and the FSM then
            # enters FAILED for the wrong reason. Route through the
            # existing FAILED-state investigator which reads
            # StateFailedReason and triggers SIM failover for
            # sim-missing / sim-error, or schedules the failed-retry
            # backoff for other reasons.
            if state == -1:  # MM_MODEM_STATE_FAILED
                logger.warning(
                    "Modem already in FAILED state at initial configuration — "
                    "skipping configuration cascade and investigating reason",
                    extra={'interface_number': self.interface_number,
                           'modem_state': state})
                self.initial_configuration_in_progress = False
                await self._handle_failed_state_event(state)
                return

            # Only reset if modem is actually connected (abnormal startup condition)
            # States: 4=DISABLED, 6=ENABLING, 7=ENABLED, 8=SEARCHING, 9=REGISTERED, 11=CONNECTING, 12=CONNECTED
            if state >= 11:  # Only CONNECTING or CONNECTED states need reset
                logger.warning("Modem found in connected state at service startup - performing gentle reset",
                              extra={'interface_number': self.interface_number,
                                     'modem_state': state,
                                     'reason': 'Service should manage connections, not inherit existing ones'})

                # Strategy 1: Gentle disable-enable cycle (preserves USB/QMI interface)
                try:
                    success = await self._try_gentle_reset()
                    if success:
                        logger.info("Gentle reset (disable-enable) successful",
                                   extra={'interface_number': self.interface_number})
                        # Continue with normal configuration - modem should now be in disabled state
                    else:
                        # Strategy 2: Hardware reset as fallback (with cooldown protection)
                        if self._is_reset_allowed():
                            logger.warning("Gentle reset failed, trying hardware reset",
                                          extra={'interface_number': self.interface_number})
                            await modem_reset(self.interface_number)
                            self._record_reset()
                            logger.info("Hardware reset completed, waiting for modem re-enumeration",
                                       extra={'interface_number': self.interface_number})
                            # Give modem proper time to boot up - modems can take 2+ minutes
                            await asyncio.sleep(30)  # Initial wait for hardware initialization

                            # Re-scan for modem after reset with patient timeout
                            self.proxy = None  # Clear old proxy
                            # scan_for_modem() has built-in exponential backoff and will wait patiently
                            await self.scan_for_modem()  # Use existing scan method
                        else:
                            logger.warning("Skipping hardware reset after gentle reset failure due to cooldown",
                                         extra={'interface_number': self.interface_number})

                except Exception as reset_error:
                    logger.error(f"Hardware reset failed: {reset_error}",
                                extra={'interface_number': self.interface_number})
                    # Continue with software disable as fallback
            else:
                # Normal case: modem is in acceptable state (DISABLED, ENABLED, SEARCHING, REGISTERED)
                logger.info("Modem found in acceptable state, proceeding with configuration",
                           extra={'interface_number': self.interface_number,
                                  'modem_state': state,
                                  'reason': 'No reset needed for idle/searching modem'})

            # Step 1: Ensure modem is disabled for configuration
            await self._ensure_modem_disabled_for_config()

            # Step 2: Configure SIM slot while disabled.  The SIM-slot switch
            # (SetPrimarySimSlot) is the ONLY modem-level setting that genuinely
            # requires the DISABLED state — band and network-mode selection are
            # backed by the QMI NAS service, which is INACTIVE while the modem
            # is disabled, so writing them here is silently ignored on QMI
            # modems (e.g. Telit FN920).  They are applied after enable below.
            await self._configure_sim_slot()

            # Step 3: Enable the modem
            await self._ensure_modem_enabled()

            # Step 4: Unlock SIM if needed after enabling
            await self._unlock_sim_if_needed()

            # Step 5: Configure supported bands now that the modem is ENABLED.
            # SetCurrentBands goes through the QMI NAS service, which only
            # exists once the modem is enabled — attempting it while disabled is
            # a no-op (the modem keeps all bands enabled).  Done before the
            # connection cascade so the restriction is in force when the modem
            # registers/attaches.
            await self._configure_supported_bands()

            # Step 5.5: Configure network mode (access technology) — same NAS
            # requirement as bands, so it also runs post-enable.
            await self._configure_network_mode()

            # Step 6: Lock onto the preferred carrier BEFORE the modem settles
            # on an automatic PLMN choice. _ensure_modem_enabled returns as soon
            # as the modem reaches ENABLED/SEARCHING (state >= 6) — i.e. before
            # automatic registration has completed — so issuing manual network
            # selection here makes the modem attach directly to the configured
            # PLMN instead of registering on one operator and then visibly
            # flapping over to another. Customers who set a preferred carrier
            # want a hard lock; dual-SIM provides the recovery path when that
            # carrier is unavailable. SIM unlock must precede this (a PIN-locked
            # SIM cannot register at all), so it stays at Step 4.
            await self._configure_preferred_carrier()

            # Step 7: Validate ICCID lock (SIM must be enabled + unlocked for
            # identity to be readable). Runs after carrier selection so the
            # manual-PLMN lock is applied at the earliest possible moment and
            # does not race the modem's automatic attach.
            await self._validate_sim_iccid()

            logger.info("Initial modem configuration complete",
                       extra={'interface_number': self.interface_number})

            # Check connection mode: park at REGISTERED_IDLE for connect-on-demand
            if self.machine.current_state == ModemState.CONFIGURING.value:
                if (self.connection_mode == 'connect-on-demand'
                        and not self.bearer_requested):
                    logger.info("Connect-on-demand active — parking at REGISTERED_IDLE "
                                "(modem registered, no bearer, SMS available)",
                               extra={'interface_number': self.interface_number})
                    self.transition(ModemEvent.ENTER_IDLE)
                else:
                    # always-on: auto-connect and stay connected (auto-reconnect on failure)
                    # dial-on-demand: auto-connect at boot, bearer toggleable via
                    #   connect_bearer() / disconnect_bearer(); no auto-reconnect
                    #   after manual disconnect_bearer()
                    # connect-on-demand with a standing connect request
                    #   (bearer_requested, e.g. restored after a crash): reconnect
                    #   and then behave like always-on until explicit disconnect.
                    logger.info(f"{self.connection_mode} active — proceeding to connection phase",
                               extra={'interface_number': self.interface_number,
                                      'bearer_requested': self.bearer_requested})
                    self.transition(ModemEvent.CONNECT)
            else:
                logger.info("Skipping automatic connect transition - FSM already advanced",
                           extra={'interface_number': self.interface_number,
                                  'current_state': self.machine.current_state})

            # Debug: Log current configuration
            logger.info(f"Current config keys: {list(self.config.keys()) if self.config else 'No config'}",
                        extra={'interface_number': self.interface_number})
            if self.config:
                logger.info(f"Config structure: {self.config}",
                           extra={'interface_number': self.interface_number})

            # Proper APN connection priority order:
            # 1. Try APNs from colleague's discovery service
            # 2. Try automatic network-provided APN
            # 3. Fallback to configured APN as customer override

            logger.info("Starting APN connection attempts with proper priority order",
                       extra={'interface_number': self.interface_number})

            # Registration gate — never call Simple.Connect() on a modem
            # that has not yet reached REGISTERED. On a search-loop
            # modem (e.g. SIM that requires an unsupported band) the
            # MM Simple.Connect call will internally wait up to ~60s
            # for registration and then fail with a misleading
            # "Network timeout", driving the FSM into FAILED for the
            # wrong reason. The post-FAILED path (apply_modem_configuration)
            # already has this gate; replicate it here for the startup
            # cascade in _configure_modem_initial as well.
            #
            # Use the STABLE-registration check (two consecutive reads) rather
            # than a single State snapshot: Step 5 just (re)applied the band
            # restriction, which bounces registration, and a one-shot read can
            # catch a stale REGISTERED from the band the modem just left.  A
            # SIM that cannot register on the restricted band therefore reaches
            # the timeout → SIM-failover branch below instead of slipping into
            # a misleading APN connect failure with no failover.
            registered = await self._wait_for_stable_registration()
            if not registered:
                logger.warning(
                    "Modem did not reach a stable REGISTERED state — aborting connection cascade",
                    extra={'interface_number': self.interface_number})
                self.last_failure_reason = (
                    "Modem failed to reach REGISTERED state within the "
                    "configured registration timeout. The SIM and/or "
                    "supported bands may not match any available carrier."
                )
                self.last_failure_time = time.time()
                # Bump the failure counter and route through the
                # standard FAILED path so dual-SIM failover can run
                # via the same logic used for connection failures.
                self.initial_connection_failure_count += 1
                self.transition(ModemEvent.CONNECTION_FAILED)
                # Give dual-SIM failover a chance — no-op when no
                # alternate SIM exists.
                await self._handle_sim_missing_failover()
                return

            # Get SIM config for connection parameters.  Anchor on the slot
            # actually active.  Normally _configure_sim_slot (Step 2) has just
            # forced the modem onto the primary and set current_active_sim to
            # it, so this equals primary_sim_slot — but if that switch failed
            # and we are still on a different slot, current_active_sim reflects
            # reality, so the connect params (pdp_type/roaming) match the SIM
            # the modem is genuinely on.
            active_slot = self.current_active_sim or (
                self.config.get('primary_sim_slot', 1) if self.config else 1)
            sim_config = {'pdp_type': 'ipv4v6', 'roaming': 'enabled'}  # defaults

            if self.config and 'sim_slots' in self.config:
                for slot in self.config['sim_slots']:
                    if slot['slot'] == active_slot:
                        sim_config = {
                            'pdp_type': slot.get('pdp_type', 'ipv4v6'),
                            'roaming': slot.get('roaming', 'enabled')
                        }
                        break

            connection_successful = False

            # ── Pre-connection roaming check ──────────────────────────────
            # If the modem has registered on a roaming network but the SIM's
            # roaming policy is 'disabled', every APN attempt will be rejected
            # by ModemManager with "roaming not allowed".  Detect this early
            # and skip straight to failover / FAILED instead of burning
            # through all APN candidates for no reason.
            try:
                gpp_iface = "org.freedesktop.ModemManager1.Modem.Modem3gpp"
                reg_v = await props.call_get(gpp_iface, "RegistrationState")
                current_reg_state = reg_v.value if reg_v else 0
            except Exception:
                current_reg_state = 0  # Unknown — proceed normally

            if current_reg_state == 5 and sim_config.get('roaming', 'enabled') == 'disabled':
                logger.warning(
                    "Modem registered on roaming network but roaming is disabled "
                    "for this SIM — skipping APN connection attempts",
                    extra={'interface_number': self.interface_number,
                           'registration_state': 'ROAMING',
                           'roaming_policy': 'disabled',
                           'active_slot': active_slot})
                self.last_failure_reason = (
                    "SIM is registered on a roaming network but roaming is disabled. "
                    "Enable roaming for this SIM slot or insert a SIM with a home "
                    "network registration."
                )
                self.last_failure_time = time.time()

                # Attempt SIM failover to the alternate SIM.  The shared
                # executor probes SimSlots for an actually-present alternate,
                # applies cooldown/lock gating, and (via pre_switch_event)
                # transitions through CONNECTION_FAILED so SWITCH_SIM has a
                # valid source state.  suppress_failback keeps us off the
                # roaming-locked primary until corrected config arrives.
                switched = await self._failover_to_alternate_sim(
                    'roaming_not_allowed', '_configure_modem_initial',
                    switch_reason='roaming_not_allowed',
                    suppress_failback=True,
                    pre_switch_event=ModemEvent.CONNECTION_FAILED)
                if switched:
                    return

                # No failover available — park in FAILED
                logger.error(
                    "No SIM failover available for roaming mismatch — parking in FAILED",
                    extra={'interface_number': self.interface_number})
                self.transition(ModemEvent.CONNECTION_FAILED)
                return

            # Get current SIM information and check for SIM changes
            sim_info = await self._get_sim_information()
            if not sim_info:
                logger.warning("Could not get SIM information - no SIM card may be present",
                              extra={'interface_number': self.interface_number})

                # Verify by checking the Sim property directly
                try:
                    sim_path_variant = await props.call_get(MODEM_INTERFACE, "Sim")
                    sim_path = sim_path_variant.value if hasattr(sim_path_variant, 'value') else sim_path_variant
                except Exception:
                    sim_path = None

                if not sim_path or sim_path == '/':
                    logger.error("❌ No SIM card detected - cannot connect. Transitioning to WAITING_FOR_SIM",
                                extra={'interface_number': self.interface_number,
                                       'sim_path': sim_path})
                    self.transition(ModemEvent.SIM_MISSING)
                    self._safe_create_task(self._handle_sim_missing_failover())
                    return  # Stop - don't attempt APN connections without a SIM

                sim_changed = False
            else:
                sim_changed = await self._check_sim_change(sim_info)

            # PRIORITY 1: Try configured APN first (highest priority).
            # Even after a SIM identity change, explicit user-configured APN
            # remains a strong intent signal and should be attempted before
            # discovery/automatic fallback paths.
            apn_config = None
            if self.config and 'sim_slots' in self.config:
                active_sim = None
                for slot in self.config['sim_slots']:
                    if slot['slot'] == active_slot:
                        active_sim = slot
                        break

                if active_sim and active_sim.get('apn'):
                    apn_config = self._normalize_apn_config(active_sim.get('apn', ''))

                    if not apn_config.get('name'):
                        logger.info("No APN name configured - skipping configured APN, will use discovery",
                                   extra={'interface_number': self.interface_number})
                        apn_config = None  # Force fall-through to discovery

                if apn_config and apn_config.get('name'):
                    if sim_changed:
                        logger.info("SIM changed, but still trying configured APN first",
                                   extra={'interface_number': self.interface_number,
                                          'configured_apn': apn_config['name'],
                                          'active_slot': active_slot})
                    logger.info("Attempting connection with configured APN (highest priority)",
                               extra={'interface_number': self.interface_number,
                                      'configured_apn': apn_config['name']})

                    success, reason = await self._try_connection_with_apn(apn_config, sim_config)
                    if success:
                        connection_successful = True
                    elif reason == 'connection_failed':
                        logger.warning(
                            "Configured APN attempt failed for non-APN reason; "
                            "a non-APN failure means trying other APNs is pointless — "
                            "failing the connection and offering SIM failover",
                            extra={'interface_number': self.interface_number,
                                   'apn_name': apn_config.get('name', 'unknown'),
                                   'failure_reason': reason})
                        self.last_failure_reason = (
                            "Non-APN modem/network failure occurred during configured APN attempt "
                            "(e.g. the SIM could not register on the configured band/network)."
                        )
                        self.last_failure_time = time.time()
                        self.initial_connection_failure_count += 1
                        self.transition(ModemEvent.CONNECTION_FAILED)
                        # A non-APN connect failure usually means the modem
                        # could not register / carry data on this SIM (e.g. a
                        # band-restricted SIM with no matching coverage).  Offer
                        # dual-SIM failover — no-op when no alternate SIM exists
                        # or cooldown is active.
                        await self._handle_sim_missing_failover()
                        return

            # PRIORITY 1.5: Try in-memory last-connected APN (fastest reconnection)
            # Skipped when SIM changed — stale APN for old SIM
            if not connection_successful and not sim_changed and self.connected_apn:
                last_apn_name = self.connected_apn.get('name', '')
                # Avoid redundant attempt if configured APN is the same one we just tried
                already_tried = (apn_config and apn_config.get('name') == last_apn_name)
                if last_apn_name and not already_tried:
                    logger.info("Trying last-connected APN for fast reconnection",
                               extra={'interface_number': self.interface_number,
                                      'apn_name': last_apn_name})
                    success, reason = await self._try_connection_with_apn(self.connected_apn, sim_config)
                    if success:
                        connection_successful = True
                        logger.info("Last-connected APN reconnection successful",
                                   extra={'interface_number': self.interface_number,
                                          'apn_name': last_apn_name})
                    elif reason == 'connection_failed':
                        logger.warning(
                            "Last-known APN failed for non-APN reason; "
                            "a non-APN failure means trying other APNs is pointless — "
                            "failing the connection and offering SIM failover",
                            extra={'interface_number': self.interface_number,
                                   'apn_name': last_apn_name,
                                   'failure_reason': reason})
                        self.last_failure_reason = (
                            "Non-APN modem/network failure occurred during last-known APN attempt "
                            "(e.g. the SIM could not register on the configured band/network)."
                        )
                        self.last_failure_time = time.time()
                        self.initial_connection_failure_count += 1
                        self.transition(ModemEvent.CONNECTION_FAILED)
                        # See note in the configured-APN branch: a non-APN
                        # connect failure (no registration / no data path)
                        # warrants dual-SIM failover.  No-op when no alternate.
                        await self._handle_sim_missing_failover()
                        return

            # PRIORITY 3: Try APNs from discovery service
            if not connection_successful and (not self.config or self.config.get('android_apn_discovery', 'enabled') == 'enabled'):
                logger.info("Attempting connection using APN discovery service",
                           extra={'interface_number': self.interface_number})
                try:
                    # This will try discovered APNs in order
                    success, discovery_reason = await self._try_apn_candidates_from_discovery(sim_config)
                    if success:
                        connection_successful = True
                    elif discovery_reason == 'restart_required':
                        logger.warning(
                            "Discovery phase reported non-APN MM failure; "
                            "failing the connection and offering SIM failover",
                            extra={'interface_number': self.interface_number,
                                   'failure_reason': discovery_reason})
                        self.last_failure_reason = (
                            "Non-APN modem/network failure occurred during APN discovery "
                            "(e.g. the SIM could not register on the configured band/network)."
                        )
                        self.last_failure_time = time.time()
                        self.initial_connection_failure_count += 1
                        self.transition(ModemEvent.CONNECTION_FAILED)
                        # See note in the configured-APN branch: a non-APN
                        # failure warrants dual-SIM failover.  No-op when no
                        # alternate SIM exists or cooldown is active.
                        await self._handle_sim_missing_failover()
                        return
                except Exception as e:
                    logger.warning(f"APN discovery service failed: {e}",
                                 extra={'interface_number': self.interface_number})

            # PRIORITY 4: Try automatic network-provided APN (lowest priority)
            if not connection_successful:
                logger.info("Attempting automatic APN assignment from network",
                           extra={'interface_number': self.interface_number})
                try:
                    success = await self._try_automatic_apn_assignment(sim_config)
                    if success:
                        connection_successful = True
                except Exception as e:
                    logger.warning(f"Automatic APN assignment failed: {e}",
                                 extra={'interface_number': self.interface_number})

            if connection_successful:
                # Honor an in-flight user disconnect.  In connect-on-demand /
                # dial-on-demand a disconnect may have been issued while this
                # connect was still completing (FSM in CONNECTING, so the
                # disconnect handler could not fire ENTER_IDLE from CONNECTED).
                # The requirement is that once the user disconnects we stay
                # down until an explicit connect arrives — so tear the freshly
                # established bearer back down and park at REGISTERED_IDLE
                # instead of advancing to CONNECTED.  A subsequent connect
                # clears user_disconnected and proceeds normally.
                if self.user_disconnected and self.connection_mode in (
                        'connect-on-demand', 'dial-on-demand'):
                    logger.info(
                        "Connection completed but user requested disconnect — "
                        "tearing bearer back down and parking idle",
                        extra={'interface_number': self.interface_number,
                               'connection_mode': self.connection_mode,
                               'current_state': self.machine.current_state})
                    await self._disconnect_bearer()
                    if self.machine.current_state == ModemState.CONNECTING.value:
                        self.transition(ModemEvent.ENTER_IDLE)
                    return

                logger.info("Connection established successfully, transitioning to CONNECTED state",
                           extra={'interface_number': self.interface_number})

                # Clear any previous failure tracking — connection is now good
                self.last_failure_reason = ''
                self.last_failure_time = 0
                self.last_failed_apn = ''
                self.configured_apn_rejected = False
                self.initial_connection_failure_count = 0

                # APN capture (requested + carrier-negotiated) happens at the
                # connect chokepoint itself — _try_connection_with_apn for the
                # configured/last-known/discovery candidates, _detect_assigned_apn
                # for the automatic-assignment path — so no extra QMI read here.

                # Update SIM info after successful connection for future change detection
                if sim_info:
                    self.last_known_sim_info = sim_info.copy()
                    self.sim_changed = False
                    # Cache per-slot SIM identity so status can report both SIMs
                    slot = self.current_active_sim or active_slot
                    self.sim_slot_info_cache[slot] = {
                        'imsi': sim_info.get('imsi', ''),
                        'iccid': sim_info.get('sim_identifier', ''),
                        'operator': sim_info.get('operator_name', ''),
                        'mcc_mnc': sim_info.get('mcc_mnc', ''),
                        'spn': sim_info.get('spn', ''),
                    }
                    logger.debug("Updated stored SIM info after successful connection",
                                extra={'interface_number': self.interface_number,
                                       'sim_slot': slot,
                                       'operator': sim_info.get('operator_name', 'Unknown'),
                                       'mcc_mnc': sim_info.get('mcc_mnc', 'Unknown')})

                # Transition to CONNECTED and stay there for event-driven monitoring
                if self.machine.current_state == ModemState.CONNECTING.value:
                    self.transition(ModemEvent.CONNECTED)
                elif self.machine.current_state in (ModemState.CONNECTED.value,
                                                    ModemState.USAGE_MONITORING.value):
                    # FSM already advanced to a genuine connected state via an
                    # MM CONNECTED (11) signal that raced ahead of us — fine,
                    # proceed with the connected-side bringup below.
                    logger.info("FSM already in connected state - proceeding",
                               extra={'interface_number': self.interface_number,
                                      'current_state': self.machine.current_state})
                else:
                    # MM reported a bearer up, but the FSM is NOT in a connected
                    # state (typically FAILED: an earlier non-APN failure in this
                    # same cascade already fired CONNECTION_FAILED).  Adopting
                    # this bearer here would leave a half-up, possibly dead
                    # session (e.g. SIM cannot carry data on the registered band:
                    # pdn-ipv6-call-disallowed + uninstallable IPv4 route) that
                    # nothing tears down until the failed-retry timer fires much
                    # later.  Take the session down now and leave the FSM in its
                    # current (FAILED) state so its retry / failover logic owns
                    # recovery.
                    logger.warning(
                        "Bearer came up but FSM is not in a connected state — "
                        "tearing the session down instead of adopting it",
                        extra={'interface_number': self.interface_number,
                               'current_state': self.machine.current_state})
                    try:
                        await self._disconnect_bearer()
                    except Exception as e:
                        logger.debug(f"Bearer teardown after stale connect failed: {e}",
                                    extra={'interface_number': self.interface_number})
                    return
                logger.info("Connected - staying in CONNECTED state for event-driven monitoring",
                           extra={'interface_number': self.interface_number})

                # Apply bearer IP configuration to interface (VyOS responsibility).
                # If the bearer registered but cannot route (dead data path),
                # fail over instead of declaring CONNECTED on a SIM that cannot
                # carry data on the registered band/network.
                if not await self._apply_bearer_ip_or_fail('configure_modem_initial'):
                    return

                # Start network interface management
                try:
                    if self.ensure_link_up_on_connect:
                        self._safe_create_task(self._ensure_interface_up())
                    self._safe_create_task(self._start_network_interface_monitoring())
                    # Set up SMS incoming-message listener
                    self._safe_create_task(self._setup_sms_listener())
                except RuntimeError:
                    # No event loop running (e.g., during tests) - ignore
                    pass

                # Reset failover counters — connection is stable
                self._reset_failover_counters()
                self._record_bearer_up('apply_modem_configuration')
                self._ensure_usage_monitoring_started('apply_modem_configuration')

                # Start connectivity monitoring (ping tests) if configured
                self._safe_create_task(self.start_connectivity_monitoring())

                # Start failback monitor if we're on the failover SIM
                self._start_failback_monitor()
            else:
                # --- Connection failure handling ---
                # Record which APN was configured by the user (if any)
                user_apn_name = apn_config.get('name', '') if apn_config else ''
                self.configured_apn_rejected = bool(user_apn_name)
                self.last_failed_apn = user_apn_name or '(auto-discovery)'
                self.last_failure_time = time.time()

                if user_apn_name:
                    self.last_failure_reason = (
                        f"Connection failed using customer-configured APN '{user_apn_name}'. "
                        f"All fallback methods (discovery, auto-assign) also failed. "
                        f"Please verify the APN, username, password, and PDP type are correct "
                        f"for your carrier and SIM card. "
                        f"A new configuration must be applied to retry."
                    )
                else:
                    self.last_failure_reason = (
                        "All automatic APN connection methods failed (discovery and auto-assign). "
                        "No customer APN was configured. Consider configuring the correct APN "
                        "for your carrier and SIM card."
                    )

                self.initial_connection_failure_count += 1

                logger.error("All APN connection methods failed",
                           extra={'interface_number': self.interface_number,
                                  'configured_apn_rejected': self.configured_apn_rejected,
                                  'failed_apn': self.last_failed_apn,
                                  'failure_reason': self.last_failure_reason,
                                  'initial_connection_failure_count': self.initial_connection_failure_count})

                # Respect sim_failover_connect_retries: must exhaust the full APN
                # cascade this many times before switching SIMs.  The cascade
                # already covers last-connected → Android DB → blank/automatic,
                # so each count represents a genuine attempt with all methods.
                retries_required = self.config.get('sim_failover_connect_retries', 3) if self.config else 3
                if self.initial_connection_failure_count < retries_required:
                    logger.warning(
                        f"APN cascade failed (attempt {self.initial_connection_failure_count}/{retries_required}) — "
                        "scheduling failed-state retry before considering SIM failover",
                        extra={'interface_number': self.interface_number,
                               'failures_so_far': self.initial_connection_failure_count,
                               'retries_required': retries_required})
                    self.transition(ModemEvent.CONNECTION_FAILED)
                    return

                # For dual-SIM: attempt failover to the other SIM.  The shared
                # executor probes for an actually-present alternate slot,
                # applies cooldown/lock gating, transitions through
                # CONNECTION_FAILED (pre_switch_event) so SWITCH_SIM has a valid
                # source state, and suppresses failback to the known-bad primary
                # until corrected config arrives.
                switched = await self._failover_to_alternate_sim(
                    'initial_connection_failure', '_configure_modem_initial',
                    switch_reason='initial_connection_failure',
                    suppress_failback=True,
                    pre_switch_event=ModemEvent.CONNECTION_FAILED,
                    extra_data={'configured_apn_rejected': self.configured_apn_rejected,
                                'failed_apn': self.last_failed_apn})
                if not switched:
                    # Single SIM or failover not allowed/possible — park in
                    # FAILED and wait for the user to push corrected config.
                    logger.error(
                        "No SIM failover available — parking in FAILED state. "
                        "Apply new configuration via SetConfiguration() to retry.",
                        extra={'interface_number': self.interface_number,
                               'sim_failover_enabled': self._is_sim_failover_enabled(),
                               'failure_reason': self.last_failure_reason})
                    self.transition(ModemEvent.CONNECTION_FAILED)

        except Exception as e:
            logger.error(f"Initial modem configuration failed: {e}",
                        extra={'interface_number': self.interface_number})
            # Record the exception as the failure reason
            self.last_failure_reason = f"Modem configuration error: {e}"
            self.last_failure_time = time.time()

            # Clear "service is mid-disable / mid-reset" flags that
            # _ensure_modem_disabled_for_config set on the way in.  If we
            # leave these set, the handle_modem_event() FAILED/UNKNOWN
            # branch will silently suppress the recovery dispatch (it
            # treats our own disable/reset as the cause of FAILED).  That
            # was the precise reason cold-attach SIM failover never fired
            # when the modem was already `state=failed reason=sim-missing`
            # — config raised, flags stayed True, dispatch hit the guard
            # and returned without ever issuing SetPrimarySimSlot.
            self.service_initiated_disable = False
            self.reset_operation_in_progress = False
            self.reset_grace_period_end = 0

            # Don't override SIM_MISSING transition with CONNECTION_FAILED
            if self.machine.current_state != ModemState.WAITING_FOR_SIM.value:
                self.transition(ModemEvent.CONNECTION_FAILED)

            # Re-read modem State so the SIM-missing recovery path runs.
            # If the modem is still sitting in FAILED with sim-missing
            # (the very condition that caused this except branch),
            # _dispatch_initial_modem_state -> handle_modem_event(-1) ->
            # _handle_failed_state_event -> _handle_sim_missing_failover
            # will now succeed because the suppression flags are clear.
            self._safe_create_task(self._dispatch_initial_modem_state())
        finally:
            self.initial_configuration_in_progress = False

    async def _get_unlock_retries(self):
        """Read SIM unlock retry counters from ModemManager.

        Returns a dict mapping lock type to remaining retries, e.g.
        ``{1: 3, 2: 10}`` where key 1 = PIN retries, key 2 = PUK retries.
        Returns empty dict on failure.
        """
        try:
            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
            retries_variant = await props.call_get(MODEM_INTERFACE, "UnlockRetries")
            retries_raw = retries_variant.value if retries_variant else {}
            # Normalise: dbus_next may wrap each value in a Variant
            retries = {}
            for k, v in retries_raw.items():
                key = k.value if hasattr(k, 'value') else int(k)
                val = v.value if hasattr(v, 'value') else int(v)
                retries[key] = val
            return retries
        except Exception as e:
            logger.warning(f"Could not read UnlockRetries: {e}",
                          extra={'interface_number': self.interface_number})
            return {}

    async def _unlock_sim_if_needed(self):
        """Unlock SIM with PIN/PUK if required.

        Safety rules (headless router protection):
        - PIN unlock is attempted at most once per boot cycle.
        - If PIN fails, PUK auto-recovery is tried (once) if PUK is configured.
        - If PIN retries <= 1 before attempting, skip PIN and go to PUK recovery.
        - PUK unlock is attempted at most once per boot cycle.
        - If PUK retries <= 1, refuse to try — log CRITICAL.
        """
        try:
            if not self.config:
                return

            # If we already know the SIM is permanently destroyed, stop immediately
            if self._sim_permanently_locked:
                logger.critical("SIM is permanently locked (PUK exhausted) — cannot unlock",
                               extra={'interface_number': self.interface_number})
                raise Exception("SIM permanently locked — PUK retries exhausted")

            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
            state_variant = await props.call_get(MODEM_INTERFACE, "State")
            state = state_variant.value

            logger.info("Checking if SIM unlock is needed",
                       extra={'interface_number': self.interface_number,
                              'modem_state': state})

            # State 2 = LOCKED (needs PIN or PUK)
            if state == 2:
                # Get unlock requirement
                unlock_required_variant = await props.call_get(MODEM_INTERFACE, "UnlockRequired")
                unlock_required = unlock_required_variant.value

                # Read retry counters from SIM EEPROM
                retries = await self._get_unlock_retries()
                self._pin_retries_remaining = retries.get(1, -1)  # key 1 = SIM-PIN
                self._puk_retries_remaining = retries.get(2, -1)  # key 2 = SIM-PUK

                logger.info("SIM is locked, checking unlock requirement",
                           extra={'interface_number': self.interface_number,
                                  'unlock_required': unlock_required,
                                  'pin_retries': self._pin_retries_remaining,
                                  'puk_retries': self._puk_retries_remaining})

                # Anchor on the active slot so the correct SIM's PIN/PUK is
                # used after a failover (not the configured primary's).
                active_slot = self.current_active_sim or self.config.get('primary_sim_slot', 1)
                sim_slots = self.config.get('sim_slots', [])
                active_sim_config = next(
                    (sim for sim in sim_slots if sim['slot'] == active_slot), {}
                )

                if unlock_required == 1:  # MM_MODEM_LOCK_SIM_PIN
                    await self._unlock_with_pin(active_sim_config)
                elif unlock_required == 2:  # MM_MODEM_LOCK_SIM_PUK
                    # SIM is PUK-locked (PIN retries exhausted)
                    await self._unlock_with_puk(active_sim_config)
                else:
                    logger.warning("Unknown unlock requirement",
                                  extra={'interface_number': self.interface_number,
                                         'unlock_required': unlock_required})
            else:
                # Modem not locked - but check if SIM is actually present
                # With no SIM, modem can still reach ENABLED state on some hardware
                try:
                    sim_path_variant = await props.call_get(MODEM_INTERFACE, "Sim")
                    sim_path = sim_path_variant.value if hasattr(sim_path_variant, 'value') else sim_path_variant
                    if not sim_path or sim_path == '/':
                        logger.warning("⚠️ No SIM card detected in modem (Sim path is empty)",
                                      extra={'interface_number': self.interface_number,
                                             'modem_state': state,
                                             'sim_path': sim_path})
                        # Transition to WAITING_FOR_SIM
                        self.transition(ModemEvent.SIM_MISSING)
                        self._safe_create_task(self._handle_sim_missing_failover())
                        raise Exception("No SIM card present")
                    else:
                        logger.info("SIM unlock not needed",
                                   extra={'interface_number': self.interface_number,
                                          'modem_state': state,
                                          'sim_path': sim_path})
                except DBusError as dbus_e:
                    logger.warning(f"Could not check SIM presence: {dbus_e}",
                                  extra={'interface_number': self.interface_number})
                    # If we can't check, log but continue (don't block on D-Bus errors)
                    logger.info("SIM unlock not needed (presence check inconclusive)",
                               extra={'interface_number': self.interface_number,
                                      'modem_state': state})

        except Exception as e:
            if "No SIM card present" in str(e):
                # Re-raise SIM missing - this should stop the connection flow
                raise
            if "SIM permanently locked" in str(e):
                raise
            logger.error(f"SIM unlock check failed: {e}",
                        extra={'interface_number': self.interface_number})
            # Don't fail the entire configuration for SIM unlock issues
            logger.warning("Continuing configuration without SIM unlock",
                          extra={'interface_number': self.interface_number})

    async def _unlock_with_pin(self, sim_config):
        """Unlock SIM with PIN — tried at most once per boot cycle.

        Safety logic:
        1. If already attempted this boot cycle, refuse.
        2. If PIN retries <= 1, skip PIN and attempt PUK recovery instead.
        3. Send PIN once.  On failure, attempt PUK recovery if PUK is configured.
        """
        try:
            pin = sim_config.get('pin', '')

            if not pin:
                logger.warning("PIN required but not configured",
                              extra={'interface_number': self.interface_number})
                raise Exception("PIN required but not configured")

            # ── Guard: only one attempt per boot cycle ────────────────────
            if self._pin_unlock_attempted:
                if self._pin_unlock_failed:
                    logger.error("PIN unlock already failed this boot cycle — "
                                 "will not retry to protect remaining SIM retries",
                                extra={'interface_number': self.interface_number,
                                       'pin_retries': self._pin_retries_remaining})
                    raise Exception("PIN unlock already failed this boot cycle")
                # PIN succeeded previously — nothing to do
                logger.info("PIN unlock already succeeded this boot cycle",
                           extra={'interface_number': self.interface_number})
                return

            # ── Guard: check retry counter before sending ─────────────────
            if 0 < self._pin_retries_remaining <= 1:
                logger.critical("PIN retries dangerously low (%d) — skipping PIN, "
                                "attempting PUK recovery to avoid permanent lock",
                               self._pin_retries_remaining,
                               extra={'interface_number': self.interface_number,
                                      'pin_retries': self._pin_retries_remaining})
                self._pin_unlock_attempted = True
                self._pin_unlock_failed = True
                # Escalate to PUK recovery
                await self._unlock_with_puk(sim_config)
                return

            # ── Send PIN (one attempt) ────────────────────────────────────
            self._pin_unlock_attempted = True
            logger.info("Sending PIN to unlock SIM (one attempt, retries=%s)",
                       self._pin_retries_remaining,
                       extra={'interface_number': self.interface_number,
                              'pin_retries': self._pin_retries_remaining})

            iface = self.proxy.get_interface(MODEM_INTERFACE)
            await iface.call_send_pin(str(pin))

            # Wait for unlock to process
            await asyncio.sleep(3)

            # Verify unlock was successful
            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
            state_variant = await props.call_get(MODEM_INTERFACE, "State")
            state = state_variant.value

            if state != 2:  # No longer locked
                self._pin_unlock_failed = False
                # Refresh retry counters after success (they reset to max)
                retries = await self._get_unlock_retries()
                self._pin_retries_remaining = retries.get(1, -1)
                logger.info("SIM unlocked with PIN successfully",
                           extra={'interface_number': self.interface_number,
                                  'pin_retries_after': self._pin_retries_remaining})
            else:
                self._pin_unlock_failed = True
                # Re-read retries to see how many are left
                retries = await self._get_unlock_retries()
                self._pin_retries_remaining = retries.get(1, -1)
                self._puk_retries_remaining = retries.get(2, -1)
                logger.error("PIN unlock failed — SIM still locked "
                             "(retries remaining: PIN=%s, PUK=%s)",
                            self._pin_retries_remaining,
                            self._puk_retries_remaining,
                            extra={'interface_number': self.interface_number,
                                   'pin_retries': self._pin_retries_remaining,
                                   'puk_retries': self._puk_retries_remaining})
                # Attempt PUK recovery if PUK is configured
                puk = sim_config.get('puk', '')
                if puk:
                    logger.info("PIN failed — attempting PUK recovery to reset PIN",
                               extra={'interface_number': self.interface_number})
                    await self._unlock_with_puk(sim_config)
                else:
                    logger.critical("PIN failed and no PUK configured — SIM cannot be "
                                    "unlocked. Remaining PIN retries: %s",
                                   self._pin_retries_remaining,
                                   extra={'interface_number': self.interface_number,
                                          'pin_retries': self._pin_retries_remaining})
                    raise Exception("PIN unlock failed — no PUK configured for recovery")

        except Exception as e:
            if "already failed this boot cycle" in str(e):
                raise
            if "already succeeded this boot cycle" in str(e):
                return
            if "PUK" in str(e):
                raise  # Let PUK errors propagate
            logger.error(f"PIN unlock failed: {e}",
                        extra={'interface_number': self.interface_number})
            raise

    async def _unlock_with_puk(self, sim_config):
        """Unlock SIM with PUK, resetting PIN to the configured value.

        Uses SendPuk(puk, pin) where pin is the configured PIN — no separate
        new_pin field needed.  Tried at most once per boot cycle.

        Safety logic:
        1. If already attempted this boot cycle, refuse.
        2. If PUK retries <= 1, refuse — log CRITICAL (risk of permanent SIM destruction).
        3. Send PUK + PIN once.
        """
        try:
            puk = sim_config.get('puk', '')
            pin = sim_config.get('pin', '')

            if not puk:
                logger.critical("SIM is PUK-locked but no PUK configured — "
                                "cannot recover. Configure PUK to enable auto-recovery.",
                               extra={'interface_number': self.interface_number})
                raise Exception("PUK required but not configured")
            if not pin:
                logger.critical("SIM is PUK-locked — PUK is configured but no PIN "
                                "to reset to. Configure both PUK and PIN.",
                               extra={'interface_number': self.interface_number})
                raise Exception("PUK recovery requires a PIN to reset to")

            # ── Guard: only one attempt per boot cycle ────────────────────
            if self._puk_unlock_attempted:
                if self._puk_unlock_failed:
                    logger.critical("PUK unlock already failed this boot cycle — "
                                    "will not retry to protect remaining PUK retries",
                                   extra={'interface_number': self.interface_number,
                                          'puk_retries': self._puk_retries_remaining})
                    raise Exception("PUK unlock already failed this boot cycle")
                logger.info("PUK unlock already succeeded this boot cycle",
                           extra={'interface_number': self.interface_number})
                return

            # ── Guard: check PUK retry counter ────────────────────────────
            if 0 < self._puk_retries_remaining <= 1:
                self._puk_unlock_attempted = True
                self._puk_unlock_failed = True
                self._sim_permanently_locked = True
                logger.critical(
                    "PUK retries critically low (%d) — refusing to attempt PUK unlock. "
                    "SIM will be permanently destroyed if this last attempt fails. "
                    "Manual intervention required (mmcli or physical SIM removal).",
                    self._puk_retries_remaining,
                    extra={'interface_number': self.interface_number,
                           'puk_retries': self._puk_retries_remaining})
                raise Exception("PUK retries too low — refusing to risk permanent SIM destruction")

            # ── Send PUK + PIN (one attempt) ──────────────────────────────
            self._puk_unlock_attempted = True
            logger.info("Sending PUK to unlock SIM and reset PIN (one attempt, "
                        "PUK retries=%s)",
                       self._puk_retries_remaining,
                       extra={'interface_number': self.interface_number,
                              'puk_retries': self._puk_retries_remaining})

            iface = self.proxy.get_interface(MODEM_INTERFACE)
            await iface.call_send_puk(str(puk), str(pin))

            # Wait for unlock to process
            await asyncio.sleep(5)

            # Verify unlock was successful
            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
            state_variant = await props.call_get(MODEM_INTERFACE, "State")
            state = state_variant.value

            if state != 2:  # No longer locked
                self._puk_unlock_failed = False
                # Reset the PIN-failed flag too — PUK recovery restored PIN
                self._pin_unlock_failed = False
                self._pin_unlock_attempted = False
                # Refresh retry counters (they reset to max after PUK success)
                retries = await self._get_unlock_retries()
                self._pin_retries_remaining = retries.get(1, -1)
                self._puk_retries_remaining = retries.get(2, -1)
                logger.info("SIM unlocked with PUK — PIN reset to configured value "
                            "(PIN retries=%s, PUK retries=%s)",
                           self._pin_retries_remaining,
                           self._puk_retries_remaining,
                           extra={'interface_number': self.interface_number,
                                  'pin_retries': self._pin_retries_remaining,
                                  'puk_retries': self._puk_retries_remaining})
            else:
                self._puk_unlock_failed = True
                # Re-read retries
                retries = await self._get_unlock_retries()
                self._puk_retries_remaining = retries.get(2, -1)
                if self._puk_retries_remaining == 0:
                    self._sim_permanently_locked = True
                    logger.critical(
                        "PUK unlock failed and PUK retries exhausted — "
                        "SIM is permanently destroyed",
                        extra={'interface_number': self.interface_number})
                else:
                    logger.critical(
                        "PUK unlock failed — SIM still locked "
                        "(PUK retries remaining: %s)",
                        self._puk_retries_remaining,
                        extra={'interface_number': self.interface_number,
                               'puk_retries': self._puk_retries_remaining})
                raise Exception("PUK unlock failed — SIM still locked")

        except Exception as e:
            if "already failed this boot cycle" in str(e):
                raise
            if "already succeeded this boot cycle" in str(e):
                return
            if ("not configured" in str(e) or "too low" in str(e) or
                    "permanently destroyed" in str(e) or "still locked" in str(e)):
                raise
            logger.error(f"PUK unlock failed: {e}",
                        extra={'interface_number': self.interface_number})
            raise

    async def _configure_preferred_carrier(self):
        """Configure preferred carrier with smart scanning to minimize delays"""
        try:
            if not self.config:
                return

            # Get active SIM configuration.  Anchor on the slot that is
            # actually active (current_active_sim) so a failover SIM's own
            # preferred-carrier / network-scan settings are used, not the
            # configured primary's.  Falls back to primary before first switch.
            active_slot = self.current_active_sim or self.config.get('primary_sim_slot', 1)
            sim_slots = self.config.get('sim_slots', [])
            active_sim_config = next((sim for sim in sim_slots if sim['slot'] == active_slot), {})

            preferred_carrier = active_sim_config.get('preferred_carrier', '')
            enable_network_scan = active_sim_config.get('enable_network_scan', False)

            if not preferred_carrier and not enable_network_scan:
                logger.info("No preferred carrier configured and network scan disabled, "
                           "using automatic registration",
                           extra={'interface_number': self.interface_number})
                return

            logger.info("Checking carrier/scan configuration",
                       extra={'interface_number': self.interface_number,
                              'preferred_carrier': preferred_carrier or '(none)',
                              'enable_network_scan': enable_network_scan})

            # Get 3GPP interface
            try:
                introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, self.modem_path)
                proxy = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, self.modem_path, introspect)
                gpp_iface = proxy.get_interface("org.freedesktop.ModemManager1.Modem.Modem3gpp")
                props = proxy.get_interface("org.freedesktop.DBus.Properties")
            except Exception:
                logger.info("3GPP interface not available, using automatic registration",
                           extra={'interface_number': self.interface_number})
                return

            if preferred_carrier:
                # ── Preferred carrier path ───────────────────────────────
                # Check if already on preferred carrier (avoid scanning)
                try:
                    current_operator_name_variant = await props.call_get(
                        "org.freedesktop.ModemManager1.Modem.Modem3gpp", "OperatorName")
                    current_operator_name = current_operator_name_variant.value
                    if preferred_carrier.lower() in current_operator_name.lower():
                        logger.info("Already registered to preferred carrier",
                                   extra={'interface_number': self.interface_number,
                                          'current_operator': current_operator_name})
                        # Still do a diagnostic scan if enabled
                        if enable_network_scan:
                            await self._perform_diagnostic_scan(gpp_iface, props)
                        return
                except Exception:
                    pass

                # Try direct registration first (faster than scanning)
                if preferred_carrier.isdigit() and len(preferred_carrier) >= 5:
                    logger.info("Attempting direct registration using operator code",
                               extra={'interface_number': self.interface_number,
                                      'operator_code': preferred_carrier})
                    try:
                        await gpp_iface.call_register(preferred_carrier)
                        await self._wait_for_registered()
                        logger.info("Direct registration completed",
                                   extra={'interface_number': self.interface_number})
                        # Still do a diagnostic scan if enabled
                        if enable_network_scan:
                            await self._perform_diagnostic_scan(gpp_iface, props)
                        return
                    except Exception:
                        logger.info("Direct registration failed, falling back to network scan",
                                   extra={'interface_number': self.interface_number})

                # Friendly name requires a scan to resolve MCCMNC — always scan
                logger.warning("Performing network scan to resolve preferred carrier name "
                              "- this may take 2+ minutes",
                              extra={'interface_number': self.interface_number,
                                     'preferred_carrier': preferred_carrier})

                try:
                    scan_timeout = self.config.get('network_scan_timeout', 180)
                    operators = await asyncio.wait_for(gpp_iface.call_scan(), timeout=float(scan_timeout))
                    await self._process_scan_results(operators, preferred_carrier, gpp_iface, props)
                except asyncio.TimeoutError:
                    logger.warning("Network scan timed out, using automatic registration",
                                  extra={'interface_number': self.interface_number,
                                         'timeout_seconds': scan_timeout})

            elif enable_network_scan:
                # ── Diagnostic scan only (no preferred carrier) ──────────
                await self._perform_diagnostic_scan(gpp_iface, props)

        except Exception as e:
            logger.info("Carrier selection not supported, using automatic registration",
                       extra={'interface_number': self.interface_number,
                              'error': str(e)})

    async def _perform_diagnostic_scan(self, gpp_iface, props):
        """Perform a network scan for status/diagnostic purposes only.

        Results are cached in ``self.last_scan_results`` and appear in the
        ``available_networks`` field of the status output.  No registration
        change is made.
        """
        logger.info("Performing diagnostic network scan for status reporting "
                    "- this may take 2+ minutes",
                    extra={'interface_number': self.interface_number})
        try:
            scan_timeout = self.config.get('network_scan_timeout', 180)
            operators = await asyncio.wait_for(gpp_iface.call_scan(), timeout=float(scan_timeout))
            await self._process_scan_results(operators, None, gpp_iface, props)
        except asyncio.TimeoutError:
            logger.warning("Diagnostic network scan timed out",
                          extra={'interface_number': self.interface_number,
                                 'timeout_seconds': scan_timeout})
        except Exception as e:
            logger.warning("Diagnostic network scan failed",
                          extra={'interface_number': self.interface_number,
                                 'error': str(e)})

    @staticmethod
    def _carrier_name_matches(user_input, operator_long, operator_short):
        """Return True if user_input matches either reported operator name.

        Matching is case-insensitive and bidirectional, so both
        "Bell" vs "Bell Canada" and "Bell Canada" vs "Bell" match.
        No carrier names or telecom-specific vocabulary are hardcoded —
        matching is pure string containment against whatever
        ModemManager reports as operator-long / operator-short.
        """
        if not user_input or (not operator_long and not operator_short):
            return False

        user = user_input.strip().lower()
        if not user:
            return False
        names = [n.strip().lower() for n in (operator_long, operator_short)
                 if n and n.strip()]
        if not names:
            return False

        for name in names:
            if user == name or user in name or name in user:
                return True
        return False

    async def _process_scan_results(self, operators, preferred_carrier, gpp_iface, props):
        """Process network scan results and register to preferred operator.

        Scan() returns aa{sv} — an array of dicts, each with Variant values:
            'operator-long'  (s)  — long operator name, e.g. "T-Mobile"
            'operator-short' (s)  — short operator name
            'operator-code'  (s)  — MCCMNC code, e.g. "310260"
            'status'         (u)  — MMModem3gppNetworkAvailability enum
            'access-technology' (u) — MMModemAccessTechnology bitmask

        Status values:
            0 = Unknown, 1 = Available, 2 = Current, 3 = Forbidden

        Results are cached in ``self.last_scan_results`` for status reporting.
        """
        status_labels = {0: 'unknown', 1: 'available', 2: 'current', 3: 'forbidden'}
        target_code = None
        target_name = None
        parsed_results = []

        for op in operators:
            try:
                # Each op is a dict[str, Variant]; unwrap Variant values
                operator_code = op.get('operator-code')
                operator_name = op.get('operator-long')
                operator_short = op.get('operator-short')
                status = op.get('status')
                access_tech = op.get('access-technology')

                # Unwrap Variant objects (dbus_next wraps a{sv} values as Variant)
                if hasattr(operator_code, 'value'):
                    operator_code = operator_code.value
                if hasattr(operator_name, 'value'):
                    operator_name = operator_name.value
                if hasattr(operator_short, 'value'):
                    operator_short = operator_short.value
                if hasattr(status, 'value'):
                    status = status.value
                if hasattr(access_tech, 'value'):
                    access_tech = access_tech.value

                operator_code = operator_code or ''
                operator_name = operator_name or ''
                operator_short = operator_short or ''
                status = status if isinstance(status, int) else 0
                access_tech = access_tech if isinstance(access_tech, int) else 0

                parsed_results.append({
                    'operator_name': operator_name,
                    'operator_short': operator_short,
                    'operator_code': operator_code,
                    'status': status_labels.get(status, f'unknown({status})'),
                    'access_technology': self._access_tech_to_string(access_tech),
                })

                logger.info("Found operator",
                           extra={'interface_number': self.interface_number,
                                  'operator_name': operator_name,
                                  'operator_code': operator_code,
                                  'status': status})

                # Match preferred carrier by MCCMNC code or name.
                # Status 1 = Available, 2 = Current (already registered).
                #
                # Name matching is bidirectional and checks both the long
                # and short operator-name fields so that user input like
                # "bell canada" still matches a modem reporting just "Bell"
                # (and vice-versa: "bell" matches "Bell Mobility Canada").
                # Token-overlap matching catches cases where neither side
                # is a clean substring (e.g. "Bell Canada" vs "BellMTS").
                if preferred_carrier and status in [1, 2] and (
                    preferred_carrier == operator_code
                    or self._carrier_name_matches(
                        preferred_carrier, operator_name, operator_short
                    )
                ):
                    target_code = operator_code
                    target_name = operator_name
                    logger.info("Matched preferred carrier in scan",
                               extra={'interface_number': self.interface_number,
                                      'operator_name': operator_name,
                                      'operator_code': operator_code})
                    break

            except Exception:
                continue

        # Cache results for status reporting
        self.last_scan_results = parsed_results
        logger.info("Network scan complete",
                   extra={'interface_number': self.interface_number,
                          'operators_found': len(parsed_results)})

        # Register() takes an MCCMNC operator code string (e.g. "310260")
        if target_code:
            logger.info("Registering to preferred carrier from scan",
                       extra={'interface_number': self.interface_number,
                              'operator_name': target_name,
                              'operator_code': target_code})
            await gpp_iface.call_register(target_code)
            await self._wait_for_registered()
        elif preferred_carrier:
            logger.warning("Preferred carrier not found in scan, using automatic",
                          extra={'interface_number': self.interface_number})

    def _get_connection_timeout(self) -> float:
        """Get configured APN connection timeout in seconds."""
        timeout = float(getattr(self, 'connection_timeout', 120.0))
        return max(5.0, timeout)

    def _get_registration_timeout(self) -> float:
        """Get configured registration timeout in seconds."""
        timeout = float(getattr(self, 'registration_timeout', 180.0))
        return max(30.0, timeout)

    async def _wait_for_registered(self):
        """Wait until ModemManager reaches REGISTERED/CONNECTING/CONNECTED."""
        timeout = self._get_registration_timeout()
        deadline = time.time() + timeout

        while time.time() < deadline:
            try:
                props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
                state_variant = await props.call_get(MODEM_INTERFACE, "State")
                mm_state = state_variant.value
                if mm_state in (8, 10, 11):
                    return True
            except Exception:
                pass
            await asyncio.sleep(2)

        logger.warning("Registration wait timed out",
                      extra={'interface_number': self.interface_number,
                             'timeout_seconds': timeout})
        return False

    async def _wait_for_stable_registration(self):
        """Wait until the modem is CONFIRMED registered on two consecutive reads.

        A plain single ``State`` read is unreliable right after a band/mode
        change: setting CurrentBands on an enabled modem deregisters it from
        the old band and forces a re-acquisition on the new one, but for a
        brief window the modem can still report a STALE ``REGISTERED`` from the
        band it just left.  If the connection cascade trusts that stale value
        it issues Simple.Connect() into a modem that immediately drops
        registration — the connect fails and (worse) no SIM failover runs
        because the modem never reached a FAILED state.

        Requiring two consecutive registered reads (~3 s apart) ensures the
        registration is real and has survived the post-band-change settle, so a
        SIM that genuinely cannot register on the restricted band falls through
        to the timeout → failover path instead of a misleading connect failure.
        """
        timeout = self._get_registration_timeout()
        deadline = time.time() + timeout
        consecutive = 0

        while time.time() < deadline:
            try:
                props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
                state_variant = await props.call_get(MODEM_INTERFACE, "State")
                mm_state = state_variant.value
                if mm_state in (8, 10, 11):
                    consecutive += 1
                    if consecutive >= 2:
                        return True
                else:
                    consecutive = 0  # lost registration — start over
            except Exception:
                consecutive = 0
            await asyncio.sleep(3)

        logger.warning("Stable-registration wait timed out",
                      extra={'interface_number': self.interface_number,
                             'timeout_seconds': timeout})
        return False

    async def _force_network_reregistration(self, reason: str = 'reregister'):
        """Nudge the modem to (re)acquire the network after a config change.

        Writing CurrentBands / SetCurrentModes on an ENABLED modem changes the
        allowed RF set, but some modems (notably Telit QMI modems) do not
        re-evaluate registration on their own afterwards — they stay parked at
        ENABLED/SEARCHING using the prior context, so a freshly-switched SIM can
        sit idle until the registration timeout fires.

        Two-step nudge, both best-effort and non-fatal:
          1. Ask ModemManager for AUTOMATIC registration (``Modem3gpp.Register``
             with an empty operator id).  This is the light "go attach now"
             kick and is enough on most modems.
          2. If the modem is still not registered shortly after, do a clean
             disable→enable cycle, which forces a full PLMN/cell re-scan with
             the new band/mode set in effect.  CurrentBands persists across the
             cycle, so the restriction stays applied.

        Returns True if the modem is registered by the end, else False.
        """
        if not self.proxy:
            return False

        props = self.proxy.get_interface("org.freedesktop.DBus.Properties")

        async def _is_registered() -> bool:
            try:
                state_v = await props.call_get(MODEM_INTERFACE, "State")
                return state_v.value in (8, 10, 11)
            except Exception:
                return False

        # Already registered — nothing to nudge.
        if await _is_registered():
            return True

        # Step 1: request automatic registration.
        try:
            gpp_iface = self.proxy.get_interface(
                "org.freedesktop.ModemManager1.Modem.Modem3gpp")
            logger.info("Requesting automatic network registration",
                       extra={'interface_number': self.interface_number,
                              'reason': reason})
            # Register('') blocks until the modem attaches or errors; cap it so
            # a no-coverage band can't stall the switch flow here (the caller's
            # connection cascade has its own registration gate + failover).
            await asyncio.wait_for(gpp_iface.call_register(''), timeout=30)
        except asyncio.TimeoutError:
            logger.info("Automatic registration request still pending after 30s",
                       extra={'interface_number': self.interface_number,
                              'reason': reason})
        except Exception as e:
            logger.debug(f"Automatic registration request failed (non-fatal): {e}",
                        extra={'interface_number': self.interface_number,
                               'reason': reason})

        if await _is_registered():
            logger.info("Modem registered after automatic-registration nudge",
                       extra={'interface_number': self.interface_number,
                              'reason': reason})
            return True

        # Step 2: heavier kick — disable→enable to force a full re-scan.
        try:
            logger.info("Modem still not registered — forcing disable/enable "
                       "cycle to re-acquire on the new configuration",
                       extra={'interface_number': self.interface_number,
                              'reason': reason})
            await self._ensure_modem_disabled_for_config()
            await self._ensure_modem_enabled()
        except Exception as e:
            logger.warning(f"Disable/enable re-registration cycle failed (non-fatal): {e}",
                          extra={'interface_number': self.interface_number,
                                 'reason': reason})

        registered = await _is_registered()
        logger.info("Re-registration nudge complete",
                   extra={'interface_number': self.interface_number,
                          'reason': reason,
                          'registered': registered})
        return registered

    async def _ensure_modem_disabled_for_config(self):
        """Ensure modem is disabled for SIM/band configuration"""
        try:
            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
            state_variant = await props.call_get(MODEM_INTERFACE, "State")
            state = state_variant.value

            # If modem is enabled (state >= 6), disable it for configuration
            if state >= 6:
                logger.info("Disabling modem for SIM/band configuration",
                           extra={'interface_number': self.interface_number,
                                  'current_state': state})

                # Set flags to prevent false SIM missing detection during gentle reset
                self.service_initiated_disable = True
                self.reset_operation_in_progress = True
                self.reset_grace_period_end = time.time() + 30  # Shorter grace period for gentle reset

                iface = self.proxy.get_interface(MODEM_INTERFACE)
                await iface.call_enable(False)

                # Wait for modem to be disabled
                max_wait = 30
                wait_time = 0
                while wait_time < max_wait:
                    await asyncio.sleep(2)
                    wait_time += 2
                    state_variant = await props.call_get(MODEM_INTERFACE, "State")
                    state = state_variant.value
                    if state <= 3:  # DISABLED or lower
                        logger.info("Modem disabled for configuration",
                                   extra={'interface_number': self.interface_number})
                        return

                raise Exception("Timeout waiting for modem to disable for configuration")
            else:
                logger.info("Modem already disabled for configuration",
                           extra={'interface_number': self.interface_number,
                                  'modem_state': state})

        except Exception as e:
            logger.error(f"Failed to disable modem for configuration: {e}",
                        extra={'interface_number': self.interface_number})
            raise

    async def _ensure_modem_enabled(self, max_attempts=3, post_reset=False):
        """Enable the modem if it's disabled - with enhanced recovery"""

        for attempt in range(max_attempts):
            try:
                # Use longer timeouts after hardware reset
                if post_reset:
                    # Much longer timeouts after reset: 120s, 180s, 240s
                    timeout = 120 + (60 * attempt)
                else:
                    # Normal timeouts: 30s, 60s, 90s
                    timeout = 30 + (30 * attempt)

                await self._try_enable_modem_once(timeout)
                return  # Success!

            except Exception as e:
                logger.warning(f"Modem enable attempt {attempt + 1} failed: {e}",
                              extra={'interface_number': self.interface_number,
                                     'attempt': attempt + 1,
                                     'max_attempts': max_attempts,
                                     'post_reset': post_reset})

                if attempt < max_attempts - 1:
                    # Try recovery methods before next attempt
                    if attempt == 1 and not post_reset:  # Only reset if not already post-reset
                        if self._is_reset_allowed():
                            logger.info("Attempting hardware reset before retry",
                                       extra={'interface_number': self.interface_number})
                            try:
                                await modem_reset(self.interface_number)
                                self._record_reset()
                                await asyncio.sleep(30)  # Increased wait time for modem boot
                                # Next attempt will be post-reset
                                post_reset = True
                            except Exception as reset_e:
                                logger.error(f"Hardware reset failed: {reset_e}",
                                            extra={'interface_number': self.interface_number})
                        else:
                            logger.warning("Skipping hardware reset before retry due to cooldown",
                                         extra={'interface_number': self.interface_number})

                    await asyncio.sleep(10)  # Brief pause before retry
                else:
                    # All attempts failed
                    logger.error("All modem enable attempts failed",
                                extra={'interface_number': self.interface_number})
                    raise

    async def _try_enable_modem_once(self, timeout_seconds):
        """Single attempt to enable modem with specified timeout"""
        props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
        state_variant = await props.call_get(MODEM_INTERFACE, "State")
        state = state_variant.value

        # State 3 = DISABLED
        if state == 3:
            # Check power state first - modem needs to be powered on before enabling
            power_state_variant = await props.call_get(MODEM_INTERFACE, "PowerState")
            power_state = power_state_variant.value

            # PowerState: 0=unknown, 1=off, 2=low, 3=on
            if power_state == 1:  # Power is off
                logger.info("Modem power is off, powering on first...",
                           extra={'interface_number': self.interface_number})

                iface = self.proxy.get_interface(MODEM_INTERFACE)
                try:
                    # Power on the modem first
                    await iface.call_set_power_state(2)  # 2 = low power (sufficient for enable)
                    await asyncio.sleep(3)  # Wait for power to stabilize

                    # Check if power state changed
                    power_state_variant = await props.call_get(MODEM_INTERFACE, "PowerState")
                    new_power_state = power_state_variant.value
                    logger.info(f"Power state after power-on: {new_power_state}",
                               extra={'interface_number': self.interface_number})

                except Exception as power_error:
                    logger.warning(f"Failed to power on modem: {power_error}",
                                  extra={'interface_number': self.interface_number})
                    # Continue anyway - maybe it will work
            elif power_state == 2:  # Low power (airplane-mode leftover)
                # Modem is RF-off — raise to ON before Enable(True),
                # otherwise some drivers reject the enable call.
                logger.info("Modem in low-power state, raising to ON before enable",
                           extra={'interface_number': self.interface_number})
                iface = self.proxy.get_interface(MODEM_INTERFACE)
                try:
                    await iface.call_set_power_state(3)  # 3 = on
                    await asyncio.sleep(3)
                    self._airplane_mode_active = False
                except Exception as power_error:
                    logger.warning(f"Failed to raise power to ON: {power_error}",
                                  extra={'interface_number': self.interface_number})
                    # Continue anyway — Enable() may still work on some firmware

            logger.info(f"Modem is disabled, enabling... (timeout: {timeout_seconds}s)",
                       extra={'interface_number': self.interface_number})

            iface = self.proxy.get_interface(MODEM_INTERFACE)
            await iface.call_enable(True)

            # Wait for modem to be enabled with specified timeout
            wait_time = 0
            while wait_time < timeout_seconds:
                await asyncio.sleep(2)
                wait_time += 2
                state_variant = await props.call_get(MODEM_INTERFACE, "State")
                state = state_variant.value
                if state >= 6:  # ENABLED or higher
                    logger.info(f"Modem enabled successfully after {wait_time}s",
                               extra={'interface_number': self.interface_number})
                    # Clear service-initiated disable flags
                    self.service_initiated_disable = False
                    self.reset_operation_in_progress = False
                    return

            raise Exception(f"Timeout waiting for modem to enable ({timeout_seconds}s)")
        else:
            logger.info("Modem already enabled",
                       extra={'interface_number': self.interface_number,
                              'modem_state': state})

    async def _configure_sim_slot(self):
        """Configure the active SIM slot while modem is disabled"""
        try:
            if not self.config:
                return

            config_sim_slot = self.config.get('primary_sim_slot', 1)
            self.config_active_sim = config_sim_slot

            logger.info("Configuring SIM slot while disabled",
                       extra={'interface_number': self.interface_number,
                              'config_sim_slot': config_sim_slot})

            # GPIO-mux: the slot is selected by an external mux, not by
            # ModemManager's PrimarySimSlot.  Read the mux's current position
            # from the sim_select line; if it does not match the configured
            # primary, drive the mux and reboot so the modem enumerates the
            # newly-selected SIM.
            if self.sim_controller.is_gpio_mux:
                current_slot = await self.sim_controller.current_selected_slot()
                self.current_active_sim = current_slot or config_sim_slot
                logger.info("GPIO-mux SIM slot check",
                           extra={'interface_number': self.interface_number,
                                  'mux_slot': current_slot,
                                  'config_sim': config_sim_slot})
                if current_slot is not None and current_slot != config_sim_slot:
                    self._sim_switch_in_progress = True
                    try:
                        await self.sim_controller.switch_to(config_sim_slot)
                        await self._rescan_after_sim_switch()
                    finally:
                        self._sim_switch_in_progress = False
                    self.current_active_sim = config_sim_slot
                    logger.info("GPIO-mux SIM slot selected",
                               extra={'interface_number': self.interface_number,
                                      'new_sim': config_sim_slot})
                return

            # Check current SIM slot
            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
            try:
                actual_sim_variant = await props.call_get(MODEM_INTERFACE, "PrimarySimSlot")
                actual_sim = actual_sim_variant.value
                self.current_active_sim = actual_sim

                logger.info("SIM slot configuration check",
                           extra={'interface_number': self.interface_number,
                                  'actual_sim': actual_sim,
                                  'config_sim': config_sim_slot,
                                  'needs_switch': actual_sim != config_sim_slot})

                if actual_sim != config_sim_slot:
                    # Simple SIM slot change while disabled.
                    # On Telit LN920, SetPrimarySimSlot causes a modem reset /
                    # USB re-enumeration — protect from the on_modem_removed handler.
                    logger.info("Setting SIM slot while modem disabled",
                               extra={'interface_number': self.interface_number,
                                      'from_sim': actual_sim,
                                      'to_sim': config_sim_slot})

                    # Suppress modem-removed handler during the switch
                    self._sim_switch_in_progress = True
                    try:
                        # Set primary SIM slot using the SetPrimarySimSlot method
                        # (not the property setter, which is read-only on some modems like Telit LN920)
                        iface = self.proxy.get_interface(MODEM_INTERFACE)
                        await iface.call_set_primary_sim_slot(config_sim_slot)

                        # Modem will likely disappear — wait for it to come back
                        logger.info("SIM slot command sent — waiting for modem to re-appear",
                                   extra={'interface_number': self.interface_number})
                        await self._rescan_after_sim_switch()
                    finally:
                        self._sim_switch_in_progress = False

                    # Verify the switch with the new proxy
                    props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
                    new_sim_variant = await props.call_get(MODEM_INTERFACE, "PrimarySimSlot")
                    new_sim = new_sim_variant.value
                    self.current_active_sim = new_sim

                    if new_sim == config_sim_slot:
                        logger.info("SIM slot configured successfully",
                                   extra={'interface_number': self.interface_number,
                                          'new_sim': new_sim})
                    else:
                        logger.error("SIM slot configuration failed",
                                    extra={'interface_number': self.interface_number,
                                           'target_sim': config_sim_slot,
                                           'actual_sim': new_sim})
                        raise Exception(f"SIM slot switch failed: expected {config_sim_slot}, got {new_sim}")
                else:
                    logger.info("SIM slot already correct",
                               extra={'interface_number': self.interface_number,
                                      'active_sim': actual_sim})

            except Exception as e:
                logger.warning(f"SIM slot configuration failed: {e}",
                              extra={'interface_number': self.interface_number})
                # Don't fail completely - continue with current SIM

        except Exception as e:
            logger.error(f"SIM slot configuration error: {e}",
                        extra={'interface_number': self.interface_number})

    async def _validate_sim_iccid(self):
        """Validate that the inserted SIM matches the configured ICCID lock.

        Called after the modem is enabled and the SIM is unlocked so that the
        ICCID (SimIdentifier) is readable via D-Bus.  If the configured ICCID
        is empty the check is skipped (no lock).

        On mismatch the method raises ``Exception`` which causes
        ``_configure_modem_initial()`` to abort — the FSM will not connect
        with a non-matching SIM.
        """
        if not self.config:
            return

        active_slot = self.current_active_sim or self.config.get('primary_sim_slot', 1)
        sim_slots = self.config.get('sim_slots', [])
        slot_cfg = None
        for s in sim_slots:
            if s.get('slot') == active_slot:
                slot_cfg = s
                break

        if not slot_cfg:
            return

        expected_iccid = slot_cfg.get('iccid', '')
        if not expected_iccid:
            # No ICCID lock configured — allow any SIM
            return

        # Read the actual ICCID from the inserted SIM via D-Bus
        actual_iccid = ''
        try:
            probed = await self._probe_sim_slot_info(active_slot)
            actual_iccid = probed.get('iccid', '')
        except Exception as e:
            logger.error(f"Cannot read SIM ICCID for lock validation: {e}",
                        extra={'interface_number': self.interface_number,
                               'slot': active_slot})

        if not actual_iccid:
            # SIM present but ICCID unreadable — treat as mismatch
            logger.critical("ICCID lock: cannot read ICCID from SIM — rejecting slot",
                           extra={'interface_number': self.interface_number,
                                  'slot': active_slot,
                                  'expected_iccid': expected_iccid})
            self.iccid_mismatch = True
            raise Exception(f"SIM slot {active_slot}: ICCID unreadable — ICCID lock rejects this SIM")

        if actual_iccid != expected_iccid:
            logger.critical("ICCID lock MISMATCH — SIM in slot does not match configured ICCID",
                           extra={'interface_number': self.interface_number,
                                  'slot': active_slot,
                                  'expected_iccid': expected_iccid,
                                  'actual_iccid': actual_iccid})
            self.iccid_mismatch = True
            raise Exception(
                f"SIM slot {active_slot}: ICCID mismatch — "
                f"expected {expected_iccid}, got {actual_iccid}"
            )

        # Match — clear any prior mismatch flag
        self.iccid_mismatch = False
        logger.info("ICCID lock validated — SIM identity matches",
                   extra={'interface_number': self.interface_number,
                          'slot': active_slot,
                          'iccid': actual_iccid})

    def _is_sim_failover_enabled(self) -> bool:
        """Check if SIM failover is enabled.

        SIM failover is a global setting under the ``sim`` tree,
        at the same level as ``failback``.
        """
        if not self.config:
            return True
        return self.config.get('sim_failover', 'enabled') == 'enabled'

    def _is_failover_allowed(self) -> bool:
        """Check if SIM failover is allowed (not in cooldown / backoff)"""
        current_time = time.time()
        time_since_last = current_time - self.last_failover_time

        # Extended backoff after too many failovers
        if self.failover_count >= self.max_failovers_before_backoff:
            if time_since_last < self.failover_backoff_seconds:
                remaining = self.failover_backoff_seconds - time_since_last
                logger.warning(f"SIM failover blocked by extended backoff - {remaining:.1f}s remaining "
                              f"(failover_count={self.failover_count})",
                              extra={'interface_number': self.interface_number})
                return False
            else:
                # Backoff expired, reset counter
                logger.info("Extended failover backoff expired, resetting counter",
                           extra={'interface_number': self.interface_number})
                self.failover_count = 0

        # Normal cooldown between failovers
        if time_since_last < self.failover_cooldown_seconds:
            remaining = self.failover_cooldown_seconds - time_since_last
            logger.warning(f"SIM failover blocked by cooldown - {remaining:.1f}s remaining",
                          extra={'interface_number': self.interface_number})
            return False

        return True

    def _is_target_sim_enabled(self, target_slot: int) -> bool:
        """Check if the target SIM slot is enabled in the configuration.

        Returns False if the target slot is explicitly disabled, preventing
        pointless failover attempts to a slot the user has turned off.
        """
        if not self.config or 'sim_slots' not in self.config:
            return True  # No config to check — assume enabled
        for slot in self.config['sim_slots']:
            if slot.get('slot') == target_slot:
                return slot.get('enabled', True)
        return True  # Slot not found in config — assume enabled

    def _signal_failover_possible(self) -> bool:
        """Cheap precheck: is signal-loss SIM-failover worth evaluating?

        Avoids spinning the below-threshold timer (and emitting failover
        attempts) on single-SIM setups or when failover is disabled.  Returns
        True only when failover is enabled and at least one *eligible* SIM slot
        other than the currently-active one exists in the configuration.
        Physical presence of that SIM is still verified at switch time by
        _failover_to_alternate_sim_locked().

        A candidate slot is NOT eligible if it is the primary SIM while a
        data-cap sticky hold (``failback_suppressed_by_data_limit``) is
        active: in that case the primary was deliberately abandoned because it
        hit its data limit, so weak signal on the backup must not drag us back
        onto the capped primary (which would defeat sim-failover-sticky and
        cause failover↔failback oscillation).
        """
        if not self.config or not self._is_sim_failover_enabled():
            return False
        active = self.current_active_sim or self.config.get('primary_sim_slot', 1)
        primary = self.config.get('primary_sim_slot', 1)
        for slot in self.config.get('sim_slots', []):
            slot_num = slot.get('slot')
            if slot_num == active or not slot.get('enabled', True):
                continue
            if slot_num == primary and self.failback_suppressed_by_data_limit:
                continue
            return True
        return False

    async def _present_eligible_alternate_exists(self) -> bool:
        """Presence-aware companion to ``_signal_failover_possible()``.

        ``_signal_failover_possible()`` is a cheap *config-only* gate: it is
        satisfied as soon as a configured, enabled, non-active slot exists —
        it does NOT confirm a SIM is physically in that slot.  That is correct
        for the cooldown-guarded switch path (presence is verified at switch
        time), but it means weak-signal failover keeps ARMING its timer and
        emitting attempts even when the only alternate slot is physically
        empty (e.g. right after a hot-eject failover, where the just-vacated
        slot is still configured+enabled but now holds no SIM).

        This probes ModemManager ``SimSlots`` for each eligible slot and
        returns True only when at least one actually has a SIM present, so the
        signal-loss path can stay quiet when there is nowhere to switch.
        Slightly more expensive (one D-Bus read per eligible slot), so callers
        invoke it only at decision points (arming / firing), never per poll.
        """
        if not self._signal_failover_possible():
            return False
        active = self.current_active_sim or self.config.get('primary_sim_slot', 1)
        primary = self.config.get('primary_sim_slot', 1)
        for slot in self.config.get('sim_slots', []):
            slot_num = slot.get('slot')
            if slot_num == active or not slot.get('enabled', True):
                continue
            if slot_num == primary and self.failback_suppressed_by_data_limit:
                continue
            if await self._check_primary_sim_available(slot_num):
                return True
        return False

    def _record_failover(self):
        """Record that a SIM failover was performed"""
        self.last_failover_time = time.time()
        self.failover_count += 1
        self.lifetime_failover_count += 1
        self.is_on_failover_sim = True
        logger.info(f"SIM failover #{self.failover_count} recorded",
                   extra={'interface_number': self.interface_number,
                          'failover_count': self.failover_count,
                          'lifetime_failover_count': self.lifetime_failover_count,
                          'failover_time': self.last_failover_time,
                          'primary_sim': self.primary_sim_slot})
        self._emit_alert(
            alert_type='sim_failover',
            severity='warning',
            message='SIM failover recorded',
            failover_count=self.failover_count,
            primary_sim_slot=self.primary_sim_slot or 0,
            active_sim_slot=self.current_active_sim or 0,
            last_failover_time=self.last_failover_time,
        )

    def _record_bearer_down(self, reason: str, *, registration_lost: bool = False):
        """Record a bearer-down event and start downtime accounting."""
        now = time.time()
        self.bearer_disconnect_count += 1
        if registration_lost:
            self.registration_loss_count += 1
        self.last_disconnect_time = now
        self.last_disconnect_reason = reason

        if self._bearer_down_since is None:
            self._bearer_down_since = now

        # The current session is over — invalidate the usage baseline so it is
        # not reused for a different session/slot.
        self._usage_baseline_bytes = None
        self._usage_baseline_slot = None
        # Drop the salvage cache too; any in-flight session was already flushed
        # by the caller (e.g. on_modem_removed) before this point.
        self._last_session_bytes = 0
        self._last_session_slot = None

        logger.info("Recorded bearer disconnect",
                   extra={'interface_number': self.interface_number,
                          'reason': reason,
                          'bearer_disconnect_count': self.bearer_disconnect_count,
                          'registration_loss_count': self.registration_loss_count})
        self._emit_alert(
            alert_type='bearer_down',
            severity='warning',
            message=f'Bearer disconnected ({reason})',
            reason=reason,
            registration_lost=registration_lost,
            bearer_disconnect_count=self.bearer_disconnect_count,
            registration_loss_count=self.registration_loss_count,
            disconnect_time=now,
        )

    def _record_reconnect_attempt(self, reason: str):
        """Record an automatic reconnect attempt after a bearer loss."""
        self.reconnect_attempt_count += 1
        logger.info("Recorded reconnect attempt",
                   extra={'interface_number': self.interface_number,
                          'reason': reason,
                          'reconnect_attempt_count': self.reconnect_attempt_count})
        self._emit_alert(
            alert_type='reconnect_attempt',
            severity='info',
            message=f'Automatic reconnect attempt ({reason})',
            reason=reason,
            reconnect_attempt_count=self.reconnect_attempt_count,
        )

    def _record_bearer_up(self, reason: str = 'reconnected'):
        """Record bearer recovery and close downtime accounting if active."""
        if self._bearer_down_since is None:
            return

        now = time.time()
        downtime = max(0, int(now - self._bearer_down_since))
        self.total_bearer_downtime_seconds += downtime
        self.reconnect_success_count += 1
        self._bearer_down_since = None

        logger.info("Recorded bearer recovery",
                   extra={'interface_number': self.interface_number,
                          'reason': reason,
                          'downtime_seconds': downtime,
                          'total_bearer_downtime_seconds': self.total_bearer_downtime_seconds,
                          'reconnect_success_count': self.reconnect_success_count})
        self._emit_alert(
            alert_type='bearer_up',
            severity='info',
            message=f'Bearer recovered ({reason})',
            reason=reason,
            downtime_seconds=downtime,
            total_bearer_downtime_seconds=self.total_bearer_downtime_seconds,
            reconnect_success_count=self.reconnect_success_count,
        )

    def _record_sim_switch(self, from_sim: int, to_sim: int, reason: str):
        """Record a runtime SIM slot change."""
        if from_sim in (None, 0) or to_sim in (None, 0) or from_sim == to_sim:
            return

        # Dedupe: reset-based modems re-enumerate on SetPrimarySimSlot, so the
        # same switch can be reported both by the switch executor and by a
        # later PrimarySimSlot PropertiesChanged signal.  Count it once.
        key = (from_sim, to_sim)
        now = time.time()
        if self._last_sim_switch_key == key and (now - self._last_sim_switch_ts) < 30:
            return
        self._last_sim_switch_key = key
        self._last_sim_switch_ts = now

        self.sim_switch_count += 1
        logger.info("Recorded SIM switch",
                   extra={'interface_number': self.interface_number,
                          'from_sim': from_sim,
                          'to_sim': to_sim,
                          'reason': reason,
                          'sim_switch_count': self.sim_switch_count})
        self._emit_alert(
            alert_type='sim_switch',
            severity='warning' if 'failover' in str(reason) else 'info',
            message=f'SIM switched from slot {from_sim} to slot {to_sim} ({reason})',
            from_sim=from_sim,
            to_sim=to_sim,
            reason=reason,
            sim_switch_count=self.sim_switch_count,
        )

    def _current_usage_slot(self) -> int:
        """Return the SIM slot number used as the usage-tracking key.

        Usage is tracked per SIM slot (not per physical ICCID) because the
        carrier data plan / billing limit is configured against a slot
        (``sim_slot_N_*``).  Tracking by physical ICCID would reset the
        counter when a replacement SIM is issued on the same plan.
        """
        return self.current_active_sim or self.config.get('primary_sim_slot', 1)

    def _ensure_usage_monitoring_started(self, source: str):
        """Start usage monitoring whenever a bearer is connected."""
        if self.usage_monitor_task and not self.usage_monitor_task.done():
            return

        data_cfg = self._get_active_sim_data_config()
        logger.info("Starting usage monitoring",
                   extra={'interface_number': self.interface_number,
                          'source': source,
                          'usage_tracking_slot': self._current_usage_slot(),
                          'data_limit_bytes': data_cfg.get('data_limit_size', 0)})
        self.usage_monitor_task = self._safe_create_task(self.monitor_data_usage())

    def _reset_failover_counters(self):
        """Reset failover counters after a stable connection is established"""
        if self.failover_count > 0 or self.connectivity_recovery_attempts > 0:
            logger.info("Resetting failover counters after stable connection",
                       extra={'interface_number': self.interface_number,
                              'previous_failover_count': self.failover_count,
                              'previous_recovery_attempts': self.connectivity_recovery_attempts})
        self.failover_count = 0
        self.connectivity_recovery_attempts = 0
        self.initial_connection_failure_count = 0
        self.hardware_reset_attempts = 0

    # ── APN state persistence ──────────────────────────────────────────────

    def _apn_state_path(self) -> str:
        """Return the path of the per-interface APN state file."""
        return os.path.join(APN_STATE_DIR, f"wwan{self.interface_number}.json")

    def _persist_connected_apn(self, apn: dict) -> None:
        """Write the last-connected APN to disk so it survives reboots."""
        try:
            os.makedirs(APN_STATE_DIR, exist_ok=True)
            with open(self._apn_state_path(), 'w') as f:
                json.dump(apn, f)
        except Exception as e:
            logger.warning(f"Could not persist connected APN: {e}",
                          extra={'interface_number': self.interface_number})

    def _restore_connected_apn(self) -> dict | None:
        """Load the last-connected APN from disk (called once at startup)."""
        path = self._apn_state_path()
        try:
            if os.path.exists(path):
                with open(path) as f:
                    apn = json.load(f)
                if apn and apn.get('name'):
                    logger.info("Restored last-connected APN from disk",
                               extra={'interface_number': self.interface_number,
                                      'apn_name': apn.get('name', '')})
                    return apn
        except Exception as e:
            logger.warning(f"Could not restore persisted APN: {e}",
                          extra={'interface_number': self.interface_number})
        return None

    def _clear_persisted_apn(self) -> None:
        """Remove the persisted APN state file (called on SIM change)."""
        try:
            path = self._apn_state_path()
            if os.path.exists(path):
                os.remove(path)
                logger.debug("Cleared persisted APN after SIM change",
                            extra={'interface_number': self.interface_number})
        except Exception as e:
            logger.warning(f"Could not clear persisted APN: {e}",
                          extra={'interface_number': self.interface_number})

    # ── SIM failback mechanism ───────────────────────────────────────────────

    def _start_failback_monitor(self):
        """Start the periodic failback check if conditions are met.

        Conditions:
          1. Currently running on a non-primary SIM (derived from observed
             current_active_sim vs configured primary_sim_slot — NOT just
             the is_on_failover_sim bookkeeping flag, because modem-
             firmware-initiated failover after physical SIM removal causes
             a USB re-enumeration that bypasses _record_failover()).
          2. sim_failback_enabled is True in config
          3. No failback task already running
        """
        if not self.config:
            return
        if not self.config.get('sim_failback_enabled', True):
            logger.debug("SIM failback disabled in config",
                        extra={'interface_number': self.interface_number})
            return

        # Derive failover state from observed reality.  Physical slot
        # numbers are the only stable identifier across modem re-
        # enumeration — D-Bus modem indices and SIM object paths all
        # change on every SetPrimarySimSlot or SIM eject/insert event.
        primary = self.primary_sim_slot
        current = self.current_active_sim
        if primary is None or current is None:
            logger.debug("Cannot evaluate failback start — primary or current SIM unknown",
                        extra={'interface_number': self.interface_number,
                               'primary_sim': primary,
                               'current_sim': current})
            return
        if current == primary:
            # Already on primary — nothing to fail back to.  Sync
            # bookkeeping with observed reality: clear any stale
            # is_on_failover_sim flag and cancel any leftover monitor
            # task so we never run failback against ourselves.  This
            # handles paths where we land on primary by routes other
            # than _execute_failback() (e.g. SIM 2 ejected, SIM 1
            # reinserted, modem re-enumerates onto SIM 1 directly).
            if self.is_on_failover_sim:
                logger.info("Back on primary SIM — clearing failover state",
                           extra={'interface_number': self.interface_number,
                                  'primary_sim': primary,
                                  'current_sim': current})
                self.is_on_failover_sim = False
            # Clear failback suppression flags — they only meaningful
            # while running on a non-primary SIM.
            self.failback_suppressed_by_data_limit = False
            self._sticky_failover_timestamp = None
            self.failback_suppressed_by_connection_failure = False
            self._primary_first_seen_present_ts = None
            # Cancel any leftover monitor task from a previous failover
            # session so it doesn't run against the new (primary)
            # context.
            if self.failback_task and not self.failback_task.done():
                self.failback_task.cancel()
                self.failback_task = None
            return

        # We're on a non-primary SIM.  Make the flag reflect reality so
        # status reporting and downstream consumers are consistent,
        # regardless of how we got here (FSM-driven failover, modem-
        # firmware self-failover after SIM removal, or boot-time
        # mismatch).
        if not self.is_on_failover_sim:
            logger.info("Detected operation on non-primary SIM without recorded "
                        "failover (likely modem-initiated after SIM removal or "
                        "boot mismatch) — marking failover state for failback",
                        extra={'interface_number': self.interface_number,
                               'primary_sim': primary,
                               'current_sim': current})
            self.is_on_failover_sim = True

        # Suppress failback when sticky failover is active (data-limit triggered)
        # Note: we still start the monitor loop so it can detect when the
        # billing cycle resets and lift the suppression automatically.
        if self.failback_suppressed_by_data_limit:
            logger.info("SIM failback currently suppressed by data-limit sim-failover-sticky — "
                       "monitor will check for billing cycle reset",
                       extra={'interface_number': self.interface_number})

        # Don't start duplicate tasks
        if self.failback_task and not self.failback_task.done():
            logger.debug("Failback monitor already running",
                        extra={'interface_number': self.interface_number})
            return

        check_interval = self.config.get('sim_failback_check_interval', 600)
        logger.info("Starting SIM failback monitor",
                   extra={'interface_number': self.interface_number,
                          'primary_sim': self.primary_sim_slot,
                          'current_sim': self.current_active_sim,
                          'check_interval': check_interval})
        self.failback_task = self._safe_create_task(self._failback_monitor_loop())

    async def _failback_monitor_loop(self):
        """Periodically check if the primary SIM is available and switch back.

        Queries ModemManager SimSlots property to inspect the SIM object in the
        primary slot.  A SIM that exposes a valid IMSI/operator is considered
        available.  When it is, we initiate a controlled switch back.
        """
        check_interval = 600
        if self.config:
            check_interval = max(60, self.config.get('sim_failback_check_interval', 600))

        # Stability gate — primary SIM must be CONTINUOUSLY available for
        # this many seconds before failback fires.  Reuses the existing
        # sim_failback_stability_time config knob (default 300s).  Anti-flap:
        # if SIM 1 disappears at any point, the timestamp resets and the
        # gate restarts from zero.
        stability_time = 300
        if self.config:
            stability_time = max(0, int(self.config.get('sim_failback_stability_time', 300)))

        # Cooldown between successive failbacks — prevents rapid
        # failover↔failback ping-pong if the user keeps cycling the SIM
        # after a successful failback.  Reuses the carrier-friendly
        # failover_cooldown_seconds (default 600s).
        failback_cooldown = 600
        if self.config:
            failback_cooldown = max(0, int(self.config.get(
                'failover_cooldown_seconds', 600)))

        # Fine evaluation cadence — DECOUPLED from check_interval.  The
        # stability gate is wall-clock based, so it can only fire as
        # promptly as the loop wakes up; sleeping a full check_interval
        # (default 600s) between iterations rounded a 300s stability_time
        # up to the next poll, so failback took ~10 min instead of ~5.
        # The presence probe is a cheap local D-Bus SimSlots read (it
        # never touches the radio), so waking every ~30s — or faster if
        # the user deliberately set a shorter check_interval — is free and
        # lets the gate fire at stability_time (±poll_cadence) while
        # genuinely re-verifying continuous presence on every tick.
        poll_cadence = max(5, min(check_interval, 30))

        primary = self.primary_sim_slot
        if primary is None:
            logger.warning("Primary SIM slot unknown, cannot run failback monitor",
                          extra={'interface_number': self.interface_number})
            return

        logger.info("Failback monitor loop started",
                   extra={'interface_number': self.interface_number,
                          'primary_sim': primary,
                          'check_interval_seconds': check_interval,
                          'poll_cadence_seconds': poll_cadence,
                          'stability_time_seconds': stability_time,
                          'failback_cooldown_seconds': failback_cooldown})

        # First probe happens after a short settle so the SIM 2 connection
        # has a chance to stabilize and ModemManager has populated SimSlots
        # for the (possibly just re-enumerated) modem.  Subsequent
        # iterations wake on the fine poll_cadence.
        FIRST_CHECK_SETTLE_SECONDS = 30
        # Reset stability tracking on monitor start — every fresh
        # on-failover session begins with no observed primary presence.
        self._primary_first_seen_present_ts = None
        first_iteration = True

        while True:
            try:
                if first_iteration:
                    await asyncio.sleep(FIRST_CHECK_SETTLE_SECONDS)
                    first_iteration = False
                else:
                    await asyncio.sleep(poll_cadence)

                # Guard: stop if we're no longer on a failover SIM (e.g. user manually switched)
                if not self.is_on_failover_sim:
                    logger.info("No longer on failover SIM, stopping failback monitor",
                               extra={'interface_number': self.interface_number})
                    break

                # Suppress failback when primary SIM left due to connection failure
                # (wrong APN / parameters).  Only a new configuration event clears
                # this flag — there is no point switching back to known-bad config.
                if self.failback_suppressed_by_connection_failure:
                    logger.debug(
                        "Failback suppressed — primary SIM connection parameters "
                        "failed; waiting for new configuration before retrying",
                        extra={'interface_number': self.interface_number,
                               'primary_sim': primary})
                    continue

                # Check if sticky failover hold should be lifted (billing cycle crossed)
                if self.failback_suppressed_by_data_limit:
                    try:
                        now = datetime.datetime.now()
                        # Get billing date from the primary SIM's data config
                        sim_slots = self.config.get('sim_slots', []) if self.config else []
                        primary_cfg = next((s for s in sim_slots if s.get('slot') == primary), {})
                        billing_date = primary_cfg.get('data_limit_billing_date', 1)
                        # Use the timestamp when sticky was activated as the reference
                        sticky_set_time = getattr(self, '_sticky_failover_timestamp', None)
                        if sticky_set_time and self._billing_cycle_crossed(sticky_set_time, now, billing_date):
                            self.failback_suppressed_by_data_limit = False
                            self._sticky_failover_timestamp = None
                            logger.info("Billing cycle crossed — sim-failover-sticky hold lifted, "
                                       "failback may resume",
                                       extra={'interface_number': self.interface_number,
                                              'billing_date': billing_date})
                        else:
                            logger.debug("Sticky failover still active, skipping failback check",
                                        extra={'interface_number': self.interface_number})
                            continue
                    except Exception as e:
                        logger.debug(f"Could not check billing cycle for sticky hold: {e}",
                                    extra={'interface_number': self.interface_number})
                        continue

                # Guard: only check while connected
                current_state = self.machine.current_state
                if current_state != ModemState.CONNECTED.value:
                    logger.debug("Not in connected state, skipping failback check",
                                extra={'interface_number': self.interface_number,
                                       'state': current_state})
                    continue

                # Query the primary SIM slot status via ModemManager
                primary_available = await self._check_primary_sim_available(primary)

                now_ts = time.time()

                if not primary_available:
                    # Primary not present — reset the stability gate.  This
                    # is the anti-flap mechanism: every removal forces the
                    # continuous-presence counter back to zero.
                    if self._primary_first_seen_present_ts is not None:
                        logger.info("Primary SIM disappeared — resetting failback stability gate",
                                   extra={'interface_number': self.interface_number,
                                          'primary_sim': primary})
                        self._primary_first_seen_present_ts = None
                    logger.debug("Primary SIM not yet available, will check again",
                                extra={'interface_number': self.interface_number,
                                       'primary_sim': primary,
                                       'next_check_in': poll_cadence})
                    continue

                # Primary appears present.  Start (or continue) the
                # continuous-presence timer.
                if self._primary_first_seen_present_ts is None:
                    self._primary_first_seen_present_ts = now_ts
                    logger.info("Primary SIM detected — starting failback stability gate",
                               extra={'interface_number': self.interface_number,
                                      'primary_sim': primary,
                                      'required_seconds': stability_time})
                    continue

                continuous_present = now_ts - self._primary_first_seen_present_ts
                if continuous_present < stability_time:
                    logger.debug("Primary SIM present but stability gate not yet satisfied",
                                extra={'interface_number': self.interface_number,
                                       'primary_sim': primary,
                                       'continuous_present_seconds': int(continuous_present),
                                       'required_seconds': stability_time})
                    continue

                # Cooldown gate — refuse to failback if we just failed back
                # recently.  Protects against rapid failover↔failback
                # ping-pong when a user repeatedly cycles SIM 1.
                since_last_failback = now_ts - self._last_failback_time
                if (self._last_failback_time > 0
                        and since_last_failback < failback_cooldown):
                    logger.info("Failback cooldown active — deferring failback",
                               extra={'interface_number': self.interface_number,
                                      'primary_sim': primary,
                                      'seconds_since_last_failback': int(since_last_failback),
                                      'cooldown_seconds': failback_cooldown})
                    continue

                logger.info("Primary SIM stably available — initiating failback",
                           extra={'interface_number': self.interface_number,
                                  'primary_sim': primary,
                                  'current_sim': self.current_active_sim,
                                  'continuous_present_seconds': int(continuous_present)})
                self._last_failback_time = now_ts
                await self._execute_failback(primary)
                break  # Failback initiated, exit loop

            except asyncio.CancelledError:
                logger.info("Failback monitor cancelled",
                           extra={'interface_number': self.interface_number})
                break
            except Exception as e:
                logger.error(f"Failback monitor error: {e}",
                            extra={'interface_number': self.interface_number})
                # Continue monitoring despite errors
                await asyncio.sleep(poll_cadence)

    async def _probe_sim_slot_info(self, slot_number: int) -> dict:
        """Read whatever SIM identity is available from a specific slot's D-Bus object.

        For the active slot this returns full info (IMSI, ICCID, operator).
        For an inactive slot ModemManager may only expose ICCID or just confirm
        physical presence — the modem doesn't power the inactive slot.

        Returns a dict with whatever was readable, or empty dict on failure.
        """
        info = {}
        try:
            if not self.proxy:
                return info

            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
            sim_slots_variant = await props.call_get(MODEM_INTERFACE, "SimSlots")
            sim_slots = sim_slots_variant.value

            slot_index = slot_number - 1
            if slot_index < 0 or slot_index >= len(sim_slots):
                return info

            sim_path = sim_slots[slot_index]
            if not sim_path or sim_path == "/":
                info['present'] = False
                return info

            info['present'] = True

            introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, sim_path)
            sim_proxy = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, sim_path, introspect)
            sim_props = sim_proxy.get_interface("org.freedesktop.DBus.Properties")
            SIM_INTERFACE = "org.freedesktop.ModemManager1.Sim"

            for prop, key in [("Imsi", "imsi"), ("SimIdentifier", "iccid"),
                              ("OperatorName", "operator")]:
                try:
                    v = await sim_props.call_get(SIM_INTERFACE, prop)
                    val = v.value if v else ""
                    if val:
                        info[key] = val
                except Exception:
                    pass

            # Derive MCC/MNC from IMSI if available
            imsi = info.get('imsi', '')
            if imsi and len(imsi) >= 5:
                info['mcc_mnc'] = imsi[:6] if len(imsi) >= 6 and imsi[5].isdigit() else imsi[:5]

        except Exception as e:
            logger.debug(f"Could not probe SIM slot {slot_number}: {e}",
                        extra={'interface_number': self.interface_number})
        return info

    async def _check_primary_sim_available(self, primary_slot: int) -> bool:
        """Check if the primary SIM slot has a usable SIM card.

        Queries the ModemManager SimSlots property to get the D-Bus path of
        the SIM in the given slot.  Uses a three-tier detection strategy
        (IMSI → ICCID → D-Bus object existence) because non-active slots
        may not have IMSI/ICCID populated until the modem powers them.

        Returns True if the SIM appears present, False otherwise.
        """
        try:
            # GPIO-mux: SIM presence comes from the board SIM_DETECT lines,
            # not ModemManager — the modem exposes only the selected slot and
            # structurally cannot report whether the other slot is populated.
            if self.sim_controller.is_gpio_mux:
                return await self.sim_controller.is_present(primary_slot)

            if not self.proxy:
                return False

            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")

            # SimSlots is an array of object paths — one per physical slot
            sim_slots_variant = await props.call_get(MODEM_INTERFACE, "SimSlots")
            sim_slots = sim_slots_variant.value

            # Slot numbering: MM uses 1-based for PrimarySimSlot but SimSlots
            # is a 0-indexed array.
            slot_index = primary_slot - 1
            if slot_index < 0 or slot_index >= len(sim_slots):
                logger.debug("Primary slot index out of range",
                            extra={'interface_number': self.interface_number,
                                   'primary_slot': primary_slot,
                                   'total_slots': len(sim_slots)})
                return False

            sim_path = sim_slots[slot_index]

            # An empty or "/" path means no SIM in slot
            if not sim_path or sim_path == "/":
                return False

            # Introspect the SIM object to read its properties
            introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, sim_path)
            sim_proxy = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, sim_path, introspect)
            sim_props = sim_proxy.get_interface("org.freedesktop.DBus.Properties")

            SIM_INTERFACE = "org.freedesktop.ModemManager1.Sim"

            # Tier 1: IMSI — most reliable indicator
            try:
                imsi_variant = await sim_props.call_get(SIM_INTERFACE, "Imsi")
                imsi = imsi_variant.value if imsi_variant else ""
                if imsi:
                    logger.debug("Primary SIM IMSI read successfully",
                                extra={'interface_number': self.interface_number,
                                       'primary_slot': primary_slot,
                                       'imsi_prefix': imsi[:6] + '...' if len(imsi) > 6 else imsi})
                    return True
            except Exception:
                pass

            # Tier 2: ICCID (SimIdentifier) — may be available when IMSI is not
            try:
                iccid_variant = await sim_props.call_get(SIM_INTERFACE, "SimIdentifier")
                iccid = iccid_variant.value if iccid_variant else ""
                if iccid:
                    logger.debug("Primary SIM ICCID read (IMSI empty — non-active slot)",
                                extra={'interface_number': self.interface_number,
                                       'primary_slot': primary_slot})
                    return True
            except Exception:
                pass

            # Tier 3: D-Bus object exists — SIM is physically there but slot
            # is not powered, so no IMSI/ICCID yet.  Still counts as present.
            logger.debug("Primary SIM has D-Bus object but no IMSI/ICCID "
                        "(non-active slot not yet powered) — treating as available",
                        extra={'interface_number': self.interface_number,
                               'primary_slot': primary_slot,
                               'sim_path': sim_path})
            return True

        except Exception as e:
            logger.debug(f"Could not query primary SIM status: {e}",
                        extra={'interface_number': self.interface_number,
                               'primary_slot': primary_slot})
            return False

    async def _execute_failback(self, primary_slot: int):
        """Switch back to the primary SIM from the failover SIM.

        This follows the same SIM switch chain as a regular failover but with
        a specific reason marker so logs and events are distinguishable.
        """
        try:
            # Cancel failback task reference so it won't be restarted
            self.failback_task = None

            # Cancel monitoring tasks that will be restarted after reconnection
            if self.usage_monitor_task and not self.usage_monitor_task.done():
                self.usage_monitor_task.cancel()
                self.usage_monitor_task = None
            if hasattr(self, 'connectivity_monitor_task') and self.connectivity_monitor_task:
                self.connectivity_monitor_task.cancel()
                self.connectivity_monitor_task = None

            logger.info("Executing SIM failback to primary",
                       extra={'interface_number': self.interface_number,
                              'from_sim': self.current_active_sim,
                              'to_sim': primary_slot})

            self.sim_switch_reason = 'failback_to_primary'
            self.target_sim_slot = primary_slot
            self.previous_sim_slot = self.current_active_sim

            # Emit event for observability
            self._emit_failover_event(
                event_type='failback',
                from_sim=self.current_active_sim,
                to_sim=primary_slot,
                reason='primary_sim_available',
                trigger='_execute_failback')

            # Clear failover flag — if the switch succeeds we're back on primary;
            # if it fails, _sim_switch_cleanup will rollback and we'll stay on
            # the failover SIM (the flag will be re-evaluated).
            self.is_on_failover_sim = False

            self.transition(ModemEvent.SWITCH_SIM)
            await self._execute_sim_switch()

            logger.info("SIM failback initiated successfully",
                       extra={'interface_number': self.interface_number,
                              'target_sim': primary_slot})

        except Exception as e:
            logger.error(f"SIM failback failed: {e}",
                        extra={'interface_number': self.interface_number,
                               'primary_slot': primary_slot})
            # Restore failover flag since we couldn't switch back
            self.is_on_failover_sim = True
            # Don't transition — we're still connected on failover SIM,
            # the failback monitor will try again on next interval
            self._start_failback_monitor()

    # ── Failover event notification ──────────────────────────────────────────

    def _emit_failover_event(self, event_type: str, from_sim: int, to_sim: int,
                              reason: str, trigger: str, extra_data: dict = None):
        """Write a structured failover event to the per-interface event log.

        Events are stored in /var/lib/vyos/wwan/wwan{N}_events.json as an
        array of objects.  The file is capped at 100 events to prevent
        unbounded growth.  Survives reboots and service restarts.

        Args:
            event_type: 'failover', 'failback', 'data_limit_failover', etc.
            from_sim: SIM slot we are switching from.
            to_sim: SIM slot we are switching to.
            reason: Human-readable reason (e.g. 'sim_missing', 'connectivity_failure').
            trigger: Code path that triggered the event.
            extra_data: Optional dict of additional context.
        """
        event = {
            'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
            'event_type': event_type,
            'interface': self.interface_number,
            'from_sim': from_sim,
            'to_sim': to_sim,
            'reason': reason,
            'trigger': trigger,
            'failover_count': self.failover_count,
        }
        if extra_data:
            event['extra'] = extra_data

        event_file = f'/var/lib/vyos/wwan/wwan{self.interface_number}_events.json'

        try:
            os.makedirs('/var/lib/vyos/wwan', exist_ok=True)

            # Load existing events
            events = []
            if os.path.exists(event_file):
                try:
                    with open(event_file, 'r') as f:
                        events = json.load(f)
                except (json.JSONDecodeError, IOError):
                    events = []

            events.append(event)

            # Cap at 100 most recent events
            if len(events) > 100:
                events = events[-100:]

            with open(event_file, 'w') as f:
                json.dump(events, f, indent=2)

            logger.info(f"Failover event recorded: {event_type}",
                       extra={'interface_number': self.interface_number,
                              'event_type': event_type,
                              'from_sim': from_sim,
                              'to_sim': to_sim,
                              'reason': reason})

        except Exception as e:
            # Event logging should never break the main flow
            logger.warning(f"Failed to write failover event: {e}",
                          extra={'interface_number': self.interface_number})

    async def _sim_switch_cleanup(self, original_sim: int):
        """Emergency cleanup: re-enable modem on original SIM after a failed switch.

        This prevents leaving the modem in a disabled state with no connectivity.
        """
        try:
            logger.warning("SIM switch cleanup: attempting to restore original SIM",
                          extra={'interface_number': self.interface_number,
                                 'original_sim': original_sim})

            # If proxy is gone (modem disappeared during switch), try to rescan first
            if not self.proxy:
                logger.info("Proxy is None during cleanup — attempting to rescan for modem",
                           extra={'interface_number': self.interface_number})
                try:
                    await self._rescan_after_sim_switch()
                except Exception as rescan_e:
                    logger.error(f"Could not find modem for cleanup: {rescan_e}",
                                extra={'interface_number': self.interface_number})
                    return  # Nothing we can do without a proxy

            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")

            # Try to set back to original SIM using the SetPrimarySimSlot method
            try:
                if self.sim_controller.is_gpio_mux:
                    # GPIO-mux: restore the mux to the original slot (this
                    # also reboots the modem to re-enumerate that SIM).
                    await self.sim_controller.switch_to(original_sim)
                else:
                    iface = self.proxy.get_interface(MODEM_INTERFACE)
                    await iface.call_set_primary_sim_slot(original_sim)
                await asyncio.sleep(3)
                logger.info("Restored original SIM slot",
                           extra={'interface_number': self.interface_number,
                                  'restored_sim': original_sim})
            except Exception as e:
                logger.warning(f"Could not restore original SIM slot: {e}",
                              extra={'interface_number': self.interface_number})

            # Re-enable modem regardless of which SIM is active
            try:
                iface = self.proxy.get_interface(MODEM_INTERFACE)
                await iface.call_enable(True)

                max_wait = 30
                wait_time = 0
                while wait_time < max_wait:
                    await asyncio.sleep(2)
                    wait_time += 2
                    state_variant = await props.call_get(MODEM_INTERFACE, "State")
                    state = state_variant.value
                    if state >= 6:  # ENABLED or higher
                        logger.info("Modem re-enabled during cleanup",
                                   extra={'interface_number': self.interface_number})
                        break

                # Update tracking
                actual_sim_variant = await props.call_get(MODEM_INTERFACE, "PrimarySimSlot")
                self.current_active_sim = actual_sim_variant.value
                logger.info("SIM switch cleanup completed",
                           extra={'interface_number': self.interface_number,
                                  'active_sim': self.current_active_sim})

            except Exception as e:
                logger.error(f"Could not re-enable modem during cleanup: {e}",
                            extra={'interface_number': self.interface_number})

        except Exception as e:
            logger.error(f"SIM switch cleanup failed entirely: {e}",
                        extra={'interface_number': self.interface_number})

    async def _handle_failed_state_event(self, mm_state):
        """Handle ModemManager FAILED/UNKNOWN state transition.

        When the modem reports state -1 (FAILED) the generic
        ``CONNECTION_FAILED`` path is insufficient because it does not look
        at *why* the modem failed.  The most common cause in field
        deployments is that the active SIM was physically removed (e.g.
        SIM1 pulled while running) — the modem then sits in
        ``state=failed reason=sim-missing`` and never connects on SIM2
        unless we explicitly trigger SIM failover.

        Strategy:
          * Read ``StateFailedReason`` from the Modem D-Bus interface.
          * For ``sim-missing`` (2) or ``sim-error`` (3): route through
            ``_handle_sim_missing_failover`` so the FSM switches to the
            alternate slot.
          * Otherwise: fall back to the original CONNECTION_FAILED
            transition (only meaningful when the FSM was actively
            configuring/connecting/connected).
        """
        try:
            failed_reason = 0
            if self.proxy:
                try:
                    props = self.proxy.get_interface(
                        "org.freedesktop.DBus.Properties")
                    sfr_v = await props.call_get(
                        MODEM_INTERFACE, "StateFailedReason")
                    failed_reason = sfr_v.value if hasattr(sfr_v, 'value') else sfr_v
                except Exception as e:
                    logger.debug(
                        f"Could not read StateFailedReason: {e}",
                        extra={'interface_number': self.interface_number})

            reason_name = {
                0: 'none', 1: 'unknown', 2: 'sim-missing', 3: 'sim-error',
            }.get(failed_reason, f'unknown({failed_reason})')

            # Debounce duplicate investigations of the same FAILED reason.
            # At startup both _configure_modem_initial() Step 0a and the
            # synthesized _dispatch_initial_modem_state() event can land here
            # for the very same pre-existing FAILED condition; without this
            # guard the reason investigation and SIM-failover attempt run
            # (and log) twice. A short window is safe — repeating failover
            # within seconds adds nothing when it already concluded.
            now = time.time()
            if (self._last_failed_investigation_reason == failed_reason
                    and (now - self._last_failed_investigation_ts) < 10.0):
                logger.debug(
                    "Skipping duplicate FAILED-state investigation "
                    "(same reason within debounce window)",
                    extra={'interface_number': self.interface_number,
                           'failed_reason': failed_reason,
                           'failed_reason_name': reason_name})
                return
            self._last_failed_investigation_ts = now
            self._last_failed_investigation_reason = failed_reason

            logger.warning(
                "Modem FAILED state — investigating reason",
                extra={'interface_number': self.interface_number,
                       'mm_state': mm_state,
                       'failed_reason': failed_reason,
                       'failed_reason_name': reason_name})

            # GPIO-mux: the modem does NOT reliably report sim-missing — it
            # just fails generically when the active SIM is pulled.  So
            # StateFailedReason is demoted to a hint and SIM_DETECT is the
            # authority: if the active slot's SIM is gone (or an alternate is
            # present), treat it as a SIM problem and route to failover;
            # otherwise fall through to the normal connection-failure path.
            if self.sim_controller.is_gpio_mux:
                active = (self.current_active_sim
                          or (self.config or {}).get('primary_sim_slot', 1))
                active_present = await self.sim_controller.is_present(active)
                present = await self.sim_controller.present_slots()
                alternate_present = any(s != active for s in present)
                if (not active_present) or alternate_present:
                    logger.warning(
                        "Modem FAILED and SIM_DETECT indicates a SIM problem "
                        "(GPIO-mux) — triggering SIM failover",
                        extra={'interface_number': self.interface_number,
                               'active_slot': active,
                               'active_present': active_present,
                               'present_slots': sorted(present)})
                    self._cancel_failed_retry()
                    self.transition(ModemEvent.SIM_MISSING)
                    await self._handle_sim_missing_failover()
                    return
                # Active SIM still present and no alternate — a genuine
                # (non-SIM) connection failure; preserve normal recovery.
                current_fsm_state = self.machine.current_state
                if current_fsm_state in [ModemState.CONFIGURING.value,
                                         ModemState.CONNECTING.value,
                                         ModemState.CONNECTED.value,
                                         ModemState.USAGE_MONITORING.value]:
                    self.transition(ModemEvent.CONNECTION_FAILED)
                return

            # sim-missing (2) or sim-error (3) → route through SIM failover.
            # The active SIM tray is empty (or unreadable) but the modem
            # still reports it as the active slot, so failover must be
            # triggered explicitly to swap to the alternate slot.
            if failed_reason in (2, 3):
                logger.warning(
                    "Modem FAILED with SIM-related reason — "
                    "triggering SIM failover",
                    extra={'interface_number': self.interface_number,
                           'failed_reason_name': reason_name})
                self._cancel_failed_retry()  # SIM event supersedes retry
                self.transition(ModemEvent.SIM_MISSING)
                await self._handle_sim_missing_failover()
                return

            # Non-SIM failure during an active operation — preserve the
            # original behaviour so the existing failed-retry loop kicks in.
            current_fsm_state = self.machine.current_state
            if current_fsm_state in [ModemState.CONFIGURING.value,
                                     ModemState.CONNECTING.value,
                                     ModemState.CONNECTED.value,
                                     ModemState.USAGE_MONITORING.value]:
                self.transition(ModemEvent.CONNECTION_FAILED)

        except Exception as e:
            logger.error(
                f"Failed-state event handler error: {e}",
                extra={'interface_number': self.interface_number})

    async def _handle_locked_state_detection(self):
        """Distinguish between PIN-locked SIM and physically missing SIM.

        MM state 2 (LOCKED) can mean either:
        - SIM is present but needs PIN/PUK unlock
        - SIM is physically missing

        Check the UnlockRequired property to determine which case we're in.
        """
        try:
            # Skip during SIM switch or active failover
            if self._sim_switch_in_progress or self._sim_failover_in_progress:
                logger.debug("Locked-state detection skipped — SIM switch/failover in progress",
                            extra={'interface_number': self.interface_number})
                return

            if not self.proxy:
                self.transition(ModemEvent.SIM_MISSING)
                self._safe_create_task(self._handle_sim_missing_failover())
                return

            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")

            # Check what type of lock is required
            try:
                unlock_variant = await props.call_get(MODEM_INTERFACE, "UnlockRequired")
                unlock_required = unlock_variant.value
            except Exception:
                unlock_required = 0  # Unknown, fall through to missing SIM handling

            # ModemManager UnlockRequired values:
            # 0 = MM_MODEM_LOCK_UNKNOWN
            # 1 = MM_MODEM_LOCK_NONE
            # 2 = MM_MODEM_LOCK_SIM_PIN
            # 3 = MM_MODEM_LOCK_SIM_PIN2
            # 4 = MM_MODEM_LOCK_SIM_PUK
            # 5 = MM_MODEM_LOCK_SIM_PUK2

            if unlock_required in [2, 3, 4, 5]:  # PIN or PUK required
                logger.info("SIM is present but locked (PIN/PUK required)",
                           extra={'interface_number': self.interface_number,
                                  'unlock_required': unlock_required})
                # Route to PIN unlock flow, NOT failover
                self.transition(ModemEvent.SIM_LOCKED)
                return

            # Check if SIM is physically present by inspecting SimSlots
            try:
                sim_path_variant = await props.call_get(MODEM_INTERFACE, "Sim")
                sim_path = sim_path_variant.value if hasattr(sim_path_variant, 'value') else sim_path_variant

                if sim_path and sim_path != '/':
                    # SIM is present but locked for an unknown reason
                    logger.info("SIM present but in locked state (unknown lock type)",
                               extra={'interface_number': self.interface_number,
                                      'sim_path': sim_path,
                                      'unlock_required': unlock_required})
                    self.transition(ModemEvent.SIM_LOCKED)
                    return
            except Exception:
                pass

            # No SIM detected - this is a genuine missing SIM
            logger.warning("SIM physically missing (LOCKED state with no SIM path)",
                          extra={'interface_number': self.interface_number,
                                 'unlock_required': unlock_required})
            self.transition(ModemEvent.SIM_MISSING)
            self._safe_create_task(self._handle_sim_missing_failover())

        except Exception as e:
            logger.error(f"Failed to detect lock type: {e}",
                        extra={'interface_number': self.interface_number})
            # Fallback to missing SIM handling
            self.transition(ModemEvent.SIM_MISSING)
            self._safe_create_task(self._handle_sim_missing_failover())

    async def _execute_sim_switch(self):
        """Execute the complete SIM switch process with rollback on failure"""
        # Save original SIM for potential rollback
        self.previous_sim_slot = self.current_active_sim

        # Set the flag BEFORE we start — this tells on_modem_removed to
        # stay out of the way when the modem disappears during the switch
        self._sim_switch_in_progress = True

        try:
            logger.info("Starting SIM switch process",
                       extra={'interface_number': self.interface_number,
                              'target_sim': self.target_sim_slot,
                              'original_sim': self.previous_sim_slot,
                              'current_state': self.machine.current_state})

            # Step 1: Disconnect if connected
            if self.bearer_path:
                await self._sim_switch_disconnect()
            else:
                # Skip disconnect, go straight to disable
                self.transition(ModemEvent.SIM_DISCONNECTED)
                await self._sim_switch_disable()

        except Exception as e:
            logger.error(f"SIM switch process failed: {e}",
                        extra={'interface_number': self.interface_number,
                               'target_sim': self.target_sim_slot,
                               'original_sim': self.previous_sim_slot})
            # Attempt to restore modem to working state on original SIM
            if self.previous_sim_slot is not None:
                await self._sim_switch_cleanup(self.previous_sim_slot)
            self.transition(ModemEvent.CONNECTION_FAILED)
        finally:
            # Always clear the flag when the switch process ends
            self._sim_switch_in_progress = False

    async def _sim_switch_disconnect(self):
        """Step 1: Disconnect from network for SIM switch"""
        try:
            logger.info("Disconnecting for SIM switch",
                       extra={'interface_number': self.interface_number,
                              'bearer_path': self.bearer_path})

            # Fold the outgoing SIM's in-flight session usage into its persisted
            # total before we tear the bearer down, so a short-lived session
            # (e.g. a quick failover) is not lost.
            await self._flush_active_usage('sim_switch')

            if self.bearer_path and self.proxy:
                simple_iface = self.proxy.get_interface(SIMPLE_INTERFACE)
                await simple_iface.call_disconnect(self.bearer_path)
                self.bearer_path = None

                logger.info("Disconnected for SIM switch",
                           extra={'interface_number': self.interface_number})

            # Transition to next step
            self.transition(ModemEvent.SIM_DISCONNECTED)
            await self._sim_switch_disable()

        except Exception as e:
            logger.error(f"Failed to disconnect for SIM switch: {e}",
                        extra={'interface_number': self.interface_number})
            raise

    async def _sim_switch_disable(self):
        """Step 2: Disable modem for SIM switch - with enhanced recovery"""
        max_attempts = 2

        # --- retry loop covers ONLY the disable step ---
        # SIM_DISABLED and _sim_switch_hardware() are fired ONCE outside the
        # loop.  Keeping hardware-switch inside the retry caused SIM_DISABLED
        # to be fired a second time on attempt 1 while the FSM was already in
        # SIM_ENABLING (advanced by attempt 0's SIM_SWITCHED transition),
        # which has no sim_disabled handler → "Can not transition" error.
        for attempt in range(max_attempts):
            try:
                # Use escalating timeouts: 30s, 60s
                timeout = 30 + (30 * attempt)
                await self._try_disable_modem_once(timeout)
                break  # disable succeeded — exit retry loop

            except Exception as e:
                logger.warning(f"Modem disable attempt {attempt + 1} failed: {e}",
                              extra={'interface_number': self.interface_number,
                                     'attempt': attempt + 1,
                                     'max_attempts': max_attempts})

                if attempt < max_attempts - 1:
                    # Try hardware reset before next attempt (with cooldown protection)
                    if self._is_reset_allowed():
                        logger.info("Attempting hardware reset before retry",
                                   extra={'interface_number': self.interface_number})
                        try:
                            await modem_reset(self.interface_number)
                            self._record_reset()
                            await asyncio.sleep(30)  # Increased wait time for modem boot

                            # Re-scan for modem after reset
                            await self._rescan_after_reset()
                        except Exception as reset_e:
                            logger.error(f"Hardware reset failed: {reset_e}",
                                        extra={'interface_number': self.interface_number})
                    else:
                        logger.warning("Skipping hardware reset due to cooldown",
                                     extra={'interface_number': self.interface_number})

                    await asyncio.sleep(10)  # Brief pause before retry
                else:
                    # All attempts failed
                    logger.error("All modem disable attempts failed",
                                extra={'interface_number': self.interface_number})
                    raise

        # Transition and hardware switch happen exactly once, after disable succeeds
        self.transition(ModemEvent.SIM_DISABLED)
        await self._sim_switch_hardware()

    async def _handle_sim_missing_failover(self):
        """Handle SIM missing by attempting failover to available SIM.

        Thin wrapper retained for the many call sites that react to a
        missing/locked/FAILED SIM. Delegates to the shared, reason-aware
        executor below.
        """
        return await self._failover_to_alternate_sim(
            'sim_missing', '_handle_sim_missing_failover')

    def _on_sim_detect_event(self, slot: int, present: bool):
        """Scheduled (thread-safe) on a debounced GPIO SIM_DETECT edge.

        Called via ``loop.call_soon_threadsafe`` from the GPIO-mux detect
        watcher thread, so it runs on the FSM's asyncio loop.  The presence
        model is already updated by the watcher; this only decides whether
        any action is warranted.

        Policy (GPIO-mux):
          * REMOVED — record only.  We do NOT proactively act: the modem
            tears the network down in its own orderly way and we evaluate
            failover once it actually reaches FAILED.
          * INSERTED — a SIM became active in the live path or a primary
            returned; hand off to the async insertion handler.
        """
        try:
            if not self.sim_controller.is_gpio_mux:
                return
            if not present:
                logger.info("SIM_DETECT removed — recorded; waiting for modem "
                            "to fail gracefully before evaluating failover",
                            extra={'interface_number': self.interface_number,
                                   'slot': slot})
                return
            self._safe_create_task(
                self._handle_sim_detect_insertion(slot),
                name='sim_detect_insertion')
        except Exception as e:
            logger.error(f"SIM_DETECT event handler error: {e}",
                        extra={'interface_number': self.interface_number,
                               'slot': slot})

    async def _handle_sim_detect_insertion(self, slot: int):
        """React to a SIM being inserted (GPIO-mux), per the design model.

        Reboot is only ever issued for a SIM *becoming active*:
          * insertion into the currently-selected slot while parked
            (FAILED / waiting) — reboot so the modem enumerates it;
          * primary returns while on the failover SIM — hand to the
            failback monitor (controlled switch with stability gate);
          * otherwise — availability is recorded for the failover executor;
            no immediate action.
        """
        try:
            if self._sim_switch_in_progress or self._sim_failover_in_progress:
                logger.debug("SIM_DETECT insertion ignored — switch/failover in progress",
                            extra={'interface_number': self.interface_number,
                                   'slot': slot})
                return

            selected = (self.current_active_sim
                        or (self.config or {}).get('primary_sim_slot', 1))
            primary = self.primary_sim_slot or (
                self.config or {}).get('primary_sim_slot', 1)
            state = self.machine.current_state

            # Primary SIM returned while running on the failover SIM — let the
            # failback monitor perform the controlled switch (it honors the
            # stability gate + cooldown and reads GPIO presence).
            if self.is_on_failover_sim and slot == primary and slot != selected:
                logger.info("SIM_DETECT: primary SIM returned — starting failback monitor",
                           extra={'interface_number': self.interface_number,
                                  'slot': slot, 'selected': selected})
                self._start_failback_monitor()
                return

            # Insertion into the slot the modem is wired to, while parked.  The
            # modem cannot detect the SIM on its own, so reboot to enumerate.
            if slot == selected and state in (ModemState.FAILED.value,
                                              ModemState.WAITING_FOR_SIM.value):
                if not self._is_reset_allowed():
                    logger.info("SIM_DETECT: selected-slot SIM inserted but reset "
                               "blocked by cooldown — will retry on next event/poll",
                               extra={'interface_number': self.interface_number,
                                      'slot': slot})
                    return
                logger.info("SIM_DETECT: SIM inserted into selected slot while parked "
                           "— rebooting modem to enumerate it",
                           extra={'interface_number': self.interface_number,
                                  'slot': slot, 'state': state})
                self._cancel_failed_retry()
                ok = await modem_reset(self.interface_number)
                self._record_reset()
                if not ok:
                    logger.warning("SIM_DETECT: modem reboot after insertion found "
                                  "no working reset method",
                                  extra={'interface_number': self.interface_number,
                                         'slot': slot})
                return

            # Alternate slot became populated while the active SIM is gone —
            # attempt failover (the executor re-checks GPIO presence + gating).
            if slot != selected and state == ModemState.FAILED.value:
                if not await self.sim_controller.is_present(selected):
                    logger.info("SIM_DETECT: alternate SIM inserted while active "
                               "absent — attempting failover",
                               extra={'interface_number': self.interface_number,
                                      'slot': slot, 'selected': selected})
                    await self._handle_sim_missing_failover()
                    return

            logger.debug("SIM_DETECT insertion recorded — no immediate action",
                        extra={'interface_number': self.interface_number,
                               'slot': slot, 'selected': selected, 'state': state})
        except Exception as e:
            logger.error(f"SIM_DETECT insertion handler error: {e}",
                        extra={'interface_number': self.interface_number,
                               'slot': slot})

    async def _handle_signal_loss_failover(self):
        """Fail over to the alternate SIM after sustained weak signal.

        Triggered by ``_monitor_signal_strength`` once the active SIM's
        signal stays below the configured ``sim sim-failover
        signal-threshold`` (metric-aware: RSRP for LTE/5G, RSSI for 2G/3G)
        continuously for ``sim-failover signal-loss-timer`` seconds.

        Reuses the same alternate-SIM discovery, cooldown/backoff gating
        and switch primitive as the missing-SIM path; the only differences
        are the recorded reason and observability metadata.
        """
        return await self._failover_to_alternate_sim(
            'signal_loss', '_handle_signal_loss_failover')

    async def _failover_to_alternate_sim(self, reason: str, trigger: str, *,
                                         switch_reason: str = None,
                                         event_type: str = None,
                                         extra_data: dict = None,
                                         pre_switch_event=None,
                                         suppress_failback: bool = False,
                                         disconnect_reason_override: str = None):
        """Reentrancy-guarded wrapper around the SIM failover executor.

        Protected by _sim_failover_lock to prevent multiple concurrent failover
        attempts when the SIM tray is rapidly pushed in and out.  If a failover
        or SIM switch is already running, additional calls are silently skipped.

        Keyword arguments let the various failover triggers (roaming mismatch,
        initial-connection failure, recovery exhaustion, connectivity
        escalation, registration flap, ...) reuse the single race-safe,
        slot-probing executor while preserving their distinct observability and
        FSM side effects:

            switch_reason            override for ``self.sim_switch_reason``
                                     (defaults to ``automatic_failover_<reason>``)
            event_type               override for the emitted event type
                                     (defaults to ``failover`` / ``data_limit_failover``)
            extra_data               extra context merged into the event payload
            pre_switch_event         ModemEvent transitioned before SWITCH_SIM
                                     (e.g. CONNECTION_FAILED when the FSM is not
                                     in a state from which SWITCH_SIM is valid)
            suppress_failback        set ``failback_suppressed_by_connection_failure``
                                     so we do not bounce back to a known-bad primary
            disconnect_reason_override  stamp ``self._disconnect_reason_override``
                                     consumed by the DISCONNECT handler
        """
        try:
            # ── Reentrancy guard ─────────────────────────────────────────
            if self._sim_failover_in_progress or self._sim_switch_in_progress:
                logger.info("SIM failover skipped — already in progress",
                           extra={'interface_number': self.interface_number,
                                  'reason': reason,
                                  'failover_in_progress': self._sim_failover_in_progress,
                                  'switch_in_progress': self._sim_switch_in_progress})
                return False

            if self._sim_failover_lock.locked():
                logger.info("SIM failover skipped — lock held by another task",
                           extra={'interface_number': self.interface_number,
                                  'reason': reason})
                return False

            async with self._sim_failover_lock:
                self._sim_failover_in_progress = True
                try:
                    return await self._failover_to_alternate_sim_locked(
                        reason, trigger,
                        switch_reason=switch_reason,
                        event_type=event_type,
                        extra_data=extra_data,
                        pre_switch_event=pre_switch_event,
                        suppress_failback=suppress_failback,
                        disconnect_reason_override=disconnect_reason_override)
                finally:
                    self._sim_failover_in_progress = False

        except Exception as e:
            logger.error(f"SIM failover attempt failed (outer): {e}",
                        extra={'interface_number': self.interface_number,
                               'reason': reason})
            return False

    async def _failover_to_alternate_sim_locked(self, reason: str, trigger: str, *,
                                                switch_reason: str = None,
                                                event_type: str = None,
                                                extra_data: dict = None,
                                                pre_switch_event=None,
                                                suppress_failback: bool = False,
                                                disconnect_reason_override: str = None):
        """Inner implementation of SIM failover — always called under _sim_failover_lock."""
        try:
            if not self.config:
                return False

            # Proxy may have disappeared between the guard check and lock acquisition
            if not self.proxy:
                logger.warning("Proxy gone before SIM failover could query SIM slots",
                              extra={'interface_number': self.interface_number})
                return False

            # Honor a standing user disconnect.  In connect-on-demand /
            # dial-on-demand, automatic SIM failover (sim-missing, signal
            # loss, ...) must not silently bring a SIM back up and reconnect
            # while the operator has explicitly disconnected — we must stay
            # down until an explicit connect.  A connect always clears
            # user_disconnected *before* dispatching, so connect-initiated
            # failover (e.g. "connect while the active SIM is gone") still
            # passes this gate and proceeds to the alternate SIM.
            if self.user_disconnected and self.connection_mode in (
                    'connect-on-demand', 'dial-on-demand'):
                logger.info(
                    "SIM failover suppressed — user disconnect active (on-demand); "
                    "staying down until an explicit connect",
                    extra={'interface_number': self.interface_number,
                           'reason': reason,
                           'connection_mode': self.connection_mode})
                return False

            # Check if failover is enabled for the active SIM
            if not self._is_sim_failover_enabled():
                logger.info("SIM failover disabled for active slot, waiting for configured SIM",
                           extra={'interface_number': self.interface_number,
                                  'config_sim': self.config_active_sim})
                return False

            # Check failover cooldown to prevent ping-pong between SIMs
            if not self._is_failover_allowed():
                logger.warning("SIM failover blocked by cooldown/backoff, waiting",
                              extra={'interface_number': self.interface_number,
                                     'reason': reason,
                                     'failover_count': self.failover_count,
                                     'last_failover_time': self.last_failover_time})
                return False

            # Anchor on the SIM actually in use (current_active_sim), not just
            # the configured primary.  This is what makes "switch away from the
            # SIM we're on" correct for every trigger — including a failover
            # fired while already running on the backup SIM (e.g. weak signal
            # or data-limit on the backup).  Falls back to the configured slot
            # before the first successful registration sets current_active_sim.
            from_sim = self.current_active_sim or self.config_active_sim

            logger.info("Attempting SIM failover",
                       extra={'interface_number': self.interface_number,
                              'reason': reason,
                              'active_sim': from_sim})

            # Check what SIMs are available
            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
            sim_slots_variant = await props.call_get(MODEM_INTERFACE, "SimSlots")
            sim_slots = sim_slots_variant.value  # Extract array from Variant

            available_sims = []
            if self.sim_controller.is_gpio_mux:
                # GPIO-mux: ModemManager only sees the selected slot, so the
                # alternate-SIM set comes from the SIM_DETECT presence model.
                available_sims = sorted(await self.sim_controller.present_slots())
            else:
                for slot_num, slot_path in enumerate(sim_slots, 1):
                    if slot_path and slot_path != '/':  # Valid SIM present
                        try:
                            # Test if SIM is responsive
                            sim_introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, slot_path)
                            sim_proxy = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, slot_path, sim_introspect)
                            sim_props = sim_proxy.get_interface("org.freedesktop.DBus.Properties")

                            sim_interface = "org.freedesktop.ModemManager1.Sim"

                            # Try IMSI first (most reliable indicator)
                            try:
                                imsi_variant = await sim_props.call_get(sim_interface, "Imsi")
                                imsi = imsi_variant.value
                                if imsi:
                                    available_sims.append(slot_num)
                                    continue
                            except Exception:
                                pass

                            # IMSI may be empty for non-active slots — check SimIdentifier (ICCID)
                            try:
                                iccid_variant = await sim_props.call_get(sim_interface, "SimIdentifier")
                                iccid = iccid_variant.value
                                if iccid:
                                    available_sims.append(slot_num)
                                    continue
                            except Exception:
                                pass

                            # SIM object exists on D-Bus but has no IMSI/ICCID — still
                            # treat it as available (non-active slot may not be powered)
                            logger.info(f"SIM in slot {slot_num} has D-Bus object but no IMSI/ICCID "
                                       f"(non-active slot not yet powered) — treating as available",
                                       extra={'interface_number': self.interface_number,
                                              'slot': slot_num,
                                              'sim_path': slot_path})
                            available_sims.append(slot_num)

                        except Exception:
                            continue  # SIM not available

            logger.info("Available SIMs detected",
                       extra={'interface_number': self.interface_number,
                              'available_sims': available_sims,
                              'active_sim': from_sim})

            # Find alternative SIM
            fallback_sim = None
            for sim_num in available_sims:
                if sim_num != from_sim:
                    fallback_sim = sim_num
                    break

            if fallback_sim and not self._is_target_sim_enabled(fallback_sim):
                logger.warning(
                    f"SIM failover target slot {fallback_sim} is disabled in config — "
                    "not failing over",
                    extra={'interface_number': self.interface_number,
                           'target_sim': fallback_sim})
                return False

            if fallback_sim:
                logger.warning("Performing automatic SIM failover",
                              extra={'interface_number': self.interface_number,
                                     'from_sim': from_sim,
                                     'to_sim': fallback_sim,
                                     'reason': reason})

                # Set failover reason and target.  Callers may override the
                # recorded switch reason so the existing per-trigger status
                # strings (roaming_not_allowed, connectivity_failure_escalation,
                # ...) are preserved verbatim in op-mode status output.
                self.sim_switch_reason = switch_reason or f'automatic_failover_{reason}'
                self.target_sim_slot = fallback_sim

                # Optional per-trigger FSM side effects: suppress failback to a
                # known-bad primary, and/or stamp the disconnect reason that the
                # DISCONNECT handler consumes.
                if suppress_failback:
                    self.failback_suppressed_by_connection_failure = True
                if disconnect_reason_override:
                    self._disconnect_reason_override = disconnect_reason_override

                # Record the failover for cooldown tracking
                self._record_failover()

                # Emit event for observability — keep the dedicated
                # data-limit/registration-flap event types so telemetry stays
                # distinct.  Always include the probed available-SIM list.
                event_extra = {'available_sims': available_sims}
                if extra_data:
                    event_extra.update(extra_data)
                self._emit_failover_event(
                    event_type=(event_type
                                or ('data_limit_failover'
                                    if reason == 'data_limit' else 'failover')),
                    from_sim=from_sim,
                    to_sim=fallback_sim,
                    reason=reason,
                    trigger=trigger,
                    extra_data=event_extra)

                # Some callers (initial-configuration failures) are not in a
                # state from which SWITCH_SIM is valid; let them inject an
                # intermediate transition (e.g. CONNECTION_FAILED) first.
                if pre_switch_event is not None:
                    self.transition(pre_switch_event)

                # Start SIM switch process
                self.transition(ModemEvent.SWITCH_SIM)
                await self._execute_sim_switch()
                return True

            else:
                logger.warning("No alternative SIM available for failover",
                            extra={'interface_number': self.interface_number,
                                   'reason': reason,
                                   'active_sim': from_sim,
                                   'available_sims': available_sims})
                return False

        except Exception as e:
            logger.error(f"SIM failover attempt failed: {e}",
                        extra={'interface_number': self.interface_number,
                               'reason': reason})
            return False

    async def _handle_locked_state(self):
        """Handle LOCKED state by distinguishing between missing SIM and locked SIM"""
        try:
            if not self.proxy or not self.config:
                return

            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
            sim_slots_variant = await props.call_get(MODEM_INTERFACE, "SimSlots")
            sim_slots = sim_slots_variant.value  # Extract array from Variant
            config_sim_slot = self.config.get('primary_sim_slot', 1)

            # Check if configured SIM slot has a SIM
            if len(sim_slots) >= config_sim_slot:
                slot_path = sim_slots[config_sim_slot - 1]  # Convert to 0-based index

                if slot_path and slot_path != '/':  # SIM is present, just locked
                    logger.info("SIM is present but locked, attempting unlock",
                               extra={'interface_number': self.interface_number,
                                      'sim_slot': config_sim_slot})
                    # SIM is present but locked - attempt unlock instead of failover
                    self.transition(ModemEvent.SIM_LOCKED)
                    return

            # No SIM in configured slot - treat as missing
            logger.info("SIM actually missing from configured slot",
                       extra={'interface_number': self.interface_number,
                              'sim_slot': config_sim_slot})
            self.transition(ModemEvent.SIM_MISSING)
            self._safe_create_task(self._handle_sim_missing_failover())

        except Exception as e:
            logger.error(f"Failed to handle locked state: {e}",
                        extra={'interface_number': self.interface_number})
            # Fallback to missing SIM handling
            self.transition(ModemEvent.SIM_MISSING)
            self._safe_create_task(self._handle_sim_missing_failover())

    async def _check_sim_insertion(self):
        """Check if a SIM was inserted in the configured slot"""
        try:
            # Skip during SIM switch or active failover
            if self._sim_switch_in_progress or self._sim_failover_in_progress:
                logger.debug("SIM insertion check skipped — SIM switch/failover in progress",
                            extra={'interface_number': self.interface_number})
                return False

            # GPIO-mux: presence comes from the SIM_DETECT model.  If the
            # configured slot now reports a SIM, resume the normal
            # configuration lane (the detect watcher drives instant events;
            # this polling path is the periodic safety net).
            if self.sim_controller.is_gpio_mux:
                if not self.config:
                    return False
                config_sim_slot = self.config.get('primary_sim_slot', 1)
                if await self.sim_controller.is_present(config_sim_slot):
                    self._cancel_failed_retry()
                    return await self._resume_after_sim_available()
                return False

            if not self.proxy or not self.config:
                return

            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
            sim_slots_variant = await props.call_get(MODEM_INTERFACE, "SimSlots")
            sim_slots = sim_slots_variant.value  # Extract array from Variant
            config_sim_slot = self.config.get('primary_sim_slot', 1)

            # Check if configured SIM slot now has a SIM
            if len(sim_slots) >= config_sim_slot:
                slot_path = sim_slots[config_sim_slot - 1]  # Convert to 0-based index

                if slot_path and slot_path != '/':  # Valid SIM present
                    try:
                        # Test if SIM is responsive
                        sim_introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, slot_path)
                        sim_proxy = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, slot_path, sim_introspect)
                        sim_props = sim_proxy.get_interface("org.freedesktop.DBus.Properties")

                        sim_interface = "org.freedesktop.ModemManager1.Sim"
                        imsi_variant = await sim_props.call_get(sim_interface, "Imsi")
                        imsi = imsi_variant.value

                        if imsi:  # SIM is present and readable
                            # Only treat this as a real SIM insertion event
                            # when the SIM identity has actually changed
                            # since the last time we observed it. Without
                            # this gate, MM's normal `searching -> enabled`
                            # carrier-search oscillation (which happens
                            # continuously when registration is impossible,
                            # e.g. SIM requires an unsupported band) is
                            # repeatedly misread as a hot-swap, tearing
                            # down a perfectly fine modem and cancelling
                            # the carrier-friendly failed-retry backoff.
                            last_imsi = ''
                            if isinstance(self.last_known_sim_info, dict):
                                last_imsi = self.last_known_sim_info.get('imsi', '') or ''

                            if last_imsi and last_imsi == imsi:
                                logger.debug(
                                    "Modem enabled but SIM identity unchanged "
                                    "- not a hot-swap, leaving failed-retry intact",
                                    extra={'interface_number': self.interface_number,
                                           'sim_slot': config_sim_slot})
                                return False

                            logger.info("SIM insertion detected in configured slot",
                                       extra={'interface_number': self.interface_number,
                                              'sim_slot': config_sim_slot,
                                              'imsi': imsi[:6] + '...',  # Partial IMSI for privacy
                                              'previous_imsi_known': bool(last_imsi)})

                            # Confirmed SIM identity change — now it is
                            # safe to supersede the failed-retry backoff
                            # and resume the configuration lane.
                            self._cancel_failed_retry()

                            # SIM is back! Resume the normal configuration/connection lane.
                            return await self._resume_after_sim_available()

                    except Exception as e:
                        logger.debug(f"SIM slot {config_sim_slot} not ready: {e}",
                                    extra={'interface_number': self.interface_number})

            return False

        except Exception as e:
            logger.error(f"Error checking SIM insertion: {e}",
                        extra={'interface_number': self.interface_number})
            return False

    async def _resume_after_sim_available(self):
        """Resume the normal configuration flow once a SIM becomes available.

        This is the explicit recovery path for the boot-with-no-SIM case.
        It re-enters the CONFIGURING lane using the same FSM events used by
        startup/recovery, then hands control back to _configure_modem_initial()
        so the existing connection cascade can complete normally.
        """
        try:
            if self._sim_switch_in_progress or self._sim_failover_in_progress:
                logger.debug("SIM resume skipped — SIM switch/failover in progress",
                            extra={'interface_number': self.interface_number})
                return False

            if not self.proxy or not self.config:
                logger.warning("Cannot resume configuration after SIM availability — missing proxy or config",
                              extra={'interface_number': self.interface_number,
                                     'has_proxy': bool(self.proxy),
                                     'has_config': bool(self.config)})
                return False

            # SIM appearance supersedes any stale retry / failover loops.
            self._cancel_failed_retry()

            current_state = self.machine.current_state
            logger.info("Resuming configuration after SIM availability",
                       extra={'interface_number': self.interface_number,
                              'current_state': current_state})

            # The FSM rules already map WAITING_FOR_SIM → CONFIGURING on SIM_READY,
            # and FAILED → CONFIGURING on SIM_READY. Use that explicit event so the
            # later connection flow re-enters the normal configuration lane.
            if current_state in (ModemState.WAITING_FOR_SIM.value,
                                 ModemState.FAILED.value):
                self.transition(ModemEvent.SIM_READY)

            # If the state machine did not land in CONFIGURING, do not force the
            # connection cascade — log and let the caller retry on the next poll.
            if self.machine.current_state != ModemState.CONFIGURING.value:
                logger.warning("SIM resume did not reach CONFIGURING state",
                              extra={'interface_number': self.interface_number,
                                     'current_state': self.machine.current_state,
                                     'previous_state': current_state})
                return False

            await self._configure_modem_initial()
            return True

        except Exception as e:
            logger.error(f"Error resuming after SIM availability: {e}",
                        extra={'interface_number': self.interface_number})
            return False

    async def _handle_potential_sim_insertion(self):
        """Handle potential SIM insertion when modem becomes enabled"""
        try:
            # Skip during SIM switch or active failover
            if self._sim_switch_in_progress or self._sim_failover_in_progress:
                logger.debug("SIM insertion handling skipped — SIM switch/failover in progress",
                            extra={'interface_number': self.interface_number})
                return

            # Wait a moment for SIM to fully initialize
            await asyncio.sleep(3)

            # Check if we now have the configured SIM
            sim_inserted = await self._check_sim_insertion()

            if not sim_inserted:
                # `_check_sim_insertion` returns False for two very
                # different reasons:
                #   (a) the configured slot really has no SIM, OR
                #   (b) the SIM identity is unchanged since the last
                #       observation (i.e. this is just MM's normal
                #       `searching -> enabled` carrier-search
                #       oscillation, not a hot-swap).
                # Only case (a) warrants triggering SIM failover —
                # case (b) should be a quiet no-op so the existing
                # carrier-friendly failed-retry backoff is not
                # repeatedly disturbed.
                if await self._is_configured_sim_present():
                    logger.debug(
                        "SIM still present in configured slot - "
                        "no failover needed (search-loop oscillation)",
                        extra={'interface_number': self.interface_number})
                    return

                # Still no configured SIM - check for any available SIM
                if self._is_sim_failover_enabled():
                    logger.info("No configured SIM found, checking for failover options",
                               extra={'interface_number': self.interface_number})
                    await self._handle_sim_missing_failover()
                else:
                    logger.info("No configured SIM found and sim-failover disabled for active slot",
                               extra={'interface_number': self.interface_number})

        except Exception as e:
            logger.error(f"Error handling potential SIM insertion: {e}",
                        extra={'interface_number': self.interface_number})

    async def _is_configured_sim_present(self) -> bool:
        """Return True if a SIM is currently present in the configured slot.

        Used by ``_handle_potential_sim_insertion`` to distinguish a real
        "SIM removed" condition from MM's normal `searching <-> enabled`
        oscillation on an unregisterable carrier (e.g. band mismatch).
        """
        try:
            # GPIO-mux: answer from the SIM_DETECT presence model.
            if self.sim_controller.is_gpio_mux:
                slot = (self.config or {}).get('primary_sim_slot', 1)
                return await self.sim_controller.is_present(slot)
            if not self.proxy or not self.config:
                return False
            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
            sim_slots_variant = await props.call_get(MODEM_INTERFACE, "SimSlots")
            sim_slots = sim_slots_variant.value
            config_sim_slot = self.config.get('primary_sim_slot', 1)
            if len(sim_slots) < config_sim_slot:
                return False
            slot_path = sim_slots[config_sim_slot - 1]
            return bool(slot_path and slot_path != '/')
        except Exception as e:
            logger.debug(f"Could not check configured SIM presence: {e}",
                        extra={'interface_number': self.interface_number})
            return False

    async def _periodic_sim_check(self):
        """Periodic check for SIM insertion while in WAITING_FOR_SIM state"""
        while self.machine.current_state == ModemState.WAITING_FOR_SIM.value:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds

                if self.machine.current_state != ModemState.WAITING_FOR_SIM.value:
                    break  # State changed, exit loop

                logger.debug("Periodic SIM check while waiting",
                            extra={'interface_number': self.interface_number})

                sim_found = await self._check_sim_insertion()
                if sim_found:
                    break  # SIM found and handled

            except Exception as e:
                logger.debug(f"Periodic SIM check error: {e}",
                            extra={'interface_number': self.interface_number})

        logger.debug("Periodic SIM check ended",
                    extra={'interface_number': self.interface_number,
                           'final_state': self.machine.current_state})

    async def _try_disable_modem_once(self, timeout_seconds):
        """Single attempt to disable modem with specified timeout"""
        logger.info(f"Disabling modem for SIM switch (timeout: {timeout_seconds}s)",
                   extra={'interface_number': self.interface_number})

        props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
        state_variant = await props.call_get(MODEM_INTERFACE, "State")
        state = state_variant.value

        if state > 3:  # If not already disabled
            iface = self.proxy.get_interface(MODEM_INTERFACE)
            await iface.call_enable(False)

            # Wait for modem to be disabled with specified timeout
            wait_time = 0
            while wait_time < timeout_seconds:
                await asyncio.sleep(2)
                wait_time += 2
                state_variant = await props.call_get(MODEM_INTERFACE, "State")
                state = state_variant.value
                if state <= 3:  # DISABLED or lower
                    logger.info(f"Modem disabled for SIM switch after {wait_time}s",
                               extra={'interface_number': self.interface_number})
                    return

            raise Exception(f"Timeout waiting for modem to disable ({timeout_seconds}s)")
        else:
            logger.info("Modem already disabled",
                       extra={'interface_number': self.interface_number,
                              'modem_state': state})

    async def _rescan_after_reset(self):
        """Re-scan for modem after hardware reset with proper patience"""
        logger.info("Re-scanning for modem after hardware reset",
                   extra={'interface_number': self.interface_number})

        # Clear current proxy since modem may have changed paths
        self.proxy = None
        self.modem_path = None

        # Wait for modem hardware to initialize - modems need time!
        await asyncio.sleep(15)

        # Re-scan using same logic as initial scan with patience
        target_modem_id = f"modem{self.interface_number}"

        try:
            # Try multiple times with increasing delays - modems can take 2+ minutes to boot
            max_attempts = 24  # 24 attempts over ~2 minutes

            for attempt in range(1, max_attempts + 1):
                try:
                    msg = Message(
                        destination=MODEM_MANAGER_SERVICE,
                        path=MODEM_MANAGER_PATH,
                        interface=OBJECT_MANAGER_INTERFACE,
                        member="GetManagedObjects"
                    )
                    reply = await self.bus.call(msg)

                    if reply.message_type.name == "METHOD_RETURN":
                        managed_objects = reply.body[0]
                        paths = [
                            path for path, interfaces in managed_objects.items()
                            if MODEM_INTERFACE in interfaces
                        ]

                        for path in paths:
                            try:
                                introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, path)
                                proxy = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, path, introspect)
                                props = proxy.get_interface("org.freedesktop.DBus.Properties")

                                device_variant = await props.call_get(MODEM_INTERFACE, "Device")
                                physdev_uid = device_variant.value  # Extract string from Variant

                                if physdev_uid == target_modem_id:
                                    self.proxy = proxy
                                    self.modem_path = path

                                    # Set proxy for connection manager
                                    self.connection_manager.set_proxy(proxy)

                                    # Enable signal monitoring for accurate dBm readings
                                    await self._enable_signal_monitoring()

                                    logger.info("Modem re-found after reset",
                                               extra={'interface_number': self.interface_number,
                                                      'modem_path': path,
                                                      'physdev_uid': physdev_uid,
                                                      'attempts': attempt})
                                    return

                            except Exception:
                                continue

                    # Not found yet, wait before next attempt (if not last attempt)
                    if attempt < max_attempts:
                        wait_time = min(5 + (attempt * 0.5), 10)  # 5-10 seconds between attempts
                        logger.debug(f"Modem not found after reset, attempt {attempt}/{max_attempts}, waiting {wait_time}s",
                                   extra={'interface_number': self.interface_number})
                        await asyncio.sleep(wait_time)

                except Exception as e:
                    logger.debug(f"D-Bus error during rescan attempt {attempt}: {e}",
                               extra={'interface_number': self.interface_number})
                    if attempt < max_attempts:
                        await asyncio.sleep(5)

            raise Exception("Modem not found after reset - exhausted all attempts")

        except Exception as e:
            logger.error(f"Failed to re-scan for modem after reset: {e}",
                        extra={'interface_number': self.interface_number})
            raise

    async def _sim_switch_hardware(self):
        """Step 3: Perform actual SIM slot switch.

        On Telit LN920 (and similar modems), calling SetPrimarySimSlot causes
        the modem to reset and temporarily disappear from D-Bus.  The
        on_modem_removed handler is suppressed via _sim_switch_in_progress,
        so we must rescan for the modem ourselves after the hardware switch.
        """
        try:
            logger.info("Switching SIM slot hardware",
                       extra={'interface_number': self.interface_number,
                              'target_sim': self.target_sim_slot})

            # GPIO-mux: drive the external SIM mux and reboot the modem so it
            # re-reads the now-selected slot.  ModemManager's
            # SetPrimarySimSlot does not apply (only one SIM interface is
            # exposed to the modem).  The reboot is the only one issued for a
            # SIM becoming active.
            if self.sim_controller.is_gpio_mux:
                await self.sim_controller.switch_to(self.target_sim_slot)
            else:
                # Set the primary SIM slot using the SetPrimarySimSlot method
                # (not the property setter, which is read-only on some modems like Telit LN920)
                iface = self.proxy.get_interface(MODEM_INTERFACE)
                await iface.call_set_primary_sim_slot(self.target_sim_slot)

            # The modem will likely disappear from D-Bus now (USB re-enumeration).
            # Wait for it to come back by rescanning.  The on_modem_removed handler
            # has already cleared self.proxy for us if the signal fired.
            logger.info("SIM slot command sent — waiting for modem to re-appear",
                       extra={'interface_number': self.interface_number,
                              'target_sim': self.target_sim_slot})

            # Wait for modem re-enumeration then rescan
            await self._rescan_after_sim_switch()

            logger.info("SIM slot hardware switch completed — modem back on D-Bus",
                       extra={'interface_number': self.interface_number,
                              'target_sim': self.target_sim_slot,
                              'new_modem_path': self.modem_path})

            # Transition to enable step
            self.transition(ModemEvent.SIM_SWITCHED)
            await self._sim_switch_enable()

        except Exception as e:
            logger.error(f"Failed to switch SIM hardware: {e}",
                        extra={'interface_number': self.interface_number})
            # Attempt cleanup on hardware switch failure
            if self.previous_sim_slot is not None:
                await self._sim_switch_cleanup(self.previous_sim_slot)
            raise

    async def _rescan_after_sim_switch(self):
        """Wait for modem to reappear after a SIM slot switch.

        Shorter initial wait than _rescan_after_reset because the modem
        just needs to re-enumerate on USB, not do a full cold boot.
        """
        logger.info("Waiting for modem to reappear after SIM switch",
                   extra={'interface_number': self.interface_number})

        # The proxy is already None (cleared by on_modem_removed or us)
        self.proxy = None
        self.modem_path = None

        # Initial wait for USB re-enumeration (typically 5-15s for Telit LN920)
        await asyncio.sleep(5)

        target_modem_id = f"modem{self.interface_number}"
        max_attempts = 30  # Up to ~60 seconds total
        for attempt in range(1, max_attempts + 1):
            try:
                msg = Message(
                    destination=MODEM_MANAGER_SERVICE,
                    path=MODEM_MANAGER_PATH,
                    interface=OBJECT_MANAGER_INTERFACE,
                    member="GetManagedObjects"
                )
                reply = await self.bus.call(msg)

                if reply.message_type.name == "METHOD_RETURN":
                    managed_objects = reply.body[0]
                    paths = [
                        path for path, interfaces in managed_objects.items()
                        if MODEM_INTERFACE in interfaces
                    ]

                    for path in paths:
                        try:
                            introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, path)
                            proxy = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, path, introspect)
                            props = proxy.get_interface("org.freedesktop.DBus.Properties")

                            device_variant = await props.call_get(MODEM_INTERFACE, "Device")
                            physdev_uid = device_variant.value

                            if physdev_uid == target_modem_id:
                                self.proxy = proxy
                                self.modem_path = path
                                self.connection_manager.set_proxy(proxy)

                                # Re-enable signal monitoring
                                await self._enable_signal_monitoring()

                                # Re-register PropertiesChanged handler on the new proxy
                                try:
                                    new_props_iface = proxy.get_interface("org.freedesktop.DBus.Properties")
                                    new_props_iface.on_properties_changed(self._dispatch_properties_changed)
                                except Exception as sig_e:
                                    logger.warning(f"Could not re-register signal handlers after SIM switch: {sig_e}",
                                                  extra={'interface_number': self.interface_number})

                                logger.info("Modem re-found after SIM switch",
                                           extra={'interface_number': self.interface_number,
                                                  'modem_path': path,
                                                  'attempts': attempt})
                                return

                        except Exception:
                            continue

            except Exception as e:
                logger.debug(f"D-Bus error during SIM switch rescan attempt {attempt}: {e}",
                           extra={'interface_number': self.interface_number})

            if attempt < max_attempts:
                await asyncio.sleep(2)

        raise Exception("Modem not found after SIM switch - exhausted all attempts")

    async def _sim_switch_enable(self):
        """Step 4: Re-enable modem after SIM switch"""
        try:
            logger.info("Re-enabling modem after SIM switch",
                       extra={'interface_number': self.interface_number})

            iface = self.proxy.get_interface(MODEM_INTERFACE)
            await iface.call_enable(True)

            # Wait for modem to be enabled
            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
            max_wait = 30
            wait_time = 0
            while wait_time < max_wait:
                await asyncio.sleep(2)
                wait_time += 2
                state_variant = await props.call_get(MODEM_INTERFACE, "State")
                state = state_variant.value
                if state >= 6:  # ENABLED or higher
                    logger.info("Modem re-enabled after SIM switch",
                               extra={'interface_number': self.interface_number})
                    break
            else:
                raise Exception("Timeout waiting for modem to re-enable")

            # Verify SIM switch worked
            actual_sim_variant = await props.call_get(MODEM_INTERFACE, "PrimarySimSlot")
            actual_sim = actual_sim_variant.value
            self.current_active_sim = actual_sim

            if actual_sim == self.target_sim_slot:
                logger.info("SIM switch successful",
                           extra={'interface_number': self.interface_number,
                                  'new_sim': actual_sim,
                                  'reason': self.sim_switch_reason})
            else:
                logger.error("SIM switch verification failed - aborting reconfiguration",
                            extra={'interface_number': self.interface_number,
                                   'target_sim': self.target_sim_slot,
                                   'actual_sim': actual_sim})
                raise Exception(
                    f"SIM switch verification failed: expected slot {self.target_sim_slot}, "
                    f"got slot {actual_sim}"
                )

            # Transition to reconfiguration
            self.transition(ModemEvent.SIM_ENABLED)
            await self._sim_switch_reconfigure()

        except Exception as e:
            logger.error(f"Failed to re-enable modem after SIM switch: {e}",
                        extra={'interface_number': self.interface_number})
            # Attempt cleanup on enable failure
            if self.previous_sim_slot is not None:
                await self._sim_switch_cleanup(self.previous_sim_slot)
            raise

    async def _sim_switch_reconfigure(self):
        """Step 5: Reconfigure modem with new SIM settings"""
        try:
            logger.info("Reconfiguring modem with new SIM settings",
                       extra={'interface_number': self.interface_number,
                              'active_sim': self.current_active_sim})

            # Get the NEW SIM's configuration
            current_slot = self.current_active_sim
            sim_slots = self.config.get('sim_slots', [])
            new_sim_config = next((sim for sim in sim_slots if sim['slot'] == current_slot), {})

            logger.info("Using new SIM configuration",
                       extra={'interface_number': self.interface_number,
                              'sim_slot': current_slot,
                              'apn': new_sim_config.get('apn', ''),
                              'bands': new_sim_config.get('supported_bands', [])})

            # Reconfigure bands and network mode for new SIM
            await self._configure_supported_bands()
            await self._configure_network_mode()

            # Apply the NEW SIM's preferred-carrier / network-scan policy.
            # _configure_preferred_carrier anchors on the active slot, so the
            # failover SIM's own preferred carrier is honored.  When a
            # preferred carrier is configured it issues a direct
            # Modem3gpp.Register(MCCMNC) — which is itself the re-registration
            # kick for that case; when none is configured it returns early and
            # the automatic-registration nudge below does the kick instead.
            await self._configure_preferred_carrier()

            # Nudge the modem to (re)register on the NEW SIM.  After a SIM
            # switch the modem is ENABLED and we have just rewritten its
            # allowed-band / mode set, but some modems (e.g. Telit FN920) sit
            # idle instead of actively searching — the old SIM's registration
            # context is gone and nothing tells the modem to attach again.
            # Requesting automatic registration kicks off a fresh PLMN/cell
            # search with the new band set in effect so the new SIM actually
            # comes up instead of waiting out the registration timeout.  This is
            # a no-op when _configure_preferred_carrier already registered us.
            await self._force_network_reregistration('sim_switch')

            # SIM switch complete - transition back to normal configuration
            self.transition(ModemEvent.SIM_SWITCH_COMPLETE)

            # New SIM = fresh attempt counter — don't carry over failures from old SIM
            self.initial_connection_failure_count = 0

            logger.info("SIM switch process completed — now establishing connection on new SIM",
                       extra={'interface_number': self.interface_number,
                              'new_sim': self.current_active_sim,
                              'switch_reason': self.sim_switch_reason})

            # ── Establish connection on the new SIM ──────────────────────
            # Registration recovery is suppressed during SIM switch, so we
            # must explicitly connect and apply IP configuration here.
            # Wait briefly for the modem to settle after band reconfiguration
            await asyncio.sleep(3)

            # Safety: bail out if proxy disappeared (SIM yanked during reconfigure)
            if not self.proxy:
                logger.warning("Proxy lost during SIM reconfigure — cannot establish connection",
                              extra={'interface_number': self.interface_number})
                return

            # Check if bearer is already connected (unlikely now that reg recovery is suppressed
            # during SIM switch, but handle defensively)
            is_connected = await self._is_bearer_connected()
            if not is_connected:
                if not self.proxy:
                    logger.warning("Proxy lost before APN configuration",
                                  extra={'interface_number': self.interface_number})
                    return
                logger.info("Establishing connection on new SIM via APN configuration",
                           extra={'interface_number': self.interface_number})
                await self.apply_modem_configuration()

                # Verify connection was established
                await asyncio.sleep(2)
                is_connected = await self._is_bearer_connected()

            if is_connected:
                logger.info("Bearer connected on new SIM — applying IP configuration",
                           extra={'interface_number': self.interface_number})

                # Transition FSM to CONNECTED
                try:
                    if self.machine.current_state == ModemState.CONFIGURING.value:
                        self.transition(ModemEvent.CONNECT)
                    if self.machine.current_state == ModemState.CONNECTING.value:
                        self.transition(ModemEvent.CONNECTED)
                except Exception as trans_e:
                    logger.warning(f"FSM transition after SIM switch connection: {trans_e}",
                                 extra={'interface_number': self.interface_number,
                                        'current_state': self.machine.current_state})

                # Apply bearer IP configuration to the network interface
                await self._apply_bearer_ip_configuration()

                # Start network interface monitoring
                try:
                    if getattr(self, 'ensure_link_up_on_connect', True):
                        self._safe_create_task(self._ensure_interface_up())
                    self._safe_create_task(self._start_network_interface_monitoring())
                except RuntimeError:
                    pass

                # Reset failover counters — connection is stable on new SIM
                self._reset_failover_counters()
                # Close the bearer-downtime window opened when the old bearer
                # dropped for the switch, and count the slot change (reset-based
                # modems never emit a PrimarySimSlot PropertiesChanged signal).
                self._record_bearer_up('sim_switch')
                self._record_sim_switch(
                    self.previous_sim_slot,
                    self.current_active_sim,
                    self.sim_switch_reason or 'sim_switch')

                # Start connectivity monitoring if configured
                self._safe_create_task(self.start_connectivity_monitoring())

                # Start failback monitor if we're on the failover SIM
                self._start_failback_monitor()

                logger.info("SIM switch completed with active connection",
                           extra={'interface_number': self.interface_number,
                                  'new_sim': self.current_active_sim,
                                  'fsm_state': self.machine.current_state})
            else:
                logger.warning("Could not establish connection on new SIM after switch — "
                              "FSM will retry via event-driven handler",
                             extra={'interface_number': self.interface_number,
                                    'new_sim': self.current_active_sim})

        except Exception as e:
            logger.error(f"Failed to reconfigure after SIM switch: {e}",
                        extra={'interface_number': self.interface_number})
            raise

    @staticmethod
    def _band_array_to_ints(variant):
        """Normalize a ModemManager band-array property (``au``) to ``list[int]``.

        dbus-next returns the value of an ``au`` property as a plain list of
        Python ``int``, NOT a list of Variant objects.  The band code used to do
        ``[band.value for band in variant.value]`` which raises
        ``AttributeError: 'int' object has no attribute 'value'`` on every call —
        an error that was silently swallowed and mislabeled as "band
        configuration not supported by this modem", so the configured bands were
        NEVER actually written (a stale single-band lock survived SIM switches).

        This mirrors the defensive ``x.value if hasattr(x, 'value') else x``
        pattern already used by ``_configure_network_mode`` so both Variant-
        wrapped and plain-int elements are handled.
        """
        raw = variant.value if (variant is not None and hasattr(variant, 'value')) else (variant or [])
        out = []
        for b in raw or []:
            b = b.value if hasattr(b, 'value') else b
            try:
                out.append(int(b))
            except (TypeError, ValueError):
                continue
        return out

    async def _configure_supported_bands(self):
        """Configure supported bands.

        Per-SIM ``supported_bands`` accepts ``all`` or specific band names
        (e.g. eutran-7, ngran-78).  Technology-group keywords (2G, 3G, LTE, 5G)
        are ignored with a warning — use ``network-mode`` to control which
        radio technologies the modem hardware is allowed to use.

        The final band set is: per-SIM bands ∩ modem-supported bands.
        If per-SIM is ``all`` it is treated as "no restriction".
        """
        try:
            if not self.config:
                logger.info("No configuration available for band setup",
                           extra={'interface_number': self.interface_number})
                return

            # ── Read per-SIM band configuration ─────────────────────────
            # Use the slot that is ACTUALLY ACTIVE, not the configured primary.
            # After a SIM failover current_active_sim is the failover slot, and
            # we must apply THAT slot's bands — otherwise the primary's band
            # restriction (e.g. eutran-8) gets re-applied to the failover SIM,
            # locking it to a band it may not support and preventing it from
            # ever registering.  Falls back to primary_sim_slot during initial
            # configuration before current_active_sim is set.
            active_slot = self.current_active_sim or self.config.get('primary_sim_slot', 1)
            sim_slots = self.config.get('sim_slots', [])
            active_sim_config = next((sim for sim in sim_slots if sim['slot'] == active_slot), {})

            per_sim_bands_raw = active_sim_config.get('supported_bands', 'all')
            if isinstance(per_sim_bands_raw, str):
                per_sim_bands_cfg = [b.strip() for b in per_sim_bands_raw.split(',') if b.strip()]
            else:
                per_sim_bands_cfg = list(per_sim_bands_raw)

            logger.info("Configuring supported bands while disabled",
                       extra={'interface_number': self.interface_number,
                              'active_sim_slot': active_slot,
                              'per_sim_bands': per_sim_bands_cfg})

            # Get what bands the modem actually supports (MM returns numeric constants)
            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")

            try:
                # Get modem's supported bands (uint32 array)
                modem_supported_bands_variant = await props.call_get(MODEM_INTERFACE, "SupportedBands")
                modem_bands_list = self._band_array_to_ints(modem_supported_bands_variant)

                # Get currently enabled bands (uint32 array)
                current_bands_variant = await props.call_get(MODEM_INTERFACE, "CurrentBands")
                current_bands_list = self._band_array_to_ints(current_bands_variant)

                # Convert numeric constants back to human names for logging
                modem_band_names = [self._mm_constant_to_band_name(band) for band in modem_bands_list]
                current_band_names = [self._mm_constant_to_band_name(band) for band in current_bands_list]

                logger.info("Modem band capabilities",
                           extra={'interface_number': self.interface_number,
                                  'modem_supported_bands': modem_band_names,
                                  'modem_supported_constants': modem_bands_list,
                                  'current_enabled_bands': current_band_names,
                                  'current_enabled_constants': current_bands_list,
                                  'per_sim_bands': per_sim_bands_cfg})

                # ── Resolve per-SIM bands (specific bands only) ──────────
                per_sim_is_all = (per_sim_bands_cfg == ['all'] or not per_sim_bands_cfg)
                per_sim_band_constants = []

                if not per_sim_is_all:
                    per_sim_invalid = []
                    per_sim_tech_groups = []
                    for band_name in per_sim_bands_cfg:
                        mm_constant = self._band_name_to_mm_constant(band_name)
                        if mm_constant is not None:
                            per_sim_band_constants.append(mm_constant)
                        elif self._is_technology_group(band_name):
                            # Technology group in per-SIM config — warn and ignore
                            per_sim_tech_groups.append(band_name)
                        else:
                            per_sim_invalid.append(band_name)
                    if per_sim_tech_groups:
                        logger.warning("Technology groups (2G/3G/LTE/5G) are modem-level settings "
                                      "and cannot be set per-SIM — use 'network-mode' instead. "
                                      "These entries are ignored.",
                                      extra={'interface_number': self.interface_number,
                                             'ignored_groups': per_sim_tech_groups,
                                             'sim_slot': active_slot})
                    if per_sim_invalid:
                        logger.warning("Invalid per-SIM band names ignored",
                                      extra={'interface_number': self.interface_number,
                                             'invalid_bands': per_sim_invalid,
                                             'valid_formats': ['all', 'eutran-1', 'ngran-78', 'umts-1', 'gsm-850']})

                # ── Compute target = per-SIM ∩ modem ────────────────────
                # Capability source = SupportedBands ∪ CurrentBands.  Some QMI
                # modems (e.g. Telit FN920) report an INCOMPLETE SupportedBands
                # list while the band is plainly usable — any band currently
                # enabled (CurrentBands) is by definition supported, so folding
                # it in recovers bands MM's capability query dropped.  Without
                # this a configured band missing from SupportedBands yields an
                # empty intersection and (previously) silently enabled ALL bands.
                capability_bands = set(modem_bands_list) | set(current_bands_list)
                if per_sim_is_all:
                    # Per-SIM unrestricted — the modem must be free to scan
                    # EVERY band it supports.  Express this with
                    # MM_MODEM_BAND_ANY (0), the canonical "no restriction"
                    # sentinel that `mmcli --set-current-bands=any` sends,
                    # instead of enumerating SupportedBands.
                    #
                    # Why not enumerate: a QMI modem (e.g. Telit FN920) can
                    # report an INCOMPLETE SupportedBands list before it is
                    # fully registered.  If that truncated list happened to
                    # match the single band the modem is currently camped on,
                    # the enumerate-then-compare path below would treat a real,
                    # stale restriction — e.g. a previous SIM's eutran-8 lock
                    # carried over after a SIM switch to an unrestricted SIM —
                    # as "already correct" and skip the write, stranding the new
                    # SIM on the old band.  ANY clears the restriction
                    # regardless of what SupportedBands reports.
                    MM_MODEM_BAND_ANY = 0
                    current_set = set(current_bands_list)
                    supported_set = set(modem_bands_list)

                    # No restriction to clear when the modem already has every
                    # band it supports enabled.  Require >1 current band so a
                    # single camped band (the classic stale-lock signature) is
                    # never mistaken for "unrestricted".
                    already_unrestricted = (
                        len(current_set) > 1
                        and bool(supported_set)
                        and supported_set.issubset(current_set))
                    if already_unrestricted:
                        logger.info("Per-SIM bands are 'all' and no restriction "
                                    "is in effect — leaving bands unrestricted",
                                   extra={'interface_number': self.interface_number,
                                          'current_bands': current_band_names})
                        return

                    logger.info("Per-SIM bands are 'all' — clearing band "
                                "restriction (bands = ANY) so the modem can "
                                "scan every supported band",
                               extra={'interface_number': self.interface_number,
                                      'current_bands': current_band_names})

                    modem_iface = self.proxy.get_interface(MODEM_INTERFACE)
                    await modem_iface.call_set_current_bands([MM_MODEM_BAND_ANY])
                    await asyncio.sleep(3)

                    cleared_variant = await props.call_get(MODEM_INTERFACE, "CurrentBands")
                    cleared_list = self._band_array_to_ints(cleared_variant)
                    cleared_names = [self._mm_constant_to_band_name(b) for b in cleared_list]

                    # Success = the modem widened beyond the prior narrow set.
                    # Some QMI modems reject the ANY sentinel; if the band set
                    # did not widen, fall back to writing the explicit
                    # supported-band list (what the modem advertises).
                    if set(cleared_list) != current_set and len(cleared_list) >= len(current_set):
                        logger.info("Band restriction cleared — modem now unrestricted",
                                   extra={'interface_number': self.interface_number,
                                          'bands': cleared_names})
                        return

                    if modem_bands_list:
                        logger.info("ANY band sentinel not honored — falling "
                                    "back to explicit supported-band list",
                                   extra={'interface_number': self.interface_number,
                                          'supported_bands': modem_band_names})
                        await modem_iface.call_set_current_bands(modem_bands_list)
                        await asyncio.sleep(3)
                    return
                else:
                    # Per-SIM restricts to specific bands.
                    #
                    # Non-NR bands (LTE/UMTS/GSM) are written AS REQUESTED even
                    # when SupportedBands does not list them.  QMI modems (e.g.
                    # Telit FN920) report a TRUNCATED SupportedBands before the
                    # modem is fully registered, so intersecting with capability
                    # would silently drop bands that are actually usable — and,
                    # worse, if the surviving intersection collapsed to exactly
                    # the single band the modem is already camped on (e.g. a
                    # previous SIM's eutran-8 lock carried across a switch), the
                    # no-op equality skip below would misfire and strand this SIM
                    # on that stale single-band lock instead of widening to its
                    # own configured set.  The modem harmlessly rejects any band
                    # it genuinely cannot do, so requesting the full set is safe.
                    #
                    # NR/NGRAN bands still require advertisement: RedCap-only
                    # bands are not settable until registration, so an
                    # unadvertised NR band is dropped rather than written.
                    requested_non_ngran = [b for b in per_sim_band_constants if b < 301]
                    requested_ngran = [b for b in per_sim_band_constants if b >= 301]
                    modem_ngran = [b for b in capability_bands if b >= 301]
                    usable_ngran = [b for b in requested_ngran if b in capability_bands]

                    target_bands = requested_non_ngran + usable_ngran
                    target_band_names = [self._mm_constant_to_band_name(b) for b in target_bands]

                    # NR bands the modem doesn't advertise are dropped above.
                    if requested_ngran and not modem_ngran:
                        logger.info("Requested 5G NR bands are not advertised by the modem "
                                    "and will be ignored",
                                    extra={'interface_number': self.interface_number,
                                           'requested_ngran': [self._mm_constant_to_band_name(b) for b in requested_ngran]})

                    dropped_ngran = [b for b in requested_ngran if b not in capability_bands]
                    if dropped_ngran:
                        logger.warning("Requested NR bands not in modem capability — dropped from filter",
                                      extra={'interface_number': self.interface_number,
                                             'dropped_bands': [self._mm_constant_to_band_name(b) for b in dropped_ngran]})

                    logger.info("Applying per-SIM band restriction",
                               extra={'interface_number': self.interface_number,
                                      'requested_bands': [self._mm_constant_to_band_name(b) for b in per_sim_band_constants],
                                      'result_bands': target_band_names})

                # Empty intersection handling.  CRITICAL: when the operator
                # explicitly restricted bands we must NOT widen to "all bands"
                # — that lets the modem camp on any band (the very thing the
                # restriction forbids).  Instead honor the request as best
                # effort by writing the requested constants directly; the modem
                # rejects truly unsupported ones, but a band MM merely failed to
                # advertise will be accepted.  Only an 'all' selection (handled
                # above) ever enables every band.
                if not target_bands:
                    if per_sim_is_all:
                        logger.warning("Band intersection is empty — falling back to all modem-supported bands",
                                      extra={'interface_number': self.interface_number})
                        target_bands = modem_bands_list
                        target_band_names = modem_band_names
                    else:
                        logger.warning("No requested band intersects modem capability — "
                                      "writing the requested set as-is rather than enabling all bands",
                                      extra={'interface_number': self.interface_number,
                                             'requested_bands': [self._mm_constant_to_band_name(b) for b in per_sim_band_constants]})
                        target_bands = list(per_sim_band_constants)
                        target_band_names = [self._mm_constant_to_band_name(b) for b in target_bands]

                # Apply band configuration using MM numeric constants — but only
                # when the modem is not already on exactly this set.  Writing
                # CurrentBands can trigger a brief deregister/reattach on some
                # modems, so a redundant write is disruptive, not free.  Skip it
                # when it would be a no-op; NR enforcement below still runs.
                if set(current_bands_list) == set(target_bands):
                    logger.info("Bands already configured correctly — skipping CurrentBands write",
                               extra={'interface_number': self.interface_number,
                                      'enabled_bands': current_band_names})
                else:
                    logger.info("Setting new band configuration",
                               extra={'interface_number': self.interface_number,
                                      'from_bands': current_band_names,
                                      'to_bands': target_band_names,
                                      'from_constants': current_bands_list,
                                      'to_constants': target_bands})

                    # Set bands via the ModemManager SetCurrentBands METHOD
                    # (what `mmcli --set-current-bands` calls), NOT a property
                    # write.  CurrentBands is a READ-ONLY property — writing it
                    # through org.freedesktop.DBus.Properties.Set is silently
                    # ignored by ModemManager, so the restriction never took
                    # effect.  The method takes an `au` (array of uint32), i.e.
                    # a plain list of ints — no Variant wrapping.
                    modem_iface = self.proxy.get_interface(MODEM_INTERFACE)
                    await modem_iface.call_set_current_bands(target_bands)

                    # Brief wait for band configuration to take effect
                    await asyncio.sleep(3)

                    # Verify band configuration
                    new_bands_variant = await props.call_get(MODEM_INTERFACE, "CurrentBands")
                    new_bands_list = self._band_array_to_ints(new_bands_variant)
                    new_band_names = [self._mm_constant_to_band_name(band) for band in new_bands_list]

                    # Some QMI modems silently ignore the first restriction and
                    # leave the full band set enabled — retry the write once
                    # before giving up.
                    if set(new_bands_list) != set(target_bands):
                        logger.info("Band write not reflected — retrying SetCurrentBands once",
                                   extra={'interface_number': self.interface_number,
                                          'target_bands': target_band_names,
                                          'actual_bands': new_band_names})
                        await modem_iface.call_set_current_bands(target_bands)
                        await asyncio.sleep(3)
                        new_bands_variant = await props.call_get(MODEM_INTERFACE, "CurrentBands")
                        new_bands_list = self._band_array_to_ints(new_bands_variant)
                        new_band_names = [self._mm_constant_to_band_name(band) for band in new_bands_list]

                    if set(new_bands_list) == set(target_bands):
                        logger.info("Band configuration successful",
                                   extra={'interface_number': self.interface_number,
                                          'applied_bands': new_band_names,
                                          'applied_constants': new_bands_list})
                    else:
                        # The modem did not honor the restriction.  Flag loudly
                        # — the operator's band selection is NOT in effect and
                        # the modem may camp on an unconfigured band.
                        logger.warning("Band configuration NOT honored by modem — "
                                      "requested restriction is not in effect",
                                      extra={'interface_number': self.interface_number,
                                             'target_bands': target_band_names,
                                             'actual_bands': new_band_names,
                                             'target_constants': target_bands,
                                             'actual_constants': new_bands_list})
                        self._emit_alert(
                            alert_type='band_config_not_honored',
                            severity='warning',
                            message='Modem did not honor the configured band restriction',
                            requested_bands=target_band_names,
                            actual_bands=new_band_names,
                        )

            except Exception as band_e:
                # Band read/write failed.  This is logged LOUDLY with the
                # actual exception type+message in the visible text (not just
                # the extra dict) because a swallowed error here silently
                # leaves the modem on whatever bands it had — which is exactly
                # how a stale single-band lock survives a SIM switch.  Most
                # commonly this fires when SupportedBands/CurrentBands cannot be
                # read in the current modem power/enabled state.
                logger.warning(
                    f"Band configuration step failed ({type(band_e).__name__}: {band_e}) "
                    "— modem bands left unchanged",
                    extra={'interface_number': self.interface_number,
                           'error': str(band_e),
                           'error_type': type(band_e).__name__,
                           'per_sim_bands': per_sim_bands_cfg})

        except Exception as e:
            logger.error(f"Band configuration error: {e}",
                        extra={'interface_number': self.interface_number})
            # Don't fail the entire configuration for band issues
            logger.warning("Continuing configuration without band changes",
                          extra={'interface_number': self.interface_number})

    async def _configure_network_mode(self):
        """Configure network mode (access technology) on the modem.

        Capability-driven: ModemManager's ``SetCurrentModes`` only accepts an
        ``(allowed, preferred)`` tuple that appears verbatim in the modem's
        ``SupportedModes`` list, and that list differs on every modem.  So we
        never fabricate a bitmask.  Instead the CLI value expresses *intent*
        (which radio technologies the operator wants) and we pick the
        supported tuple that best matches:

          * ``auto``     → the widest supported tuple (all RATs the modem can do)
          * ``2g/3g``    → the tuple restricted to that RAT
          * ``lte``/``4g`` → the tuple restricted to 4G
          * ``5g``       → the tuple covering 5G (+4G anchor for NSA), preferring 5G

        Runs after the modem is enabled (SetCurrentModes, like SetCurrentBands,
        is backed by the QMI NAS service which is inactive while the modem is
        disabled).  Never raises — on any problem the modem keeps its prior mode.
        """
        try:
            if not self.config:
                return

            network_mode = self.config.get('network_mode', 'auto')
            mode_key = network_mode.lower().strip()

            # MMModemMode bits
            MODE_NONE = 0
            MODE_2G = 1 << 1
            MODE_3G = 1 << 2
            MODE_4G = 1 << 3
            MODE_5G = 1 << 4

            # CLI value → (desired RAT bitset, preferred bit).
            # desired=None means "auto" (use everything the modem supports).
            wanted_map = {
                'auto':    (None,              MODE_NONE),
                '2g':      (MODE_2G,           MODE_NONE),
                '3g':      (MODE_3G,           MODE_NONE),
                'lte':     (MODE_4G,           MODE_NONE),
                '4g':      (MODE_4G,           MODE_NONE),
                # 5G NR preferred, with the LTE anchor kept for NSA operation.
                '5g':      (MODE_5G | MODE_4G, MODE_5G),
                # True 5G standalone — NR only, no LTE anchor.  The
                # capability scorer picks a pure-NR supported tuple when the
                # modem advertises one; if it only supports NSA (NR+LTE) the
                # scorer falls back to the closest tuple and logs it.
                '5g-only': (MODE_5G,           MODE_5G),
            }
            if mode_key not in wanted_map:
                logger.warning("Unrecognised network_mode value, falling back to 'auto'",
                              extra={'interface_number': self.interface_number,
                                     'configured_mode': network_mode,
                                     'valid_modes': list(wanted_map.keys())})
                mode_key = 'auto'
            desired_bits, desired_pref = wanted_map[mode_key]

            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")

            # Read the modem's advertised SupportedModes — array of (uu).
            try:
                sm_variant = await props.call_get(MODEM_INTERFACE, "SupportedModes")
                sm_raw = sm_variant.value if sm_variant else []
            except Exception as e:
                logger.info("Modem does not expose SupportedModes — skipping network-mode",
                           extra={'interface_number': self.interface_number, 'error': str(e)})
                return

            supported = []
            for entry in sm_raw or []:
                try:
                    a, p = entry[0], entry[1]
                    a = a.value if hasattr(a, 'value') else a
                    p = p.value if hasattr(p, 'value') else p
                    supported.append((int(a), int(p)))
                except (TypeError, IndexError, ValueError):
                    continue

            if not supported:
                logger.info("Modem advertised no usable SupportedModes — leaving mode unchanged",
                           extra={'interface_number': self.interface_number})
                return

            # Union of every RAT the modem can do.
            all_bits = 0
            for a, _ in supported:
                all_bits |= a

            # `auto` = "the operator did not pick a technology, so enable them
            # all and let the modem/network decide".  Capture that intent
            # before we resolve the concrete bitset so the scorer can prefer a
            # genuine no-preference tuple.
            is_auto = desired_bits is None
            if is_auto:
                desired_bits = all_bits           # auto → all RATs
            desired_bits &= all_bits              # never ask for a RAT the modem lacks
            if desired_bits == 0:
                logger.warning("Requested network-mode RAT not supported by this modem — "
                              "leaving mode unchanged",
                              extra={'interface_number': self.interface_number,
                                     'configured_mode': network_mode,
                                     'modem_modes': [self._mode_mask_to_names(a) for a, _ in supported]})
                return

            def _popcount(x):
                return bin(x & 0xFFFFFFFF).count('1')

            # Score every supported tuple; lowest score wins.
            #   extra      : unwanted RATs the tuple enables (defeats a restriction)
            #   missing    : wanted RATs the tuple omits
            #   pref_ok    : 0 if it matches the desired preferred RAT, else 1
            #   auto_pref  : for `auto` only — prefer a *no-preference* tuple so
            #                "all technologies" really means "let the modem
            #                decide"; 0 if p==none, else 1.  Always 0 for an
            #                explicit value (its own pref_ok already governs).
            #   -width     : among ties, the widest (most RATs) tuple wins.
            #   -p         : final deterministic tie-break — when only
            #                preference-bearing tuples exist (e.g. a RedCap
            #                modem that always carries a preference), pick the
            #                one preferring the *highest* RAT (5G > 4G > …)
            #                rather than whatever the modem happened to list
            #                first.
            best = None
            best_score = None
            for a, p in supported:
                extra = _popcount(a & ~desired_bits)
                missing = _popcount(desired_bits & ~a)
                pref_ok = 0 if (desired_pref == MODE_NONE or (p & desired_pref)) else 1
                auto_pref = 1 if (is_auto and p != MODE_NONE) else 0
                score = (extra, missing, pref_ok, auto_pref, -_popcount(a), -int(p))
                if best_score is None or score < best_score:
                    best_score, best = score, (a, p)

            allowed, preferred = best

            logger.info("Selected network mode from modem-supported tuples",
                       extra={'interface_number': self.interface_number,
                              'network_mode': network_mode,
                              'chosen_allowed': self._mode_mask_to_names(allowed),
                              'chosen_preferred': self._mode_mask_to_names(preferred),
                              'supported': [
                                  (self._mode_mask_to_names(a), self._mode_mask_to_names(p))
                                  for a, p in supported]})

            try:
                # Skip the write if the modem is already in the chosen mode.
                current_modes_variant = await props.call_get(MODEM_INTERFACE, "CurrentModes")
                current_struct = current_modes_variant.value if current_modes_variant else None
                if current_struct and len(current_struct) >= 2:
                    cur_allowed = current_struct[0]
                    cur_preferred = current_struct[1]
                    if hasattr(cur_allowed, 'value'):
                        cur_allowed = cur_allowed.value
                    if hasattr(cur_preferred, 'value'):
                        cur_preferred = cur_preferred.value
                    if int(cur_allowed) == allowed and int(cur_preferred) == preferred:
                        logger.info("Network mode already configured correctly",
                                   extra={'interface_number': self.interface_number,
                                          'mode': network_mode})
                        return

                modem_iface = self.proxy.get_interface(MODEM_INTERFACE)
                await modem_iface.call_set_current_modes((allowed, preferred))
                await asyncio.sleep(2)

                logger.info("Network mode configured successfully",
                           extra={'interface_number': self.interface_number,
                                  'mode': network_mode,
                                  'allowed': self._mode_mask_to_names(allowed),
                                  'preferred': self._mode_mask_to_names(preferred)})

            except Exception as mode_e:
                logger.info("Network mode configuration not supported by this modem or driver",
                           extra={'interface_number': self.interface_number,
                                  'error': str(mode_e),
                                  'mode': network_mode})

        except Exception as e:
            logger.error(f"Network mode configuration error: {e}",
                        extra={'interface_number': self.interface_number})
            # Don't fail the entire configuration for mode issues
            logger.warning("Continuing configuration without network mode changes",
                          extra={'interface_number': self.interface_number})

    @staticmethod
    def _mode_mask_to_names(mask) -> str:
        """Render an MMModemMode bitmask as a readable RAT list (e.g. '4g|5g')."""
        try:
            mask = int(mask)
        except (TypeError, ValueError):
            return ''
        if mask == 0:
            return 'none'
        names = []
        for bit, name in ((1 << 1, '2g'), (1 << 2, '3g'),
                          (1 << 3, '4g'), (1 << 4, '5g')):
            if mask & bit:
                names.append(name)
        return '|'.join(names) if names else f'0x{mask:x}'


    def _get_band_name_to_constant_mapping(self):
        """Map human-readable band names to ModemManager uint32 constants"""
        # These are the actual MM_MODEM_BAND_* constants from ModemManager source
        return {
            # GSM bands — values are the real MM_MODEM_BAND_* enum; the tokens
            # match exactly what `show interfaces wwan` prints, so a band seen
            # in status can be pasted straight into `supported-bands`.
            'egsm-900': 1,
            'dcs-1800': 2,
            'pcs-1900': 3,
            'g850': 4,
            'g450': 14,
            'g480': 15,
            'g750': 16,
            'g380': 17,
            'g410': 18,
            'g710': 19,
            'g810': 20,
            'any': 256,

            # UMTS/3G bands (legacy MM_MODEM_BAND_UTRAN_* — the enum order is
            # NOT sequential with the 3GPP band number, hence the mapping)
            'umts-1': 5,     # UTRAN_1  2100 MHz
            'umts-3': 6,     # UTRAN_3  1800 MHz
            'umts-4': 7,     # UTRAN_4  1700/2100 MHz AWS
            'umts-6': 8,     # UTRAN_6  800 MHz
            'umts-5': 9,     # UTRAN_5  850 MHz
            'umts-8': 10,    # UTRAN_8  900 MHz
            'umts-9': 11,    # UTRAN_9  1700 MHz
            'umts-2': 12,    # UTRAN_2  1900 MHz PCS
            'umts-7': 13,    # UTRAN_7  2600 MHz

            # LTE/EUTRAN bands
            'eutran-1': 31,   # 2100 MHz
            'eutran-2': 32,   # 1900 MHz PCS
            'eutran-3': 33,   # 1800 MHz DCS
            'eutran-4': 34,   # 1700/2100 MHz AWS
            'eutran-5': 35,   # 850 MHz
            'eutran-6': 36,   # 800 MHz
            'eutran-7': 37,   # 2600 MHz
            'eutran-8': 38,   # 900 MHz
            'eutran-9': 39,   # 1800 MHz
            'eutran-10': 40,  # 1700/2100 MHz
            'eutran-11': 41,  # 1500 MHz
            'eutran-12': 42,  # 700 MHz a
            'eutran-13': 43,  # 700 MHz c
            'eutran-14': 44,  # 700 MHz PS
            'eutran-17': 47,  # 700 MHz b
            'eutran-18': 48,  # 800 MHz
            'eutran-19': 49,  # 800 MHz
            'eutran-20': 50,  # 800 MHz DD
            'eutran-21': 51,  # 1500 MHz
            'eutran-25': 55,  # 1900 MHz+
            'eutran-26': 56,  # 850 MHz+
            'eutran-28': 58,  # 700 MHz APT
            'eutran-41': 71,  # 2500 MHz
            'eutran-66': 96,  # 1700/2100 MHz
            'eutran-71': 101, # 600 MHz

            # 5G NR/NGRAN bands (MM_MODEM_BAND_NGRAN_N = 300 + N)
            'ngran-1': 301,   # 2100 MHz
            'ngran-2': 302,   # 1900 MHz
            'ngran-3': 303,   # 1800 MHz
            'ngran-5': 305,   # 850 MHz
            'ngran-7': 307,   # 2600 MHz
            'ngran-8': 308,   # 900 MHz
            'ngran-12': 312,  # 700 MHz
            'ngran-13': 313,  # 700 MHz c
            'ngran-14': 314,  # 700 MHz PS
            'ngran-18': 318,  # 800 MHz
            'ngran-20': 320,  # 800 MHz DD
            'ngran-25': 325,  # 1900 MHz
            'ngran-26': 326,  # 850 MHz
            'ngran-28': 328,  # 700 MHz APT
            'ngran-29': 329,  # 700 MHz SDL
            'ngran-30': 330,  # 2300 MHz
            'ngran-34': 334,  # 2010 MHz TDD
            'ngran-38': 338,  # 2600 MHz TDD
            'ngran-39': 339,  # 1900 MHz TDD
            'ngran-40': 340,  # 2300 MHz TDD
            'ngran-41': 341,  # 2500 MHz TDD
            'ngran-48': 348,  # 3600 MHz CBRS
            'ngran-50': 350,  # 1500 MHz SDL
            'ngran-51': 351,  # 1500 MHz
            'ngran-53': 353,  # 2400 MHz
            'ngran-65': 365,  # 2100 MHz
            'ngran-66': 366,  # 1700/2100 MHz AWS
            'ngran-67': 367,  # 700 MHz EU SDL
            'ngran-70': 370,  # 1700/2100 MHz
            'ngran-71': 371,  # 600 MHz
            'ngran-74': 374,  # 1400 MHz SDL
            'ngran-75': 375,  # 1500 MHz SDL
            'ngran-76': 376,  # 1500 MHz SDL
            'ngran-77': 377,  # 3700 MHz TDD
            'ngran-78': 378,  # 3500 MHz TDD
            'ngran-79': 379,  # 4700 MHz TDD
            'ngran-80': 380,  # 1800 MHz SUL
            'ngran-81': 381,  # 900 MHz SUL
            'ngran-82': 382,  # 800 MHz SUL
            'ngran-83': 383,  # 700 MHz SUL
            'ngran-84': 384,  # 2100 MHz SUL
            'ngran-86': 386,  # 1700 MHz SUL
            'ngran-89': 389,  # 800 MHz SUL
            'ngran-90': 390,  # 2500 MHz TDD
            'ngran-91': 391,  # 800/1400 MHz
            'ngran-92': 392,  # 800/700 MHz
            'ngran-93': 393,  # 900/1500 MHz
            'ngran-94': 394,  # 880/1400 MHz
            'ngran-95': 395,  # 2100 MHz SUL
            # 5G NR FR2 mmWave bands
            'ngran-257': 557, # 28 GHz mmWave
            'ngran-258': 558, # 26 GHz mmWave
            'ngran-260': 560, # 39 GHz mmWave
            'ngran-261': 561, # 28 GHz mmWave
        }

    def _band_name_to_mm_constant(self, band_name):
        """Convert a human-readable band token to its MM constant.

        Falls back to the algorithmic EUTRAN/NGRAN/UTRAN encodings so every
        band the modem can report round-trips with :meth:`_band_to_string`,
        even when it is not in the hand-maintained mapping table.  Returns
        ``None`` for unrecognised tokens.
        """
        name = band_name.lower().strip()
        mapping = self._get_band_name_to_constant_mapping()
        if name in mapping:
            return mapping[name]
        m = re.match(r'(eutran|ngran|umts|utran)-(\d+)$', name)
        if m:
            family, number = m.group(1), int(m.group(2))
            if family == 'ngran':
                return 300 + number
            if family == 'eutran':
                return 30 + number
            # modern MM_MODEM_BAND_UTRAN_N = 200 + N
            return 200 + number
        return None

    @staticmethod
    def _is_technology_group(name):
        """Return True if *name* is a technology-group keyword (2G/3G/LTE/5G)
        rather than a specific band name."""
        return name.lower().strip() in {'2g', '3g', 'lte', '5g'}

    def _mm_constant_to_band_name(self, mm_constant):
        """Convert MM constant back to human-readable band name"""
        mapping = self._get_band_name_to_constant_mapping()
        reverse_mapping = {v: k for k, v in mapping.items()}
        return reverse_mapping.get(mm_constant, f"unknown-{mm_constant}")

    def _qmi_control_device(self, modem_props):
        """Return the QMI control device node (e.g. ``/dev/cdc-wdm0``).

        Reads ModemManager's ``Ports`` property (an array of
        ``(name, MMModemPortType)`` tuples) and returns the first QMI port
        (``MM_MODEM_PORT_TYPE_QMI == 6``).  Returns ``None`` when the modem
        exposes no QMI port (e.g. an MBIM- or AT-only modem).

        The ``MMModemPortType`` enum is 1-based:
        ``UNKNOWN=1, NET=2, AT=3, QCDM=4, GPS=5, QMI=6, MBIM=7, AUDIO=8,
        IGNORED=9`` — so QMI is 6 (5 is GPS).
        """
        try:
            ports = modem_props.get('Ports', []) or []
            for entry in ports:
                try:
                    name, ptype = entry[0], int(entry[1])
                except (TypeError, IndexError, ValueError):
                    continue
                if ptype != 6:  # MM_MODEM_PORT_TYPE_QMI
                    continue
                if hasattr(name, 'value'):
                    name = name.value
                name = str(name) if name else ''
                if not name:
                    continue
                return name if name.startswith('/dev/') else f'/dev/{name}'
        except Exception:
            pass
        return None

    async def _qmi_get_serving_cell_info(self, modem_props) -> dict:
        """Read live serving-cell info (band, channel, cell IDs) via ``qmicli``.

        Fallback for status reporting when ModemManager's
        ``Modem.CellInfo.GetCellInfo()`` returns no serving cell — a common
        gap on QMI modems / older MM where the CellInfo interface is present
        but unpopulated.

        Two QMI sources are consulted over the shared ModemManager
        ``qmi-proxy`` (``-p``, read-only):

        1. ``--nas-get-rf-band-info`` — reports the *active* radio interface,
           band and channel.  This is reliable while the modem is RRC
           **connected** (active bearer), where the cell-location serving
           block can be empty.  Primary source for band/channel/RAT.
        2. ``--nas-get-cell-location-info`` — its ``Intrafrequency LTE Info``
           block carries the serving cell ID, global cell ID and TAC (and
           EARFCN, used as a band fallback).  Best populated when the modem
           is idle, so used to enrich the cell-identity fields.

        Never raises — returns ``{}`` when QMI is unavailable or nothing
        could be parsed.

        :returns: dict with any of ``serving_cell_type``, ``serving_band``,
            ``serving_earfcn``, ``serving_cell_id``, ``serving_tac``,
            ``serving_physical_ci`` — or ``{}``.
        """
        info = {}
        try:
            device = self._qmi_control_device(modem_props)
            if not device:
                logger.info("No QMI control device — cannot read serving cell",
                            extra={'interface_number': self.interface_number})
                return {}
            if not shutil.which('qmicli'):
                logger.info("qmicli not installed — cannot read serving cell",
                            extra={'interface_number': self.interface_number})
                return {}

            async def _qmicli(*args):
                """Run a read-only qmicli command over MM's qmi-proxy.
                Returns stdout text, or ``None`` on failure/timeout."""
                try:
                    proc = await asyncio.create_subprocess_exec(
                        'qmicli', '-d', device, '-p', *args,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    out, err = await asyncio.wait_for(
                        proc.communicate(), timeout=8)
                except asyncio.TimeoutError:
                    logger.info("qmicli serving-cell query timed out",
                                extra={'interface_number': self.interface_number,
                                       'args': ' '.join(args)})
                    return None
                if proc.returncode != 0:
                    logger.info("qmicli serving-cell query failed",
                                extra={'interface_number': self.interface_number,
                                       'args': ' '.join(args),
                                       'error': err.decode(errors='replace').strip()})
                    return None
                return out.decode(errors='replace')

            # --- PRIMARY: NAS Get RF Band Info (works while connected) ---
            # Output varies slightly by libqmi version but reliably contains,
            # per active radio interface:
            #   Radio interface: 'lte'
            #   Active band class: 'eutran-7'   (or "Active band:")
            #   Active channel: '3050'
            # Parse the first LTE interface as the serving RAT; fall back to
            # the first 5G NR interface when LTE is absent (pure-NR camp).
            rf = await _qmicli('--nas-get-rf-band-info')
            if rf:
                # Split into per-interface chunks on the "Radio interface:" key.
                # NOTE: qmicli emits "Radio Interface:" (capitalised) on this
                # firmware, so the split MUST be case-insensitive or no chunk
                # is produced and nothing parses.
                chunks = re.split(r"Radio interface:", rf, flags=re.IGNORECASE)
                lte_chunk = nr_chunk = None
                for ch in chunks[1:]:
                    low = ch.lower()
                    if lte_chunk is None and "'lte'" in low.split('\n', 1)[0]:
                        lte_chunk = ch
                    elif nr_chunk is None and (
                            "'5gnr'" in low.split('\n', 1)[0]
                            or "'nr5g'" in low.split('\n', 1)[0]):
                        nr_chunk = ch
                chosen = lte_chunk or nr_chunk
                if chosen is not None:
                    info['serving_cell_type'] = 'lte' if lte_chunk else 'nr5g'
                    m_band = re.search(
                        r"Active band(?:\s*class)?:\s*'?((?:eutran|ngran|utran|gsm)-\d+)'?",
                        chosen, re.IGNORECASE)
                    if m_band:
                        info['serving_band'] = m_band.group(1).lower()
                    m_chan = re.search(
                        r"Active channel:\s*'?(\d+)'?", chosen, re.IGNORECASE)
                    if m_chan:
                        info['serving_earfcn'] = m_chan.group(1)
                        # Derive band from EARFCN if the band name was absent.
                        if not info.get('serving_band') and info['serving_cell_type'] == 'lte':
                            band = self._lte_earfcn_to_band(m_chan.group(1))
                            if band:
                                info['serving_band'] = band.lower()

            # --- SECONDARY: NAS Get Cell Location Info (cell-identity) ---
            # Enriches with serving / global cell ID + TAC, and supplies band
            # via EARFCN when rf-band-info did not yield one.
            cell = await _qmicli('--nas-get-cell-location-info')
            if cell:
                lte_idx = cell.lower().find('intrafrequency lte info')
                if lte_idx != -1:
                    seg = cell[lte_idx:]
                    m_earfcn = re.search(
                        r"EUTRA Absolute RF Channel Number:\s*'(\d+)'", seg, re.IGNORECASE)
                    if m_earfcn and not info.get('serving_earfcn'):
                        info.setdefault('serving_cell_type', 'lte')
                        info['serving_earfcn'] = m_earfcn.group(1)
                        if not info.get('serving_band'):
                            band = self._lte_earfcn_to_band(m_earfcn.group(1))
                            if band:
                                info['serving_band'] = band.lower()
                    m_tac = re.search(r"Tracking Area Code:\s*'(\d+)'", seg, re.IGNORECASE)
                    if m_tac:
                        info['serving_tac'] = m_tac.group(1)
                    m_gcid = re.search(r"Global Cell ID:\s*'(\d+)'", seg, re.IGNORECASE)
                    if m_gcid:
                        info['serving_cell_id'] = m_gcid.group(1)
                    m_scid = re.search(r"Serving Cell ID:\s*'(\d+)'", seg, re.IGNORECASE)
                    if m_scid:
                        info['serving_physical_ci'] = m_scid.group(1)
                # Pure-NR camp: no LTE block, grab the NR channel.
                if 'serving_cell_type' not in info:
                    m_nr = re.search(r"5GNR ARFCN:\s*'(\d+)'", cell, re.IGNORECASE)
                    if m_nr:
                        info['serving_cell_type'] = 'nr5g'
                        info['serving_earfcn'] = m_nr.group(1)

            if info:
                logger.info("Read serving-cell info over QMI",
                            extra={'interface_number': self.interface_number,
                                   'device': device,
                                   'serving_band': info.get('serving_band', ''),
                                   'serving_earfcn': info.get('serving_earfcn', ''),
                                   'serving_cell_id': info.get('serving_cell_id', '')})
            else:
                logger.info("Serving cell not reported by QMI (rf-band + "
                            "cell-location both empty)",
                            extra={'interface_number': self.interface_number,
                                   'device': device})
        except Exception as e:
            logger.info("Serving-cell info not readable over QMI",
                        extra={'interface_number': self.interface_number,
                               'error': str(e)})
        return info

    async def _qmi_get_current_apn(self, modem_props=None) -> str:
        """Read the carrier-negotiated APN of the live session via ``qmicli``.

        ModemManager's ``Bearer.Properties.apn`` only echoes back the value we
        passed to ``Simple.Connect()`` — including the empty string on the
        automatic-assignment path — so it cannot tell us which APN the network
        actually activated.  The genuinely-negotiated APN is exposed by QMI
        ``WDS Get Current Settings`` for the running packet session.

        Runs over the shared ModemManager ``qmi-proxy`` (``-p``, read-only) so
        it does not disturb MM's own QMI session.  Never raises.

        :param modem_props: optional pre-fetched Modem property dict; fetched
            from the live modem when omitted.
        :returns: the negotiated APN name, or ``''`` when unavailable.
        """
        try:
            if modem_props is None:
                if not self.proxy:
                    return ''
                props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
                modem_all_raw = await props.call_get_all(MODEM_INTERFACE)
                modem_props = {k: (v.value if hasattr(v, 'value') else v)
                               for k, v in modem_all_raw.items()}

            device = self._qmi_control_device(modem_props)
            if not device:
                return ''  # MBIM/AT-only modem — no QMI port
            if not shutil.which('qmicli'):
                return ''

            try:
                proc = await asyncio.create_subprocess_exec(
                    'qmicli', '-d', device, '-p', '--wds-get-current-settings',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                out, err = await asyncio.wait_for(proc.communicate(), timeout=8)
            except asyncio.TimeoutError:
                logger.info("qmicli current-APN query timed out",
                            extra={'interface_number': self.interface_number})
                return ''
            if proc.returncode != 0:
                logger.info("qmicli current-APN query failed",
                            extra={'interface_number': self.interface_number,
                                   'device': device,
                                   'error': err.decode(errors='replace').strip()})
                return ''

            # Output carries one "APN: 'name'" line per active WDS session
            # (IPv4/IPv6 share the same APN).  Take the first non-empty value.
            text = out.decode(errors='replace')
            for match in re.finditer(r"APN:\s*'([^']*)'", text, re.IGNORECASE):
                apn = match.group(1).strip()
                if apn:
                    return apn
        except Exception as e:
            logger.info("Negotiated APN not readable over QMI",
                        extra={'interface_number': self.interface_number,
                               'error': str(e)})
        return ''

    def _requires_disconnection(self, old_config, new_config):
        """Determine whether a config change impacts the *running* connection.

        Returns True only for changes that affect the bearer currently in
        service, so the caller performs a full graceful restart.  Everything
        else (timers, data-limits, interface-management, connectivity probes,
        logging, and edits to a SIM slot we are NOT currently running on —
        e.g. adding/provisioning the backup SIM) is applied live without
        bouncing the connection.

        Restart-worthy changes:
          * ``primary_sim_slot`` — switches which SIM is in service;
          * ``network_mode``     — modem-level RAT selection (SetCurrentModes);
          * connection parameters (APN, auth, pdp-type, roaming, bands) of the
            **active** SIM slot only.
        """
        if not old_config:
            return False  # First-time configuration doesn't need disconnection

        # primary_sim_slot / network_mode are modem-level and always impact the
        # running session when changed.
        for param in ('primary_sim_slot', 'network_mode'):
            if old_config.get(param) != new_config.get(param):
                logger.info(f"Connection parameter '{param}' changed - restart required",
                           extra={'interface_number': self.interface_number, 'param': param})
                return True

        # SIM-slot connection params: only a change to the slot we are actually
        # running on matters.  Edits to the other slot (provisioning a second
        # SIM, fixing its APN, etc.) do not touch the live bearer and are
        # applied live; they take effect naturally on the next failover.
        active_slot = self.current_active_sim or new_config.get('primary_sim_slot', 1)
        if self._sim_connection_params_changed(
                old_config.get('sim_slots', []),
                new_config.get('sim_slots', []),
                active_slot):
            logger.info("Active-SIM connection parameters changed - restart required",
                       extra={'interface_number': self.interface_number,
                              'active_slot': active_slot})
            return True

        logger.info("Only live-apply parameters changed - no restart needed",
                   extra={'interface_number': self.interface_number})
        return False

    def _sim_connection_params_changed(self, old_sim_slots, new_sim_slots, active_slot):
        """Check if the ACTIVE SIM slot's connection parameters changed.

        Only the slot currently in service (``active_slot``) is compared —
        edits to an inactive slot do not disturb the running bearer.
        ``supported_bands`` is included so that a band-only edit on the active
        SIM re-runs the modem-level band configuration (including 5G NR over
        QMI) via the restart path; a band edit on the inactive slot does not,
        because the modem only enforces the active SIM's bands.
        """
        old_slots = {slot['slot']: slot for slot in old_sim_slots}
        new_slots = {slot['slot']: slot for slot in new_sim_slots}

        old_slot = old_slots.get(active_slot, {})
        new_slot = new_slots.get(active_slot, {})

        connection_sim_params = ['apn', 'username', 'password', 'auth_type',
                                 'pdp_type', 'roaming', 'supported_bands']

        for param in connection_sim_params:
            if old_slot.get(param) != new_slot.get(param):
                logger.info(f"Active SIM slot {active_slot} connection parameter '{param}' changed",
                           extra={'interface_number': self.interface_number,
                                  'slot': active_slot, 'param': param,
                                  'old_value': old_slot.get(param),
                                  'new_value': new_slot.get(param)})
                if param == 'supported_bands':
                    # Make it unambiguous which radio families changed — most
                    # importantly 5G NR, whose band write goes over QMI (not
                    # ModemManager's CurrentBands), so the MM band-write step
                    # logs "skipping CurrentBands write" even though the bearer
                    # IS being rebuilt for the NR change.  This line names the
                    # changed family so a 5G-only edit is clearly attributed.
                    changed_families = self._band_families_changed(
                        old_slot.get(param), new_slot.get(param))
                    logger.info(
                        "Active-SIM supported-bands change spans %s — bearer "
                        "will be rebuilt (5G NR applied over QMI while the "
                        "modem is disabled)",
                        ', '.join(changed_families) if changed_families else 'unknown',
                        extra={'interface_number': self.interface_number,
                               'slot': active_slot,
                               'changed_band_families': changed_families})
                return True

        return False

    @staticmethod
    def _band_families_changed(old_bands, new_bands) -> list:
        """Return the radio families whose band membership changed.

        Classifies each band token into its family (5G NR, LTE, 3G, 2G) and
        returns the families that differ between ``old_bands`` and
        ``new_bands``.  ``all`` is treated as its own pseudo-family so a
        switch to/from unrestricted is reported too.  Purely diagnostic — used
        to make a 5G-NR-only band change obvious in the journal, since NR bands
        are written over QMI rather than ModemManager.
        """
        def _families(value):
            if isinstance(value, str):
                tokens = [t.strip().lower() for t in value.split(',') if t.strip()]
            elif value:
                tokens = [str(t).strip().lower() for t in value if str(t).strip()]
            else:
                tokens = []
            fam = {}
            for tok in tokens:
                if tok == 'all':
                    fam.setdefault('all', set()).add('all')
                elif tok.startswith('ngran-'):
                    fam.setdefault('5G NR', set()).add(tok)
                elif tok.startswith('eutran-'):
                    fam.setdefault('LTE', set()).add(tok)
                elif tok.startswith(('umts-', 'utran-')):
                    fam.setdefault('3G', set()).add(tok)
                elif tok.startswith(('gsm-', 'egsm-', 'dcs-', 'pcs-', 'g')):
                    fam.setdefault('2G', set()).add(tok)
                else:
                    fam.setdefault('other', set()).add(tok)
            return fam

        old_fam = _families(old_bands)
        new_fam = _families(new_bands)
        changed = []
        # Preserve a stable, human-friendly ordering.
        for family in ('5G NR', 'LTE', '3G', '2G', 'all', 'other'):
            if old_fam.get(family, set()) != new_fam.get(family, set()):
                changed.append(family)
        return changed

    async def _reconfigure_modem(self):
        """Reconfigure modem with new settings"""
        logger.info("Reconfiguring modem",
                   extra={'interface_number': self.interface_number})

        # Check if we need to disconnect for this configuration change
        old_config = getattr(self, '_previous_config', {})
        needs_disconnect = self._requires_disconnection(old_config, self.config)

        # apply_config() always fires RECONFIGURE before scheduling this
        # coroutine, so by the time we run the FSM has already left its prior
        # stable state (CONNECTED / USAGE_MONITORING / REGISTERED_IDLE / ...)
        # and is parked in CONFIGURING.  Capture the real bearer state up-front
        # so we can decide how to settle the FSM afterwards.
        bearer_up = await self._is_bearer_connected()

        if needs_disconnect:
            # ── Modem-level change → full graceful restart ───────────────
            # SIM slot, supported-bands and network-mode are modem-level
            # parameters that can only be written while the modem is DISABLED,
            # and a mistaken value (e.g. a band the serving cell doesn't use)
            # can leave the modem unable to register at all.  The safe,
            # predictable response is therefore to treat the change as a HARD
            # RESTART: gracefully tear the whole session down and re-run the
            # exact same startup sequence the service performs at boot.
            #
            # `_configure_modem_initial()` is that canonical sequence —
            # gentle-reset (if still connected) → disable → SIM/bands/mode →
            # enable → unlock → connect-or-park.  Crucially it ends by honouring
            # `connection_mode` the same way it does at boot:
            #   * always-on / dial-on-demand  → reconnect (comes back CONNECTED)
            #   * connect-on-demand           → park at REGISTERED_IDLE
            # so any runtime disconnect_bearer() intent is intentionally
            # discarded for the always-on family — exactly like a reboot.  This
            # is the behaviour an operator expects from a band change: rebuild
            # from scratch rather than honour a stale, possibly-mistaken state.
            logger.info(
                "Modem-level parameter change (SIM/bands/network-mode) — "
                "performing a full graceful restart of the modem session",
                extra={'interface_number': self.interface_number,
                       'connection_mode': self.connection_mode,
                       'bearer_up': bearer_up})

            # Graceful teardown: stop monitoring, drop the bearer (if up), and
            # remove all downstream LAN state (ip-passthrough dnsmasq/routes,
            # ipv6-bridging prefix/radvd) so nothing stale survives the
            # restart.  Each step is best-effort and idempotent.
            try:
                await self._stop_network_interface_monitoring()
            except Exception as e:
                logger.debug(f"Monitoring stop during restart failed: {e}",
                            extra={'interface_number': self.interface_number})
            if bearer_up:
                try:
                    await self._disconnect_bearer()
                except Exception as e:
                    logger.debug(f"Bearer disconnect during restart failed: {e}",
                                extra={'interface_number': self.interface_number})
            try:
                await self._teardown_downstream_features()
            except Exception as e:
                logger.debug(f"Downstream teardown during restart failed: {e}",
                            extra={'interface_number': self.interface_number})

            # Persist config for future diffs BEFORE the restart so a
            # subsequent reconfigure compares against what we just applied.
            self._previous_config = self.config.copy() if self.config else {}

            # Re-run the canonical startup.  It owns
            # initial_configuration_in_progress and drives the final
            # connect/park transition itself, so we must NOT also run
            # _settle_after_reconfigure() — return straight after.  The FSM is
            # already parked in CONFIGURING (from RECONFIGURE), which is exactly
            # the state _configure_modem_initial() finalises from at boot.
            await self._configure_modem_initial()
            return

        # ── Monitoring-only change (e.g. connection-mode, timers) ────────
        logger.info("Configuration updated without disconnection - only monitoring/timer changes",
                   extra={'interface_number': self.interface_number})
        # For non-connection changes, just update internal state.
        # Reconcile downstream-LAN features (ip-passthrough, ipv6-bridging)
        # immediately rather than waiting for the next bearer event —
        # disabling these features should take effect on commit, not at
        # the next IP-change.
        await self._reconcile_downstream_features()

        # The preceding RECONFIGURE parked the FSM in CONFIGURING.  A
        # monitoring-only change does not bounce the bearer, so no
        # ModemManager state-change signal will fire to move us out of
        # CONFIGURING — settle the FSM back to a stable state here so the
        # modem does not get stuck reporting CONFIGURING while connected.
        await self._settle_after_reconfigure()

        # Store current config for future comparisons
        self._previous_config = self.config.copy() if self.config else {}

    async def _settle_after_reconfigure(self):
        """Drive the FSM out of the transient CONFIGURING state after a
        runtime reconfigure.

        ``apply_config()`` fires ``RECONFIGURE`` before ``_reconfigure_modem()``
        runs, which moves the FSM from its prior stable state into
        ``CONFIGURING``.  A monitoring-only change (such as ``connection-mode``)
        does not bounce the bearer, so no ModemManager state-change signal
        fires to advance the FSM and it would otherwise remain in
        ``CONFIGURING`` indefinitely even though the bearer is up and traffic
        flows.  Reconcile the FSM with the real bearer state here.

        Idempotent and safe: when another path (an MM signal or the connection
        cascade) has already advanced the FSM past ``CONFIGURING`` this is a
        no-op.
        """
        if self.machine.current_state != ModemState.CONFIGURING.value:
            # Another path already advanced the FSM — nothing to settle.
            return

        bearer_up = await self._is_bearer_connected()

        if bearer_up:
            # Bearer is still up: return to CONNECTED and resume monitoring.
            logger.info("Reconfigure complete — bearer still up, returning to CONNECTED",
                       extra={'interface_number': self.interface_number})
            self.transition(ModemEvent.CONNECT)    # CONFIGURING -> CONNECTING
            self.transition(ModemEvent.CONNECTED)  # CONNECTING  -> CONNECTED
            try:
                await self._apply_bearer_ip_configuration()
                if self.ensure_link_up_on_connect:
                    self._safe_create_task(self._ensure_interface_up())
            except Exception as e:
                logger.warning("Post-reconfigure bearer re-apply failed: %s", e,
                              extra={'interface_number': self.interface_number})
            self._ensure_usage_monitoring_started('reconfigure_settle')
            return

        # No bearer up.  Honour the connection mode and any standing user
        # disconnect: on-demand modes park at REGISTERED_IDLE until a connect
        # trigger arrives; always-on drives a fresh connection.
        if self.user_disconnected or (
                self.connection_mode in ('connect-on-demand', 'dial-on-demand')
                and not self.bearer_requested):
            logger.info("Reconfigure complete — parking at REGISTERED_IDLE",
                       extra={'interface_number': self.interface_number,
                              'connection_mode': self.connection_mode,
                              'user_disconnected': self.user_disconnected})
            self.transition(ModemEvent.ENTER_IDLE)  # CONFIGURING -> REGISTERED_IDLE
        else:
            logger.info("Reconfigure complete — driving fresh connection",
                       extra={'interface_number': self.interface_number,
                              'connection_mode': self.connection_mode})
            self.transition(ModemEvent.CONNECT)     # CONFIGURING -> CONNECTING
            await self.apply_modem_configuration()

    async def _reconcile_downstream_features(self):
        """Reconcile passthrough + ipv6-bridging state with the live config.

        Invoked on a no-disconnect config update so that the operator
        sees an immediate effect when they remove or retarget either of
        these downstream-LAN features.  Without this, stale state
        (dnsmasq + policy routes for passthrough, a bridged /64 + radvd
        for ipv6-bridging) lingers until the bearer bounces.

        The method is idempotent and safe regardless of bearer state.
        """
        # ── IP passthrough ───────────────────────────────────────────
        # Push the latest config to the manager.  If the feature is no
        # longer active (node removed, or `interface` leaf cleared),
        # tear down.  If the target interface changed, also tear down —
        # the next bearer event will re-apply on the new interface with
        # current carrier IPs.
        try:
            pt_cfg = (self.config or {}).get('ip_passthrough')
            iface_changed = self._passthrough.update_config(pt_cfg)
            if not self._passthrough.cfg.is_active():
                await self._passthrough.teardown()
            elif iface_changed:
                await self._passthrough.teardown()
        except Exception as e:
            logger.warning("Passthrough reconcile failed: %s", e,
                           extra={'interface_number': self.interface_number})

        # ── IPv6 bridging ────────────────────────────────────────────
        # `_bridging_config` is already updated via _apply_parsed_configuration().
        # If we currently have a prefix applied somewhere but the feature
        # is now disabled or aimed at a different LAN interface, remove.
        try:
            enabled = bool(self._bridging_config.get('enabled'))
            new_iface = self._bridging_config.get('interface') or ''
            applied_ifaces = list(self._bridging_applied.keys()) \
                if hasattr(self, '_bridging_applied') else []
            target_changed = bool(applied_ifaces) and (new_iface not in applied_ifaces)
            if applied_ifaces and (not enabled or target_changed):
                await self._bridging_remove_all()
        except Exception as e:
            logger.warning("IPv6 bridging reconcile failed: %s", e,
                           extra={'interface_number': self.interface_number})

        # ── Re-apply on live bearer ──────────────────────────────────
        # If the bearer is up, re-invoke the bearer-IP apply path so that
        # newly-enabled features (e.g. just-added ipv6-bridging or
        # ip-passthrough) are installed immediately, and feature-enabled
        # changes that depend on bearer IPs (DNS, MTU, prefix) refresh
        # without waiting for the next IP-change event.  The apply path
        # is idempotent — re-applying with unchanged IPs is a no-op.
        if self.machine.current_state in (
                ModemState.CONNECTED.value,
                ModemState.USAGE_MONITORING.value):
            try:
                await self._apply_bearer_ip_configuration()
            except Exception as e:
                logger.warning(
                    "Bearer IP re-apply during reconcile failed: %s", e,
                    extra={'interface_number': self.interface_number})

    async def _disconnect_bearer(self):
        """Disconnect the current bearer connection.

        Always issues a disconnect down to ModemManager — even when we have
        no tracked bearer path — and finishes with an all-bearers sweep
        (``Simple.Disconnect('/')``).  Disconnecting an already-idle modem is
        harmless, and the unconditional sweep is what keeps ModemManager from
        drifting out of sync with the FSM: a stale bearer_path, an extra
        bearer MM created on its own, or a bearer left behind by a racey
        teardown would otherwise stay up while the FSM believes it is idle.
        This mirrors the convention used on the startup / retry paths.
        """
        try:
            if not self.proxy:
                logger.warning("No modem proxy — cannot disconnect bearer",
                              extra={'interface_number': self.interface_number})
                return

            simple_iface = self.proxy.get_interface(SIMPLE_INTERFACE)

            if self.bearer_path:
                logger.info("Disconnecting bearer",
                           extra={'interface_number': self.interface_number,
                                  'bearer_path': self.bearer_path})
                try:
                    await simple_iface.call_disconnect(self.bearer_path)
                except Exception as e:
                    # Fall through to the all-bearers sweep below.
                    logger.debug(f"Tracked bearer disconnect failed: {e}",
                                extra={'interface_number': self.interface_number})
                self.bearer_path = None

            # Unconditional sweep: drop any bearer MM still holds so the modem
            # is genuinely idle regardless of what we were tracking.  Harmless
            # no-op when nothing is connected.
            await simple_iface.call_disconnect('/')

            logger.info("Bearer disconnected successfully",
                       extra={'interface_number': self.interface_number})

        except Exception as e:
            logger.error(f"Failed to disconnect bearer: {e}",
                        extra={'interface_number': self.interface_number})

    async def apply_modem_configuration(self):
        """Apply connection configuration with APN auto-discovery"""
        if not self.proxy or not self.config:
            logger.warning("Cannot apply configuration - missing proxy or config",
                          extra={'interface_number': self.interface_number,
                                 'has_proxy': bool(self.proxy),
                                 'has_config': bool(self.config)})
            return

        try:
            # Registration gate — never attempt Simple.Connect() on a
            # modem that is not at least REGISTERED. The Modem.Simple
            # D-Bus interface is not exposed on modems in FAILED /
            # LOCKED / DISABLED / ENABLED / SEARCHING, so attempting
            # the cascade in those states produces a misleading
            # `interface not found on this object:
            # org.freedesktop.ModemManager1.Modem.Simple` error and
            # then drives the FSM into FAILED for the wrong reason.
            # Check current MM state first; only wait if the modem is
            # plausibly in the process of registering.
            try:
                props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
                state_variant = await props.call_get(MODEM_INTERFACE, "State")
                mm_state = state_variant.value
            except Exception as e:
                logger.warning(f"Could not read modem state before connection cascade: {e}",
                              extra={'interface_number': self.interface_number})
                mm_state = None

            # MM state numbers: -1 FAILED, 2 LOCKED, 3 DISABLED,
            # 6 ENABLED, 7 SEARCHING, 8 REGISTERED, 10 CONNECTING,
            # 11 CONNECTED.
            if mm_state is not None and mm_state < 6:
                logger.warning(
                    "Modem not in a connectable state - aborting connection cascade",
                    extra={'interface_number': self.interface_number,
                           'modem_state': mm_state})
                # Let the FSM's existing failed/locked state handlers
                # decide recovery (SIM failover, retry, etc.).
                self.transition(ModemEvent.CONNECTION_FAILED)
                # Give dual-SIM failover a chance — this is functionally
                # equivalent to SIM-missing from the connection-cascade
                # point of view. _handle_sim_missing_failover is a no-op
                # if no alternate SIM exists, failover is disabled, or
                # cooldown is active.
                await self._handle_sim_missing_failover()
                return

            if mm_state is None or mm_state < 8:
                logger.info(
                    "Waiting for modem to reach REGISTERED before connection cascade",
                    extra={'interface_number': self.interface_number,
                           'modem_state': mm_state})
                registered = await self._wait_for_registered()
                if not registered:
                    logger.warning(
                        "Modem did not register in time - aborting connection cascade",
                        extra={'interface_number': self.interface_number})
                    self.last_failure_reason = (
                        "Modem failed to reach REGISTERED state within the "
                        "configured registration timeout. The SIM and/or "
                        "supported bands may not match any available carrier."
                    )
                    self.last_failure_time = time.time()
                    self.transition(ModemEvent.CONNECTION_FAILED)
                    # Registration timeout on the active SIM looks
                    # identical to a dead/unusable SIM from a failover
                    # standpoint (e.g. SIM requires a band this modem
                    # does not support). Offer dual-SIM failover; it
                    # is a no-op when no alternate SIM is configured.
                    await self._handle_sim_missing_failover()
                    return

            # 🔧 FIX: Check if bearer is already connected before attempting new connections
            is_already_connected = await self._is_bearer_connected()
            if is_already_connected:
                logger.info("Bearer already connected - transitioning to CONNECTED state instead of creating new connection",
                           extra={'interface_number': self.interface_number})
                # Apply IP configuration from existing bearer.  If the bearer
                # registered but cannot route (dead data path), fail over rather
                # than declaring CONNECTED on a SIM that cannot carry data.
                if not await self._apply_bearer_ip_or_fail('apply_modem_configuration'):
                    return
                # Set interface UP
                await self._ensure_interface_up()
                # Transition to CONNECTED state
                if self.machine.current_state != ModemState.CONNECTED.value:
                    self.transition(ModemEvent.CONNECTED)
                return

            # 🆕 Clean up any stale bearer before fresh connection attempt
            # This ensures we don't try to create a new bearer while MM still
            # has a partial/disconnected bearer from before.
            if self.bearer_path:
                logger.info("Cleaning up stale bearer before fresh connection attempt",
                           extra={'interface_number': self.interface_number})
                await self._cleanup_bearers()
                self.bearer_path = None

            # Detect runtime SIM identity changes before choosing APN
            # strategy. This catches out-of-band SIM mux + modem reset
            # sequences where PrimarySimSlot stays constant but IMSI/ICCID
            # changed underneath us.
            sim_changed = False
            sim_info = await self._get_sim_information()
            if sim_info:
                sim_changed = await self._check_sim_change(sim_info)
                if sim_changed:
                    logger.warning("Runtime SIM identity change detected — forcing fresh APN discovery",
                                  extra={'interface_number': self.interface_number,
                                         'active_sim_slot': self.current_active_sim,
                                         'operator': sim_info.get('operator_name', ''),
                                         'mcc_mnc': sim_info.get('mcc_mnc', '')})
                    # Ensure we do not reuse APN assumptions from the old SIM.
                    self.connected_apn = None
                    self._clear_persisted_apn()

            # Get active SIM configuration.  Anchor on the slot that is
            # actually active (current_active_sim), not the configured primary —
            # after a SIM failover we must use the failover slot's APN/config,
            # not the primary's.  Falls back to primary_sim_slot before the
            # first switch.
            active_slot = self.current_active_sim or self.config.get('primary_sim_slot', 1)
            sim_slots = self.config.get('sim_slots', [])
            active_sim_config = next((sim for sim in sim_slots if sim['slot'] == active_slot), {})

            # Get normalized APN configuration
            apn_config = self._normalize_apn_config(active_sim_config.get('apn', ''))

            # 🎯 NEW: Check if user configured an APN. Even after SIM
            # identity changes, explicit configured APN should be tried
            # first; only stale in-memory APN cache is suppressed.
            if apn_config['name']:
                if sim_changed:
                    logger.info("SIM changed, but still trying user-configured APN first",
                               extra={'interface_number': self.interface_number,
                                      'apn_name': apn_config['name'],
                                      'active_sim_slot': self.current_active_sim})
                logger.info("Using user-configured APN",
                           extra={'interface_number': self.interface_number,
                                  'apn_name': apn_config['name'],
                                  'has_auth': apn_config['auth_type'] != 'none'})

                # Try user APN directly
                success, reason = await self._try_connection_with_apn(apn_config, active_sim_config)
                if success:
                    return
                else:
                    logger.warning("User-configured APN failed, falling back to auto-discovery",
                                  extra={'interface_number': self.interface_number,
                                         'failed_apn': apn_config['name']})

            # 🎯 NEW: Auto-discovery flow
            logger.info("Starting APN auto-discovery",
                       extra={'interface_number': self.interface_number,
                              'active_sim_slot': active_slot,
                              'library_available': APN_LOOKUP_AVAILABLE})

            # Get SIM information for lookup
            if not sim_info:
                sim_info = await self._get_sim_information()
            if not sim_info:
                logger.error("Could not get SIM information for APN discovery",
                            extra={'interface_number': self.interface_number})
                self.transition(ModemEvent.CONNECTION_FAILED)
                return

            # Get prioritized APN list from discovery
            apn_candidates = await self._discover_apn_candidates(sim_info, active_sim_config)

            if not apn_candidates:
                logger.warning("No APN candidates found, trying automatic assignment",
                              extra={'interface_number': self.interface_number})
                auto_ok = await self._try_automatic_apn_assignment(active_sim_config)
                if not auto_ok:
                    self.last_failure_reason = (
                        "No APN candidates were discovered and automatic APN assignment failed."
                    )
                    self.last_failure_time = time.time()
                    self.last_failed_apn = '(auto-assignment)'
                    self.configured_apn_rejected = False
                    self.transition(ModemEvent.CONNECTION_FAILED)
                return

            # Try each APN candidate in priority order with explicit outcome handling.
            success, discovery_reason = await self._try_apn_candidates(
                apn_candidates, active_sim_config, sim_info
            )
            if success:
                return

            # Non-APN modem/network failure while testing candidates -> restart full flow.
            if discovery_reason == 'restart_required':
                self.last_failure_reason = (
                    "Non-APN modem/network failure occurred during APN discovery; "
                    "restarting connection workflow from the beginning."
                )
                self.last_failure_time = time.time()
                self.last_failed_apn = '(apn-discovery)'
                self.configured_apn_rejected = False
                self.transition(ModemEvent.CONNECTION_FAILED)
                return

            # Candidate exhaustion paths fall back to automatic APN assignment.
            auto_ok = await self._try_automatic_apn_assignment(active_sim_config)
            if not auto_ok:
                self.last_failure_reason = (
                    "All APN discovery candidates failed and automatic APN assignment also failed."
                )
                self.last_failure_time = time.time()
                self.last_failed_apn = '(apn-discovery)'
                self.configured_apn_rejected = False
                self.transition(ModemEvent.CONNECTION_FAILED)
                return

        except Exception as e:
            logger.error(f"Connection configuration failed: {e}",
                        extra={'interface_number': self.interface_number})
            self.transition(ModemEvent.CONNECTION_FAILED)

    async def _get_sim_information(self):
        """Extract comprehensive SIM information for Android APN lookup"""
        try:
            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")

            # Get current SIM path
            sim_path_variant = await props.call_get(MODEM_INTERFACE, "Sim")
            if not sim_path_variant:
                return None

            # Extract the actual path from the Variant
            sim_path = sim_path_variant.value if hasattr(sim_path_variant, 'value') else sim_path_variant
            if not sim_path or sim_path == '/':
                return None

            # Get SIM details
            sim_introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, sim_path)
            sim_proxy = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, sim_path, sim_introspect)
            sim_props = sim_proxy.get_interface("org.freedesktop.DBus.Properties")

            sim_interface = "org.freedesktop.ModemManager1.Sim"

            # Extract comprehensive SIM identifiers for Android lookup
            imsi_variant = await sim_props.call_get(sim_interface, "Imsi")
            operator_name_variant = await sim_props.call_get(sim_interface, "OperatorName")
            sim_identifier_variant = await sim_props.call_get(sim_interface, "SimIdentifier")

            # Extract values from Variants
            imsi = imsi_variant.value if hasattr(imsi_variant, 'value') else imsi_variant
            operator_name = operator_name_variant.value if hasattr(operator_name_variant, 'value') else operator_name_variant
            sim_identifier = sim_identifier_variant.value if hasattr(sim_identifier_variant, 'value') else sim_identifier_variant

            # Try to get additional identifiers for Android lookup
            gid1 = ""
            gid2 = ""
            try:
                # These might not be available on all modems
                gid1_variant = await sim_props.call_get(sim_interface, "Gid1")
                gid2_variant = await sim_props.call_get(sim_interface, "Gid2")
                gid1 = (gid1_variant.value if hasattr(gid1_variant, 'value') else gid1_variant) or ""
                gid2 = (gid2_variant.value if hasattr(gid2_variant, 'value') else gid2_variant) or ""
            except Exception:
                pass

            # Extract MCC/MNC from IMSI
            mcc_mnc = None
            if imsi and len(imsi) >= 5:
                if len(imsi) >= 6 and imsi[5].isdigit():
                    mcc_mnc = imsi[:6]  # 6-digit MCC+MNC
                else:
                    mcc_mnc = imsi[:5]  # 5-digit MCC+MNC

            sim_info = {
                'imsi': imsi,
                'operator_name': operator_name,
                'sim_identifier': sim_identifier,  # This is ICCID
                'mcc_mnc': mcc_mnc,
                'mcc': imsi[:3] if imsi and len(imsi) >= 3 else None,
                'mnc': mcc_mnc[3:] if mcc_mnc else None,
                'gid1': gid1,
                'gid2': gid2,
                'plmn': mcc_mnc,  # Same as mcc_mnc for Android lookup
                'spn': operator_name  # Service Provider Name
            }

            logger.info("SIM information extracted for Android APN lookup",
                       extra={'interface_number': self.interface_number,
                              'operator_name': operator_name,
                              'mcc_mnc': mcc_mnc,
                              'imsi_prefix': imsi[:6] + '...' if imsi else None,
                              'has_gid1': bool(gid1),
                              'has_gid2': bool(gid2)})

            return sim_info

        except Exception as e:
            logger.error(f"Failed to get comprehensive SIM information: {e}",
                        extra={'interface_number': self.interface_number})
            return None

    async def _discover_apn_candidates(self, sim_info, sim_config):
        """Discover APN candidates using new APNDiscovery class"""
        return await self.apn_discovery.discover_apn_candidates(sim_info, sim_config)

    def _convert_android_apns(self, android_apns, sim_info):
        """Convert Android APN format using extracted utility"""
        return convert_android_apns(android_apns, sim_info)

    def _extract_apn_field(self, apn, field_name: str, default_value: str = '') -> str:
        """Extract field from Android APN object using extracted utility"""
        return extract_apn_field(apn, field_name, default_value)

    def _convert_android_auth_type(self, android_auth: str) -> str:
        """Convert Android auth type using extracted utility"""
        return convert_android_auth_type(android_auth)

    def _calculate_android_priority(self, apn, index: int) -> int:
        """Calculate priority from Android APN (lower = higher priority)"""
        try:
            # Check if Android APN has explicit priority
            explicit_priority = self._extract_apn_field(apn, 'priority', None)
            if explicit_priority and explicit_priority.isdigit():
                return int(explicit_priority)

            # Priority based on APN type
            apn_type = self._extract_apn_field(apn, 'type', 'default').lower()

            if 'default' in apn_type:
                return 1  # Highest priority
            elif 'supl' in apn_type:
                return 2
            elif 'mms' in apn_type:
                return 3
            elif 'ims' in apn_type:
                return 4
            else:
                return 5 + index  # Lower priority, with index as tiebreaker

        except Exception:
            return 5 + index
    async def _try_apn_candidates(self, candidates, sim_config, sim_info=None):
        """Try a pre-built list of APN candidates with full escalation semantics.

        This is the single, canonical APN-iteration loop used by both the
        initial-configuration path (via _try_apn_candidates_from_discovery) and
        the runtime reconnection path (via apply_modem_configuration).

        Returns:
            (success: bool, reason: str)
              - success=True,  reason='success'
              - success=False, reason='all_apn_failed'   (all candidates exhausted)
              - success=False, reason='restart_required' (non-APN modem/network failure;
                                                          caller should trigger CONNECTION_FAILED)
        """
        # State-code → name mapping used for logging in the timeout branch.
        _STATE_NAMES = {
            -1: 'FAILED', 2: 'LOCKED', 3: 'DISABLED', 4: 'DISABLING',
            5: 'ENABLING', 6: 'ENABLED', 7: 'SEARCHING', 8: 'REGISTERED',
            9: 'DISCONNECTING', 10: 'CONNECTING', 11: 'CONNECTED',
        }

        if not candidates:
            return (False, 'all_apn_failed')

        logger.info("Trying APN candidates (canonical loop)",
                   extra={'interface_number': self.interface_number,
                          'candidate_count': len(candidates)})

        for i, apn_data in enumerate(candidates):
            apn_name = apn_data.get('name', 'unknown')
            logger.info(f"Trying APN candidate {i + 1}/{len(candidates)}",
                       extra={'interface_number': self.interface_number,
                              'apn_name': apn_name,
                              'apn_type': apn_data.get('type', 'default'),
                              'priority': apn_data.get('priority', 0)})

            apn_config = {
                'name': apn_data.get('name', ''),
                'username': apn_data.get('username', ''),
                'password': apn_data.get('password', ''),
                'auth_type': apn_data.get('auth_type', 'none'),
                'pdp_type': apn_data.get('pdp_type', 'ipv4v6'),
            }

            success, reason = await self._try_connection_with_apn(apn_config, sim_config)

            if success:
                logger.info("APN candidate connected successfully",
                           extra={'interface_number': self.interface_number,
                                  'apn_name': apn_name,
                                  'attempt': i + 1})
                return (True, 'success')

            # ── Non-APN modem/network failure: abort immediately and ask caller
            # to restart the whole connection workflow rather than burning through
            # remaining APNs for a non-APN problem.
            if reason == 'connection_failed':
                logger.warning(
                    "Non-APN ModemManager failure while testing APN; requesting full restart",
                    extra={'interface_number': self.interface_number,
                           'apn_name': apn_name,
                           'failure_reason': reason})
                await self._cleanup_bearers()
                return (False, 'restart_required')

            # ── Timeout: check MM modem state.  If still CONNECTING, poll up to
            # 60 s for a terminal MM decision before giving up on this APN.
            if reason == 'timeout':
                modem_state = None
                try:
                    if self.proxy:
                        props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
                        state_v = await props.call_get(MODEM_INTERFACE, "State")
                        modem_state = state_v.value if hasattr(state_v, 'value') else state_v
                except Exception as state_err:
                    logger.debug(f"Could not read modem state after timeout (non-fatal): {state_err}",
                               extra={'interface_number': self.interface_number})

                state_name = _STATE_NAMES.get(modem_state, f'UNKNOWN({modem_state})')
                logger.info(f"Connection timeout — modem state: {state_name}",
                           extra={'interface_number': self.interface_number,
                                  'modem_state': modem_state,
                                  'apn_name': apn_name})

                # 10 = CONNECTING: MM may still be negotiating; give it 60 s more.
                if modem_state == 10:
                    logger.info(
                        "Modem still CONNECTING after timeout; waiting up to 60 s for MM decision",
                        extra={'interface_number': self.interface_number,
                               'apn_name': apn_name})
                    poll_deadline = time.monotonic() + 60
                    while time.monotonic() < poll_deadline:
                        await asyncio.sleep(5)
                        try:
                            if self.proxy:
                                props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
                                state_v = await props.call_get(MODEM_INTERFACE, "State")
                                current_state = state_v.value if hasattr(state_v, 'value') else state_v
                                if current_state != 10:  # MM has reached a decision
                                    new_name = _STATE_NAMES.get(current_state, f'UNKNOWN({current_state})')
                                    logger.info(f"MM reached decision on APN: {new_name}",
                                               extra={'interface_number': self.interface_number,
                                                      'modem_state': current_state,
                                                      'apn_name': apn_name})
                                    modem_state = current_state
                                    break
                        except Exception as poll_err:
                            logger.debug(f"Poll error reading modem state (non-fatal): {poll_err}",
                                       extra={'interface_number': self.interface_number})
                    else:
                        logger.warning(
                            "MM still CONNECTING after 60 s wait; moving to next APN candidate",
                            extra={'interface_number': self.interface_number,
                                   'apn_name': apn_name})

            # ── APN-specific or transient outcome (apn_rejected / verification_failed /
            # error / timeout with non-CONNECTING final state): clean up and continue.
            logger.info(f"APN candidate failed ({reason}), cleaning up and continuing",
                       extra={'interface_number': self.interface_number,
                              'apn_name': apn_name})
            await self._cleanup_bearers()

        logger.warning("All APN candidates exhausted",
                      extra={'interface_number': self.interface_number,
                             'total_candidates_tried': len(candidates)})
        return (False, 'all_apn_failed')

    async def _mm_bearer_apn(self):
        """Read the negotiated APN from ModemManager's connected data bearer.

        The genuinely-effective APN is the one MM's *data* bearer is running
        with.  A modem can expose several connected bearers at once — e.g. on
        Verizon there is an admin/IMS bearer (``vzwadmin``) with NO net
        interface alongside the real data bearer (``VZWINTERNET``) bound to the
        modem's net port (``wwan0``).  The data bearer is the one with a
        non-empty ``Interface``; the admin bearer has none.  Picking the wrong
        one (e.g. the first listed) reports a misleading APN, so we explicitly
        select the connected bearer that has a network interface.

        This replaces the previous ``qmicli --wds-get-current-settings`` probe,
        which allocates a fresh WDS client with no active session on an
        MM-managed modem and therefore returns nothing.  Reading MM's own
        bearer is reliable, in-process, and needs no external tool.  Never
        raises; returns ``''`` when no suitable bearer/APN is found.
        """
        if not self.proxy:
            return ''
        try:
            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
            bearers_variant = await props.call_get(MODEM_INTERFACE, "Bearers")
            bearers = bearers_variant.value if bearers_variant else []
        except Exception as e:
            logger.debug(f"Could not list bearers for APN read: {e}",
                        extra={'interface_number': self.interface_number})
            return ''

        fallback_apn = ''  # connected bearer APN without an interface (last resort)
        for bearer_path in bearers or []:
            try:
                introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, bearer_path)
                bproxy = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, bearer_path, introspect)
                bprops = bproxy.get_interface("org.freedesktop.DBus.Properties")

                connected_v = await bprops.call_get(BEARER_INTERFACE, "Connected")
                if not (connected_v.value if hasattr(connected_v, 'value') else connected_v):
                    continue

                iface_v = await bprops.call_get(BEARER_INTERFACE, "Interface")
                iface = iface_v.value if hasattr(iface_v, 'value') else iface_v

                bp_v = await bprops.call_get(BEARER_INTERFACE, "Properties")
                bp = bp_v.value if hasattr(bp_v, 'value') else bp_v
                apn = bp.get('apn', '') if bp else ''
                apn = (apn.value if hasattr(apn, 'value') else apn) or ''
                apn = apn.strip()
                if not apn:
                    continue

                # Data bearer = connected AND bound to a net interface.
                if iface:
                    return apn
                # Admin/IMS bearer (no interface) — keep only as last resort.
                if not fallback_apn:
                    fallback_apn = apn
            except Exception as e:
                logger.debug(f"Bearer APN read failed for {bearer_path}: {e}",
                            extra={'interface_number': self.interface_number})
                continue

        return fallback_apn

    async def _capture_connected_apn(self):
        """Record the APN of the current successful connection.

        Reads the APN the ConnectionManager just connected with, persists it
        for fast reconnection, and captures the carrier-negotiated APN from
        ModemManager's connected data bearer.  Invoked from every successful
        connect path (initial config, runtime reconnect, SIM switch) so
        ``show interfaces wwan`` reports the APN regardless of how the bearer
        was established.
        """
        # Store the connected APN for fast reconnection and status reporting
        cm_apn = getattr(self.connection_manager, 'connected_apn', None)
        if cm_apn:
            self.connected_apn = cm_apn.copy()
            self.requested_apn = cm_apn.get('name', '')
            self._persist_connected_apn(cm_apn)
            logger.info("Stored connected APN for fast reconnection",
                       extra={'interface_number': self.interface_number,
                              'apn_name': cm_apn.get('name', '')})

        # Capture the APN the *carrier actually activated*.  Read it from
        # ModemManager's connected DATA bearer (the one bound to the net
        # interface); fall back to the QMI probe only when MM exposes no usable
        # bearer APN.  MM only echoes the requested APN in some paths, so this
        # is how we learn the real one when the network assigned or overrode it.
        # Adopting it as the fast-reconnect hint means the next connect requests
        # the APN that is known to work instead of re-running the cascade.  Both
        # the requested and negotiated names are kept for troubleshooting
        # (surfaced in status).
        negotiated_apn = await self._mm_bearer_apn()
        if not negotiated_apn:
            try:
                negotiated_apn = await self._qmi_get_current_apn()
            except Exception:
                negotiated_apn = ''
        self.negotiated_apn = negotiated_apn
        if negotiated_apn:
            requested_name = self.requested_apn
            if negotiated_apn != requested_name:
                # Network assigned/overrode the APN.  Credentials we held were
                # tied to the requested name, so drop them — a network-default
                # APN typically needs no auth.
                real_apn = {
                    'name': negotiated_apn,
                    'username': '',
                    'password': '',
                    'auth_type': 'none',
                }
                self.connected_apn = real_apn
                self._persist_connected_apn(real_apn)
                logger.info("Captured carrier-negotiated APN over QMI",
                           extra={'interface_number': self.interface_number,
                                  'requested_apn': requested_name,
                                  'negotiated_apn': negotiated_apn})

    async def _try_connection_with_apn(self, apn_config, sim_config):
        """Try connection using new ConnectionManager"""
        # Set proxy for connection manager
        self.connection_manager.set_proxy(self.proxy)

        # Inject runtime connection timeout so ConnectionManager enforces
        # the configured MM Simple.Connect() wait.
        sim_config_with_timeout = dict(sim_config or {})
        sim_config_with_timeout['connection_timeout'] = self._get_connection_timeout()

        # Use the extracted connection manager
        success, reason = await self.connection_manager.try_connection_with_apn(apn_config, sim_config_with_timeout)

        if success:
            # Mirror the bearer path onto self so other FSM code paths
            # that read self.bearer_path see the live value.
            self.bearer_path = self.connection_manager.get_current_bearer_path()
            # Record requested/negotiated APN for status + fast reconnect.
            # Done here — the single canonical successful-connect point — so
            # it runs for every path (initial config, runtime reconnect, SIM
            # switch), not just the initial-configuration flow.
            await self._capture_connected_apn()

        return (success, reason)

    async def _try_automatic_apn_assignment(self, sim_config):
        """Try automatic APN assignment as last resort"""
        try:
            logger.info("Attempting automatic APN assignment",
                       extra={'interface_number': self.interface_number})

            # Build minimal connection parameters - let network assign APN
            # Pass an empty APN string rather than omitting the key entirely;
            # ModemManager's 3GPP connect logic requires the 'apn' property
            # to be present even when letting the network assign one.
            connect_params = {
                'apn': Variant('s', ''),
            }

            # Only specify IP type and roaming
            pdp_type = sim_config.get('pdp_type', 'ipv4v6')
            connect_params['ip-type'] = Variant('u', self._convert_pdp_type(pdp_type))

            roaming = sim_config.get('roaming', 'enabled')
            connect_params['allow-roaming'] = Variant('b', roaming == 'enabled')

            # Let ModemManager/network handle APN assignment
            simple_iface = self.proxy.get_interface(SIMPLE_INTERFACE)
            connection_timeout = self._get_connection_timeout()
            bearer_path = await asyncio.wait_for(
                simple_iface.call_connect(connect_params),
                timeout=connection_timeout,
            )
            self.bearer_path = bearer_path

            # Verify connection
            await asyncio.sleep(5)  # Longer wait for automatic assignment
            is_connected = await self._verify_bearer_connection()

            if is_connected:
                logger.info("Automatic APN assignment successful",
                           extra={'interface_number': self.interface_number,
                                  'bearer_path': bearer_path})

                # Try to determine what APN was assigned
                await self._detect_assigned_apn()
                return True
            else:
                logger.error("Automatic APN assignment failed",
                            extra={'interface_number': self.interface_number})
                return False

        except Exception as e:
            logger.error(f"Automatic APN assignment failed: {e}",
                        extra={'interface_number': self.interface_number})
            return False

    async def _detect_assigned_apn(self):
        """Try to detect what APN was automatically assigned"""
        try:
            if not self.bearer_path:
                return

            # Get bearer properties
            introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, self.bearer_path)
            proxy = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, self.bearer_path, introspect)
            props = proxy.get_interface("org.freedesktop.DBus.Properties")

            # Try to get APN from bearer properties
            try:
                bearer_properties_variant = await props.call_get(BEARER_INTERFACE, "Properties")
                bearer_properties = bearer_properties_variant.value if bearer_properties_variant else {}
                assigned_apn = bearer_properties.get('apn', '')

                # MM only echoes the requested APN (empty on this path), so ask
                # the modem over QMI for the APN the carrier actually activated.
                if not assigned_apn:
                    assigned_apn = await self._qmi_get_current_apn() or 'Unknown'

                # Surface the network-assigned APN in status and adopt it as the
                # fast-reconnect hint (this path requests an empty APN, so MM
                # never records a name of its own).
                if assigned_apn and assigned_apn != 'Unknown':
                    self.negotiated_apn = assigned_apn
                    real_apn = {
                        'name': assigned_apn,
                        'username': '',
                        'password': '',
                        'auth_type': 'none',
                    }
                    self.connected_apn = real_apn
                    if not self.requested_apn:
                        self.requested_apn = assigned_apn
                    self._persist_connected_apn(real_apn)

                logger.info("Detected automatically assigned APN",
                           extra={'interface_number': self.interface_number,
                                  'assigned_apn': assigned_apn})

            except Exception as e:
                logger.debug(f"Could not detect assigned APN: {e}",
                            extra={'interface_number': self.interface_number})

        except Exception as e:
            logger.debug(f"APN detection failed: {e}",
                        extra={'interface_number': self.interface_number})

    def _normalize_apn_config(self, apn):
        """Normalize APN configuration to dict format (same as config service)"""
        if isinstance(apn, str):
            # Convert simple string to dict format
            return {
                'name': apn,
                'username': '',
                'password': '',
                'auth_type': 'none'
            }
        elif isinstance(apn, dict):
            # Ensure all required fields exist
            normalized = {
                'name': apn.get('name', ''),
                'username': apn.get('username', ''),
                'password': apn.get('password', ''),
                'auth_type': apn.get('auth_type', 'none')
            }
            return normalized
        else:
            # Default empty APN
            return {
                'name': '',
                'username': '',
                'password': '',
                'auth_type': 'none'
            }

    async def _check_sim_change(self, current_sim_info):
        """
        Check if SIM card has changed since last connection.
        Returns True if SIM changed, False if same SIM or no previous SIM data.
        """
        try:
            if not current_sim_info:
                logger.warning("No current SIM info available for change detection",
                              extra={'interface_number': self.interface_number})
                return False

            # If we have no previous SIM info, this is first run - save current info
            if not self.last_known_sim_info:
                logger.info("First SIM detection - saving SIM info",
                           extra={'interface_number': self.interface_number,
                                  'imsi': current_sim_info.get('imsi', 'Unknown')[:8] + '...',  # Log only first 8 digits for privacy
                                  'operator': current_sim_info.get('operator_name', 'Unknown'),
                                  'mcc_mnc': current_sim_info.get('mcc_mnc', 'Unknown')})
                self.last_known_sim_info = current_sim_info.copy()
                self.sim_changed = False
                # Cache per-slot identity
                slot = self.current_active_sim or 1
                self.sim_slot_info_cache[slot] = {
                    'imsi': current_sim_info.get('imsi', ''),
                    'iccid': current_sim_info.get('sim_identifier', ''),
                    'operator': current_sim_info.get('operator_name', ''),
                    'mcc_mnc': current_sim_info.get('mcc_mnc', ''),
                    'spn': current_sim_info.get('spn', ''),
                }
                return False

            # Compare key SIM identifiers
            current_imsi = current_sim_info.get('imsi', '')
            current_mcc_mnc = current_sim_info.get('mcc_mnc', '')
            current_operator = current_sim_info.get('operator_name', '')

            last_imsi = self.last_known_sim_info.get('imsi', '')
            last_mcc_mnc = self.last_known_sim_info.get('mcc_mnc', '')
            last_operator = self.last_known_sim_info.get('operator_name', '')

            # Check for changes in IMSI (most reliable) or MCC/MNC
            sim_changed = False
            change_reasons = []

            if current_imsi != last_imsi and current_imsi and last_imsi:
                sim_changed = True
                change_reasons.append("IMSI changed")

            if current_mcc_mnc != last_mcc_mnc and current_mcc_mnc and last_mcc_mnc:
                sim_changed = True
                change_reasons.append(f"MCC/MNC changed from {last_mcc_mnc} to {current_mcc_mnc}")

            if current_operator != last_operator and current_operator and last_operator:
                # Operator name change alone might not indicate SIM change (roaming)
                # but combined with other changes it's significant
                if sim_changed:
                    change_reasons.append(f"Operator changed from {last_operator} to {current_operator}")

            if sim_changed:
                logger.warning("SIM card change detected - will use fresh APN discovery",
                              extra={'interface_number': self.interface_number,
                                     'changes': ', '.join(change_reasons),
                                     'current_operator': current_operator,
                                     'previous_operator': last_operator})

                # Update stored SIM info
                self.last_known_sim_info = current_sim_info.copy()
                self.sim_changed = True
                self.connected_apn = None  # Invalidate — new SIM needs fresh discovery
                self._clear_persisted_apn()  # Don't reuse stale APN after SIM swap
                # Cache per-slot identity for the new SIM
                slot = self.current_active_sim or 1
                self.sim_slot_info_cache[slot] = {
                    'imsi': current_sim_info.get('imsi', ''),
                    'iccid': current_sim_info.get('sim_identifier', ''),
                    'operator': current_sim_info.get('operator_name', ''),
                    'mcc_mnc': current_sim_info.get('mcc_mnc', ''),
                    'spn': current_sim_info.get('spn', ''),
                }
                return True
            else:
                logger.debug("SIM unchanged since last connection",
                            extra={'interface_number': self.interface_number,
                                   'operator': current_operator,
                                   'mcc_mnc': current_mcc_mnc})
                self.sim_changed = False
                return False

        except Exception as e:
            logger.error(f"Error checking SIM change: {e}",
                        extra={'interface_number': self.interface_number})
            # On error, assume no change to be safe
            return False

    async def _try_apn_candidates_from_discovery(self, sim_config):
        """Discover APN candidates from the Android DB and try them via the canonical loop.

        This is a thin discovery wrapper around _try_apn_candidates(); all
        reason-aware escalation and timeout handling lives there.
        """
        try:
            sim_info = await self._get_sim_information()
            if not sim_info:
                logger.warning("No SIM info available for APN discovery",
                              extra={'interface_number': self.interface_number})
                return (False, 'no_sim_info')

            apn_candidates = await self._discover_apn_candidates(sim_info, sim_config)
            if not apn_candidates:
                logger.warning("No APN candidates discovered",
                              extra={'interface_number': self.interface_number})
                return (False, 'no_candidates')

            logger.info(f"Discovered {len(apn_candidates)} APN candidates, delegating to canonical loop",
                       extra={'interface_number': self.interface_number})
            return await self._try_apn_candidates(apn_candidates, sim_config, sim_info)

        except Exception as e:
            logger.error(f"APN discovery phase failed: {e}",
                        extra={'interface_number': self.interface_number})
            return (False, 'discovery_error')

    async def _cleanup_bearers(self):
        """Disconnect all bearers via MM Simple interface (best-effort, non-fatal).

        Called between APN attempts to prevent ModemManager returning
        "operation already in progress" when the previous attempt left a
        partial bearer open.
        """
        try:
            if self.proxy:
                simple_iface = self.proxy.get_interface(SIMPLE_INTERFACE)
                await asyncio.wait_for(simple_iface.call_disconnect('/'), timeout=5.0)
                logger.debug("Bearers disconnected between APN attempts",
                            extra={'interface_number': self.interface_number})
                await asyncio.sleep(1)  # Let MM process the disconnect
        except Exception as cleanup_err:
            logger.debug(f"Bearer cleanup (non-fatal): {cleanup_err}",
                        extra={'interface_number': self.interface_number})

    def _convert_pdp_type(self, pdp_type):
        """Convert PDP type to ModemManager IP family constant"""
        pdp_mapping = {
            'ipv4': 1,      # MM_BEARER_IP_FAMILY_IPV4
            'ipv6': 2,      # MM_BEARER_IP_FAMILY_IPV6
            'ipv4v6': 3     # MM_BEARER_IP_FAMILY_IPV4V6
        }
        return pdp_mapping.get(pdp_type, 1)  # Default to IPv4

    def _convert_auth_type(self, auth_type):
        """Convert auth type to ModemManager authentication constant"""
        auth_mapping = {
            'none': 0,      # MM_BEARER_ALLOWED_AUTH_NONE
            'pap': 1,       # MM_BEARER_ALLOWED_AUTH_PAP
            'chap': 2,      # MM_BEARER_ALLOWED_AUTH_CHAP
            'pap-chap': 3   # MM_BEARER_ALLOWED_AUTH_PAP | MM_BEARER_ALLOWED_AUTH_CHAP
        }
        return auth_mapping.get(auth_type, 0)  # Default to none

    async def _verify_bearer_connection(self):
        """Verify that the bearer connection is working"""
        try:
            if not self.bearer_path:
                logger.warning("No bearer path available for verification",
                              extra={'interface_number': self.interface_number})
                return False

            # Get bearer properties to verify connection
            introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, self.bearer_path)
            proxy = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, self.bearer_path, introspect)
            props = proxy.get_interface("org.freedesktop.DBus.Properties")

            # Check if bearer is connected - FIX: Extract .value from Variant
            connected_variant = await props.call_get(BEARER_INTERFACE, "Connected")
            connected = connected_variant.value

            interface_variant = await props.call_get(BEARER_INTERFACE, "Interface")
            interface_name = interface_variant.value

            # Store interface name for later use in interface management
            self.interface_name = interface_name

            if connected:
                logger.info("Bearer connection verified",
                           extra={'interface_number': self.interface_number,
                                  'bearer_path': self.bearer_path,
                                  'interface_name': interface_name,
                                  'connected': connected})

                # Get IP configuration details - FIX: Correct IP config access
                try:
                    ipv4_config_variant = await props.call_get(BEARER_INTERFACE, "Ip4Config")
                    ipv4_config = ipv4_config_variant.value
                    if ipv4_config and 'address' in ipv4_config:
                        ip_address = ipv4_config['address']
                        logger.info("IPv4 configuration obtained",
                                   extra={'interface_number': self.interface_number,
                                          'ip_address': ip_address})
                except Exception as ip_e:
                    logger.debug(f"Could not get IP configuration: {ip_e}",
                                extra={'interface_number': self.interface_number})

                return True  # FIX: Return boolean result
            else:
                logger.warning("Bearer created but not connected",
                              extra={'interface_number': self.interface_number,
                                     'bearer_path': self.bearer_path,
                                     'connected': connected})
                return False  # FIX: Return boolean result

        except Exception as e:
            logger.error(f"Bearer connection verification failed: {e}",
                        extra={'interface_number': self.interface_number,
                               'bearer_path': self.bearer_path})
            # FIX: Be more lenient - if verification fails due to error, assume connection is OK
            # This prevents disconnecting working connections due to verification issues
            logger.info("Assuming connection is working despite verification error",
                       extra={'interface_number': self.interface_number})
            return True

    def _get_active_sim_data_config(self):
        """Get data limit configuration for the currently active SIM slot.

        Returns per-SIM data config if available, falls back to global config.
        """
        active_slot = self.current_active_sim or (
            self.config.get('primary_sim_slot', 1) if self.config else 1)
        return self._get_sim_data_config(active_slot)

    def _get_sim_data_config(self, slot: int) -> dict:
        """Get data limit configuration for an arbitrary SIM slot.

        Per-SIM values take priority; falls back to global config, then to
        DEFAULT_DATA_CONFIG.  Used by both the active-SIM monitor loop and
        the status reporter (which needs to surface per-slot config for
        inactive slots in the show command).
        """
        sim_slots = self.config.get('sim_slots', []) if self.config else []
        sim_config = next((s for s in sim_slots if s.get('slot') == slot), {})

        def _fallback(key, default):
            if self.config and key in self.config:
                return self.config.get(key, default)
            return default

        return {
            'data_limit_size': sim_config.get(
                'data_limit_size',
                _fallback('data_limit_size', DEFAULT_DATA_CONFIG['data_limit_size'])),
            'data_limit_action': sim_config.get(
                'data_limit_action',
                _fallback('data_limit_action', DEFAULT_DATA_CONFIG['data_limit_action'])),
            'data_limit_warning': sim_config.get(
                'data_limit_warning',
                _fallback('data_limit_warning',
                          list(DEFAULT_DATA_CONFIG['data_limit_warning']))),
            'data_limit_billing_date': sim_config.get(
                'data_limit_billing_date',
                _fallback('data_limit_billing_date',
                          DEFAULT_DATA_CONFIG['data_limit_billing_date'])),
        }

    async def monitor_data_usage(self):
        """Monitor data usage limits per-SIM with failover support.

        Reads data limits from the active SIM's per-slot config (falls back to
        global config). Supports actions: none, disable, sim-failover, sim-failover-sticky.
        """
        if not self.bearer_path:
            return

        # Get per-SIM data config
        data_cfg = self._get_active_sim_data_config()
        data_limit = data_cfg['data_limit_size']
        data_action = data_cfg['data_limit_action']
        data_warning_thresholds = sorted(data_cfg.get('data_limit_warning', []))
        billing_date = data_cfg['data_limit_billing_date']

        logger.info("Starting per-SIM data usage monitoring",
                   extra={'interface_number': self.interface_number,
                          'bearer_path': self.bearer_path,
                          'active_sim': self.current_active_sim,
                          'data_limit_gb': data_limit / (1024*1024*1024) if data_limit else 0,
                          'action': data_action,
                          'warning_thresholds': data_warning_thresholds,
                          'billing_date': billing_date})

        # Load persisted cumulative usage for this SIM
        cumulative_bytes = self._load_persisted_usage()
        # Record the baseline so _flush_active_usage() can persist in-flight
        # session bytes to this slot (e.g. before a SIM switch) using the same
        # cumulative + session formula, without double counting.
        self._usage_baseline_bytes = cumulative_bytes
        self._usage_baseline_slot = self._current_usage_slot()
        warnings_logged = set()   # tracks which pct thresholds have been logged
        limit_logged = False

        try:
            # Monitor while connected
            while self.machine.current_state == ModemState.CONNECTED.value:
                try:
                    # Check data usage statistics from bearer
                    introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, self.bearer_path)
                    proxy = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, self.bearer_path, introspect)
                    props = proxy.get_interface("org.freedesktop.DBus.Properties")

                    try:
                        stats_variant = await props.call_get(BEARER_INTERFACE, "Stats")
                        if stats_variant and stats_variant.value:
                            stats = stats_variant.value
                            rx_bytes = stats.get('rx-bytes', 0)
                            tx_bytes = stats.get('tx-bytes', 0)
                            session_bytes = rx_bytes + tx_bytes
                            total_bytes = cumulative_bytes + session_bytes

                            # Cache the live session so an unplanned drop (e.g.
                            # modem removal) can still salvage usage even after
                            # the bearer becomes unreadable.
                            self._last_session_bytes = session_bytes
                            self._last_session_slot = self._current_usage_slot()

                            logger.info("Data usage check",
                                       extra={'interface_number': self.interface_number,
                                              'active_sim': self.current_active_sim,
                                              'session_mb': session_bytes / (1024*1024),
                                              'cumulative_mb': cumulative_bytes / (1024*1024),
                                              'total_mb': total_bytes / (1024*1024),
                                              'limit_gb': data_limit / (1024*1024*1024)})

                            # Persist current usage periodically
                            self._persist_usage(total_bytes)

                            usage_pct = (total_bytes / data_limit) * 100 if data_limit > 0 else 0

                            # Check per-SIM data-limit warning thresholds
                            if data_limit > 0:
                                for threshold in data_warning_thresholds:
                                    if usage_pct >= threshold and threshold not in warnings_logged:
                                        warnings_logged.add(threshold)
                                        logger.warning(
                                            f"Data usage warning: {usage_pct:.1f}% of limit reached "
                                            f"(warning threshold: {threshold}%)",
                                            extra={'interface_number': self.interface_number,
                                                   'active_sim': self.current_active_sim,
                                                   'usage_pct': round(usage_pct, 1),
                                                   'warning_threshold': threshold,
                                                   'total_mb': total_bytes / (1024*1024),
                                                   'limit_gb': data_limit / (1024*1024*1024)})
                                        self._emit_alert(
                                            alert_type='data_usage_warning',
                                            severity='warning',
                                            message=f'Data usage crossed {threshold}% threshold',
                                            warning_threshold=float(threshold),
                                            usage_percent=round(usage_pct, 1),
                                            active_sim_slot=self.current_active_sim or 0,
                                            total_bytes=int(total_bytes),
                                            data_limit_bytes=int(data_limit),
                                            action=data_action,
                                        )

                            # Check if limit exceeded
                            if data_limit > 0 and total_bytes >= data_limit:
                                if not limit_logged:
                                    limit_logged = True
                                    logger.warning(
                                        "Data usage limit reached",
                                        extra={'interface_number': self.interface_number,
                                               'active_sim': self.current_active_sim,
                                               'usage_gb': total_bytes / (1024*1024*1024),
                                               'limit_gb': data_limit / (1024*1024*1024),
                                               'action': data_action})
                                    self._emit_alert(
                                        alert_type='data_usage_limit_reached',
                                        severity='error',
                                        message='Data usage limit reached',
                                        active_sim_slot=self.current_active_sim or 0,
                                        total_bytes=int(total_bytes),
                                        data_limit_bytes=int(data_limit),
                                        usage_percent=round(usage_pct, 1),
                                        action=data_action,
                                    )

                                if data_action in ('sim-failover', 'sim-failover-sticky'):
                                    # Switch to alternative SIM
                                    if data_action == 'sim-failover-sticky':
                                        self.failback_suppressed_by_data_limit = True
                                        self._sticky_failover_timestamp = datetime.datetime.now()
                                        logger.info("Sticky failover: failback suppressed until billing cycle resets",
                                                   extra={'interface_number': self.interface_number,
                                                          'active_sim': self.current_active_sim})
                                    await self._handle_data_limit_failover()
                                    break
                                elif data_action in ('disconnect', 'disable'):
                                    self.transition(ModemEvent.USAGE_LIMIT_EXCEEDED)
                                    break
                                # 'none' (default) — log warning but take no action
                        else:
                            logger.debug("Bearer statistics not available",
                                       extra={'interface_number': self.interface_number})

                    except Exception as stats_e:
                        logger.debug(f"Could not retrieve bearer statistics: {stats_e}",
                                   extra={'interface_number': self.interface_number})

                    monitoring_interval = self.config.get('data_usage_monitoring_interval', 30) if self.config else 30
                    await asyncio.sleep(monitoring_interval)

                except Exception as e:
                    logger.error(f"Data usage monitoring error: {e}",
                               extra={'interface_number': self.interface_number})
                    await asyncio.sleep(60)

        except Exception as e:
            logger.error(f"Failed to initialize data usage monitoring: {e}",
                        extra={'interface_number': self.interface_number})

    async def _handle_data_limit_failover(self):
        """Handle SIM failover triggered by data limit exceeded on current SIM.

        Delegates to the shared, lock-protected failover executor
        (``_failover_to_alternate_sim``) so the data-limit path gets the same
        real D-Bus SIM probing, cooldown/backoff gating and reentrancy guards
        as the missing-SIM and signal-loss triggers — no duplicated switch
        logic.  If no failover is possible (failover disabled, blocked by
        cooldown/backoff, no usable alternate SIM present, or the target slot
        disabled) the modem is disconnected instead, because staying connected
        on a SIM that is over its data cap is not acceptable.

        The sticky-hold bookkeeping (``failback_suppressed_by_data_limit``) is
        set by the data-usage monitor before this is called, so failback will
        not return to the capped SIM until the billing cycle resets.
        """
        try:
            if not self._is_sim_failover_enabled():
                logger.warning("Data limit sim-failover requested but sim_failover is "
                              "globally disabled, disconnecting instead",
                              extra={'interface_number': self.interface_number})
                self.transition(ModemEvent.USAGE_LIMIT_EXCEEDED)
                return

            logger.warning("Data limit exceeded - initiating SIM failover",
                          extra={'interface_number': self.interface_number,
                                 'current_sim': self.current_active_sim})

            success = await self._failover_to_alternate_sim(
                'data_limit', '_handle_data_limit_failover')

            if not success:
                logger.warning("Data limit failover could not switch SIM "
                              "(no usable alternate / blocked) — disconnecting instead",
                              extra={'interface_number': self.interface_number,
                                     'current_sim': self.current_active_sim})
                self.transition(ModemEvent.USAGE_LIMIT_EXCEEDED)

        except Exception as e:
            logger.error(f"Data limit failover failed: {e}",
                        extra={'interface_number': self.interface_number})
            self.transition(ModemEvent.CONNECTION_FAILED)

    # ── Per-SIM persistent usage tracking ────────────────────────────────────

    def _usage_file_path(self) -> str:
        """Return the path to the per-interface usage persistence file.

        Uses /var/lib/vyos/wwan/ for persistence across reboots and service
        restarts.  The directory is created on first write by _persist_usage().
        """
        return f"/var/lib/vyos/wwan/wwan{self.interface_number}_usage.json"

    def _load_all_persisted_usage(self) -> dict:
        """Return the full per-slot usage dict from disk (no billing-cycle reset).

        Used by the status reporter so that the show command can display the
        cumulative usage of *all* SIM slots, not just the active one.  Returns
        an empty dict if the file is missing or unreadable.
        """
        try:
            path = self._usage_file_path()
            with open(path, 'r') as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, PermissionError):
            return {}

    def _load_persisted_usage(self) -> int:
        """Load cumulative byte count for the current active SIM from disk.

        The file is a JSON dict keyed by SIM slot number, e.g.:
            {"1": {"bytes": 123456789, "billing_date": 1, "last_updated": "..."}, "2": ...}
        Handles billing-cycle resets automatically.
        """
        slot = self._current_usage_slot()
        slot_key = str(slot)
        data_cfg = self._get_active_sim_data_config()
        billing_date = data_cfg['data_limit_billing_date']

        try:
            path = self._usage_file_path()
            with open(path, 'r') as f:
                usage_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, PermissionError):
            return 0

        slot_data = usage_data.get(slot_key, {})
        stored_bytes = slot_data.get('bytes', 0)
        last_updated = slot_data.get('last_updated', '')

        # Check if we've crossed a billing cycle boundary since last update
        try:
            now = datetime.datetime.now()
            if last_updated:
                last_dt = datetime.datetime.fromisoformat(last_updated)
                # Reset if billing day has passed since last update
                if self._billing_cycle_crossed(last_dt, now, billing_date):
                    logger.info("Billing cycle crossed - resetting cumulative usage",
                               extra={'interface_number': self.interface_number,
                                      'sim_slot': slot_key,
                                      'previous_bytes': stored_bytes,
                                      'billing_date': billing_date})
                    # Clear sticky failover hold when billing cycle resets
                    if self.failback_suppressed_by_data_limit:
                        self.failback_suppressed_by_data_limit = False
                        logger.info("Billing cycle reset lifted sim-failover-sticky hold — "
                                   "failback may resume",
                                   extra={'interface_number': self.interface_number,
                                          'sim_slot': slot_key})
                    self._persist_usage(0)
                    return 0
        except Exception:
            pass  # If date parsing fails, use stored value

        logger.debug(f"Loaded persisted usage for slot {slot_key}: {stored_bytes / (1024*1024):.1f} MB",
                    extra={'interface_number': self.interface_number})
        return stored_bytes

    def _persist_usage(self, total_bytes: int, slot: int = None):
        """Persist cumulative usage for a SIM slot to disk.

        Defaults to the current active slot; pass ``slot`` explicitly to record
        usage for a slot that is no longer active (e.g. salvaging the outgoing
        SIM's session after a failover).
        """
        if slot is None:
            slot = self._current_usage_slot()
        slot_key = str(slot)
        data_cfg = self._get_sim_data_config(slot)
        path = self._usage_file_path()

        # Read existing data
        try:
            with open(path, 'r') as f:
                usage_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, PermissionError):
            usage_data = {}

        # Update this SIM slot's entry
        usage_data[slot_key] = {
            'bytes': total_bytes,
            'billing_date': data_cfg['data_limit_billing_date'],
            'slot': slot,
            'last_updated': datetime.datetime.now().isoformat(),
        }

        # Write atomically
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp_path = path + '.tmp'
            with open(tmp_path, 'w') as f:
                json.dump(usage_data, f, indent=2)
            os.replace(tmp_path, path)
        except Exception as e:
            logger.warning(f"Could not persist usage data: {e}",
                          extra={'interface_number': self.interface_number})

    async def _flush_active_usage(self, reason: str = 'flush'):
        """Persist the in-flight session bytes to the active SIM's usage record.

        monitor_data_usage() only persists on its polling interval, so a SIM
        that is active only briefly (e.g. a quick failover, or a modem that is
        removed before the first poll) can lose its whole session because the
        monitor never persisted before the bearer was torn down.  Call this on
        every drop path to fold the current session into that slot's total.

        Prefers a fresh read of the live bearer; if the bearer is already gone
        (modem removed) it falls back to the last session byte count cached by
        the monitor loop / status builder, so usage is still salvaged.

        Uses the same ``baseline + session`` formula as monitor_data_usage()
        and only ever increases the on-disk total, so repeated flushes / a
        later monitor poll never double count or regress the stored value.
        """
        slot = self._current_usage_slot()
        # Prefer the baseline captured by the running monitor; fall back to the
        # on-disk value (monitor has not persisted this session yet, so disk
        # still holds the pre-session cumulative).
        if self._usage_baseline_slot == slot and self._usage_baseline_bytes is not None:
            baseline = self._usage_baseline_bytes
        else:
            baseline = self._load_persisted_usage()

        session_bytes = None
        if self.bearer_path:
            try:
                introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, self.bearer_path)
                proxy = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, self.bearer_path, introspect)
                props = proxy.get_interface("org.freedesktop.DBus.Properties")
                stats_variant = await props.call_get(BEARER_INTERFACE, "Stats")
                if stats_variant and stats_variant.value:
                    stats = stats_variant.value
                    session_bytes = stats.get('rx-bytes', 0) + stats.get('tx-bytes', 0)
            except Exception as e:
                logger.debug(f"Could not read live bearer stats to flush usage: {e}",
                            extra={'interface_number': self.interface_number})

        # Live read unavailable (bearer gone) — fall back to the cached session
        # captured during the session by the monitor loop / status builder.
        if session_bytes is None:
            if self._last_session_slot == slot and self._last_session_bytes:
                session_bytes = self._last_session_bytes
                logger.info("Live bearer unreadable — salvaging cached session usage",
                           extra={'interface_number': self.interface_number,
                                  'reason': reason,
                                  'usage_tracking_slot': slot,
                                  'cached_session_bytes': session_bytes})
            else:
                logger.debug("No live or cached session usage to flush",
                            extra={'interface_number': self.interface_number,
                                   'reason': reason,
                                   'usage_tracking_slot': slot})
                return

        total_bytes = baseline + session_bytes
        # Never regress a larger value already persisted (e.g. by a monitor
        # poll that ran after the cache was captured).
        existing = self._load_all_persisted_usage().get(str(slot), {})
        existing_bytes = existing.get('bytes', 0) if isinstance(existing, dict) else 0
        if total_bytes <= existing_bytes:
            return

        self._persist_usage(total_bytes, slot=slot)
        logger.info("Flushed in-flight session usage to SIM slot",
                   extra={'interface_number': self.interface_number,
                          'reason': reason,
                          'usage_tracking_slot': slot,
                          'session_bytes': session_bytes,
                          'total_bytes': total_bytes})

    @staticmethod
    def _billing_cycle_crossed(last_dt, now_dt, billing_day: int) -> bool:
        """Return True if a billing-cycle boundary (billing_day of month) was
        crossed between last_dt and now_dt."""
        # Clamp billing_day to valid range
        billing_day = max(1, min(28, billing_day))

        # Build the most recent billing boundary relative to now
        try:
            if now_dt.day >= billing_day:
                # Boundary is billing_day of current month
                boundary = now_dt.replace(day=billing_day, hour=0, minute=0, second=0, microsecond=0)
            else:
                # Boundary is billing_day of previous month
                month = now_dt.month - 1 if now_dt.month > 1 else 12
                year = now_dt.year if now_dt.month > 1 else now_dt.year - 1
                boundary = datetime.datetime(year, month, billing_day, 0, 0, 0)
        except ValueError:
            return False  # Shouldn't happen with billing_day 1-28

        return last_dt < boundary <= now_dt

    async def _recover_bearer_connection(self):
        """Attempt to recover bearer connection with enhanced signal validation"""
        try:
            logger.info("Attempting enhanced bearer connection recovery",
                       extra={'interface_number': self.interface_number,
                              'current_bearer': self.bearer_path})

            if not self.proxy:
                logger.error("No modem proxy available for bearer recovery")
                return False

            # 🆕 Enhanced: Check signal quality before attempting recovery
            signal_adequate = await self._check_signal_adequacy_for_reconnection()
            if not signal_adequate:
                logger.warning("Signal inadequate for reconnection - waiting for improvement",
                              extra={'interface_number': self.interface_number})

                # Wait for signal improvement with timeout
                # 🆕 Enhanced: Wait for adequate signal before reconnection
                if not await self._wait_for_adequate_signal():  # Uses configurable timeout
                    logger.warning("Signal did not improve - attempting recovery anyway",
                                  extra={'interface_number': self.interface_number})

            # Check if bearer still exists
            try:
                props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
                bearers_variant = await props.call_get(MODEM_INTERFACE, "Bearers")
                bearers = bearers_variant.value if bearers_variant else []

                if self.bearer_path not in bearers:
                    logger.warning("Current bearer no longer exists, attempting reconnection",
                                  extra={'interface_number': self.interface_number,
                                         'old_bearer': self.bearer_path,
                                         'available_bearers': bearers})

                    # Bearer is gone - try to reconnect with signal validation
                    return await self._enhanced_reconnection_attempt()

            except Exception as bearer_check_e:
                logger.error(f"Failed to check bearer status: {bearer_check_e}",
                            extra={'interface_number': self.interface_number})

            # Try to refresh bearer interface
            try:
                introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, self.bearer_path)
                proxy = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, self.bearer_path, introspect)
                props = proxy.get_interface("org.freedesktop.DBus.Properties")

                # Test if interface is responsive by getting Connected property
                await props.call_get(BEARER_INTERFACE, "Connected")

                logger.info("Bearer interface is responsive after refresh",
                           extra={'interface_number': self.interface_number})
                return True

            except Exception as refresh_e:
                logger.error(f"Bearer interface refresh failed: {refresh_e}",
                            extra={'interface_number': self.interface_number})

            # If all else fails, try full reconnection with signal validation
            logger.warning("Attempting full reconnection as last resort",
                          extra={'interface_number': self.interface_number})

            return await self._enhanced_reconnection_attempt()

        except Exception as e:
            logger.error(f"Enhanced bearer recovery failed: {e}",
                        extra={'interface_number': self.interface_number})
            return False

    async def _handle_registration_recovery(self):
        """Handle bearer reconnection after network registration recovery"""
        try:
            # Give the interface a moment to come up
            await asyncio.sleep(1)

            logger.info("🔄 Checking bearer status after registration recovery",
                       extra={'interface_number': self.interface_number})

            # Check if bearer is already connected
            is_connected = await self._is_bearer_connected()

            if is_connected:
                logger.info("✅ Bearer already connected after registration recovery",
                           extra={'interface_number': self.interface_number})
                # Apply IP configuration from existing bearer
                await self._apply_bearer_ip_configuration()
                return True

            logger.info("🔌 Bearer not connected - initiating reconnection after registration recovery",
                       extra={'interface_number': self.interface_number})

            # Use the existing enhanced reconnection logic
            success = await self._enhanced_reconnection_attempt()

            if success:
                logger.info("✅ Bearer reconnection successful after registration recovery",
                           extra={'interface_number': self.interface_number})
                # Apply bearer IP configuration to the network interface
                # (the reconnection path through apply_modem_configuration does NOT
                #  call _apply_bearer_ip_configuration when going through APN discovery)
                await self._apply_bearer_ip_configuration()
            else:
                logger.warning("⚠️ Bearer reconnection failed after registration recovery",
                              extra={'interface_number': self.interface_number})

            return success

        except Exception as e:
            logger.error(f"Error handling registration recovery: {e}",
                        extra={'interface_number': self.interface_number})
            return False

    @staticmethod
    def _select_signal_metric(signal_detail, signal_dbm, rssi_threshold, rsrp_threshold):
        """Pick the comparison metric + matching threshold for the active RAT.

        RSRP is the canonical 3GPP coverage metric for LTE/5G-NR; RSSI is the
        legacy wideband metric for 2G/3G. The two scales differ by ~20 dB, so
        each is compared against its own configured threshold.

        Args:
            signal_detail: dict from _get_detailed_signal_quality with keys
                'technology', 'rssi', 'rsrp' (values may be '' when absent).
            signal_dbm: the collapsed dBm value (fallback when the preferred
                metric field is unavailable).
            rssi_threshold: configured RSSI threshold (dBm).
            rsrp_threshold: configured RSRP threshold (dBm).

        Returns:
            (metric_name, metric_dbm, threshold_dbm)
        """
        def _num(value):
            try:
                if value is None or value == '':
                    return None
                return float(value)
            except (TypeError, ValueError):
                return None

        detail = signal_detail or {}
        technology = (detail.get('technology') or '').upper()
        rsrp = _num(detail.get('rsrp'))
        rssi = _num(detail.get('rssi'))

        # LTE / 5G-NR: prefer RSRP (3GPP coverage metric) when available.
        if technology in ('LTE', '5G NR', 'NR5G', '5G') and rsrp is not None:
            return 'rsrp', rsrp, rsrp_threshold

        # 2G/3G or any RAT that only exposes RSSI.
        if rssi is not None:
            return 'rssi', rssi, rssi_threshold

        # No technology hint but an RSRP value is present (e.g. LTE-only modem).
        if rsrp is not None:
            return 'rsrp', rsrp, rsrp_threshold

        # Last resort: compare the collapsed value against the RSSI threshold
        # (matches legacy behaviour and the documented default scale).
        return 'rssi', signal_dbm, rssi_threshold

    async def _check_signal_adequacy_for_reconnection(self):
        """Check if signal strength is adequate for reliable reconnection.

        Signal strength is reported on different scales depending on the
        active radio technology, so a single dBm threshold cannot be applied
        uniformly:

          * 2G/3G (GSM/UMTS/CDMA/EVDO) report wideband RSSI.
          * LTE / 5G-NR report RSRP, the 3GPP per-resource-element coverage
            metric, which sits roughly 20 dB below RSSI for the same radio
            conditions.

        We therefore pick the configured threshold that matches the metric
        actually reported by the modem (rssi vs rsrp).
        """
        try:
            # If enhanced reconnection is disabled, always return True
            if not getattr(self, 'enhanced_reconnection', True):
                return True

            buffer_dbm = getattr(self, 'signal_strength_buffer', 5)
            rssi_threshold = getattr(self, 'reconnection_signal_threshold_rssi', -85)
            rsrp_threshold = getattr(self, 'reconnection_signal_threshold_rsrp', -105)

            signal_percent, signal_dbm, signal_detail = await self._get_detailed_signal_quality()

            if signal_percent is None or signal_dbm is None:
                logger.warning("Cannot read signal strength - assuming adequate for reconnection",
                              extra={'interface_number': self.interface_number})
                return True

            # Update signal tracker for LED indication (rolling average + level change detection)
            if self.signal_tracker and signal_dbm:
                await self.signal_tracker.update(signal_dbm, signal_detail)

            # Select the metric + matching threshold for the active technology.
            metric_name, metric_dbm, min_signal_dbm = self._select_signal_metric(
                signal_detail, signal_dbm, rssi_threshold, rsrp_threshold)
            effective_threshold = min_signal_dbm - buffer_dbm

            adequate = metric_dbm >= effective_threshold

            logger.info("Enhanced signal adequacy check for reconnection",
                       extra={'interface_number': self.interface_number,
                              'signal_percent': signal_percent,
                              'technology': (signal_detail or {}).get('technology'),
                              'metric': metric_name,
                              'metric_dbm': metric_dbm,
                              'threshold_dbm': min_signal_dbm,
                              'effective_threshold': effective_threshold,
                              'buffer_dbm': buffer_dbm,
                              'adequate': adequate})

            return adequate

        except Exception as e:
            logger.error(f"Signal adequacy check failed: {e}",
                        extra={'interface_number': self.interface_number})
            return True  # Assume adequate if check fails

    async def _enable_signal_monitoring(self):
        """Enable ModemManager signal monitoring for accurate dBm readings"""
        try:
            if not self.proxy:
                logger.warning("Cannot enable signal monitoring - no modem proxy",
                             extra={'interface_number': self.interface_number})
                return False

            # Use the Signal interface to setup signal monitoring
            # This is equivalent to: mmcli -m 0 --signal-setup=5
            signal_interface = self.proxy.get_interface("org.freedesktop.ModemManager1.Modem.Signal")

            # Setup signal monitoring with 5-second refresh rate
            await signal_interface.call_setup(5)  # 5 seconds refresh rate

            logger.info("Signal monitoring enabled (5-second refresh)",
                       extra={'interface_number': self.interface_number})
            return True

        except Exception as e:
            logger.warning(f"Could not enable signal monitoring: {e}",
                         extra={'interface_number': self.interface_number})
            logger.debug("Signal quality will fall back to percentage-based estimation",
                        extra={'interface_number': self.interface_number})
            return False

    async def _get_detailed_signal_quality(self):
        """Get detailed signal quality metrics using actual dBm readings.

        Returns (signal_percent, signal_dbm, signal_detail) where
        signal_detail is a dict with keys: rssi, rsrp, rsrq, snr,
        technology (or None if unavailable).
        """
        try:
            if not self.proxy:
                return None, None, None

            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")

            # Get signal quality percentage
            # SignalQuality is (uint32 percent, bool recently_updated)
            signal_percent = 0
            try:
                signal_quality_variant = await props.call_get(MODEM_INTERFACE, "SignalQuality")
                if signal_quality_variant and signal_quality_variant.value:
                    sq = signal_quality_variant.value
                    signal_percent = sq[0] if isinstance(sq, (list, tuple)) and sq else sq
            except Exception as e:
                logger.debug(f"Could not get signal quality percentage: {e}",
                           extra={'interface_number': self.interface_number})

            # Get actual dBm readings from Signal interface
            signal_dbm = None
            signal_detail = None
            try:
                def _extract_val(signals, key):
                    """Safely extract a numeric value from a signal dict."""
                    if key in signals:
                        v = signals[key]
                        return v.value if hasattr(v, 'value') else v
                    return None

                # Get LTE signal metrics from Signal interface
                lte_signal_variant = await props.call_get("org.freedesktop.ModemManager1.Modem.Signal", "Lte")
                if lte_signal_variant and lte_signal_variant.value:
                    lte_signals = lte_signal_variant.value

                    # Try RSSI first (most common)
                    if 'rssi' in lte_signals:
                        signal_dbm = _extract_val(lte_signals, 'rssi')
                        logger.debug(f"Got RSSI signal: {signal_dbm} dBm",
                                   extra={'interface_number': self.interface_number})
                    # Fall back to RSRP for LTE
                    elif 'rsrp' in lte_signals:
                        signal_dbm = _extract_val(lte_signals, 'rsrp')
                        logger.debug(f"Got RSRP signal: {signal_dbm} dBm",
                                   extra={'interface_number': self.interface_number})

                    signal_detail = {
                        'technology': 'LTE',
                        'rssi': _extract_val(lte_signals, 'rssi') or '',
                        'rsrp': _extract_val(lte_signals, 'rsrp') or '',
                        'rsrq': _extract_val(lte_signals, 'rsrq') or '',
                        'snr': _extract_val(lte_signals, 'snr') or '',
                    }

                # Try other technologies if LTE not available
                if signal_dbm is None:
                    # Try 5G NR signals first (most modern)
                    try:
                        nr5g_signal_variant = await props.call_get("org.freedesktop.ModemManager1.Modem.Signal", "Nr5g")
                        if nr5g_signal_variant and nr5g_signal_variant.value:
                            nr5g_signals = nr5g_signal_variant.value
                            # 5G typically uses RSRP as primary metric
                            if 'rsrp' in nr5g_signals:
                                signal_dbm = _extract_val(nr5g_signals, 'rsrp')
                                logger.debug(f"Got 5G NR RSRP signal: {signal_dbm} dBm",
                                           extra={'interface_number': self.interface_number})
                            elif 'rssi' in nr5g_signals:
                                signal_dbm = _extract_val(nr5g_signals, 'rssi')
                                logger.debug(f"Got 5G NR RSSI signal: {signal_dbm} dBm",
                                           extra={'interface_number': self.interface_number})

                            signal_detail = {
                                'technology': '5G NR',
                                'rssi': _extract_val(nr5g_signals, 'rssi') or '',
                                'rsrp': _extract_val(nr5g_signals, 'rsrp') or '',
                                'rsrq': _extract_val(nr5g_signals, 'rsrq') or '',
                                'snr': _extract_val(nr5g_signals, 'snr') or '',
                            }
                    except Exception:
                        pass

                    # Try UMTS signals (3G)
                    if signal_dbm is None:
                        try:
                            umts_signal_variant = await props.call_get("org.freedesktop.ModemManager1.Modem.Signal", "Umts")
                            if umts_signal_variant and umts_signal_variant.value:
                                umts_signals = umts_signal_variant.value
                                if 'rssi' in umts_signals:
                                    signal_dbm = _extract_val(umts_signals, 'rssi')
                                    logger.debug(f"Got UMTS (3G) RSSI signal: {signal_dbm} dBm",
                                               extra={'interface_number': self.interface_number})
                                elif 'rscp' in umts_signals:
                                    signal_dbm = _extract_val(umts_signals, 'rscp')
                                    logger.debug(f"Got UMTS (3G) RSCP signal: {signal_dbm} dBm",
                                               extra={'interface_number': self.interface_number})

                                signal_detail = {
                                    'technology': 'UMTS',
                                    'rssi': _extract_val(umts_signals, 'rssi') or '',
                                    'rsrp': '',
                                    'rsrq': '',
                                    'snr': '',
                                }
                        except Exception:
                            pass

                    # Try GSM signals (2G)
                    if signal_dbm is None:
                        try:
                            gsm_signal_variant = await props.call_get("org.freedesktop.ModemManager1.Modem.Signal", "Gsm")
                            if gsm_signal_variant and gsm_signal_variant.value:
                                gsm_signals = gsm_signal_variant.value
                                if 'rssi' in gsm_signals:
                                    signal_dbm = _extract_val(gsm_signals, 'rssi')
                                    logger.debug(f"Got GSM (2G) RSSI signal: {signal_dbm} dBm",
                                               extra={'interface_number': self.interface_number})

                                    signal_detail = {
                                        'technology': 'GSM',
                                        'rssi': _extract_val(gsm_signals, 'rssi') or '',
                                        'rsrp': '',
                                        'rsrq': '',
                                        'snr': '',
                                    }
                        except Exception:
                            pass

                    # Try CDMA signals (2G CDMA)
                    if signal_dbm is None:
                        try:
                            cdma_signal_variant = await props.call_get("org.freedesktop.ModemManager1.Modem.Signal", "Cdma")
                            if cdma_signal_variant and cdma_signal_variant.value:
                                cdma_signals = cdma_signal_variant.value
                                if 'rssi' in cdma_signals:
                                    signal_dbm = _extract_val(cdma_signals, 'rssi')
                                    logger.debug(f"Got CDMA (2G) RSSI signal: {signal_dbm} dBm",
                                               extra={'interface_number': self.interface_number})

                                    signal_detail = {
                                        'technology': 'CDMA',
                                        'rssi': _extract_val(cdma_signals, 'rssi') or '',
                                        'rsrp': '',
                                        'rsrq': '',
                                        'snr': '',
                                    }
                        except Exception:
                            pass

                    # Try EVDO signals (3G CDMA)
                    if signal_dbm is None:
                        try:
                            evdo_signal_variant = await props.call_get("org.freedesktop.ModemManager1.Modem.Signal", "Evdo")
                            if evdo_signal_variant and evdo_signal_variant.value:
                                evdo_signals = evdo_signal_variant.value
                                if 'rssi' in evdo_signals:
                                    signal_dbm = _extract_val(evdo_signals, 'rssi')
                                    logger.debug(f"Got EVDO (3G CDMA) RSSI signal: {signal_dbm} dBm",
                                               extra={'interface_number': self.interface_number})

                                    signal_detail = {
                                        'technology': 'EVDO',
                                        'rssi': _extract_val(evdo_signals, 'rssi') or '',
                                        'rsrp': '',
                                        'rsrq': '',
                                        'snr': '',
                                    }
                        except Exception:
                            pass

            except Exception as e:
                logger.debug(f"Could not access Signal interface: {e}",
                           extra={'interface_number': self.interface_number})

            # Fall back to percentage-based estimation if no dBm available
            if signal_dbm is None:
                logger.debug("Using percentage-based dBm estimation as fallback",
                           extra={'interface_number': self.interface_number})
                if signal_percent > 80:
                    signal_dbm = -60
                elif signal_percent > 60:
                    signal_dbm = -70
                elif signal_percent > 40:
                    signal_dbm = -80
                elif signal_percent > 20:
                    signal_dbm = -90
                else:
                    signal_dbm = -100

            return signal_percent, signal_dbm, signal_detail

        except Exception as e:
            logger.error(f"Failed to get detailed signal quality: {e}",
                        extra={'interface_number': self.interface_number})
            return None, None, None

    async def _wait_for_adequate_signal(self, max_wait=None):
        """Wait for signal to improve before attempting reconnection"""
        if max_wait is None:
            max_wait = getattr(self, 'max_wait_for_signal', 120)
        check_interval = getattr(self, 'signal_check_interval', 10)

        start_time = time.time()

        logger.info("Waiting for signal improvement before reconnection",
                   extra={'interface_number': self.interface_number,
                          'max_wait': max_wait,
                          'check_interval': check_interval})

        while time.time() - start_time < max_wait:
            if await self._check_signal_adequacy_for_reconnection():
                elapsed = time.time() - start_time
                logger.info(f"Signal improved after {elapsed:.1f}s - ready for reconnection",
                           extra={'interface_number': self.interface_number})
                return True

            elapsed = time.time() - start_time
            logger.debug(f"Signal still inadequate after {elapsed:.0f}s - continuing to wait",
                        extra={'interface_number': self.interface_number})

            await asyncio.sleep(check_interval)

        logger.warning(f"Signal did not improve within {max_wait}s timeout",
                      extra={'interface_number': self.interface_number})
        return False

    async def _enhanced_reconnection_attempt(self):
        """Enhanced reconnection with signal validation and faster timing"""
        try:
            self._record_reconnect_attempt('enhanced_reconnection')
            # Final signal check before reconnection
            signal_adequate = await self._check_signal_adequacy_for_reconnection()
            if signal_adequate:
                logger.info("Signal adequate - proceeding with reconnection",
                           extra={'interface_number': self.interface_number})
            else:
                logger.warning("Attempting reconnection despite inadequate signal",
                              extra={'interface_number': self.interface_number})

            # Disconnect current bearer if it exists
            if self.bearer_path:
                try:
                    simple_iface = self.proxy.get_interface(SIMPLE_INTERFACE)
                    await simple_iface.call_disconnect(self.bearer_path)
                    await asyncio.sleep(3)  # Reduced from 5s for faster recovery
                    logger.info("Existing bearer disconnected for reconnection",
                               extra={'interface_number': self.interface_number})
                except Exception as disconnect_e:
                    logger.warning(f"Could not disconnect existing bearer: {disconnect_e}",
                                  extra={'interface_number': self.interface_number})

            # Attempt reconnection
            await self.apply_modem_configuration()
            logger.info("Enhanced reconnection attempt completed",
                       extra={'interface_number': self.interface_number})
            return True

        except Exception as e:
            logger.error(f"Enhanced reconnection attempt failed: {e}",
                        extra={'interface_number': self.interface_number})
            return False

    async def _monitor_signal_strength(self, interval_seconds: int = 5) -> None:
        """Periodically poll signal strength while CONNECTED.

        Feeds dBm samples into ``self.signal_tracker``, which is the
        only thing that fires ``_update_signal_led``.  Without this
        loop the LED stays dark in steady state because the only other
        caller of ``signal_tracker.update`` is the reconnection path.

        It also drives signal-loss SIM failover: when the active SIM's
        signal stays below the configured ``sim sim-failover
        signal-threshold`` (metric-aware: RSRP for LTE/5G, RSSI for 2G/3G)
        continuously for ``sim-failover signal-loss-timer`` seconds, it
        triggers ``_handle_signal_loss_failover`` to switch to the
        alternate SIM.

        Started by ``_start_network_interface_monitoring`` on entry to
        CONNECTED and cancelled by ``_stop_network_interface_monitoring``
        on exit; safe to be cancelled at any await point.
        """
        # Reset the below-threshold tracker each time the loop starts (i.e. on
        # every entry to CONNECTED) so a stale timestamp from a previous
        # session can't cause an immediate failover.
        self._signal_failover_below_since = None
        try:
            while True:
                try:
                    _percent, signal_dbm, signal_detail = \
                        await self._get_detailed_signal_quality()
                    if (self.signal_tracker is not None
                            and signal_dbm is not None):
                        await self.signal_tracker.update(
                            signal_dbm, signal_detail or {})

                    # Signal-loss SIM failover evaluation
                    await self._evaluate_signal_loss_failover(
                        signal_dbm, signal_detail)
                except asyncio.CancelledError:
                    raise
                except Exception as poll_err:
                    logger.debug("Signal-poll iteration failed: %s",
                                 poll_err,
                                 extra={'interface_number': self.interface_number})
                await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            logger.debug("Signal-strength poll task cancelled",
                         extra={'interface_number': self.interface_number})
            raise

    async def _evaluate_signal_loss_failover(self, signal_dbm, signal_detail) -> None:
        """Track sustained weak signal and fail over to the alternate SIM.

        Called once per signal-poll iteration. Compares the active SIM's
        signal against the configured sim-failover threshold for the metric
        actually reported by the modem (RSRP on LTE/5G, RSSI on 2G/3G). When
        the signal stays below that threshold continuously for
        ``sim_failover_signal_loss_timer`` seconds, it triggers a failover.
        """
        # Cheap gate: skip entirely on single-SIM setups or when disabled.
        if not self._signal_failover_possible():
            self._signal_failover_below_since = None
            return

        # Don't evaluate while a switch/failover is already running.
        if self._sim_switch_in_progress or self._sim_failover_in_progress:
            return

        if signal_dbm is None:
            # No reading — don't accumulate against the timer (a missing
            # reading is not the same as confirmed weak signal).
            return

        rssi_threshold = self.config.get('sim_failover_signal_threshold_rssi', -90)
        rsrp_threshold = self.config.get('sim_failover_signal_threshold_rsrp', -110)
        loss_timer = max(1, int(self.config.get('sim_failover_signal_loss_timer', 60)))

        metric_name, metric_dbm, threshold = self._select_signal_metric(
            signal_detail, signal_dbm, rssi_threshold, rsrp_threshold)

        if metric_dbm >= threshold:
            # Signal adequate — clear any in-progress weak-signal window.
            if self._signal_failover_below_since is not None:
                logger.info("Signal recovered above sim-failover threshold",
                           extra={'interface_number': self.interface_number,
                                  'metric': metric_name,
                                  'metric_dbm': metric_dbm,
                                  'threshold_dbm': threshold})
                self._signal_failover_below_since = None
            return

        # Below threshold — start or continue the weak-signal window.
        now = time.time()
        if self._signal_failover_below_since is None:
            # Only arm the timer if there is actually somewhere to switch to.
            # The cheap _signal_failover_possible() gate above is config-only;
            # confirm a SIM is physically present in an eligible slot before
            # arming so we don't spin the timer (and emit attempts) into an
            # empty slot — e.g. right after a hot-eject failover where the
            # just-vacated slot is still configured+enabled but now empty.
            if not await self._present_eligible_alternate_exists():
                logger.debug("Weak signal but no present alternate SIM — "
                             "not arming signal-loss failover",
                             extra={'interface_number': self.interface_number,
                                    'metric': metric_name,
                                    'metric_dbm': metric_dbm,
                                    'threshold_dbm': threshold})
                return
            self._signal_failover_below_since = now
            logger.warning("Signal dropped below sim-failover threshold — "
                          "starting signal-loss timer",
                          extra={'interface_number': self.interface_number,
                                 'metric': metric_name,
                                 'metric_dbm': metric_dbm,
                                 'threshold_dbm': threshold,
                                 'signal_loss_timer': loss_timer})
            return

        elapsed = now - self._signal_failover_below_since
        if elapsed >= loss_timer:
            # Re-confirm a present alternate before firing: the alternate SIM
            # could have been removed during the loss window, in which case we
            # silently reset rather than launch a doomed switch.
            if not await self._present_eligible_alternate_exists():
                logger.debug("Sustained weak signal but no present alternate "
                             "SIM — skipping signal-loss failover",
                             extra={'interface_number': self.interface_number,
                                    'metric': metric_name,
                                    'metric_dbm': metric_dbm,
                                    'threshold_dbm': threshold,
                                    'elapsed_seconds': round(elapsed, 1)})
                self._signal_failover_below_since = None
                return
            logger.warning("Sustained weak signal — triggering SIM failover",
                          extra={'interface_number': self.interface_number,
                                 'metric': metric_name,
                                 'metric_dbm': metric_dbm,
                                 'threshold_dbm': threshold,
                                 'elapsed_seconds': round(elapsed, 1),
                                 'signal_loss_timer': loss_timer})
            # Require a fresh full window before another attempt (the
            # cooldown/backoff in _is_failover_allowed also applies).
            self._signal_failover_below_since = None
            self._safe_create_task(self._handle_signal_loss_failover())

    async def _update_signal_led(self, level: int, avg_dbm: float, signal_detail: dict) -> None:
        """Update modem STAT LEDs using hardware API signal-level mapping.

        Args:
            level: Signal level 0-7 (0=no-signal, 7=maximum).
            avg_dbm: Rolling average signal in dBm.
            signal_detail: Dict with {rssi, rsrp, rsrq, snr, technology}.
        """
        level_names = ['no-signal', 'barely-usable', 'very-poor', 'weak', 'fair', 'good', 'very-good', 'excellent']
        level_name = level_names[level] if 0 <= level <= 7 else 'unknown'

        # Map wwanN interface to MODEMN naming expected by hw API.
        modem_name = f"MODEM{self.interface_number}"

        # Keep logging explicit for operational visibility.
        logger.info(
            f"[LED UPDATE] Signal: {level_name} [{level}/7] (avg={avg_dbm} dBm, tech={signal_detail.get('technology', 'Unknown')})",
            extra={'interface_number': self.interface_number,
                   'level': level, 'avg_dbm': avg_dbm, 'level_name': level_name}
        )

        try:
            # Lazy import keeps FSM unit tests and non-hardware images tolerant.
            import vyos.hardware.api as hw_api

            hw_api.modem_signal_level(level=level, modem=modem_name)
        except Exception as e:
            # Non-fatal: signal logic should continue even if LED hardware is absent.
            logger.debug("Signal LED update skipped (non-fatal): %s",
                         e,
                         extra={'interface_number': self.interface_number,
                                'level': level,
                                'modem_name': modem_name})

    async def _clear_signal_led(self, reason: str = "") -> None:
        """Clear modem STAT LED to OFF (level 0) and reset rolling signal history.

        Called when there is no active bearer / interface is down so the UI
        doesn't display stale signal bars from a previous connected session.
        """
        modem_name = f"MODEM{self.interface_number}"
        try:
            if self.signal_tracker:
                self.signal_tracker.reset()

            import vyos.hardware.api as hw_api
            hw_api.modem_signal_level(level=0, modem=modem_name)

            logger.info("[LED UPDATE] Signal cleared (OFF)",
                       extra={'interface_number': self.interface_number,
                              'level': 0,
                              'modem_name': modem_name,
                              'reason': reason or 'unspecified'})
        except Exception as e:
            logger.debug("Signal LED clear skipped (non-fatal): %s",
                        e,
                        extra={'interface_number': self.interface_number,
                               'modem_name': modem_name,
                               'reason': reason or 'unspecified'})

    def get_sim_status_summary(self):
        """Get quick SIM status summary"""
        return {
            'current_active_sim': self.current_active_sim,
            'config_active_sim': self.config_active_sim,
            'is_on_configured_sim': self.current_active_sim == self.config_active_sim,
            'sim_switch_reason': self.sim_switch_reason,
            'auto_failover_active': self.current_active_sim != self.config_active_sim
        }

    # ------------------------------------------------------------------
    # Comprehensive status report (used by D-Bus get_status)
    # ------------------------------------------------------------------
    async def get_comprehensive_status(self) -> dict:
        """Return a flat dict with everything known about this interface.

        All values are plain Python types (str, int, float, bool).
        The D-Bus layer wraps each into a Variant for the ``a{sv}`` return.
        """

        status = {}

        # Modem.GetAll() properties — populated in section 4/5 below, but
        # initialised here at function scope so later sections (e.g. the QMI
        # serving-cell fallback) can safely read the QMI control port even if
        # that GetAll never ran or failed.
        modem_props = {}

        # ── 1. FSM / interface identity ──────────────────────────────────
        current_state = (
            getattr(self.machine, 'current_state', 'UNKNOWN')
            if hasattr(self, 'machine') and self.machine else 'UNKNOWN'
        )
        status['interface_number'] = self.interface_number
        status['interface_name'] = getattr(self, 'interface_name', f"wwan{self.interface_number}")
        status['fsm_state'] = current_state
        status['modem_path'] = self.modem_path or ''
        status['bearer_path'] = self.bearer_path or ''
        status['config_applied'] = bool(self.config)
        status['user_disconnected'] = self.user_disconnected
        status['connect_requested'] = self.connect_requested

        # ── 1a. Connection failure details ───────────────────────────────
        # These fields explain WHY the modem is in FAILED state so that
        # operators / monitoring tools can see the reason without parsing logs.
        status['failure_reason'] = self.last_failure_reason if current_state == ModemState.FAILED.value else ''
        status['failure_time'] = (
            datetime.datetime.fromtimestamp(self.last_failure_time).isoformat()
            if self.last_failure_time and current_state == ModemState.FAILED.value else ''
        )
        status['failed_apn'] = self.last_failed_apn if current_state == ModemState.FAILED.value else ''
        status['configured_apn_rejected'] = (
            self.configured_apn_rejected if current_state == ModemState.FAILED.value else False
        )

        # ── 2. SIM status ────────────────────────────────────────────────
        status['active_sim_slot'] = self.current_active_sim or 0
        status['configured_sim_slot'] = self.config_active_sim or 0
        status['primary_sim_slot'] = self.primary_sim_slot or 0
        status['is_on_configured_sim'] = (self.current_active_sim == self.config_active_sim)
        status['is_on_failover_sim'] = self.is_on_failover_sim
        status['sim_switch_reason'] = self.sim_switch_reason or ''
        status['sim_failover_enabled'] = self._is_sim_failover_enabled()
        status['sim_failback_enabled'] = (
            self.config.get('sim_failback_enabled', True) if self.config else True
        )
        status['failback_suppressed_by_connection_failure'] = self.failback_suppressed_by_connection_failure

        # Cached SIM identifiers
        sim = self.last_known_sim_info or {}
        status['sim_imsi'] = sim.get('imsi', '')
        status['sim_iccid'] = sim.get('sim_identifier', '')
        status['sim_operator'] = sim.get('operator_name', '')
        status['sim_mcc_mnc'] = sim.get('mcc_mnc', '')

        # ── 2a. SIM PIN/PUK unlock status ────────────────────────────────
        status['pin_unlock_attempted'] = self._pin_unlock_attempted
        status['pin_unlock_failed'] = self._pin_unlock_failed
        status['puk_unlock_attempted'] = self._puk_unlock_attempted
        status['puk_unlock_failed'] = self._puk_unlock_failed
        status['sim_permanently_locked'] = self._sim_permanently_locked
        status['pin_retries_remaining'] = self._pin_retries_remaining
        status['puk_retries_remaining'] = self._puk_retries_remaining
        # Live retry counters from SIM EEPROM (if modem is present)
        try:
            if self.proxy:
                retries = await self._get_unlock_retries()
                if retries:
                    self._pin_retries_remaining = retries.get(1, self._pin_retries_remaining)
                    self._puk_retries_remaining = retries.get(2, self._puk_retries_remaining)
                    status['pin_retries_remaining'] = self._pin_retries_remaining
                    status['puk_retries_remaining'] = self._puk_retries_remaining
        except Exception:
            pass  # Keep cached values

        # ── 3. Live SIM details (query D-Bus if modem present) ───────────
        try:
            if self.proxy:
                live_sim = await self._get_sim_information()
                if live_sim:
                    status['sim_imsi'] = live_sim.get('imsi', '') or status['sim_imsi']
                    status['sim_iccid'] = live_sim.get('sim_identifier', '') or status['sim_iccid']
                    status['sim_operator'] = live_sim.get('operator_name', '') or status['sim_operator']
                    status['sim_mcc_mnc'] = live_sim.get('mcc_mnc', '') or status['sim_mcc_mnc']
                    status['sim_spn'] = live_sim.get('spn', '')
        except Exception:
            pass  # Keep cached values

        # ── 3a. Connected APN ────────────────────────────────────────────
        apn = self.connected_apn or {}
        status['connected_apn'] = apn.get('name', '')
        status['connected_apn_auth'] = apn.get('auth_type', '')
        status['connected_apn_username'] = apn.get('username', '')
        # APN we asked MM to connect with, and the one the carrier actually
        # activated (read over QMI).  A mismatch flags a network override —
        # surfaced separately so troubleshooting can see both.
        status['requested_apn'] = self.requested_apn or ''
        status['negotiated_apn'] = self.negotiated_apn or ''

        # ── 4 & 5. Modem hardware + registration (batched GetAll) ────────
        # A single GetAll on MODEM_INTERFACE replaces ~12 individual
        # call_get round-trips; one more GetAll for Modem3gpp replaces 3.
        try:
            if self.proxy:
                props = self.proxy.get_interface("org.freedesktop.DBus.Properties")

                # --- Batch: all properties from MODEM_INTERFACE -----------
                modem_all_raw = await props.call_get_all(MODEM_INTERFACE)
                # Unwrap Variants: each value is Variant(signature, value)
                modem_props = {}
                for k, v in modem_all_raw.items():
                    modem_props[k] = v.value if hasattr(v, 'value') else v

                # Section 4 — hardware
                status['modem_manufacturer'] = modem_props.get('Manufacturer', '')
                status['modem_model'] = modem_props.get('Model', '')
                status['modem_imei'] = modem_props.get('EquipmentIdentifier', '')
                status['modem_firmware'] = modem_props.get('Revision', '')
                status['modem_device'] = modem_props.get('Device', '')

                own_nums = modem_props.get('OwnNumbers', [])
                if own_nums and hasattr(own_nums, '__iter__'):
                    own_nums = list(own_nums)
                else:
                    own_nums = []
                status['modem_phone_number'] = own_nums[0] if own_nums else ''
                status['modem_phone_numbers'] = own_nums

                status['modem_hardware_revision'] = modem_props.get('HardwareRevision', '')

                pwr_val = modem_props.get('PowerState', 0)
                status['modem_power_state'] = pwr_val
                status['modem_power_state_name'] = {
                    0: 'unknown', 1: 'off', 2: 'low', 3: 'on'
                }.get(pwr_val, 'unknown')

                # Section 5 — registration / access technology
                status['modem_state'] = modem_props.get('State', -1)
                at_val = modem_props.get('AccessTechnologies', 0)
                status['access_technologies'] = at_val
                status['access_technology_name'] = self._access_tech_to_string(at_val)

                sfr_val = modem_props.get('StateFailedReason', 0)
                status['modem_state_failed_reason'] = sfr_val
                status['modem_state_failed_reason_name'] = {
                    0: 'none', 1: 'unknown', 2: 'sim-missing',
                    3: 'sim-error',
                }.get(sfr_val, f'unknown({sfr_val})')

                band_list = modem_props.get('CurrentBands', [])
                if band_list and hasattr(band_list, '__iter__'):
                    status['current_bands'] = [self._band_to_string(b) for b in band_list]
                else:
                    status['current_bands'] = []

                # Supported (capability) bands — every band the modem reports
                # it can operate on, as exposed by ModemManager's SupportedBands
                # (this includes 5G NR; RedCap-only bands are not advertised
                # until registration and cannot be set, so they are absent here).
                supported_constants = []
                supported_list = modem_props.get('SupportedBands', [])
                if supported_list and hasattr(supported_list, '__iter__'):
                    for b in supported_list:
                        bv = b.value if hasattr(b, 'value') else b
                        try:
                            supported_constants.append(int(bv))
                        except (TypeError, ValueError):
                            continue
                seen_band_names = set()
                supported_band_names = []
                for c in sorted(supported_constants):
                    name = self._band_to_string(c)
                    if name not in seen_band_names:
                        seen_band_names.add(name)
                        supported_band_names.append(name)
                status['supported_bands'] = supported_band_names

                # Signal quality percentage (from modem GetAll)
                sq = modem_props.get('SignalQuality', None)
                if sq:
                    sq_val = sq[0] if isinstance(sq, (list, tuple)) and sq else sq
                    status['_signal_percent_from_getall'] = sq_val

                # --- Batch: all properties from Modem3gpp -----------------
                try:
                    gpp_iface = "org.freedesktop.ModemManager1.Modem.Modem3gpp"
                    gpp_all_raw = await props.call_get_all(gpp_iface)
                    gpp_props = {}
                    for k, v in gpp_all_raw.items():
                        gpp_props[k] = v.value if hasattr(v, 'value') else v

                    status['operator_name'] = gpp_props.get('OperatorName', '')
                    status['registration_state'] = gpp_props.get('RegistrationState', 0)
                    status['operator_code'] = gpp_props.get('OperatorCode', '')
                except Exception:
                    status.setdefault('operator_name', '')
                    status.setdefault('registration_state', 0)
                    status.setdefault('operator_code', '')
        except Exception:
            for k in ('modem_manufacturer', 'modem_model', 'modem_imei',
                      'modem_firmware', 'modem_device',
                      'modem_hardware_revision', 'modem_power_state_name'):
                status.setdefault(k, '')
            status.setdefault('modem_phone_number', '')
            status.setdefault('modem_phone_numbers', [])
            status.setdefault('modem_power_state', 0)
            for k in ('modem_state', 'access_technologies',
                      'access_technology_name', 'operator_name',
                      'registration_state', 'operator_code',
                      'modem_state_failed_reason_name'):
                status.setdefault(k, '')
            status.setdefault('modem_state_failed_reason', 0)
            status.setdefault('current_bands', [])
            status.setdefault('supported_bands', [])

        # ── 6. Signal quality (batched GetAll on Signal interface) ─────────
        try:
            # Use signal percent already captured from modem GetAll if available
            signal_percent = status.pop('_signal_percent_from_getall', None)
            if signal_percent is None:
                signal_percent = 0

            signal_dbm = None
            signal_detail = None

            if self.proxy:
                sig_props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
                sig_iface = "org.freedesktop.ModemManager1.Modem.Signal"
                try:
                    sig_all_raw = await sig_props.call_get_all(sig_iface)
                    sig_all = {}
                    for k, v in sig_all_raw.items():
                        sig_all[k] = v.value if hasattr(v, 'value') else v

                    def _unwrap_sig_dict(d):
                        """Unwrap a signal tech dict (may have Variant values)."""
                        out = {}
                        if d and isinstance(d, dict):
                            for sk, sv in d.items():
                                out[sk] = sv.value if hasattr(sv, 'value') else sv
                        return out

                    # Try LTE first
                    lte = _unwrap_sig_dict(sig_all.get('Lte'))
                    if lte:
                        signal_dbm = lte.get('rssi') or lte.get('rsrp')
                        signal_detail = {
                            'technology': 'LTE',
                            'rssi': lte.get('rssi', ''),
                            'rsrp': lte.get('rsrp', ''),
                            'rsrq': lte.get('rsrq', ''),
                            'snr': lte.get('snr', ''),
                        }

                    # 5G NR
                    if signal_dbm is None:
                        nr5g = _unwrap_sig_dict(sig_all.get('Nr5g'))
                        if nr5g:
                            signal_dbm = nr5g.get('rsrp') or nr5g.get('rssi')
                            signal_detail = {
                                'technology': '5G NR',
                                'rssi': nr5g.get('rssi', ''),
                                'rsrp': nr5g.get('rsrp', ''),
                                'rsrq': nr5g.get('rsrq', ''),
                                'snr': nr5g.get('snr', ''),
                            }

                    # UMTS (3G)
                    if signal_dbm is None:
                        umts = _unwrap_sig_dict(sig_all.get('Umts'))
                        if umts:
                            signal_dbm = umts.get('rssi') or umts.get('rscp')
                            signal_detail = {
                                'technology': 'UMTS',
                                'rssi': umts.get('rssi', ''),
                                'rsrp': '', 'rsrq': '', 'snr': '',
                            }

                    # GSM (2G)
                    if signal_dbm is None:
                        gsm = _unwrap_sig_dict(sig_all.get('Gsm'))
                        if gsm and gsm.get('rssi'):
                            signal_dbm = gsm['rssi']
                            signal_detail = {
                                'technology': 'GSM',
                                'rssi': gsm['rssi'],
                                'rsrp': '', 'rsrq': '', 'snr': '',
                            }

                    # CDMA
                    if signal_dbm is None:
                        cdma = _unwrap_sig_dict(sig_all.get('Cdma'))
                        if cdma and cdma.get('rssi'):
                            signal_dbm = cdma['rssi']
                            signal_detail = {
                                'technology': 'CDMA',
                                'rssi': cdma['rssi'],
                                'rsrp': '', 'rsrq': '', 'snr': '',
                            }

                    # EVDO
                    if signal_dbm is None:
                        evdo = _unwrap_sig_dict(sig_all.get('Evdo'))
                        if evdo and evdo.get('rssi'):
                            signal_dbm = evdo['rssi']
                            signal_detail = {
                                'technology': 'EVDO',
                                'rssi': evdo['rssi'],
                                'rsrp': '', 'rsrq': '', 'snr': '',
                            }
                except Exception:
                    pass  # Signal interface may not be set up yet

            # Fall back to percentage-based estimation
            if signal_dbm is None:
                if signal_percent > 80:
                    signal_dbm = -60
                elif signal_percent > 60:
                    signal_dbm = -70
                elif signal_percent > 40:
                    signal_dbm = -80
                elif signal_percent > 20:
                    signal_dbm = -90
                else:
                    signal_dbm = -100

            status['signal_percent'] = signal_percent or 0
            status['signal_dbm'] = signal_dbm or 0
            if signal_detail:
                status['signal_rssi'] = signal_detail.get('rssi', '')
                status['signal_rsrp'] = signal_detail.get('rsrp', '')
                status['signal_rsrq'] = signal_detail.get('rsrq', '')
                status['signal_snr'] = signal_detail.get('snr', '')
                status['signal_technology'] = signal_detail.get('technology', '')
            else:
                for k in ('signal_rssi', 'signal_rsrp', 'signal_rsrq',
                          'signal_snr', 'signal_technology'):
                    status[k] = ''
        except Exception:
            status['signal_percent'] = 0
            status['signal_dbm'] = 0
            for k in ('signal_rssi', 'signal_rsrp', 'signal_rsrq',
                      'signal_snr', 'signal_technology'):
                status[k] = ''

        # ── 6b. Serving cell info (band actually camped on) ──────────
        # ModemManager 1.20+ exposes Modem.CellInfo.GetCellInfo() which
        # returns serving + neighbor cell dictionaries. We extract the
        # serving cell's band / EARFCN / cell-id. For LTE we derive the
        # band from EARFCN if the modem doesn't report it directly.
        for k in ('serving_cell_type', 'serving_band', 'serving_earfcn',
                  'serving_cell_id', 'serving_tac', 'serving_physical_ci'):
            status[k] = ''
        try:
            if self.proxy:
                ci_iface = self.proxy.get_interface(
                    "org.freedesktop.ModemManager1.Modem.CellInfo")
                cells_raw = await ci_iface.call_get_cell_info()
                for cell in cells_raw or []:
                    cell_d = {}
                    for ck, cv in cell.items():
                        cell_d[ck] = cv.value if hasattr(cv, 'value') else cv
                    if not cell_d.get('serving'):
                        continue
                    ctype = str(cell_d.get('cell-type', '')).lower()
                    status['serving_cell_type'] = ctype
                    status['serving_cell_id'] = str(cell_d.get('ci', ''))
                    status['serving_tac'] = str(cell_d.get('tac', ''))
                    status['serving_physical_ci'] = str(
                        cell_d.get('physical-ci', ''))
                    band_str = str(cell_d.get('band', '') or '')
                    if ctype == 'lte':
                        earfcn = cell_d.get('earfcn', '')
                        status['serving_earfcn'] = str(earfcn) if earfcn != '' else ''
                        if not band_str and earfcn != '':
                            band_str = self._lte_earfcn_to_band(earfcn)
                    elif ctype in ('nr5g', '5gnr'):
                        nrarfcn = cell_d.get('nrarfcn', '')
                        status['serving_earfcn'] = str(nrarfcn) if nrarfcn != '' else ''
                    elif ctype == 'umts':
                        uarfcn = cell_d.get('uarfcn', '')
                        status['serving_earfcn'] = str(uarfcn) if uarfcn != '' else ''
                    elif ctype == 'gsm':
                        arfcn = cell_d.get('arfcn', '')
                        status['serving_earfcn'] = str(arfcn) if arfcn != '' else ''
                    status['serving_band'] = band_str
                    break
        except Exception:
            # CellInfo interface unavailable (older MM) or no serving cell yet
            pass

        # Fallback: ModemManager's CellInfo returned nothing usable — common
        # on QMI modems / older MM builds where the interface is present but
        # the serving cell is never populated.  Read the serving band,
        # channel and cell IDs straight from the modem over QMI.  Only fills
        # fields the MM path left blank, so a populated CellInfo always wins.
        if not status.get('serving_band'):
            try:
                qmi_cell = await self._qmi_get_serving_cell_info(modem_props)
                for k, v in qmi_cell.items():
                    if v and not status.get(k):
                        status[k] = v
            except Exception:
                pass

        # ── 7. IP configuration (live from interface) ────────────────────
        try:
            ip_info = await self._get_current_ip()
            if ip_info:
                status['ipv4_address'] = ip_info.get('ipv4', '') or ''
                status['ipv6_address'] = ip_info.get('ipv6', '') or ''
            else:
                status['ipv4_address'] = ''
                status['ipv6_address'] = ''
        except Exception:
            status['ipv4_address'] = ''
            status['ipv6_address'] = ''

        # Bearer IP config (gateway, DNS from ModemManager)
        try:
            bearer_ips = await self._get_bearer_expected_ips()
            if bearer_ips:
                status['ipv4_gateway'] = bearer_ips.get('ipv4_gateway', '')
                status['ipv4_dns'] = ', '.join(bearer_ips.get('ipv4_dns', []))
                status['ipv6_gateway'] = bearer_ips.get('ipv6_gateway', '')
                status['ipv6_dns'] = ', '.join(bearer_ips.get('ipv6_dns', []))
                status['mtu'] = bearer_ips.get('ipv4_mtu', bearer_ips.get('ipv6_mtu', ''))
            else:
                for k in ('ipv4_gateway', 'ipv4_dns', 'ipv6_gateway', 'ipv6_dns', 'mtu'):
                    status[k] = ''
        except Exception:
            for k in ('ipv4_gateway', 'ipv4_dns', 'ipv6_gateway', 'ipv6_dns', 'mtu'):
                status[k] = ''

        # MTU config summary
        if self.config:
            interface_mtu = self.config.get('mtu', 1420)
            network_mtu = status.get('mtu', '')

            # Look up per-SIM MTU for active slot
            sim_mtu = 0
            sim_slots = self.config.get('sim_slots', [])
            active_slot = self.current_active_sim or self.config.get('primary_sim_slot', 1)
            sim_config = next((s for s in sim_slots if s['slot'] == active_slot), {})
            sim_mtu = sim_config.get('mtu', 0)

            if sim_mtu and sim_mtu > 0:
                status['mtu_effective'] = str(sim_mtu)
                status['mtu_source'] = 'per-sim'
            elif network_mtu:
                status['mtu_effective'] = str(min(int(network_mtu), interface_mtu))
                status['mtu_source'] = 'network' if int(network_mtu) <= interface_mtu else 'network-capped'
            else:
                status['mtu_effective'] = str(interface_mtu)
                status['mtu_source'] = 'interface'
            status['mtu_interface'] = interface_mtu
            status['mtu_per_sim'] = sim_mtu

            # Configured bands for the active SIM — the value the operator
            # typed under `sim slot N supported-bands`.  Surfaced separately
            # from MM's effective CurrentBands ('current_bands') so the show
            # command can confirm a restriction was registered even when the
            # effective view cannot reflect it — most importantly for 5G NR,
            # which is enforced over QMI and never appears in CurrentBands.
            cfg_bands_raw = sim_config.get('supported_bands', 'all')
            if isinstance(cfg_bands_raw, str):
                cfg_bands = [b.strip() for b in cfg_bands_raw.split(',') if b.strip()]
            else:
                cfg_bands = [str(b).strip() for b in (cfg_bands_raw or []) if str(b).strip()]
            # Normalise an empty / unset selection to the 'all' sentinel.
            if not cfg_bands or cfg_bands == ['all']:
                status['configured_bands'] = ['all']
            else:
                status['configured_bands'] = cfg_bands
        else:
            for k in ('mtu_effective', 'mtu_source', 'mtu_interface', 'mtu_per_sim'):
                status[k] = ''
            status['configured_bands'] = ['all']

        # ── 8. Bearer stats (session data, uptime) ───────────────────────
        try:
            if self.bearer_path:
                introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, self.bearer_path)
                bp = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, self.bearer_path, introspect)
                bprops = bp.get_interface("org.freedesktop.DBus.Properties")
                stats_v = await bprops.call_get(BEARER_INTERFACE, "Stats")
                if stats_v and stats_v.value:
                    stats = stats_v.value
                    rx = stats.get('rx-bytes', 0)
                    tx = stats.get('tx-bytes', 0)
                    rx_val = rx.value if hasattr(rx, 'value') else rx
                    tx_val = tx.value if hasattr(tx, 'value') else tx
                    status['session_rx_bytes'] = int(rx_val)
                    status['session_tx_bytes'] = int(tx_val)
                    status['session_total_bytes'] = int(rx_val) + int(tx_val)
                    dur = stats.get('duration', 0)
                    dur_val = dur.value if hasattr(dur, 'value') else dur
                    status['session_duration_seconds'] = int(dur_val)
                    # Refresh the salvage cache from this live read so a drop
                    # before the next monitor poll does not lose the session.
                    self._last_session_bytes = int(rx_val) + int(tx_val)
                    self._last_session_slot = self._current_usage_slot()
                else:
                    for k in ('session_rx_bytes', 'session_tx_bytes',
                              'session_total_bytes', 'session_duration_seconds'):
                        status[k] = 0
        except Exception:
            for k in ('session_rx_bytes', 'session_tx_bytes',
                      'session_total_bytes', 'session_duration_seconds'):
                status.setdefault(k, 0)

        # ── 9. Per-SIM cumulative data usage ─────────────────────────────
        try:
            active_slot = self._current_usage_slot()
            session_total = status.get('session_total_bytes', 0)

            # The on-disk persisted value already folds in session bytes up to
            # the last monitor poll, so it must NOT be re-added to the full live
            # session (that double counts).  While the monitor is running for
            # this slot, the captured baseline is the true pre-session
            # cumulative; "Cumulative bytes" therefore reports the baseline and
            # "Including session" reports baseline + live session.  Calling
            # _load_persisted_usage() also triggers any billing-cycle reset.
            persisted_active = self._load_persisted_usage()
            if (self._usage_baseline_slot == active_slot
                    and self._usage_baseline_bytes is not None):
                active_prior = self._usage_baseline_bytes
            else:
                # No live monitoring baseline — the persisted value is the final
                # cumulative and there is no separate live session to add.
                active_prior = persisted_active
                session_total = 0

            status['cumulative_bytes'] = active_prior
            status['cumulative_plus_session'] = active_prior + session_total
            data_cfg = self._get_active_sim_data_config()
            status['data_limit_bytes'] = data_cfg.get('data_limit_size', 0)
            status['data_limit_action'] = data_cfg.get('data_limit_action', 'none')
            status['data_limit_warning'] = data_cfg.get('data_limit_warning', [])
            status['data_limit_billing_date'] = data_cfg.get('data_limit_billing_date', 1)
            status['usage_tracking_slot'] = active_slot
            limit = status['data_limit_bytes']
            total = status['cumulative_plus_session']
            status['data_usage_percent'] = round((total / limit) * 100, 1) if limit > 0 else 0.0

            # Per-slot persisted cumulative + per-slot data-limit config (all
            # slots, not just active).  Each slot entry mirrors the fields
            # reported for the active SIM so the show command can display
            # symmetric details for active and inactive SIMs.
            persisted = self._load_all_persisted_usage()
            # Union of slots seen on disk and slots configured in CLI
            configured_slots = {
                s.get('slot') for s in (self.config.get('sim_slots', []) if self.config else [])
                if isinstance(s.get('slot'), int)
            }
            disk_slots = set()
            for slot_key in persisted.keys():
                try:
                    disk_slots.add(int(slot_key))
                except (TypeError, ValueError):
                    continue
            all_slots = sorted(configured_slots | disk_slots)

            per_slot = {}
            for slot_num in all_slots:
                slot_data = persisted.get(str(slot_num), {}) or {}
                slot_cfg = self._get_sim_data_config(slot_num)
                slot_limit = slot_cfg.get('data_limit_size', 0) or 0
                if slot_num == active_slot:
                    # Mirror the de-duplicated active figures so the per-slot
                    # block agrees with the aggregate "Cumulative Data Usage".
                    slot_prior = active_prior
                    slot_session = session_total
                else:
                    # Inactive slot: persisted value is the final cumulative;
                    # there is no live session to add.
                    slot_prior = int(slot_data.get('bytes', 0)) if isinstance(slot_data, dict) else 0
                    slot_session = 0
                slot_total = slot_prior + slot_session
                slot_pct = round((slot_total / slot_limit) * 100, 1) if slot_limit > 0 else 0.0
                per_slot[str(slot_num)] = {
                    'is_active': slot_num == active_slot,
                    'cumulative_bytes': slot_prior,
                    'cumulative_plus_session': slot_total,
                    'session_bytes': slot_session,
                    'data_limit_bytes': slot_limit,
                    'data_limit_action': slot_cfg.get('data_limit_action', 'none'),
                    'data_limit_warning': slot_cfg.get('data_limit_warning', []),
                    'data_limit_billing_date': slot_cfg.get('data_limit_billing_date', 1),
                    'data_usage_percent': slot_pct,
                    'last_updated': slot_data.get('last_updated', '') if isinstance(slot_data, dict) else '',
                }
            status['per_slot_cumulative'] = per_slot
        except Exception:
            for k in ('cumulative_bytes', 'cumulative_plus_session',
                      'data_limit_bytes', 'data_limit_action',
                      'data_limit_billing_date', 'usage_tracking_slot',
                      'data_usage_percent'):
                status.setdefault(k, 0)
            status.setdefault('data_limit_warning', [])
            status.setdefault('per_slot_cumulative', {})

        # ── 10. Failover / recovery stats ────────────────────────────────
        status['failover_count'] = self.failover_count
        status['lifetime_failover_count'] = self.lifetime_failover_count
        status['last_failover_time'] = (
            datetime.datetime.fromtimestamp(self.last_failover_time).isoformat()
            if self.last_failover_time else ''
        )
        status['connectivity_recovery_attempts'] = self.connectivity_recovery_attempts
        status['disconnection_recovery_attempts'] = self.disconnection_recovery_attempts
        status['bearer_disconnect_count'] = self.bearer_disconnect_count
        status['registration_loss_count'] = self.registration_loss_count
        status['reconnect_attempt_count'] = self.reconnect_attempt_count
        status['reconnect_success_count'] = self.reconnect_success_count
        status['sim_switch_count'] = self.sim_switch_count
        status['total_bearer_downtime_seconds'] = self.total_bearer_downtime_seconds
        # A bearer-downtime window must never be reported while the bearer is
        # actually up: if a reconnect path forgot to call _record_bearer_up(),
        # the window would otherwise grow forever.  Treat any connected state as
        # "no current downtime".
        _connected_states = (ModemState.CONNECTED.value,
                             ModemState.USAGE_MONITORING.value)
        status['current_bearer_downtime_seconds'] = (
            max(0, int(time.time() - self._bearer_down_since))
            if self._bearer_down_since
            and self.machine.current_state not in _connected_states
            else 0
        )
        status['last_disconnect_time'] = (
            datetime.datetime.fromtimestamp(self.last_disconnect_time).isoformat()
            if self.last_disconnect_time else ''
        )
        status['last_disconnect_reason'] = self.last_disconnect_reason
        status['hardware_reset_in_progress'] = self.reset_operation_in_progress
        status['last_hardware_reset_time'] = (
            datetime.datetime.fromtimestamp(self.last_reset_time).isoformat()
            if self.last_reset_time else ''
        )

        # Boot-scoped diagnostic counters (reset on power cycle, survive
        # service/MM crashes — see interfaces_wwan_diag).
        try:
            status['service_start_count'] = wwan_diag.get('service_start_count')
            status['modemmanager_restart_count'] = wwan_diag.get('modemmanager_restart_count')
            status['modem_nuclear_reset_count'] = wwan_diag.get('modem_nuclear_reset_count')
            status['hardware_reset_count'] = wwan_diag.get(
                f'hardware_reset_count_{self.interface_number}')
        except Exception:
            for k in ('service_start_count', 'modemmanager_restart_count',
                      'modem_nuclear_reset_count', 'hardware_reset_count'):
                status.setdefault(k, 0)

        # ── 11. SIM slot details from config + physical SIM identity ────
        if self.config:
            sim_slots = self.config.get('sim_slots', [])
            for i, slot in enumerate(sim_slots):
                slot_num = i + 1
                prefix = f"sim_slot_{slot_num}"
                # Config
                status[f"{prefix}_enabled"] = slot.get('enabled', True)
                status[f"{prefix}_roaming"] = slot.get('roaming', 'enabled')
                status[f"{prefix}_pdp_type"] = slot.get('pdp_type', 'ipv4v6')
                apn_val = slot.get('apn', '')
                status[f"{prefix}_apn"] = apn_val.get('name', '') if isinstance(apn_val, dict) else str(apn_val)
                status[f"{prefix}_preferred_carrier"] = slot.get('preferred_carrier', '')
                status[f"{prefix}_data_limit_bytes"] = slot.get('data_limit_size', 0)
                status[f"{prefix}_data_limit_action"] = slot.get('data_limit_action', 'none')
                status[f"{prefix}_data_limit_warning"] = slot.get('data_limit_warning', [])

                # ICCID lock status
                configured_iccid = slot.get('iccid', '')
                status[f"{prefix}_configured_iccid"] = configured_iccid
                if slot_num == (self.current_active_sim or 0):
                    status[f"{prefix}_iccid_mismatch"] = self.iccid_mismatch if configured_iccid else False
                else:
                    status[f"{prefix}_iccid_mismatch"] = False

                # Physical SIM identity — start from cache, refresh from D-Bus
                cached = self.sim_slot_info_cache.get(slot_num, {})
                if slot_num == (self.current_active_sim or 0):
                    # Active slot: use live SIM info (section 3 already queried it)
                    status[f"{prefix}_imsi"] = status.get('sim_imsi', cached.get('imsi', ''))
                    status[f"{prefix}_iccid"] = status.get('sim_iccid', cached.get('iccid', ''))
                    status[f"{prefix}_operator"] = status.get('sim_operator', cached.get('operator', ''))
                    status[f"{prefix}_mcc_mnc"] = status.get('sim_mcc_mnc', cached.get('mcc_mnc', ''))
                    status[f"{prefix}_present"] = True
                else:
                    # Inactive slot: try D-Bus probe, fall back to cache
                    try:
                        probed = await self._probe_sim_slot_info(slot_num)
                        # Merge: probed D-Bus values win, then cache, then empty
                        status[f"{prefix}_present"] = probed.get('present', cached.get('present', False))
                        status[f"{prefix}_imsi"] = probed.get('imsi', cached.get('imsi', ''))
                        status[f"{prefix}_iccid"] = probed.get('iccid', cached.get('iccid', ''))
                        status[f"{prefix}_operator"] = probed.get('operator', cached.get('operator', ''))
                        status[f"{prefix}_mcc_mnc"] = probed.get('mcc_mnc', cached.get('mcc_mnc', ''))
                        # Update cache with any new info from probe
                        if probed:
                            merged = {**cached, **{k: v for k, v in probed.items() if v}}
                            self.sim_slot_info_cache[slot_num] = merged
                    except Exception:
                        status[f"{prefix}_present"] = cached.get('present', False)
                        status[f"{prefix}_imsi"] = cached.get('imsi', '')
                        status[f"{prefix}_iccid"] = cached.get('iccid', '')
                        status[f"{prefix}_operator"] = cached.get('operator', '')
                        status[f"{prefix}_mcc_mnc"] = cached.get('mcc_mnc', '')

        # ── 12. Key configuration summary ────────────────────────────────
        if self.config:
            status['connection_mode'] = self.config.get('connection_mode', 'always-on')
            status['android_apn_discovery'] = self.config.get('android_apn_discovery', 'enabled')
            status['enhanced_reconnection'] = (
                'enabled' if self.config.get('enhanced_reconnection', {}).get('enabled') else 'disabled'
            )
            status['connectivity_monitoring'] = (
                'enabled' if self.config.get('connectivity_monitoring', {}).get('enabled') else 'disabled'
            )
            status['interface_management'] = (
                'enabled' if self.config.get('interface_management', {}).get('enabled') else 'disabled'
            )

            # Registration flap detection status
            flap_window = getattr(self, 'registration_flap_window', 360)
            flap_count = getattr(self, 'registration_flap_count', 5)
            now = time.monotonic()
            cutoff = now - flap_window
            recent_flaps = [t for t in self._registration_flap_timestamps if t > cutoff]
            status['registration_flap_count_configured'] = flap_count
            status['registration_flap_window_configured'] = flap_window
            status['registration_flap_events_in_window'] = len(recent_flaps)
            status['registration_flap_failover_triggered'] = self._registration_flap_failover_triggered

            status['network_mode'] = self.config.get('network_mode', 'auto')
            status['verbose_logging'] = self.config.get('verbose_logging', True)
            status['log_level'] = self.config.get('log_level', getattr(self, 'log_level', 'info'))
            status['log_sink'] = self.config.get('log_sink', getattr(self, 'log_sink', 'both'))

        # ── 13. Network scan results (if available) ──────────────────────
        if self.last_scan_results:
            status['available_networks'] = self.last_scan_results

        # ── 14. SMS status ───────────────────────────────────────────────
        sms_supported = False
        sms_message_count = 0
        sms_unread_count = 0
        if self.modem_path:
            try:
                introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, self.modem_path)
                proxy = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, self.modem_path, introspect)
                # Check if Messaging interface exists on this modem
                try:
                    proxy.get_interface(MESSAGING_INTERFACE)
                    sms_supported = True
                except Exception:
                    pass
            except Exception:
                pass
        # Count messages in flat-file store
        try:
            messages = self._sms_load()
            sms_message_count = len(messages)
            sms_unread_count = sum(
                1 for m in messages
                if m.get('direction') == 'incoming' and not m.get('read', False)
            )
        except Exception:
            pass
        status['sms_supported'] = sms_supported
        status['sms_message_count'] = sms_message_count
        status['sms_unread_count'] = sms_unread_count

        return status

    @staticmethod
    def _access_tech_to_string(bitmask) -> str:
        """Convert MM AccessTechnologies bitmask to human-readable string."""
        if not bitmask or not isinstance(bitmask, int):
            return 'unknown'
        techs = []
        # ModemManager MMModemAccessTechnology flags
        tech_map = {
            1 << 0: 'POTS',
            1 << 1: 'GSM',
            1 << 2: 'GSM Compact',
            1 << 3: 'GPRS',
            1 << 4: 'EDGE',
            1 << 5: 'UMTS',
            1 << 6: 'HSDPA',
            1 << 7: 'HSUPA',
            1 << 8: 'HSPA',
            1 << 9: 'HSPA+',
            1 << 10: '1xRTT',
            1 << 11: 'EVDO0',
            1 << 12: 'EVDO-A',
            1 << 13: 'EVDO-B',
            1 << 14: 'LTE',
            1 << 15: '5GNR',
            1 << 16: 'LTE-CA',
        }
        for flag, name in tech_map.items():
            if bitmask & flag:
                techs.append(name)
        return ', '.join(techs) if techs else 'unknown'

    def _band_to_string(self, band_id) -> str:
        """Render an MM band constant as its canonical CLI token.

        The returned token is exactly what ``supported-bands`` accepts
        (lowercase ``eutran-7``, ``ngran-78``, ``umts-1``, ``egsm-900`` …),
        so a band shown in status can be copied straight into a ``set``
        command.  Accepts numeric or already-canonical input.
        """
        if hasattr(band_id, 'value'):
            band_id = band_id.value

        try:
            band_id = int(band_id)
        except (TypeError, ValueError):
            return f'band-{band_id}'

        # Named bands (GSM + legacy 3G) and any explicitly-mapped LTE/NR band.
        name = self._mm_constant_to_band_name(band_id)
        if not name.startswith('unknown-'):
            return name

        # Algorithmic fallback for bands not in the mapping table.  These
        # mirror _band_name_to_mm_constant so display and input round-trip.
        if 300 <= band_id <= 1000:      # MM_MODEM_BAND_NGRAN_N = 300 + N
            return f'ngran-{band_id - 300}'
        if 201 <= band_id <= 299:       # modern MM_MODEM_BAND_UTRAN_N = 200 + N
            return f'umts-{band_id - 200}'
        if 31 <= band_id <= 199:        # MM_MODEM_BAND_EUTRAN_N = 30 + N
            return f'eutran-{band_id - 30}'
        return f'band-{band_id}'

    @staticmethod
    def _lte_earfcn_to_band(earfcn) -> str:
        """Map an LTE downlink EARFCN to a band label (e.g. EUTRAN-66).

        Returns '' if the EARFCN does not fall into a known band range.
        Reference: 3GPP TS 36.101 Table 5.7.3-1.
        """
        try:
            n = int(earfcn)
        except (TypeError, ValueError):
            return ''
        # (low, high, band) ranges, downlink EARFCN.
        ranges = [
            (0, 599, 1), (600, 1199, 2), (1200, 1949, 3), (1950, 2399, 4),
            (2400, 2649, 5), (2650, 2749, 6), (2750, 3449, 7),
            (3450, 3799, 8), (3800, 4149, 9), (4150, 4749, 10),
            (4750, 4949, 11), (5010, 5179, 12), (5180, 5279, 13),
            (5280, 5379, 14), (5730, 5849, 17), (5850, 5999, 18),
            (6000, 6149, 19), (6150, 6449, 20), (6450, 6599, 21),
            (6600, 7399, 22), (7500, 7699, 23), (7700, 8039, 24),
            (8040, 8689, 25), (8690, 9039, 26), (9040, 9209, 27),
            (9210, 9659, 28), (9660, 9769, 29), (9770, 9869, 30),
            (9870, 9919, 31), (9920, 10359, 32),
            (36000, 36199, 33), (36200, 36349, 34), (36350, 36949, 35),
            (36950, 37549, 36), (37550, 37749, 37),
            (37750, 38249, 38), (38250, 38649, 39), (38650, 39649, 40),
            (39650, 41589, 41), (41590, 43589, 42), (43590, 45589, 43),
            (45590, 46589, 44), (46590, 46789, 45), (46790, 54539, 46),
            (54540, 55239, 47), (55240, 56739, 48), (56740, 58239, 49),
            (58240, 59089, 50), (59090, 59139, 51), (59140, 60139, 52),
            (60140, 60254, 53),
            (65536, 66435, 65), (66436, 67335, 66), (67336, 67535, 67),
            (67536, 67835, 68), (67836, 68335, 69), (68336, 68585, 70),
            (68586, 68935, 71), (68936, 68985, 72), (68986, 69035, 73),
            (69036, 69465, 74), (69466, 70315, 75), (70316, 70365, 76),
            (70366, 70545, 85), (70546, 70595, 87), (70596, 70645, 88),
        ]
        for lo, hi, band in ranges:
            if lo <= n <= hi:
                return f'EUTRAN-{band}'
        return ''

    async def update_bus_connection(self, new_bus):
        """Update D-Bus connection after ModemManager restart"""
        logger.info("Updating bus connection",
                   extra={'interface_number': self.interface_number})

        # Stop usage monitoring if running
        if self.usage_monitor_task:
            self.usage_monitor_task.cancel()
            self.usage_monitor_task = None

        self.bus = new_bus
        self.proxy = None
        self.modem_path = None
        self.bearer_path = None

        # Reset to initial state. ``FiniteMachine.current_state`` is a
        # read-only property — assigning to it raises
        # ``AttributeError: property 'current_state' of 'FiniteMachine'
        # object has no setter``. The supported reset path is to call
        # ``initialize()`` again, which re-seeds the machine to
        # ``default_start_state`` (ModemState.INITIAL — see __init__).
        try:
            self.machine.initialize()
        except Exception as e:
            logger.warning(f"FSM machine re-initialize failed: {e}",
                          extra={'interface_number': self.interface_number})
        await self.initialize()

    async def shutdown(self):
        """Graceful shutdown of the FSM.

        Cancels all background tasks (including failed-state retry timers
        that would otherwise reconnect after we disconnect) and forces
        the bearer down on ModemManager.  We do NOT gate the disconnect
        on the FSM's internal ``current_state`` because the modem may be
        connected via an externally-established bearer (or our state may
        not have caught up yet) — in that case we still want the bearer
        torn down on `del interfaces wwan wwanN`.
        """
        logger.info("Shutting down FSM",
                   extra={'interface_number': self.interface_number})

        # CRITICAL: set user_disconnected BEFORE doing anything else.
        # This flag is checked by handle_disconnection_recovery() and the
        # bearer-disconnect signal handlers — without it, our intentional
        # disconnect below is treated as an unexpected bearer drop and
        # the enhanced-reconnection path immediately re-establishes the
        # bearer (observed in production: "Disconnection recovery
        # attempt 1/3" firing right after we disconnect).
        self.user_disconnected = True
        # Mark shutdown explicitly — used as belt-and-suspenders for any
        # code path that might not check user_disconnected.
        self._shutting_down = True

        # Cancel failed-state retry timer (would reconnect after disconnect)
        try:
            self._cancel_failed_retry()
        except Exception as e:
            logger.debug(f"Error cancelling failed-retry during shutdown: {e}",
                        extra={'interface_number': self.interface_number})

        # Stop the GPIO-mux SIM-detect watcher thread (no-op for the
        # ModemManager-managed controller).
        try:
            self.sim_controller.stop_watch()
        except Exception as e:
            logger.debug(f"Error stopping SIM-detect watcher during shutdown: {e}",
                        extra={'interface_number': self.interface_number})

        # Cancel usage monitoring
        if self.usage_monitor_task and not self.usage_monitor_task.done():
            self.usage_monitor_task.cancel()
        self.usage_monitor_task = None

        # Cancel connectivity monitoring
        if (hasattr(self, 'connectivity_monitor_task')
                and self.connectivity_monitor_task
                and not self.connectivity_monitor_task.done()):
            self.connectivity_monitor_task.cancel()
            self.connectivity_monitor_task = None

        # Stop network interface monitoring (bearer signal, IP change, etc.)
        try:
            await self._stop_network_interface_monitoring()
        except Exception as e:
            logger.debug(f"Error stopping netdev monitoring during shutdown: {e}",
                        extra={'interface_number': self.interface_number})

        # Cancel failback check task
        if (hasattr(self, 'failback_task') and self.failback_task
                and not self.failback_task.done()):
            self.failback_task.cancel()
            self.failback_task = None

        # Cancel any in-progress initial configuration task
        if (hasattr(self, '_initial_config_task') and self._initial_config_task
                and not self._initial_config_task.done()):
            self._initial_config_task.cancel()
            self._initial_config_task = None

        # Cancel bearer-disconnect debounce timer (would otherwise still
        # fire and trigger handle_disconnection_recovery — gated now by
        # user_disconnected but cancel anyway to avoid log noise)
        if (hasattr(self, '_bearer_disconnect_timer')
                and self._bearer_disconnect_timer
                and not self._bearer_disconnect_timer.done()):
            self._bearer_disconnect_timer.cancel()
            self._bearer_disconnect_timer = None

        # Cancel registration debounce timer
        if (hasattr(self, '_registration_debounce_timer')
                and self._registration_debounce_timer
                and not self._registration_debounce_timer.done()):
            self._registration_debounce_timer.cancel()
            self._registration_debounce_timer = None

        # Force-disconnect the bearer unconditionally — do NOT gate on
        # current_state, because the FSM's internal state may lag the
        # real modem state (e.g. when an empty config was applied and a
        # bearer was auto-established by ModemManager).  If we don't
        # know the exact bearer path, pass '/' to disconnect all
        # bearers on this modem (ModemManager convention).
        if self.proxy:
            try:
                simple_iface = self.proxy.get_interface(SIMPLE_INTERFACE)
                target = self.bearer_path if self.bearer_path else '/'
                await simple_iface.call_disconnect(target)
                logger.info("Bearer disconnected during shutdown",
                           extra={'interface_number': self.interface_number,
                                  'bearer_path': target})
            except Exception as e:
                logger.error(f"Error disconnecting bearer during shutdown: {e}",
                           extra={'interface_number': self.interface_number})
            self.bearer_path = None

        # Tear down every downstream artifact (passthrough,
        # ipv6-bridging, FSM MSS clamp, link DOWN).  Same cleanup the
        # admin-disable path performs — operator deleting the interface
        # expects no LAN-side state to linger.
        try:
            await self._teardown_downstream_features()
        except Exception as e:
            logger.warning(f"Downstream teardown failed during shutdown: {e}",
                          extra={'interface_number': self.interface_number})

        # Remove from global registry
        ModemStateMachine.modem_state_machines.pop(f"wwan{self.interface_number}", None)

        logger.info("FSM shutdown complete",
                   extra={'interface_number': self.interface_number})

    async def _admin_disable(self):
        """Administratively disable the interface.

        Disconnects the bearer, cancels all monitoring and retry tasks,
        and stops network interface monitoring.  The FSM stays in memory
        so it can be re-enabled later via a config update with
        ``interface_disabled: False``.
        """
        try:
            # Cancel failed-state retry timer
            self._cancel_failed_retry()

            # Cancel usage monitoring
            if self.usage_monitor_task and not self.usage_monitor_task.done():
                self.usage_monitor_task.cancel()
                self.usage_monitor_task = None

            # Cancel connectivity monitoring
            if hasattr(self, 'connectivity_monitor_task') and self.connectivity_monitor_task and not self.connectivity_monitor_task.done():
                self.connectivity_monitor_task.cancel()
                self.connectivity_monitor_task = None

            # Stop network interface monitoring (bearer signal, IP change, etc.)
            await self._stop_network_interface_monitoring()

            # Cancel failback check task
            if self.failback_task and not self.failback_task.done():
                self.failback_task.cancel()
                self.failback_task = None

            # Cancel any in-progress initial configuration task
            if self._initial_config_task and not self._initial_config_task.done():
                self._initial_config_task.cancel()
                self._initial_config_task = None

            # Disconnect bearer if connected
            if self.bearer_path and self.proxy:
                try:
                    simple_iface = self.proxy.get_interface(SIMPLE_INTERFACE)
                    await simple_iface.call_disconnect(self.bearer_path)
                    logger.info("Bearer disconnected for admin disable",
                               extra={'interface_number': self.interface_number})
                except Exception as e:
                    logger.error(f"Error disconnecting bearer during admin disable: {e}",
                               extra={'interface_number': self.interface_number})
                self.bearer_path = None
            elif self.proxy:
                # No tracked bearer path, but the modem may have an
                # auto-established bearer (initial-EPS) we need to drop.
                try:
                    simple_iface = self.proxy.get_interface(SIMPLE_INTERFACE)
                    await simple_iface.call_disconnect('/')
                    logger.info("All bearers disconnected for admin disable",
                               extra={'interface_number': self.interface_number})
                except Exception as e:
                    logger.debug(f"Disconnect-all returned (non-fatal): {e}",
                                extra={'interface_number': self.interface_number})

            # Tear down every downstream artifact (passthrough,
            # ipv6-bridging, FSM MSS clamp, link DOWN).  Done BEFORE we
            # power the modem off so that any feature whose teardown
            # needs working network/DBus state can still complete.
            await self._teardown_downstream_features()

            # Drive modem into airplane mode (RF off) — this is the real
            # "off" the user expects when they `set ... disable`.  If the
            # modem isn't bound yet (proxy is None), the flag is set and
            # the airplane transition runs from on_modem_found() once we
            # bind to MM.
            await self._enter_airplane_mode()

            logger.info("Interface admin-disabled — modem idle, all tasks cancelled",
                       extra={'interface_number': self.interface_number,
                              'previous_state': self.machine.current_state})

        except Exception as e:
            logger.error(f"Error during admin disable: {e}",
                       extra={'interface_number': self.interface_number})

    async def _teardown_downstream_features(self):
        """Tear down every FSM-installed downstream artifact.

        Used by both ``shutdown()`` (interface deleted) and
        ``_admin_disable()`` (interface administratively disabled) so the
        operator sees a clean slate on the LAN side regardless of which
        path was taken.  Idempotent — each sub-teardown is gated on
        whether the feature was actually active.

        Cleans up:
          * IP passthrough (dnsmasq, policy routes, conntrack rules)
          * IPv6 bridging (LAN /64 address, proxy-NDP entries, radvd,
            sysctl restores, netlink watcher tasks)
          * FSM-owned mangle/FORWARD TCPMSS clamp rules (v4 + v6)
          * Sets the wwanN link DOWN so no stale IPs linger
        """
        interface_name = f"wwan{self.interface_number}"

        # IP passthrough — only torn down if the manager believes it is
        # active.  teardown() is itself idempotent but this avoids log noise.
        try:
            if hasattr(self, '_passthrough') and self._passthrough.cfg.is_active():
                await self._passthrough.teardown()
                logger.info("IP passthrough torn down",
                           extra={'interface_number': self.interface_number})
        except Exception as e:
            logger.warning(f"IP passthrough teardown failed: {e}",
                          extra={'interface_number': self.interface_number})

        # IPv6 bridging — remove bridged /64, proxy-NDP, stop radvd,
        # cancel background netlink watcher.
        try:
            if (hasattr(self, '_bridging_applied') and self._bridging_applied):
                await self._bridging_remove_all()
                logger.info("IPv6 bridging torn down",
                           extra={'interface_number': self.interface_number})
        except Exception as e:
            logger.warning(f"IPv6 bridging teardown failed: {e}",
                          extra={'interface_number': self.interface_number})

        # FSM-owned MSS clamp (mangle/FORWARD TCPMSS rules)
        try:
            if (getattr(self, '_fsm_mss_clamp_v4_active', False)
                    or getattr(self, '_fsm_mss_clamp_v6_active', False)):
                await self._remove_fsm_mss_clamp(interface_name)
        except Exception as e:
            logger.warning(f"FSM MSS clamp removal failed: {e}",
                          extra={'interface_number': self.interface_number})

        # Set the link DOWN so any address ModemManager leaves behind
        # is not advertised, and so downstream code sees the interface
        # as offline.  Gated by interface_management_enabled internally.
        try:
            await self._set_interface_down()
        except Exception as e:
            logger.warning(f"Set interface down failed: {e}",
                          extra={'interface_number': self.interface_number})

    async def _enter_airplane_mode(self):
        """Drive the modem into low-power RF-off state.

        Sequence: Modem.Enable(False) → Modem.SetPowerState(LOW).
        Some modems reject SetPowerState while still enabled, so disable
        first.  If SetPowerState is unsupported, we fall back to leaving
        the modem disabled — caller has already torn down the bearer.
        """
        if not self.proxy:
            logger.info("Modem not bound yet — airplane mode will apply when modem appears",
                       extra={'interface_number': self.interface_number})
            self._airplane_mode_requested = True
            return

        self._airplane_mode_requested = True
        try:
            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
            modem_iface = self.proxy.get_interface(MODEM_INTERFACE)

            # Step 1: disable the modem (state 3 = DISABLED).  If already
            # disabled, this is a no-op.  ModemManager rejects power-state
            # changes on an enabled modem on most drivers.
            try:
                state_v = await props.call_get(MODEM_INTERFACE, "State")
                state = state_v.value
                if state >= 6:  # ENABLING or higher — needs disable first
                    try:
                        await modem_iface.call_enable(False)
                        logger.info("Modem disabled for airplane mode",
                                   extra={'interface_number': self.interface_number})
                        # Brief settle — MM signals propagate
                        await asyncio.sleep(1)
                    except Exception as e:
                        logger.warning(f"Modem disable failed (continuing to power-state): {e}",
                                      extra={'interface_number': self.interface_number})
            except Exception as e:
                logger.debug(f"Could not read Modem.State (continuing): {e}",
                            extra={'interface_number': self.interface_number})

            # Step 2: power state LOW (2).  Most modern QMI modems
            # support this; if not, log and leave the modem disabled.
            try:
                await modem_iface.call_set_power_state(2)
                logger.info("Modem RF disabled (PowerState=LOW) — airplane mode active",
                           extra={'interface_number': self.interface_number})
                self._airplane_mode_active = True
            except Exception as e:
                logger.warning(
                    f"SetPowerState(LOW) failed: {e} — modem remains disabled only",
                    extra={'interface_number': self.interface_number})
                self._airplane_mode_active = False
        except Exception as e:
            logger.error(f"Error entering airplane mode: {e}",
                        extra={'interface_number': self.interface_number})

    async def _exit_airplane_mode_if_needed(self):
        """Restore modem power state to ON if we previously set it to LOW.

        Called when the interface is re-enabled.  The subsequent normal
        flow (``_ensure_modem_enabled``) handles the Enable(True) step;
        here we only need to bring power back up so Enable() will be
        accepted.
        """
        # Clear the request flag unconditionally — caller wants normal ops
        self._airplane_mode_requested = False

        if not self.proxy:
            self._airplane_mode_active = False
            return

        try:
            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
            modem_iface = self.proxy.get_interface(MODEM_INTERFACE)
            ps_v = await props.call_get(MODEM_INTERFACE, "PowerState")
            ps = ps_v.value
            # PowerState: 0=unknown, 1=off, 2=low, 3=on
            if ps != 3:
                logger.info(f"Exiting airplane mode (PowerState={ps} → ON)",
                           extra={'interface_number': self.interface_number})
                try:
                    await modem_iface.call_set_power_state(3)
                    # Modem firmware may take a few seconds to bring the
                    # RF subsystem back up before Enable() will succeed.
                    await asyncio.sleep(3)
                except Exception as e:
                    logger.warning(f"SetPowerState(ON) failed: {e}",
                                  extra={'interface_number': self.interface_number})
            self._airplane_mode_active = False
        except Exception as e:
            logger.error(f"Error exiting airplane mode: {e}",
                        extra={'interface_number': self.interface_number})
            self._airplane_mode_active = False

    async def handle_disconnection_recovery(self, escalate=True,
                                              connectivity_triggered=False):
        """Handle automatic reconnection after network disconnection.

        When *escalate* is True (default, used for bearer-drop recovery),
        the modem-registered branch retries up to max_recovery_before_sim_switch
        times and then escalates to SIM failover if available.

        When *escalate* is False (used by _trigger_connectivity_recovery which
        has its own escalation counter), only a single reconnection attempt is
        made so that the caller controls retry/escalation.

        When *connectivity_triggered* is True, the caller has already
        determined (via ping tests) that the data path is dead.  If
        ModemManager still reports state 11 (CONNECTED), we treat it as
        a stale bearer: force-disconnect and re-establish rather than
        trusting ModemManager's state.
        """
        try:
            logger.info("Network disconnection detected, starting recovery",
                       extra={'interface_number': self.interface_number,
                              'current_state': self.machine.current_state})

            # Don't auto-recover if user requested disconnect
            if self.user_disconnected:
                logger.info("User-initiated disconnect detected, skipping auto-recovery",
                           extra={'interface_number': self.interface_number})
                return

            # Save bearer path before clearing (needed for stale bearer teardown)
            saved_bearer_path = self.bearer_path
            self.bearer_path = None

            # Stop monitoring tasks if still running
            if self.usage_monitor_task and not self.usage_monitor_task.done():
                self.usage_monitor_task.cancel()
                self.usage_monitor_task = None

            # 🆕 Stop connectivity monitoring
            if hasattr(self, 'connectivity_monitor_task') and self.connectivity_monitor_task:
                self.connectivity_monitor_task.cancel()
                self.connectivity_monitor_task = None

            # Check if we have configuration to attempt reconnection
            if not self.config:
                logger.warning("No configuration available for reconnection",
                              extra={'interface_number': self.interface_number})
                return

            # Wait a moment for network to stabilize
            await asyncio.sleep(5)

            # Check modem state - see if it recovered automatically
            if self.proxy:
                props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
                mm_state_variant = await props.call_get(MODEM_INTERFACE, "State")
                mm_state = mm_state_variant.value

                logger.info("Checking modem state for recovery",
                           extra={'interface_number': self.interface_number,
                                  'modem_state': mm_state})

                if mm_state == 11:  # Already CONNECTED
                    if not connectivity_triggered:
                        # Verify the bearer is actually connected before
                        # trusting MM state — MM may still report state 11
                        # briefly after the bearer drops ("Regular
                        # deactivation").  If we return early here the FSM
                        # is stuck in DISCONNECTING with no recovery path.
                        bearer_really_connected = False
                        if saved_bearer_path:
                            try:
                                bp_introspect = await self.bus.introspect(
                                    'org.freedesktop.ModemManager1',
                                    saved_bearer_path)
                                bp_proxy = self.bus.get_proxy_object(
                                    'org.freedesktop.ModemManager1',
                                    saved_bearer_path,
                                    bp_introspect)
                                bp_props = bp_proxy.get_interface(
                                    'org.freedesktop.DBus.Properties')
                                bp_connected_var = await bp_props.call_get(
                                    'org.freedesktop.ModemManager1.Bearer',
                                    'Connected')
                                bearer_really_connected = bp_connected_var.value
                            except Exception as bp_err:
                                logger.debug(
                                    f"Could not verify bearer connected "
                                    f"state: {bp_err}",
                                    extra={
                                        'interface_number':
                                            self.interface_number})

                        if bearer_really_connected:
                            logger.info(
                                "Modem automatically reconnected "
                                "(bearer verified connected)",
                                extra={
                                    'interface_number':
                                        self.interface_number})
                            # Restore bearer path so signal monitoring
                            # and IP config continue to work.
                            self.bearer_path = saved_bearer_path
                            return

                        # Bearer is disconnected but MM still reports
                        # state 11 — fall through to stale-bearer
                        # handling (same path as connectivity_triggered).
                        logger.warning(
                            "MM reports CONNECTED but bearer is "
                            "disconnected — treating as stale bearer",
                            extra={
                                'interface_number':
                                    self.interface_number,
                                'saved_bearer_path':
                                    saved_bearer_path})

                    # Stale bearer: MM says CONNECTED but pings prove
                    # the data path is dead.  Force-disconnect the bearer
                    # and re-establish the connection.
                    logger.warning(
                        "Stale bearer detected: MM reports CONNECTED "
                        "but connectivity checks failed — "
                        "force-disconnecting",
                        extra={
                            'interface_number': self.interface_number,
                            'saved_bearer_path': saved_bearer_path})
                    try:
                        if self.proxy:
                            simple_iface = self.proxy.get_interface(
                                SIMPLE_INTERFACE)
                            # Use saved path or '/' to disconnect all
                            disconnect_path = saved_bearer_path or '/'
                            await asyncio.wait_for(
                                simple_iface.call_disconnect(
                                    disconnect_path),
                                timeout=30)
                            logger.info(
                                "Stale bearer disconnected",
                                extra={
                                    'interface_number':
                                        self.interface_number})
                    except asyncio.TimeoutError:
                        logger.error(
                            "Force-disconnect timed out after 30s",
                            extra={
                                'interface_number':
                                    self.interface_number})
                    except Exception as e:
                        logger.error(
                            f"Force-disconnect failed: {e}",
                            extra={
                                'interface_number':
                                    self.interface_number})

                    # Wait for MM to process the disconnect
                    await asyncio.sleep(3)

                    # Attempt reconnection after stale bearer teardown
                    logger.info(
                        "Attempting reconnection after stale bearer "
                        "teardown",
                        extra={
                            'interface_number': self.interface_number})
                    # Move FSM to CONFIGURING so the connection flow
                    # (handle_modem_event states 7→8→10→11) works.
                    if self.machine.current_state == ModemState.DISCONNECTING.value:
                        self.transition(ModemEvent.CONFIG_UPDATE)
                    elif self.machine.current_state == ModemState.DISCONNECTED.value:
                        self.transition(ModemEvent.RECONFIGURE)
                    if self.enhanced_reconnection:
                        success = await (
                            self._enhanced_reconnection_attempt())
                        if not success:
                            logger.warning(
                                "Enhanced reconnection failed after "
                                "stale bearer, falling back to "
                                "standard",
                                extra={
                                    'interface_number':
                                        self.interface_number})
                            self._record_reconnect_attempt('standard_recovery_fallback')
                            await self.apply_modem_configuration()
                    else:
                        self._record_reconnect_attempt('standard_recovery')
                        await self.apply_modem_configuration()

                elif mm_state == 8:  # REGISTERED but not connected
                    # Move FSM to CONFIGURING so the connection flow
                    # (handle_modem_event states 7→8→10→11) works.
                    if self.machine.current_state == ModemState.DISCONNECTING.value:
                        self.transition(ModemEvent.CONFIG_UPDATE)
                    elif self.machine.current_state == ModemState.DISCONNECTED.value:
                        self.transition(ModemEvent.RECONFIGURE)
                    if escalate:
                        # Retry loop with SIM failover escalation
                        for attempt in range(1, self.max_recovery_before_sim_switch + 1):
                            self.disconnection_recovery_attempts = attempt
                            logger.info(
                                "Disconnection recovery attempt "
                                f"{attempt}/{self.max_recovery_before_sim_switch}",
                                extra={'interface_number': self.interface_number,
                                       'attempt': attempt,
                                       'max_attempts': self.max_recovery_before_sim_switch})

                            # Attempt reconnection
                            if self.enhanced_reconnection:
                                success = await self._enhanced_reconnection_attempt()
                                if not success:
                                    logger.warning(
                                        "Enhanced reconnection failed, falling back to standard",
                                        extra={'interface_number': self.interface_number,
                                               'attempt': attempt})
                                    self._record_reconnect_attempt('standard_recovery_fallback')
                                    await self.apply_modem_configuration()
                            else:
                                self._record_reconnect_attempt('standard_recovery')
                                await self.apply_modem_configuration()

                            # Allow time for connection to establish
                            await asyncio.sleep(10)

                            # Re-check modem state
                            mm_state_variant = await props.call_get(MODEM_INTERFACE, "State")
                            mm_state_now = mm_state_variant.value

                            if mm_state_now == 11:  # CONNECTED
                                logger.info(
                                    "Disconnection recovery succeeded",
                                    extra={'interface_number': self.interface_number,
                                           'attempt': attempt})
                                self.disconnection_recovery_attempts = 0
                                return

                            if mm_state_now not in [8, 6, 7]:  # Left recoverable state
                                logger.warning(
                                    "Modem left recoverable state during recovery",
                                    extra={'interface_number': self.interface_number,
                                           'modem_state': mm_state_now,
                                           'attempt': attempt})
                                break

                            # Backoff before next attempt
                            if attempt < self.max_recovery_before_sim_switch:
                                backoff = min(10 * attempt, 30)
                                logger.info(
                                    f"Waiting {backoff}s before next recovery attempt",
                                    extra={'interface_number': self.interface_number,
                                           'backoff': backoff})
                                await asyncio.sleep(backoff)

                        # All retries exhausted — escalate to SIM failover
                        logger.warning(
                            "Disconnection recovery exhausted on current SIM",
                            extra={'interface_number': self.interface_number,
                                   'attempts': self.disconnection_recovery_attempts,
                                   'current_sim': self.current_active_sim})

                        # Escalate to SIM failover via the shared executor
                        # (probes SimSlots for a present alternate, applies
                        # cooldown/lock gating).  Reset the recovery counter
                        # only once the switch is under way so the new SIM
                        # starts fresh; otherwise fail.
                        switched = await self._failover_to_alternate_sim(
                            'disconnection_recovery_exhausted',
                            'handle_disconnection_recovery',
                            switch_reason='disconnection_recovery_exhausted',
                            extra_data={'recovery_attempts':
                                        self.max_recovery_before_sim_switch})
                        if switched:
                            self.disconnection_recovery_attempts = 0
                            return

                        # No SIM failover available
                        self.transition(ModemEvent.CONNECTION_FAILED)

                    else:
                        # Single attempt — caller handles escalation
                        logger.info("Modem registered, attempting reconnection",
                                   extra={'interface_number': self.interface_number})
                        if self.enhanced_reconnection:
                            success = await self._enhanced_reconnection_attempt()
                            if not success:
                                logger.warning(
                                    "Enhanced reconnection failed, "
                                    "falling back to standard",
                                    extra={'interface_number': self.interface_number})
                                self._record_reconnect_attempt('standard_recovery_fallback')
                                await self.apply_modem_configuration()
                        else:
                            self._record_reconnect_attempt('standard_recovery')
                            await self.apply_modem_configuration()

                elif mm_state in [6, 7]:  # ENABLED or SEARCHING
                    # Previously this branch only logged and returned, which could
                    # leave the FSM stuck in DISCONNECTING forever if no follow-up
                    # state transition arrived. Actively wait for registration and
                    # then retry recovery, otherwise escalate.
                    if self.machine.current_state == ModemState.DISCONNECTING.value:
                        # Teardown already happened; don't expose prolonged
                        # registration wait as DISCONNECTING.
                        self.transition(ModemEvent.DISCONNECTED)

                    registration_wait = self._get_registration_timeout()
                    poll_interval = 5
                    deadline = time.monotonic() + registration_wait

                    logger.info(
                        "Modem searching for network during disconnection recovery; "
                        "waiting for registration before reconnect",
                        extra={'interface_number': self.interface_number,
                               'modem_state': mm_state,
                               'registration_wait_seconds': registration_wait,
                               'poll_interval_seconds': poll_interval})

                    while time.monotonic() < deadline:
                        await asyncio.sleep(poll_interval)

                        if self.user_disconnected:
                            logger.info(
                                "User disconnected while waiting for registration; "
                                "aborting automatic recovery",
                                extra={'interface_number': self.interface_number})
                            return

                        try:
                            mm_state_variant = await props.call_get(MODEM_INTERFACE, "State")
                            mm_state_now = mm_state_variant.value
                        except Exception as state_err:
                            logger.debug(
                                f"Could not read modem state while waiting for registration: {state_err}",
                                extra={'interface_number': self.interface_number})
                            continue

                        if mm_state_now in [6, 7]:
                            continue

                        if mm_state_now in [8, 11]:
                            logger.info(
                                "Modem left searching state; retrying disconnection recovery",
                                extra={'interface_number': self.interface_number,
                                       'modem_state': mm_state_now})
                            await self.handle_disconnection_recovery(
                                escalate=escalate,
                                connectivity_triggered=connectivity_triggered,
                            )
                            return

                        logger.warning(
                            "Modem left searching state without registration; "
                            "escalating disconnection recovery",
                            extra={'interface_number': self.interface_number,
                                   'modem_state': mm_state_now})
                        break
                    else:
                        logger.warning(
                            "Timed out waiting for modem registration during disconnection recovery",
                            extra={'interface_number': self.interface_number,
                                   'timeout_seconds': registration_wait})

                    # Escalate to SIM failover (when enabled) before declaring failure.
                    # The shared executor probes for a present alternate slot and
                    # applies cooldown/lock gating; the escalate flag stays here.
                    if escalate:
                        switched = await self._failover_to_alternate_sim(
                            'registration_recovery_timeout',
                            'handle_disconnection_recovery',
                            switch_reason='registration_recovery_timeout',
                            extra_data={'registration_timeout_seconds': registration_wait})
                        if switched:
                            self.disconnection_recovery_attempts = 0
                            return

                    self.transition(ModemEvent.CONNECTION_FAILED)

                elif mm_state in [2, 3]:  # LOCKED or DISABLED - potential SIM issue
                    logger.warning("Modem in locked/disabled state, checking for SIM issues",
                                  extra={'interface_number': self.interface_number,
                                         'modem_state': mm_state})

                    # Check if SIM failover is enabled for the active slot
                    if self._is_sim_failover_enabled():
                        # Attempt SIM failover
                        failover_success = await self._handle_sim_missing_failover()
                        if not failover_success:
                            # No alternative SIM, wait for configured SIM
                            self.transition(ModemEvent.SIM_MISSING)
                    else:
                        # Wait for configured SIM
                        self.transition(ModemEvent.SIM_MISSING)

                else:  # Failed or unknown states
                    logger.error("Modem in failed state during recovery",
                                extra={'interface_number': self.interface_number,
                                       'modem_state': mm_state})
                    self.transition(ModemEvent.CONNECTION_FAILED)

        except Exception as e:
            logger.error(f"Disconnection recovery failed: {e}",
                        extra={'interface_number': self.interface_number})
            self.transition(ModemEvent.CONNECTION_FAILED)

    async def start_connectivity_monitoring(self):
        """Start connectivity health monitoring with configurable ping tests"""
        if not self.config:
            return

        # Check if connectivity monitoring is enabled
        connectivity_config = self.config.get('connectivity_monitoring', {})
        if not connectivity_config.get('enabled', True):
            logger.info("Connectivity monitoring disabled",
                       extra={'interface_number': self.interface_number})
            return

        logger.info("Starting connectivity health monitoring",
                   extra={'interface_number': self.interface_number,
                          'config': connectivity_config})

        # Start monitoring task
        if not hasattr(self, 'connectivity_monitor_task') or self.connectivity_monitor_task is None:
            self.connectivity_monitor_task = self._safe_create_task(self._connectivity_monitor_loop())

    async def _connectivity_monitor_loop(self):
        """Main connectivity monitoring loop with ping tests"""
        if not self.config:
            return

        connectivity_config = self.config.get('connectivity_monitoring', {})

        # Configuration with defaults from central dict
        interval = connectivity_config.get('interval', DEFAULT_CONNECTIVITY_CONFIG['interval'])
        timeout = connectivity_config.get('timeout', DEFAULT_CONNECTIVITY_CONFIG['timeout'])
        retry_count = connectivity_config.get('retry_count', DEFAULT_CONNECTIVITY_CONFIG['retry_count'])
        failure_threshold = connectivity_config.get('failure_threshold', DEFAULT_CONNECTIVITY_CONFIG['failure_threshold'])

        # Ping targets
        ipv4_targets = connectivity_config.get('ipv4_targets', DEFAULT_CONNECTIVITY_CONFIG['ipv4_targets'])
        ipv6_targets = connectivity_config.get('ipv6_targets', DEFAULT_CONNECTIVITY_CONFIG['ipv6_targets'])

        # Test configuration
        test_ipv4 = connectivity_config.get('test_ipv4', DEFAULT_CONNECTIVITY_CONFIG['test_ipv4'])
        test_ipv6 = connectivity_config.get('test_ipv6', DEFAULT_CONNECTIVITY_CONFIG['test_ipv6'])
        require_both = connectivity_config.get('require_both', DEFAULT_CONNECTIVITY_CONFIG['require_both'])

        consecutive_failures = 0

        logger.info("Connectivity monitoring started",
                   extra={'interface_number': self.interface_number,
                          'interval': interval,
                          'ipv4_targets': ipv4_targets if test_ipv4 else [],
                          'ipv6_targets': ipv6_targets if test_ipv6 else [],
                          'require_both': require_both,
                          'failure_threshold': failure_threshold})

        while self.machine.current_state == ModemState.CONNECTED.value:
            try:
                # Only test if we have a bearer connection (guard against brief state gaps)
                if not self.bearer_path:
                    logger.debug("No bearer connection, skipping connectivity test",
                               extra={'interface_number': self.interface_number})
                    await asyncio.sleep(interval)
                    continue

                # Get interface name for source binding
                interface_name = await self._get_bearer_interface_name()

                # Perform connectivity tests
                connectivity_results = await self._test_connectivity(
                    interface_name, ipv4_targets, ipv6_targets,
                    test_ipv4, test_ipv6, timeout, retry_count
                )

                # Evaluate results
                connectivity_ok = self._evaluate_connectivity_results(
                    connectivity_results, require_both, test_ipv4, test_ipv6
                )

                if connectivity_ok:
                    # Reset failure counter on success
                    if consecutive_failures > 0:
                        logger.info("Connectivity restored",
                                   extra={'interface_number': self.interface_number,
                                          'previous_failures': consecutive_failures,
                                          'results': connectivity_results})
                    consecutive_failures = 0

                    logger.info("Connectivity test passed",
                               extra={'interface_number': self.interface_number,
                                      'results': connectivity_results})
                else:
                    consecutive_failures += 1
                    logger.warning(f"Connectivity test failed ({consecutive_failures}/{failure_threshold})",
                                  extra={'interface_number': self.interface_number,
                                         'consecutive_failures': consecutive_failures,
                                         'results': connectivity_results})

                    # Check if we've reached failure threshold
                    if consecutive_failures >= failure_threshold:
                        logger.error("Connectivity failure threshold exceeded, triggering reconnection",
                                    extra={'interface_number': self.interface_number,
                                           'consecutive_failures': consecutive_failures,
                                           'failure_threshold': failure_threshold})

                        # Trigger disconnection and recovery via FSM
                        await self._trigger_connectivity_recovery()
                        break

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                if self._modem_removed:
                    logger.info("Connectivity monitoring cancelled - modem removed",
                               extra={'interface_number': self.interface_number})
                else:
                    logger.info("Connectivity monitoring cancelled",
                               extra={'interface_number': self.interface_number})
                break
            except Exception as e:
                logger.error(f"Connectivity monitoring error: {e}",
                            extra={'interface_number': self.interface_number})
                await asyncio.sleep(interval)  # Continue monitoring despite errors

        # Log when the loop exits because the FSM left CONNECTED (e.g. reconfig,
        # disconnect, SIM switch).  The monitoring task will be restarted
        # automatically when the FSM re-enters CONNECTED.
        if self.machine.current_state != ModemState.CONNECTED.value:
            logger.info("Connectivity monitoring stopped — FSM left CONNECTED state",
                       extra={'interface_number': self.interface_number,
                              'current_state': self.machine.current_state})

    async def _get_bearer_interface_name(self):
        """Get network interface name from bearer for source binding"""
        try:
            if not self.bearer_path:
                return None

            introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, self.bearer_path)
            proxy = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, self.bearer_path, introspect)
            props = proxy.get_interface("org.freedesktop.DBus.Properties")

            interface_name_variant = await props.call_get(BEARER_INTERFACE, "Interface")
            interface_name = interface_name_variant.value if interface_name_variant else None
            return interface_name

        except Exception as e:
            logger.debug(f"Could not get bearer interface name: {e}",
                        extra={'interface_number': self.interface_number})
            return None

    async def _test_connectivity(self, interface_name, ipv4_targets, ipv6_targets,
                               test_ipv4, test_ipv6, timeout, retry_count):
        """Test connectivity using ping to configured targets"""
        results = {
            'ipv4': {'tested': test_ipv4, 'success': False, 'details': []},
            'ipv6': {'tested': test_ipv6, 'success': False, 'details': []}
        }

        # Test IPv4 connectivity
        if test_ipv4 and ipv4_targets:
            ipv4_success = await self._test_ip_family_connectivity(
                ipv4_targets, interface_name, 'ipv4', timeout, retry_count
            )
            results['ipv4']['success'] = ipv4_success
            results['ipv4']['details'] = ipv4_targets

        # Test IPv6 connectivity
        if test_ipv6 and ipv6_targets:
            ipv6_success = await self._test_ip_family_connectivity(
                ipv6_targets, interface_name, 'ipv6', timeout, retry_count
            )
            results['ipv6']['success'] = ipv6_success
            results['ipv6']['details'] = ipv6_targets

        return results

    async def _test_ip_family_connectivity(self, targets, interface_name, ip_family, timeout, retry_count):
        """Test connectivity for specific IP family (IPv4 or IPv6)"""
        ping_cmd = 'ping' if ip_family == 'ipv4' else 'ping6'

        for target in targets:
            for attempt in range(retry_count):
                try:
                    # Build ping command with interface binding
                    cmd = [ping_cmd, '-c', '1', '-W', str(timeout)]

                    # Add interface binding if available
                    if interface_name:
                        if ip_family == 'ipv4':
                            cmd.extend(['-I', interface_name])
                        else:  # IPv6
                            cmd.extend(['-I', interface_name])

                    cmd.append(target)

                    logger.info(f"Testing {ip_family} connectivity",
                              extra={'interface_number': self.interface_number,
                                     'target': target,
                                     'attempt': attempt + 1,
                                     'interface': interface_name,
                                     'command': ' '.join(cmd)})

                    # Run ping with timeout
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )

                    try:
                        stdout, stderr = await asyncio.wait_for(
                            process.communicate(),
                            timeout=timeout + 5  # Extra buffer for process management
                        )

                        if process.returncode == 0:
                            logger.info(f"{ip_family} connectivity test successful",
                                       extra={'interface_number': self.interface_number,
                                              'target': target,
                                              'attempt': attempt + 1})
                            return True  # Success on first working target
                        else:
                            logger.warning(f"{ip_family} ping failed",
                                          extra={'interface_number': self.interface_number,
                                                 'target': target,
                                                 'attempt': attempt + 1,
                                                 'returncode': process.returncode,
                                                 'stderr': stderr.decode()[:200]})

                    except asyncio.TimeoutError:
                        logger.warning(f"{ip_family} ping timed out",
                                      extra={'interface_number': self.interface_number,
                                             'target': target,
                                             'attempt': attempt + 1,
                                             'timeout': timeout})
                        try:
                            process.kill()
                            await process.wait()
                        except Exception:
                            pass

                except Exception as e:
                    logger.debug(f"{ip_family} connectivity test error: {e}",
                               extra={'interface_number': self.interface_number,
                                      'target': target,
                                      'attempt': attempt + 1})

        # All targets and retries failed
        logger.debug(f"All {ip_family} connectivity tests failed",
                   extra={'interface_number': self.interface_number,
                          'targets': targets,
                          'retry_count': retry_count})
        return False

    def _evaluate_connectivity_results(self, results, require_both, test_ipv4, test_ipv6):
        """Evaluate connectivity test results based on configuration"""
        ipv4_ok = not test_ipv4 or results['ipv4']['success']
        ipv6_ok = not test_ipv6 or results['ipv6']['success']

        if require_both:
            # Both IPv4 and IPv6 must work
            connectivity_ok = ipv4_ok and ipv6_ok
            logger.debug("Connectivity evaluation (require both)",
                       extra={'interface_number': self.interface_number,
                              'ipv4_ok': ipv4_ok,
                              'ipv6_ok': ipv6_ok,
                              'overall_ok': connectivity_ok})
        else:
            # At least one IP family must work
            connectivity_ok = ipv4_ok or ipv6_ok
            logger.debug("Connectivity evaluation (require one)",
                       extra={'interface_number': self.interface_number,
                              'ipv4_ok': ipv4_ok,
                              'ipv6_ok': ipv6_ok,
                              'overall_ok': connectivity_ok})

        return connectivity_ok

    async def _trigger_connectivity_recovery(self):
        """Trigger recovery due to connectivity failure, with SIM escalation.

        Delegates all bearer teardown and task cleanup to the normal FSM
        paths (handle_disconnection_recovery / _execute_sim_switch) so that
        this method does not duplicate their logic.

        On first failures, attempt normal reconnection on the current SIM.
        After max_recovery_before_sim_switch consecutive failures, escalate
        to a SIM failover if enabled and allowed.
        """
        try:
            self.connectivity_recovery_attempts += 1

            logger.warning("Triggering connectivity recovery",
                          extra={'interface_number': self.interface_number,
                                 'current_state': self.machine.current_state,
                                 'recovery_attempt': self.connectivity_recovery_attempts,
                                 'max_before_sim_switch': self.max_recovery_before_sim_switch})

            # Check if we should escalate to SIM failover
            if (self.connectivity_recovery_attempts >= self.max_recovery_before_sim_switch
                    and self._is_sim_failover_enabled()
                    and self._is_failover_allowed()):

                logger.warning("Connectivity recovery exhausted on current SIM, escalating to SIM failover",
                              extra={'interface_number': self.interface_number,
                                     'recovery_attempts': self.connectivity_recovery_attempts,
                                     'current_sim': self.current_active_sim})

                # Reset recovery counter (will be set again if new SIM also fails)
                self.connectivity_recovery_attempts = 0

                # Escalate via the shared executor: probes SimSlots for a present
                # alternate, applies cooldown/lock gating, stamps the disconnect
                # reason consumed by the DISCONNECT handler, and runs the full
                # switch.  On any failure (no alternate / disabled target /
                # cooldown) fall through to normal recovery below.
                switched = await self._failover_to_alternate_sim(
                    'connectivity_failure_escalation',
                    '_trigger_connectivity_recovery',
                    switch_reason='connectivity_failure_escalation',
                    disconnect_reason_override='connectivity_failure',
                    extra_data={'recovery_attempts': self.connectivity_recovery_attempts})
                if switched:
                    return

            # Normal recovery: use the standard disconnect → recovery path.
            # handle_disconnection_recovery already cancels monitoring tasks,
            # clears the bearer, and attempts reconnection.
            # Pass escalate=False so that only a single attempt is made;
            # _trigger_connectivity_recovery handles retry counting and
            # SIM escalation itself.
            self._disconnect_reason_override = 'connectivity_failure'
            self.transition(ModemEvent.DISCONNECT)
            await self.handle_disconnection_recovery(
                escalate=False, connectivity_triggered=True)

        except Exception as e:
            logger.error(f"Connectivity recovery failed: {e}",
                        extra={'interface_number': self.interface_number})
            self.transition(ModemEvent.CONNECTION_FAILED)

    def _normalize_connectivity_config(self, config):
        """Normalize connectivity monitoring configuration with defaults"""
        if not isinstance(config, dict):
            return dict(DEFAULT_CONNECTIVITY_CONFIG, enabled=False)

        return {
            'enabled': config.get('enabled', DEFAULT_CONNECTIVITY_CONFIG['enabled']),
            'interval': max(30, config.get('interval', DEFAULT_CONNECTIVITY_CONFIG['interval'])),
            'timeout': max(5, config.get('timeout', DEFAULT_CONNECTIVITY_CONFIG['timeout'])),
            'retry_count': max(1, config.get('retry_count', DEFAULT_CONNECTIVITY_CONFIG['retry_count'])),
            'failure_threshold': max(1, config.get('failure_threshold', DEFAULT_CONNECTIVITY_CONFIG['failure_threshold'])),
            'test_ipv4': config.get('test_ipv4', DEFAULT_CONNECTIVITY_CONFIG['test_ipv4']),
            'test_ipv6': config.get('test_ipv6', DEFAULT_CONNECTIVITY_CONFIG['test_ipv6']),
            'require_both': config.get('require_both', DEFAULT_CONNECTIVITY_CONFIG['require_both']),
            'ipv4_targets': config.get('ipv4_targets', DEFAULT_CONNECTIVITY_CONFIG['ipv4_targets']),
            'ipv6_targets': config.get('ipv6_targets', DEFAULT_CONNECTIVITY_CONFIG['ipv6_targets'])
        }

    # ============================================================================
    # NETWORK INTERFACE MANAGEMENT METHODS
    # ============================================================================

    async def _ensure_interface_up(self):
        """Ensure Linux network interface is UP"""
        if not self.interface_management_enabled:
            return

        try:
            # Use predictable mapping: interface_number 0 -> wwan0, 1 -> wwan1, etc.
            interface_name = f"wwan{self.interface_number}"
            logger.info(f"Setting interface {interface_name} UP (interface number {self.interface_number})",
                       extra={'interface_number': self.interface_number})

            # Check if interface exists and get current state
            result = await asyncio.create_subprocess_exec(
                'ip', 'link', 'show', interface_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                logger.warning(f"Interface {interface_name} not found",
                              extra={'interface_number': self.interface_number,
                                     'interface': interface_name})
                return

            interface_info = stdout.decode()
            is_up = 'state UP' in interface_info or ',UP,' in interface_info

            if not is_up:
                logger.info(f"Setting interface {interface_name} UP",
                           extra={'interface_number': self.interface_number,
                                  'interface': interface_name})

                # Set interface UP
                result = await asyncio.create_subprocess_exec(
                    'ip', 'link', 'set', interface_name, 'up',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(result.communicate(),
                                                       timeout=self.interface_up_timeout)

                if result.returncode == 0:
                    logger.info(f"Interface {interface_name} set UP successfully",
                               extra={'interface_number': self.interface_number,
                                      'interface': interface_name})
                else:
                    logger.error(f"Failed to set interface {interface_name} UP: {stderr.decode()}",
                                extra={'interface_number': self.interface_number,
                                       'interface': interface_name})
            else:
                logger.debug(f"Interface {interface_name} already UP",
                            extra={'interface_number': self.interface_number,
                                   'interface': interface_name})

        except asyncio.TimeoutError:
            logger.error("Timeout setting interface UP",
                        extra={'interface_number': self.interface_number})
        except Exception as e:
            logger.error(f"Error ensuring interface UP: {e}",
                        extra={'interface_number': self.interface_number})

    async def _set_interface_up(self):
        """Set Linux network interface UP"""
        await self._ensure_interface_up()

    async def _get_interface_name(self):
        """Get the network interface name (e.g. wwan0, wwan1) for this modem"""
        try:
            if not self.proxy:
                return None

            # Use predictable mapping: interface_number 0 -> wwan0, 1 -> wwan1, etc.
            # This matches the systemd.link configuration that ensures consistent naming
            # regardless of ModemManager's dynamic modem numbering (modem0, modem1, etc.)
            expected_name = f"wwan{self.interface_number}"

            # Verify the expected interface exists
            if os.path.exists(f'/sys/class/net/{expected_name}'):
                return expected_name

            # Fallback: Find any available wwan interface if expected one doesn't exist
            result = await asyncio.create_subprocess_exec(
                'ls', '/sys/class/net/',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()

            if result.returncode == 0:
                interfaces = stdout.decode().strip().split('\n')
                wwan_interfaces = [iface for iface in interfaces if iface.startswith('wwan')]

                # For simplicity, use the interface number to match
                # wwan0 for interface 0, wwan1 for interface 1, etc.
                expected_name = f"wwan{self.interface_number}"
                if expected_name in wwan_interfaces:
                    return expected_name

                # If expected name not found, use first available wwan interface
                if wwan_interfaces:
                    logger.info(f"Using first available wwan interface: {wwan_interfaces[0]}",
                               extra={'interface_number': self.interface_number})
                    return wwan_interfaces[0]

            return None

        except Exception as e:
            logger.error(f"Error getting interface name: {e}",
                        extra={'interface_number': self.interface_number})
            return None

    async def _get_current_ip(self):
        """Get current IP addresses of the interface (both IPv4 and IPv6)"""
        try:
            interface_name = await self._get_interface_name()
            if not interface_name:
                return None

            result = await asyncio.create_subprocess_exec(
                'ip', 'addr', 'show', interface_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()

            if result.returncode == 0:
                lines = stdout.decode().split('\n')
                ipv4 = None
                ipv6 = None

                for line in lines:
                    line = line.strip()
                    if 'inet ' in line and 'scope global' in line and not ipv4:
                        # Extract IPv4 address (format: "inet 10.1.2.3/24 brd ...")
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part == 'inet' and i + 1 < len(parts):
                                ip_cidr = parts[i + 1]
                                ipv4 = ip_cidr.split('/')[0]  # Remove /24 suffix
                                break
                    elif 'inet6 ' in line and 'scope global' in line:
                        # Collect all IPv6 addresses (including SLAAC-generated ones)
                        if 'deprecated' not in line:  # Skip deprecated but include temporary
                            parts = line.split()
                            for i, part in enumerate(parts):
                                if part == 'inet6' and i + 1 < len(parts):
                                    ip_cidr = parts[i + 1]
                                    current_ipv6 = ip_cidr.split('/')[0]  # Remove /64 suffix
                                    # Use the first non-temporary address, but fallback to any address
                                    if not ipv6 or ('temporary' not in line and ipv6 and 'temporary' in str(ipv6)):
                                        ipv6 = current_ipv6
                                    break

                return {'ipv4': ipv4, 'ipv6': ipv6}
            else:
                return None

        except Exception as e:
            logger.error(f"Error getting current IP: {e}",
                        extra={'interface_number': self.interface_number})
            return None

    def _ipv6_same_subnet(self, ip1, ip2, prefix_len=64):
        """Check if two IPv6 addresses are in the same subnet (typically /64 for SLAAC)"""
        try:
            import ipaddress

            if not ip1 or not ip2:
                return False

            addr1 = ipaddress.IPv6Address(ip1)
            addr2 = ipaddress.IPv6Address(ip2)

            # Create networks with the specified prefix length
            net1 = ipaddress.IPv6Network(f"{addr1}/{prefix_len}", strict=False)
            net2 = ipaddress.IPv6Network(f"{addr2}/{prefix_len}", strict=False)

            # Check if they're in the same network
            return net1.network_address == net2.network_address

        except Exception as e:
            logger.debug(f"IPv6 subnet comparison error: {e}",
                        extra={'interface_number': self.interface_number,
                               'ip1': ip1, 'ip2': ip2})
            return False

    async def _get_bearer_expected_ips(self):
        """Get expected IP addresses from ModemManager bearer configuration"""
        try:
            if not hasattr(self, 'bearer_path') or not self.bearer_path:
                return None

            introspect = await self.bus.introspect('org.freedesktop.ModemManager1', self.bearer_path)
            bearer_proxy = self.bus.get_proxy_object('org.freedesktop.ModemManager1', self.bearer_path, introspect)
            bearer_props = bearer_proxy.get_interface('org.freedesktop.DBus.Properties')

            result = {}

            # Get IPv4 configuration
            try:
                ipv4_config_variant = await bearer_props.call_get('org.freedesktop.ModemManager1.Bearer', 'Ip4Config')
                if ipv4_config_variant.value:
                    ipv4_config = ipv4_config_variant.value
                    if 'address' in ipv4_config:
                        result['ipv4'] = ipv4_config['address'].value
                    if 'prefix' in ipv4_config:
                        result['ipv4_prefix'] = str(ipv4_config['prefix'].value)
                    if 'gateway' in ipv4_config:
                        result['ipv4_gateway'] = ipv4_config['gateway'].value
                    # Extract DNS servers (can be dns1/dns2 or dns array)
                    ipv4_dns = []
                    if 'dns' in ipv4_config:
                        ipv4_dns = [dns.value for dns in ipv4_config['dns'].value]
                    else:
                        # Check for individual dns1, dns2, etc.
                        for i in range(1, 5):  # Check dns1, dns2, dns3, dns4
                            dns_key = f'dns{i}'
                            if dns_key in ipv4_config:
                                ipv4_dns.append(ipv4_config[dns_key].value)
                    if ipv4_dns:
                        result['ipv4_dns'] = ipv4_dns
                    if 'mtu' in ipv4_config:
                        result['ipv4_mtu'] = str(ipv4_config['mtu'].value)
            except Exception as e:
                logger.debug(f"Could not get IPv4 config from bearer: {e}",
                           extra={'interface_number': self.interface_number})

            # Get IPv6 configuration
            try:
                ipv6_config_variant = await bearer_props.call_get('org.freedesktop.ModemManager1.Bearer', 'Ip6Config')
                if ipv6_config_variant.value:
                    ipv6_config = ipv6_config_variant.value
                    if 'address' in ipv6_config:
                        result['ipv6'] = ipv6_config['address'].value
                    if 'prefix' in ipv6_config:
                        result['ipv6_prefix'] = str(ipv6_config['prefix'].value)
                    if 'gateway' in ipv6_config:
                        result['ipv6_gateway'] = ipv6_config['gateway'].value
                    # Extract DNS servers (can be dns1/dns2 or dns array)
                    ipv6_dns = []
                    if 'dns' in ipv6_config:
                        ipv6_dns = [dns.value for dns in ipv6_config['dns'].value]
                    else:
                        # Check for individual dns1, dns2, etc.
                        for i in range(1, 5):  # Check dns1, dns2, dns3, dns4
                            dns_key = f'dns{i}'
                            if dns_key in ipv6_config:
                                ipv6_dns.append(ipv6_config[dns_key].value)
                    if ipv6_dns:
                        result['ipv6_dns'] = ipv6_dns
                    if 'mtu' in ipv6_config:
                        result['ipv6_mtu'] = str(ipv6_config['mtu'].value)
            except Exception as e:
                logger.debug(f"Could not get IPv6 config from bearer: {e}",
                           extra={'interface_number': self.interface_number})

            return result if result else None

        except Exception as e:
            logger.error(f"Error getting bearer expected IPs: {e}",
                        extra={'interface_number': self.interface_number})
            return None

    async def _is_bearer_connected(self):
        """Check if the current bearer is connected"""
        try:
            if not hasattr(self, 'bearer_path') or not self.bearer_path:
                return False

            introspect = await self.bus.introspect('org.freedesktop.ModemManager1', self.bearer_path)
            bearer_proxy = self.bus.get_proxy_object('org.freedesktop.ModemManager1', self.bearer_path, introspect)
            bearer_props = bearer_proxy.get_interface('org.freedesktop.DBus.Properties')

            connected_variant = await bearer_props.call_get('org.freedesktop.ModemManager1.Bearer', 'Connected')
            return connected_variant.value

        except Exception as e:
            logger.debug(f"Error checking bearer connection status: {e}",
                        extra={'interface_number': self.interface_number})
            return False

    async def _start_network_interface_monitoring(self):
        """Start network interface monitoring tasks when entering CONNECTED state"""
        if not self.interface_management_enabled:
            return

        logger.info("Starting network interface monitoring",
                   extra={'interface_number': self.interface_number,
                          'bearer_monitoring': self.monitor_bearer_state,
                          'ip_monitoring': self.monitor_ip_changes})

        # Store current IP address for change detection
        if self.monitor_ip_changes:
            self._last_known_ip = await self._get_current_ip()
            logger.info("Stored initial IP address for monitoring",
                       extra={'interface_number': self.interface_number,
                              'ip_address': self._last_known_ip})

        # Set up bearer D-Bus signal monitoring for immediate notifications
        if self.monitor_bearer_state:
            await self._setup_bearer_signal_monitoring()

        # Start IP change monitoring
        if self.monitor_ip_changes and (not self._ip_monitoring_task or self._ip_monitoring_task.done()):
            self._ip_monitoring_task = self._safe_create_task(self._monitor_ip_changes())

        # Start periodic signal-strength polling so the STAT LED tracks
        # real-time conditions.  The MM Signal interface is set up to
        # refresh every 5s by _enable_signal_monitoring(); we poll the
        # cached values at the same cadence and feed them into the
        # SignalStrengthTracker, which fires _update_signal_led() on
        # level changes.
        if not self._signal_poll_task or self._signal_poll_task.done():
            self._signal_poll_task = self._safe_create_task(
                self._monitor_signal_strength(),
                name=f"signal-poll-wwan{self.interface_number}",
            )

    async def _stop_network_interface_monitoring(self):
        """Stop network interface monitoring tasks when leaving CONNECTED state"""
        logger.info("Stopping network interface monitoring",
                   extra={'interface_number': self.interface_number})

        # Cancel bearer disconnect timer if active
        if self._bearer_disconnect_timer and not self._bearer_disconnect_timer.done():
            self._bearer_disconnect_timer.cancel()
            self._bearer_disconnect_timer = None

        # Remove bearer signal handlers
        self._cleanup_bearer_signal_monitoring()

        # Cancel IP monitoring task
        if self._ip_monitoring_task and not self._ip_monitoring_task.done():
            self._ip_monitoring_task.cancel()
            self._ip_monitoring_task = None

        # Cancel signal-strength poll task
        if self._signal_poll_task and not self._signal_poll_task.done():
            self._signal_poll_task.cancel()
            self._signal_poll_task = None

        # Remove IPv6 egress prefix filter (interface is going down)
        interface_name = f"wwan{self.interface_number}"
        await self._remove_ipv6_egress_filter(interface_name)
        # Remove IPv4 source whitelist + FSM-wide MSS clamp.
        await self._remove_ipv4_egress_filter(interface_name)
        await self._remove_fsm_mss_clamp(interface_name)

        # Stop bridging background tasks and remove the carrier prefix from
        # the downstream LAN interface
        self._bridging_stop_background_tasks()
        await self._bridging_remove_all()

        # Retract FSM-stamped IPv6 management-address (and its firewall
        # chain) so we don't keep a stale /128 in the kernel after the
        # bearer is gone.
        try:
            await self._mgmt_addr_remove()
        except Exception as mgmt_err:
            logger.debug("IPv6 management-address remove failed: %s",
                        mgmt_err,
                        extra={'interface_number': self.interface_number})

        # Clear tracked IPs so first post-reconnect apply doesn't see a
        # phantom "change" from the old session
        self._current_bearer_ipv4 = None
        self._current_bearer_ipv6 = None
        self._current_bearer_ipv6_prefix = None

    async def _setup_bearer_signal_monitoring(self):
        """Set up D-Bus signal monitoring for bearer state changes"""
        try:
            if not self.bearer_path or not self.bus:
                logger.warning("No bearer path or bus available for signal monitoring",
                              extra={'interface_number': self.interface_number})
                return

            logger.info("Setting up bearer D-Bus signal monitoring",
                       extra={'interface_number': self.interface_number,
                              'bearer_path': self.bearer_path})

            # Get bearer proxy and interface
            introspect = await self.bus.introspect("org.freedesktop.ModemManager1", self.bearer_path)
            self._bearer_proxy = self.bus.get_proxy_object("org.freedesktop.ModemManager1", self.bearer_path, introspect)
            self._bearer_interface = self._bearer_proxy.get_interface("org.freedesktop.ModemManager1.Bearer")

            # Try different signal connection methods - dbus_next might use a different API
            bearer_properties_iface = self._bearer_proxy.get_interface("org.freedesktop.DBus.Properties")

            # Use the correct dbus_next Properties interface method
            bearer_properties_iface.on_properties_changed(self._handle_bearer_properties_changed)
            logger.info("Using on_properties_changed method for D-Bus signals",
                       extra={'interface_number': self.interface_number})

            # Store reference for cleanup


            logger.info("Bearer signal monitoring active",
                       extra={'interface_number': self.interface_number})

        except Exception as e:
            logger.error(f"Failed to set up bearer signal monitoring: {e}",
                        extra={'interface_number': self.interface_number})



    def _cleanup_bearer_signal_monitoring(self):
        """Clean up bearer D-Bus signal monitoring"""
        try:
            if hasattr(self, '_bearer_interface'):
                # Note: dbus_next signal handlers are automatically cleaned up when the proxy is destroyed
                logger.debug("Bearer signal monitoring cleaned up",
                           extra={'interface_number': self.interface_number})



            # Clear references
            self._bearer_proxy = None
            self._bearer_interface = None

        except Exception as e:
            logger.debug(f"Error cleaning up bearer signal monitoring: {e}",
                        extra={'interface_number': self.interface_number})

    def _handle_bearer_properties_changed(self, interface_name, changed_properties, invalidated_properties):
        """Handle bearer PropertiesChanged D-Bus signal"""
        try:
            # Debug: Show all changed properties
            logger.debug(f"Bearer PropertiesChanged: {list(changed_properties.keys()) if changed_properties else 'None'}",
                        extra={'interface_number': self.interface_number})

            if 'Connected' in changed_properties:
                # Skip monitoring actions during controlled reset operations
                if self.reset_operation_in_progress:
                    connected = changed_properties['Connected'].value
                    logger.debug(f"Bearer connection state changed to {connected} during reset - skipping interface actions",
                               extra={'interface_number': self.interface_number,
                                      'connected': f"{connected} ({'CONNECTED' if connected else 'DISCONNECTED'})",
                                      'reason': 'reset_in_progress'})
                    return

                # Skip during initial configuration - _configure_modem_initial manages the connection
                if self.initial_configuration_in_progress:
                    connected = changed_properties['Connected'].value
                    logger.debug(f"Bearer connection state changed to {connected} during initial config - skipping",
                               extra={'interface_number': self.interface_number,
                                      'connected': f"{connected} ({'CONNECTED' if connected else 'DISCONNECTED'})",
                                      'reason': 'initial_configuration_in_progress'})
                    return
                connected = changed_properties['Connected'].value
                logger.info("Bearer connection state changed via D-Bus signal",
                           extra={'interface_number': self.interface_number,
                                  'connected': f"{connected} ({'CONNECTED' if connected else 'DISCONNECTED'})",
                                  'bearer_path': self.bearer_path})

                if not connected:
                    # Bearer disconnected - start disconnect timer
                    logger.warning("🔻 Bearer DISCONNECTED - starting debounce timer",
                                  extra={'interface_number': self.interface_number,
                                         'debounce_delay_seconds': self.bearer_disconnect_delay,
                                         'action': 'interface_will_go_down_if_no_reconnect'})
                    self._safe_create_task(self._handle_bearer_disconnect())
                else:
                    # Bearer connected/reconnected
                    if self._bearer_disconnect_timer:
                        logger.info("🔺 Bearer RECONNECTED - cancelling debounce timer",
                                   extra={'interface_number': self.interface_number,
                                          'action': 'interface_stays_up'})
                        self._cancel_disconnect_timer()

                    # Ensure interface is UP when bearer is connected
                    logger.info("🔺 Bearer CONNECTED - ensuring interface UP",
                               extra={'interface_number': self.interface_number,
                                      'action': 'setting_interface_up'})
                    self._safe_create_task(self._ensure_interface_up())

            # Check for IP configuration changes
            if 'Ip4Config' in changed_properties or 'Ip6Config' in changed_properties:
                if self.initial_configuration_in_progress:
                    logger.debug("Bearer IP config changed during initial config - skipping (will be applied by config flow)",
                               extra={'interface_number': self.interface_number,
                                      'reason': 'initial_configuration_in_progress'})
                else:
                    logger.info("🌐 Bearer IP configuration changed - updating interface",
                               extra={'interface_number': self.interface_number,
                                      'changed_configs': [k for k in ['Ip4Config', 'Ip6Config'] if k in changed_properties]})
                    self._safe_create_task(self._apply_bearer_ip_configuration())

        except Exception as e:
            logger.error(f"Error handling bearer properties changed: {e}",
                        extra={'interface_number': self.interface_number})

    async def _handle_registration_state_change(self, reg_state, reg_state_name):
        """Handle 3GPP registration state changes for enhanced interface management.

        Uses a configurable debounce (registration_recovery_delay) to avoid reacting
        to brief registration flaps that resolve themselves within seconds.
        """
        try:
            # Set flag to prevent concurrent handling and feedback loops
            self.registration_handling_in_progress = True

            # Store current registration state
            self._last_registration_state = reg_state

            # Skip monitoring actions during controlled reset operations
            if self.reset_operation_in_progress:
                logger.debug(f"Registration state changed to {reg_state} ({reg_state_name}) during reset - skipping interface actions",
                           extra={'interface_number': self.interface_number,
                                  'registration_state': f"{reg_state} ({reg_state_name})",
                                  'reason': 'reset_in_progress'})
                return

            # Skip during initial configuration - _configure_modem_initial handles its own connection
            if self.initial_configuration_in_progress:
                logger.debug(f"Registration state changed to {reg_state} ({reg_state_name}) during initial config - skipping",
                           extra={'interface_number': self.interface_number,
                                  'registration_state': f"{reg_state} ({reg_state_name})",
                                  'reason': 'initial_configuration_in_progress'})
                return

            # Skip during SIM switch - the SIM switch flow handles its own connection setup
            # Running registration recovery concurrently with SIM switch would race with
            # band reconfiguration and cause incomplete connection state
            if getattr(self, '_sim_switch_in_progress', False):
                logger.debug(f"Registration state changed to {reg_state} ({reg_state_name}) during SIM switch - skipping",
                           extra={'interface_number': self.interface_number,
                                  'registration_state': f"{reg_state} ({reg_state_name})",
                                  'reason': 'sim_switch_in_progress'})
                return

            # Define states that indicate good network connectivity
            connected_states = {1, 5}  # HOME, ROAMING
            disconnected_states = {0, 2, 3, 4}  # IDLE, SEARCHING, DENIED, UNKNOWN

            if reg_state in disconnected_states:
                # Network registration lost - start debounce timer before taking action
                # If registration recovers within registration_recovery_delay, no action is taken
                debounce_seconds = getattr(self, 'registration_recovery_delay', 20)

                # Cancel any existing debounce timer (reset the clock on repeated loss events)
                if hasattr(self, '_registration_debounce_timer') and self._registration_debounce_timer:
                    self._registration_debounce_timer.cancel()
                    self._registration_debounce_timer = None

                if debounce_seconds > 0:
                    logger.info(f"📡⏳ Network registration lost - debouncing for {debounce_seconds}s before acting",
                               extra={'interface_number': self.interface_number,
                                      'registration_state': f"{reg_state} ({reg_state_name})",
                                      'debounce_delay_seconds': debounce_seconds,
                                      'action': 'debounce_wait'})
                    self._registration_debounce_timer = self._safe_create_task(
                        self._handle_registration_loss_debounced(debounce_seconds, reg_state, reg_state_name))
                else:
                    # No debounce configured - act immediately (original behavior)
                    logger.info("📡 Network registration lost - acting immediately (debounce=0)",
                               extra={'interface_number': self.interface_number,
                                      'registration_state': f"{reg_state} ({reg_state_name})"})
                    self._safe_create_task(self._handle_registration_loss_immediate(reg_state, reg_state_name))

            elif reg_state in connected_states:
                # Network registration restored
                # Cancel any pending debounce timer - registration recovered before we acted
                debounce_cancelled = False
                if hasattr(self, '_registration_debounce_timer') and self._registration_debounce_timer:
                    self._registration_debounce_timer.cancel()
                    self._registration_debounce_timer = None
                    debounce_cancelled = True

                # Cancel any pending registration loss timers (from the 30s bearer-connected path)
                loss_timer_cancelled = False
                if hasattr(self, '_registration_loss_timer') and self._registration_loss_timer:
                    self._registration_loss_timer.cancel()
                    self._registration_loss_timer = None
                    loss_timer_cancelled = True

                if debounce_cancelled:
                    # Registration recovered within the debounce window - no action needed
                    logger.info("📡✅ Network registration restored within debounce window - no recovery action needed",
                               extra={'interface_number': self.interface_number,
                                      'registration_state': f"{reg_state} ({reg_state_name})",
                                      'action': 'debounce_cancelled_noop'})
                else:
                    # Registration recovered after debounce expired (recovery from actual outage)
                    if loss_timer_cancelled:
                        logger.info("📡🔄 Registration recovery - cancelled registration loss timer",
                                   extra={'interface_number': self.interface_number})

                    logger.info("📡✅ Network registration restored - ensuring interface UP and bearer connected",
                               extra={'interface_number': self.interface_number,
                                      'registration_state': f"{reg_state} ({reg_state_name})",
                                      'action': 'interface_up_and_bearer_check'})

                    # Ensure interface is up
                    self._safe_create_task(self._ensure_interface_up())

                    # Check bearer status and reconnect if necessary
                    self._safe_create_task(self._handle_registration_recovery())

        except Exception as e:
            logger.error(f"Error handling registration state change: {e}",
                        extra={'interface_number': self.interface_number})
        finally:
            # Always clear the flag to prevent deadlock
            self.registration_handling_in_progress = False

    async def _handle_registration_loss_debounced(self, debounce_seconds, reg_state, reg_state_name):
        """Wait for the debounce period, then handle registration loss if it persists."""
        try:
            await asyncio.sleep(debounce_seconds)

            # Re-check: has registration recovered during the debounce window?
            current_reg_state = getattr(self, '_last_registration_state', None)
            if current_reg_state in {1, 5}:  # HOME, ROAMING
                logger.info("📡✅ Registration recovered during debounce period - no action taken",
                           extra={'interface_number': self.interface_number,
                                  'recovered_registration_state': current_reg_state})
                return

            # Debounce expired and still disconnected - now take action
            logger.warning(f"📡 Registration still lost after {debounce_seconds}s debounce - taking action",
                         extra={'interface_number': self.interface_number,
                                'registration_state': f"{reg_state} ({reg_state_name})",
                                'current_registration_state': current_reg_state})

            # ── Registration flap detection ──────────────────────────────
            # Record this confirmed registration loss and check if the network
            # has been bouncing repeatedly within the configured window.
            now = time.monotonic()
            flap_count = getattr(self, 'registration_flap_count', 5)
            flap_window = getattr(self, 'registration_flap_window', 360)

            if flap_count > 0:
                self._registration_flap_timestamps.append(now)
                # Prune events older than the window
                cutoff = now - flap_window
                self._registration_flap_timestamps = [
                    t for t in self._registration_flap_timestamps if t > cutoff
                ]
                flap_events = len(self._registration_flap_timestamps)

                logger.info(f"📡📊 Registration flap count: {flap_events}/{flap_count} in last {flap_window}s",
                           extra={'interface_number': self.interface_number,
                                  'flap_events': flap_events,
                                  'flap_threshold': flap_count,
                                  'flap_window_seconds': flap_window})

                if flap_events >= flap_count and not self._registration_flap_failover_triggered:
                    # Threshold exceeded — trigger SIM failover if available
                    if hasattr(self, '_is_sim_failover_enabled') and self._is_sim_failover_enabled():
                        self._registration_flap_failover_triggered = True
                        logger.warning(
                            f"📡🔀 Registration flap threshold reached ({flap_events} losses in {flap_window}s) "
                            f"— triggering SIM failover",
                            extra={'interface_number': self.interface_number,
                                   'flap_events': flap_events,
                                   'flap_threshold': flap_count,
                                   'flap_window_seconds': flap_window,
                                   'action': 'sim_failover_flap_detection'})
                        # Clear the flap timestamps to avoid re-triggering after failover
                        self._registration_flap_timestamps.clear()
                        self._safe_create_task(self._initiate_sim_failover(
                            reason=f"registration_flap_{flap_events}_in_{flap_window}s"))
                        return  # Skip normal registration loss handling — failover takes over
                    else:
                        logger.warning(
                            f"📡⚠️ Registration flap threshold reached ({flap_events} losses in {flap_window}s) "
                            f"but SIM failover not available — continuing with normal recovery",
                            extra={'interface_number': self.interface_number,
                                   'flap_events': flap_events,
                                   'action': 'flap_detected_no_failover'})

            await self._handle_registration_loss_immediate(reg_state, reg_state_name)

        except asyncio.CancelledError:
            logger.debug("Registration loss debounce timer cancelled (registration recovered)",
                        extra={'interface_number': self.interface_number})
        except Exception as e:
            logger.error(f"Error in registration loss debounce handler: {e}",
                        extra={'interface_number': self.interface_number})
        finally:
            self._registration_debounce_timer = None

    async def _handle_registration_loss_immediate(self, reg_state, reg_state_name):
        """Handle registration loss after debounce period has expired (or debounce=0)."""
        try:
            # Check if bearer is still connected to decide severity
            try:
                if hasattr(self, 'bearer_path') and self.bearer_path:
                    introspect = await self.bus.introspect('org.freedesktop.ModemManager1', self.bearer_path)
                    bearer_proxy = self.bus.get_proxy_object('org.freedesktop.ModemManager1',
                                                           self.bearer_path, introspect)
                    bearer_props = bearer_proxy.get_interface('org.freedesktop.DBus.Properties')
                    connected_variant = await bearer_props.call_get('org.freedesktop.ModemManager1.Bearer', 'Connected')
                    bearer_connected = connected_variant.value

                    if not bearer_connected:
                        # Both registration and bearer are disconnected - definitely bring interface down
                        logger.warning("📡❌ Network registration lost AND bearer disconnected - interface going DOWN",
                                     extra={'interface_number': self.interface_number,
                                            'registration_state': f"{reg_state} ({reg_state_name})",
                                            'bearer_connected': bearer_connected,
                                            'action': 'interface_down_immediate'})
                        self._safe_create_task(self._set_interface_down())
                    else:
                        # Registration lost but bearer still connected - start conservative timer
                        registration_timeout = self._get_registration_timeout()
                        logger.warning("📡⚠️ Network registration lost but bearer still connected - starting registration recovery timer",
                                     extra={'interface_number': self.interface_number,
                                            'registration_state': f"{reg_state} ({reg_state_name})",
                                            'bearer_connected': bearer_connected,
                                            'recovery_timer_seconds': registration_timeout,
                                            'action': 'interface_down_if_no_recovery'})
                        self._safe_create_task(self._handle_registration_loss_with_bearer())
            except Exception as e:
                logger.debug(f"Could not check bearer state during registration change: {e}",
                            extra={'interface_number': self.interface_number})
                # If we can't check bearer state, be conservative and assume registration loss is serious
                logger.warning("📡❌ Network registration lost (bearer check failed) - interface going DOWN",
                             extra={'interface_number': self.interface_number,
                                    'registration_state': f"{reg_state} ({reg_state_name})",
                                    'action': 'interface_down_conservative'})
                self._safe_create_task(self._set_interface_down())
        except Exception as e:
            logger.error(f"Error in immediate registration loss handler: {e}",
                        extra={'interface_number': self.interface_number})

    async def _handle_registration_loss_with_bearer(self):
        """Handle registration loss when bearer is still connected - give time for recovery"""
        try:
            # Wait configured registration timeout for registration to recover
            registration_timeout = self._get_registration_timeout()
            await asyncio.sleep(registration_timeout)

            # Check if registration has recovered
            current_reg_state = getattr(self, '_last_registration_state', None)
            if current_reg_state in {0, 2, 3, 4}:  # Still disconnected
                logger.warning("📡⏰ Registration recovery timeout - bringing interface DOWN",
                             extra={'interface_number': self.interface_number,
                                    'final_registration_state': current_reg_state,
                             'registration_timeout_seconds': registration_timeout,
                                    'action': 'interface_down_timeout'})
                self._safe_create_task(self._set_interface_down())
            else:
                logger.info("📡✅ Registration recovered during timeout period",
                           extra={'interface_number': self.interface_number,
                                  'recovered_registration_state': current_reg_state})

        except asyncio.CancelledError:
            logger.debug("Registration recovery timer cancelled",
                        extra={'interface_number': self.interface_number})
        except Exception as e:
            logger.error(f"Error in registration loss handler: {e}",
                        extra={'interface_number': self.interface_number})

    async def _initiate_sim_failover(self, reason='registration_flap'):
        """Initiate SIM failover due to registration flap detection.

        Thin wrapper over the shared failover executor: it probes SimSlots for
        a present alternate slot, applies cooldown/lock gating, and runs the
        switch.  The registration-flap detector that calls this already gates
        on ``_is_sim_failover_enabled()``.  The distinct
        ``registration_flap_failover`` event type and the flap-specific switch
        reason are preserved for observability.
        """
        await self._failover_to_alternate_sim(
            reason, '_initiate_sim_failover',
            switch_reason=reason,
            event_type='registration_flap_failover')

    async def _set_interface_down(self):
        """Set the network interface DOWN"""
        if not self.interface_management_enabled:
            return

        try:
            # Use predictable mapping: interface_number 0 -> wwan0, 1 -> wwan1, etc.
            interface_name = f"wwan{self.interface_number}"
            logger.info(f"Setting interface {interface_name} DOWN (interface number {self.interface_number})",
                       extra={'interface_number': self.interface_number})

            # Check if interface is currently UP
            result = await asyncio.create_subprocess_exec(
                'ip', 'link', 'show', interface_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()

            if result.returncode == 0:
                interface_info = stdout.decode()
                is_up = 'state UP' in interface_info or ',UP,' in interface_info

                if is_up:
                    logger.warning(f"🔻 Setting interface {interface_name} DOWN",
                                 extra={'interface_number': self.interface_number,
                                        'reason': 'network_registration_lost'})

                    # Set interface DOWN
                    result = await asyncio.create_subprocess_exec(
                        'ip', 'link', 'set', interface_name, 'down',
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await result.communicate()

                    if result.returncode == 0:
                        logger.warning(f"🔻 Interface {interface_name} set DOWN successfully",
                                     extra={'interface_number': self.interface_number})
                    else:
                        logger.error(f"Failed to set interface {interface_name} DOWN: {stderr.decode()}",
                                   extra={'interface_number': self.interface_number})
                else:
                    logger.debug(f"Interface {interface_name} already DOWN",
                               extra={'interface_number': self.interface_number})

        except Exception as e:
            logger.error(f"Error setting interface DOWN: {e}",
                        extra={'interface_number': self.interface_number})

        # Clear LED when interface is down so stale signal strength is not shown.
        await self._clear_signal_led(reason='interface_down')

        # Remove carrier DNS from VyOS hostsd so resolv.conf is not left with stale entries
        interface_name = f"wwan{self.interface_number}"
        try:
            import vyos.hostsd_client
            hc = vyos.hostsd_client.Client()
            hc.delete_name_server_tags_system([interface_name])
            hc.delete_name_servers([interface_name])
            hc.apply()
        except Exception:
            pass  # hostsd may not be running; non-fatal

    async def _monitor_ip_changes(self):
        """Monitor for IP address changes"""
        try:
            logger.debug("IP change monitoring started",
                        extra={'interface_number': self.interface_number,
                               'initial_ip': self._last_known_ip})

            while self.machine.current_state == ModemState.CONNECTED.value:
                try:
                    current_ips = await self._get_current_ip()
                    bearer_ips = await self._get_bearer_expected_ips()

                    # Enhanced IP validation: Compare interface IPs to bearer IPs
                    ip_mismatch = False
                    mismatch_details = []

                    if bearer_ips and current_ips:
                        # Check IPv4 mismatch
                        if bearer_ips.get('ipv4') and bearer_ips['ipv4'] != current_ips.get('ipv4'):
                            ip_mismatch = True
                            mismatch_details.append(f"IPv4: bearer={bearer_ips['ipv4']} vs interface={current_ips.get('ipv4', 'None')}")

                        # Check IPv6 mismatch (compare subnets for SLAAC compatibility)
                        if bearer_ips.get('ipv6') and current_ips.get('ipv6'):
                            # Use subnet comparison instead of exact match for IPv6 (SLAAC generates multiple addresses)
                            if not self._ipv6_same_subnet(bearer_ips['ipv6'], current_ips['ipv6']):
                                ip_mismatch = True
                                mismatch_details.append(f"IPv6 subnet: bearer={bearer_ips['ipv6']} vs interface={current_ips.get('ipv6', 'None')} (different /64 subnets)")
                        elif bearer_ips.get('ipv6') and not current_ips.get('ipv6'):
                            ip_mismatch = True
                            mismatch_details.append(f"IPv6 missing: bearer={bearer_ips['ipv6']} vs interface=None")

                    if ip_mismatch:
                        # Check if bearer is still connected before handling mismatch
                        bearer_connected = await self._is_bearer_connected()
                        if bearer_connected:
                            logger.warning("🔧 IP address mismatch detected - cycling interface",
                                          extra={'interface_number': self.interface_number,
                                                 'bearer_ips': bearer_ips,
                                                 'interface_ips': current_ips,
                                                 'mismatches': mismatch_details,
                                                 'action': 'interface_cycle_for_ip_fix'})
                            await self._handle_ip_mismatch(bearer_ips, current_ips)
                        else:
                            logger.debug("🔧 IP mismatch detected but bearer disconnected - skipping fix",
                                        extra={'interface_number': self.interface_number,
                                               'bearer_connected': bearer_connected,
                                               'action': 'skip_ip_mismatch_fix'})
                    elif current_ips != self._last_known_ip:
                        # Traditional change detection (for other IP changes)
                        logger.info("📡 IP address changed (within expected range)",
                                   extra={'interface_number': self.interface_number,
                                          'old_ip': self._last_known_ip,
                                          'new_ip': current_ips})

                    self._last_known_ip = current_ips

                    # Check every 30 seconds
                    await asyncio.sleep(30)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"IP monitoring error: {e}",
                                extra={'interface_number': self.interface_number})
                    await asyncio.sleep(30)

        except asyncio.CancelledError:
            if self._modem_removed:
                logger.debug("IP monitoring cancelled - modem removed",
                            extra={'interface_number': self.interface_number})
            else:
                logger.debug("IP monitoring cancelled",
                            extra={'interface_number': self.interface_number})
        except Exception as e:
            logger.error(f"IP monitoring failed: {e}",
                        extra={'interface_number': self.interface_number})

    async def _handle_bearer_disconnect(self):
        """Handle bearer disconnect with configurable delay and automatic reconnection.

        After the debounce timer expires without the bearer reconnecting,
        recovery path depends on context:
        - Intentional on-demand idle (FSM REGISTERED_IDLE) is treated as
          normal and does not cycle Linux link state.
        - Unexpected bearer loss triggers Linux link-down and recovery.
        """
        try:
            # Start disconnect timer
            self._bearer_disconnect_timer = self._safe_create_task(
                asyncio.sleep(self.bearer_disconnect_delay)
            )

            await self._bearer_disconnect_timer

            current_state = self.machine.current_state

            # User/admin requested on-demand bearer teardown is not an error.
            # Keep Linux interface state unchanged in idle path.
            if (current_state == ModemState.REGISTERED_IDLE.value and
                    self.connection_mode in ('connect-on-demand', 'dial-on-demand')):
                logger.info("Bearer disconnect debounce expired in on-demand idle; preserving Linux link state",
                           extra={'interface_number': self.interface_number,
                                  'current_state': current_state,
                                  'connection_mode': self.connection_mode,
                                  'user_disconnected': self.user_disconnected,
                                  'delay': self.bearer_disconnect_delay})
                self._bearer_disconnect_timer = None
                return

            # Timer expired without cancellation - notify Linux of link down
            logger.warning("Bearer disconnect timer expired - setting interface DOWN",
                          extra={'interface_number': self.interface_number,
                                 'delay': self.bearer_disconnect_delay})
            await self._set_interface_down()

            # Tear down IP passthrough so no stale lease is advertised to the
            # downstream device while the bearer is gone.
            try:
                if self._passthrough.cfg.is_active():
                    await self._passthrough.teardown()
            except Exception as pt_err:
                logger.warning("IP passthrough teardown failed: %s", pt_err,
                              extra={'interface_number': self.interface_number})

            # Clear timer
            self._bearer_disconnect_timer = None

            # Trigger reconnection recovery — the bearer was deactivated
            # (e.g. "Regular deactivation" from carrier) and did not
            # reconnect within the debounce window.  Transition the FSM
            # and attempt to re-establish the connection.
            # Note: FSM may be in USAGE_MONITORING (not just CONNECTED)
            # because the state machine transitions there after connect.
            if (self.machine.current_state in (ModemState.CONNECTED.value,
                                                ModemState.USAGE_MONITORING.value)
                    and not self.user_disconnected):
                logger.warning("Bearer lost while FSM in %s — triggering reconnection recovery",
                              self.machine.current_state,
                              extra={'interface_number': self.interface_number,
                                     'current_state': self.machine.current_state})
                self.transition(ModemEvent.DISCONNECT)
                self._safe_create_task(self.handle_disconnection_recovery())

        except asyncio.CancelledError:
            if self._modem_removed:
                logger.info("Bearer disconnect timer cancelled - modem removed",
                           extra={'interface_number': self.interface_number})
            else:
                logger.info("Bearer disconnect timer cancelled - bearer recovered",
                           extra={'interface_number': self.interface_number})
        except Exception as e:
            logger.error(f"Bearer disconnect handling error: {e}",
                        extra={'interface_number': self.interface_number})

    def _cancel_disconnect_timer(self):
        """Cancel bearer disconnect timer"""
        if self._bearer_disconnect_timer and not self._bearer_disconnect_timer.done():
            self._bearer_disconnect_timer.cancel()
            self._bearer_disconnect_timer = None

    async def _handle_ip_change(self, old_ip, new_ip):
        """Handle IP address change with brief interface cycling"""
        try:
            logger.info("Handling IP address change",
                       extra={'interface_number': self.interface_number,
                              'old_ip': old_ip,
                              'new_ip': new_ip,
                              'delay': self.ip_change_delay})

            # Brief interface down/up cycle to trigger DHCP renewal
            await self._set_interface_down()
            await asyncio.sleep(self.ip_change_delay / 1000)
            await self._set_interface_up()

            logger.info("IP change interface cycling completed",
                       extra={'interface_number': self.interface_number,
                              'new_ip': new_ip})

        except Exception as e:
            logger.error(f"IP change handling error: {e}",
                        extra={'interface_number': self.interface_number})

    async def _handle_ip_mismatch(self, bearer_ips, interface_ips):
        """Handle IP address mismatch between bearer and interface.

        Re-applies bearer IP configuration (which includes source address
        enforcement) rather than doing a naive interface down/up cycle.
        """
        try:
            logger.warning("🔧 Handling IP mismatch - re-applying bearer config with source enforcement",
                          extra={'interface_number': self.interface_number,
                                 'bearer_ips': bearer_ips,
                                 'interface_ips': interface_ips,
                                 'action': 'reapply_bearer_ip_config'})

            await self._apply_bearer_ip_configuration()

            # Wait briefly for configuration to settle, then verify
            await asyncio.sleep(2)
            new_interface_ips = await self._get_current_ip()
            logger.info("🔧 IP mismatch fix completed",
                       extra={'interface_number': self.interface_number,
                              'bearer_ips': bearer_ips,
                              'new_interface_ips': new_interface_ips,
                              'fix_successful': self._ips_match(bearer_ips, new_interface_ips)})

        except Exception as e:
            logger.error(f"IP mismatch handling error: {e}",
                        extra={'interface_number': self.interface_number})

    def _ips_match(self, bearer_ips, interface_ips):
        """Check if bearer and interface IPs match"""
        if not bearer_ips or not interface_ips:
            return False

        ipv4_match = (not bearer_ips.get('ipv4') or
                      bearer_ips.get('ipv4') == interface_ips.get('ipv4'))
        ipv6_match = (not bearer_ips.get('ipv6') or
                      self._ipv6_same_subnet(bearer_ips.get('ipv6'), interface_ips.get('ipv6')))

        return ipv4_match and ipv6_match

    async def _try_gentle_reset(self) -> bool:
        """
        Attempt gentle modem reset using disable/enable cycle.

        This is equivalent to 'mmcli -m 0 --disable' followed by 'mmcli -m 0 --enable'
        and cleanly resets the modem state including all bearers.

        Returns:
            bool: True if gentle reset succeeded, False if it failed
        """
        try:
            if not self.proxy:
                logger.error("No modem proxy available for gentle reset",
                           extra={'interface_number': self.interface_number})
                return False

            # Set flag to suspend registration/bearer monitoring during controlled reset
            self.reset_operation_in_progress = True
            self.service_initiated_disable = True  # Prevent SIM failover during gentle reset

            # Set up timeout to ensure flag gets cleared even if something goes wrong
            if self.reset_timeout_task:
                self.reset_timeout_task.cancel()
            self.reset_timeout_task = self._safe_create_task(self._reset_timeout_handler())

            logger.info("Starting gentle reset using modem disable/enable cycle",
                       extra={'interface_number': self.interface_number})

            # Get modem interface
            modem_iface = self.proxy.get_interface(MODEM_INTERFACE)
            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")

            # Disable modem
            try:
                logger.info("Disabling modem (equivalent to 'mmcli -m 0 --disable')",
                           extra={'interface_number': self.interface_number})
                await modem_iface.call_enable(False)
                logger.info("Modem disable call completed successfully",
                           extra={'interface_number': self.interface_number})
            except Exception as disable_error:
                logger.error(f"Modem disable call failed: {disable_error}",
                           extra={'interface_number': self.interface_number,
                                  'error_type': type(disable_error).__name__})
                self._clear_reset_operation_flag()
                return False

            # Wait for disable to complete
            for i in range(30):  # Wait up to 30 seconds
                await asyncio.sleep(1)
                try:
                    state_variant = await props.call_get(MODEM_INTERFACE, "State")
                    current_state = state_variant.value
                    logger.debug(f"Waiting for disable: state = {current_state}",
                               extra={'interface_number': self.interface_number})
                    if current_state <= 2:  # DISABLED state
                        logger.info("Modem successfully disabled",
                                   extra={'interface_number': self.interface_number})
                        break
                except Exception as e:
                    logger.debug(f"State check failed: {e}",
                               extra={'interface_number': self.interface_number})
                    continue
            else:
                logger.error("Modem failed to disable within 30 seconds",
                           extra={'interface_number': self.interface_number})
                self._clear_reset_operation_flag()
                return False

            # Re-enable modem
            try:
                logger.info("Re-enabling modem (equivalent to 'mmcli -m 0 --enable')",
                           extra={'interface_number': self.interface_number})
                await modem_iface.call_enable(True)
                logger.info("Modem enable call completed successfully",
                           extra={'interface_number': self.interface_number})
            except Exception as enable_error:
                logger.error(f"Modem enable call failed: {enable_error}",
                           extra={'interface_number': self.interface_number,
                                  'error_type': type(enable_error).__name__})
                self._clear_reset_operation_flag()
                return False

            # Wait for enable to complete
            for i in range(30):  # Wait up to 30 seconds
                await asyncio.sleep(1)
                try:
                    state_variant = await props.call_get(MODEM_INTERFACE, "State")
                    current_state = state_variant.value
                    logger.debug(f"Waiting for enable: state = {current_state}",
                               extra={'interface_number': self.interface_number})
                    if current_state >= 3:  # ENABLED state or higher
                        logger.info("Gentle reset completed successfully - modem re-enabled",
                                   extra={'interface_number': self.interface_number})
                        self._clear_reset_operation_flag()
                        return True
                except Exception as e:
                    logger.debug(f"State check failed: {e}",
                               extra={'interface_number': self.interface_number})
                    continue

            logger.error("Modem failed to re-enable within 30 seconds",
                       extra={'interface_number': self.interface_number})
            self._clear_reset_operation_flag()
            return False

        except Exception as e:
            logger.error(f"Gentle reset failed: {e}",
                        extra={'interface_number': self.interface_number})
            self._clear_reset_operation_flag()
            return False

    def _clear_reset_operation_flag(self):
        """Clear reset operation flag and cancel timeout task"""
        self.reset_operation_in_progress = False
        self.service_initiated_disable = False  # Clear SIM failover protection flag
        if self.reset_timeout_task:
            self.reset_timeout_task.cancel()
            self.reset_timeout_task = None

    async def _reset_timeout_handler(self):
        """Timeout handler to ensure reset flag doesn't stay set indefinitely"""
        try:
            # Wait for reasonable timeout (120 seconds should be plenty for any reset)
            await asyncio.sleep(120)

            # If we get here, the reset took too long - force clear the flag
            if self.reset_operation_in_progress:
                logger.warning("Reset operation timeout - forcing resumption of network monitoring",
                             extra={'interface_number': self.interface_number,
                                    'timeout_seconds': 120})
                self.reset_operation_in_progress = False

        except asyncio.CancelledError:
            # Normal case - reset completed and task was cancelled
            pass
        except Exception as e:
            logger.error(f"Error in reset timeout handler: {e}",
                        extra={'interface_number': self.interface_number})

    # ── Source address enforcement helpers ──────────────────────────────
    #
    # IPv4: During IP swap, briefly block all egress on wwan, flush conntrack
    #        entries for the old source, apply new IP, then unblock.
    # IPv6: Maintain a persistent ip6tables FORWARD chain that only allows
    #        packets whose source falls within the current carrier prefix.
    #        This prevents LAN hosts with stale globally-routable addresses
    #        from leaking traffic after a prefix change.

    async def _run_ipcmd(self, *args):
        """Run an ip/iptables/conntrack command; log on failure but don't raise."""
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.debug(
                f"Command failed ({proc.returncode}): {' '.join(args)} — {stderr.decode().strip()}",
                extra={'interface_number': self.interface_number},
            )
        return proc.returncode, stdout.decode(), stderr.decode()

    async def _block_egress_ipv4(self, interface_name):
        """Insert iptables rules to DROP all IPv4 egress on the WWAN interface."""
        await self._run_ipcmd('iptables', '-I', 'OUTPUT', '1', '-o', interface_name, '-j', 'DROP')
        await self._run_ipcmd('iptables', '-I', 'FORWARD', '1', '-o', interface_name, '-j', 'DROP')
        logger.info("IPv4 egress blocked on %s", interface_name,
                    extra={'interface_number': self.interface_number})

    async def _unblock_egress_ipv4(self, interface_name):
        """Remove the temporary IPv4 egress DROP rules."""
        await self._run_ipcmd('iptables', '-D', 'OUTPUT', '-o', interface_name, '-j', 'DROP')
        await self._run_ipcmd('iptables', '-D', 'FORWARD', '-o', interface_name, '-j', 'DROP')
        logger.info("IPv4 egress unblocked on %s", interface_name,
                    extra={'interface_number': self.interface_number})

    async def _flush_conntrack_ipv4(self, old_ipv4):
        """Flush conntrack entries that used `old_ipv4` as source (SNAT reply)."""
        if not old_ipv4:
            return
        # -q = reply source (post-NAT), covers SNAT/masquerade
        rc, _, _ = await self._run_ipcmd('conntrack', '-D', '-q', old_ipv4)
        # also flush by original source for locally-originated traffic
        await self._run_ipcmd('conntrack', '-D', '-s', old_ipv4)
        logger.info("Flushed conntrack entries for old IPv4 %s", old_ipv4,
                    extra={'interface_number': self.interface_number})

    def _ipv6_chain_name(self, interface_name):
        """Return the ip6tables chain name for source address enforcement."""
        # e.g. "WWAN0_SRC_ENFORCE" — 28 chars max
        return f"{interface_name.upper()}_SRC_ENFORCE"

    async def _install_ipv6_egress_filter(self, interface_name, ipv6_addr, prefix_len):
        """Install or update a persistent ip6tables FORWARD chain that enforces
        carrier-contract egress hygiene on the WWAN interface.

        Carriers (and 3GPP TS 23.401 §4.7.3 / RFC 7066) require that the CPE
        never send packets that violate the bearer contract.  PGW/UPF will
        drop them, but persistent violations are logged as abuse signals and
        on IoT/M2M plans can trigger throttling or SIM suspension.  We enforce
        the floor here so the customer's `firewall` config cannot accidentally
        relax it below the contract.

        Chain structure (rules evaluated top-to-bottom):
          FORWARD → -o <iface> -j <CHAIN>
          <CHAIN>:
            -p icmpv6 --icmpv6-type 134           -j DROP   (outbound RA — illegal: router is a host)
            -p udp --sport 547                    -j DROP   (outbound DHCPv6 server — never legal)
            -p udp --sport 546                    -j DROP   (only if PD NOT configured)
            -s <carrier_prefix>::/<len>           -j RETURN (permit current bearer prefix)
            -s fe80::/10                          -j RETURN (permit link-local NDP / dhcp6c)
                                                  -j DROP   (drop everything else — stale prefix, RFC4193, multicast, …)
        """
        chain = self._ipv6_chain_name(interface_name)
        import ipaddress
        network = ipaddress.IPv6Network(f"{ipv6_addr}/{prefix_len}", strict=False)
        prefix_cidr = str(network)  # e.g. "2605:b100:116:4a63::/64"

        if self._ipv6_egress_filter_active:
            # Chain already exists — flush and repopulate with new prefix
            await self._run_ipcmd('ip6tables', '-F', chain)
        else:
            # First time: create chain + jump rule from FORWARD
            await self._run_ipcmd('ip6tables', '-N', chain)
            await self._run_ipcmd(
                'ip6tables', '-I', 'FORWARD', '1',
                '-o', interface_name, '-j', chain,
            )
            self._ipv6_egress_filter_active = True

        # 1. Drop outbound Router Advertisements (RFC 7066 — CPE is a host upstream).
        await self._run_ipcmd(
            'ip6tables', '-A', chain,
            '-p', 'icmpv6', '--icmpv6-type', 'router-advertisement', '-j', 'DROP',
        )
        # 2. Drop outbound DHCPv6 server packets (UDP/547 source).  No legitimate
        #    source ever exists upstream — PGW is the DHCPv6 server (or none at all).
        await self._run_ipcmd(
            'ip6tables', '-A', chain,
            '-p', 'udp', '--sport', '547', '-j', 'DROP',
        )
        # 3. Drop outbound DHCPv6 *client* packets unless the user configured
        #    dhcpv6-options pd.  This prevents idle dhcp6c probes from leaking
        #    upstream on bearers that don't support DHCPv6.  The drop is placed
        #    before the fe80::/10 RETURN below so it wins precedence.
        if not self._dhcpv6_pd_enabled:
            await self._run_ipcmd(
                'ip6tables', '-A', chain,
                '-p', 'udp', '--sport', '546', '-j', 'DROP',
            )
        # 4. Permit current carrier prefix.
        await self._run_ipcmd('ip6tables', '-A', chain, '-s', prefix_cidr, '-j', 'RETURN')
        # 5. Permit link-local (NDP, and dhcp6c when PD is enabled).
        await self._run_ipcmd('ip6tables', '-A', chain, '-s', 'fe80::/10', '-j', 'RETURN')
        # 6. Drop everything else.
        await self._run_ipcmd('ip6tables', '-A', chain, '-j', 'DROP')

        logger.info(
            "IPv6 egress filter updated: allow %s on %s (dhcpv6-pd=%s)",
            prefix_cidr, interface_name, self._dhcpv6_pd_enabled,
            extra={'interface_number': self.interface_number},
        )

    async def _remove_ipv6_egress_filter(self, interface_name):
        """Remove the persistent ip6tables FORWARD chain entirely."""
        if not self._ipv6_egress_filter_active:
            return
        chain = self._ipv6_chain_name(interface_name)
        # Remove jump rule from FORWARD, then flush + delete chain
        await self._run_ipcmd(
            'ip6tables', '-D', 'FORWARD', '-o', interface_name, '-j', chain,
        )
        await self._run_ipcmd('ip6tables', '-F', chain)
        await self._run_ipcmd('ip6tables', '-X', chain)
        self._ipv6_egress_filter_active = False
        logger.info("IPv6 egress filter removed from %s", interface_name,
                    extra={'interface_number': self.interface_number})

    # ── IPv4 egress source whitelist ────────────────────────────────────
    #
    # Mirrors the IPv6 chain.  Even with VyOS NAT correctly pointed at the
    # bearer, a stray PBR rule or a misconfigured `outbound-interface` can
    # leak RFC1918 sources upstream — carriers count those as abuse signals.
    # The chain accepts only the current bearer /32, drops DHCPv4 (no
    # cellular bearer ever runs DHCPv4), and drops everything else.

    def _ipv4_chain_name(self, interface_name):
        """Return the iptables chain name for v4 source enforcement."""
        return f"{interface_name.upper()}_SRC_ENFORCE_V4"

    async def _install_ipv4_egress_filter(self, interface_name, ipv4_addr):
        """Install or update a persistent iptables FORWARD chain that only
        allows packets whose IPv4 source equals the current bearer /32.

        Chain structure:
          FORWARD → -o <iface> -j <CHAIN>
          <CHAIN>:
            -p udp --sport 67  -j DROP      (outbound DHCPv4 server — never legal)
            -p udp --sport 68  -j DROP      (outbound DHCPv4 client — cellular bearer
                                             receives address via QMI/MBIM, not DHCP)
            -s <bearer>/32     -j RETURN    (permit current bearer source)
            -j DROP                          (drop RFC1918 leaks, 0.0.0.0, stale src, …)
        """
        if not ipv4_addr:
            return
        chain = self._ipv4_chain_name(interface_name)

        if self._ipv4_egress_filter_active:
            # Chain already exists — flush and repopulate with new bearer /32
            await self._run_ipcmd('iptables', '-F', chain)
        else:
            await self._run_ipcmd('iptables', '-N', chain)
            await self._run_ipcmd(
                'iptables', '-I', 'FORWARD', '1',
                '-o', interface_name, '-j', chain,
            )
            self._ipv4_egress_filter_active = True

        await self._run_ipcmd(
            'iptables', '-A', chain,
            '-p', 'udp', '--sport', '67', '-j', 'DROP',
        )
        await self._run_ipcmd(
            'iptables', '-A', chain,
            '-p', 'udp', '--sport', '68', '-j', 'DROP',
        )
        await self._run_ipcmd(
            'iptables', '-A', chain, '-s', f"{ipv4_addr}/32", '-j', 'RETURN',
        )
        await self._run_ipcmd('iptables', '-A', chain, '-j', 'DROP')

        logger.info(
            "IPv4 egress filter updated: allow %s/32 on %s", ipv4_addr, interface_name,
            extra={'interface_number': self.interface_number},
        )

    async def _remove_ipv4_egress_filter(self, interface_name):
        """Remove the persistent iptables FORWARD chain entirely."""
        if not self._ipv4_egress_filter_active:
            return
        chain = self._ipv4_chain_name(interface_name)
        await self._run_ipcmd(
            'iptables', '-D', 'FORWARD', '-o', interface_name, '-j', chain,
        )
        await self._run_ipcmd('iptables', '-F', chain)
        await self._run_ipcmd('iptables', '-X', chain)
        self._ipv4_egress_filter_active = False
        logger.info("IPv4 egress filter removed from %s", interface_name,
                    extra={'interface_number': self.interface_number})

    # ── FSM-wide TCP MSS clamp to PMTU ──────────────────────────────────
    #
    # Industry-standard fix for downstream clients that ignore DHCP option 26
    # / RA MTU and emit oversized TCP segments.  The kernel rewrites the MSS
    # option in SYN/SYN-ACK to fit the WWAN egress PMTU; --clamp-mss-to-pmtu
    # auto-tracks the wwan<N> MTU so bearer MTU changes are picked up without
    # rewriting the rule.
    #
    # This is installed for *every* WWAN mode (plain, ipv6-bridging, plus
    # the modes that don't already manage their own clamp).  When the
    # ip-passthrough manager is active, it installs its own clamp via
    # PassthroughManager._install_mss_clamp(); to avoid duplicate rules we
    # skip installing the FSM-wide clamp in that case.

    async def _install_fsm_mss_clamp(self, interface_name):
        """Install mangle/FORWARD TCPMSS --clamp-mss-to-pmtu (v4 + v6).

        No-op when the ip-passthrough manager is already clamping, since
        that path covers the same packets with an identical rule.
        """
        try:
            passthrough_active = bool(
                getattr(self, '_passthrough', None)
                and self._passthrough.cfg.is_active()
                and self._passthrough.cfg.mss_clamp_enabled
            )
        except Exception:
            passthrough_active = False
        if passthrough_active:
            logger.debug(
                "FSM MSS clamp skipped on %s (passthrough manages it)",
                interface_name,
                extra={'interface_number': self.interface_number},
            )
            return

        if not self._fsm_mss_clamp_v4_active:
            await self._run_ipcmd(
                'iptables', '-t', 'mangle', '-A', 'FORWARD',
                '-o', interface_name,
                '-p', 'tcp', '--tcp-flags', 'SYN,RST', 'SYN',
                '-j', 'TCPMSS', '--clamp-mss-to-pmtu',
            )
            self._fsm_mss_clamp_v4_active = True
        if not self._fsm_mss_clamp_v6_active:
            await self._run_ipcmd(
                'ip6tables', '-t', 'mangle', '-A', 'FORWARD',
                '-o', interface_name,
                '-p', 'tcp', '--tcp-flags', 'SYN,RST', 'SYN',
                '-j', 'TCPMSS', '--clamp-mss-to-pmtu',
            )
            self._fsm_mss_clamp_v6_active = True
        logger.info(
            "FSM MSS clamp-to-PMTU active on %s (v4+v6)", interface_name,
            extra={'interface_number': self.interface_number},
        )

    async def _remove_fsm_mss_clamp(self, interface_name):
        """Remove the FSM-wide mangle/FORWARD TCPMSS rules."""
        if self._fsm_mss_clamp_v4_active:
            await self._run_ipcmd(
                'iptables', '-t', 'mangle', '-D', 'FORWARD',
                '-o', interface_name,
                '-p', 'tcp', '--tcp-flags', 'SYN,RST', 'SYN',
                '-j', 'TCPMSS', '--clamp-mss-to-pmtu',
            )
            self._fsm_mss_clamp_v4_active = False
        if self._fsm_mss_clamp_v6_active:
            await self._run_ipcmd(
                'ip6tables', '-t', 'mangle', '-D', 'FORWARD',
                '-o', interface_name,
                '-p', 'tcp', '--tcp-flags', 'SYN,RST', 'SYN',
                '-j', 'TCPMSS', '--clamp-mss-to-pmtu',
            )
            self._fsm_mss_clamp_v6_active = False
        logger.info("FSM MSS clamp removed from %s", interface_name,
                    extra={'interface_number': self.interface_number})

    async def _kill_stale_ipv6_sockets(self, old_ipv6):
        """Kill locally-originated sockets still bound to the old IPv6 address."""
        if not old_ipv6:
            return
        await self._run_ipcmd('ss', '--kill', '-6', 'src', old_ipv6)
        logger.debug("Killed stale IPv6 sockets bound to %s", old_ipv6,
                     extra={'interface_number': self.interface_number})

    # ── IPv6 bridging (carrier prefix → single downstream LAN) ─────────
    #
    # The carrier assigns an IPv6 prefix (typically /64) via the bearer's
    # Ip6Config.  This feature copies that prefix verbatim to a single
    # downstream LAN interface so SLAAC clients on that LAN get globally-
    # routable addresses.  This is NOT DHCPv6 PD — it is a one-prefix copy
    # with no sub-delegation.  For real DHCPv6 PD, use the standard VyOS
    # 'dhcpv6-options pd' tree (handled by dhcp6c via Interface.update()).
    #
    # Two background tasks keep the address in sync with the LAN interface:
    #   1. Netlink watch  — instant RTM_NEWLINK/DELLINK notification
    #   2. Reconciliation — periodic safety-net re-check

    def _bridging_target_interface(self):
        """Return the configured downstream LAN interface name, or None."""
        if not self._bridging_config or not self._bridging_config.get('enabled'):
            return None
        iface = self._bridging_config.get('interface') or ''
        return iface or None

    def _bridging_build_desired_state(self, carrier_net, carrier_prefix_len):
        """Compute the desired bridged address for the downstream interface.

        Returns: {iface_name: {'addr': str, 'prefix_len': int}} or {}.

        The downstream interface gets the first usable host address inside
        the carrier-supplied prefix (network_address + 1) at the carrier's
        prefix length.  This makes the carrier prefix on-link on the LAN
        so SLAAC clients can form globally-routable addresses.
        """
        iface = self._bridging_target_interface()
        if not iface:
            return {}
        if carrier_prefix_len >= 128:
            logger.info("IPv6 bridging skipped: carrier /%d is address-only",
                       carrier_prefix_len,
                       extra={'interface_number': self.interface_number})
            return {}
        try:
            net_int = int(carrier_net.network_address)
            # Default host bit: network+1.  If that collides with the bearer's
            # own address (carrier sometimes hands out ::1), pick network+2 so
            # the router's bridged side never duplicates the upstream side.
            host_int = net_int | 1
            bearer_int = None
            if self._bridging_bearer_addr:
                try:
                    bearer_int = int(ipaddress.IPv6Address(
                        self._bridging_bearer_addr))
                except Exception:
                    bearer_int = None
            if bearer_int is not None and host_int == bearer_int:
                host_int = net_int | 2
            addr = str(ipaddress.IPv6Address(host_int))
        except Exception as e:
            logger.error("IPv6 bridging address compute failed: %s", e,
                        extra={'interface_number': self.interface_number})
            return {}
        return {iface: {'addr': addr, 'prefix_len': carrier_prefix_len}}

    def _bridging_interface_exists(self, iface_name):
        """Check if a network interface exists."""
        return os.path.isdir(f"/sys/class/net/{iface_name}")

    async def _bridging_apply_to_interface(self, iface_name, addr, prefix_len):
        """Add the bridged carrier prefix to a downstream LAN interface.

        Uses 'nodad' to skip Duplicate Address Detection — the router owns
        this address by construction, and DAD against its own proxied entries
        on the wwan side can otherwise mark the address dadfailed.
        """
        cidr = f"{addr}/{prefix_len}"
        rc, _, stderr = await self._run_ipcmd(
            'ip', '-6', 'addr', 'add', cidr, 'dev', iface_name, 'nodad'
        )
        if rc == 0 or 'exists' in stderr:
            logger.info("IPv6 bridging applied %s on %s", cidr, iface_name,
                       extra={'interface_number': self.interface_number})
            return True
        logger.warning("IPv6 bridging failed to apply %s on %s: %s",
                      cidr, iface_name, stderr.strip(),
                      extra={'interface_number': self.interface_number})
        return False

    async def _bridging_remove_from_interface(self, iface_name, addr, prefix_len):
        """Remove the bridged carrier prefix from a downstream LAN interface."""
        cidr = f"{addr}/{prefix_len}"
        if not self._bridging_interface_exists(iface_name):
            logger.debug("IPv6 bridging skip remove %s from %s (interface gone)",
                        cidr, iface_name,
                        extra={'interface_number': self.interface_number})
            return
        rc, _, stderr = await self._run_ipcmd(
            'ip', '-6', 'addr', 'del', cidr, 'dev', iface_name
        )
        if rc == 0 or 'Cannot assign' in stderr:
            logger.info("IPv6 bridging removed %s from %s", cidr, iface_name,
                       extra={'interface_number': self.interface_number})
        else:
            logger.debug("IPv6 bridging remove %s from %s: %s",
                        cidr, iface_name, stderr.strip(),
                        extra={'interface_number': self.interface_number})

    async def _bridging_apply_all(self, carrier_net, carrier_prefix_len,
                                  bearer_addr=None, dns_servers=None):
        """Apply the carrier prefix to the configured downstream interface.

        bearer_addr is the carrier-assigned address on the wwan side; it is
        excluded from the LAN host-bit choice so we never duplicate it.
        dns_servers is the carrier's IPv6 DNS list; advertised via RDNSS.
        If the interface does not exist yet, it is added to _bridging_pending.
        Starts netlink watch and reconciliation timer if bridging is configured.
        """
        self._bridging_bearer_addr = bearer_addr
        if not self._bridging_target_interface():
            return

        # Detect prefix change so we can deprecate the old LAN address (sends
        # preferred_lft=0 RA to SLAAC clients) before swapping prefixes.
        prev_net = self._bridging_carrier_prefix
        prev_plen = self._bridging_carrier_prefix_len
        prefix_changed = (
            prev_net is not None and
            (int(prev_net.network_address) != int(carrier_net.network_address)
             or prev_plen != carrier_prefix_len)
        )
        if prefix_changed:
            await self._bridging_deprecate_previous()

        self._bridging_carrier_prefix = carrier_net
        self._bridging_carrier_prefix_len = carrier_prefix_len

        # Kernel sysctls required for end-to-end v6 reachability through the
        # router: forward on both sides, accept the carrier's RA on wwan, and
        # enable proxy-NDP on wwan so the router can answer NSes for hosts on
        # the LAN side.  Saved values are restored in _bridging_remove_all.
        await self._bridging_apply_sysctls()

        desired = self._bridging_build_desired_state(carrier_net, carrier_prefix_len)
        self._bridging_pending = set()
        self._bridging_applied = {}

        for iface_name, info in desired.items():
            if self._bridging_interface_exists(iface_name):
                ok = await self._bridging_apply_to_interface(
                    iface_name, info['addr'], info['prefix_len']
                )
                if ok:
                    self._bridging_applied[iface_name] = {
                        'prefix': f"{info['addr']}/{info['prefix_len']}",
                        'addr': info['addr'],
                        'prefix_len': info['prefix_len'],
                    }
            else:
                self._bridging_pending.add(iface_name)
                logger.info("IPv6 bridging pending: %s not present yet",
                           iface_name,
                           extra={'interface_number': self.interface_number})

        if desired:
            self._bridging_start_background_tasks()

        # FSM-owned radvd: start (or reload) advertising the current
        # carrier prefix + carrier DNS on the LAN.  This replaces any
        # need for the operator to configure `service router-advert`
        # for the bridged interface — the prefix tracks the bearer.
        lan = self._bridging_target_interface()
        if lan and self._bridging_applied.get(lan):
            try:
                net_str = str(self._bridging_carrier_prefix.network_address)
                await self._bridging_radvd.apply(
                    lan=lan,
                    prefix=net_str,
                    plen=carrier_prefix_len,
                    dns_servers=list(dns_servers or []),
                )
            except Exception as e:
                logger.error("IPv6 bridging radvd apply failed: %s", e,
                            extra={'interface_number': self.interface_number})

        logger.info("IPv6 bridging apply complete: %d applied, %d pending",
                   len(self._bridging_applied), len(self._bridging_pending),
                   extra={'interface_number': self.interface_number})

    async def _bridging_remove_all(self):
        """Remove the bridged prefix from the downstream interface and reset state."""
        # Stop background tasks first so they don't race with cleanup.
        self._bridging_stop_background_tasks()
        # Stop the FSM-owned radvd so it doesn't keep advertising a
        # prefix we no longer hold.
        try:
            await self._bridging_radvd.stop()
        except Exception as e:
            logger.debug("IPv6 bridging radvd stop failed: %s", e,
                        extra={'interface_number': self.interface_number})
        # Flush any proxy-NDP entries we installed on the wwan side.
        await self._bridging_flush_proxy_entries()
        for iface_name, info in list(self._bridging_applied.items()):
            await self._bridging_remove_from_interface(
                iface_name, info['addr'], info['prefix_len']
            )
        self._bridging_applied.clear()
        self._bridging_pending.clear()
        self._bridging_carrier_prefix = None
        self._bridging_carrier_prefix_len = None
        # Restore kernel sysctls to their pre-bridging values.
        await self._bridging_restore_sysctls()
        logger.info("IPv6 bridging: removed bridged prefix",
                   extra={'interface_number': self.interface_number})

    # ── IPv6 management-address (FSM-stamped <prefix>::host-id on wwanN) ──
    #
    # Whenever the bearer comes up with an IPv6 prefix and the user has
    # not configured `ip-passthrough`, the FSM derives a stable host
    # address inside the carrier prefix and adds it as /128 directly on
    # wwanN.  By default the host portion is ::1 → `<prefix>::1/128`.
    # That gives services on the router (nginx, ssh, …) a destination
    # that does not move when the carrier rotates the bearer IID.
    #
    # The address is locked down by an FSM-owned ip6tables chain
    # (MGMT_<IF>_IN) jumped from INPUT for traffic arriving on wwanN to
    # that address.  All inbound is dropped except for user-configured
    # permit-tcp / permit-udp / permit-source exceptions.  Established
    # / related is always permitted so connect-out replies work.

    def _mgmt_addr_chain_name(self):
        return f"MGMT_W{self.interface_number}_IN"

    def _mgmt_addr_compute(self, carrier_net, carrier_prefix_len, bearer_addr):
        """Compute <prefix>::host-id, avoiding collision with bearer IID.

        Returns the host address string or None when no address can be
        derived (e.g. carrier prefix is /128, host-id parse failure).
        """
        if carrier_prefix_len >= 128:
            return None
        host_id_str = self._mgmt_addr_config.get('host_id') or '::1'
        try:
            host_id_int = int(ipaddress.IPv6Address(host_id_str))
        except (ValueError, TypeError) as e:
            logger.warning("IPv6 management-address: invalid host-id '%s': %s",
                          host_id_str, e,
                          extra={'interface_number': self.interface_number})
            return None
        # Upper bits of host-id must be zero so OR-merging with the
        # carrier prefix is unambiguous.
        host_mask = (1 << (128 - carrier_prefix_len)) - 1
        if host_id_int & ~host_mask:
            logger.warning(
                "IPv6 management-address: host-id '%s' has bits outside "
                "the carrier host portion (/%d) — truncating",
                host_id_str, carrier_prefix_len,
                extra={'interface_number': self.interface_number})
            host_id_int &= host_mask
        if host_id_int == 0:
            host_id_int = 1  # ::0 would alias the network address
        try:
            net_int = int(carrier_net.network_address)
        except Exception:
            return None
        addr_int = net_int | host_id_int
        # Collision avoidance vs the bearer's own carrier-assigned IID.
        try:
            bearer_int = int(ipaddress.IPv6Address(bearer_addr)) if bearer_addr else None
        except (ValueError, TypeError):
            bearer_int = None
        if bearer_int is not None and addr_int == bearer_int:
            addr_int ^= 1  # flip lsb to step off the collision
            if addr_int & ~host_mask:
                # extremely improbable — keep original and let the kernel
                # complain about duplicate-address detection instead
                addr_int = net_int | host_id_int
        try:
            return str(ipaddress.IPv6Address(addr_int))
        except Exception:
            return None

    async def _mgmt_addr_install_firewall(self, interface_name, addr):
        """Install ip6tables drop chain for <addr> with user-permitted exceptions."""
        chain = self._mgmt_addr_chain_name()
        # Recreate idempotently: flush if present, otherwise create.
        if self._mgmt_addr_chain_active:
            await self._run_ipcmd('ip6tables', '-F', chain)
        else:
            # -N may fail if already exists — flush as fallback so we end
            # up with an empty chain regardless of prior state.
            rc, _, _ = await self._run_ipcmd('ip6tables', '-N', chain)
            if rc != 0:
                await self._run_ipcmd('ip6tables', '-F', chain)
            await self._run_ipcmd(
                'ip6tables', '-I', 'INPUT', '1',
                '-i', interface_name, '-d', addr, '-j', chain,
            )
            self._mgmt_addr_chain_active = True

        # Always-permit: ICMPv6 (PMTUD, NDP, ping), established/related.
        await self._run_ipcmd(
            'ip6tables', '-A', chain, '-p', 'ipv6-icmp', '-j', 'RETURN')
        await self._run_ipcmd(
            'ip6tables', '-A', chain, '-m', 'conntrack',
            '--ctstate', 'ESTABLISHED,RELATED', '-j', 'RETURN')

        sources = list(self._mgmt_addr_config.get('permit_source') or [])
        tcp_ports = list(self._mgmt_addr_config.get('permit_tcp') or [])
        udp_ports = list(self._mgmt_addr_config.get('permit_udp') or [])

        # Auto-permit TCP 443 (VyOS HTTPS UI) when the feature is opted
        # into, unless the user explicitly suppresses it.  The auto-permit
        # is treated identically to user-supplied permits and is therefore
        # gated by `permit-source` if any source prefixes are configured.
        if not self._mgmt_addr_config.get('disable_default_https'):
            if 443 not in tcp_ports:
                tcp_ports = [443] + tcp_ports

        def _emit_port_rules(proto, ports):
            rules = []
            for port in ports:
                if sources:
                    for src in sources:
                        rules.append(
                            ['-A', chain, '-p', proto, '--dport', str(port),
                             '-s', src, '-j', 'RETURN'])
                else:
                    rules.append(
                        ['-A', chain, '-p', proto, '--dport', str(port),
                         '-j', 'RETURN'])
            return rules

        for args in _emit_port_rules('tcp', tcp_ports):
            await self._run_ipcmd('ip6tables', *args)
        for args in _emit_port_rules('udp', udp_ports):
            await self._run_ipcmd('ip6tables', *args)

        await self._run_ipcmd('ip6tables', '-A', chain, '-j', 'DROP')
        logger.info(
            "IPv6 management-address firewall installed: %s "
            "(tcp=%s udp=%s sources=%s)",
            addr, tcp_ports, udp_ports, sources,
            extra={'interface_number': self.interface_number})

    async def _mgmt_addr_remove_firewall(self, interface_name, addr):
        """Tear down ip6tables drop chain for <addr>."""
        if not self._mgmt_addr_chain_active:
            return
        chain = self._mgmt_addr_chain_name()
        # Remove the INPUT jump first (idempotent — delete by spec).
        await self._run_ipcmd(
            'ip6tables', '-D', 'INPUT',
            '-i', interface_name, '-d', addr, '-j', chain,
        )
        await self._run_ipcmd('ip6tables', '-F', chain)
        await self._run_ipcmd('ip6tables', '-X', chain)
        self._mgmt_addr_chain_active = False

    async def _mgmt_addr_apply(self, carrier_net, carrier_prefix_len,
                               bearer_addr=None):
        """Apply <prefix>::host-id/128 on wwanN and install firewall chain."""
        if not (self._mgmt_addr_config or {}).get('enabled'):
            return
        interface_name = f"wwan{self.interface_number}"
        addr = self._mgmt_addr_compute(
            carrier_net, carrier_prefix_len, bearer_addr)
        if not addr:
            return

        # If the prefix changed under us, retract the previous address +
        # firewall first so we don't leave a stale /128 floating around.
        if self._mgmt_addr_applied and self._mgmt_addr_applied != addr:
            try:
                await self._run_ipcmd(
                    'ip', '-6', 'addr', 'del',
                    f"{self._mgmt_addr_applied}/128",
                    'dev', interface_name,
                )
            except Exception:
                pass
            await self._mgmt_addr_remove_firewall(
                interface_name, self._mgmt_addr_applied)

        # Add the new address as /128 (point-to-point — same convention as
        # the bearer's own carrier IID).  nodad: DAD is meaningless on a
        # 3GPP PDN bearer.
        rc, _, stderr = await self._run_ipcmd(
            'ip', '-6', 'addr', 'add', f"{addr}/128",
            'dev', interface_name, 'nodad',
        )
        if rc != 0 and 'exists' not in stderr.lower():
            logger.error(
                "IPv6 management-address add failed for %s on %s: %s",
                addr, interface_name, stderr.strip(),
                extra={'interface_number': self.interface_number})
            return

        await self._mgmt_addr_install_firewall(interface_name, addr)
        self._mgmt_addr_applied = addr
        self._mgmt_addr_prefix_len = carrier_prefix_len
        logger.info("IPv6 management-address stamped: %s/128 on %s",
                   addr, interface_name,
                   extra={'interface_number': self.interface_number})

    async def _mgmt_addr_remove(self):
        """Retract the FSM-stamped management address and its firewall chain."""
        if not self._mgmt_addr_applied:
            # Still try to clear a leftover chain in case state is partial.
            if self._mgmt_addr_chain_active:
                interface_name = f"wwan{self.interface_number}"
                chain = self._mgmt_addr_chain_name()
                await self._run_ipcmd('ip6tables', '-F', chain)
                await self._run_ipcmd('ip6tables', '-X', chain)
                self._mgmt_addr_chain_active = False
            return
        interface_name = f"wwan{self.interface_number}"
        addr = self._mgmt_addr_applied
        await self._run_ipcmd(
            'ip', '-6', 'addr', 'del', f"{addr}/128",
            'dev', interface_name,
        )
        await self._mgmt_addr_remove_firewall(interface_name, addr)
        self._mgmt_addr_applied = None
        self._mgmt_addr_prefix_len = None
        logger.info("IPv6 management-address removed from %s",
                   interface_name,
                   extra={'interface_number': self.interface_number})

    def _bridging_start_background_tasks(self):
        """Start netlink watch, reconciliation timer, and NDP-proxy tasks."""
        if not self._bridging_netlink_task or self._bridging_netlink_task.done():
            self._bridging_netlink_task = self._safe_create_task(
                self._bridging_netlink_watch(), name='bridging-netlink-watch'
            )
        if not self._bridging_reconciliation_task or \
                self._bridging_reconciliation_task.done():
            self._bridging_reconciliation_task = self._safe_create_task(
                self._bridging_reconciliation_loop(), name='bridging-reconciliation'
            )
        if not self._bridging_ndp_task or self._bridging_ndp_task.done():
            self._bridging_ndp_task = self._safe_create_task(
                self._bridging_ndp_proxy_watch(), name='bridging-ndp-proxy'
            )

    def _bridging_stop_background_tasks(self):
        """Cancel bridging background tasks."""
        if self._bridging_netlink_task and not self._bridging_netlink_task.done():
            self._bridging_netlink_task.cancel()
            self._bridging_netlink_task = None
        if self._bridging_reconciliation_task and \
                not self._bridging_reconciliation_task.done():
            self._bridging_reconciliation_task.cancel()
            self._bridging_reconciliation_task = None
        if self._bridging_ndp_task and not self._bridging_ndp_task.done():
            self._bridging_ndp_task.cancel()
            self._bridging_ndp_task = None

    # ── sysctl save/apply/restore for bridging ─────────────────────────
    #
    # End-to-end IPv6 reachability through a bridging router needs:
    #   - all.forwarding=1            (allow forwarding at all)
    #   - <wwan>.proxy_ndp=1          (answer NS for hosts on the LAN side)
    #   - <lan>.forwarding=1          (forward replies back to wwan)
    #
    # NOTE on RA: in this FSM-native design the modem hands us the full
    # IPv6 config via the bearer's Ip6Config D-Bus property. The kernel
    # must NEVER autoconfigure from a carrier RA — that would race the
    # FSM (duplicate /64 SLAAC address, competing default route, RDNSS
    # pollution, MTU clobber). accept_ra/autoconf are forced to 0 on
    # wwan by _harden_wwan_ipv6_sysctls() at bearer-up time, in both
    # bridging and non-bridging modes.
    # We snapshot prior values so removal restores the system to its
    # exact previous state.

    def _bridging_sysctl_targets(self):
        wwan = f"wwan{self.interface_number}"
        lan = self._bridging_target_interface()
        targets = {
            f"/proc/sys/net/ipv6/conf/all/forwarding": "1",
            f"/proc/sys/net/ipv6/conf/{wwan}/proxy_ndp": "1",
        }
        if lan:
            targets[f"/proc/sys/net/ipv6/conf/{lan}/forwarding"] = "1"
        return targets

    async def _bridging_apply_sysctls(self):
        """Apply forwarding/accept_ra/proxy_ndp sysctls, saving prior values."""
        for path, desired in self._bridging_sysctl_targets().items():
            try:
                with open(path, 'r') as fh:
                    current = fh.read().strip()
                if path not in self._bridging_saved_sysctls:
                    self._bridging_saved_sysctls[path] = current
                if current != desired:
                    with open(path, 'w') as fh:
                        fh.write(desired + '\n')
                    logger.info("IPv6 bridging sysctl: %s %s → %s",
                               path, current, desired,
                               extra={'interface_number': self.interface_number})
            except FileNotFoundError:
                # Interface not present yet — reconciliation will retry.
                logger.debug("IPv6 bridging sysctl skipped (missing): %s", path,
                            extra={'interface_number': self.interface_number})
            except Exception as e:
                logger.warning("IPv6 bridging sysctl %s failed: %s", path, e,
                              extra={'interface_number': self.interface_number})

    async def _bridging_restore_sysctls(self):
        """Restore the sysctls captured by _bridging_apply_sysctls."""
        for path, original in list(self._bridging_saved_sysctls.items()):
            try:
                with open(path, 'w') as fh:
                    fh.write(original + '\n')
                logger.info("IPv6 bridging sysctl restore: %s → %s",
                           path, original,
                           extra={'interface_number': self.interface_number})
            except FileNotFoundError:
                pass
            except Exception as e:
                logger.debug("IPv6 bridging sysctl restore %s failed: %s",
                            path, e,
                            extra={'interface_number': self.interface_number})
        self._bridging_saved_sysctls.clear()

    # ── carrier-RA isolation on wwan ───────────────────────────────────
    #
    # The modem hands us full IPv6 configuration (address, prefix, gateway,
    # DNS, MTU) via the bearer's Ip6Config D-Bus property. Any RA the
    # carrier emits on the bearer must therefore be IGNORED by the kernel
    # — otherwise we get a competing /64 SLAAC address, a competing
    # default route via fe80::, RDNSS pollution and possibly MTU clobber.
    #
    # This must be applied BEFORE any address is installed on wwan, and
    # in BOTH bridging and non-bridging modes. accept_ra=2 (the previous
    # bridging-mode value) was wrong — it told the kernel to keep
    # honoring carrier RAs even while forwarding=1, which is the exact
    # behavior we do NOT want in an FSM-as-sole-authority design.

    def _wwan_ra_isolation_targets(self):
        wwan = f"wwan{self.interface_number}"
        return {
            f"/proc/sys/net/ipv6/conf/{wwan}/accept_ra":         "0",
            f"/proc/sys/net/ipv6/conf/{wwan}/autoconf":          "0",
            f"/proc/sys/net/ipv6/conf/{wwan}/accept_ra_defrtr":  "0",
            f"/proc/sys/net/ipv6/conf/{wwan}/accept_ra_pinfo":   "0",
            f"/proc/sys/net/ipv6/conf/{wwan}/accept_ra_rtr_pref": "0",
            f"/proc/sys/net/ipv6/conf/{wwan}/accept_ra_rt_info": "0",
            f"/proc/sys/net/ipv6/conf/{wwan}/accept_ra_rdnss":   "0",
            f"/proc/sys/net/ipv6/conf/{wwan}/accept_redirects":  "0",
            f"/proc/sys/net/ipv6/conf/{wwan}/use_tempaddr":      "0",
        }

    async def _harden_wwan_ipv6_sysctls(self):
        """Force the kernel to ignore carrier RAs on wwan.

        Idempotent. Logs at debug level for missing files (interface
        gone) and at warning for unexpected errors. Does NOT snapshot
        prior values — these knobs are wwan-specific and the wwan
        netdev is owned by this FSM for its whole lifetime.
        """
        for path, desired in self._wwan_ra_isolation_targets().items():
            try:
                with open(path, 'r') as fh:
                    current = fh.read().strip()
                if current != desired:
                    with open(path, 'w') as fh:
                        fh.write(desired + '\n')
                    logger.debug("wwan RA-isolation sysctl: %s %s → %s",
                                 path, current, desired,
                                 extra={'interface_number': self.interface_number})
            except FileNotFoundError:
                logger.debug("wwan RA-isolation sysctl skipped (missing): %s",
                             path,
                             extra={'interface_number': self.interface_number})
            except Exception as e:
                logger.warning("wwan RA-isolation sysctl %s failed: %s",
                               path, e,
                               extra={'interface_number': self.interface_number})

    # ── radvd reload + LAN address deprecation on prefix change ────────

    async def _bridging_signal_radvd(self):
        """No-op compatibility shim.

        Real radvd lifecycle is owned by ``self._bridging_radvd.apply()``;
        this method exists so external introspection / status reporters
        that look up the name on the FSM object do not raise.
        """
        return

    async def _bridging_deprecate_previous(self):
        """Deprecate the currently-applied LAN address before swapping prefix.

        Two steps:
          1. Ask our FSM-owned radvd to advertise preferred_lft=0 on the
             previous prefix so SLAAC clients mark their old addresses
             deprecated as soon as they hear the next RA.
          2. Set the kernel's own address to preferred_lft=0 / valid_lft=30
             so the router itself stops sourcing traffic from it.
        """
        try:
            await self._bridging_radvd.deprecate_previous()
        except Exception as e:
            logger.debug("IPv6 bridging radvd deprecate failed: %s", e,
                        extra={'interface_number': self.interface_number})

        for iface_name, info in list(self._bridging_applied.items()):
            cidr = f"{info['addr']}/{info['prefix_len']}"
            await self._run_ipcmd(
                'ip', '-6', 'addr', 'change', cidr, 'dev', iface_name,
                'preferred_lft', '0', 'valid_lft', '30'
            )
            logger.info("IPv6 bridging: deprecated %s on %s before renumber",
                       cidr, iface_name,
                       extra={'interface_number': self.interface_number})

    # ── proxy-NDP entry management on the wwan side ────────────────────
    #
    # When a LAN host has an address inside the carrier prefix, the carrier
    # router will Neighbor-Solicit that address on the bearer link.  Because
    # the host is on the LAN side, the kernel won't answer unless we install
    # a proxy entry: `ip -6 neigh add proxy <addr> dev <wwan>`.  We learn
    # those addresses by watching RTM_NEWNEIGH events on the LAN interface.

    async def _bridging_add_proxy(self, addr):
        """Install a proxy-NDP entry on the wwan side for one LAN host."""
        if addr in self._bridging_proxy_entries:
            return
        wwan = f"wwan{self.interface_number}"
        rc, _, stderr = await self._run_ipcmd(
            'ip', '-6', 'neigh', 'add', 'proxy', addr, 'dev', wwan
        )
        if rc == 0 or 'exists' in stderr.lower() or 'file exists' in stderr.lower():
            self._bridging_proxy_entries.add(addr)
            logger.info("IPv6 bridging: proxy-NDP +%s on %s", addr, wwan,
                       extra={'interface_number': self.interface_number})
        else:
            logger.debug("IPv6 bridging: proxy-NDP add %s on %s failed: %s",
                        addr, wwan, stderr.strip(),
                        extra={'interface_number': self.interface_number})

    async def _bridging_del_proxy(self, addr):
        """Remove a proxy-NDP entry on the wwan side."""
        if addr not in self._bridging_proxy_entries:
            return
        wwan = f"wwan{self.interface_number}"
        await self._run_ipcmd(
            'ip', '-6', 'neigh', 'del', 'proxy', addr, 'dev', wwan
        )
        self._bridging_proxy_entries.discard(addr)
        logger.info("IPv6 bridging: proxy-NDP -%s on %s", addr, wwan,
                   extra={'interface_number': self.interface_number})

    async def _bridging_flush_proxy_entries(self):
        """Remove all proxy-NDP entries we installed."""
        for addr in list(self._bridging_proxy_entries):
            await self._bridging_del_proxy(addr)

    def _bridging_addr_eligible_for_proxy(self, addr_str):
        """True if addr is inside the carrier prefix and not the bearer/router itself."""
        if not self._bridging_carrier_prefix:
            return False
        try:
            addr = ipaddress.IPv6Address(addr_str)
        except Exception:
            return False
        if addr.is_link_local or addr.is_multicast or addr.is_unspecified:
            return False
        if addr not in self._bridging_carrier_prefix:
            return False
        if self._bridging_bearer_addr:
            try:
                if addr == ipaddress.IPv6Address(self._bridging_bearer_addr):
                    return False
            except Exception:
                pass
        for info in self._bridging_applied.values():
            try:
                if addr == ipaddress.IPv6Address(info['addr']):
                    return False
            except Exception:
                pass
        return True

    async def _bridging_ndp_proxy_watch(self):
        """Watch RTM_NEWNEIGH/DELNEIGH on the LAN and mirror proxy entries on wwan."""
        NETLINK_ROUTE = 0
        RTMGRP_NEIGH = 0x4
        RTM_NEWNEIGH = 28
        RTM_DELNEIGH = 29
        NDA_DST = 1
        NLMSG_HDRLEN = 16
        NDMSG_LEN = 12   # family,_pad,ifindex(4),state(2),flags,type

        sock = None
        try:
            # Find LAN ifindex (the only one we care about).
            lan = self._bridging_target_interface()
            if not lan:
                return
            try:
                lan_ifindex = socket.if_nametoindex(lan)
            except OSError:
                lan_ifindex = None  # may appear later; we still watch

            sock = socket.socket(socket.AF_NETLINK, socket.SOCK_DGRAM, NETLINK_ROUTE)
            sock.bind((0, RTMGRP_NEIGH))
            sock.setblocking(False)
            loop = asyncio.get_event_loop()

            # Seed with current LAN neighbors so we don't have to wait for
            # gratuitous traffic before installing proxies.
            await self._bridging_seed_proxy_from_neigh_dump(lan)

            while True:
                future = loop.create_future()

                def _on_readable():
                    if not future.done():
                        future.set_result(None)

                loop.add_reader(sock.fileno(), _on_readable)
                try:
                    await future
                finally:
                    loop.remove_reader(sock.fileno())

                try:
                    data = sock.recv(65535)
                except BlockingIOError:
                    continue

                # Refresh lan ifindex lazily in case it appeared late.
                if lan_ifindex is None:
                    try:
                        lan_ifindex = socket.if_nametoindex(lan)
                    except OSError:
                        lan_ifindex = None

                offset = 0
                while offset < len(data):
                    if offset + NLMSG_HDRLEN > len(data):
                        break
                    nlmsg_len, nlmsg_type, _, _, _ = struct.unpack_from(
                        '=IHHII', data, offset
                    )
                    if nlmsg_len < NLMSG_HDRLEN or offset + nlmsg_len > len(data):
                        break
                    if nlmsg_type in (RTM_NEWNEIGH, RTM_DELNEIGH):
                        fam, _pad, ifindex = struct.unpack_from(
                            '=BBxxI', data, offset + NLMSG_HDRLEN
                        )
                        if fam == socket.AF_INET6 and (
                            lan_ifindex is None or ifindex == lan_ifindex
                        ):
                            attr_offset = offset + NLMSG_HDRLEN + NDMSG_LEN
                            dst = None
                            while attr_offset + 4 <= offset + nlmsg_len:
                                rta_len, rta_type = struct.unpack_from(
                                    '=HH', data, attr_offset
                                )
                                if rta_len < 4:
                                    break
                                if rta_type == NDA_DST and rta_len >= 4 + 16:
                                    raw16 = data[attr_offset + 4:attr_offset + 4 + 16]
                                    try:
                                        dst = str(ipaddress.IPv6Address(raw16))
                                    except Exception:
                                        dst = None
                                    break
                                attr_offset += (rta_len + 3) & ~3
                            if dst and self._bridging_addr_eligible_for_proxy(dst):
                                if nlmsg_type == RTM_NEWNEIGH:
                                    await self._bridging_add_proxy(dst)
                                else:
                                    await self._bridging_del_proxy(dst)
                    offset += (nlmsg_len + 3) & ~3

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("IPv6 bridging NDP-proxy watch error: %s", e,
                        extra={'interface_number': self.interface_number})
        finally:
            if sock is not None:
                sock.close()

    async def _bridging_seed_proxy_from_neigh_dump(self, lan):
        """Pre-populate proxy entries from `ip -6 neigh show dev <lan>`."""
        try:
            proc = await asyncio.create_subprocess_exec(
                'ip', '-6', 'neigh', 'show', 'dev', lan,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            for line in stdout.decode().splitlines():
                addr = line.split()[0] if line.split() else ''
                if addr and self._bridging_addr_eligible_for_proxy(addr):
                    await self._bridging_add_proxy(addr)
        except Exception as e:
            logger.debug("IPv6 bridging proxy seed failed: %s", e,
                        extra={'interface_number': self.interface_number})

    async def _bridging_reconciliation_loop(self):
        """Periodically re-check the downstream interface and reconcile state."""
        try:
            while True:
                await asyncio.sleep(self._bridging_reconciliation_interval)

                if not self._bridging_carrier_prefix or \
                        not self._bridging_target_interface():
                    continue

                desired = self._bridging_build_desired_state(
                    self._bridging_carrier_prefix,
                    self._bridging_carrier_prefix_len,
                )

                newly_applied = []
                for iface_name in list(self._bridging_pending):
                    if iface_name in desired and \
                            self._bridging_interface_exists(iface_name):
                        info = desired[iface_name]
                        ok = await self._bridging_apply_to_interface(
                            iface_name, info['addr'], info['prefix_len']
                        )
                        if ok:
                            self._bridging_applied[iface_name] = {
                                'prefix': f"{info['addr']}/{info['prefix_len']}",
                                'addr': info['addr'],
                                'prefix_len': info['prefix_len'],
                            }
                            newly_applied.append(iface_name)

                for iface_name in newly_applied:
                    self._bridging_pending.discard(iface_name)

                for iface_name in list(self._bridging_applied):
                    if not self._bridging_interface_exists(iface_name):
                        del self._bridging_applied[iface_name]
                        if iface_name in desired:
                            self._bridging_pending.add(iface_name)
                            logger.info(
                                "IPv6 bridging reconciliation: %s disappeared, "
                                "moved to pending", iface_name,
                                extra={'interface_number': self.interface_number})

                if newly_applied:
                    logger.info("IPv6 bridging reconciliation: applied to %s",
                               ', '.join(newly_applied),
                               extra={'interface_number': self.interface_number})

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("IPv6 bridging reconciliation loop error: %s", e,
                        extra={'interface_number': self.interface_number})

    async def _bridging_netlink_watch(self):
        """Watch RTM_NEWLINK/DELLINK and apply/remove the bridged prefix."""
        NETLINK_ROUTE = 0
        RTMGRP_LINK = 1
        RTM_NEWLINK = 16
        RTM_DELLINK = 17
        IFLA_IFNAME = 3
        NLMSG_HDRLEN = 16
        IFINFOMSG_LEN = 16

        sock = None
        try:
            sock = socket.socket(socket.AF_NETLINK, socket.SOCK_DGRAM, NETLINK_ROUTE)
            sock.bind((0, RTMGRP_LINK))
            sock.setblocking(False)

            loop = asyncio.get_event_loop()

            while True:
                future = loop.create_future()

                def _on_readable():
                    if not future.done():
                        future.set_result(None)

                loop.add_reader(sock.fileno(), _on_readable)
                try:
                    await future
                finally:
                    loop.remove_reader(sock.fileno())

                try:
                    data = sock.recv(65535)
                except BlockingIOError:
                    continue

                offset = 0
                while offset < len(data):
                    if offset + NLMSG_HDRLEN > len(data):
                        break
                    nlmsg_len, nlmsg_type, _, _, _ = struct.unpack_from(
                        '=IHHII', data, offset
                    )
                    if nlmsg_len < NLMSG_HDRLEN or offset + nlmsg_len > len(data):
                        break

                    if nlmsg_type in (RTM_NEWLINK, RTM_DELLINK):
                        attr_offset = offset + NLMSG_HDRLEN + IFINFOMSG_LEN
                        iface_name = None

                        while attr_offset + 4 <= offset + nlmsg_len:
                            rta_len, rta_type = struct.unpack_from('=HH', data, attr_offset)
                            if rta_len < 4:
                                break
                            if rta_type == IFLA_IFNAME:
                                name_start = attr_offset + 4
                                name_end = attr_offset + rta_len
                                raw = data[name_start:name_end]
                                iface_name = raw.rstrip(b'\x00').decode(
                                    'ascii', errors='replace')
                                break
                            attr_offset += (rta_len + 3) & ~3

                        if iface_name:
                            await self._bridging_handle_netlink_event(
                                nlmsg_type, iface_name
                            )

                    offset += (nlmsg_len + 3) & ~3

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("IPv6 bridging netlink watch error: %s", e,
                        extra={'interface_number': self.interface_number})
        finally:
            if sock is not None:
                sock.close()

    async def _bridging_handle_netlink_event(self, msg_type, iface_name):
        """Handle a single RTM_NEWLINK or RTM_DELLINK event for bridging."""
        RTM_NEWLINK = 16
        RTM_DELLINK = 17

        if msg_type == RTM_NEWLINK and iface_name in self._bridging_pending:
            if not self._bridging_carrier_prefix or \
                    not self._bridging_target_interface():
                return
            desired = self._bridging_build_desired_state(
                self._bridging_carrier_prefix,
                self._bridging_carrier_prefix_len,
            )
            if iface_name in desired:
                info = desired[iface_name]
                ok = await self._bridging_apply_to_interface(
                    iface_name, info['addr'], info['prefix_len']
                )
                if ok:
                    self._bridging_applied[iface_name] = {
                        'prefix': f"{info['addr']}/{info['prefix_len']}",
                        'addr': info['addr'],
                        'prefix_len': info['prefix_len'],
                    }
                    self._bridging_pending.discard(iface_name)
                    logger.info(
                        "IPv6 bridging netlink: applied to newly-appeared %s",
                        iface_name,
                        extra={'interface_number': self.interface_number})

        elif msg_type == RTM_DELLINK and iface_name in self._bridging_applied:
            del self._bridging_applied[iface_name]
            if not self._bridging_carrier_prefix or \
                    not self._bridging_target_interface():
                return
            desired = self._bridging_build_desired_state(
                self._bridging_carrier_prefix,
                self._bridging_carrier_prefix_len,
            )
            if iface_name in desired:
                self._bridging_pending.add(iface_name)
                logger.info(
                    "IPv6 bridging netlink: %s destroyed, moved to pending",
                    iface_name,
                    extra={'interface_number': self.interface_number})

    async def _install_default_route(self, family, gateway, interface_name):
        """Install the bearer default route for a point-to-point cellular link.

        Both families apply the bearer address as a host route (/32 for IPv4,
        /128 for IPv6), so there is never a connected subnet that makes the
        carrier gateway on-link.  A plain ``via <gw>`` route therefore fails
        with "No route to host"; ``onlink`` is the correct-by-construction
        form for this PtP addressing, so we use it directly.  When the carrier
        supplies no gateway we fall back to a device-scope default route
        (valid because the link is point-to-point).

        ``ip route replace`` is used for idempotency: it succeeds whether or
        not a default route already exists, so reconfiguration on every IP
        change is clean and produces no spurious warnings.

        Args:
            family: 4 or 6 (IP version).
            gateway: carrier gateway address, or a falsy value if none.
            interface_name: e.g. ``wwan0``.
        """
        base = ['ip', '-6'] if family == 6 else ['ip']
        label = f"IPv{family}"

        if gateway:
            # onlink: nexthop is directly reachable on this PtP device even
            # though the host-route addressing leaves no on-link subnet.
            cmd = base + ['route', 'replace', 'default', 'via', gateway,
                          'dev', interface_name, 'onlink']
            success_msg = (f"{label} default route via {gateway} "
                           f"dev {interface_name} (onlink)")
        else:
            cmd = base + ['route', 'replace', 'default', 'dev', interface_name]
            success_msg = f"{label} default route via device {interface_name}"

        result = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await result.communicate()

        if result.returncode == 0:
            logger.info(success_msg,
                       extra={'interface_number': self.interface_number})
            return True

        # gateway present but unreachable: last-resort device-scope route.
        if gateway:
            logger.warning(
                f"{label} default route via {gateway} failed "
                f"({stderr.decode().strip()}); falling back to device route",
                extra={'interface_number': self.interface_number})
            fallback = base + ['route', 'replace', 'default',
                               'dev', interface_name]
            result = await asyncio.create_subprocess_exec(
                *fallback,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await result.communicate()
            if result.returncode == 0:
                logger.info(f"{label} default route via device {interface_name} "
                            f"(device-only fallback)",
                           extra={'interface_number': self.interface_number})
                return True

        logger.error(f"All {label} route attempts failed: {stderr.decode().strip()}",
                    extra={'interface_number': self.interface_number})
        return False

    async def _apply_bearer_ip_configuration(self):
        """Apply bearer IP configuration to the interface (VyOS responsibility).

        Returns True when the bearer produced a usable data path, and False
        only when ModemManager handed us address(es) but no default route
        could be installed for any address family (a registered-but-unroutable
        session, e.g. a band/PLMN-mismatched SIM: pdn-ipv6-call-disallowed with
        an unreachable IPv4 gateway).  Indeterminate cases (no bearer path, no
        IP config yet, unexpected exception) return True so timing races never
        trigger a false failover; callers that care escalate only on an
        explicit False via _apply_bearer_ip_or_fail().
        """
        try:
            if not hasattr(self, 'bearer_path') or not self.bearer_path:
                logger.warning("No bearer path available for IP configuration",
                             extra={'interface_number': self.interface_number})
                return True

            # Get bearer IP configuration from ModemManager
            bearer_ips = await self._get_bearer_expected_ips()
            if not bearer_ips:
                logger.warning("No IP configuration available from bearer",
                             extra={'interface_number': self.interface_number})
                return True

            interface_name = f"wwan{self.interface_number}"

            # Track whether the bearer gave us any address and whether each
            # address family ended up with a working default route.  Both
            # families are first-class here: this product runs dual-stack
            # (IPv4 + IPv6), so a usable path means *at least one* family
            # routes.  Used by the return value so callers can distinguish a
            # usable session from a registered-but-unroutable one.
            had_ipv4 = bool(bearer_ips.get('ipv4'))
            had_ipv6 = bool(bearer_ips.get('ipv6'))
            had_ip = had_ipv4 or had_ipv6
            ipv4_routed = False
            ipv6_routed = False


            # Ensure interface is UP before applying IP configuration
            # Routes cannot be installed on a DOWN interface (causes "Nexthop has invalid gateway")
            result = await asyncio.create_subprocess_exec(
                'ip', 'link', 'set', 'dev', interface_name, 'up',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            if result.returncode != 0:
                logger.warning(f"Failed to bring {interface_name} UP before IP config: {stderr.decode().strip()}",
                             extra={'interface_number': self.interface_number})
            else:
                logger.info(f"Interface {interface_name} set UP for IP configuration",
                           extra={'interface_number': self.interface_number})

            # Force-disable kernel RA/SLAAC autoconfiguration on wwan
            # before any address is installed. The modem already gave us
            # full IPv6 config via Ip6Config — a carrier RA on the bearer
            # must NOT race the FSM's address/route/DNS plumbing.
            await self._harden_wwan_ipv6_sysctls()

            # ── Source address enforcement: capture old IPs before clearing ──
            old_ipv4 = self._current_bearer_ipv4
            old_ipv6 = self._current_bearer_ipv6
            new_ipv4 = bearer_ips.get('ipv4')
            new_ipv6 = bearer_ips.get('ipv6')
            ipv4_changed = old_ipv4 and new_ipv4 and old_ipv4 != new_ipv4
            ipv6_changed = old_ipv6 and new_ipv6 and old_ipv6 != new_ipv6

            # Block IPv4 egress while we swap addresses + flush conntrack
            if ipv4_changed:
                logger.info("IPv4 address changing %s → %s — blocking egress during swap",
                           old_ipv4, new_ipv4,
                           extra={'interface_number': self.interface_number})
                await self._block_egress_ipv4(interface_name)

            # Clear existing IP addresses to avoid conflicts (except link-local)
            await self._clear_interface_addresses(interface_name)

            # Flush conntrack entries for the old IPv4 source so NAT doesn't
            # re-use the stale mapping for in-flight or retransmitted packets
            if ipv4_changed:
                await self._flush_conntrack_ipv4(old_ipv4)

            # Apply IPv4 configuration
            if bearer_ips.get('ipv4'):
                ipv4_addr = bearer_ips['ipv4']
                ipv4_prefix = bearer_ips.get('ipv4_prefix', '30')  # Carrier prefix (used for passthrough / logging)
                ipv4_gateway = bearer_ips.get('ipv4_gateway')
                ipv4_dns = bearer_ips.get('ipv4_dns', [])
                ipv4_mtu = bearer_ips.get('ipv4_mtu')

                logger.info(f"Applying IPv4 configuration: {ipv4_addr}/32 (carrier prefix /{ipv4_prefix})",
                           extra={'interface_number': self.interface_number,
                                  'gateway': ipv4_gateway,
                                  'dns_servers': ipv4_dns,
                                  'mtu': ipv4_mtu})

                # Add IPv4 address with /32 — point-to-point link to carrier.
                # The carrier-reported prefix is often synthetic; a host route
                # avoids installing a bogus connected subnet and mirrors the
                # IPv6 /128 model.  The default route is installed as 'onlink'
                # (see _install_default_route) so the gateway is still usable.
                result = await asyncio.create_subprocess_exec(
                    'ip', 'addr', 'add', f"{ipv4_addr}/32", 'dev', interface_name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await result.communicate()

                if result.returncode != 0 and b'exists' not in stderr:
                    logger.warning(f"Failed to add IPv4 address: {stderr.decode()}",
                                 extra={'interface_number': self.interface_number})

                # Set MTU — priority: per-SIM mtu > min(bearer, interface) > interface mtu
                interface_mtu = self.config.get('mtu', 1420) if self.config else 1420

                # Check per-SIM MTU override for the active SIM
                sim_mtu = 0
                if self.config:
                    sim_slots = self.config.get('sim_slots', [])
                    active_slot = self.current_active_sim or self.config.get('primary_sim_slot', 1)
                    sim_config = next((s for s in sim_slots if s['slot'] == active_slot), {})
                    sim_mtu = sim_config.get('mtu', 0)

                if sim_mtu and sim_mtu > 0:
                    effective_mtu = str(sim_mtu)
                    mtu_source = 'per-sim'
                elif ipv4_mtu:
                    effective_mtu = str(min(int(ipv4_mtu), interface_mtu))
                    mtu_source = 'network' if int(ipv4_mtu) <= interface_mtu else 'network-capped'
                else:
                    effective_mtu = str(interface_mtu)
                    mtu_source = 'interface'

                if effective_mtu:
                    result = await asyncio.create_subprocess_exec(
                        'ip', 'link', 'set', 'dev', interface_name, 'mtu', effective_mtu,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await result.communicate()

                    if result.returncode != 0:
                        logger.warning(f"Failed to set MTU {effective_mtu} ({mtu_source}): {stderr.decode()}",
                                     extra={'interface_number': self.interface_number})
                    else:
                        logger.info(f"Set interface MTU to {effective_mtu} (source: {mtu_source})",
                                   extra={'interface_number': self.interface_number,
                                          'mtu': effective_mtu,
                                          'mtu_source': mtu_source,
                                          'network_mtu': ipv4_mtu or 'not provided'})

                # Add IPv4 default route (onlink via gateway, or device route).
                if not ipv4_gateway:
                    logger.info("No IPv4 gateway from carrier, adding device route",
                               extra={'interface_number': self.interface_number})
                ipv4_routed = await self._install_default_route(
                    4, ipv4_gateway, interface_name)

            # ── IPv4 source enforcement: unblock egress now that new IP + route are live ──
            if ipv4_changed:
                await self._unblock_egress_ipv4(interface_name)
            # Persistent IPv4 source whitelist (installed once the bearer /32
            # is live; refreshed on every IP change).  Drops DHCPv4 + any
            # non-bearer source.
            if new_ipv4:
                await self._install_ipv4_egress_filter(interface_name, new_ipv4)
            # Track current IPv4 for next change detection
            if new_ipv4:
                self._current_bearer_ipv4 = new_ipv4

            # Apply IPv6 configuration
            if bearer_ips.get('ipv6'):
                ipv6_addr = bearer_ips['ipv6']
                ipv6_prefix = bearer_ips.get('ipv6_prefix', '64')  # Carrier prefix length (used for bridging / egress filter)
                ipv6_gateway = bearer_ips.get('ipv6_gateway')
                ipv6_dns = bearer_ips.get('ipv6_dns', [])
                ipv6_mtu = bearer_ips.get('ipv6_mtu')

                logger.info(f"Applying IPv6 configuration: {ipv6_addr}/128 (carrier prefix /{ipv6_prefix})",
                           extra={'interface_number': self.interface_number,
                                  'gateway': ipv6_gateway,
                                  'dns_servers': ipv6_dns,
                                  'mtu': ipv6_mtu})

                # Add IPv6 address with /128 — point-to-point link to carrier;
                # the full carrier prefix may be bridged to a downstream LAN
                # interface via 'ipv6-bridging' (see _bridging_apply_all).
                result = await asyncio.create_subprocess_exec(
                    'ip', '-6', 'addr', 'add', f"{ipv6_addr}/128", 'dev', interface_name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await result.communicate()

                if result.returncode != 0 and b'exists' not in stderr:
                    logger.warning(f"Failed to add IPv6 address: {stderr.decode()}",
                                 extra={'interface_number': self.interface_number})

                # Add IPv6 default route (onlink via gateway, or device route).
                if not ipv6_gateway:
                    logger.info("No IPv6 gateway from carrier, adding device route",
                               extra={'interface_number': self.interface_number})
                ipv6_routed = await self._install_default_route(
                    6, ipv6_gateway, interface_name)

            # ── IPv6 source enforcement: persistent egress prefix whitelist ──
            if new_ipv6:
                ipv6_prefix_len = bearer_ips.get('ipv6_prefix', '64')
                await self._install_ipv6_egress_filter(interface_name, new_ipv6, ipv6_prefix_len)
                # Kill locally-originated sockets still bound to old address
                if ipv6_changed:
                    await self._kill_stale_ipv6_sockets(old_ipv6)
                # Track current IPv6 for next change detection
                self._current_bearer_ipv6 = new_ipv6
                self._current_bearer_ipv6_prefix = ipv6_prefix_len

            # ── FSM-wide TCP MSS clamp ─────────────────────────────────────
            # Apply once the bearer is live so PMTU is correctly tracked.
            # Idempotent; skipped when ip-passthrough is already clamping.
            if new_ipv4 or new_ipv6:
                await self._install_fsm_mss_clamp(interface_name)

            # ── IPv6 bridging: copy carrier-supplied prefix to one downstream LAN ──
            if bearer_ips.get('ipv6') and self._bridging_config.get('enabled') \
                    and self._bridging_config.get('interface'):
                ipv6_addr = bearer_ips['ipv6']
                carrier_plen = int(bearer_ips.get('ipv6_prefix', '64'))
                try:
                    carrier_net = ipaddress.IPv6Network(
                        f"{ipv6_addr}/{carrier_plen}", strict=False
                    )
                    await self._bridging_apply_all(
                        carrier_net, carrier_plen,
                        bearer_addr=ipv6_addr,
                        dns_servers=ipv6_dns,
                    )
                except Exception as brg_err:
                    logger.error("IPv6 bridging apply failed: %s", brg_err,
                                extra={'interface_number': self.interface_number})

            # ── IPv6 management-address: stamp <prefix>::host-id/128 on wwanN ──
            # Default-on whenever bearer has IPv6 and ip-passthrough is not
            # configured (verify() forbids coexistence).  Gives services on
            # the router itself a stable, carrier-renumber-tolerant address.
            pt_active = ((self.config or {}).get('ip_passthrough') or {}).get('enabled')
            if bearer_ips.get('ipv6') and not pt_active \
                    and (self._mgmt_addr_config or {}).get('enabled'):
                ipv6_addr = bearer_ips['ipv6']
                carrier_plen = int(bearer_ips.get('ipv6_prefix', '64'))
                try:
                    carrier_net = ipaddress.IPv6Network(
                        f"{ipv6_addr}/{carrier_plen}", strict=False
                    )
                    await self._mgmt_addr_apply(
                        carrier_net, carrier_plen, bearer_addr=ipv6_addr,
                    )
                except Exception as mgmt_err:
                    logger.error(
                        "IPv6 management-address apply failed: %s", mgmt_err,
                        extra={'interface_number': self.interface_number})

            # Register all carrier DNS servers with VyOS hostsd (same mechanism as DHCP interfaces)
            all_dns = bearer_ips.get('ipv4_dns', []) + bearer_ips.get('ipv6_dns', [])
            if all_dns:
                try:
                    import vyos.hostsd_client
                    hc = vyos.hostsd_client.Client()
                    hc.delete_name_servers([interface_name])
                    hc.add_name_servers({interface_name: all_dns})
                    hc.add_name_server_tags_system([interface_name])
                    hc.apply()
                    logger.info(f"Registered carrier DNS servers with VyOS: {', '.join(all_dns)}",
                               extra={'interface_number': self.interface_number,
                                      'interface': interface_name})
                except Exception as dns_err:
                    logger.warning(f"Could not register DNS with VyOS hostsd (carrier DNS unavailable): {dns_err}",
                                  extra={'interface_number': self.interface_number})

            logger.info("Bearer IP configuration applied successfully",
                       extra={'interface_number': self.interface_number,
                              'ipv4': bearer_ips.get('ipv4'),
                              'ipv6': bearer_ips.get('ipv6')})

            # ── IP Passthrough: hand carrier IP to a downstream device ──
            try:
                pt_cfg = (self.config or {}).get('ip_passthrough')
                self._passthrough.update_config(pt_cfg)
                if self._passthrough.cfg.is_active():
                    v6_plen = int(bearer_ips.get('ipv6_prefix', '128') or 128)
                    # Bearer MTU: prefer v4 then v6 then the configured iface
                    # MTU as fallback so the value handed downstream matches
                    # what the carrier actually negotiated.
                    try:
                        bearer_mtu = int(
                            bearer_ips.get('ipv4_mtu')
                            or bearer_ips.get('ipv6_mtu')
                            or self.config.get('mtu', 0)
                            or 0
                        )
                    except (TypeError, ValueError):
                        bearer_mtu = 0
                    try:
                        v4_plen = int(bearer_ips.get('ipv4_prefix', 30) or 30)
                    except (TypeError, ValueError):
                        v4_plen = 30
                    await self._passthrough.apply(
                        carrier_v4=bearer_ips.get('ipv4'),
                        carrier_v6=bearer_ips.get('ipv6'),
                        carrier_v6_prefix=v6_plen,
                        carrier_v4_prefix=v4_plen,
                        ipv4_dns=bearer_ips.get('ipv4_dns', []),
                        ipv6_dns=bearer_ips.get('ipv6_dns', []),
                        bearer_mtu=bearer_mtu or None,
                    )
            except Exception as pt_err:
                logger.error("IP passthrough apply failed: %s", pt_err,
                            extra={'interface_number': self.interface_number})

            # Re-apply VyOS infrastructure settings (VRF, sysctl, mirror/redirect,
            # description, etc.) in case the kernel interface was destroyed and
            # recreated during USB re-enumeration or modem reset.
            await self._reapply_vyos_infrastructure(interface_name)

            # Usable data path = the bearer gave us address(es) and at least
            # one address family installed a working default route.  Both IPv4
            # and IPv6 are considered equally: a dual-stack bearer is usable if
            # *either* family routes, and only a bearer that had address(es) but
            # routes on NEITHER family is treated as a dead path.  Anything else
            # (a healthy single family, or a transient/racy state) is reported
            # usable so legitimate connections never trigger a spurious
            # failover.
            route_installed = ipv4_routed or ipv6_routed
            if had_ip and not route_installed:
                logger.error(
                    "Bearer has address(es) but no usable default route for "
                    "either IPv4 or IPv6 — data path is dead",
                    extra={'interface_number': self.interface_number,
                           'had_ipv4': had_ipv4, 'had_ipv6': had_ipv6,
                           'ipv4_routed': ipv4_routed,
                           'ipv6_routed': ipv6_routed})
                return False
            return True

        except Exception as e:
            logger.error(f"Failed to apply bearer IP configuration: {e}",
                        extra={'interface_number': self.interface_number})
            return True

    async def _apply_bearer_ip_or_fail(self, source: str) -> bool:
        """Apply bearer IP config and verify a usable data path exists.

        Returns True when the bearer produced a usable data path.  Returns
        False only for a *persistent* registered-but-unroutable session — the
        bearer reported connected and handed us address(es) but no default
        route could be installed for any address family even after the
        interface came up and we retried (e.g. a band/PLMN-mismatched SIM:
        pdn-ipv6-call-disallowed with an unreachable IPv4 gateway).  In that
        case it stamps a failure reason, tears the session down, drives
        CONNECTION_FAILED, and offers SIM failover (a no-op without an
        eligible alternate).

        TIMING SAFETY — the single most common cause of a first-pass route
        failure is NOT a dead SIM but a local race: the bearer just came up
        and ``wwanN`` is admin-up but not yet operationally up (no carrier),
        so ``ip route`` fails with "Nexthop device is not up" even though MM
        gave us a valid address + gateway.  In normal operation a later
        Ip4Config/Ip6Config PropertiesChanged signal re-installs the route a
        beat later, which is why this path "never fails" in the field.  We
        therefore wait for the interface to become operational and retry the
        apply several times before ever concluding the path is dead, so a slow
        bearer / slow link-up can never trigger a spurious failover.

        Honours a standing user disconnect: if the operator asked us down
        mid-connect, we do not override that by re-driving failover.
        """
        usable = await self._apply_bearer_ip_configuration()
        if usable:
            return True

        # First pass reported no usable route.  Before treating this as a dead
        # SIM, give the interface time to come operationally up and retry — the
        # overwhelmingly common case is a link-up race, not an unroutable SIM.
        interface_name = f"wwan{self.interface_number}"
        max_retries = 6          # ~ up to 6 * 5s = 30s of patience
        retry_delay = 5
        for attempt in range(1, max_retries + 1):
            if self.user_disconnected:
                logger.info("Stopping data-path retry — user requested disconnect",
                           extra={'interface_number': self.interface_number,
                                  'source': source})
                return False
            # Bail out early if the bearer dropped underneath us — that is a
            # different failure handled by the disconnect path, not here.
            if not await self._is_bearer_connected():
                logger.info("Bearer dropped while waiting for a usable route — "
                           "leaving recovery to the disconnect path",
                           extra={'interface_number': self.interface_number,
                                  'source': source,
                                  'attempt': attempt})
                return False
            await self._ensure_interface_up()
            await asyncio.sleep(retry_delay)
            usable = await self._apply_bearer_ip_configuration()
            if usable:
                logger.info("Usable default route installed on retry — data path OK",
                           extra={'interface_number': self.interface_number,
                                  'source': source,
                                  'attempt': attempt})
                return True
            logger.warning("Still no usable default route after retry",
                          extra={'interface_number': self.interface_number,
                                 'source': source,
                                 'attempt': attempt,
                                 'max_retries': max_retries})

        if self.user_disconnected:
            logger.info("Dead data path detected but user requested disconnect "
                       "— not escalating to failover",
                       extra={'interface_number': self.interface_number,
                              'source': source})
            return False

        logger.error(
            "Bearer reported connected but has no usable data path after "
            "%ds of retries — treating as a failed connection and offering "
            "SIM failover", max_retries * retry_delay,
            extra={'interface_number': self.interface_number, 'source': source})
        self.last_failure_reason = (
            "ModemManager reported the bearer connected, but no usable default "
            "route could be installed for any address family. The SIM may not "
            "be permitted to carry data on the registered band/network "
            "(e.g. pdn-ipv6-call-disallowed with an unreachable IPv4 gateway)."
        )
        self.last_failure_time = time.time()
        try:
            await self._disconnect_bearer()
        except Exception as e:
            logger.debug(f"Bearer teardown after dead data path failed: {e}",
                        extra={'interface_number': self.interface_number})
        self.transition(ModemEvent.CONNECTION_FAILED)
        # No-op when no eligible/ present alternate SIM, failover disabled, or
        # cooldown active — same contract as the other connection-failure sites.
        await self._handle_sim_missing_failover()
        return False

    async def _reapply_vyos_infrastructure(self, interface_name):
        """Re-apply VyOS infrastructure settings after bearer IP configuration.

        When a modem resets or USB re-enumerates, the kernel interface is
        destroyed and recreated, losing all VyOS-managed settings (VRF binding,
        mirror/redirect tc rules, sysctl knobs, description, etc.).  These are
        normally applied by interfaces_wwan.py → WWANIf.update() at commit time
        but there is no callback from the FSM back to configd.

        This method re-reads the active VyOS config tree and calls
        WWANIf.update() to restore those settings.  It runs in a thread pool
        because the VyOS Config API is synchronous.
        """
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self._reapply_vyos_infrastructure_sync, interface_name
            )
        except Exception as e:
            logger.warning(f"VyOS infrastructure reapply failed: {e}",
                          extra={'interface_number': self.interface_number})

    def _reapply_vyos_infrastructure_sync(self, interface_name):
        """Synchronous helper — runs in executor thread."""
        from vyos.config import Config
        from vyos.ifconfig import WWANIf

        conf = Config()
        path = ['interfaces', 'wwan', interface_name]
        if not conf.exists(path):
            logger.debug("No VyOS config for %s — skipping infrastructure reapply",
                        interface_name,
                        extra={'interface_number': self.interface_number})
            return

        wwan = conf.get_config_dict(
            path,
            key_mangling=('-', '_'),
            get_first_key=True,
            with_defaults=True,
        )
        wwan['ifname'] = interface_name

        w = WWANIf(interface_name)
        w.update(wwan)
        logger.info("VyOS infrastructure settings reapplied to %s",
                    interface_name,
                    extra={'interface_number': self.interface_number})

    async def _clear_interface_addresses(self, interface_name):
        """Clear existing global IP addresses from interface (keep link-local)"""
        try:
            # Clear IPv4 addresses (except loopback/link-local)
            result = await asyncio.create_subprocess_exec(
                'ip', 'addr', 'flush', 'dev', interface_name, 'scope', 'global',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.communicate()

            # Note: We don't clear IPv6 addresses explicitly as 'flush scope global'
            # should handle both, but we keep link-local addresses intact

        except Exception as e:
            logger.debug(f"Error clearing interface addresses: {e}",
                        extra={'interface_number': self.interface_number})

        # Remove carrier DNS entries from VyOS hostsd so stale servers don't persist
        try:
            import vyos.hostsd_client
            hc = vyos.hostsd_client.Client()
            hc.delete_name_server_tags_system([interface_name])
            hc.delete_name_servers([interface_name])
            hc.apply()
        except Exception:
            pass  # hostsd may not be running; non-fatal

    # ── SMS support ─────────────────────────────────────────────────────────
    # Messages are stored in per-SIM JSON flat files under SMS_STORAGE_DIR,
    # keyed by ICCID.  Each file holds up to SMS_MAX_MESSAGES entries.
    # ModemManager Messaging D-Bus API is used for send/receive.

    def _sms_storage_path(self) -> str:
        """Return the flat-file path for the current SIM's SMS store."""
        sim = self.last_known_sim_info or {}
        iccid = sim.get('sim_identifier', '') or 'unknown'
        return os.path.join(SMS_STORAGE_DIR, f"sms_{iccid}.json")

    def _sms_load(self) -> list:
        """Load SMS messages from the current SIM's flat file."""
        path = self._sms_storage_path()
        if not os.path.exists(path):
            return []
        try:
            with open(path, 'r') as f:
                messages = json.load(f)
            if not isinstance(messages, list):
                return []
            return messages
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"SMS store corrupt or unreadable, starting fresh: {e}",
                          extra={'interface_number': self.interface_number})
            return []

    def _sms_save(self, messages: list):
        """Save SMS messages to the current SIM's flat file (atomic write)."""
        path = self._sms_storage_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        import tempfile
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix='.tmp')
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(messages[-SMS_MAX_MESSAGES:], f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _sms_append(self, msg: dict):
        """Append a message to the store, enforcing the cap."""
        messages = self._sms_load()
        messages.append(msg)
        # Trim oldest if over cap
        if len(messages) > SMS_MAX_MESSAGES:
            messages = messages[-SMS_MAX_MESSAGES:]
        self._sms_save(messages)

    async def sms_send(self, recipient: str, text: str) -> dict:
        """Send an SMS via ModemManager and record it in the flat-file store.

        Returns a dict with 'status' and 'message_id' keys.
        """
        if not self.modem_path:
            raise RuntimeError("No modem available — cannot send SMS")

        try:
            introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, self.modem_path)
            proxy = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, self.modem_path, introspect)
            messaging = proxy.get_interface(MESSAGING_INTERFACE)

            # Create SMS on ModemManager — properties dict with string Variants
            sms_properties = {
                'number': Variant('s', recipient),
                'text': Variant('s', text),
            }
            sms_path = await messaging.call_create(sms_properties)

            logger.info(f"SMS created at {sms_path}, sending...",
                       extra={'interface_number': self.interface_number})

            # Send the SMS
            sms_introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, sms_path)
            sms_proxy = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, sms_path, sms_introspect)
            sms_iface = sms_proxy.get_interface(SMS_INTERFACE)
            await sms_iface.call_send()

            # Record in flat file
            msg_id = len(self._sms_load()) + 1
            record = {
                'id': msg_id,
                'direction': 'outgoing',
                'number': recipient,
                'text': text,
                'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'status': 'sent',
            }
            self._sms_append(record)

            # Delete from ModemManager after successful send
            try:
                await messaging.call_delete(sms_path)
            except Exception:
                pass  # Non-fatal — message already sent

            logger.info(f"SMS sent to {recipient}, id={msg_id}",
                       extra={'interface_number': self.interface_number})
            return {'status': 'sent', 'message_id': msg_id}

        except Exception as e:
            logger.error(f"SMS send failed: {e}",
                        extra={'interface_number': self.interface_number})
            raise

    async def sms_list(self) -> list:
        """List all stored SMS messages for the current SIM."""
        return self._sms_load()

    async def sms_read(self, message_id: int) -> dict:
        """Read a specific SMS by ID."""
        messages = self._sms_load()
        for msg in messages:
            if msg.get('id') == message_id:
                # Mark as read if incoming and unread
                if msg.get('direction') == 'incoming' and not msg.get('read', False):
                    msg['read'] = True
                    self._sms_save(messages)
                return msg
        raise ValueError(f"SMS message {message_id} not found")

    async def sms_delete(self, message_id: int) -> dict:
        """Delete a specific SMS by ID."""
        messages = self._sms_load()
        new_messages = [m for m in messages if m.get('id') != message_id]
        if len(new_messages) == len(messages):
            raise ValueError(f"SMS message {message_id} not found")
        self._sms_save(new_messages)
        logger.info(f"SMS message {message_id} deleted",
                   extra={'interface_number': self.interface_number})
        return {'status': 'deleted', 'message_id': message_id}

    async def sms_delete_all(self) -> dict:
        """Delete all SMS messages for the current SIM."""
        self._sms_save([])
        logger.info("All SMS messages deleted",
                   extra={'interface_number': self.interface_number})
        return {'status': 'deleted', 'count': 0}

    async def _handle_incoming_sms(self, sms_path: str):
        """Handle an incoming SMS notification from ModemManager."""
        try:
            sms_introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, sms_path)
            sms_proxy = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, sms_path, sms_introspect)
            sms_props = sms_proxy.get_interface('org.freedesktop.DBus.Properties')

            # Read SMS properties
            number_v = await sms_props.call_get(SMS_INTERFACE, 'Number')
            text_v = await sms_props.call_get(SMS_INTERFACE, 'Text')
            timestamp_v = await sms_props.call_get(SMS_INTERFACE, 'Timestamp')
            state_v = await sms_props.call_get(SMS_INTERFACE, 'State')

            number = number_v.value if hasattr(number_v, 'value') else str(number_v)
            text = text_v.value if hasattr(text_v, 'value') else str(text_v)
            timestamp = timestamp_v.value if hasattr(timestamp_v, 'value') else str(timestamp_v)
            state = state_v.value if hasattr(state_v, 'value') else int(state_v)

            # ModemManager SMS states of interest:
            #   2 = receiving (message object exists but may still be assembling)
            #   3 = received  (fully received)
            # Some modems can remain in "receiving" long enough that users
            # see it via mmcli, but our previous logic dropped it completely.
            if state not in (2, 3):
                return  # Not an incoming message state we expose

            # Avoid duplicates when the same ModemManager SMS object is observed
            # both during startup drain and live Added signal processing.
            existing = self._sms_load()
            for msg in existing:
                if msg.get('source_path') == sms_path:
                    return

            msg_id = len(existing) + 1
            record = {
                'id': msg_id,
                'direction': 'incoming',
                'number': number,
                'text': text,
                'timestamp': timestamp or datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'status': 'received' if state == 3 else 'receiving',
                'read': False,
                'source_path': sms_path,
            }
            self._sms_append(record)

            logger.info(f"Incoming SMS from {number}, id={msg_id}",
                       extra={'interface_number': self.interface_number})

            # Delete from ModemManager to free SIM storage once fully received.
            # Keep "receiving" objects untouched so ModemManager can finish
            # assembly/transition to RECEIVED.
            try:
                if state == 3:
                    messaging_introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, self.modem_path)
                    messaging_proxy = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, self.modem_path, messaging_introspect)
                    messaging = messaging_proxy.get_interface(MESSAGING_INTERFACE)
                    await messaging.call_delete(sms_path)
            except Exception:
                pass  # Non-fatal

        except Exception as e:
            logger.error(f"Failed to process incoming SMS: {e}",
                       extra={'interface_number': self.interface_number})

    async def _setup_sms_listener(self):
        """Subscribe to ModemManager Messaging.Added signal for incoming SMS."""
        if not self.modem_path:
            return
        try:
            introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, self.modem_path)
            proxy = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, self.modem_path, introspect)
            messaging = proxy.get_interface(MESSAGING_INTERFACE)

            def on_sms_added(path, received):
                """Callback for new SMS — received=True means incoming."""
                if received:
                    asyncio.ensure_future(self._handle_incoming_sms(path))

            messaging.on_added(on_sms_added)
            logger.info("SMS listener registered",
                       extra={'interface_number': self.interface_number})

            # Also drain any SMS already waiting on the SIM
            await self._drain_existing_sms()

        except Exception as e:
            logger.warning(f"Could not set up SMS listener: {e}",
                          extra={'interface_number': self.interface_number})

    async def _drain_existing_sms(self):
        """Import any SMS already stored on the SIM into our flat-file store."""
        if not self.modem_path:
            return
        try:
            introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, self.modem_path)
            proxy = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, self.modem_path, introspect)
            props = proxy.get_interface('org.freedesktop.DBus.Properties')
            messages_v = await props.call_get(MESSAGING_INTERFACE, 'Messages')
            sms_paths = messages_v.value if hasattr(messages_v, 'value') else []

            for sms_path in sms_paths:
                await self._handle_incoming_sms(sms_path)

        except Exception as e:
            logger.debug(f"Could not drain existing SMS: {e}",
                        extra={'interface_number': self.interface_number})
