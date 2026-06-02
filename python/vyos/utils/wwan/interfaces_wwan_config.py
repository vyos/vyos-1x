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
import re
from dbus_next.service import ServiceInterface, method  # pylint: disable=import-error
from dbus_next.errors import DBusError  # pylint: disable=import-error
from dbus_next import Variant  # pylint: disable=import-error
from vyos.utils.wwan.wwan_logging import setup_logging


def resolve_carrier_code(carrier_input):
    """Classify a user-supplied preferred-carrier value.

    No name-to-code mapping is performed — that responsibility belongs to
    the modem / ModemManager network-scan results, not to a hardcoded
    static table.  This function only distinguishes a numeric MCCMNC
    operator code from a free-form carrier name and forwards the value
    unchanged.

    Args:
        carrier_input: User input — either a numeric MCCMNC code
            (e.g. ``"310260"``) or a free-form carrier name passed to
            ModemManager for network selection.

    Returns:
        tuple: ``(value, display_name, is_code)`` where ``is_code`` is
        ``True`` when the input is a 5+ digit numeric MCCMNC code.
    """
    if not carrier_input:
        return '', '', False

    carrier_clean = carrier_input.strip()

    # Numeric MCCMNC code (typically 5 or 6 digits: 3-digit MCC + 2/3-digit MNC)
    if carrier_clean.isdigit() and len(carrier_clean) >= 5:
        return carrier_clean, f"Operator Code {carrier_clean}", True

    # Free-form name — forward to ModemManager unchanged
    return carrier_clean, carrier_clean, False

logger = setup_logging(__name__, "wwan-config")

class InterfaceConfig(ServiceInterface):
    # Cache schema version — bump this whenever the on-disk JSON layout
    # changes incompatibly (renamed/removed/retyped keys, new required
    # fields, etc.).  At startup _restore_configuration() refuses to
    # replay any cache file whose `__schema_version__` does not match —
    # which prevents a freshly-upgraded service from trying to apply a
    # stale dict shaped for the previous code version.  The cache lives
    # in /run/wwan (tmpfs) so this only matters across service restarts
    # within the same boot — across reboots the cache is empty anyway.
    SCHEMA_VERSION = 1

    # Centralized default configuration values
    DEFAULT_CONFIG = {
        # Interface-level settings
        "interface_disabled": False,  # Admin disable — disconnect modem and suppress all activity
        "connection_mode": "always-on",  # always-on | connect-on-demand | dial-on-demand
        "primary_sim_slot": 1,  # Which SIM slot to use (1 or 2)

        # MTU settings — interface-level ceiling/default; per-SIM override in sim_slots
        "mtu": 1420,  # Interface MTU ceiling; also used as fallback when bearer provides none

        # APN discovery settings
        "android_apn_discovery": "disabled",

        # SIM failover settings (global enable + policy)
        "sim_failover": "enabled",
        "sim_failover_connect_retries": 3,
        "sim_failover_revert_timer": 300,
        "sim_failover_signal_loss_timer": 60,
        "sim_failover_signal_threshold": -90,

        # SIM failback settings
        "sim_failback_enabled": True,
        "sim_failback_check_interval": 600,

        # Data usage settings (per-SIM only; no global defaults needed)
        "data_usage_monitoring_interval": 30,

        # Hardware management settings
        "hardware_reset_enabled": True,
        "max_hardware_resets": 3,
        "hardware_reset_cooldown": 300,

        # Connection and timeout settings
        "connection_timeout": 120,
        "registration_timeout": 180,
        "network_scan_timeout": 60,
        "network_mode": "auto",

        # Monitoring intervals
        "normal_monitoring_interval": 30,

        # Logging settings
        "verbose_logging": True,
        "log_level": "info",
        "log_sink": "both",

        # Enhanced reconnection settings
        "enhanced_reconnection": {
            "enabled": True,
            "signal_threshold": -85,
            "retry_interval_good_signal": 30,
            "retry_interval_poor_signal": 120,
            "max_wait_for_signal": 120,
            "signal_check_interval": 10,
            "signal_strength_buffer": 5
        },

        # Connectivity monitoring settings
        "connectivity_monitoring": {
            "enabled": True,
            "interval": 60,
            "timeout": 10,
            "retry_count": 3,
            "failure_threshold": 2,
            "test_ipv4": True,
            "test_ipv6": False,
            "require_both": False,
            "ipv4_targets": ["8.8.8.8", "1.1.1.1"],
            "ipv6_targets": ["2001:4860:4860::8888", "2606:4700:4700::1111"]
        },

        # Network interface management settings
        "interface_management": {
            "enabled": True,                    # Enable network interface management
            "bearer_disconnect_delay": 15,      # Wait time before link down on bearer loss (seconds)
            "registration_recovery_delay": 20,  # Debounce delay before acting on registration loss (seconds)
            "registration_flap_count": 5,          # Number of registration losses within window to trigger SIM failover
            "registration_flap_window": 360,        # Time window (seconds) in which flap_count losses trigger failover
            "ip_change_delay": 500,            # Brief delay for IP change link cycling (milliseconds)
            "ensure_link_up_on_connect": True, # Ensure interface UP when entering CONNECTED state
            "monitor_bearer_state": True,      # Monitor ModemManager bearer state changes
            "monitor_ip_changes": True,        # Monitor for carrier IP address reassignments
            "interface_up_timeout": 10,        # Timeout for interface up/down operations (seconds)
        },

        # Failed-state periodic retry settings
        "failed_retry": {
            "enabled": True,                          # Enable automatic retry from FAILED state
            "intervals": [600, 1800, 3600, 7200],      # Backoff intervals in seconds (10, 30, 60, 120 min) — carrier-friendly
            "max_interval": 7200,                      # Cap interval once list is exhausted (2 hr, carrier-friendly)
            "escalation_threshold": 3,                 # Consecutive failures before disable/enable cycle (0 = disabled)
        },

        # IPv6 bridging — hand the carrier-supplied /64 to one downstream LAN
        # interface (NOT DHCPv6 PD).  For real PD, use the standard VyOS
        # 'dhcpv6-options pd' tree (handled by dhcp6c via Interface.update()).
        "ipv6_bridging": {
            "enabled": False,
            "interface": "",
            "reconciliation_interval": 10,    # Seconds between safety-net re-checks
        },

        # IP Passthrough (DOCSIS-modem-style) — hand carrier IP to one
        # downstream device via dnsmasq on a designated LAN interface.
        # Empty / enabled=False = disabled; populated by conf_mode when the
        # user sets `interfaces wwan <if> ip-passthrough interface <lan>`.
        "ip_passthrough": {"enabled": False},

        # DHCPv6 PD enabled — set by conf_mode when the user configures
        # `interfaces wwan <if> dhcpv6-options pd ...`.  Controls whether
        # the FSM-installed IPv6 egress hygiene chain permits DHCPv6
        # client traffic (UDP/546) on the bearer.  Default OFF: cellular
        # bearers do not run DHCPv6 unless the operator explicitly opts
        # in via PD.
        "dhcpv6_pd_enabled": False,

        # SIM configurations - array of SIM configs
        "sim_slots": [
            {
                "slot": 1,
                "enabled": True,
                "roaming": "enabled",
                "preferred_carrier": "",
                "enable_network_scan": False,  # Control scanning behavior for carrier selection
                "supported_bands": ["all"],
                "pdp_type": "ipv4v6",
                # Enhanced APN configuration - supports both formats
                "apn": {
                    "name": "",              # APN name (e.g., "internet.t-mobile.com")
                    "username": "",          # Optional username for authentication
                    "password": "",          # Optional password for authentication
                    "auth_type": "none"      # "none", "pap", "chap", or "pap-chap"
                },
                "pin": "",           # SIM PIN (if set, FSM auto-unlocks)
                "puk": "",           # SIM PUK (used with PIN for auto-recovery)
                "iccid": "",         # Expected ICCID — if set, slot rejects any other SIM (tamper lock)
                "mtu": 0,            # Per-SIM MTU override (0 = use interface mtu)
                # Per-SIM data usage limits
                "data_limit_size": 0,            # Bytes (0 = unlimited)
                "data_limit_action": "none",      # none, disable, sim-failover, sim-failover-sticky
                "data_limit_warning": [],          # Pct thresholds, e.g. [75, 90, 95] (empty = no warnings)
                "data_limit_billing_date": 1      # Day of month (1-28) for usage reset
            },
            {
                "slot": 2,
                "enabled": True,
                "roaming": "enabled",
                "preferred_carrier": "",
                "enable_network_scan": False,  # Control scanning behavior for carrier selection
                "supported_bands": ["all"],
                "pdp_type": "ipv4v6",
                "apn": {
                    "name": "",
                    "username": "",
                    "password": "",
                    "auth_type": "none"
                },
                "pin": "",           # SIM PIN (if set, FSM auto-unlocks)
                "puk": "",           # SIM PUK (used with PIN for auto-recovery)
                "iccid": "",         # Expected ICCID — if set, slot rejects any other SIM (tamper lock)
                "mtu": 0,            # Per-SIM MTU override (0 = use interface mtu)
                # Per-SIM data usage limits
                "data_limit_size": 0,            # Bytes (0 = unlimited)
                "data_limit_action": "none",      # none, disable, sim-failover, sim-failover-sticky
                "data_limit_warning": [],          # Pct thresholds, e.g. [75, 90, 95] (empty = no warnings)
                "data_limit_billing_date": 1      # Day of month (1-28) for usage reset
            }
        ]
    }

    def __init__(self, interface_number: int, fsm):
        super().__init__("com.igos.IgosModemManager.Interface")
        self.interface_number = interface_number
        self.fsm = fsm
        self._restored_runtime_state = {}

        # Configuration persistence (only for service crashes, not across reboots)
        self.config_state_dir = "/run/wwan"  # /run is tmpfs, cleared on boot
        self.config_state_file = f"{self.config_state_dir}/interface{interface_number}.conf"

        # Try to restore configuration on startup
        self._restore_configuration()

    def _save_configuration(self, config_dict):
        """Save configuration to persistent storage (atomic write)"""
        try:
            import os
            import json
            import tempfile

            # Create state directory if it doesn't exist
            os.makedirs(self.config_state_dir, exist_ok=True)

            # Create JSON-safe copy of configuration
            json_safe_config = {}
            for key, value in config_dict.items():
                try:
                    # Test if value is JSON serializable
                    json.dumps(value)
                    json_safe_config[key] = value
                except (TypeError, ValueError):
                    # Convert complex objects to string representation
                    json_safe_config[key] = str(value)

            # Preserve runtime state section across config rewrites
            runtime_state = {}
            if os.path.exists(self.config_state_file):
                try:
                    with open(self.config_state_file, 'r') as f:
                        existing = json.load(f)
                    runtime_state = existing.get('__runtime_state__', {})
                except Exception:
                    runtime_state = {}

            json_safe_config['__runtime_state__'] = runtime_state
            # Stamp the cache schema so a future service restart can
            # detect on-disk-vs-code drift and refuse the replay cleanly
            # instead of partially applying a wrong-shaped dict.
            json_safe_config['__schema_version__'] = self.SCHEMA_VERSION

            # Atomic write: write to temp file then rename so a crash
            # mid-write never leaves a truncated/corrupt config file.
            fd, tmp_path = tempfile.mkstemp(
                dir=self.config_state_dir, suffix='.tmp'
            )
            try:
                with os.fdopen(fd, 'w') as f:
                    json.dump(json_safe_config, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, self.config_state_file)
            except BaseException:
                # Clean up temp file on any failure
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

            logger.info("Configuration saved to persistent storage",
                       extra={'interface_number': self.interface_number,
                              'config_file': self.config_state_file,
                              'config_keys': list(json_safe_config.keys())})
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}",
                        extra={'interface_number': self.interface_number})
            import traceback
            logger.error(f"Save traceback: {traceback.format_exc()}")

    def _save_runtime_state(self):
        """Persist runtime state (e.g. user disconnect hold) for crash recovery."""
        try:
            import os
            import json
            import tempfile

            os.makedirs(self.config_state_dir, exist_ok=True)

            state_doc = {}
            if os.path.exists(self.config_state_file):
                try:
                    with open(self.config_state_file, 'r') as f:
                        state_doc = json.load(f)
                except Exception:
                    state_doc = {}

            runtime_state = {
                'user_disconnected': bool(getattr(self.fsm, 'user_disconnected', False)),
                'connection_mode': str(getattr(self.fsm, 'connection_mode', 'always-on')),
            }
            state_doc['__runtime_state__'] = runtime_state

            fd, tmp_path = tempfile.mkstemp(dir=self.config_state_dir, suffix='.tmp')
            try:
                with os.fdopen(fd, 'w') as f:
                    json.dump(state_doc, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, self.config_state_file)
            except BaseException:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

            logger.info("Runtime state saved",
                       extra={'interface_number': self.interface_number,
                              'user_disconnected': runtime_state['user_disconnected'],
                              'connection_mode': runtime_state['connection_mode']})
        except Exception as e:
            logger.error(f"Failed to save runtime state: {e}",
                        extra={'interface_number': self.interface_number})

    def _remove_configuration(self):
        """Remove configuration from persistent storage (called during interface removal)"""
        try:
            import os

            if os.path.exists(self.config_state_file):
                os.remove(self.config_state_file)
                logger.info("Configuration file removed from persistent storage",
                           extra={'interface_number': self.interface_number,
                                  'config_file': self.config_state_file})
            else:
                logger.debug("Configuration file already not present",
                            extra={'interface_number': self.interface_number,
                                   'config_file': self.config_state_file})
        except Exception as e:
            logger.error(f"Failed to remove configuration file: {e}",
                        extra={'interface_number': self.interface_number})

    def _quarantine_cache(self, reason: str) -> None:
        """Move the persisted cache aside as `<file>.bad` for forensics.

        Called whenever a restore is rejected (schema mismatch, validation
        failure, apply-time exception).  Renaming rather than deleting
        preserves the offending document for inspection.  Best-effort —
        a failure to rename simply leaves the file in place.
        """
        try:
            import os
            if not os.path.exists(self.config_state_file):
                return
            bad_path = self.config_state_file + '.bad'
            # If a previous .bad already exists, drop it — the most recent
            # failure is the most useful one to keep.
            try:
                if os.path.exists(bad_path):
                    os.remove(bad_path)
            except OSError:
                pass
            os.rename(self.config_state_file, bad_path)
            logger.error(
                f"Quarantined unusable cache: {reason}",
                extra={'interface_number': self.interface_number,
                       'config_file': self.config_state_file,
                       'quarantine_file': bad_path,
                       'reason': reason})
        except Exception as exc:
            logger.error(
                f"Failed to quarantine cache (leaving in place): {exc}",
                extra={'interface_number': self.interface_number})

    def _restore_configuration(self):
        """Restore configuration from persistent storage on service restart"""
        try:
            import os
            import json

            if not os.path.exists(self.config_state_file):
                logger.info("No saved configuration found",
                           extra={'interface_number': self.interface_number})
                return

            # Load configuration from JSON
            try:
                with open(self.config_state_file, 'r') as f:
                    saved_config = json.load(f)
            except (json.JSONDecodeError, ValueError) as je:
                logger.error(
                    f"Corrupt configuration file, quarantining: {je}",
                    extra={'interface_number': self.interface_number,
                           'config_file': self.config_state_file})
                self._quarantine_cache(f"corrupt json: {je}")
                return

            # Schema-version gate.  Cache files written by a previous
            # code version may have keys this version no longer expects
            # (or be missing keys it now requires).  Refuse to replay —
            # the FSM will sit in WAITING_FOR_CONFIG until a fresh CLI
            # commit arrives, which is the correct behaviour after an
            # upgrade.
            cache_schema = saved_config.get('__schema_version__')
            if cache_schema != self.SCHEMA_VERSION:
                logger.warning(
                    "Cache schema mismatch — refusing restore "
                    f"(cache={cache_schema!r}, code={self.SCHEMA_VERSION!r})",
                    extra={'interface_number': self.interface_number,
                           'config_file': self.config_state_file,
                           'cache_schema': cache_schema,
                           'code_schema': self.SCHEMA_VERSION})
                self._quarantine_cache(
                    f"schema mismatch: cache={cache_schema} code={self.SCHEMA_VERSION}"
                )
                return

            # Restore runtime state section separately (not part of SetConfiguration)
            self._restored_runtime_state = saved_config.pop('__runtime_state__', {}) or {}
            # Strip the schema marker before the config is handed to the
            # validator / FSM — it's metadata, not a configuration field.
            saved_config.pop('__schema_version__', None)

            # Validate-before-apply.  _validate_configuration() is the
            # only thing allowed to refuse a restore: if it passes here,
            # downstream apply MUST NOT raise.  Anything that does is a
            # code bug, not a cache problem — and is handled in
            # _apply_restored_config() by quarantining and logging.
            try:
                self._validate_configuration(saved_config)
            except Exception as ve:
                logger.error(
                    f"Restored configuration failed validation, quarantining: {ve}",
                    extra={'interface_number': self.interface_number,
                           'config_file': self.config_state_file})
                self._quarantine_cache(f"validation failed: {ve}")
                return

            logger.info("Restored configuration from persistent storage",
                       extra={'interface_number': self.interface_number,
                              'config_file': self.config_state_file})

            # Apply the restored configuration
            from dbus_next import Variant  # pylint: disable=import-error

            def _to_variant(val):
                """Recursively convert Python values to D-Bus Variants."""
                if isinstance(val, dict):
                    return Variant('a{sv}', {k: _to_variant(v) for k, v in val.items()})
                if isinstance(val, list):
                    if not val:
                        return Variant('as', [])
                    if all(isinstance(x, str) for x in val):
                        return Variant('as', val)
                    if all(isinstance(x, int) and not isinstance(x, bool) for x in val):
                        return Variant('ai', val)
                    if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in val):
                        return Variant('ad', [float(x) for x in val])
                    return Variant('av', [_to_variant(x) for x in val])
                if isinstance(val, bool):
                    return Variant('b', val)
                if isinstance(val, int):
                    if -2_147_483_648 <= val <= 2_147_483_647:
                        return Variant('i', val)
                    return Variant('x', val)
                if isinstance(val, float):
                    return Variant('d', val)
                if isinstance(val, str):
                    return Variant('s', val)
                return Variant('s', str(val))

            dbus_config = {k: _to_variant(v) for k, v in saved_config.items()}

            # Apply configuration asynchronously
            import asyncio
            task = asyncio.create_task(self._apply_restored_config(dbus_config))
            task.add_done_callback(self._restore_task_done)

        except Exception as e:
            logger.error(f"Failed to restore configuration: {e}",
                        extra={'interface_number': self.interface_number})

    def _restore_task_done(self, task):
        """Callback to log exceptions from the config-restore task."""
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.error(f"Restored-config task failed: {exc}",
                        extra={'interface_number': self.interface_number})

    async def _apply_restored_config(self, dbus_config):
        """Apply restored configuration asynchronously"""
        try:
            # Wait a moment for the service to be fully ready
            await asyncio.sleep(2)

            logger.info("Applying restored configuration",
                       extra={'interface_number': self.interface_number})

            # Apply the configuration
            await self.set_configuration(dbus_config)

            # Re-apply persisted runtime hold state (dial-on-demand manual disconnect)
            if isinstance(self._restored_runtime_state, dict):
                hold = bool(self._restored_runtime_state.get('user_disconnected', False))
                mode = str(getattr(self.fsm, 'connection_mode', 'always-on'))
                if hold and mode == 'dial-on-demand':
                    self.fsm.user_disconnected = True
                    logger.info("Restored dial-on-demand manual-disconnect hold from crash state",
                               extra={'interface_number': self.interface_number,
                                      'user_disconnected': True,
                                      'connection_mode': mode})
                else:
                    logger.debug("No runtime hold restoration needed",
                                extra={'interface_number': self.interface_number,
                                       'restored_hold': hold,
                                       'connection_mode': mode})

            logger.info("Restored configuration applied successfully",
                       extra={'interface_number': self.interface_number})

        except Exception as e:
            # If we reach here, validation passed in _restore_configuration()
            # but apply still raised — this is a code bug, not a cache
            # problem.  Log loud (full traceback + the offending dict),
            # quarantine the cache so the next service start does NOT
            # replay the same broken state, and leave the FSM in
            # whatever state it has now.  The FSM starts in
            # WAITING_FOR_CONFIG; if apply_config never completed cleanly
            # it has likely not progressed past that, and a fresh CLI
            # commit will push a known-good config.
            import traceback
            logger.error(
                f"Failed to apply restored configuration: {e}",
                extra={'interface_number': self.interface_number})
            logger.error(
                f"Apply-restored traceback: {traceback.format_exc()}",
                extra={'interface_number': self.interface_number})
            try:
                # Surface the dict we tried to apply (Variants → values)
                debug_cfg = {
                    k: self._extract_variant_value(v)
                    for k, v in dbus_config.items()
                }
                logger.info(
                    f"Apply-restored offending config: {debug_cfg}",
                    extra={'interface_number': self.interface_number})
            except Exception:
                pass
            self._quarantine_cache(f"apply raised: {e}")

    def _extract_variant_value(self, value):
        """Extract value from D-Bus Variant, handling nested structures"""
        from dbus_next.signature import Variant  # pylint: disable=import-error

        if isinstance(value, Variant):
            # Recursively extract the Variant's value
            return self._extract_variant_value(value.value)
        elif isinstance(value, dict):
            # Handle dict with Variant values
            return {k: self._extract_variant_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            # Handle list with Variant values
            return [self._extract_variant_value(item) for item in value]
        else:
            return value

    @method()
    async def set_configuration(self, config: 'a{sv}') -> 's':  # type: ignore[name-defined]  # noqa: F821, F722
        try:
            logger.info("Setting configuration",
                       extra={'interface_number': self.interface_number,
                              'config_keys': list(config.keys())})

            # Get current configuration from FSM, or use defaults if none exists
            current_cfg = getattr(self.fsm, 'config', {})
            if current_cfg is None:
                current_cfg = {}

            # Build configuration using current values, then new values, then defaults
            cfg = {}
            for key in self.DEFAULT_CONFIG:
                if key == "sim_slots":
                    # Handle SIM slots specially
                    cfg[key] = self._merge_sim_slots(
                        self._extract_variant_value(config.get(key)),
                        current_cfg.get(key),
                        self.DEFAULT_CONFIG[key]
                    )
                elif key == "connectivity_monitoring":
                    # Handle connectivity monitoring specially
                    cfg[key] = self._merge_connectivity_monitoring(
                        self._extract_variant_value(config.get(key)),
                        current_cfg.get(key),
                        self.DEFAULT_CONFIG[key]
                    )
                elif key == "enhanced_reconnection":
                    # Handle enhanced reconnection specially
                    cfg[key] = self._merge_enhanced_reconnection(
                        self._extract_variant_value(config.get(key)),
                        current_cfg.get(key),
                        self.DEFAULT_CONFIG[key]
                    )
                else:
                    # Extract Variant value for regular parameters
                    new_value = config.get(key)
                    if new_value is not None:
                        cfg[key] = self._extract_variant_value(new_value)
                    else:
                        cfg[key] = current_cfg.get(key, self.DEFAULT_CONFIG[key])

            # Validate the built configuration with Python values
            self._validate_configuration(cfg)

            # Apply configuration to FSM
            self.fsm.apply_config(cfg)

            # Save configuration for crash recovery
            self._save_configuration(cfg)

            logger.info("Configuration applied successfully",
                       extra={'interface_number': self.interface_number,
                              'config_keys': list(cfg.keys()),
                              'active_sim': cfg.get('primary_sim_slot', 1),
                              'connectivity_monitoring': cfg.get('connectivity_monitoring', {}).get('enabled', True)})
            return f"Configuration applied to interface {self.interface_number}"

        except ValueError as e:
            logger.error("Invalid parameter",
                        extra={'interface_number': self.interface_number,
                               'error': str(e)})
            raise DBusError("com.igos.IgosModemManager.InvalidParameter", str(e))
        except Exception as e:
            logger.error("Configuration error",
                        extra={'interface_number': self.interface_number,
                               'error': str(e)})
            raise DBusError("com.igos.IgosModemManager.ConfigurationError", str(e))

    def _merge_sim_slots(self, new_sim_slots, current_sim_slots, default_sim_slots):
        """Merge SIM slot configurations"""
        if not new_sim_slots:
            return current_sim_slots or default_sim_slots

        # Start with defaults
        merged_slots = []
        for default_slot in default_sim_slots:
            slot_num = default_slot['slot']

            # Find current config for this slot
            current_slot = None
            if current_sim_slots:
                current_slot = next((s for s in current_sim_slots if s['slot'] == slot_num), None)

            # Find new config for this slot
            new_slot = next((s for s in new_sim_slots if s['slot'] == slot_num), None)

            # Merge: new -> current -> default
            merged_slot = {}
            for key in default_slot:
                if key == 'apn':
                    # Special handling for APN configuration
                    merged_slot[key] = self._merge_apn_config(
                        new_slot.get(key) if new_slot else None,
                        current_slot.get(key) if current_slot else None,
                        default_slot[key]
                    )
                else:
                    # Use None-aware merge: prefer new, then current, then default.
                    # Plain 'or' would treat 0, False, '' as falsy and skip them.
                    new_val = new_slot.get(key) if new_slot else None
                    if new_val is not None:
                        merged_slot[key] = new_val
                    else:
                        cur_val = current_slot.get(key) if current_slot else None
                        if cur_val is not None:
                            merged_slot[key] = cur_val
                        else:
                            merged_slot[key] = default_slot[key]

            merged_slots.append(merged_slot)

        return merged_slots

    def _merge_apn_config(self, new_apn, current_apn, default_apn):
        """Merge APN configurations supporting both string and dict formats"""
        # Normalize all inputs to dict format
        new_apn_dict = self._normalize_apn_config(new_apn)
        current_apn_dict = self._normalize_apn_config(current_apn)
        default_apn_dict = self._normalize_apn_config(default_apn)

        # Merge: new -> current -> default
        merged_apn = {}
        for key in default_apn_dict:
            merged_apn[key] = (
                new_apn_dict.get(key) if new_apn_dict.get(key) else None
            ) or (
                current_apn_dict.get(key) if current_apn_dict.get(key) else None
            ) or default_apn_dict[key]

        return merged_apn

    def _normalize_apn_config(self, apn):
        """Normalize APN configuration to dict format"""
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

    def _merge_enhanced_reconnection(self, new_reconnection, current_reconnection, default_reconnection):
        """Merge enhanced reconnection configurations"""
        if not new_reconnection:
            return current_reconnection or default_reconnection

        # Start with default
        merged = default_reconnection.copy()

        # Apply current values
        if current_reconnection:
            merged.update(current_reconnection)

        # Apply new values
        merged.update(new_reconnection)

        return merged

    def _validate_configuration(self, config):
        """Validate configuration parameters before applying"""

        # Validate interface-level settings
        valid_modes = ['always-on', 'connect-on-demand', 'dial-on-demand']
        if 'connection_mode' in config and config['connection_mode'] not in valid_modes:
            logger.warning("Invalid connection_mode value",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'connection_mode'})
            raise ValueError(f"connection_mode must be one of {valid_modes}")

        # Validate active SIM slot
        if 'primary_sim_slot' in config:
            slot = config['primary_sim_slot']
            if not isinstance(slot, int) or slot not in [1, 2]:
                logger.warning("Invalid primary_sim_slot",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'primary_sim_slot'})
                raise ValueError("primary_sim_slot must be 1 or 2")

        # Validate interface-level MTU (ceiling / default)
        if 'mtu' in config:
            mtu = config['mtu']
            if not isinstance(mtu, int) or mtu < 576 or mtu > 9000:
                raise ValueError("mtu must be an integer between 576 and 9000")

        # Validate registration flap detection parameters
        if 'interface_management' in config and isinstance(config['interface_management'], dict):
            im = config['interface_management']
            if 'registration_flap_count' in im:
                val = int(im['registration_flap_count'])
                if val < 0:
                    raise ValueError("registration_flap_count must be >= 0 (0 = disabled)")
                im['registration_flap_count'] = val
            if 'registration_flap_window' in im:
                val = int(im['registration_flap_window'])
                if val < 1:
                    raise ValueError("registration_flap_window must be >= 1 second")
                im['registration_flap_window'] = val

        # Validate SIM failover
        if 'sim_failover' in config and config['sim_failover'] not in ['enabled', 'disabled']:
            logger.warning("Invalid sim_failover value",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'sim_failover'})
            raise ValueError("sim_failover must be 'enabled' or 'disabled'")

        # Validate and normalize SIM failback to boolean
        if 'sim_failback_enabled' in config:
            val = config['sim_failback_enabled']
            if val in (True, 'enabled'):
                config['sim_failback_enabled'] = True
            elif val in (False, 'disabled'):
                config['sim_failback_enabled'] = False
            else:
                logger.warning("Invalid sim_failback_enabled value",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_failback_enabled'})
                raise ValueError("sim_failback_enabled must be True/False or 'enabled'/'disabled'")

        if 'sim_failback_check_interval' in config:
            interval = config['sim_failback_check_interval']
            try:
                interval = int(interval)
                if interval < 60:
                    raise ValueError("sim_failback_check_interval must be at least 60 seconds")
            except (TypeError, ValueError) as e:
                logger.warning(f"Invalid sim_failback_check_interval: {e}",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_failback_check_interval'})
                raise ValueError("sim_failback_check_interval must be an integer >= 60")

        # Validate sim-failover policy

        # Validate SIM slots configuration
        if 'sim_slots' in config:
            sim_slots = config['sim_slots']
            if not isinstance(sim_slots, list):
                logger.warning("Invalid sim_slots type",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_slots'})
                raise ValueError("sim_slots must be a list")
            for sim_slot in sim_slots:
                self._validate_sim_slot(sim_slot)

       # Validate connectivity monitoring configuration
        if 'connectivity_monitoring' in config:
            self._validate_connectivity_monitoring(config['connectivity_monitoring'])

        # Validate other parameters (sim-failover timers, data limits, etc.)
        self._validate_other_parameters(config)

        logger.info("Configuration validation passed",
                   extra={'interface_number': self.interface_number,
                          'config_keys': list(config.keys())})

    def _validate_sim_slot(self, sim_slot):
        """Validate individual SIM slot configuration"""
        if not isinstance(sim_slot, dict):
            raise ValueError("Each SIM slot configuration must be a dictionary")

        # Validate slot number
        if 'slot' not in sim_slot:
            raise ValueError("SIM slot configuration must include 'slot' number")

        slot_num = sim_slot['slot']
        if not isinstance(slot_num, int) or slot_num not in [1, 2]:
            logger.warning("Invalid SIM slot number",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'sim_slots',
                                 'sim_slot': slot_num})
            raise ValueError("SIM slot number must be 1 or 2")

        # Validate enabled flag
        if 'enabled' in sim_slot and not isinstance(sim_slot['enabled'], bool):
            logger.warning("Invalid SIM enabled flag",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'sim_slots',
                                 'sim_slot': slot_num})
            raise ValueError(f"SIM{slot_num} enabled must be true or false")

        # Validate roaming
        if 'roaming' in sim_slot and sim_slot['roaming'] not in ['enabled', 'disabled']:
            logger.warning("Invalid SIM roaming value",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'sim_slots',
                                 'sim_slot': slot_num})
            raise ValueError(f"SIM{slot_num} roaming must be 'enabled' or 'disabled'")

        # Validate pdp_type
        if 'pdp_type' in sim_slot and sim_slot['pdp_type'] not in ['ipv4', 'ipv6', 'ipv4v6']:
            logger.warning("Invalid SIM pdp_type value",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'sim_slots',
                                 'sim_slot': slot_num})
            raise ValueError(f"SIM{slot_num} pdp_type must be 'ipv4', 'ipv6', or 'ipv4v6'")

        # Validate supported_bands
        if 'supported_bands' in sim_slot:
            bands = sim_slot['supported_bands']
            if not isinstance(bands, list):
                logger.warning("Invalid SIM supported_bands type",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_slots',
                                     'sim_slot': slot_num})
                raise ValueError(f"SIM{slot_num} supported_bands must be a list")

            # Special case: if "all" is specified, it should be the only entry
            if "all" in bands:
                if len(bands) != 1:
                    logger.warning("Invalid SIM 'all' bands configuration",
                                  extra={'interface_number': self.interface_number,
                                         'validation_field': 'sim_slots',
                                         'sim_slot': slot_num,
                                         'band_count': len(bands)})
                    raise ValueError(f"When 'all' is specified for SIM{slot_num} supported_bands, it must be the only entry")
            else:
                # Validate band format
                valid_band_patterns = [
                    r'^gsm-\d+$', r'^dcs$|^pcs$', r'^u\d+\+?$', r'^umts-\d+$',
                    r'^eutran-\d+$', r'^ngran-\d+$', r'^cdma-bc\d+$',
                    r'^(aws|cellular|egsm|pgsm)$', r'^(gsm|umts|lte|5gnr|cdma|any)$'
                ]

                for band in bands:
                    if not isinstance(band, str):
                        logger.warning("Invalid SIM band type",
                                      extra={'interface_number': self.interface_number,
                                             'validation_field': 'sim_slots',
                                             'sim_slot': slot_num})
                        raise ValueError(f"All SIM{slot_num} band entries must be strings")

                    if not any(re.match(pattern, band.lower()) for pattern in valid_band_patterns):
                        logger.warning("Invalid SIM band format",
                                      extra={'interface_number': self.interface_number,
                                             'validation_field': 'sim_slots',
                                             'sim_slot': slot_num,
                                             'invalid_band': band})
                        raise ValueError(f"Invalid band format '{band}' for SIM{slot_num}. Must be ModemManager band format")

                logger.info("SIM band validation passed",
                           extra={'interface_number': self.interface_number,
                                  'sim_slot': slot_num,
                                  'band_count': len(bands)})

        # Enhanced APN validation - supports both string and dict formats
        if 'apn' in sim_slot:
            apn = sim_slot['apn']

            # Support both string and dict formats
            if isinstance(apn, str):
                # Simple string format validation
                if len(apn) > 100:
                    logger.warning("SIM APN too long",
                                  extra={'interface_number': self.interface_number,
                                         'validation_field': 'sim_slots',
                                         'sim_slot': slot_num})
                    raise ValueError(f"SIM{slot_num} apn must be 100 characters or less")
                if apn and not re.match(r'^[a-zA-Z0-9.-]+$', apn):
                    logger.warning("Invalid SIM APN format",
                                  extra={'interface_number': self.interface_number,
                                         'validation_field': 'sim_slots',
                                         'sim_slot': slot_num})
                    raise ValueError(f"SIM{slot_num} apn can only contain letters, numbers, dots, and hyphens")

            elif isinstance(apn, dict):
                # Enhanced dict format validation
                self._validate_apn_dict(apn, slot_num)

            else:
                logger.warning("Invalid SIM APN type",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_slots',
                                     'sim_slot': slot_num})
                raise ValueError(f"SIM{slot_num} apn must be a string or dictionary")

        # Enhanced preferred_carrier validation with name resolution
        if 'preferred_carrier' in sim_slot:
            carrier = sim_slot['preferred_carrier']
            if not isinstance(carrier, str):
                logger.warning("Invalid SIM preferred_carrier type",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_slots',
                                     'sim_slot': slot_num})
                raise ValueError(f"SIM{slot_num} preferred_carrier must be a string")
            if len(carrier) > 50:
                logger.warning("SIM preferred carrier name too long",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_slots',
                                     'sim_slot': slot_num})
                raise ValueError(f"SIM{slot_num} preferred_carrier must be 50 characters or less")

            # Resolve carrier name to code for validation logging
            if carrier:
                resolved_code, display_name, is_code = resolve_carrier_code(carrier)
                logger.info("Carrier configuration resolved",
                           extra={'interface_number': self.interface_number,
                                  'sim_slot': slot_num,
                                  'user_input': carrier,
                                  'resolved_code': resolved_code,
                                  'display_name': display_name,
                                  'direct_code': is_code,
                                  'carrier_resolved': True})

        # Validate enable_network_scan
        if 'enable_network_scan' in sim_slot and not isinstance(sim_slot['enable_network_scan'], bool):
            logger.warning("Invalid SIM enable_network_scan flag",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'sim_slots',
                                 'sim_slot': slot_num})
            raise ValueError(f"SIM{slot_num} enable_network_scan must be true or false")

        # Validate PIN
        if 'pin' in sim_slot:
            pin = sim_slot['pin']
            if not isinstance(pin, str):
                logger.warning("Invalid SIM PIN type",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_slots',
                                     'sim_slot': slot_num})
                raise ValueError(f"SIM{slot_num} pin must be a string")

            if pin and not re.match(r'^\d{4,8}$', pin):
                logger.warning("Invalid SIM PIN format",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_slots',
                                     'sim_slot': slot_num})
                raise ValueError(f"SIM{slot_num} pin must be 4-8 digits")

        # Validate PUK
        if 'puk' in sim_slot:
            puk = sim_slot['puk']
            if not isinstance(puk, str):
                logger.warning("Invalid SIM PUK type",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_slots',
                                     'sim_slot': slot_num})
                raise ValueError(f"SIM{slot_num} puk must be a string")

            if puk and not re.match(r'^\d{8}$', puk):
                logger.warning("Invalid SIM PUK format",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_slots',
                                     'sim_slot': slot_num})
                raise ValueError(f"SIM{slot_num} puk must be exactly 8 digits")

        # Cross-validation: if PUK is provided, pin must also be provided
        # (PUK recovery uses SendPuk(puk, pin) to reset the SIM PIN)
        if sim_slot.get('puk') and not sim_slot.get('pin'):
            logger.warning("PUK provided without pin",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'sim_slots',
                                 'sim_slot': slot_num})
            raise ValueError(f"SIM{slot_num}: when puk is provided, pin must also be provided")

        # Validate ICCID lock (empty = no lock; if set, must be 19-20 digit string)
        if 'iccid' in sim_slot:
            iccid = sim_slot['iccid']
            if not isinstance(iccid, str):
                logger.warning("Invalid SIM ICCID type",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_slots',
                                     'sim_slot': slot_num})
                raise ValueError(f"SIM{slot_num} iccid must be a string")
            if iccid and not re.match(r'^\d{19,20}$', iccid):
                logger.warning("Invalid SIM ICCID format",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_slots',
                                     'sim_slot': slot_num,
                                     'iccid_length': len(iccid)})
                raise ValueError(f"SIM{slot_num} iccid must be 19-20 digits")

        # Validate per-SIM data_limit_warning (list of pct thresholds 1-100)
        if 'data_limit_warning' in sim_slot:
            thresholds = sim_slot['data_limit_warning']
            if not isinstance(thresholds, list):
                logger.warning("Invalid SIM data_limit_warning type",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_slots',
                                     'sim_slot': slot_num})
                raise ValueError(f"SIM{slot_num} data_limit_warning must be a list of percentages")
            for t in thresholds:
                if not isinstance(t, (int, float)) or t < 1 or t > 100:
                    logger.warning("Invalid SIM data_limit_warning value",
                                  extra={'interface_number': self.interface_number,
                                         'validation_field': 'sim_slots',
                                         'sim_slot': slot_num})
                    raise ValueError(f"SIM{slot_num} each data_limit_warning threshold must be between 1 and 100")

        # Validate per-SIM data_limit_action
        if 'data_limit_action' in sim_slot:
            valid_data_actions = ['none', 'disable', 'sim-failover', 'sim-failover-sticky']
            if sim_slot['data_limit_action'] not in valid_data_actions:
                logger.warning("Invalid SIM data_limit_action",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_slots',
                                     'sim_slot': slot_num})
                raise ValueError(f"SIM{slot_num} data_limit_action must be one of: {', '.join(valid_data_actions)}")

        # Validate per-SIM data_limit_billing_date (1-28)
        if 'data_limit_billing_date' in sim_slot:
            date = sim_slot['data_limit_billing_date']
            if not isinstance(date, int) or date < 1 or date > 28:
                logger.warning("Invalid SIM data_limit_billing_date",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_slots',
                                     'sim_slot': slot_num})
                raise ValueError(f"SIM{slot_num} data_limit_billing_date must be an integer between 1 and 28")

        # Validate per-SIM data_limit_size (0 = unlimited, positive = bytes)
        if 'data_limit_size' in sim_slot:
            size = sim_slot['data_limit_size']
            if not isinstance(size, (int, float)) or size < 0:
                logger.warning("Invalid SIM data_limit_size",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_slots',
                                     'sim_slot': slot_num})
                raise ValueError(f"SIM{slot_num} data_limit_size must be a non-negative number")

        # Validate per-SIM MTU (0 = use interface default, or 576-9000)
        if 'mtu' in sim_slot:
            mtu = sim_slot['mtu']
            if not isinstance(mtu, int) or mtu < 0:
                raise ValueError(f"SIM{slot_num} mtu must be a non-negative integer (0 = use interface default)")
            if mtu > 0 and (mtu < 576 or mtu > 9000):
                raise ValueError(f"SIM{slot_num} mtu must be 0 (interface default) or between 576 and 9000")

        logger.info("SIM configuration validation passed",
                   extra={'interface_number': self.interface_number,
                          'sim_slot': slot_num,
                          'has_pin': bool(sim_slot.get('pin')),
                          'has_puk': bool(sim_slot.get('puk')),
                          'has_carrier': bool(sim_slot.get('preferred_carrier')),
                          'scan_enabled': sim_slot.get('enable_network_scan', False)})

    def _validate_apn_dict(self, apn_config, slot_num):
        """Validate enhanced APN dictionary configuration"""

        # Validate APN name
        if 'name' not in apn_config:
            logger.warning("APN name missing",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'sim_slots',
                                 'sim_slot': slot_num})
            raise ValueError(f"SIM{slot_num} apn must include 'name' field")

        apn_name = apn_config['name']
        if not isinstance(apn_name, str):
            logger.warning("Invalid APN name type",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'sim_slots',
                                 'sim_slot': slot_num})
            raise ValueError(f"SIM{slot_num} apn name must be a string")

        if len(apn_name) > 100:
            logger.warning("APN name too long",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'sim_slots',
                                 'sim_slot': slot_num})
            raise ValueError(f"SIM{slot_num} apn name must be 100 characters or less")

        if apn_name and not re.match(r'^[a-zA-Z0-9.-]+$', apn_name):
            logger.warning("Invalid APN name format",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'sim_slots',
                                 'sim_slot': slot_num})
            raise ValueError(f"SIM{slot_num} apn name can only contain letters, numbers, dots, and hyphens")

        # Validate username (optional)
        if 'username' in apn_config:
            username = apn_config['username']
            if not isinstance(username, str):
                logger.warning("Invalid APN username type",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_slots',
                                     'sim_slot': slot_num})
                raise ValueError(f"SIM{slot_num} apn username must be a string")
            if len(username) > 50:
                logger.warning("APN username too long",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_slots',
                                     'sim_slot': slot_num})
                raise ValueError(f"SIM{slot_num} apn username must be 50 characters or less")

        # Validate password (optional)
        if 'password' in apn_config:
            password = apn_config['password']
            if not isinstance(password, str):
                logger.warning("Invalid APN password type",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_slots',
                                     'sim_slot': slot_num})
                raise ValueError(f"SIM{slot_num} apn password must be a string")
            if len(password) > 50:
                logger.warning("APN password too long",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_slots',
                                     'sim_slot': slot_num})
                raise ValueError(f"SIM{slot_num} apn password must be 50 characters or less")

        # Validate auth_type
        if 'auth_type' in apn_config:
            auth_type = apn_config['auth_type']
            valid_auth_types = ['none', 'pap', 'chap', 'pap-chap']
            if auth_type not in valid_auth_types:
                logger.warning("Invalid APN auth_type",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_slots',
                                     'sim_slot': slot_num})
                raise ValueError(f"SIM{slot_num} apn auth_type must be one of: {valid_auth_types}")

        # Cross-validation: if auth_type is not 'none', username should be provided
        auth_type = apn_config.get('auth_type', 'none')
        username = apn_config.get('username', '')
        if auth_type != 'none' and not username:
            logger.warning("APN authentication requires username",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'sim_slots',
                                 'sim_slot': slot_num})
            raise ValueError(f"SIM{slot_num} apn with auth_type '{auth_type}' requires username")

        logger.info("APN configuration validation passed",
                   extra={'interface_number': self.interface_number,
                          'sim_slot': slot_num,
                          'apn_name': apn_name,
                          'has_auth': auth_type != 'none'})

    def _validate_other_parameters(self, config):
        """Validate non-SIM configuration parameters"""

        # Validate sim_failover_connect_retries
        if 'sim_failover_connect_retries' in config:
            retries = config['sim_failover_connect_retries']
            if not isinstance(retries, int) or retries < 0 or retries > 100:
                logger.warning("Invalid sim_failover_connect_retries",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_failover_connect_retries'})
                raise ValueError("sim_failover_connect_retries must be an integer between 0 and 100")

        # Validate sim_failover_revert_timer
        if 'sim_failover_revert_timer' in config:
            timer = config['sim_failover_revert_timer']
            if not isinstance(timer, int) or timer < 0 or timer > 86400:
                logger.warning("Invalid sim_failover_revert_timer",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_failover_revert_timer'})
                raise ValueError("sim_failover_revert_timer must be an integer between 0 and 86400 seconds")

        # Validate sim_failover_signal_loss_timer
        if 'sim_failover_signal_loss_timer' in config:
            timer = config['sim_failover_signal_loss_timer']
            if not isinstance(timer, int) or timer < 1 or timer > 3600:
                logger.warning("Invalid sim_failover_signal_loss_timer",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_failover_signal_loss_timer'})
                raise ValueError("sim_failover_signal_loss_timer must be an integer between 1 and 3600 seconds")

        # Validate data_limit_billing_date
        if 'data_limit_billing_date' in config:
            date = config['data_limit_billing_date']
            if not isinstance(date, int) or date < 1 or date > 28:
                logger.warning("Invalid data_limit_billing_date",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'data_limit_billing_date'})
                raise ValueError("data_limit_billing_date must be an integer between 1 and 28")

        # Validate data_limit_action
        valid_data_actions = ['none', 'disable', 'sim-failover', 'sim-failover-sticky']
        if 'data_limit_action' in config and config['data_limit_action'] not in valid_data_actions:
            logger.warning("Invalid data_limit_action",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'data_limit_action'})
            raise ValueError(f"data_limit_action must be one of: {', '.join(valid_data_actions)}")

        # Validate data_limit_warning (list of pct thresholds 1-100)
        if 'data_limit_warning' in config:
            thresholds = config['data_limit_warning']
            if not isinstance(thresholds, list):
                logger.warning("Invalid data_limit_warning type",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'data_limit_warning'})
                raise ValueError("data_limit_warning must be a list of percentages")
            for t in thresholds:
                if not isinstance(t, (int, float)) or t < 1 or t > 100:
                    logger.warning("Invalid data_limit_warning threshold value",
                                  extra={'interface_number': self.interface_number,
                                         'validation_field': 'data_limit_warning'})
                    raise ValueError("Each data_limit_warning threshold must be between 1 and 100 percent")

        # Validate signal threshold
        if 'sim_failover_signal_threshold' in config:
            threshold = config['sim_failover_signal_threshold']
            if not isinstance(threshold, int) or threshold < -120 or threshold > 0:
                logger.warning("Invalid sim_failover_signal_threshold",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_failover_signal_threshold'})
                raise ValueError("sim_failover_signal_threshold must be between -120 and 0 dBm")

        # Validate data_limit_size (0 = unlimited, positive = limit in bytes)
        if 'data_limit_size' in config:
            size = config['data_limit_size']
            if not isinstance(size, int) or size < 0:
                logger.warning("Invalid data_limit_size",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'data_limit_size'})
                raise ValueError("data_limit_size must be a non-negative integer (bytes, 0 = unlimited)")

        # Validate interface_disabled
        if 'interface_disabled' in config and not isinstance(config['interface_disabled'], bool):
            logger.warning("Invalid interface_disabled",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'interface_disabled'})
            raise ValueError("interface_disabled must be true or false")

        # Validate APN discovery settings
        if 'android_apn_discovery' in config and config['android_apn_discovery'] not in ['enabled', 'disabled']:
            logger.warning("Invalid android_apn_discovery",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'android_apn_discovery'})
            raise ValueError("android_apn_discovery must be 'enabled' or 'disabled'")

        # Validate hardware reset settings
        if 'hardware_reset_enabled' in config and not isinstance(config['hardware_reset_enabled'], bool):
            logger.warning("Invalid hardware_reset_enabled",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'hardware_reset_enabled'})
            raise ValueError("hardware_reset_enabled must be true or false")

        if 'max_hardware_resets' in config:
            resets = config['max_hardware_resets']
            if not isinstance(resets, int) or resets < 0 or resets > 10:
                logger.warning("Invalid max_hardware_resets",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'max_hardware_resets'})
                raise ValueError("max_hardware_resets must be an integer between 0 and 10")

        if 'hardware_reset_cooldown' in config:
            cooldown = config['hardware_reset_cooldown']
            if not isinstance(cooldown, int) or cooldown < 30 or cooldown > 3600:
                logger.warning("Invalid hardware_reset_cooldown",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'hardware_reset_cooldown'})
                raise ValueError("hardware_reset_cooldown must be between 30 and 3600 seconds")

        # Validate timeout settings
        if 'connection_timeout' in config:
            timeout = config['connection_timeout']
            if not isinstance(timeout, int) or timeout < 30 or timeout > 600:
                logger.warning("Invalid connection_timeout",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'connection_timeout'})
                raise ValueError("connection_timeout must be between 30 and 600 seconds")

        if 'registration_timeout' in config:
            timeout = config['registration_timeout']
            if not isinstance(timeout, int) or timeout < 30 or timeout > 600:
                logger.warning("Invalid registration_timeout",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'registration_timeout'})
                raise ValueError("registration_timeout must be between 30 and 600 seconds")

        if 'network_scan_timeout' in config:
            timeout = config['network_scan_timeout']
            if not isinstance(timeout, int) or timeout < 10 or timeout > 300:
                logger.warning("Invalid network_scan_timeout",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'network_scan_timeout'})
                raise ValueError("network_scan_timeout must be between 10 and 300 seconds")

        # Validate network mode
        if 'network_mode' in config and config['network_mode'] not in ['auto', 'lte', '5g', '3g', '2g']:
            logger.warning("Invalid network_mode",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'network_mode'})
            raise ValueError("network_mode must be 'auto', 'lte', '5g', '3g', or '2g'")

        # Validate monitoring intervals
        if 'normal_monitoring_interval' in config:
            interval = config['normal_monitoring_interval']
            if not isinstance(interval, int) or interval < 10 or interval > 3600:
                logger.warning("Invalid normal_monitoring_interval",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'normal_monitoring_interval'})
                raise ValueError("normal_monitoring_interval must be between 10 and 3600 seconds")

        if 'data_usage_monitoring_interval' in config:
            interval = config['data_usage_monitoring_interval']
            if not isinstance(interval, int) or interval < 10 or interval > 3600:
                logger.warning("Invalid data_usage_monitoring_interval",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'data_usage_monitoring_interval'})
                raise ValueError("data_usage_monitoring_interval must be between 10 and 3600 seconds")

        # Validate logging settings
        if 'verbose_logging' in config and not isinstance(config['verbose_logging'], bool):
            logger.warning("Invalid verbose_logging",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'verbose_logging'})
            raise ValueError("verbose_logging must be true or false")

        if 'log_level' in config and config['log_level'] not in ['debug', 'info', 'warning', 'error', 'critical']:
            logger.warning("Invalid log_level",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'log_level'})
            raise ValueError("log_level must be 'debug', 'info', 'warning', 'error', or 'critical'")

        if 'log_sink' in config and config['log_sink'] not in ['both', 'journal', 'syslog']:
            logger.warning("Invalid log_sink",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'log_sink'})
            raise ValueError("log_sink must be 'both', 'journal', or 'syslog'")

    def _normalize_connectivity_monitoring(self, config_data):
        """Normalize connectivity monitoring configuration"""
        connectivity = config_data.get('connectivity_monitoring', {})

        if not isinstance(connectivity, dict):
            return {'enabled': True}

        # Normalize with safe defaults
        normalized = {
            'enabled': connectivity.get('enabled', True),
            'interval': max(30, connectivity.get('interval', 60)),
            'timeout': max(5, connectivity.get('timeout', 10)),
            'retry_count': max(1, connectivity.get('retry_count', 3)),
            'failure_threshold': max(1, connectivity.get('failure_threshold', 2)),
            'test_ipv4': connectivity.get('test_ipv4', True),
            'test_ipv6': connectivity.get('test_ipv6', False),
            'require_both': connectivity.get('require_both', False),
            'ipv4_targets': self._normalize_ping_targets(
                connectivity.get('ipv4_targets', ['8.8.8.8', '1.1.1.1'])
            ),
            'ipv6_targets': self._normalize_ping_targets(
                connectivity.get('ipv6_targets', ['2001:4860:4860::8888', '2606:4700:4700::1111'])
            )
        }

        return normalized

    def _normalize_ping_targets(self, targets):
        """Normalize and validate ping targets"""
        if not isinstance(targets, list):
            return ['8.8.8.8', '1.1.1.1']  # Safe IPv4 defaults

        # Filter out invalid targets and limit to reasonable number
        valid_targets = []
        for target in targets[:10]:  # Max 10 targets
            if isinstance(target, str) and target.strip():
                # Basic validation - could be enhanced
                target = target.strip()
                if target and not target.startswith('#'):  # Skip comments
                    valid_targets.append(target)

        return valid_targets if valid_targets else ['8.8.8.8', '1.1.1.1']


    def _merge_connectivity_monitoring(self, new_connectivity, current_connectivity, default_connectivity):
        """Merge connectivity monitoring configurations"""
        if not new_connectivity:
            return current_connectivity or default_connectivity

        # Start with defaults
        merged = default_connectivity.copy()

        # Apply current values
        if current_connectivity:
            merged.update(current_connectivity)

        # Apply new values
        if isinstance(new_connectivity, dict):
            merged.update(new_connectivity)

            # Normalize targets
            if 'ipv4_targets' in new_connectivity:
                merged['ipv4_targets'] = self._normalize_ping_targets(new_connectivity['ipv4_targets'])
            if 'ipv6_targets' in new_connectivity:
                merged['ipv6_targets'] = self._normalize_ping_targets(new_connectivity['ipv6_targets'])

            # Enforce minimums
            merged['interval'] = max(30, merged.get('interval', 60))
            merged['timeout'] = max(5, merged.get('timeout', 10))
            merged['retry_count'] = max(1, merged.get('retry_count', 3))
            merged['failure_threshold'] = max(1, merged.get('failure_threshold', 2))

        return merged

    def _validate_connectivity_monitoring(self, connectivity_config):
        """Validate connectivity monitoring configuration"""
        if not isinstance(connectivity_config, dict):
            logger.warning("Invalid connectivity_monitoring type",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'connectivity_monitoring'})
            raise ValueError("connectivity_monitoring must be a dictionary")

        # Validate enabled flag
        if 'enabled' in connectivity_config and not isinstance(connectivity_config['enabled'], bool):
            logger.warning("Invalid connectivity monitoring enabled flag",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'connectivity_monitoring'})
            raise ValueError("connectivity_monitoring enabled must be true or false")

        # Validate interval
        if 'interval' in connectivity_config:
            interval = connectivity_config['interval']
            if not isinstance(interval, int) or interval < 30:
                logger.warning("Invalid connectivity monitoring interval",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'connectivity_monitoring'})
                raise ValueError("connectivity_monitoring interval must be at least 30 seconds")

        # Validate timeout
        if 'timeout' in connectivity_config:
            timeout = connectivity_config['timeout']
            if not isinstance(timeout, int) or timeout < 5:
                logger.warning("Invalid connectivity monitoring timeout",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'connectivity_monitoring'})
                raise ValueError("connectivity_monitoring timeout must be at least 5 seconds")

        # Validate failure threshold
        if 'failure_threshold' in connectivity_config:
            threshold = connectivity_config['failure_threshold']
            if not isinstance(threshold, int) or threshold < 1:
                logger.warning("Invalid connectivity monitoring failure threshold",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'connectivity_monitoring'})
                raise ValueError("connectivity_monitoring failure_threshold must be at least 1")

        # Validate retry count
        if 'retry_count' in connectivity_config:
            retry_count = connectivity_config['retry_count']
            if not isinstance(retry_count, int) or retry_count < 1:
                logger.warning("Invalid connectivity monitoring retry count",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'connectivity_monitoring'})
                raise ValueError("connectivity_monitoring retry_count must be at least 1")

        # Validate IP family flags
        for flag in ['test_ipv4', 'test_ipv6', 'require_both']:
            if flag in connectivity_config and not isinstance(connectivity_config[flag], bool):
                logger.warning(f"Invalid connectivity monitoring {flag} flag",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'connectivity_monitoring'})
                raise ValueError(f"connectivity_monitoring {flag} must be true or false")

        # Validate targets
        if 'ipv4_targets' in connectivity_config:
            targets = connectivity_config['ipv4_targets']
            if not isinstance(targets, list):
                logger.warning("Invalid connectivity monitoring ipv4_targets type",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'connectivity_monitoring'})
                raise ValueError("connectivity_monitoring ipv4_targets must be a list")

        if 'ipv6_targets' in connectivity_config:
            targets = connectivity_config['ipv6_targets']
            if not isinstance(targets, list):
                logger.warning("Invalid connectivity monitoring ipv6_targets type",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'connectivity_monitoring'})
                raise ValueError("connectivity_monitoring ipv6_targets must be a list")

        # Check that at least one IP family is being tested
        test_ipv4 = connectivity_config.get('test_ipv4', True)
        test_ipv6 = connectivity_config.get('test_ipv6', False)
        if not test_ipv4 and not test_ipv6:
            logger.warning("No IP families enabled for connectivity monitoring",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'connectivity_monitoring'})
            raise ValueError("At least one IP family (test_ipv4 or test_ipv6) must be enabled")

        logger.info("Connectivity monitoring validation passed",
                   extra={'interface_number': self.interface_number,
                          'enabled': connectivity_config.get('enabled', True),
                          'interval': connectivity_config.get('interval', 60),
                          'test_ipv4': test_ipv4,
                          'test_ipv6': test_ipv6})

    @method()
    async def connect(self) -> 's':  # type: ignore[name-defined]  # noqa: F821
        """Request connection. Always accepted — the service handles state internally.

        If the FSM is already in a connectable state, fires the transition
        immediately.  Otherwise, sets a ``connect_requested`` flag on the FSM
        so that connection proceeds automatically as soon as the modem is ready.
        The caller never needs to know or care about FSM state.

        In on-demand / dial-on-demand modes the response is a simple
        ``"accepted"``; the caller polls ``get_bearer_status()`` separately.
        """
        try:
            # Reject if the interface is administratively disabled (airplane
            # mode).  Without this guard the request would silently queue
            # via connect_requested and never fire until the operator runs
            # 'delete interfaces wwan wwanN disable'.
            if (getattr(self.fsm, '_airplane_mode_active', False)
                    or getattr(self.fsm, '_airplane_mode_requested', False)):
                raise DBusError(
                    "com.igos.IgosModemManager.AdminDisabled",
                    f"Interface {self.interface_number} is administratively "
                    f"disabled (airplane mode). Run 'delete interfaces wwan "
                    f"wwan{self.interface_number} disable' to re-enable.")

            current_state = (
                getattr(self.fsm.machine, 'current_state', 'UNKNOWN')
                if hasattr(self.fsm, 'machine') and self.fsm.machine
                else 'UNKNOWN'
            )

            logger.info("Connect requested",
                       extra={'interface_number': self.interface_number,
                              'current_state': current_state})

            # Fire-and-forget shorthand for on-demand modes
            fire_and_forget = self.fsm.connection_mode != 'always-on'

            # States where CONNECT transition is valid right now
            connectable_states = {'FAILED', 'REGISTERED_IDLE'}
            # States where we are already connected / on the way
            already_connected_states = {'CONNECTED', 'CONNECTING'}

            if current_state == 'CONFIGURING':
                self.fsm.connect_requested = True
                if fire_and_forget:
                    return "accepted"
                msg = (f"Connect request queued for interface {self.interface_number} "
                       f"while configuration is still in progress.")
                logger.info(msg, extra={'interface_number': self.interface_number,
                                        'current_state': current_state})
                return msg

            if current_state in already_connected_states:
                if fire_and_forget:
                    return "accepted"
                msg = (f"Interface {self.interface_number} is already "
                       f"in state {current_state} — no action needed")
                logger.info(msg, extra={'interface_number': self.interface_number})
                return msg

            if current_state in connectable_states:
                from vyos.utils.wwan.interfaces_wwan_state_machine import ModemEvent
                self.fsm.transition(ModemEvent.CONNECT)
                if fire_and_forget:
                    return "accepted"
                return f"connect() on {self.interface_number}"

            # Not ready yet — queue the request so FSM connects when it can
            self.fsm.connect_requested = True
            if fire_and_forget:
                return "accepted"
            msg = (f"Connect request queued for interface {self.interface_number} "
                   f"(current state: {current_state}). "
                   f"Connection will proceed automatically when modem is ready.")
            logger.info(msg, extra={'interface_number': self.interface_number,
                                    'current_state': current_state})
            return msg

        except Exception as e:
            logger.error("Connect failed",
                        extra={'interface_number': self.interface_number,
                               'error': str(e)})
            raise DBusError("com.igos.IgosModemManager.ConnectionError", str(e))

    @method()
    async def disconnect(self) -> 's':  # type: ignore[name-defined]  # noqa: F821
        try:
            logger.info("Disconnecting interface",
                       extra={'interface_number': self.interface_number})
            from vyos.utils.wwan.interfaces_wwan_state_machine import ModemEvent, ModemState

            current_state = self.fsm.machine.current_state if hasattr(self.fsm, 'machine') and self.fsm.machine else 'UNKNOWN'

            # Fire-and-forget shorthand for on-demand modes
            fire_and_forget = self.fsm.connection_mode != 'always-on'

            # States where disconnect is a no-op (already disconnected or not connected)
            already_disconnected = {
                ModemState.DISCONNECTED.value,
                ModemState.SCANNING.value,
                ModemState.INITIAL.value,
                ModemState.WAITING_FOR_CONFIG.value,
                ModemState.MODEM_FOUND.value,
                ModemState.WAITING_FOR_SIM.value,
                ModemState.REGISTERED_IDLE.value,
            }
            if current_state in already_disconnected:
                if fire_and_forget:
                    return "accepted"
                msg = f"Interface {self.interface_number} not connected (state: {current_state})"
                logger.info(msg, extra={'interface_number': self.interface_number})
                return msg

            # States where disconnect is valid
            disconnectable = {
                ModemState.CONNECTED.value,
                ModemState.SIM_SWITCHING.value,
            }
            if current_state in disconnectable:
                # On-demand / dial-on-demand: drop bearer but keep registration
                if fire_and_forget:
                    self.fsm.transition(ModemEvent.ENTER_IDLE)
                    return "accepted"
                self.fsm.transition(ModemEvent.DISCONNECT)
                return f"disconnect() on {self.interface_number}"

            # Transitional states — log and return gracefully rather than error
            if fire_and_forget:
                return "accepted"
            msg = f"Interface {self.interface_number} in transitional state {current_state}, disconnect queued"
            logger.info(msg, extra={'interface_number': self.interface_number,
                                    'current_state': current_state})
            return msg
        except Exception as e:
            logger.error("Disconnect failed",
                        extra={'interface_number': self.interface_number,
                               'error': str(e)})
            raise DBusError("com.igos.IgosModemManager.DisconnectionError", str(e))

    @method()
    async def get_bearer_status(self) -> 's':  # type: ignore[name-defined]  # noqa: F821
        """Lightweight bearer status poll.

        Returns ``"connected"`` when the data bearer is up, or
        ``"disconnected"`` otherwise.  Designed for dial-on-demand callers
        who need to poll bearer state without the overhead of full status.
        """
        try:
            from vyos.utils.wwan.interfaces_wwan_state_machine import ModemState
            current_state = (
                self.fsm.machine.current_state
                if hasattr(self.fsm, 'machine') and self.fsm.machine
                else 'UNKNOWN'
            )
            bearer_up_states = {
                ModemState.CONNECTED.value,
            }
            status = "connected" if current_state in bearer_up_states else "disconnected"
            logger.info("Bearer status polled",
                       extra={'interface_number': self.interface_number,
                              'bearer_status': status,
                              'fsm_state': current_state})
            return status
        except Exception as e:
            logger.error("Bearer status check failed",
                        extra={'interface_number': self.interface_number,
                               'error': str(e)})
            raise DBusError("com.igos.IgosModemManager.StatusError", str(e))

    @method()
    async def connect_bearer(self) -> 's':  # type: ignore[name-defined]  # noqa: F821
        """Request bearer establishment.  Always returns ``"accepted"``.

        If the FSM is at ``REGISTERED_IDLE``, fires ``CONNECT`` immediately.
        Otherwise queues ``connect_requested`` so the bearer comes up when
        the modem is ready.  The caller polls ``get_bearer_status()`` to
        observe the result.
        """
        try:
            # Reject if the interface is administratively disabled (airplane
            # mode).  Without this guard the request would silently queue
            # via connect_requested and never fire until the operator runs
            # 'delete interfaces wwan wwanN disable'.
            if (getattr(self.fsm, '_airplane_mode_active', False)
                    or getattr(self.fsm, '_airplane_mode_requested', False)):
                raise DBusError(
                    "com.igos.IgosModemManager.AdminDisabled",
                    f"Interface {self.interface_number} is administratively "
                    f"disabled (airplane mode). Run 'delete interfaces wwan "
                    f"wwan{self.interface_number} disable' to re-enable.")

            from vyos.utils.wwan.interfaces_wwan_state_machine import ModemEvent, ModemState
            current_state = (
                self.fsm.machine.current_state
                if hasattr(self.fsm, 'machine') and self.fsm.machine
                else 'UNKNOWN'
            )
            logger.info("Bearer connect requested",
                       extra={'interface_number': self.interface_number,
                              'current_state': current_state})

            # Always clear user-disconnect hold so auto-recovery can resume
            self.fsm.user_disconnected = False
            self._save_runtime_state()

            if current_state == ModemState.REGISTERED_IDLE.value:
                self.fsm.transition(ModemEvent.CONNECT)
            elif current_state not in {ModemState.CONNECTED.value,
                                        ModemState.CONNECTING.value}:
                self.fsm.connect_requested = True
            return "accepted"
        except Exception as e:
            logger.error("Bearer connect failed",
                        extra={'interface_number': self.interface_number,
                               'error': str(e)})
            raise DBusError("com.igos.IgosModemManager.ConnectionError", str(e))

    @method()
    async def disconnect_bearer(self) -> 's':  # type: ignore[name-defined]  # noqa: F821
        """Request bearer teardown.  Always returns ``"accepted"``.

        Drops the data bearer but keeps the modem registered on the network
        (transitions to ``REGISTERED_IDLE``).  SMS remains available.  If the
        bearer is already down the call is a harmless no-op.  The caller polls
        ``get_bearer_status()`` to observe the result.
        """
        try:
            from vyos.utils.wwan.interfaces_wwan_state_machine import ModemEvent, ModemState
            current_state = (
                self.fsm.machine.current_state
                if hasattr(self.fsm, 'machine') and self.fsm.machine
                else 'UNKNOWN'
            )
            logger.info("Bearer disconnect requested",
                       extra={'interface_number': self.interface_number,
                              'current_state': current_state,
                              'connection_mode': getattr(self.fsm, 'connection_mode', 'unknown')})

            # In dial-on-demand mode, flag this as a user-initiated disconnect
            # so the FSM does not auto-reconnect.  The flag is cleared by
            # connect_bearer(), service restart, or modem reset.
            if getattr(self.fsm, 'connection_mode', '') == 'dial-on-demand':
                self.fsm.user_disconnected = True
                logger.info("Dial-on-demand: bearer held down until connect_bearer()",
                           extra={'interface_number': self.interface_number})
                self._save_runtime_state()

            bearer_up = {ModemState.CONNECTED.value}
            if current_state in bearer_up:
                self.fsm.transition(ModemEvent.ENTER_IDLE)
            return "accepted"
        except Exception as e:
            logger.error("Bearer disconnect failed",
                        extra={'interface_number': self.interface_number,
                               'error': str(e)})
            raise DBusError("com.igos.IgosModemManager.DisconnectionError", str(e))

    @method()
    async def get_status(self) -> 'a{sv}':  # type: ignore[name-defined]  # noqa: F821, F722
        """Get comprehensive interface status — everything about this interface.

        Returns a flat D-Bus dict ``a{sv}`` with keys for FSM state, SIM info,
        modem hardware, signal quality, IP configuration, bearer session stats,
        per-SIM cumulative data usage, sim-failover/recovery state, per-slot
        configuration summary, and key feature flags.
        """
        try:
            logger.info("Getting comprehensive interface status",
                       extra={'interface_number': self.interface_number})

            # Delegate the heavy lifting to the FSM
            raw = await self.fsm.get_comprehensive_status()

            # Wrap every value in an appropriate D-Bus Variant.
            # Recursively handle nested dicts/lists so structured fields
            # (e.g. per_slot_cumulative) survive the round-trip instead of
            # being stringified by str().
            def _to_variant(value):
                if isinstance(value, dict):
                    return Variant('a{sv}',
                                   {k: _to_variant(v) for k, v in value.items()})
                if isinstance(value, list):
                    if not value:
                        return Variant('as', [])
                    if all(isinstance(x, str) for x in value):
                        return Variant('as', value)
                    if all(isinstance(x, bool) for x in value):
                        return Variant('ab', value)
                    if all(isinstance(x, int) and not isinstance(x, bool)
                           for x in value):
                        return Variant('ax', value)
                    if all(isinstance(x, (int, float)) and not isinstance(x, bool)
                           for x in value):
                        return Variant('ad', [float(x) for x in value])
                    return Variant('av', [_to_variant(x) for x in value])
                if isinstance(value, bool):
                    return Variant('b', value)
                if isinstance(value, int):
                    return Variant('x', value)
                if isinstance(value, float):
                    return Variant('d', value)
                if isinstance(value, str):
                    return Variant('s', value)
                return Variant('s', str(value))

            status = {key: _to_variant(val) for key, val in raw.items()}
            return status

        except Exception as e:
            logger.error("Failed to get status",
                        extra={'interface_number': self.interface_number,
                               'error': str(e)})
            raise DBusError("com.igos.IgosModemManager.StatusError", str(e))

    # ── SMS methods ──────────────────────────────────────────────────────

    @method()
    async def send_sms(self, recipient: 's', message: 's') -> 'a{sv}':  # type: ignore[name-defined]  # noqa: F821, F722
        """Send an SMS message via the modem.

        Parameters: recipient phone number, message text.
        Returns dict with 'status' and 'message_id'.
        """
        try:
            logger.info("SMS send requested",
                       extra={'interface_number': self.interface_number})
            result = await self.fsm.sms_send(recipient, message)
            return {k: Variant('s', str(v)) for k, v in result.items()}
        except Exception as e:
            logger.error(f"SMS send failed: {e}",
                        extra={'interface_number': self.interface_number})
            raise DBusError("com.igos.IgosModemManager.SmsError", str(e))

    @method()
    async def list_sms(self) -> 'aa{sv}':  # type: ignore[name-defined]  # noqa: F821, F722
        """List all stored SMS messages for the current SIM.

        Returns array of dicts, each with id, direction, number, text,
        timestamp, status, and read fields.
        """
        try:
            messages = await self.fsm.sms_list()
            result = []
            for msg in messages:
                entry = {}
                for k, v in msg.items():
                    if isinstance(v, bool):
                        entry[k] = Variant('b', v)
                    elif isinstance(v, int):
                        entry[k] = Variant('x', v)
                    else:
                        entry[k] = Variant('s', str(v))
                result.append(entry)
            return result
        except Exception as e:
            logger.error(f"SMS list failed: {e}",
                        extra={'interface_number': self.interface_number})
            raise DBusError("com.igos.IgosModemManager.SmsError", str(e))

    @method()
    async def read_sms(self, message_id: 'x') -> 'a{sv}':  # type: ignore[name-defined]  # noqa: F821, F722
        """Read a specific SMS message by ID.

        Returns dict with all message fields.  Marks incoming messages as read.
        """
        try:
            msg = await self.fsm.sms_read(int(message_id))
            result = {}
            for k, v in msg.items():
                if isinstance(v, bool):
                    result[k] = Variant('b', v)
                elif isinstance(v, int):
                    result[k] = Variant('x', v)
                else:
                    result[k] = Variant('s', str(v))
            return result
        except ValueError as e:
            raise DBusError("com.igos.IgosModemManager.SmsNotFound", str(e))
        except Exception as e:
            logger.error(f"SMS read failed: {e}",
                        extra={'interface_number': self.interface_number})
            raise DBusError("com.igos.IgosModemManager.SmsError", str(e))

    @method()
    async def delete_sms(self, message_id: 'x') -> 'a{sv}':  # type: ignore[name-defined]  # noqa: F821, F722
        """Delete a specific SMS message by ID."""
        try:
            result = await self.fsm.sms_delete(int(message_id))
            return {k: Variant('s', str(v)) for k, v in result.items()}
        except ValueError as e:
            raise DBusError("com.igos.IgosModemManager.SmsNotFound", str(e))
        except Exception as e:
            logger.error(f"SMS delete failed: {e}",
                        extra={'interface_number': self.interface_number})
            raise DBusError("com.igos.IgosModemManager.SmsError", str(e))

    @method()
    async def delete_all_sms(self) -> 'a{sv}':  # type: ignore[name-defined]  # noqa: F821, F722
        """Delete all stored SMS messages for the current SIM."""
        try:
            result = await self.fsm.sms_delete_all()
            return {k: Variant('s', str(v)) for k, v in result.items()}
        except Exception as e:
            logger.error(f"SMS delete-all failed: {e}",
                        extra={'interface_number': self.interface_number})
            raise DBusError("com.igos.IgosModemManager.SmsError", str(e))
