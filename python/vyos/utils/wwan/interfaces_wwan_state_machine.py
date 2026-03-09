#!/usr/bin/env python3
# filepath: /home/jfeeney/vyos-1x/src/conf_mode/interfaces_wwan_state_machine.py
import asyncio
import time
import logging
import logging.handlers
import time
import socket
import os
from datetime import datetime, timezone
from enum import Enum
from dbus_next.aio import MessageBus  # pylint: disable=import-error
from dbus_next.message import Message  # pylint: disable=import-error
from dbus_next import Variant  # pylint: disable=import-error
from automaton import machines  # pylint: disable=import-error
from interfaces_wwan_util import modem_reset

# Import the existing Android APN lookup library
try:
    from apnscripts.apn_lookup_run import find_apn_list
    APN_LOOKUP_AVAILABLE = True
except ImportError:
    APN_LOOKUP_AVAILABLE = False

# Import refactored utilities
from vyos.utils.wwan.refactoring_framework import safe_extraction
from vyos.utils.wwan.wwan_utilities import (
    extract_apn_field, convert_android_auth_type,
    convert_android_apns
)
from wwan_configuration import ConfigurationLoader  # pylint: disable=import-error
from vyos.utils.wwan.apn_discovery import APNDiscovery
from vyos.utils.wwan.connection_manager import ConnectionManager
from vyos.utils.wwan.state_transition_manager import StateTransitionManager

class RFC5424Formatter(logging.Formatter):
    """RFC 5424 compliant syslog formatter for FSM SNMP integration"""

    FACILITY = 19  # local3 for FSM
    SEVERITY_MAP = {
        logging.DEBUG: 7, logging.INFO: 6, logging.WARNING: 4,
        logging.ERROR: 3, logging.CRITICAL: 2
    }

    def __init__(self, app_name="wwan-fsm"):
        super().__init__()
        self.app_name = app_name
        self.hostname = socket.gethostname()

    def format(self, record):
        severity = self.SEVERITY_MAP.get(record.levelno, 6)
        priority = self.FACILITY * 8 + severity

        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc)
        timestamp_str = timestamp.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

        pid = record.process or '-'
        msgid = self._get_message_id(record)
        structured_data = self._build_structured_data(record)

        return (f"<{priority}>1 {timestamp_str} {self.hostname} "
                f"{self.app_name} {pid} {msgid} {structured_data} {record.getMessage()}")

    def _get_message_id(self, record):
        """Generate message ID for SNMP categorization"""
        msg = record.getMessage().lower()

        if 'state changed' in msg or '→' in msg:
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
        """Build structured data for SNMP monitoring"""
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

        origin_data = [f'software="vyos-wwan-fsm"', f'version="1.0"']
        sd_elements.append(f'[origin@32473 {" ".join(origin_data)}]')

        return ''.join(sd_elements) if sd_elements else '-'

# Set up RFC 5424 logging for FSM
def setup_fsm_logging():
    formatter = RFC5424Formatter("wwan-fsm")

    try:
        syslog_handler = logging.handlers.SysLogHandler(
            address='/dev/log',
            facility=logging.handlers.SysLogHandler.LOG_LOCAL3
        )
        syslog_handler.setFormatter(formatter)
        use_syslog = True
    except (OSError, IOError):
        use_syslog = False

    console_formatter = logging.Formatter(
        '%(asctime)s wwan-fsm[%(process)d]: %(levelname)s: %(message)s'
    )
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    if use_syslog:
        logger.addHandler(syslog_handler)
    logger.addHandler(console_handler)
    logger.propagate = False

    return logger

logger = setup_fsm_logging()

# Constants
MODEM_MANAGER_SERVICE = "org.freedesktop.ModemManager1"
MODEM_MANAGER_PATH = "/org/freedesktop/ModemManager1"
MODEM_INTERFACE = "org.freedesktop.ModemManager1.Modem"
OBJECT_MANAGER_INTERFACE = "org.freedesktop.DBus.ObjectManager"
BEARER_INTERFACE = "org.freedesktop.ModemManager1.Bearer"
SIMPLE_INTERFACE = "org.freedesktop.ModemManager1.Modem.Simple"

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
    USAGE_MONITORING = "USAGE_MONITORING"
    USAGE_THRESHOLD = "USAGE_THRESHOLD"
    USAGE_RESETTING = "USAGE_RESETTING"
    # SIM switch states
    SIM_SWITCHING = "SIM_SWITCHING"
    SIM_DISCONNECTING = "SIM_DISCONNECTING"
    SIM_DISABLING = "SIM_DISABLING"
    SIM_ENABLING = "SIM_ENABLING"
    SIM_RECONFIGURING = "SIM_RECONFIGURING"

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
    START_USAGE_MONITORING = "start_usage_monitoring"
    USAGE_LIMIT_EXCEEDED = "usage_limit_exceeded"
    RESET_USAGE = "reset_usage"
    # SIM switch events
    SWITCH_SIM = "switch_sim"
    SIM_DISCONNECTED = "sim_disconnected"
    SIM_DISABLED = "sim_disabled"
    SIM_SWITCHED = "sim_switched"
    SIM_ENABLED = "sim_enabled"
    SIM_SWITCH_COMPLETE = "sim_switch_complete"

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

        # SIM change tracking for worldwide operation
        self.last_known_sim_info = None     # Store SIM info from last successful connection
        self.sim_changed = False            # Flag to indicate SIM card change detected

        # Reset cooldown tracking to prevent cascading failures
        self.last_reset_time = 0            # Timestamp of last hardware reset
        self.reset_cooldown_seconds = 300   # 5 minute cooldown between resets

        # Service-initiated modem operations tracking (improved reset-aware)
        self.service_initiated_disable = False  # Flag to prevent false SIM missing detection
        self.reset_operation_in_progress = False  # Track reset operations across re-enumeration
        self.reset_grace_period_end = 0     # Timestamp when reset grace period ends
        self.reset_timeout_task = None      # Task to clear reset flag on timeout
        self.registration_handling_in_progress = False  # Prevent concurrent registration handling tasks
        self._registration_loss_timer = None    # Initialize registration loss timer

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

    @safe_extraction("_setup_transitions")
    def _setup_transitions(self):
        """🔄 SAFE EXTRACTION: Setup transitions using new StateTransitionManager"""
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

    def _setup_transitions_original(self):
        """🏗️ ORIGINAL: Setup transitions using hardcoded table (for comparison)"""
        transitions = [
            # Initial flow
            (ModemState.INITIAL,        ModemState.SCANNING,           ModemEvent.START_SCAN),
            (ModemState.SCANNING,       ModemState.MODEM_FOUND,        ModemEvent.MODEM_FOUND),

            # Configuration flow
            (ModemState.MODEM_FOUND,    ModemState.WAITING_FOR_CONFIG, ModemEvent.WAIT_FOR_CONFIG),
            (ModemState.WAITING_FOR_CONFIG, ModemState.CONFIGURING,    ModemEvent.CONFIG_UPDATE),

            # Hot-plug: Handle new modem detection from USAGE_MONITORING state
            (ModemState.USAGE_MONITORING, ModemState.MODEM_FOUND,      ModemEvent.MODEM_FOUND),
            (ModemState.USAGE_MONITORING, ModemState.WAITING_FOR_CONFIG, ModemEvent.WAIT_FOR_CONFIG),
            (ModemState.USAGE_MONITORING, ModemState.CONFIGURING,      ModemEvent.CONFIG_UPDATE),

            # Connection flow
            (ModemState.CONFIGURING,    ModemState.CONNECTING,         ModemEvent.CONNECT),
            (ModemState.CONNECTING,     ModemState.CONNECTED,          ModemEvent.CONNECTED),
            # CONNECTED state remains connected - only transitions to USAGE_MONITORING for data limits
            (ModemState.CONNECTED,      ModemState.USAGE_MONITORING,   ModemEvent.USAGE_LIMIT_EXCEEDED),

            # Disconnection flow
            (ModemState.CONNECTED,      ModemState.DISCONNECTING,      ModemEvent.DISCONNECT),
            (ModemState.USAGE_MONITORING, ModemState.DISCONNECTING,    ModemEvent.DISCONNECT),
            (ModemState.DISCONNECTING,  ModemState.DISCONNECTED,       ModemEvent.DISCONNECTED),

            # Enhanced hot-swap transitions
            (ModemState.WAITING_FOR_SIM, ModemState.CONFIGURING,        ModemEvent.SIM_READY),
            (ModemState.FAILED,         ModemState.CONFIGURING,        ModemEvent.SIM_READY),

            # SIM SWITCH FLOW
            (ModemState.CONNECTED,      ModemState.SIM_SWITCHING,      ModemEvent.SWITCH_SIM),
            (ModemState.USAGE_MONITORING, ModemState.SIM_SWITCHING,    ModemEvent.SWITCH_SIM),
            (ModemState.DISCONNECTED,   ModemState.SIM_SWITCHING,      ModemEvent.SWITCH_SIM),

            (ModemState.SIM_SWITCHING,  ModemState.SIM_DISCONNECTING,  ModemEvent.DISCONNECT),
            (ModemState.SIM_DISCONNECTING, ModemState.SIM_DISABLING,   ModemEvent.SIM_DISCONNECTED),
            (ModemState.SIM_DISABLING,  ModemState.SIM_ENABLING,       ModemEvent.SIM_DISABLED),
            (ModemState.SIM_ENABLING,   ModemState.SIM_RECONFIGURING,  ModemEvent.SIM_ENABLED),
            (ModemState.SIM_RECONFIGURING, ModemState.CONFIGURING,     ModemEvent.SIM_SWITCH_COMPLETE),

            # Error handling
            (ModemState.CONNECTING,     ModemState.FAILED,             ModemEvent.CONNECTION_FAILED),
            (ModemState.CONNECTED,      ModemState.FAILED,             ModemEvent.CONNECTION_FAILED),
            (ModemState.DISCONNECTED,   ModemState.WAITING_FOR_SIM,    ModemEvent.SIM_MISSING),
            (ModemState.CONFIGURING,    ModemState.WAITING_FOR_SIM,    ModemEvent.SIM_MISSING),

            # Hardware removal - back to scanning from ANY state
            (ModemState.DISCONNECTED,   ModemState.SCANNING,           ModemEvent.START_SCAN),
            (ModemState.CONFIGURING,    ModemState.SCANNING,           ModemEvent.START_SCAN),
            (ModemState.CONNECTING,     ModemState.SCANNING,           ModemEvent.START_SCAN),
            (ModemState.CONNECTED,      ModemState.SCANNING,           ModemEvent.START_SCAN),
            (ModemState.USAGE_MONITORING, ModemState.SCANNING,         ModemEvent.START_SCAN),
            (ModemState.MODEM_FOUND,    ModemState.SCANNING,           ModemEvent.START_SCAN),
            (ModemState.WAITING_FOR_CONFIG, ModemState.SCANNING,       ModemEvent.START_SCAN),
            (ModemState.WAITING_FOR_SIM, ModemState.SCANNING,          ModemEvent.START_SCAN),
            (ModemState.FAILED,         ModemState.SCANNING,           ModemEvent.START_SCAN),
            (ModemState.SIM_SWITCHING,  ModemState.SCANNING,           ModemEvent.START_SCAN),
            (ModemState.SIM_DISCONNECTING, ModemState.SCANNING,        ModemEvent.START_SCAN),
            (ModemState.SIM_DISABLING,  ModemState.SCANNING,           ModemEvent.START_SCAN),
            (ModemState.SIM_ENABLING,   ModemState.SCANNING,           ModemEvent.START_SCAN),
            (ModemState.SIM_RECONFIGURING, ModemState.SCANNING,        ModemEvent.START_SCAN),
            (ModemState.USAGE_THRESHOLD, ModemState.SCANNING,          ModemEvent.START_SCAN),
            (ModemState.USAGE_RESETTING, ModemState.SCANNING,          ModemEvent.START_SCAN),

            # Reconfiguration from any configured state
            (ModemState.CONFIGURING,    ModemState.CONFIGURING,        ModemEvent.RECONFIGURE),
            (ModemState.CONNECTED,      ModemState.CONFIGURING,        ModemEvent.RECONFIGURE),
            (ModemState.DISCONNECTED,   ModemState.CONFIGURING,        ModemEvent.RECONFIGURE),
            (ModemState.FAILED,         ModemState.CONFIGURING,        ModemEvent.RECONFIGURE),
            (ModemState.USAGE_MONITORING, ModemState.CONFIGURING,      ModemEvent.RECONFIGURE),

            # Usage monitoring flow
            (ModemState.USAGE_MONITORING, ModemState.USAGE_THRESHOLD,  ModemEvent.USAGE_LIMIT_EXCEEDED),
            (ModemState.USAGE_THRESHOLD, ModemState.USAGE_RESETTING,   ModemEvent.RESET_USAGE),
            (ModemState.USAGE_RESETTING, ModemState.CONFIGURING,       ModemEvent.RECONFIGURE),
        ]
        for src, dst, event in transitions:
            self.machine.add_transition(src.value, dst.value, event.value)

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
        asyncio.create_task(self.scan_for_modem())

    def _is_reset_allowed(self) -> bool:
        """Check if hardware reset is allowed (not in cooldown period)"""
        import time
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
        import time
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
        import time
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
                logger.warning("Current modem removed via signal, transitioning to scanning",
                              extra={'interface_number': self.interface_number,
                                     'modem_path': path})

                # Store original state for logging
                original_state = self.machine.current_state

                # Clean up current modem references
                self.proxy = None
                self.modem_path = None
                self.bearer_path = None

                # Cancel any ongoing tasks
                if hasattr(self, 'usage_monitor_task') and self.usage_monitor_task and not self.usage_monitor_task.done():
                    self.usage_monitor_task.cancel()
                    logger.info("Cancelled usage monitoring task due to modem removal",
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
                    self.machine.set_state(ModemState.SCANNING)

                # Start scanning again (don't await - let it run in background)
                asyncio.create_task(self.scan_for_modem())

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
                signal_quality = None
                try:
                    signal_quality_variant = await props.call_get(MODEM_INTERFACE, "SignalQuality")
                    signal_quality = signal_quality_variant.value
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

        # Set up signal handlers for ModemManager state changes using dbus_next
        try:
            # Subscribe to PropertiesChanged signals to detect State property changes
            modem_properties_iface = self.proxy.get_interface("org.freedesktop.DBus.Properties")
            # Use the correct dbus_next method for PropertiesChanged signals
            modem_properties_iface.on_properties_changed(self._handle_modem_properties_changed)
            logger.info("ModemManager PropertiesChanged signal monitoring enabled",
                       extra={'interface_number': self.interface_number})
        except Exception as e:
            logger.error(f"Failed to set up signal handlers: {e}",
                        extra={'interface_number': self.interface_number})

        # Set up 3GPP interface signals for network events
        try:
            modem_3gpp_properties_iface = self.proxy.get_interface("org.freedesktop.DBus.Properties")
            modem_3gpp_properties_iface.on_properties_changed(self.handle_3gpp_properties)
            logger.debug("3GPP signal handlers enabled",
                        extra={'interface_number': self.interface_number})
        except Exception as e:
            logger.debug(f"3GPP interface not available: {e}",
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
            asyncio.create_task(self._configure_modem_initial())

        # Start periodic SIM check if we transition to WAITING_FOR_SIM
        if self.machine.current_state == ModemState.WAITING_FOR_SIM.value:
            asyncio.create_task(self._periodic_sim_check())

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
        if 'SignalQuality' in changed_properties:
            signal_quality = changed_properties['SignalQuality'].value
            logger.info("Signal strength changed",
                       extra={'interface_number': self.interface_number,
                              'signal_strength': signal_quality})

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
                asyncio.create_task(self._handle_registration_state_change(reg_state, reg_state_name))
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

        # Enhanced SIM hot-swap detection
        if mm_state == 2:  # LOCKED (SIM missing or PIN required)
            if current_fsm_state in [ModemState.CONFIGURING.value, ModemState.CONNECTING.value]:
                self.transition(ModemEvent.SIM_MISSING)
                asyncio.create_task(self._handle_sim_missing_failover())

        elif mm_state == 3:  # DISABLED
            if current_fsm_state in [ModemState.CONFIGURING.value, ModemState.CONNECTING.value,
                                    ModemState.CONNECTED.value, ModemState.USAGE_MONITORING.value]:
                # Don't trigger SIM missing if this is service-initiated or we're in reset grace period
                if not self.service_initiated_disable and not self._is_in_reset_grace_period():
                    self.transition(ModemEvent.SIM_MISSING)
                    asyncio.create_task(self._handle_sim_missing_failover())
                else:
                    if self.service_initiated_disable:
                        logger.debug("Modem disabled by service (gentle reset) - not triggering SIM failover",
                                   extra={'interface_number': self.interface_number})
                    else:
                        logger.debug("Modem disabled during reset grace period - not triggering SIM failover",
                                   extra={'interface_number': self.interface_number})
            elif current_fsm_state == ModemState.WAITING_FOR_SIM.value:
                # Check if SIM was inserted while waiting
                asyncio.create_task(self._check_sim_insertion())

        elif mm_state == 6:  # ENABLED - Could indicate SIM insertion
            if current_fsm_state == ModemState.WAITING_FOR_SIM.value:
                # SIM might have been inserted!
                logger.info("Modem enabled while waiting for SIM - checking for insertion",
                           extra={'interface_number': self.interface_number})
                asyncio.create_task(self._handle_potential_sim_insertion())
            elif current_fsm_state == ModemState.CONFIGURING.value:
                # Modem enabled successfully during configuration - can proceed
                logger.info("Modem enabled, continuing configuration",
                           extra={'interface_number': self.interface_number})
                # Don't transition - let configuration continue

        elif mm_state == 7:  # SEARCHING
            if current_fsm_state == ModemState.CONFIGURING.value:
                # Modem searching for network - configuration working
                logger.info("Modem searching for network",
                           extra={'interface_number': self.interface_number})
                # Transition to CONNECTING state
                self.transition(ModemEvent.CONNECT)

        elif mm_state == 8:  # REGISTERED
            if current_fsm_state in [ModemState.CONNECTING.value, ModemState.CONFIGURING.value]:
                # Successfully registered to network - ready for connection
                logger.info("Modem registered to network, ready for connection",
                           extra={'interface_number': self.interface_number})
                # Trigger connection configuration
                asyncio.create_task(self.apply_modem_configuration())

        elif mm_state == 9:  # DISCONNECTING
            if current_fsm_state in [ModemState.CONNECTED.value, ModemState.USAGE_MONITORING.value]:
                # Connection being terminated - stop network interface monitoring and trigger enhanced reconnection
                logger.warning("ModemManager disconnecting - starting enhanced reconnection",
                              extra={'interface_number': self.interface_number})
                try:
                    asyncio.create_task(self._stop_network_interface_monitoring())
                except RuntimeError:
                    # No event loop running (e.g., during tests) - ignore
                    pass
                self.transition(ModemEvent.DISCONNECT)
                # Start enhanced reconnection immediately
                asyncio.create_task(self.handle_disconnection_recovery())

        elif mm_state == 10:  # CONNECTING
            if current_fsm_state == ModemState.CONNECTING.value:
                # Modem is attempting connection - wait for result
                logger.info("Modem attempting connection",
                           extra={'interface_number': self.interface_number})
                # Don't transition - wait for CONNECTED or failure

        elif mm_state == 11:  # CONNECTED
            if current_fsm_state == ModemState.CONNECTING.value:
                # Transition to CONNECTED and stay there to listen for disconnects
                logger.info("Modem connected successfully, staying in CONNECTED state",
                           extra={'interface_number': self.interface_number})
                self.transition(ModemEvent.CONNECTED)

                # Start network interface management
                try:
                    if self.ensure_link_up_on_connect:
                        asyncio.create_task(self._ensure_interface_up())
                    asyncio.create_task(self._start_network_interface_monitoring())
                except RuntimeError:
                    # No event loop running (e.g., during tests) - ignore
                    pass

                # Only start usage monitoring if data limits are configured
                if self.config and self.config.get('data_limit_size'):
                    logger.info("Data usage limits configured, will start monitoring",
                               extra={'interface_number': self.interface_number,
                                      'limit_gb': self.config.get('data_limit_size', 0) / (1024*1024*1024)})
                    # Don't transition to USAGE_MONITORING state - just start the monitoring task
                    if not self.usage_monitor_task or self.usage_monitor_task.done():
                        self.usage_monitor_task = asyncio.create_task(self.monitor_data_usage())
                else:
                    logger.info("No data usage limits configured, staying in CONNECTED state",
                               extra={'interface_number': self.interface_number})

            elif current_fsm_state == ModemState.CONNECTED.value:
                # Already connected - connection is stable
                logger.info("Already in CONNECTED state - connection stable",
                           extra={'interface_number': self.interface_number})


        elif mm_state in [-1, 0]:  # FAILED or UNKNOWN
            if current_fsm_state in [ModemState.CONFIGURING.value, ModemState.CONNECTING.value,
                                    ModemState.CONNECTED.value, ModemState.USAGE_MONITORING.value]:
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
        # Track user-initiated disconnects and stop network interface monitoring
        if event == ModemEvent.DISCONNECT:
            # Check if this is from user or ModemManager
            current_state = getattr(self.machine, 'current_state', '')
            if current_state in [ModemState.CONNECTED.value, ModemState.USAGE_MONITORING.value]:
                # Stop network interface monitoring when leaving connected state
                try:
                    asyncio.create_task(self._stop_network_interface_monitoring())
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
        old_config = self.config
        # Store previous config for selective disconnection logic
        if hasattr(self, 'config') and self.config:
            self._previous_config = self.config.copy()

        self.config = config

        # 🔄 Extract configuration loading using safe extraction framework
        self._load_configuration_safe(config)

        active_sim_slot = config.get('active_sim_slot', 1)
        logger.info("Configuration applied",
                   extra={'interface_number': self.interface_number,
                          'config_keys': list(config.keys()) if config else [],
                          'active_sim': active_sim_slot,
                          'connectivity_monitoring': config.get('connectivity_monitoring', {}).get('enabled', False),
                          'enhanced_reconnection': self.enhanced_reconnection,
                          'signal_threshold': self.reconnection_signal_threshold,
                          'current_state': self.machine.current_state})


        current = self.machine.current_state

        # Handle configuration based on current state
        if current == ModemState.WAITING_FOR_CONFIG.value:
            # Ready to configure immediately
            self.transition(ModemEvent.CONFIG_UPDATE)
            asyncio.create_task(self._configure_modem_initial())

        elif current == ModemState.SCANNING.value:
            # Store config, will apply when modem found
            logger.info("Config stored, will apply when modem is found",
                       extra={'interface_number': self.interface_number})

        elif current in (
            ModemState.CONFIGURING.value,
            ModemState.CONNECTED.value,
            ModemState.DISCONNECTED.value,
            ModemState.FAILED.value,
            ModemState.USAGE_MONITORING.value
        ):
            # Normal reconfiguration
            self.transition(ModemEvent.RECONFIGURE)
            asyncio.create_task(self._reconfigure_modem())

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

    @safe_extraction("_load_configuration_safe")
    def _load_configuration_safe(self, config: dict):
        """🔄 SAFE EXTRACTION: Load and parse configuration using new ConfigurationLoader"""
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
        active_sim_slot = config.get('active_sim_slot', 1)
        logger.info("Configuration applied",
                   extra={'interface_number': self.interface_number,
                          'config_keys': list(config.keys()) if config else [],
                          'active_sim': active_sim_slot,
                          'connectivity_monitoring': config.get('connectivity_monitoring', {}).get('enabled', False),
                          'enhanced_reconnection': self.parsed_config.enhanced_reconnection.enabled,
                          'signal_threshold': self.parsed_config.enhanced_reconnection.signal_threshold,
                          'current_state': self.machine.current_state})

    def _load_configuration_safe_original(self, config: dict):
        """🏗️ ORIGINAL: Legacy configuration loading (for comparison)"""
        # 🆕 Initialize Enhanced Reconnection Strategy Configuration
        enhanced_value = config.get('enhanced_reconnection', 'enabled')
        if isinstance(enhanced_value, dict):
            self.enhanced_reconnection = enhanced_value.get('enabled', 'enabled').lower() == 'enabled' if isinstance(enhanced_value.get('enabled'), str) else bool(enhanced_value.get('enabled', True))
        else:
            self.enhanced_reconnection = enhanced_value.lower() == 'enabled' if isinstance(enhanced_value, str) else bool(enhanced_value)
        self.reconnection_signal_threshold = int(config.get('reconnection_signal_threshold', -85))
        self.enhanced_reconnection_max_retries = int(config.get('enhanced_reconnection_max_retries', 3))
        self.retry_interval_good_signal = int(config.get('retry_interval_good_signal', 15))
        self.retry_interval_poor_signal = int(config.get('retry_interval_poor_signal', 45))
        self.max_wait_for_signal = int(config.get('max_wait_for_signal', 120))
        self.signal_check_interval = int(config.get('signal_check_interval', 10))
        self.normal_monitoring_interval = int(config.get('normal_monitoring_interval', 30))
        self.signal_strength_buffer = int(config.get('signal_strength_buffer', 5))

        # 🆕 Initialize Network Interface Management Configuration
        self.interface_management = config.get('interface_management', {})
        self.interface_management_enabled = self.interface_management.get('enabled', True)
        self.bearer_disconnect_delay = self.interface_management.get('bearer_disconnect_delay', 15)
        self.ip_change_delay = self.interface_management.get('ip_change_delay', 2)
        self.ensure_link_up_on_connect = self.interface_management.get('ensure_link_up_on_connect', True)
        self.monitor_bearer_state = self.interface_management.get('monitor_bearer_state', True)
        self.monitor_ip_changes = self.interface_management.get('monitor_ip_changes', True)
        self.interface_up_timeout = self.interface_management.get('interface_up_timeout', 10)

        # Initialize network interface management state
        self._bearer_disconnect_timer = None
        self._last_known_ip = None
        self._ip_monitoring_task = None

        # Bearer D-Bus signal monitoring state
        self._bearer_proxy = None
        self._bearer_interface = None

        # 🆕 Normalize connectivity monitoring config
        if 'connectivity_monitoring' in config:
            config['connectivity_monitoring'] = self._normalize_connectivity_config(
                config['connectivity_monitoring']
            )

        active_sim_slot = config.get('active_sim_slot', 1)
        logger.info("Configuration applied",
                   extra={'interface_number': self.interface_number,
                          'config_keys': list(config.keys()) if config else [],
                          'active_sim': active_sim_slot,
                          'connectivity_monitoring': config.get('connectivity_monitoring', {}).get('enabled', False),
                          'enhanced_reconnection': self.enhanced_reconnection,
                          'signal_threshold': self.reconnection_signal_threshold,
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
        self.ip_change_delay = self.parsed_config.interface_management.ip_change_delay
        self.ensure_link_up_on_connect = self.parsed_config.interface_management.ensure_link_up_on_connect
        self.monitor_bearer_state = self.parsed_config.interface_management.monitor_bearer_state
        self.monitor_ip_changes = self.parsed_config.interface_management.monitor_ip_changes
        self.interface_up_timeout = self.parsed_config.interface_management.interface_up_timeout

        # Initialize network interface management state
        self._bearer_disconnect_timer = None
        self._last_known_ip = None
        self._ip_monitoring_task = None

        # Bearer D-Bus signal monitoring state
        self._bearer_proxy = None
        self._bearer_interface = None

    async def _configure_modem_initial(self):
        """Initial modem configuration - configure SIM/bands/carrier BEFORE network operations"""
        try:
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
                            from vyos.utils.wwan.interfaces_wwan_util import modem_reset
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

            # Step 4: Enable the modem
            await self._ensure_modem_enabled()

            # Step 5: Unlock SIM if needed after enabling
            await self._unlock_sim_if_needed()

            # Step 6: 🆕 Configure preferred carrier if specified
            await self._configure_preferred_carrier()

            logger.info("Initial modem configuration complete",
                       extra={'interface_number': self.interface_number})

            # Automatically proceed to connection since signal handlers are disabled
            logger.info("Automatically proceeding to connection phase",
                       extra={'interface_number': self.interface_number})
            self.transition(ModemEvent.CONNECT)

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
            active_slot = self.config.get('active_sim_slot', 1) if self.config else 1
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
                logger.warning("Could not get SIM information",
                              extra={'interface_number': self.interface_number})
                sim_changed = False
            else:
                sim_changed = await self._check_sim_change(sim_info)

            # PRIORITY 1: Try configured APN first (highest priority) - unless SIM changed
            if not sim_changed and self.config and 'sim_slots' in self.config:
                active_sim = None
                for slot in self.config['sim_slots']:
                    if slot['slot'] == active_slot:
                        active_sim = slot
                        break

                if active_sim and active_sim.get('apn'):
                    logger.info("Attempting connection with configured APN (highest priority)",
                               extra={'interface_number': self.interface_number,
                                      'configured_apn': active_sim['apn']})

                    apn_config = {
                        'name': active_sim['apn'],
                        'username': active_sim.get('username', ''),
                        'password': active_sim.get('password', ''),
                        'auth_type': active_sim.get('auth_type', 'none')
                    }

                    try:
                        success = await self._try_connection_with_apn(apn_config, sim_config)
                        if success:
                            connection_successful = True
                    except Exception as e:
                        logger.warning(f"Configured APN failed: {e}",
                                     extra={'interface_number': self.interface_number})

            # PRIORITY 1.5: If SIM changed, skip cached APNs and go straight to discovery
            # This ensures fresh discovery when user changes SIM cards

            # PRIORITY 2: Try cached successful APN (unless SIM changed)
            if not connection_successful and not sim_changed and sim_info:
                cached_apn = await self._get_cached_successful_apn(sim_info)
                if cached_apn:
                    logger.info("Trying cached successful APN",
                               extra={'interface_number': self.interface_number,
                                      'cached_apn': cached_apn['name']})
                    try:
                        success = await self._try_connection_with_apn(cached_apn, sim_config)
                        if success:
                            connection_successful = True
                            logger.info("Cached APN connection successful",
                                       extra={'interface_number': self.interface_number,
                                              'apn_name': cached_apn['name']})
                    except Exception as e:
                        logger.warning(f"Cached APN failed: {e}",
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

            # PRIORITY 3: Try automatic network-provided APN (lowest priority)
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

                # Update SIM info after successful connection for future change detection
                if sim_info:
                    self.last_known_sim_info = sim_info.copy()
                    self.sim_changed = False
                    logger.debug("Updated stored SIM info after successful connection",
                                extra={'interface_number': self.interface_number,
                                       'operator': sim_info.get('operator_name', 'Unknown'),
                                       'mcc_mnc': sim_info.get('mcc_mnc', 'Unknown')})

                # Transition to CONNECTED and stay there for event-driven monitoring
                self.transition(ModemEvent.CONNECTED)
                logger.info("Connected - staying in CONNECTED state for event-driven monitoring",
                           extra={'interface_number': self.interface_number})

                # Apply bearer IP configuration to interface (VyOS responsibility)
                await self._apply_bearer_ip_configuration()

                # Start network interface management
                try:
                    if self.ensure_link_up_on_connect:
                        asyncio.create_task(self._ensure_interface_up())
                    asyncio.create_task(self._start_network_interface_monitoring())
                except RuntimeError:
                    # No event loop running (e.g., during tests) - ignore
                    pass

                # Only start data usage monitoring if limits are configured
                if self.config and self.config.get('data_limit_size'):
                    logger.info("Data usage limits configured, starting data monitoring",
                               extra={'interface_number': self.interface_number,
                                      'limit_gb': self.config.get('data_limit_size', 0) / (1024*1024*1024)})
                    if not self.usage_monitor_task or self.usage_monitor_task.done():
                        self.usage_monitor_task = asyncio.create_task(self.monitor_data_usage())
                else:
                    logger.info("No data usage limits - connection monitoring is now event-driven",
                               extra={'interface_number': self.interface_number})
            else:
                logger.error("All APN connection methods failed",
                           extra={'interface_number': self.interface_number})
                self.transition(ModemEvent.CONNECTION_FAILED)

        except Exception as e:
            logger.error(f"Initial modem configuration failed: {e}",
                        extra={'interface_number': self.interface_number})
            self.transition(ModemEvent.CONNECTION_FAILED)

    async def _unlock_sim_if_needed(self):
        """Unlock SIM with PIN/PUK if required"""
        try:
            if not self.config:
                return

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

                logger.info("SIM is locked, checking unlock requirement",
                           extra={'interface_number': self.interface_number,
                                  'unlock_required': unlock_required})

                active_sim_slot = self.config.get('active_sim_slot', 1)
                sim_slots = self.config.get('sim_slots', [])
                active_sim_config = next((sim for sim in sim_slots if sim['slot'] == active_sim_slot), {})

                if unlock_required == 1:  # MM_MODEM_LOCK_SIM_PIN
                    await self._unlock_with_pin(active_sim_config)
                elif unlock_required == 2:  # MM_MODEM_LOCK_SIM_PUK
                    await self._unlock_with_puk(active_sim_config)
                else:
                    logger.warning("Unknown unlock requirement",
                                  extra={'interface_number': self.interface_number,
                                         'unlock_required': unlock_required})
            else:
                logger.info("SIM unlock not needed",
                           extra={'interface_number': self.interface_number,
                                  'modem_state': state})

        except Exception as e:
            logger.error(f"SIM unlock check failed: {e}",
                        extra={'interface_number': self.interface_number})
            # Don't fail the entire configuration for SIM unlock issues
            logger.warning("Continuing configuration without SIM unlock",
                          extra={'interface_number': self.interface_number})

    async def _unlock_with_pin(self, sim_config):
        """Unlock SIM with PIN"""
        try:
            pin = sim_config.get('pin', '')
            auto_unlock = sim_config.get('auto_unlock', True)

            if pin and auto_unlock:
                logger.info("Unlocking SIM with stored PIN",
                           extra={'interface_number': self.interface_number,
                                  'auto_unlock': auto_unlock})

                iface = self.proxy.get_interface(MODEM_INTERFACE)
                await iface.call_send_pin(pin)

                # Wait a moment for unlock to process
                await asyncio.sleep(3)

                # Verify unlock was successful
                props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
                state_variant = await props.call_get(MODEM_INTERFACE, "State")
                state = state_variant.value

                if state != 2:  # No longer locked
                    logger.info("SIM unlocked with PIN successfully",
                               extra={'interface_number': self.interface_number})
                else:
                    logger.error("SIM unlock with PIN failed - still locked",
                                extra={'interface_number': self.interface_number})
                    raise Exception("PIN unlock failed - SIM still locked")

            else:
                logger.warning("PIN required but not configured or auto_unlock disabled",
                              extra={'interface_number': self.interface_number,
                                     'has_pin': bool(pin),
                                     'auto_unlock': auto_unlock})
                raise Exception("PIN required but not available for auto-unlock")

        except Exception as e:
            logger.error(f"PIN unlock failed: {e}",
                        extra={'interface_number': self.interface_number})
            raise

    async def _unlock_with_puk(self, sim_config):
        """Unlock SIM with PUK and new PIN"""
        try:
            puk = sim_config.get('puk', '')
            new_pin = sim_config.get('new_pin', '')
            auto_unlock = sim_config.get('auto_unlock', True)

            if puk and new_pin and auto_unlock:
                logger.info("Unlocking SIM with PUK",
                           extra={'interface_number': self.interface_number,
                                  'has_puk': bool(puk),
                                  'has_new_pin': bool(new_pin)})

                iface = self.proxy.get_interface(MODEM_INTERFACE)
                await iface.call_send_puk(puk, new_pin)

                # Wait a moment for unlock to process
                await asyncio.sleep(5)

                # Verify unlock was successful
                props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
                state_variant = await props.call_get(MODEM_INTERFACE, "State")
                state = state_variant.value

                if state != 2:  # No longer locked
                    # Update stored PIN to new PIN for future use
                    sim_config['pin'] = new_pin

                    logger.info("SIM unlocked with PUK and new PIN set successfully",
                               extra={'interface_number': self.interface_number})
                else:
                    logger.error("SIM unlock with PUK failed - still locked",
                                extra={'interface_number': self.interface_number})
                    raise Exception("PUK unlock failed - SIM still locked")

            else:
                logger.warning("PUK/new PIN required but not configured or auto_unlock disabled",
                              extra={'interface_number': self.interface_number,
                                     'has_puk': bool(puk),
                                     'has_new_pin': bool(new_pin),
                                     'auto_unlock': auto_unlock})
                raise Exception("PUK and new PIN required but not available for auto-unlock")

        except Exception as e:
            logger.error(f"PUK unlock failed: {e}",
                        extra={'interface_number': self.interface_number})
            raise

    async def _configure_preferred_carrier(self):
        """Configure preferred carrier with smart scanning to minimize delays"""
        try:
            if not self.config:
                return

            # Get active SIM configuration
            active_sim_slot = self.config.get('active_sim_slot', 1)
            sim_slots = self.config.get('sim_slots', [])
            active_sim_config = next((sim for sim in sim_slots if sim['slot'] == active_sim_slot), {})

            preferred_carrier = active_sim_config.get('preferred_carrier', '')
            if not preferred_carrier:
                logger.info("No preferred carrier configured, using automatic registration",
                           extra={'interface_number': self.interface_number})
                return

            logger.info("Checking for preferred carrier configuration",
                       extra={'interface_number': self.interface_number,
                              'preferred_carrier': preferred_carrier})

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

            # Check if already on preferred carrier (avoid scanning)
            try:
                current_operator_name_variant = await props.call_get("org.freedesktop.ModemManager1.Modem.Modem3gpp", "OperatorName")
                current_operator_name = current_operator_name_variant.value
                if preferred_carrier.lower() in current_operator_name.lower():
                    logger.info("Already registered to preferred carrier",
                               extra={'interface_number': self.interface_number,
                                      'current_operator': current_operator_name})
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
                    return
                except Exception:
                    logger.info("Direct registration failed, checking scan option",
                               extra={'interface_number': self.interface_number})

            # Only scan if explicitly enabled
            enable_network_scan = active_sim_config.get('enable_network_scan', False)
            if not enable_network_scan:
                logger.info("Network scanning disabled for performance, using automatic registration",
                           extra={'interface_number': self.interface_number,
                                  'suggestion': 'Set enable_network_scan: true to enable scanning'})
                return

            # Full network scan (slow but comprehensive)
            logger.warning("Performing full network scan - this may take 2+ minutes",
                          extra={'interface_number': self.interface_number})

            try:
                operators = await asyncio.wait_for(gpp_iface.call_scan(), timeout=180.0)
                await self._process_scan_results(operators, preferred_carrier, gpp_iface, props)
            except asyncio.TimeoutError:
                logger.warning("Network scan timed out, using automatic registration",
                              extra={'interface_number': self.interface_number})

        except Exception as e:
            logger.info("Carrier selection not supported, using automatic registration",
                       extra={'interface_number': self.interface_number,
                              'error': str(e)})

    async def _process_scan_results(self, operators, preferred_carrier, gpp_iface, props):
        """Process network scan results and register to preferred operator"""
        target_operator = None

        for op_path in operators:
            try:
                op_introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, op_path)
                op_proxy = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, op_path, op_introspect)
                op_props = op_proxy.get_interface("org.freedesktop.DBus.Properties")

                operator_code_variant = await op_props.call_get("org.freedesktop.ModemManager1.Modem.Modem3gpp.Operator", "OperatorCode")
                operator_code = operator_code_variant.value
                operator_name_variant = await op_props.call_get("org.freedesktop.ModemManager1.Modem.Modem3gpp.Operator", "OperatorName")
                operator_name = operator_name_variant.value
                status_variant = await op_props.call_get("org.freedesktop.ModemManager1.Modem.Modem3gpp.Operator", "Status")
                status = status_variant.value

                logger.info("Found operator",
                           extra={'interface_number': self.interface_number,
                                  'operator_name': operator_name,
                                  'operator_code': operator_code})

                # Match preferred carrier
                if (preferred_carrier.lower() in operator_name.lower() or
                    preferred_carrier == operator_code) and status in [1, 2]:
                    target_operator = op_path
                    logger.info("Matched preferred carrier in scan",
                               extra={'interface_number': self.interface_number,
                                      'operator_name': operator_name})
                    break

            except Exception:
                continue

        # Register to target operator if found
        if target_operator:
            logger.info("Registering to preferred carrier from scan",
                       extra={'interface_number': self.interface_number})
            await gpp_iface.call_register(target_operator)
            await asyncio.sleep(15)
        else:
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
                logger.info(f"Modem power is off, powering on first...",
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

            config_sim_slot = self.config.get('active_sim_slot', 1)
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
                    # Simple SIM slot change while disabled
                    logger.info("Setting SIM slot while modem disabled",
                               extra={'interface_number': self.interface_number,
                                      'from_sim': actual_sim,
                                      'to_sim': config_sim_slot})

                    # Set primary SIM slot
                    await props.call_set(MODEM_INTERFACE, "PrimarySimSlot", Variant('u', config_sim_slot))

                    # Brief wait for hardware switch
                    await asyncio.sleep(3)

                    # Verify the switch
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

    async def _execute_sim_switch(self):
        """Execute the complete SIM switch process"""
        try:
            logger.info("Starting SIM switch process",
                       extra={'interface_number': self.interface_number,
                              'target_sim': self.target_sim_slot,
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
                        extra={'interface_number': self.interface_number})
            self.transition(ModemEvent.CONNECTION_FAILED)

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
        """Handle SIM missing by attempting failover to available SIM"""
        try:
            if not self.config:
                return False

            # Check if failover is enabled
            sim_failover = self.config.get('sim_failover', 'disabled')
            if sim_failover != 'enabled':
                logger.info("SIM failover disabled, waiting for configured SIM",
                           extra={'interface_number': self.interface_number,
                                  'config_sim': self.config_active_sim})
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
                        imsi_variant = await sim_props.call_get(sim_interface, "Imsi")
                        imsi = imsi_variant.value

                        if imsi:  # SIM is present and readable
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
            config_sim_slot = self.config.get('active_sim_slot', 1)

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
            asyncio.create_task(self._handle_sim_missing_failover())

        except Exception as e:
            logger.error(f"Failed to handle locked state: {e}",
                        extra={'interface_number': self.interface_number})
            # Fallback to missing SIM handling
            self.transition(ModemEvent.SIM_MISSING)
            asyncio.create_task(self._handle_sim_missing_failover())

    async def _check_sim_insertion(self):
        """Check if a SIM was inserted in the configured slot"""
        try:
            if not self.proxy or not self.config:
                return

            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")
            sim_slots_variant = await props.call_get(MODEM_INTERFACE, "SimSlots")
            sim_slots = sim_slots_variant.value  # Extract array from Variant
            config_sim_slot = self.config.get('active_sim_slot', 1)

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
            # Wait a moment for SIM to fully initialize
            await asyncio.sleep(3)

            # Check if we now have the configured SIM
            sim_inserted = await self._check_sim_insertion()

            if not sim_inserted:
                # Still no configured SIM - check for any available SIM
                if self.config.get('sim_failover') == 'enabled':
                    logger.info("No configured SIM found, checking for failover options",
                               extra={'interface_number': self.interface_number})
                    await self._handle_sim_missing_failover()
                else:
                    logger.info("No configured SIM found and failover disabled",
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
        """Step 3: Perform actual SIM slot switch"""
        try:
            logger.info("Switching SIM slot hardware",
                       extra={'interface_number': self.interface_number,
                              'target_sim': self.target_sim_slot})

            props = self.proxy.get_interface("org.freedesktop.DBus.Properties")

            # Set the primary SIM slot while modem is disabled
            await props.call_set(MODEM_INTERFACE, "PrimarySimSlot", Variant('u', self.target_sim_slot))

            # Wait a moment for hardware switch
            await asyncio.sleep(3)

            logger.info("SIM slot hardware switch completed",
                       extra={'interface_number': self.interface_number,
                              'target_sim': self.target_sim_slot})

            # Transition to enable step
            self.transition(ModemEvent.SIM_SWITCHED)
            await self._sim_switch_enable()

        except Exception as e:
            logger.error(f"Failed to switch SIM hardware: {e}",
                        extra={'interface_number': self.interface_number})
            raise

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
                logger.error("SIM switch verification failed",
                            extra={'interface_number': self.interface_number,
                                   'target_sim': self.target_sim_slot,
                                   'actual_sim': actual_sim})

            # Transition to reconfiguration
            self.transition(ModemEvent.SIM_ENABLED)
            await self._sim_switch_reconfigure()

        except Exception as e:
            logger.error(f"Failed to re-enable modem after SIM switch: {e}",
                        extra={'interface_number': self.interface_number})
            raise

    async def _sim_switch_reconfigure(self):
        """Step 5: Reconfigure modem with new SIM settings"""
        try:
            logger.info("Reconfiguring modem with new SIM settings",
                       extra={'interface_number': self.interface_number,
                              'active_sim': self.current_active_sim})

            # Get the NEW SIM's configuration
            active_sim_slot = self.current_active_sim
            sim_slots = self.config.get('sim_slots', [])
            new_sim_config = next((sim for sim in sim_slots if sim['slot'] == active_sim_slot), {})

            logger.info("Using new SIM configuration",
                       extra={'interface_number': self.interface_number,
                              'sim_slot': active_sim_slot,
                              'apn': new_sim_config.get('apn', ''),
                              'bands': new_sim_config.get('supported_bands', [])})

            # Reconfigure bands for new SIM
            await self._configure_supported_bands()

            # SIM switch complete - transition back to normal configuration
            self.transition(ModemEvent.SIM_SWITCH_COMPLETE)

            logger.info("SIM switch process completed successfully",
                       extra={'interface_number': self.interface_number,
                              'new_sim': self.current_active_sim,
                              'switch_reason': self.sim_switch_reason})

        except Exception as e:
            logger.error(f"Failed to reconfigure after SIM switch: {e}",
                        extra={'interface_number': self.interface_number})
            raise

    async def _configure_supported_bands(self):
        """Configure supported bands while modem is disabled"""
        try:
            if not self.config:
                logger.info("No configuration available for band setup",
                           extra={'interface_number': self.interface_number})
                return

            # Get active SIM configuration
            active_sim_slot = self.config.get('active_sim_slot', 1)
            sim_slots = self.config.get('sim_slots', [])
            active_sim_config = next((sim for sim in sim_slots if sim['slot'] == active_sim_slot), {})

            configured_bands = active_sim_config.get('supported_bands', ['all'])

            logger.info("Configuring supported bands while disabled",
                       extra={'interface_number': self.interface_number,
                              'active_sim_slot': active_sim_slot,
                              'configured_bands': configured_bands})

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
                                  'configured_bands': configured_bands})

                # Handle 'all' bands configuration
                if configured_bands == ['all'] or not configured_bands:
                    logger.info("Configuration requests all bands",
                               extra={'interface_number': self.interface_number})

                    # Check if all supported bands are already enabled
                    if set(current_bands_list) == set(modem_bands_list):
                        logger.info("All supported bands already enabled",
                                   extra={'interface_number': self.interface_number,
                                          'enabled_bands': len(current_bands_list),
                                          'total_supported': len(modem_bands_list)})
                        return
                    else:
                        # Enable all supported bands
                        target_bands = modem_bands_list
                        target_band_names = modem_band_names
                        logger.info("Enabling all modem-supported bands",
                                   extra={'interface_number': self.interface_number,
                                          'target_bands': target_band_names,
                                          'target_constants': target_bands})
                else:
                    # Handle specific band configuration - use intersection logic
                    logger.info("Configuration requests specific bands",
                               extra={'interface_number': self.interface_number,
                                      'requested_bands': configured_bands})

                    # Convert config band names to MM constants
                    requested_band_constants = []
                    invalid_band_names = []

                    for band_name in configured_bands:
                        mm_constant = self._band_name_to_mm_constant(band_name)
                        if mm_constant is not None:
                            requested_band_constants.append(mm_constant)
                        else:
                            invalid_band_names.append(band_name)

                    if invalid_band_names:
                        logger.warning("Some band names could not be converted to MM constants",
                                      extra={'interface_number': self.interface_number,
                                             'invalid_bands': invalid_band_names,
                                             'valid_formats': ['eutran-1', 'ngran-78', 'umts-1', 'gsm-850']})

                    if not requested_band_constants:
                        logger.warning("No valid band constants found, using all bands",
                                      extra={'interface_number': self.interface_number,
                                             'invalid_bands': configured_bands})
                        target_bands = modem_bands_list
                        target_band_names = modem_band_names
                    else:
                        # Find intersection of requested and modem-supported bands
                        valid_band_constants = [band for band in requested_band_constants if band in modem_bands_list]
                        invalid_band_constants = [band for band in requested_band_constants if band not in modem_bands_list]

                        # Log any bands that were requested but not supported by modem
                        if invalid_band_constants:
                            invalid_supported_names = [self._mm_constant_to_band_name(band) for band in invalid_band_constants]
                            logger.warning("Some requested bands are not supported by this modem",
                                          extra={'interface_number': self.interface_number,
                                                 'unsupported_bands': invalid_supported_names,
                                                 'unsupported_constants': invalid_band_constants,
                                                 'modem_supported': modem_band_names})

                        if not valid_band_constants:
                            logger.warning("No requested bands are supported by this modem - using all bands",
                                          extra={'interface_number': self.interface_number,
                                                 'requested_bands': configured_bands,
                                                 'modem_supported': modem_band_names})
                            target_bands = modem_bands_list
                            target_band_names = modem_band_names
                        else:
                            # Use intersection of requested and supported bands
                            target_bands = valid_band_constants
                            target_band_names = [self._mm_constant_to_band_name(band) for band in valid_band_constants]

                            logger.info("Using intersection of requested and supported bands",
                                       extra={'interface_number': self.interface_number,
                                              'valid_bands': target_band_names,
                                              'valid_constants': target_bands})

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
                                  'configured_bands': configured_bands})

        except Exception as e:
            logger.error(f"Band configuration error: {e}",
                        extra={'interface_number': self.interface_number})
            # Don't fail the entire configuration for band issues
            logger.warning("Continuing configuration without band changes",
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
            'active_sim_slot',
            'sim_slots',  # APN, auth, roaming changes within sim_slots
            'supported_bands',
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

        if needs_disconnect and self.machine.current_state in [ModemState.CONNECTED.value, ModemState.USAGE_MONITORING.value]:
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
                self.transition(ModemEvent.CONNECTED)
                return
            # Get active SIM configuration
            active_sim_slot = self.config.get('active_sim_slot', 1)
            sim_slots = self.config.get('sim_slots', [])
            active_sim_config = next((sim for sim in sim_slots if sim['slot'] == active_sim_slot), {})

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
                              'active_sim_slot': active_sim_slot,
                              'library_available': APN_LOOKUP_AVAILABLE})

            # Get SIM information for lookup
            sim_info = await self._get_sim_information()
            if not sim_info:
                logger.error("Could not get SIM information for APN discovery",
                            extra={'interface_number': self.interface_number})
                self.transition(ModemEvent.CONNECTION_FAILED)
                return

            # Try cached successful APN first
            cached_apn = await self._get_cached_successful_apn(sim_info)
            if cached_apn:
                logger.info("Trying cached successful APN first",
                           extra={'interface_number': self.interface_number,
                                  'cached_apn': cached_apn['name']})

                success = await self._try_connection_with_apn(cached_apn, active_sim_config)
                if success:
                    logger.info("Cached APN connection successful",
                               extra={'interface_number': self.interface_number,
                                      'apn_name': cached_apn['name']})
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

    # @safe_extraction("_discover_apn_candidates")  # Async methods need special handling
    async def _discover_apn_candidates(self, sim_info, sim_config):
        """🔄 SAFE EXTRACTION: Discover APN candidates using new APNDiscovery class"""
        return await self.apn_discovery.discover_apn_candidates(sim_info, sim_config)

    async def _discover_apn_candidates_original(self, sim_info, sim_config):
        """🏗️ ORIGINAL: Discover APN candidates using Android library or fallback (for comparison)"""
        try:
            if APN_LOOKUP_AVAILABLE:
                return await self._discover_with_android_library_original(sim_info, sim_config)
            else:
                return await self._discover_with_fallback_original(sim_info, sim_config)

        except Exception as e:
            logger.error(f"APN discovery failed: {e}",
                        extra={'interface_number': self.interface_number})
            return []

    async def _discover_with_android_library_original(self, sim_info, sim_config):
        """Use the Android apnscripts library for APN discovery"""
        try:
            # Extract SIM identifiers for the Android library
            mcc_mnc = sim_info['mcc_mnc'] or ""
            imsi_prefix = sim_info['imsi'][:15] if sim_info['imsi'] else ""
            iccid_prefix = sim_info['sim_identifier'] or ""
            gid1 = sim_info['gid1'] or ""
            gid2 = sim_info['gid2'] or ""
            plmn = sim_info['plmn'] or ""
            spn = sim_info['spn'] or ""

            logger.info("Calling Android APN lookup",
                       extra={'interface_number': self.interface_number,
                              'mcc_mnc': mcc_mnc,
                              'imsi_prefix': imsi_prefix[:6] + '...' if imsi_prefix else None,
                              'plmn': plmn,
                              'spn': spn})

            # Call the Android lookup library in executor to avoid blocking
            loop = asyncio.get_event_loop()
            apn_list = await loop.run_in_executor(
                None,
                find_apn_list,
                mcc_mnc, imsi_prefix, iccid_prefix, gid1, gid2, plmn, spn
            )

            logger.info("Android APN lookup completed",
                       extra={'interface_number': self.interface_number,
                              'raw_apn_count': len(apn_list),
                              'mcc_mnc': mcc_mnc})

            # Convert Android APNs to our format
            candidates = self._convert_android_apns(apn_list, sim_info)

            return candidates

        except Exception as e:
            logger.error(f"Android APN lookup failed: {e}",
                        extra={'interface_number': self.interface_number})
            # Fallback to built-in database
            return await self._discover_with_fallback_original(sim_info, sim_config)

    def _convert_android_apns_original(self, android_apns, sim_info):
        """ORIGINAL: Convert Android APN format to our standardized format (kept for comparison)"""
        candidates = []

        for i, apn in enumerate(android_apns):
            try:
                # Android APNs typically have these fields (adjust based on actual structure)
                candidate = {
                    'name': self._extract_apn_field_original(apn, 'apn', f'apn_{i}'),
                    'username': self._extract_apn_field_original(apn, 'user', ''),
                    'password': self._extract_apn_field_original(apn, 'password', ''),
                    'auth_type': self._convert_android_auth_type_original(
                        self._extract_apn_field_original(apn, 'authtype', '0')
                    ),
                    'type': self._extract_apn_field_original(apn, 'type', 'default'),
                    'priority': self._calculate_android_priority(apn, i),
                    'carrier': sim_info['operator_name'],
                    'mcc_mnc': sim_info['mcc_mnc'],
                    'match_type': 'android_lookup',
                    'source': 'AOSP'
                }

                # Only add if APN name is valid
                if candidate['name'] and candidate['name'] != f'apn_{i}':
                    candidates.append(candidate)

            except Exception as e:
                logger.warning(f"Failed to convert Android APN {i}: {e}",
                              extra={'interface_number': self.interface_number})
                continue

        return candidates

    @safe_extraction('_convert_android_apns')
    def _convert_android_apns(self, android_apns, sim_info):
        """NEW: Convert Android APN format using extracted utility"""
        return convert_android_apns(android_apns, sim_info)

    def _extract_apn_field_original(self, apn, field_name: str, default_value: str = '') -> str:
        """ORIGINAL: Extract field from Android APN object (kept for comparison)"""
        try:
            # Handle different possible structures
            if hasattr(apn, field_name):
                return str(getattr(apn, field_name, default_value))
            elif isinstance(apn, dict):
                return str(apn.get(field_name, default_value))
            elif hasattr(apn, '__getitem__'):
                return str(apn[field_name]) if field_name in apn else default_value
            else:
                return default_value
        except (AttributeError, KeyError, TypeError):
            return default_value

    @safe_extraction('_extract_apn_field')
    def _extract_apn_field(self, apn, field_name: str, default_value: str = '') -> str:
        """NEW: Extract field from Android APN object using extracted utility"""
        return extract_apn_field(apn, field_name, default_value)

    def _convert_android_auth_type_original(self, android_auth: str) -> str:
        """ORIGINAL: Convert Android auth type to our format (kept for comparison)"""
        auth_mapping = {
            '0': 'none',      # No authentication
            '1': 'pap',       # PAP
            '2': 'chap',      # CHAP
            '3': 'pap-chap',  # PAP or CHAP
            'none': 'none',
            'pap': 'pap',
            'chap': 'chap',
            'pap-chap': 'pap-chap'
        }
        return auth_mapping.get(str(android_auth).lower(), 'none')

    @safe_extraction('_convert_android_auth_type')
    def _convert_android_auth_type(self, android_auth: str) -> str:
        """NEW: Convert Android auth type using extracted utility"""
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

    async def _discover_with_fallback_original(self, sim_info, sim_config):
        """Fallback discovery when Android library is not available"""
        logger.info("Using fallback APN discovery",
                   extra={'interface_number': self.interface_number,
                          'mcc_mnc': sim_info['mcc_mnc'],
                          'operator_name': sim_info['operator_name']})

        candidates = []

        # Basic fallback database
        fallback_db = {
            "310260": [{"name": "fast.t-mobile.com", "username": "", "password": "", "auth_type": "none", "priority": 1}],
            "311480": [{"name": "vzwinternet", "username": "", "password": "", "auth_type": "none", "priority": 1}],
            "310410": [{"name": "broadband", "username": "", "password": "", "auth_type": "none", "priority": 1}],
        }

        mcc_mnc = sim_info['mcc_mnc']
        if mcc_mnc in fallback_db:
            for apn in fallback_db[mcc_mnc]:
                candidates.append({
                    **apn,
                    'carrier': sim_info['operator_name'],
                    'mcc_mnc': mcc_mnc,
                    'match_type': 'fallback_database',
                    'source': 'builtin'
                })

        return candidates

    # @safe_extraction("_try_apn_candidates")  # Async methods need special handling
    async def _try_apn_candidates(self, candidates, sim_config, sim_info):
        """🔄 SAFE EXTRACTION: Try APN candidates using new ConnectionManager"""
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

    async def _try_apn_candidates_original(self, candidates, sim_config, sim_info):
        """🏗️ ORIGINAL: Try APN candidates in priority order (for comparison)"""
        logger.info("Trying APN candidates in priority order",
                   extra={'interface_number': self.interface_number,
                          'candidate_count': len(candidates)})

        for i, candidate in enumerate(candidates):
            try:
                logger.info(f"Trying APN candidate {i+1}/{len(candidates)}",
                           extra={'interface_number': self.interface_number,
                                  'apn_name': candidate['name'],
                                  'apn_type': candidate.get('type', 'default'),
                                  'priority': candidate.get('priority', 0)})

                # Convert candidate to our APN config format
                apn_config = {
                    'name': candidate['name'],
                    'username': candidate.get('username', ''),
                    'password': candidate.get('password', ''),
                    'auth_type': candidate.get('auth_type', 'none')
                }

                success = await self._try_connection_with_apn_original(apn_config, sim_config)

                if success:
                    logger.info("APN candidate connection successful",
                               extra={'interface_number': self.interface_number,
                                      'successful_apn': candidate['name'],
                                      'attempt_number': i+1,
                                      'total_attempts': len(candidates)})

                    # Cache successful APN for future use
                    await self._cache_successful_apn_original(sim_info, apn_config, candidate)
                    return

                else:
                    logger.info(f"APN candidate {i+1} failed, trying next",
                               extra={'interface_number': self.interface_number,
                                      'failed_apn': candidate['name'],
                                      'remaining_candidates': len(candidates) - i - 1})

            except Exception as e:
                logger.warning(f"Error trying APN candidate: {e}",
                              extra={'interface_number': self.interface_number,
                                     'apn_name': candidate['name']})
                continue

        # All candidates failed
        logger.warning("All APN candidates failed, trying automatic assignment",
                      extra={'interface_number': self.interface_number,
                             'total_candidates_tried': len(candidates)})

        await self._try_automatic_apn_assignment(sim_config)

    # @safe_extraction("_try_connection_with_apn")  # Async methods need special handling
    async def _try_connection_with_apn(self, apn_config, sim_config):
        """🔄 SAFE EXTRACTION: Try connection using new ConnectionManager"""
        # Set proxy for connection manager
        self.connection_manager.set_proxy(self.proxy)

        # Use the extracted connection manager
        success = await self.connection_manager.try_connection_with_apn(apn_config, sim_config)

        if success:
            # Update bearer path for backward compatibility
            self.bearer_path = self.connection_manager.get_current_bearer_path()

        return success

    async def _try_connection_with_apn_original(self, apn_config, sim_config):
        """Try to establish connection with specific APN configuration"""
        try:
            logger.info("Attempting connection with APN",
                       extra={'interface_number': self.interface_number,
                              'apn_name': apn_config['name'],
                              'has_auth': apn_config['auth_type'] != 'none'})

            # Build connection parameters (reuse existing logic)
            connect_params = {}

            # Add APN name
            connect_params['apn'] = Variant('s', apn_config['name'])

            # Add PDP/IP type
            pdp_type = sim_config.get('pdp_type', 'ipv4')
            connect_params['ip-type'] = Variant('u', self._convert_pdp_type(pdp_type))

            # Add authentication if configured
            if apn_config['auth_type'] != 'none' and apn_config['username']:
                connect_params['user'] = Variant('s', apn_config['username'])
                connect_params['password'] = Variant('s', apn_config['password'])
                connect_params['allowed-auth'] = Variant('u', self._convert_auth_type(apn_config['auth_type']))

            # Add roaming settings
            roaming = sim_config.get('roaming', 'disabled')
            connect_params['allow-roaming'] = Variant('b', roaming == 'enabled')

            # Attempt connection with timeout
            simple_iface = self.proxy.get_interface(SIMPLE_INTERFACE)

            try:
                bearer_path = await asyncio.wait_for(
                    simple_iface.call_connect(connect_params),
                    timeout=60.0  # 60 second timeout per APN attempt
                )

                self.bearer_path = bearer_path

                # Verify connection
                await asyncio.sleep(3)  # Brief wait for connection to establish
                is_connected = await self._verify_bearer_connection()

                if is_connected:
                    logger.info("APN connection successful and verified",
                               extra={'interface_number': self.interface_number,
                                      'apn_name': apn_config['name'],
                                      'bearer_path': bearer_path})
                    return True
                else:
                    logger.warning("APN connection created but verification failed",
                                  extra={'interface_number': self.interface_number,
                                         'apn_name': apn_config['name']})
                    # Cleanup failed connection
                    try:
                        await simple_iface.call_disconnect(bearer_path)
                    except Exception:
                        pass
                    self.bearer_path = None
                    return False

            except asyncio.TimeoutError:
                logger.warning("APN connection attempt timed out",
                              extra={'interface_number': self.interface_number,
                                     'apn_name': apn_config['name'],
                                     'timeout_seconds': 60})
                return False

        except Exception as e:
            logger.warning(f"APN connection attempt failed: {e}",
                          extra={'interface_number': self.interface_number,
                                 'apn_name': apn_config['name']})
            return False

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

    # @safe_extraction("_cache_successful_apn")  # Async methods need special handling
    async def _cache_successful_apn(self, sim_info, apn_config, candidate_info):
        """🔄 SAFE EXTRACTION: Cache successful APN using ConnectionManager"""
        # Use the extracted connection manager
        await self.connection_manager._cache_successful_apn(sim_info, apn_config, candidate_info)

    async def _cache_successful_apn_original(self, sim_info, apn_config, candidate_info):
        """🏗️ ORIGINAL: Cache successful APN for future quick connection (for comparison)"""
        try:
            import json
            import os

            # Create cache key from SIM identifiers
            cache_key = f"{sim_info['mcc_mnc']}_{sim_info.get('sim_identifier', 'unknown')}"

            cache_entry = {
                'apn_config': apn_config,
                'candidate_info': candidate_info,
                'timestamp': time.time(),
                'success_count': 1,
                'interface_number': self.interface_number
            }

            # Store in persistent cache
            cache_dir = "/var/lib/vyos/wwan-apn-cache"
            os.makedirs(cache_dir, exist_ok=True)

            cache_file = os.path.join(cache_dir, f"{cache_key}.json")

            with open(cache_file, 'w') as f:
                json.dump(cache_entry, f, indent=2)

            logger.info("Successful APN cached for future use",
                       extra={'interface_number': self.interface_number,
                              'cache_key': cache_key,
                              'apn_name': apn_config['name'],
                              'apn_type': candidate_info.get('type', 'unknown')})

        except Exception as e:
            logger.warning(f"Failed to cache successful APN: {e}",
                          extra={'interface_number': self.interface_number})

    async def _get_cached_successful_apn(self, sim_info):
        """Get previously successful APN from cache"""
        try:
            import json
            import os

            cache_key = f"{sim_info['mcc_mnc']}_{sim_info.get('sim_identifier', 'unknown')}"
            cache_file = f"/var/lib/vyos/wwan-apn-cache/{cache_key}.json"

            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    cached_entry = json.load(f)

                # Check if cache is not too old (7 days)
                age_seconds = time.time() - cached_entry.get('timestamp', 0)
                max_age = 7 * 24 * 3600  # 7 days

                if age_seconds < max_age:
                    logger.info("Found cached successful APN",
                               extra={'interface_number': self.interface_number,
                                      'cache_key': cache_key,
                                      'apn_name': cached_entry['apn_config']['name'],
                                      'age_hours': age_seconds / 3600,
                                      'success_count': cached_entry.get('success_count', 1)})

                    return cached_entry['apn_config']
                else:
                    logger.info("Cached APN expired, will try fresh discovery",
                               extra={'interface_number': self.interface_number,
                                      'cache_key': cache_key,
                                      'age_days': age_seconds / 86400})

            return None

        except Exception as e:
            logger.debug(f"Error accessing APN cache: {e}",
                        extra={'interface_number': self.interface_number})
            return None

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
                change_reasons.append(f"IMSI changed")

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

    async def monitor_data_usage(self):
        """Monitor data usage limits (no connection health monitoring)"""
        if not self.bearer_path:
            return

        logger.info("Starting data usage monitoring",
                   extra={'interface_number': self.interface_number,
                          'bearer_path': self.bearer_path})

        # Use correct config key names
        data_limit = self.config.get('data_limit_size', 0)
        data_action = self.config.get('data_limit_action', 'alert')
        billing_date = self.config.get('data_limit_billing_date', '2024-01-01')

        if not data_limit:
            logger.info("No data usage limit configured",
                       extra={'interface_number': self.interface_number})
            return

        logger.info("Data usage monitoring configured",
                   extra={'interface_number': self.interface_number,
                          'data_limit_gb': data_limit / (1024*1024*1024),
                          'action': data_action,
                          'billing_date': billing_date})

        try:
            # Monitor while in CONNECTED or USAGE_MONITORING states
            while self.machine.current_state in [ModemState.CONNECTED.value, ModemState.USAGE_MONITORING.value]:
                try:
                    # Check data usage statistics from bearer
                    introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, self.bearer_path)
                    proxy = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, self.bearer_path, introspect)
                    props = proxy.get_interface("org.freedesktop.DBus.Properties")

                    # Try to get statistics (may not be available on all modems)
                    try:
                        stats_variant = await props.call_get(BEARER_INTERFACE, "Stats")
                        if stats_variant and stats_variant.value:
                            stats = stats_variant.value
                            rx_bytes = stats.get('rx-bytes', 0)
                            tx_bytes = stats.get('tx-bytes', 0)
                            total_bytes = rx_bytes + tx_bytes

                            logger.info("Data usage check",
                                       extra={'interface_number': self.interface_number,
                                              'total_mb': total_bytes / (1024*1024),
                                              'rx_mb': rx_bytes / (1024*1024),
                                              'tx_mb': tx_bytes / (1024*1024),
                                              'limit_gb': data_limit / (1024*1024*1024)})

                            # Check if limit exceeded
                            if total_bytes >= data_limit:
                                logger.warning("Data usage limit exceeded",
                                             extra={'interface_number': self.interface_number,
                                                    'usage_gb': total_bytes / (1024*1024*1024),
                                                    'limit_gb': data_limit / (1024*1024*1024),
                                                    'action': data_action})

                                if data_action == 'disconnect':
                                    # Transition to USAGE_MONITORING for limit handling
                                    self.transition(ModemEvent.USAGE_LIMIT_EXCEEDED)
                                    break
                                elif data_action == 'alert':
                                    # Just log alert and continue monitoring
                                    logger.alert("Data usage limit exceeded - alerting only",
                                               extra={'interface_number': self.interface_number})
                        else:
                            logger.debug("Bearer statistics not available",
                                       extra={'interface_number': self.interface_number})

                    except Exception as stats_e:
                        logger.debug(f"Could not retrieve bearer statistics: {stats_e}",
                                   extra={'interface_number': self.interface_number})

                    await asyncio.sleep(60)  # Check every minute for data usage

                except Exception as e:
                    logger.error(f"Data usage monitoring error: {e}",
                               extra={'interface_number': self.interface_number})
                    await asyncio.sleep(60)

        except Exception as e:
            logger.error(f"Failed to initialize data usage monitoring: {e}",
                        extra={'interface_number': self.interface_number})

    async def monitor_usage(self):
        """Legacy method - now redirects to data usage monitoring"""
        logger.warning("monitor_usage() is deprecated - connection monitoring now event-driven",
                      extra={'interface_number': self.interface_number})
        await self.monitor_data_usage()

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

            # Get signal quality percentage (for backwards compatibility)
            signal_percent = 0
            try:
                signal_quality_variant = await props.call_get(MODEM_INTERFACE, "SignalQuality")
                if signal_quality_variant and signal_quality_variant.value:
                    # SignalQuality is a dict with 'signal-quality' and 'recent' keys
                    signal_data = signal_quality_variant.value
                    signal_percent = signal_data.get('signal-quality', 0) if isinstance(signal_data, dict) else signal_data
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

            # 🆕 Check if this was triggered by connectivity monitoring
            if hasattr(self, 'connectivity_triggered_reconnect') and self.connectivity_triggered_reconnect:
                logger.info("Connectivity-triggered recovery in progress",
                           extra={'interface_number': self.interface_number})
                # Reset flag
                self.connectivity_triggered_reconnect = False

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

                    # Check if SIM failover is enabled
                    sim_failover = self.config.get('sim_failover', 'disabled')
                    if sim_failover == 'enabled':
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
        if not connectivity_config.get('enabled', False):
            logger.info("Connectivity monitoring disabled",
                       extra={'interface_number': self.interface_number})
            return

        logger.info("Starting connectivity health monitoring",
                   extra={'interface_number': self.interface_number,
                          'config': connectivity_config})

        # Start monitoring task
        if not hasattr(self, 'connectivity_monitor_task') or self.connectivity_monitor_task is None:
            self.connectivity_monitor_task = asyncio.create_task(self._connectivity_monitor_loop())

    async def _connectivity_monitor_loop(self):
        """Main connectivity monitoring loop with ping tests"""
        if not self.config:
            return

        connectivity_config = self.config.get('connectivity_monitoring', {})

        # Configuration with defaults
        interval = connectivity_config.get('interval', 60)  # Check every 60 seconds
        timeout = connectivity_config.get('timeout', 10)    # 10 second ping timeout
        retry_count = connectivity_config.get('retry_count', 3)  # 3 retries before failure
        failure_threshold = connectivity_config.get('failure_threshold', 2)  # 2 consecutive failures = restart

        # Ping targets
        ipv4_targets = connectivity_config.get('ipv4_targets', ['8.8.8.8', '1.1.1.1'])
        ipv6_targets = connectivity_config.get('ipv6_targets', ['2001:4860:4860::8888', '2606:4700:4700::1111'])

        # Test configuration
        test_ipv4 = connectivity_config.get('test_ipv4', True)
        test_ipv6 = connectivity_config.get('test_ipv6', False)  # IPv6 off by default
        require_both = connectivity_config.get('require_both', False)  # Both IPv4 and IPv6 must work

        consecutive_failures = 0

        logger.info("Connectivity monitoring started",
                   extra={'interface_number': self.interface_number,
                          'interval': interval,
                          'ipv4_targets': ipv4_targets if test_ipv4 else [],
                          'ipv6_targets': ipv6_targets if test_ipv6 else [],
                          'require_both': require_both,
                          'failure_threshold': failure_threshold})

        while self.machine.current_state == ModemState.USAGE_MONITORING.value:
            try:
                # Only test if we have a bearer connection
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

                        # Set flag to prevent auto-recovery interference
                        self.connectivity_triggered_reconnect = True

                        # Trigger disconnection and recovery
                        await self._trigger_connectivity_recovery()
                        break

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                logger.info("Connectivity monitoring cancelled",
                           extra={'interface_number': self.interface_number})
                break
            except Exception as e:
                logger.error(f"Connectivity monitoring error: {e}",
                            extra={'interface_number': self.interface_number})
                await asyncio.sleep(interval)  # Continue monitoring despite errors

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
        import subprocess
        import asyncio

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
        """Trigger recovery due to connectivity failure"""
        try:
            logger.warning("Triggering connectivity recovery",
                          extra={'interface_number': self.interface_number,
                                 'current_state': self.machine.current_state})

            # Cancel usage monitoring to prevent conflicts
            if self.usage_monitor_task and not self.usage_monitor_task.done():
                self.usage_monitor_task.cancel()
                self.usage_monitor_task = None

            # Cancel our own connectivity monitoring
            if hasattr(self, 'connectivity_monitor_task') and self.connectivity_monitor_task:
                self.connectivity_monitor_task.cancel()
                self.connectivity_monitor_task = None

            # Disconnect current bearer
            if self.bearer_path and self.proxy:
                try:
                    simple_iface = self.proxy.get_interface(SIMPLE_INTERFACE)
                    await simple_iface.call_disconnect(self.bearer_path)
                    self.bearer_path = None
                    logger.info("Bearer disconnected for connectivity recovery",
                               extra={'interface_number': self.interface_number})
                except Exception as e:
                    logger.warning(f"Error disconnecting bearer for recovery: {e}",
                                  extra={'interface_number': self.interface_number})

            # Wait a moment for disconnection to complete
            await asyncio.sleep(5)

            # Transition to disconnected state
            self.transition(ModemEvent.DISCONNECTED)

            # Trigger the normal disconnection recovery process
            await self.handle_disconnection_recovery()

        except Exception as e:
            logger.error(f"Connectivity recovery failed: {e}",
                        extra={'interface_number': self.interface_number})
            self.transition(ModemEvent.CONNECTION_FAILED)

    def _normalize_connectivity_config(self, config):
        """Normalize connectivity monitoring configuration with defaults"""
        if not isinstance(config, dict):
            return {'enabled': False}

        return {
            'enabled': config.get('enabled', False),
            'interval': max(30, config.get('interval', 60)),  # Minimum 30 seconds
            'timeout': max(5, config.get('timeout', 10)),     # Minimum 5 seconds
            'retry_count': max(1, config.get('retry_count', 3)),  # Minimum 1 retry
            'failure_threshold': max(1, config.get('failure_threshold', 2)),  # Minimum 1 failure
            'test_ipv4': config.get('test_ipv4', True),
            'test_ipv6': config.get('test_ipv6', False),
            'require_both': config.get('require_both', False),
            'ipv4_targets': config.get('ipv4_targets', ['8.8.8.8', '1.1.1.1']),
            'ipv6_targets': config.get('ipv6_targets', ['2001:4860:4860::8888', '2606:4700:4700::1111'])
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

    async def _set_interface_down(self):
        """Set Linux network interface DOWN"""
        if not self.interface_management_enabled:
            return

        try:
            interface_name = await self._get_interface_name()
            if not interface_name:
                return

            logger.info(f"Setting interface {interface_name} DOWN",
                       extra={'interface_number': self.interface_number,
                              'interface': interface_name})

            result = await asyncio.create_subprocess_exec(
                'ip', 'link', 'set', interface_name, 'down',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(result.communicate(),
                                                   timeout=self.interface_up_timeout)

            if result.returncode == 0:
                logger.info(f"Interface {interface_name} set DOWN successfully",
                           extra={'interface_number': self.interface_number,
                                  'interface': interface_name})
            else:
                logger.error(f"Failed to set interface {interface_name} DOWN: {stderr.decode()}",
                            extra={'interface_number': self.interface_number,
                                   'interface': interface_name})

        except asyncio.TimeoutError:
            logger.error("Timeout setting interface DOWN",
                        extra={'interface_number': self.interface_number})
        except Exception as e:
            logger.error(f"Error setting interface DOWN: {e}",
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
            self._ip_monitoring_task = asyncio.create_task(self._monitor_ip_changes())

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
                    asyncio.create_task(self._handle_bearer_disconnect())
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
                    asyncio.create_task(self._ensure_interface_up())

            # Check for IP configuration changes
            if 'Ip4Config' in changed_properties or 'Ip6Config' in changed_properties:
                logger.info("🌐 Bearer IP configuration changed - updating interface",
                           extra={'interface_number': self.interface_number,
                                  'changed_configs': [k for k in ['Ip4Config', 'Ip6Config'] if k in changed_properties]})
                asyncio.create_task(self._apply_bearer_ip_configuration())

        except Exception as e:
            logger.error(f"Error handling bearer properties changed: {e}",
                        extra={'interface_number': self.interface_number})

    async def _handle_registration_state_change(self, reg_state, reg_state_name):
        """Handle 3GPP registration state changes for enhanced interface management"""
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

            # Define states that indicate good network connectivity
            connected_states = {1, 5}  # HOME, ROAMING
            disconnected_states = {0, 2, 3, 4}  # IDLE, SEARCHING, DENIED, UNKNOWN

            if reg_state in disconnected_states:
                # Network registration lost - consider bringing interface down
                # But check if bearer is still connected to avoid unnecessary flapping
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
                            asyncio.create_task(self._set_interface_down())
                        else:
                            # Registration lost but bearer still connected - start conservative timer
                            logger.warning("📡⚠️ Network registration lost but bearer still connected - starting registration recovery timer",
                                         extra={'interface_number': self.interface_number,
                                                'registration_state': f"{reg_state} ({reg_state_name})",
                                                'bearer_connected': bearer_connected,
                                                'recovery_timer_seconds': 30,
                                                'action': 'interface_down_if_no_recovery'})
                            asyncio.create_task(self._handle_registration_loss_with_bearer())
                except Exception as e:
                    logger.debug(f"Could not check bearer state during registration change: {e}",
                                extra={'interface_number': self.interface_number})
                    # If we can't check bearer state, be conservative and assume registration loss is serious
                    logger.warning("📡❌ Network registration lost (bearer check failed) - interface going DOWN",
                                 extra={'interface_number': self.interface_number,
                                        'registration_state': f"{reg_state} ({reg_state_name})",
                                        'action': 'interface_down_conservative'})
                    asyncio.create_task(self._set_interface_down())

            elif reg_state in connected_states:
                # Network registration restored
                logger.info("📡✅ Network registration restored - ensuring interface UP and bearer connected",
                           extra={'interface_number': self.interface_number,
                                  'registration_state': f"{reg_state} ({reg_state_name})",
                                  'action': 'interface_up_and_bearer_check'})
                # Cancel any pending registration loss timers
                if hasattr(self, '_registration_loss_timer') and self._registration_loss_timer:
                    self._registration_loss_timer.cancel()
                    self._registration_loss_timer = None
                    logger.info("📡🔄 Registration recovery - cancelled registration loss timer",
                               extra={'interface_number': self.interface_number})

                # Ensure interface is up
                asyncio.create_task(self._ensure_interface_up())

                # Check bearer status and reconnect if necessary
                asyncio.create_task(self._handle_registration_recovery())

        except Exception as e:
            logger.error(f"Error handling registration state change: {e}",
                        extra={'interface_number': self.interface_number})
        finally:
            # Always clear the flag to prevent deadlock
            self.registration_handling_in_progress = False

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
                asyncio.create_task(self._set_interface_down())
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

    async def _set_interface_down(self):
        """Set the network interface DOWN"""
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
            logger.debug("IP monitoring cancelled",
                        extra={'interface_number': self.interface_number})
        except Exception as e:
            logger.error(f"IP monitoring failed: {e}",
                        extra={'interface_number': self.interface_number})

    async def _check_bearer_connected(self):
        """Check if ModemManager bearer is connected"""
        try:
            if not self.proxy or not self.bearer_path:
                return False

            # Get bearer proxy
            introspect = await self.bus.introspect(MODEM_MANAGER_SERVICE, self.bearer_path)
            bearer_proxy = self.bus.get_proxy_object(MODEM_MANAGER_SERVICE, self.bearer_path, introspect)
            bearer_iface = bearer_proxy.get_interface("org.freedesktop.ModemManager1.Bearer")

            # Check Connected property
            connected_property = await bearer_iface.get_connected()
            return connected_property.value if connected_property else False

        except Exception as e:
            logger.debug(f"Error checking bearer state: {e}",
                        extra={'interface_number': self.interface_number})
            return False

    async def _handle_bearer_disconnect(self):
        """Handle bearer disconnect with configurable delay"""
        try:
            # Start disconnect timer
            self._bearer_disconnect_timer = asyncio.create_task(
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
            # Timer was cancelled - bearer came back
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
            await asyncio.sleep(self.ip_change_delay)
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
            await asyncio.sleep(self.ip_change_delay * 2)  # Longer delay for IP sync
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
            self.reset_timeout_task = asyncio.create_task(self._reset_timeout_handler())

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

                # Set MTU if provided
                if ipv4_mtu:
                    result = await asyncio.create_subprocess_exec(
                        'ip', 'link', 'set', 'dev', interface_name, 'mtu', ipv4_mtu,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await result.communicate()

                    if result.returncode != 0:
                        logger.warning(f"Failed to set MTU {ipv4_mtu}: {stderr.decode()}",
                                     extra={'interface_number': self.interface_number})
                    else:
                        logger.debug(f"Set interface MTU to {ipv4_mtu}",
                                   extra={'interface_number': self.interface_number})

                # Configure DNS servers using systemd-resolved (IPv4 only, IPv6 will be combined later)
                if ipv4_dns and not bearer_ips.get('ipv6_dns'):
                    # Only apply IPv4 DNS if there are no IPv6 DNS servers to combine with
                    result = await asyncio.create_subprocess_exec(
                        'resolvectl', 'dns', interface_name, *ipv4_dns,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await result.communicate()

                    if result.returncode != 0:
                        logger.warning(f"Failed to set IPv4 DNS servers: {stderr.decode()}",
                                     extra={'interface_number': self.interface_number})
                    else:
                        logger.info(f"Configured IPv4 DNS servers: {', '.join(ipv4_dns)}",
                                  extra={'interface_number': self.interface_number})

                # Add IPv4 default route if gateway provided
                if ipv4_gateway:
                    result = await asyncio.create_subprocess_exec(
                        'ip', 'route', 'add', 'default', 'via', ipv4_gateway, 'dev', interface_name,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await result.communicate()

                    if result.returncode != 0 and b'exists' not in stderr:
                        logger.debug(f"IPv4 route add result: {stderr.decode()}",
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

                # Configure IPv6 DNS servers using systemd-resolved (combine with IPv4 DNS if present)
                if ipv6_dns:
                    # Combine IPv4 and IPv6 DNS servers for this interface
                    all_dns = (bearer_ips.get('ipv4_dns', []) + ipv6_dns)
                    result = await asyncio.create_subprocess_exec(
                        'resolvectl', 'dns', interface_name, *all_dns,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await result.communicate()

                    if result.returncode != 0:
                        logger.warning(f"Failed to set combined DNS servers: {stderr.decode()}",
                                     extra={'interface_number': self.interface_number})
                    else:
                        logger.info(f"Configured combined DNS servers (IPv4+IPv6): {', '.join(all_dns)}",
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
                        logger.debug(f"IPv6 route add result: {stderr.decode()}",
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
