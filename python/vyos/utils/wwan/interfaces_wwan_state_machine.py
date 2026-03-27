#!/usr/bin/env python3
# filepath: /home/jfeeney/vyos-1x/python/vyos/utils/wwan/interfaces_wwan_state_machine.py
import asyncio
import time
import os
import json
import datetime
from enum import Enum
from dbus_next.aio import MessageBus  # pylint: disable=import-error
from dbus_next.message import Message  # pylint: disable=import-error
from dbus_next.errors import DBusError  # pylint: disable=import-error
from dbus_next import Variant  # pylint: disable=import-error
from automaton import machines  # pylint: disable=import-error
from vyos.utils.wwan.interfaces_wwan_util import modem_reset

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

from vyos.utils.wwan.rfc5424_logging import RFC5424Formatter as _BaseFormatter, setup_logging


class FSMFormatter(_BaseFormatter):
    """FSM-specific RFC 5424 formatter with state-machine message IDs."""

    def _get_message_id(self, record):
        msg = record.getMessage().lower()
        if 'state changed' in msg or '\u2192' in msg:
            return 'STATE_CHANGE'
        elif 'modem found' in msg:
            return 'MODEM_FOUND'
        elif 'config applied' in msg:
            return 'CONFIG_APPLIED'
        elif 'connecting' in msg:
            return 'CONNECT_EVENT'
        elif 'disconnecting' in msg or 'disconnected' in msg:
            return 'DISCONNECT_EVENT'
        elif 'usage' in msg and ('rx=' in msg or 'tx=' in msg):
            return 'USAGE_STATS'
        elif 'usage limit' in msg:
            return 'USAGE_LIMIT'
        elif 'scan' in msg:
            return 'MODEM_SCAN'
        elif 'fsm error' in msg:
            return 'FSM_ERROR'
        elif 'timeout' in msg:
            return 'TIMEOUT'
        elif 'sim switch' in msg:
            return 'SIM_SWITCH'
        else:
            return 'FSM_EVENT'

    def _build_structured_data(self, record):
        sd_elements = []
        fsm_data = []
        if hasattr(record, 'interface_number'):
            fsm_data.append(f'interface="{record.interface_number}"')
        if hasattr(record, 'current_state'):
            fsm_data.append(f'state="{record.current_state}"')
        if hasattr(record, 'event'):
            fsm_data.append(f'event="{record.event}"')
        if hasattr(record, 'modem_path'):
            fsm_data.append(f'modem_path="{record.modem_path}"')
        if hasattr(record, 'physdev_uid'):
            fsm_data.append(f'physdev_uid="{record.physdev_uid}"')
        if hasattr(record, 'rx_bytes'):
            fsm_data.append(f'rx_bytes="{record.rx_bytes}"')
        if hasattr(record, 'tx_bytes'):
            fsm_data.append(f'tx_bytes="{record.tx_bytes}"')
        if hasattr(record, 'signal_strength'):
            fsm_data.append(f'signal="{record.signal_strength}"')
        if hasattr(record, 'current_sim'):
            fsm_data.append(f'current_sim="{record.current_sim}"')
        if hasattr(record, 'config_sim'):
            fsm_data.append(f'config_sim="{record.config_sim}"')
        if hasattr(record, 'sim_switch_reason'):
            fsm_data.append(f'sim_switch_reason="{record.sim_switch_reason}"')
        if hasattr(record, 'target_sim'):
            fsm_data.append(f'target_sim="{record.target_sim}"')
        if fsm_data:
            sd_elements.append(f'[fsm@32473 {" ".join(fsm_data)}]')
        origin_data = ['software="vyos-wwan-fsm"', 'version="1.0"']
        sd_elements.append(f'[origin@32473 {" ".join(origin_data)}]')
        return ''.join(sd_elements) if sd_elements else '-'


logger = setup_logging(__name__, "wwan-fsm", formatter_class=FSMFormatter)

# Constants
MODEM_MANAGER_SERVICE = "org.freedesktop.ModemManager1"
MODEM_MANAGER_PATH = "/org/freedesktop/ModemManager1"
MODEM_INTERFACE = "org.freedesktop.ModemManager1.Modem"
OBJECT_MANAGER_INTERFACE = "org.freedesktop.DBus.ObjectManager"
BEARER_INTERFACE = "org.freedesktop.ModemManager1.Bearer"
SIMPLE_INTERFACE = "org.freedesktop.ModemManager1.Modem.Simple"

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

    def __init__(self, interface_number: int, bus: MessageBus):
        self.interface_number = interface_number
        self.bus = bus
        self.proxy = None
        self.config = None
        self._previous_config = None        # Track previous config for selective disconnection
        self.modem_path = None
        self.bearer_path = None
        self.user_disconnected = False
        self.usage_monitor_task = None
        self.current_active_sim = None      # Track actual active SIM
        self.config_active_sim = None       # Track configured active SIM
        self.sim_switch_reason = None       # Track why SIM was switched
        self.target_sim_slot = None         # Track target SIM during switch
        self.previous_sim_slot = None        # Track original SIM for rollback on switch failure

        # SIM failover cooldown tracking to prevent ping-pong
        self.last_failover_time = 0          # Timestamp of last SIM failover
        self.failover_count = 0              # Number of failovers since last stable connection
        self.failover_cooldown_seconds = 300 # 5 minute cooldown between failovers
        self.max_failovers_before_backoff = 3 # Max failovers before extended backoff
        self.failover_backoff_seconds = 900  # 15 minute extended backoff after max failovers

        # Connectivity recovery tracking for SIM escalation
        self.connectivity_recovery_attempts = 0  # Consecutive recovery attempts on same SIM
        self.max_recovery_before_sim_switch = 3  # Attempts before escalating to SIM switch

        # SIM failback tracking — automatically return to primary SIM when possible
        self.is_on_failover_sim = False          # True when running on non-primary SIM after failover
        self.primary_sim_slot = None             # Configured primary_sim_slot (set from config)
        self.failback_task = None                # Periodic failback check task
        self.failback_suppressed_by_data_limit = False  # Sticky failover: suppress failback until billing reset
        self._sticky_failover_timestamp = None            # When sticky hold was activated
        self.failback_suppressed_by_connection_failure = False  # Suppress failback when primary SIM's APN cascade failed

        # SIM change tracking for worldwide operation
        self.last_known_sim_info = None     # Store SIM info from last successful connection
        self.sim_changed = False            # Flag to indicate SIM card change detected
        self.connected_apn = None           # Last successful APN config dict (for reconnection & status)

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

    def _is_reset_allowed(self) -> bool:
        """Check if hardware reset is allowed (not in cooldown period)"""
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
        # Start reset grace period to prevent false SIM missing detection
        self.reset_operation_in_progress = True
        self.reset_grace_period_end = time.time() + 60  # 60 second grace period after reset
        logger.info(f"Hardware reset recorded, next reset allowed after {self.reset_cooldown_seconds}s cooldown",
                   extra={'interface_number': self.interface_number,
                          'reset_time': self.last_reset_time,
                          'grace_period_end': self.reset_grace_period_end})

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
            if current_fsm_state in [ModemState.CONFIGURING.value, ModemState.CONNECTING.value]:
                # Distinguish between PIN-locked and actually missing SIM
                self._safe_create_task(self._handle_locked_state_detection())

        elif mm_state == 3:  # DISABLED
            if current_fsm_state in [ModemState.CONFIGURING.value, ModemState.CONNECTING.value,
                                    ModemState.CONNECTED.value]:
                # Don't trigger SIM missing if this is service-initiated or we're in reset grace period
                if not self.service_initiated_disable and not self._is_in_reset_grace_period():
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
            if current_fsm_state == ModemState.WAITING_FOR_SIM.value:
                # SIM might have been inserted!
                logger.info("Modem enabled while waiting for SIM - checking for insertion",
                           extra={'interface_number': self.interface_number})
                self._safe_create_task(self._handle_potential_sim_insertion())
            elif current_fsm_state == ModemState.CONFIGURING.value:
                # Modem enabled successfully during configuration - can proceed
                logger.info("Modem enabled, continuing configuration",
                           extra={'interface_number': self.interface_number})
                # Don't transition - let configuration continue

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

        elif mm_state == 9:  # DISCONNECTING
            if current_fsm_state in [ModemState.CONNECTED.value]:
                # Connection being terminated - stop network interface monitoring and trigger enhanced reconnection
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

                    # Only start usage monitoring if data limits are configured (per-SIM)
                    sim_data_cfg = self._get_active_sim_data_config()
                    if sim_data_cfg['data_limit_size']:
                        logger.info("Data usage limits configured, will start monitoring",
                                   extra={'interface_number': self.interface_number,
                                          'limit_gb': sim_data_cfg['data_limit_size'] / (1024*1024*1024),
                                          'sim_slot': self.current_active_sim})
                        # Don't transition — just start the monitoring task
                        if not self.usage_monitor_task or self.usage_monitor_task.done():
                            self.usage_monitor_task = self._safe_create_task(self.monitor_data_usage())
                    else:
                        logger.info("No data usage limits configured, staying in CONNECTED state",
                                   extra={'interface_number': self.interface_number})

                    # Start connectivity monitoring (ping tests) if configured
                    self._safe_create_task(self.start_connectivity_monitoring())

                    # Start failback monitor if we're on the failover SIM
                    self._start_failback_monitor()

            elif current_fsm_state == ModemState.CONNECTED.value:
                # Already connected - connection is stable
                logger.info("Already in CONNECTED state - connection stable",
                           extra={'interface_number': self.interface_number})


        elif mm_state in [-1, 0]:  # FAILED or UNKNOWN
            if current_fsm_state in [ModemState.CONFIGURING.value, ModemState.CONNECTING.value,
                                    ModemState.CONNECTED.value]:
                # Failure during active operation
                logger.error("Modem entered failed/unknown state",
                            extra={'interface_number': self.interface_number,
                                   'mm_state': mm_state})
                self.transition(ModemEvent.CONNECTION_FAILED)

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
            if current_state in [ModemState.CONNECTED.value]:
                # Stop network interface monitoring when leaving connected state
                try:
                    self._safe_create_task(self._stop_network_interface_monitoring())
                except RuntimeError:
                    # No event loop running (e.g., during tests) - ignore
                    pass
                # This is a user-initiated disconnect from connected state
                self.user_disconnected = True
                logger.info("User-initiated disconnect flagged",
                           extra={'interface_number': self.interface_number,
                                  'current_state': current_state})

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

            # Log detailed failure info when entering FAILED state
            if new_state == ModemState.FAILED.value and old_state != ModemState.FAILED.value:
                logger.error("Modem entered FAILED state",
                            extra={'interface_number': self.interface_number,
                                   'failure_reason': self.last_failure_reason or 'unspecified',
                                   'failed_apn': self.last_failed_apn or 'none',
                                   'configured_apn_rejected': self.configured_apn_rejected,
                                   'trigger_event': event.value,
                                   'from_state': old_state})
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

    def apply_config(self, config: dict):
        """Apply configuration - handles all states properly"""
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
                          'signal_threshold': self.reconnection_signal_threshold,
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
            # Normal reconfiguration
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
            # Config is stored, SIM switch completion will pick up new config

        elif current in (
            ModemState.CONNECTING.value,
            ModemState.DISCONNECTING.value
        ):
            # Config change during connection transition - queue for completion
            logger.info("Configuration queued - connection transition in progress",
                       extra={'interface_number': self.interface_number,
                              'current_state': current})
            # Will be handled when transition completes

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
                          'signal_threshold': self.parsed_config.enhanced_reconnection.signal_threshold,
                          'current_state': self.machine.current_state})

    def _apply_parsed_configuration(self):
        """Apply parsed configuration to instance variables for backward compatibility"""
        # Enhanced reconnection configuration
        self.enhanced_reconnection = self.parsed_config.enhanced_reconnection.enabled
        self.reconnection_signal_threshold = self.parsed_config.enhanced_reconnection.signal_threshold
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

        # Connection mode: always-on | connect-on-demand | dial-on-demand
        self.connection_mode = self.parsed_config.raw_config.get('connection_mode', 'always-on')

        # Bearer D-Bus signal monitoring state
        self._bearer_proxy = None
        self._bearer_interface = None

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

            # Step 2: Configure SIM slot while disabled
            await self._configure_sim_slot()

            # Step 3: Configure supported bands while disabled
            await self._configure_supported_bands()

            # Step 3.5: Configure network mode (access technology) while disabled
            await self._configure_network_mode()

            # Step 4: Enable the modem
            await self._ensure_modem_enabled()

            # Step 5: Unlock SIM if needed after enabling
            await self._unlock_sim_if_needed()

            # Step 5.5: Validate ICCID lock (SIM must be enabled + unlocked for identity to be readable)
            await self._validate_sim_iccid()

            # Step 6: 🆕 Configure preferred carrier if specified
            await self._configure_preferred_carrier()

            logger.info("Initial modem configuration complete",
                       extra={'interface_number': self.interface_number})

            # Check connection mode: park at REGISTERED_IDLE for connect-on-demand
            if self.machine.current_state == ModemState.CONFIGURING.value:
                if self.connection_mode == 'connect-on-demand':
                    logger.info("Connect-on-demand active — parking at REGISTERED_IDLE "
                                "(modem registered, no bearer, SMS available)",
                               extra={'interface_number': self.interface_number})
                    self.transition(ModemEvent.ENTER_IDLE)
                else:
                    # always-on: auto-connect and stay connected (auto-reconnect on failure)
                    # dial-on-demand: auto-connect at boot, bearer toggleable via
                    #   connect_bearer() / disconnect_bearer(); no auto-reconnect
                    #   after manual disconnect_bearer()
                    logger.info(f"{self.connection_mode} active — proceeding to connection phase",
                               extra={'interface_number': self.interface_number})
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

            # Get SIM config for connection parameters
            active_slot = self.config.get('primary_sim_slot', 1) if self.config else 1
            sim_config = {'pdp_type': 'ipv4', 'roaming': 'disabled'}  # defaults

            if self.config and 'sim_slots' in self.config:
                for slot in self.config['sim_slots']:
                    if slot['slot'] == active_slot:
                        sim_config = {
                            'pdp_type': slot.get('pdp_type', 'ipv4'),
                            'roaming': slot.get('roaming', 'disabled')
                        }
                        break

            connection_successful = False

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

            # PRIORITY 1: Try configured APN first (highest priority) - unless SIM changed
            apn_config = None
            if not sim_changed and self.config and 'sim_slots' in self.config:
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
                    logger.info("Attempting connection with configured APN (highest priority)",
                               extra={'interface_number': self.interface_number,
                                      'configured_apn': apn_config['name']})

                    try:
                        success = await self._try_connection_with_apn(apn_config, sim_config)
                        if success:
                            connection_successful = True
                    except Exception as e:
                        logger.warning(f"Configured APN failed: {e}",
                                     extra={'interface_number': self.interface_number})

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
                    try:
                        success = await self._try_connection_with_apn(self.connected_apn, sim_config)
                        if success:
                            connection_successful = True
                            logger.info("Last-connected APN reconnection successful",
                                       extra={'interface_number': self.interface_number,
                                              'apn_name': last_apn_name})
                    except Exception as e:
                        logger.warning(f"Last-connected APN failed: {e}",
                                      extra={'interface_number': self.interface_number})

            # PRIORITY 3: Try APNs from discovery service
            if not connection_successful and self.config and self.config.get('android_apn_discovery') == 'enabled':
                logger.info("Attempting connection using APN discovery service",
                           extra={'interface_number': self.interface_number})
                try:
                    # This will try discovered APNs in order
                    success = await self._try_apn_candidates_from_discovery(sim_config)
                    if success:
                        connection_successful = True
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
                logger.info("Connection established successfully, transitioning to CONNECTED state",
                           extra={'interface_number': self.interface_number})

                # Clear any previous failure tracking — connection is now good
                self.last_failure_reason = ''
                self.last_failure_time = 0
                self.last_failed_apn = ''
                self.configured_apn_rejected = False

                # Store the connected APN for fast reconnection and status reporting
                cm_apn = getattr(self.connection_manager, 'connected_apn', None)
                if cm_apn:
                    self.connected_apn = cm_apn.copy()
                    logger.info("Stored connected APN for fast reconnection",
                               extra={'interface_number': self.interface_number,
                                      'apn_name': cm_apn.get('name', '')})

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
                else:
                    logger.info("Skipping connected transition - FSM already advanced",
                               extra={'interface_number': self.interface_number,
                                      'current_state': self.machine.current_state})
                logger.info("Connected - staying in CONNECTED state for event-driven monitoring",
                           extra={'interface_number': self.interface_number})

                # Apply bearer IP configuration to interface (VyOS responsibility)
                await self._apply_bearer_ip_configuration()

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

                # Only start data usage monitoring if limits are configured (per-SIM)
                sim_data_cfg = self._get_active_sim_data_config()
                if sim_data_cfg['data_limit_size']:
                    logger.info("Data usage limits configured, starting data monitoring",
                               extra={'interface_number': self.interface_number,
                                      'limit_gb': sim_data_cfg['data_limit_size'] / (1024*1024*1024),
                                      'sim_slot': self.current_active_sim})
                    if not self.usage_monitor_task or self.usage_monitor_task.done():
                        self.usage_monitor_task = self._safe_create_task(self.monitor_data_usage())
                else:
                    logger.info("No data usage limits - connection monitoring is now event-driven",
                               extra={'interface_number': self.interface_number})

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

                logger.error("All APN connection methods failed",
                           extra={'interface_number': self.interface_number,
                                  'configured_apn_rejected': self.configured_apn_rejected,
                                  'failed_apn': self.last_failed_apn,
                                  'failure_reason': self.last_failure_reason})

                # For dual-SIM: attempt failover to the other SIM if enabled
                if (self._is_sim_failover_enabled()
                        and self._is_failover_allowed()):
                    fallback_sim = 2 if self.current_active_sim == 1 else 1
                    logger.warning(
                        "Initial connection failed on current SIM, "
                        "attempting failover to alternate SIM",
                        extra={'interface_number': self.interface_number,
                               'current_sim': self.current_active_sim,
                               'target_sim': fallback_sim,
                               'reason': 'initial_connection_failure'})
                    self.sim_switch_reason = 'initial_connection_failure'
                    self.target_sim_slot = fallback_sim
                    # Suppress failback to primary until new config arrives —
                    # the primary SIM's APN/parameters are known-bad so there is
                    # no point switching back only to fail again.
                    self.failback_suppressed_by_connection_failure = True
                    self._record_failover()
                    self._emit_failover_event(
                        event_type='failover',
                        from_sim=self.current_active_sim,
                        to_sim=fallback_sim,
                        reason='initial_connection_failure',
                        trigger='_configure_modem_initial',
                        extra_data={'configured_apn_rejected': self.configured_apn_rejected,
                                    'failed_apn': self.last_failed_apn})
                    self.transition(ModemEvent.SWITCH_SIM)
                    self._safe_create_task(self._execute_sim_switch())
                else:
                    # Single SIM or failover not allowed — park in FAILED and
                    # wait for the user to push corrected configuration.
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
            # Don't override SIM_MISSING transition with CONNECTION_FAILED
            if self.machine.current_state != ModemState.WAITING_FOR_SIM.value:
                self.transition(ModemEvent.CONNECTION_FAILED)
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

                primary_sim_slot = self.config.get('primary_sim_slot', 1)
                sim_slots = self.config.get('sim_slots', [])
                active_sim_config = next(
                    (sim for sim in sim_slots if sim['slot'] == primary_sim_slot), {}
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
            await iface.call_send_pin(pin)

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
            await iface.call_send_puk(puk, pin)

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

            # Get active SIM configuration
            primary_sim_slot = self.config.get('primary_sim_slot', 1)
            sim_slots = self.config.get('sim_slots', [])
            active_sim_config = next((sim for sim in sim_slots if sim['slot'] == primary_sim_slot), {})

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
                        await asyncio.sleep(10)
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
                    scan_timeout = self.config.get('network_scan_timeout', 60)
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
            scan_timeout = self.config.get('network_scan_timeout', 60)
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

                # Match preferred carrier by name or MCCMNC code
                # Status 1 = Available, 2 = Current (already registered)
                if preferred_carrier and (
                    preferred_carrier.lower() in operator_name.lower() or
                    preferred_carrier == operator_code) and status in [1, 2]:
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
            await asyncio.sleep(15)
        elif preferred_carrier:
            logger.warning("Preferred carrier not found in scan, using automatic",
                          extra={'interface_number': self.interface_number})

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

    def _record_failover(self):
        """Record that a SIM failover was performed"""
        self.last_failover_time = time.time()
        self.failover_count += 1
        self.is_on_failover_sim = True
        logger.info(f"SIM failover #{self.failover_count} recorded",
                   extra={'interface_number': self.interface_number,
                          'failover_count': self.failover_count,
                          'failover_time': self.last_failover_time,
                          'primary_sim': self.primary_sim_slot})

    def _reset_failover_counters(self):
        """Reset failover counters after a stable connection is established"""
        if self.failover_count > 0 or self.connectivity_recovery_attempts > 0:
            logger.info("Resetting failover counters after stable connection",
                       extra={'interface_number': self.interface_number,
                              'previous_failover_count': self.failover_count,
                              'previous_recovery_attempts': self.connectivity_recovery_attempts})
        self.failover_count = 0
        self.connectivity_recovery_attempts = 0

    # ── SIM failback mechanism ───────────────────────────────────────────────

    def _start_failback_monitor(self):
        """Start the periodic failback check if conditions are met.

        Conditions:
          1. Currently running on the failover (non-primary) SIM
          2. sim_failback_enabled is True in config
          3. No failback task already running
        """
        if not self.is_on_failover_sim:
            return
        if not self.config:
            return
        if not self.config.get('sim_failback_enabled', True):
            logger.debug("SIM failback disabled in config",
                        extra={'interface_number': self.interface_number})
            return

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

        primary = self.primary_sim_slot
        if primary is None:
            logger.warning("Primary SIM slot unknown, cannot run failback monitor",
                          extra={'interface_number': self.interface_number})
            return

        logger.info("Failback monitor loop started",
                   extra={'interface_number': self.interface_number,
                          'primary_sim': primary,
                          'interval_seconds': check_interval})

        while True:
            try:
                await asyncio.sleep(check_interval)

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

                if primary_available:
                    logger.info("Primary SIM appears available — initiating failback",
                               extra={'interface_number': self.interface_number,
                                      'primary_sim': primary,
                                      'current_sim': self.current_active_sim})
                    await self._execute_failback(primary)
                    break  # Failback initiated, exit loop
                else:
                    logger.debug("Primary SIM not yet available, will check again",
                                extra={'interface_number': self.interface_number,
                                       'primary_sim': primary,
                                       'next_check_in': check_interval})

            except asyncio.CancelledError:
                logger.info("Failback monitor cancelled",
                           extra={'interface_number': self.interface_number})
                break
            except Exception as e:
                logger.error(f"Failback monitor error: {e}",
                            extra={'interface_number': self.interface_number})
                # Continue monitoring despite errors
                await asyncio.sleep(check_interval)

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

        for attempt in range(max_attempts):
            try:
                # Use escalating timeouts: 30s, 60s
                timeout = 30 + (30 * attempt)
                await self._try_disable_modem_once(timeout)

                # Transition to next step
                self.transition(ModemEvent.SIM_DISABLED)
                await self._sim_switch_hardware()
                return  # Success!

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

    async def _handle_sim_missing_failover(self):
        """Handle SIM missing by attempting failover to available SIM.

        Protected by _sim_failover_lock to prevent multiple concurrent failover
        attempts when the SIM tray is rapidly pushed in and out.  If a failover
        or SIM switch is already running, additional calls are silently skipped.
        """
        try:
            # ── Reentrancy guard ─────────────────────────────────────────
            if self._sim_failover_in_progress or self._sim_switch_in_progress:
                logger.info("SIM failover skipped — already in progress",
                           extra={'interface_number': self.interface_number,
                                  'failover_in_progress': self._sim_failover_in_progress,
                                  'switch_in_progress': self._sim_switch_in_progress})
                return False

            if self._sim_failover_lock.locked():
                logger.info("SIM failover skipped — lock held by another task",
                           extra={'interface_number': self.interface_number})
                return False

            async with self._sim_failover_lock:
                self._sim_failover_in_progress = True
                try:
                    return await self._handle_sim_missing_failover_locked()
                finally:
                    self._sim_failover_in_progress = False

        except Exception as e:
            logger.error(f"SIM failover attempt failed (outer): {e}",
                        extra={'interface_number': self.interface_number})
            return False

    async def _handle_sim_missing_failover_locked(self):
        """Inner implementation of SIM failover — always called under _sim_failover_lock."""
        try:
            if not self.config:
                return False

            # Proxy may have disappeared between the guard check and lock acquisition
            if not self.proxy:
                logger.warning("Proxy gone before SIM failover could query SIM slots",
                              extra={'interface_number': self.interface_number})
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
                                     'failover_count': self.failover_count,
                                     'last_failover_time': self.last_failover_time})
                return False

            logger.info("Attempting SIM failover due to missing SIM",
                       extra={'interface_number': self.interface_number,
                              'missing_sim': self.config_active_sim})

            # Check what SIMs are available
            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
            sim_slots_variant = await props.call_get(MODEM_INTERFACE, "SimSlots")
            sim_slots = sim_slots_variant.value  # Extract array from Variant

            available_sims = []
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
                              'config_sim': self.config_active_sim})

            # Find alternative SIM
            fallback_sim = None
            for sim_num in available_sims:
                if sim_num != self.config_active_sim:
                    fallback_sim = sim_num
                    break

            if fallback_sim:
                logger.warning("Performing automatic SIM failover",
                              extra={'interface_number': self.interface_number,
                                     'from_sim': self.config_active_sim,
                                     'to_sim': fallback_sim,
                                     'reason': 'sim_missing'})

                # Set failover reason and target
                self.sim_switch_reason = 'automatic_failover_missing_sim'
                self.target_sim_slot = fallback_sim

                # Record the failover for cooldown tracking
                self._record_failover()

                # Emit event for observability
                self._emit_failover_event(
                    event_type='failover',
                    from_sim=self.config_active_sim,
                    to_sim=fallback_sim,
                    reason='sim_missing',
                    trigger='_handle_sim_missing_failover',
                    extra_data={'available_sims': available_sims})

                # Start SIM switch process
                self.transition(ModemEvent.SWITCH_SIM)
                await self._execute_sim_switch()
                return True

            else:
                logger.error("No alternative SIM available for failover",
                            extra={'interface_number': self.interface_number,
                                   'config_sim': self.config_active_sim,
                                   'available_sims': available_sims})
                return False

        except Exception as e:
            logger.error(f"SIM failover attempt failed: {e}",
                        extra={'interface_number': self.interface_number})
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
                            logger.info("SIM insertion detected in configured slot",
                                       extra={'interface_number': self.interface_number,
                                              'sim_slot': config_sim_slot,
                                              'imsi': imsi[:6] + '...'})  # Partial IMSI for privacy

                            # SIM is back! Resume configuration
                            self.transition(ModemEvent.SIM_READY)
                            await self._configure_modem_initial()
                            return True

                    except Exception as e:
                        logger.debug(f"SIM slot {config_sim_slot} not ready: {e}",
                                    extra={'interface_number': self.interface_number})

            return False

        except Exception as e:
            logger.error(f"Error checking SIM insertion: {e}",
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

            # SIM switch complete - transition back to normal configuration
            self.transition(ModemEvent.SIM_SWITCH_COMPLETE)

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

    async def _configure_supported_bands(self):
        """Configure supported bands while modem is disabled.

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
            primary_sim_slot = self.config.get('primary_sim_slot', 1)
            sim_slots = self.config.get('sim_slots', [])
            active_sim_config = next((sim for sim in sim_slots if sim['slot'] == primary_sim_slot), {})

            per_sim_bands_raw = active_sim_config.get('supported_bands', 'all')
            if isinstance(per_sim_bands_raw, str):
                per_sim_bands_cfg = [b.strip() for b in per_sim_bands_raw.split(',') if b.strip()]
            else:
                per_sim_bands_cfg = list(per_sim_bands_raw)

            logger.info("Configuring supported bands while disabled",
                       extra={'interface_number': self.interface_number,
                              'primary_sim_slot': primary_sim_slot,
                              'per_sim_bands': per_sim_bands_cfg})

            # Get what bands the modem actually supports (MM returns numeric constants)
            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")

            try:
                # Get modem's supported bands (uint32 array)
                modem_supported_bands_variant = await props.call_get(MODEM_INTERFACE, "SupportedBands")
                modem_supported_bands = modem_supported_bands_variant.value if modem_supported_bands_variant else []
                modem_bands_list = [band.value for band in modem_supported_bands] if modem_supported_bands else []

                # Get currently enabled bands (uint32 array)
                current_bands_variant = await props.call_get(MODEM_INTERFACE, "CurrentBands")
                current_bands = current_bands_variant.value if current_bands_variant else []
                current_bands_list = [band.value for band in current_bands] if current_bands else []

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
                                             'sim_slot': primary_sim_slot})
                    if per_sim_invalid:
                        logger.warning("Invalid per-SIM band names ignored",
                                      extra={'interface_number': self.interface_number,
                                             'invalid_bands': per_sim_invalid,
                                             'valid_formats': ['all', 'eutran-1', 'ngran-78', 'umts-1', 'gsm-850']})

                # ── Compute target = per-SIM ∩ modem ────────────────────
                if per_sim_is_all:
                    # Per-SIM unrestricted — use all modem bands
                    target_bands = modem_bands_list
                    target_band_names = modem_band_names
                    logger.info("Per-SIM bands are 'all' — enabling all modem bands",
                               extra={'interface_number': self.interface_number,
                                      'count': len(target_bands)})
                else:
                    # Per-SIM restricts — intersect with modem-supported
                    target_bands = [b for b in per_sim_band_constants if b in modem_bands_list]
                    target_band_names = [self._mm_constant_to_band_name(b) for b in target_bands]
                    logger.info("Applying per-SIM ∩ modem band filter",
                               extra={'interface_number': self.interface_number,
                                      'per_sim_bands': [self._mm_constant_to_band_name(b) for b in per_sim_band_constants],
                                      'result_bands': target_band_names})

                # Fall back to all modem bands if intersection is empty
                if not target_bands:
                    logger.warning("Band intersection is empty — falling back to all modem-supported bands",
                                  extra={'interface_number': self.interface_number})
                    target_bands = modem_bands_list
                    target_band_names = modem_band_names

                    # Check if target bands are already enabled
                    if set(current_bands_list) == set(target_bands):
                        logger.info("Requested bands already configured correctly",
                                   extra={'interface_number': self.interface_number,
                                          'enabled_bands': current_band_names})
                        return

                # Apply band configuration using MM numeric constants
                logger.info("Setting new band configuration",
                           extra={'interface_number': self.interface_number,
                                  'from_bands': current_band_names,
                                  'to_bands': target_band_names,
                                  'from_constants': current_bands_list,
                                  'to_constants': target_bands})

                # Use ModemManager API to set bands (uint32 array)
                band_variants = [Variant('u', band) for band in target_bands]
                await props.call_set(MODEM_INTERFACE, "CurrentBands", Variant('au', band_variants))

                # Brief wait for band configuration to take effect
                await asyncio.sleep(3)

                # Verify band configuration
                new_bands_variant = await props.call_get(MODEM_INTERFACE, "CurrentBands")
                new_bands = new_bands_variant.value if new_bands_variant else []
                new_bands_list = [band.value for band in new_bands] if new_bands else []
                new_band_names = [self._mm_constant_to_band_name(band) for band in new_bands_list]

                if set(new_bands_list) == set(target_bands):
                    logger.info("Band configuration successful",
                               extra={'interface_number': self.interface_number,
                                      'applied_bands': new_band_names,
                                      'applied_constants': new_bands_list})
                else:
                    logger.warning("Band configuration verification failed",
                                  extra={'interface_number': self.interface_number,
                                         'target_bands': target_band_names,
                                         'actual_bands': new_band_names,
                                         'target_constants': target_bands,
                                         'actual_constants': new_bands_list})

            except Exception as band_e:
                # Many modems don't support runtime band configuration
                logger.info("Band configuration not supported by this modem or driver",
                           extra={'interface_number': self.interface_number,
                                  'error': str(band_e),
                                  'per_sim_bands': per_sim_bands_cfg})

        except Exception as e:
            logger.error(f"Band configuration error: {e}",
                        extra={'interface_number': self.interface_number})
            # Don't fail the entire configuration for band issues
            logger.warning("Continuing configuration without band changes",
                          extra={'interface_number': self.interface_number})

    async def _configure_network_mode(self):
        """Configure network mode (access technology) on the modem.

        Maps config values to ModemManager MMModemMode bitmask constants and
        applies them via SetCurrentModes(allowed, preferred).  Runs while the
        modem is still disabled so that mode changes take effect before the
        modem begins scanning for networks.
        """
        try:
            if not self.config:
                return

            network_mode = self.config.get('network_mode', 'auto')

            # MMModemMode bitmask constants
            MM_MODEM_MODE_NONE = 0
            MM_MODEM_MODE_2G   = 1 << 1   # 2
            MM_MODEM_MODE_3G   = 1 << 2   # 4
            MM_MODEM_MODE_4G   = 1 << 3   # 8
            MM_MODEM_MODE_5G   = 1 << 4   # 16
            MM_MODEM_MODE_ANY  = 0xFFFFFFFF

            # Map config strings to (allowed_mask, preferred_mask)
            mode_mapping = {
                'auto': (MM_MODEM_MODE_ANY, MM_MODEM_MODE_NONE),
                '2g':   (MM_MODEM_MODE_2G, MM_MODEM_MODE_NONE),
                '3g':   (MM_MODEM_MODE_3G | MM_MODEM_MODE_2G, MM_MODEM_MODE_NONE),
                'lte':  (MM_MODEM_MODE_4G, MM_MODEM_MODE_NONE),
                '4g':   (MM_MODEM_MODE_4G, MM_MODEM_MODE_NONE),
                '5g':   (MM_MODEM_MODE_5G | MM_MODEM_MODE_4G, MM_MODEM_MODE_5G),
            }

            mode_key = network_mode.lower().strip()
            if mode_key not in mode_mapping:
                logger.warning("Unrecognised network_mode value, falling back to 'auto'",
                              extra={'interface_number': self.interface_number,
                                     'configured_mode': network_mode,
                                     'valid_modes': list(mode_mapping.keys())})
                mode_key = 'auto'

            allowed, preferred = mode_mapping[mode_key]

            logger.info("Configuring network mode",
                       extra={'interface_number': self.interface_number,
                              'network_mode': network_mode,
                              'allowed_mask': allowed,
                              'preferred_mask': preferred})

            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")

            try:
                # Read current modes — MM returns a struct (uu)
                current_modes_variant = await props.call_get(MODEM_INTERFACE, "CurrentModes")
                current_struct = current_modes_variant.value if current_modes_variant else None

                if current_struct and len(current_struct) >= 2:
                    cur_allowed = current_struct[0]
                    cur_preferred = current_struct[1]
                    # Unwrap Variant wrappers if present
                    if hasattr(cur_allowed, 'value'):
                        cur_allowed = cur_allowed.value
                    if hasattr(cur_preferred, 'value'):
                        cur_preferred = cur_preferred.value

                    logger.info("Current modem modes",
                               extra={'interface_number': self.interface_number,
                                      'current_allowed': cur_allowed,
                                      'current_preferred': cur_preferred,
                                      'target_allowed': allowed,
                                      'target_preferred': preferred})

                    if cur_allowed == allowed and cur_preferred == preferred:
                        logger.info("Network mode already configured correctly",
                                   extra={'interface_number': self.interface_number,
                                          'mode': network_mode})
                        return

                # Apply via SetCurrentModes(uu)
                modem_iface = self.proxy.get_interface(MODEM_INTERFACE)
                await modem_iface.call_set_current_modes((allowed, preferred))

                await asyncio.sleep(2)

                logger.info("Network mode configured successfully",
                           extra={'interface_number': self.interface_number,
                                  'mode': network_mode,
                                  'allowed_mask': allowed,
                                  'preferred_mask': preferred})

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

    def _get_band_name_to_constant_mapping(self):
        """Map human-readable band names to ModemManager uint32 constants"""
        # These are the actual MM_MODEM_BAND_* constants from ModemManager source
        return {
            # GSM bands
            'gsm-850': 1,
            'gsm-900': 2,
            'gsm-1800': 3,
            'gsm-1900': 4,

            # UMTS/3G bands
            'umts-1': 5,     # 2100 MHz
            'umts-2': 6,     # 1900 MHz PCS
            'umts-3': 7,     # 1800 MHz DCS
            'umts-4': 8,     # 1700/2100 MHz AWS
            'umts-5': 9,     # 850 MHz
            'umts-6': 10,    # 800 MHz
            'umts-7': 11,    # 2600 MHz
            'umts-8': 12,    # 900 MHz
            'umts-9': 13,    # 1700 MHz
            'umts-10': 14,   # 1700/2100 MHz

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

            # 5G NR/NGRAN bands
            'ngran-1': 128,   # 2100 MHz
            'ngran-2': 129,   # 1900 MHz
            'ngran-3': 130,   # 1800 MHz
            'ngran-5': 132,   # 850 MHz
            'ngran-7': 134,   # 2600 MHz
            'ngran-8': 135,   # 900 MHz
            'ngran-12': 139,  # 700 MHz
            'ngran-20': 147,  # 800 MHz
            'ngran-25': 152,  # 1900 MHz
            'ngran-28': 155,  # 700 MHz
            'ngran-41': 168,  # 2500 MHz
            'ngran-66': 193,  # 1700/2100 MHz
            'ngran-71': 198,  # 600 MHz
            'ngran-77': 204,  # 3700 MHz
            'ngran-78': 205,  # 3500 MHz
            'ngran-79': 206,  # 4700 MHz
        }

    def _band_name_to_mm_constant(self, band_name):
        """Convert human-readable band name to MM constant"""
        mapping = self._get_band_name_to_constant_mapping()
        return mapping.get(band_name.lower().strip())

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

    def _requires_disconnection(self, old_config, new_config):
        """Determine if configuration changes require bearer disconnection"""
        if not old_config:
            return False  # First-time configuration doesn't need disconnection

        # Connection-affecting parameters that require disconnection
        connection_params = [
            'primary_sim_slot',
            'sim_slots',  # APN, auth, roaming changes within sim_slots
            'network_mode'
        ]

        # Check basic connection parameters
        for param in connection_params:
            if old_config.get(param) != new_config.get(param):
                # For sim_slots, check if connection parameters changed
                if param == 'sim_slots':
                    if self._sim_connection_params_changed(old_config.get('sim_slots', []), new_config.get('sim_slots', [])):
                        logger.info("SIM connection parameters changed - disconnection required",
                                   extra={'interface_number': self.interface_number})
                        return True
                else:
                    logger.info(f"Connection parameter '{param}' changed - disconnection required",
                               extra={'interface_number': self.interface_number, 'param': param})
                    return True

        logger.info("Only monitoring/timer parameters changed - no disconnection needed",
                   extra={'interface_number': self.interface_number})
        return False

    def _sim_connection_params_changed(self, old_sim_slots, new_sim_slots):
        """Check if SIM connection parameters (APN, auth, etc.) changed"""
        # Convert to dict by slot for easier comparison
        old_slots = {slot['slot']: slot for slot in old_sim_slots}
        new_slots = {slot['slot']: slot for slot in new_sim_slots}

        # Connection-affecting SIM parameters
        connection_sim_params = ['apn', 'username', 'password', 'auth_type', 'pdp_type', 'roaming']

        for slot_num in set(old_slots.keys()) | set(new_slots.keys()):
            old_slot = old_slots.get(slot_num, {})
            new_slot = new_slots.get(slot_num, {})

            for param in connection_sim_params:
                if old_slot.get(param) != new_slot.get(param):
                    logger.info(f"SIM slot {slot_num} connection parameter '{param}' changed",
                               extra={'interface_number': self.interface_number,
                                      'slot': slot_num, 'param': param,
                                      'old_value': old_slot.get(param),
                                      'new_value': new_slot.get(param)})
                    return True

        return False

    async def _reconfigure_modem(self):
        """Reconfigure modem with new settings"""
        logger.info("Reconfiguring modem",
                   extra={'interface_number': self.interface_number})

        # Check if we need to disconnect for this configuration change
        old_config = getattr(self, '_previous_config', {})
        needs_disconnect = self._requires_disconnection(old_config, self.config)

        if needs_disconnect and self.machine.current_state == ModemState.CONNECTED.value:
            logger.info("Disconnecting for connection parameter changes",
                       extra={'interface_number': self.interface_number})
            await self._disconnect_bearer()

            # Reconfigure connection-affecting parameters
            await self._configure_sim_slot()
            await self._configure_supported_bands()

            # After reconfiguration, attempt reconnection
            logger.info("Reconnecting with updated configuration",
                       extra={'interface_number': self.interface_number})
            await self.apply_modem_configuration()
        else:
            logger.info("Configuration updated without disconnection - only monitoring/timer changes",
                       extra={'interface_number': self.interface_number})
            # For non-connection changes, just update internal state
            # The FSM will continue in its current state with updated parameters

        # Store current config for future comparisons
        self._previous_config = self.config.copy() if self.config else {}

    async def _disconnect_bearer(self):
        """Disconnect the current bearer connection"""
        try:
            if self.bearer_path and self.proxy:
                logger.info("Disconnecting bearer for reconfiguration",
                           extra={'interface_number': self.interface_number,
                                  'bearer_path': self.bearer_path})

                simple_iface = self.proxy.get_interface(SIMPLE_INTERFACE)
                await simple_iface.call_disconnect(self.bearer_path)
                self.bearer_path = None

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
            # 🔧 FIX: Check if bearer is already connected before attempting new connections
            is_already_connected = await self._is_bearer_connected()
            if is_already_connected:
                logger.info("Bearer already connected - transitioning to CONNECTED state instead of creating new connection",
                           extra={'interface_number': self.interface_number})
                # Apply IP configuration from existing bearer
                await self._apply_bearer_ip_configuration()
                # Set interface UP
                await self._ensure_interface_up()
                # Transition to CONNECTED state
                if self.machine.current_state != ModemState.CONNECTED.value:
                    self.transition(ModemEvent.CONNECTED)
                return
            # Get active SIM configuration
            primary_sim_slot = self.config.get('primary_sim_slot', 1)
            sim_slots = self.config.get('sim_slots', [])
            active_sim_config = next((sim for sim in sim_slots if sim['slot'] == primary_sim_slot), {})

            # Get normalized APN configuration
            apn_config = self._normalize_apn_config(active_sim_config.get('apn', ''))

            # 🎯 NEW: Check if user configured an APN
            if apn_config['name']:
                logger.info("Using user-configured APN",
                           extra={'interface_number': self.interface_number,
                                  'apn_name': apn_config['name'],
                                  'has_auth': apn_config['auth_type'] != 'none'})

                # Try user APN directly
                success = await self._try_connection_with_apn(apn_config, active_sim_config)
                if success:
                    return
                else:
                    logger.warning("User-configured APN failed, falling back to auto-discovery",
                                  extra={'interface_number': self.interface_number,
                                         'failed_apn': apn_config['name']})

            # 🎯 NEW: Auto-discovery flow
            logger.info("Starting APN auto-discovery",
                       extra={'interface_number': self.interface_number,
                              'primary_sim_slot': primary_sim_slot,
                              'library_available': APN_LOOKUP_AVAILABLE})

            # Get SIM information for lookup
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
                await self._try_automatic_apn_assignment(active_sim_config)
                return

            # Try each APN candidate in priority order
            await self._try_apn_candidates(apn_candidates, active_sim_config, sim_info)

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
    async def _try_apn_candidates(self, candidates, sim_config, sim_info):
        """Try APN candidates using new ConnectionManager"""
        # Set proxy for connection manager
        self.connection_manager.set_proxy(self.proxy)

        # Use the extracted connection manager
        success = await self.connection_manager.try_apn_candidates(candidates, sim_config, sim_info)

        if success:
            # Update bearer path for backward compatibility
            self.bearer_path = self.connection_manager.get_current_bearer_path()
        else:
            # All candidates failed, try automatic assignment
            logger.warning("All APN candidates failed, trying automatic assignment",
                          extra={'interface_number': self.interface_number,
                                 'total_candidates_tried': len(candidates)})
    async def _try_connection_with_apn(self, apn_config, sim_config):
        """Try connection using new ConnectionManager"""
        # Set proxy for connection manager
        self.connection_manager.set_proxy(self.proxy)

        # Use the extracted connection manager
        success = await self.connection_manager.try_connection_with_apn(apn_config, sim_config)

        if success:
            # Update bearer path for backward compatibility
            self.bearer_path = self.connection_manager.get_current_bearer_path()

        return success

    async def _try_automatic_apn_assignment(self, sim_config):
        """Try automatic APN assignment as last resort"""
        try:
            logger.info("Attempting automatic APN assignment",
                       extra={'interface_number': self.interface_number})

            # Build minimal connection parameters - let network assign APN
            connect_params = {}

            # Only specify IP type and roaming
            pdp_type = sim_config.get('pdp_type', 'ipv4')
            connect_params['ip-type'] = Variant('u', self._convert_pdp_type(pdp_type))

            roaming = sim_config.get('roaming', 'disabled')
            connect_params['allow-roaming'] = Variant('b', roaming == 'enabled')

            # Let ModemManager/network handle APN assignment
            simple_iface = self.proxy.get_interface(SIMPLE_INTERFACE)
            bearer_path = await simple_iface.call_connect(connect_params)
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
                assigned_apn = bearer_properties.get('apn', 'Unknown')

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
        """Try APNs from external discovery service"""
        try:
            # Extract current SIM info if available
            sim_info = await self._get_sim_information()
            if not sim_info:
                logger.warning("No SIM info available for APN discovery",
                              extra={'interface_number': self.interface_number})
                return False

            # Discover APN candidates using Android library
            apn_candidates = await self._discover_apn_candidates(sim_info, sim_config)
            if not apn_candidates:
                logger.warning("No APN candidates discovered",
                              extra={'interface_number': self.interface_number})
                return False

            logger.info(f"Discovered {len(apn_candidates)} APN candidates, attempting connections",
                       extra={'interface_number': self.interface_number})

            # Try each discovered APN
            for apn_data in apn_candidates:
                try:
                    logger.info(f"Trying discovered APN: {apn_data.get('name', 'unknown')}",
                               extra={'interface_number': self.interface_number})

                    # Create APN config for connection attempt
                    apn_config = {
                        'name': apn_data.get('name', ''),
                        'username': apn_data.get('username', ''),
                        'password': apn_data.get('password', ''),
                        'auth_type': apn_data.get('auth_type', 'none'),
                        'pdp_type': apn_data.get('pdp_type', 'ipv4')
                    }

                    # Attempt connection with this APN
                    success = await self._try_connection_with_apn(apn_config, sim_config)
                    if success:
                        logger.info(f"Successfully connected with discovered APN: {apn_config['name']}",
                                   extra={'interface_number': self.interface_number})
                        return True

                except Exception as e:
                    logger.warning(f"Failed to connect with discovered APN {apn_data.get('apn', 'unknown')}: {e}",
                                  extra={'interface_number': self.interface_number})
                    continue

            logger.warning("All discovered APNs failed",
                          extra={'interface_number': self.interface_number})
            return False

        except Exception as e:
            logger.error(f"APN discovery service failed: {e}",
                        extra={'interface_number': self.interface_number})
            return False

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
        sim_slots = self.config.get('sim_slots', []) if self.config else []
        active_slot = self.current_active_sim or self.config.get('primary_sim_slot', 1)
        sim_config = next((s for s in sim_slots if s['slot'] == active_slot), {})

        # Per-SIM values take priority; fall back to global config then defaults
        return {
            'data_limit_size': sim_config.get('data_limit_size',
                                              self.config.get('data_limit_size',
                                                              DEFAULT_DATA_CONFIG['data_limit_size']) if self.config else DEFAULT_DATA_CONFIG['data_limit_size']),
            'data_limit_action': sim_config.get('data_limit_action',
                                                self.config.get('data_limit_action',
                                                                DEFAULT_DATA_CONFIG['data_limit_action']) if self.config else DEFAULT_DATA_CONFIG['data_limit_action']),
            'data_limit_warning': sim_config.get('data_limit_warning',
                                                 self.config.get('data_limit_warning',
                                                                 DEFAULT_DATA_CONFIG['data_limit_warning']) if self.config else list(DEFAULT_DATA_CONFIG['data_limit_warning'])),
            'data_limit_billing_date': sim_config.get('data_limit_billing_date',
                                                      self.config.get('data_limit_billing_date',
                                                                      DEFAULT_DATA_CONFIG['data_limit_billing_date']) if self.config else DEFAULT_DATA_CONFIG['data_limit_billing_date']),
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

        if not data_limit:
            logger.info("No data usage limit configured for active SIM",
                       extra={'interface_number': self.interface_number,
                              'active_sim': self.current_active_sim})
            return

        # Load persisted cumulative usage for this SIM
        cumulative_bytes = self._load_persisted_usage()
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

                            # Check if limit exceeded
                            if total_bytes >= data_limit:
                                if not limit_logged:
                                    limit_logged = True
                                    logger.warning(
                                        "Data usage limit reached",
                                        extra={'interface_number': self.interface_number,
                                               'active_sim': self.current_active_sim,
                                               'usage_gb': total_bytes / (1024*1024*1024),
                                               'limit_gb': data_limit / (1024*1024*1024),
                                               'action': data_action})

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
        """Handle SIM failover triggered by data limit exceeded on current SIM."""
        try:
            if not self._is_sim_failover_enabled():
                logger.warning("Data limit sim-failover requested but sim_failover is globally disabled, disconnecting instead",
                              extra={'interface_number': self.interface_number})
                self.transition(ModemEvent.USAGE_LIMIT_EXCEEDED)
                return

            if not self._is_failover_allowed():
                logger.warning("Data limit failover blocked by cooldown, disconnecting instead",
                              extra={'interface_number': self.interface_number})
                self.transition(ModemEvent.USAGE_LIMIT_EXCEEDED)
                return

            logger.warning("Data limit exceeded - initiating SIM failover",
                          extra={'interface_number': self.interface_number,
                                 'current_sim': self.current_active_sim})

            self.sim_switch_reason = 'data_limit_exceeded'
            fallback_sim = 2 if self.current_active_sim == 1 else 1
            self.target_sim_slot = fallback_sim

            self._record_failover()

            # Emit event for observability
            self._emit_failover_event(
                event_type='data_limit_failover',
                from_sim=self.current_active_sim,
                to_sim=fallback_sim,
                reason='data_limit_exceeded',
                trigger='_handle_data_limit_failover')

            self.transition(ModemEvent.SWITCH_SIM)
            await self._execute_sim_switch()

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

    def _load_persisted_usage(self) -> int:
        """Load cumulative byte count for the current active SIM from disk.

        The file is a JSON dict keyed by SIM slot number, e.g.:
            {"1": {"bytes": 123456789, "billing_date": 1, "last_updated": "..."}, "2": ...}
        Handles billing-cycle resets automatically.
        """
        slot_key = str(self.current_active_sim or self.config.get('primary_sim_slot', 1))
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

        logger.debug(f"Loaded persisted usage for SIM {slot_key}: {stored_bytes / (1024*1024):.1f} MB",
                    extra={'interface_number': self.interface_number})
        return stored_bytes

    def _persist_usage(self, total_bytes: int):
        """Persist cumulative usage for the current active SIM to disk."""
        slot_key = str(self.current_active_sim or self.config.get('primary_sim_slot', 1))
        data_cfg = self._get_active_sim_data_config()
        path = self._usage_file_path()

        # Read existing data
        try:
            with open(path, 'r') as f:
                usage_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, PermissionError):
            usage_data = {}

        # Update this SIM's entry
        usage_data[slot_key] = {
            'bytes': total_bytes,
            'billing_date': data_cfg['data_limit_billing_date'],
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

    async def _check_signal_adequacy_for_reconnection(self):
        """Check if signal strength is adequate for reliable reconnection"""
        try:
            # If enhanced reconnection is disabled, always return True
            if not getattr(self, 'enhanced_reconnection', True):
                return True

            # Use enhanced reconnection configuration
            min_signal_dbm = getattr(self, 'reconnection_signal_threshold', -85)
            buffer_dbm = getattr(self, 'signal_strength_buffer', 5)
            effective_threshold = min_signal_dbm - buffer_dbm

            signal_percent, signal_dbm = await self._get_detailed_signal_quality()

            if signal_percent is None or signal_dbm is None:
                logger.warning("Cannot read signal strength - assuming adequate for reconnection",
                              extra={'interface_number': self.interface_number})
                return True

            adequate = signal_dbm >= effective_threshold

            logger.info("Enhanced signal adequacy check for reconnection",
                       extra={'interface_number': self.interface_number,
                              'signal_percent': signal_percent,
                              'signal_dbm': signal_dbm,
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
        """Get detailed signal quality metrics using actual dBm readings"""
        try:
            if not self.proxy:
                return None, None

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
            try:
                # Get LTE signal metrics from Signal interface
                lte_signal_variant = await props.call_get("org.freedesktop.ModemManager1.Modem.Signal", "Lte")
                if lte_signal_variant and lte_signal_variant.value:
                    lte_signals = lte_signal_variant.value

                    # Try RSSI first (most common)
                    if 'rssi' in lte_signals:
                        signal_dbm = lte_signals['rssi'].value
                        logger.debug(f"Got RSSI signal: {signal_dbm} dBm",
                                   extra={'interface_number': self.interface_number})
                    # Fall back to RSRP for LTE
                    elif 'rsrp' in lte_signals:
                        signal_dbm = lte_signals['rsrp'].value
                        logger.debug(f"Got RSRP signal: {signal_dbm} dBm",
                                   extra={'interface_number': self.interface_number})

                # Try other technologies if LTE not available
                if signal_dbm is None:
                    # Try 5G NR signals first (most modern)
                    try:
                        nr5g_signal_variant = await props.call_get("org.freedesktop.ModemManager1.Modem.Signal", "Nr5g")
                        if nr5g_signal_variant and nr5g_signal_variant.value:
                            nr5g_signals = nr5g_signal_variant.value
                            # 5G typically uses RSRP as primary metric
                            if 'rsrp' in nr5g_signals:
                                signal_dbm = nr5g_signals['rsrp'].value
                                logger.debug(f"Got 5G NR RSRP signal: {signal_dbm} dBm",
                                           extra={'interface_number': self.interface_number})
                            elif 'rssi' in nr5g_signals:
                                signal_dbm = nr5g_signals['rssi'].value
                                logger.debug(f"Got 5G NR RSSI signal: {signal_dbm} dBm",
                                           extra={'interface_number': self.interface_number})
                    except Exception:
                        pass

                    # Try UMTS signals (3G)
                    if signal_dbm is None:
                        try:
                            umts_signal_variant = await props.call_get("org.freedesktop.ModemManager1.Modem.Signal", "Umts")
                            if umts_signal_variant and umts_signal_variant.value:
                                umts_signals = umts_signal_variant.value
                                if 'rssi' in umts_signals:
                                    signal_dbm = umts_signals['rssi'].value
                                    logger.debug(f"Got UMTS (3G) RSSI signal: {signal_dbm} dBm",
                                               extra={'interface_number': self.interface_number})
                                elif 'rscp' in umts_signals:
                                    signal_dbm = umts_signals['rscp'].value
                                    logger.debug(f"Got UMTS (3G) RSCP signal: {signal_dbm} dBm",
                                               extra={'interface_number': self.interface_number})
                        except Exception:
                            pass

                    # Try GSM signals (2G)
                    if signal_dbm is None:
                        try:
                            gsm_signal_variant = await props.call_get("org.freedesktop.ModemManager1.Modem.Signal", "Gsm")
                            if gsm_signal_variant and gsm_signal_variant.value:
                                gsm_signals = gsm_signal_variant.value
                                if 'rssi' in gsm_signals:
                                    signal_dbm = gsm_signals['rssi'].value
                                    logger.debug(f"Got GSM (2G) RSSI signal: {signal_dbm} dBm",
                                               extra={'interface_number': self.interface_number})
                        except Exception:
                            pass

                    # Try CDMA signals (2G CDMA)
                    if signal_dbm is None:
                        try:
                            cdma_signal_variant = await props.call_get("org.freedesktop.ModemManager1.Modem.Signal", "Cdma")
                            if cdma_signal_variant and cdma_signal_variant.value:
                                cdma_signals = cdma_signal_variant.value
                                if 'rssi' in cdma_signals:
                                    signal_dbm = cdma_signals['rssi'].value
                                    logger.debug(f"Got CDMA (2G) RSSI signal: {signal_dbm} dBm",
                                               extra={'interface_number': self.interface_number})
                        except Exception:
                            pass

                    # Try EVDO signals (3G CDMA)
                    if signal_dbm is None:
                        try:
                            evdo_signal_variant = await props.call_get("org.freedesktop.ModemManager1.Modem.Signal", "Evdo")
                            if evdo_signal_variant and evdo_signal_variant.value:
                                evdo_signals = evdo_signal_variant.value
                                if 'rssi' in evdo_signals:
                                    signal_dbm = evdo_signals['rssi'].value
                                    logger.debug(f"Got EVDO (3G CDMA) RSSI signal: {signal_dbm} dBm",
                                               extra={'interface_number': self.interface_number})
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

            return signal_percent, signal_dbm

        except Exception as e:
            logger.error(f"Failed to get detailed signal quality: {e}",
                        extra={'interface_number': self.interface_number})
            return None, None

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

        # ── 4. Modem hardware information ────────────────────────────────
        try:
            if self.proxy:
                props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
                mfr_v = await props.call_get(MODEM_INTERFACE, "Manufacturer")
                status['modem_manufacturer'] = mfr_v.value if mfr_v else ''
                model_v = await props.call_get(MODEM_INTERFACE, "Model")
                status['modem_model'] = model_v.value if model_v else ''
                equip_v = await props.call_get(MODEM_INTERFACE, "EquipmentIdentifier")
                status['modem_imei'] = equip_v.value if equip_v else ''
                rev_v = await props.call_get(MODEM_INTERFACE, "Revision")
                status['modem_firmware'] = rev_v.value if rev_v else ''
                device_v = await props.call_get(MODEM_INTERFACE, "Device")
                status['modem_device'] = device_v.value if device_v else ''
        except Exception:
            for k in ('modem_manufacturer', 'modem_model', 'modem_imei',
                      'modem_firmware', 'modem_device'):
                status.setdefault(k, '')

        # ── 5. Registration / access technology ──────────────────────────
        try:
            if self.proxy:
                props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
                # Modem numeric state
                state_v = await props.call_get(MODEM_INTERFACE, "State")
                status['modem_state'] = state_v.value if state_v else -1
                # Access technologies bitmask
                at_v = await props.call_get(MODEM_INTERFACE, "AccessTechnologies")
                status['access_technologies'] = at_v.value if at_v else 0
                status['access_technology_name'] = self._access_tech_to_string(
                    status['access_technologies'])
                # 3GPP operator name and registration state
                try:
                    gpp_iface = "org.freedesktop.ModemManager1.Modem.Modem3gpp"
                    op_v = await props.call_get(gpp_iface, "OperatorName")
                    status['operator_name'] = op_v.value if op_v else ''
                    reg_v = await props.call_get(gpp_iface, "RegistrationState")
                    status['registration_state'] = reg_v.value if reg_v else 0
                    op_code_v = await props.call_get(gpp_iface, "OperatorCode")
                    status['operator_code'] = op_code_v.value if op_code_v else ''
                except Exception:
                    status.setdefault('operator_name', '')
                    status.setdefault('registration_state', 0)
                    status.setdefault('operator_code', '')
        except Exception:
            for k in ('modem_state', 'access_technologies',
                      'access_technology_name', 'operator_name',
                      'registration_state', 'operator_code'):
                status.setdefault(k, '')

        # ── 6. Signal quality ────────────────────────────────────────────
        try:
            signal_pct, signal_dbm = await self._get_detailed_signal_quality()
            status['signal_percent'] = signal_pct or 0
            status['signal_dbm'] = signal_dbm or 0
        except Exception:
            status['signal_percent'] = 0
            status['signal_dbm'] = 0

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

        # MTU override / fallback config summary
        if self.config:
            mtu_override = self.config.get('mtu_override', 0)
            mtu_fallback = self.config.get('mtu_fallback', 1500)
            network_mtu = status.get('mtu', '')
            if mtu_override and mtu_override > 0:
                status['mtu_effective'] = str(mtu_override)
                status['mtu_source'] = 'override'
            elif network_mtu:
                status['mtu_effective'] = str(network_mtu)
                status['mtu_source'] = 'network'
            elif mtu_fallback and mtu_fallback > 0:
                status['mtu_effective'] = str(mtu_fallback)
                status['mtu_source'] = 'fallback'
            else:
                status['mtu_effective'] = ''
                status['mtu_source'] = 'none'
            status['mtu_override'] = mtu_override
            status['mtu_fallback'] = mtu_fallback
        else:
            for k in ('mtu_effective', 'mtu_source', 'mtu_override', 'mtu_fallback'):
                status[k] = ''

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
            cumulative = self._load_persisted_usage()
            status['cumulative_bytes'] = cumulative
            status['cumulative_plus_session'] = cumulative + status.get('session_total_bytes', 0)
            data_cfg = self._get_active_sim_data_config()
            status['data_limit_bytes'] = data_cfg.get('data_limit_size', 0)
            status['data_limit_action'] = data_cfg.get('data_limit_action', 'none')
            status['data_limit_warning'] = data_cfg.get('data_limit_warning', [])
            status['data_limit_billing_date'] = data_cfg.get('data_limit_billing_date', 1)
            limit = status['data_limit_bytes']
            total = status['cumulative_plus_session']
            status['data_usage_percent'] = round((total / limit) * 100, 1) if limit > 0 else 0.0
        except Exception:
            for k in ('cumulative_bytes', 'cumulative_plus_session',
                      'data_limit_bytes', 'data_limit_action',
                      'data_limit_billing_date',
                      'data_usage_percent'):
                status.setdefault(k, 0)
            status.setdefault('data_limit_warning', [])

        # ── 10. Failover / recovery stats ────────────────────────────────
        status['failover_count'] = self.failover_count
        status['last_failover_time'] = (
            datetime.datetime.fromtimestamp(self.last_failover_time).isoformat()
            if self.last_failover_time else ''
        )
        status['connectivity_recovery_attempts'] = self.connectivity_recovery_attempts
        status['hardware_reset_in_progress'] = self.reset_operation_in_progress
        status['last_hardware_reset_time'] = (
            datetime.datetime.fromtimestamp(self.last_reset_time).isoformat()
            if self.last_reset_time else ''
        )

        # ── 11. SIM slot details from config + physical SIM identity ────
        if self.config:
            sim_slots = self.config.get('sim_slots', [])
            for i, slot in enumerate(sim_slots):
                slot_num = i + 1
                prefix = f"sim_slot_{slot_num}"
                # Config
                status[f"{prefix}_enabled"] = slot.get('enabled', True)
                status[f"{prefix}_roaming"] = slot.get('roaming', 'disabled')
                status[f"{prefix}_pdp_type"] = slot.get('pdp_type', 'ipv4')
                status[f"{prefix}_apn"] = slot.get('apn', {}).get('name', '')
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
            status['android_apn_discovery'] = self.config.get('android_apn_discovery', 'disabled')
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
            import time
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
            status['verbose_logging'] = self.config.get('verbose_logging', False)

        # ── 13. Network scan results (if available) ──────────────────────
        if self.last_scan_results:
            status['available_networks'] = self.last_scan_results

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

        # Reset to scanning state
        self.machine.current_state = ModemState.INITIAL.value
        await self.initialize()

    async def shutdown(self):
        """Graceful shutdown of the FSM"""
        logger.info("Shutting down FSM",
                   extra={'interface_number': self.interface_number})

        # Cancel usage monitoring
        if self.usage_monitor_task:
            self.usage_monitor_task.cancel()
            self.usage_monitor_task = None

        # Disconnect if connected
        if (self.machine.current_state == ModemState.CONNECTED.value and
            self.bearer_path and self.proxy):
            try:
                simple_iface = self.proxy.get_interface(SIMPLE_INTERFACE)
                await simple_iface.call_disconnect(self.bearer_path)
                logger.info("Modem disconnected during shutdown",
                           extra={'interface_number': self.interface_number})
            except Exception as e:
                logger.error(f"Error disconnecting during shutdown: {e}",
                           extra={'interface_number': self.interface_number})

        # Remove from global registry
        ModemStateMachine.modem_state_machines.pop(f"wwan{self.interface_number}", None)

        logger.info("FSM shutdown complete",
                   extra={'interface_number': self.interface_number})

    async def handle_disconnection_recovery(self):
        """Handle automatic reconnection after network disconnection"""
        try:
            logger.info("Network disconnection detected, starting recovery",
                       extra={'interface_number': self.interface_number,
                              'current_state': self.machine.current_state})

            # Don't auto-recover if user requested disconnect
            if self.user_disconnected:
                logger.info("User-initiated disconnect detected, skipping auto-recovery",
                           extra={'interface_number': self.interface_number})
                return

            # Clear bearer path since connection is gone
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
                    logger.info("Modem automatically reconnected",
                               extra={'interface_number': self.interface_number})
                    # ModemManager will trigger handle_modem_event with state 11
                    return

                elif mm_state == 8:  # REGISTERED but not connected
                    logger.info("Modem registered, attempting enhanced reconnection",
                               extra={'interface_number': self.interface_number})
                    # Use enhanced reconnection strategy for better reliability
                    if self.enhanced_reconnection:
                        success = await self._enhanced_reconnection_attempt()
                        if not success:
                            logger.warning("Enhanced reconnection failed, falling back to standard",
                                         extra={'interface_number': self.interface_number})
                            await self.apply_modem_configuration()
                    else:
                        await self.apply_modem_configuration()

                elif mm_state in [6, 7]:  # ENABLED or SEARCHING
                    logger.info("Modem searching for network, will use enhanced reconnection when ready",
                               extra={'interface_number': self.interface_number})
                    # Wait for automatic registration, then enhanced reconnection will take over

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

                    # Log successful test (debug level to avoid spam)
                    logger.debug("Connectivity test passed",
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

                    logger.debug(f"Testing {ip_family} connectivity",
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
                            logger.debug(f"{ip_family} connectivity test successful",
                                       extra={'interface_number': self.interface_number,
                                              'target': target,
                                              'attempt': attempt + 1})
                            return True  # Success on first working target
                        else:
                            logger.debug(f"{ip_family} ping failed",
                                       extra={'interface_number': self.interface_number,
                                              'target': target,
                                              'attempt': attempt + 1,
                                              'returncode': process.returncode,
                                              'stderr': stderr.decode()[:200]})

                    except asyncio.TimeoutError:
                        logger.debug(f"{ip_family} ping timed out",
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

                # Set up failover metadata
                self.sim_switch_reason = 'connectivity_failure_escalation'
                fallback_sim = 2 if self.current_active_sim == 1 else 1
                self.target_sim_slot = fallback_sim

                self._record_failover()
                self._emit_failover_event(
                    event_type='failover',
                    from_sim=self.current_active_sim,
                    to_sim=fallback_sim,
                    reason='connectivity_failure_escalation',
                    trigger='_trigger_connectivity_recovery',
                    extra_data={'recovery_attempts': self.connectivity_recovery_attempts})

                # FSM: CONNECTED → SIM_SWITCHING; _execute_sim_switch handles
                # bearer disconnect, task teardown, and the full switch sequence.
                self.transition(ModemEvent.SWITCH_SIM)
                await self._execute_sim_switch()
                return

            # Normal recovery: use the standard disconnect → recovery path.
            # handle_disconnection_recovery already cancels monitoring tasks,
            # clears the bearer, and attempts reconnection.
            self.transition(ModemEvent.DISCONNECT)
            await self.handle_disconnection_recovery()

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
            import time
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
                        logger.warning("📡⚠️ Network registration lost but bearer still connected - starting registration recovery timer",
                                     extra={'interface_number': self.interface_number,
                                            'registration_state': f"{reg_state} ({reg_state_name})",
                                            'bearer_connected': bearer_connected,
                                            'recovery_timer_seconds': 30,
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
            # Wait 30 seconds for registration to recover
            await asyncio.sleep(30)

            # Check if registration has recovered
            current_reg_state = getattr(self, '_last_registration_state', None)
            if current_reg_state in {0, 2, 3, 4}:  # Still disconnected
                logger.warning("📡⏰ Registration recovery timeout - bringing interface DOWN",
                             extra={'interface_number': self.interface_number,
                                    'final_registration_state': current_reg_state,
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

        Follows the same pattern as _handle_data_limit_failover: check cooldown,
        set switch reason, record the event, and trigger the SIM switch.
        """
        try:
            if not self._is_failover_allowed():
                logger.warning("Registration flap failover blocked by cooldown — skipping",
                              extra={'interface_number': self.interface_number,
                                     'reason': reason})
                return

            fallback_sim = 2 if self.current_active_sim == 1 else 1
            logger.warning(f"📡🔀 Initiating SIM failover SIM{self.current_active_sim}→SIM{fallback_sim} "
                          f"(reason: {reason})",
                          extra={'interface_number': self.interface_number,
                                 'from_sim': self.current_active_sim,
                                 'to_sim': fallback_sim,
                                 'reason': reason})

            self.sim_switch_reason = reason
            self.target_sim_slot = fallback_sim

            self._record_failover()
            self._emit_failover_event(
                event_type='registration_flap_failover',
                from_sim=self.current_active_sim,
                to_sim=fallback_sim,
                reason=reason,
                trigger='_initiate_sim_failover')

            self.transition(ModemEvent.SWITCH_SIM)
            await self._execute_sim_switch()

        except Exception as e:
            logger.error(f"Registration flap failover failed: {e}",
                        extra={'interface_number': self.interface_number,
                               'reason': reason})
            self.transition(ModemEvent.CONNECTION_FAILED)

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
        """Handle bearer disconnect with configurable delay"""
        try:
            # Start disconnect timer
            self._bearer_disconnect_timer = self._safe_create_task(
                asyncio.sleep(self.bearer_disconnect_delay)
            )

            await self._bearer_disconnect_timer

            # Timer expired without cancellation - notify Linux of link down
            logger.warning("Bearer disconnect timer expired - setting interface DOWN",
                          extra={'interface_number': self.interface_number,
                                 'delay': self.bearer_disconnect_delay})
            await self._set_interface_down()

            # Clear timer
            self._bearer_disconnect_timer = None

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
        """Handle IP address mismatch between bearer and interface with interface cycling"""
        try:
            logger.warning("🔧 Handling IP mismatch - bearer vs interface",
                          extra={'interface_number': self.interface_number,
                                 'bearer_ips': bearer_ips,
                                 'interface_ips': interface_ips,
                                 'action': 'interface_cycle_for_ip_fix',
                                 'delay': self.ip_change_delay})

            # Interface down/up cycle to synchronize with bearer configuration
            await self._set_interface_down()
            await asyncio.sleep(self.ip_change_delay * 2 / 1000)  # Longer delay for IP sync
            await self._set_interface_up()

            # Wait a bit for DHCP/configuration to complete
            await asyncio.sleep(5)

            # Verify fix
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

    async def _apply_bearer_ip_configuration(self):
        """Apply bearer IP configuration to the interface (VyOS responsibility)"""
        try:
            if not hasattr(self, 'bearer_path') or not self.bearer_path:
                logger.warning("No bearer path available for IP configuration",
                             extra={'interface_number': self.interface_number})
                return

            # Get bearer IP configuration from ModemManager
            bearer_ips = await self._get_bearer_expected_ips()
            if not bearer_ips:
                logger.warning("No IP configuration available from bearer",
                             extra={'interface_number': self.interface_number})
                return

            interface_name = f"wwan{self.interface_number}"

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

            # Clear existing IP addresses to avoid conflicts (except link-local)
            await self._clear_interface_addresses(interface_name)

            # Apply IPv4 configuration
            if bearer_ips.get('ipv4'):
                ipv4_addr = bearer_ips['ipv4']
                ipv4_prefix = bearer_ips.get('ipv4_prefix', '30')  # Default /30 for PtP
                ipv4_gateway = bearer_ips.get('ipv4_gateway')
                ipv4_dns = bearer_ips.get('ipv4_dns', [])
                ipv4_mtu = bearer_ips.get('ipv4_mtu')

                logger.info(f"Applying IPv4 configuration: {ipv4_addr}/{ipv4_prefix}",
                           extra={'interface_number': self.interface_number,
                                  'gateway': ipv4_gateway,
                                  'dns_servers': ipv4_dns,
                                  'mtu': ipv4_mtu})

                # Add IPv4 address
                result = await asyncio.create_subprocess_exec(
                    'ip', 'addr', 'add', f"{ipv4_addr}/{ipv4_prefix}", 'dev', interface_name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await result.communicate()

                if result.returncode != 0 and b'exists' not in stderr:
                    logger.warning(f"Failed to add IPv4 address: {stderr.decode()}",
                                 extra={'interface_number': self.interface_number})

                # Set MTU — priority: mtu_override > network-provided > mtu_fallback
                mtu_override = self.config.get('mtu_override', 0) if self.config else 0
                mtu_fallback = self.config.get('mtu_fallback', 1420) if self.config else 1420

                if mtu_override and mtu_override > 0:
                    effective_mtu = str(mtu_override)
                    mtu_source = 'override'
                elif ipv4_mtu:
                    effective_mtu = ipv4_mtu
                    mtu_source = 'network'
                elif mtu_fallback and mtu_fallback > 0:
                    effective_mtu = str(mtu_fallback)
                    mtu_source = 'fallback'
                else:
                    effective_mtu = None
                    mtu_source = 'none'

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

                # Add IPv4 default route if gateway provided
                if ipv4_gateway:
                    result = await asyncio.create_subprocess_exec(
                        'ip', 'route', 'add', 'default', 'via', ipv4_gateway, 'dev', interface_name,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await result.communicate()

                    if result.returncode != 0 and b'exists' not in stderr:
                        logger.warning(f"IPv4 default route via {ipv4_gateway} failed: {stderr.decode().strip()}",
                                      extra={'interface_number': self.interface_number})
                        # Retry with 'onlink' flag - tells kernel gateway is directly reachable
                        # This is standard for cellular PtP links where nexthop validation fails
                        logger.info("Retrying IPv4 route with onlink flag",
                                   extra={'interface_number': self.interface_number})
                        result = await asyncio.create_subprocess_exec(
                            'ip', 'route', 'add', 'default', 'via', ipv4_gateway, 'dev', interface_name, 'onlink',
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        stdout, stderr = await result.communicate()
                        if result.returncode == 0 or b'exists' in stderr:
                            logger.info(f"IPv4 default route added via {ipv4_gateway} dev {interface_name} (onlink)",
                                       extra={'interface_number': self.interface_number})
                        else:
                            logger.warning(f"IPv4 onlink route also failed: {stderr.decode().strip()}",
                                          extra={'interface_number': self.interface_number})
                            # Final fallback: device-only default route
                            result = await asyncio.create_subprocess_exec(
                                'ip', 'route', 'add', 'default', 'dev', interface_name,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE
                            )
                            stdout, stderr = await result.communicate()
                            if result.returncode == 0 or b'exists' in stderr:
                                logger.info(f"IPv4 default route added via device {interface_name} (device-only fallback)",
                                           extra={'interface_number': self.interface_number})
                            else:
                                logger.error(f"All IPv4 route attempts failed: {stderr.decode().strip()}",
                                            extra={'interface_number': self.interface_number})
                    else:
                        logger.info(f"IPv4 default route added via {ipv4_gateway} dev {interface_name}",
                                   extra={'interface_number': self.interface_number})
                else:
                    # No gateway from carrier - add device-only default route
                    logger.info("No IPv4 gateway from carrier, adding device route",
                               extra={'interface_number': self.interface_number})
                    result = await asyncio.create_subprocess_exec(
                        'ip', 'route', 'add', 'default', 'dev', interface_name,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await result.communicate()
                    if result.returncode == 0 or b'exists' in stderr:
                        logger.info(f"IPv4 default route added via device {interface_name}",
                                   extra={'interface_number': self.interface_number})
                    else:
                        logger.warning(f"IPv4 device route failed: {stderr.decode().strip()}",
                                      extra={'interface_number': self.interface_number})

            # Apply IPv6 configuration
            if bearer_ips.get('ipv6'):
                ipv6_addr = bearer_ips['ipv6']
                ipv6_prefix = bearer_ips.get('ipv6_prefix', '64')  # Default /64
                ipv6_gateway = bearer_ips.get('ipv6_gateway')
                ipv6_dns = bearer_ips.get('ipv6_dns', [])
                ipv6_mtu = bearer_ips.get('ipv6_mtu')

                logger.info(f"Applying IPv6 configuration: {ipv6_addr}/{ipv6_prefix}",
                           extra={'interface_number': self.interface_number,
                                  'gateway': ipv6_gateway,
                                  'dns_servers': ipv6_dns,
                                  'mtu': ipv6_mtu})

                # Add IPv6 address (carrier-assigned)
                result = await asyncio.create_subprocess_exec(
                    'ip', '-6', 'addr', 'add', f"{ipv6_addr}/{ipv6_prefix}", 'dev', interface_name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await result.communicate()

                if result.returncode != 0 and b'exists' not in stderr:
                    logger.warning(f"Failed to add IPv6 address: {stderr.decode()}",
                                 extra={'interface_number': self.interface_number})

                # Add IPv6 default route if gateway provided
                if ipv6_gateway:
                    result = await asyncio.create_subprocess_exec(
                        'ip', '-6', 'route', 'add', 'default', 'via', ipv6_gateway, 'dev', interface_name,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await result.communicate()

                    if result.returncode != 0 and b'exists' not in stderr:
                        logger.warning(f"IPv6 default route via {ipv6_gateway} failed: {stderr.decode().strip()}",
                                      extra={'interface_number': self.interface_number})
                        # Retry with 'onlink' flag
                        logger.info("Retrying IPv6 route with onlink flag",
                                   extra={'interface_number': self.interface_number})
                        result = await asyncio.create_subprocess_exec(
                            'ip', '-6', 'route', 'add', 'default', 'via', ipv6_gateway, 'dev', interface_name, 'onlink',
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        stdout, stderr = await result.communicate()
                        if result.returncode == 0 or b'exists' in stderr:
                            logger.info(f"IPv6 default route added via {ipv6_gateway} dev {interface_name} (onlink)",
                                       extra={'interface_number': self.interface_number})
                        else:
                            logger.warning(f"IPv6 onlink route also failed: {stderr.decode().strip()}",
                                          extra={'interface_number': self.interface_number})
                            # Final fallback: device-only default route
                            result = await asyncio.create_subprocess_exec(
                                'ip', '-6', 'route', 'add', 'default', 'dev', interface_name,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE
                            )
                            stdout, stderr = await result.communicate()
                            if result.returncode == 0 or b'exists' in stderr:
                                logger.info(f"IPv6 default route added via device {interface_name} (device-only fallback)",
                                           extra={'interface_number': self.interface_number})
                            else:
                                logger.error(f"All IPv6 route attempts failed: {stderr.decode().strip()}",
                                            extra={'interface_number': self.interface_number})
                    else:
                        logger.info(f"IPv6 default route added via {ipv6_gateway} dev {interface_name}",
                                   extra={'interface_number': self.interface_number})
                else:
                    # No gateway from carrier - add device-only default route
                    logger.info("No IPv6 gateway from carrier, adding device route",
                               extra={'interface_number': self.interface_number})
                    result = await asyncio.create_subprocess_exec(
                        'ip', '-6', 'route', 'add', 'default', 'dev', interface_name,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await result.communicate()
                    if result.returncode == 0 or b'exists' in stderr:
                        logger.info(f"IPv6 default route added via device {interface_name}",
                                   extra={'interface_number': self.interface_number})
                    else:
                        logger.warning(f"IPv6 device route failed: {stderr.decode().strip()}",
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

        except Exception as e:
            logger.error(f"Failed to apply bearer IP configuration: {e}",
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
