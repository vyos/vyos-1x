#!/usr/bin/env python3
# filepath: /home/jfeeney/vyos-1x/python/vyos/utils/wwan/interfaces_wwan_config.py
import asyncio
import re
from dbus_next.service import ServiceInterface, method  # pylint: disable=import-error
from dbus_next.errors import DBusError  # pylint: disable=import-error
from dbus_next import Variant  # pylint: disable=import-error
from vyos.utils.wwan.rfc5424_logging import RFC5424Formatter as _BaseFormatter, setup_logging


class ConfigFormatter(_BaseFormatter):
    """Config-specific RFC 5424 formatter."""

    def _get_message_id(self, record):
        msg = record.getMessage().lower()
        if 'setting configuration' in msg:
            return 'CONFIG_SET'
        elif 'configuration applied' in msg:
            return 'CONFIG_APPLIED'
        elif 'invalid parameter' in msg:
            return 'CONFIG_INVALID'
        elif 'sim configuration' in msg:
            return 'SIM_CONFIG'
        elif 'connecting interface' in msg:
            return 'IFACE_CONNECT'
        elif 'disconnecting interface' in msg:
            return 'IFACE_DISCONNECT'
        elif 'validation' in msg:
            return 'CONFIG_VALIDATE'
        elif 'error' in msg:
            return 'CONFIG_ERROR'
        elif 'unlock' in msg:
            return 'SIM_UNLOCK'
        elif 'carrier' in msg:
            return 'CARRIER_CONFIG'
        else:
            return 'CONFIG_EVENT'

    def _build_structured_data(self, record):
        sd_elements = []
        config_data = []
        if hasattr(record, 'interface_number'):
            config_data.append(f'interface="{record.interface_number}"')
        if hasattr(record, 'config_keys'):
            config_data.append(f'keys="{",".join(record.config_keys)}"')
        if hasattr(record, 'validation_field'):
            config_data.append(f'field="{record.validation_field}"')
        if hasattr(record, 'sim_slot'):
            config_data.append(f'sim_slot="{record.sim_slot}"')
        if hasattr(record, 'band_count'):
            config_data.append(f'band_count="{record.band_count}"')
        if hasattr(record, 'carrier_resolved'):
            config_data.append(f'carrier_resolved="{record.carrier_resolved}"')
        if config_data:
            sd_elements.append(f'[config@32473 {" ".join(config_data)}]')
        origin_data = [f'software="vyos-wwan-config"', f'version="1.0"']
        sd_elements.append(f'[origin@32473 {" ".join(origin_data)}]')
        return ''.join(sd_elements) if sd_elements else '-'

# Carrier name to operator code mapping for user-friendly configuration
CARRIER_MAPPINGS = {
    # US Carriers
    'verizon': '311480',
    'verizon wireless': '311480',
    'vzw': '311480',

    't-mobile': '310260',
    't-mobile us': '310260',
    'tmobile': '310260',
    'tmo': '310260',

    'at&t': '310410',
    'att': '310410',
    'at&t mobility': '310410',

    'sprint': '310120',
    'sprint pcs': '310120',

    'us cellular': '311580',
    'uscellular': '311580',

    'cricket': '310150',
    'cricket wireless': '310150',

    'boost mobile': '311870',
    'boost': '311870',

    'metro pcs': '310260',  # T-Mobile network
    'metro': '310260',

    'straight talk': '311480',  # Typically Verizon

    # Common MVNO carriers
    'mint mobile': '310260',    # T-Mobile network
    'mint': '310260',

    'google fi': '310260',      # Multi-carrier but often T-Mobile
    'fi': '310260',

    'visible': '311480',        # Verizon network

    'red pocket': '310260',     # Multi-carrier MVNO
    'red pocket mobile': '310260',

    'total wireless': '311480', # Verizon network
    'total': '311480',

    'tracfone': '311480',       # Multi-carrier but often Verizon
    'net10': '311480',          # TracFone subsidiary

    # International carriers (examples)
    'vodafone uk': '23415',
    'vodafone': '23415',
    'ee': '23430',
    'o2 uk': '23410',
    'three uk': '23420',

    'orange fr': '20801',
    'sfr': '20810',
    'bouygues': '20820',
    'free mobile': '20815',

    'telekom de': '26201',
    'vodafone de': '26202',
    'o2 de': '26207',
    'e-plus': '26203',

    # Canada
    'rogers': '302720',
    'bell': '302610',
    'telus': '302220',
    'freedom': '302490',

    # Add more as needed for your deployment regions
}

def resolve_carrier_code(carrier_input):
    """
    Resolve user-friendly carrier name to operator code

    Args:
        carrier_input: User input (can be name like "T-Mobile" or code like "310260")

    Returns:
        tuple: (resolved_code, display_name, is_code)
    """
    if not carrier_input:
        return '', '', False

    carrier_clean = carrier_input.strip()

    # Check if it's already a numeric code
    if carrier_clean.isdigit() and len(carrier_clean) >= 5:
        return carrier_clean, f"Operator Code {carrier_clean}", True

    # Try to resolve from mapping
    carrier_lower = carrier_clean.lower()

    # Exact match first
    if carrier_lower in CARRIER_MAPPINGS:
        operator_code = CARRIER_MAPPINGS[carrier_lower]
        return operator_code, f"{carrier_clean} ({operator_code})", False

    # Partial match (for flexibility)
    for name, code in CARRIER_MAPPINGS.items():
        if carrier_lower in name or name in carrier_lower:
            return code, f"{name.title()} ({code})", False

    # No match found - return as-is for direct operator registration attempt
    return carrier_clean, f"Unknown: {carrier_clean}", False

logger = setup_logging(__name__, "wwan-config", formatter_class=ConfigFormatter)

class InterfaceConfig(ServiceInterface):
    # Centralized default configuration values
    DEFAULT_CONFIG = {
        # Interface-level settings
        "on_demand": "disabled",
        "active_sim_slot": 1,  # Which SIM slot to use (1 or 2)
        "sim_failover": "disabled",  # Auto-switch SIMs on failure

        # APN discovery settings
        "android_apn_discovery": "disabled",
        "apn_caching": "disabled",

        # Failover settings
        "failover": "disabled",
        "failover_connect_retries": 3,
        "failover_revert_timer": 300,
        "failover_signal_loss_timer": 60,
        "failover_signal_threshold": -90,

        # Data usage settings
        "data_limit_action": "disable",
        "data_limit_billing_date": 1,
        "data_limit_size": 1000000000,
        "data_usage_monitoring_interval": 30,
        "data_usage_warning_thresholds": [75, 90, 95],

        # On-demand configuration
        "on_demand_idle_timeout": 300,
        "on_demand_traffic_threshold": 1024,

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
        "system_health_check_interval": 300,

        # Logging and monitoring settings
        "verbose_logging": True,
        "log_level": "info",
        "snmp_monitoring": True,
        "detailed_status": True,

        # Enhanced reconnection settings
        "enhanced_reconnection": {
            "enabled": False,
            "signal_threshold": -85,
            "retry_interval_good_signal": 15,
            "retry_interval_poor_signal": 45,
            "max_wait_for_signal": 120,
            "signal_check_interval": 10,
            "signal_strength_buffer": 5
        },

        # Connectivity monitoring settings
        "connectivity_monitoring": {
            "enabled": False,
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
            "registration_recovery_delay": 5,   # Debounce delay before acting on registration loss (seconds)
            "ip_change_delay": 0.5,            # Brief delay for IP change link cycling (seconds)
            "ensure_link_up_on_connect": True, # Ensure interface UP when entering CONNECTED state
            "monitor_bearer_state": True,      # Monitor ModemManager bearer state changes
            "monitor_ip_changes": True,        # Monitor for carrier IP address reassignments
            "interface_up_timeout": 10,        # Timeout for interface up/down operations (seconds)
        },

        # SIM configurations - array of SIM configs
        "sim_slots": [
            {
                "slot": 1,
                "enabled": True,
                "roaming": "disabled",
                "preferred_carrier": "",
                "enable_network_scan": False,  # Control scanning behavior for carrier selection
                "supported_bands": ["all"],
                "pdp_type": "ipv4",
                # Enhanced APN configuration - supports both formats
                "apn": {
                    "name": "",              # APN name (e.g., "internet.t-mobile.com")
                    "username": "",          # Optional username for authentication
                    "password": "",          # Optional password for authentication
                    "auth_type": "none"      # "none", "pap", "chap", or "pap-chap"
                },
                "pin": "",           # SIM PIN
                "puk": "",           # SIM PUK
                "new_pin": "",       # New PIN when unlocking with PUK
                "auto_unlock": True  # Automatically unlock SIM with stored PIN
            },
            {
                "slot": 2,
                "enabled": False,
                "roaming": "disabled",
                "preferred_carrier": "",
                "enable_network_scan": False,  # Control scanning behavior for carrier selection
                "supported_bands": ["all"],
                "pdp_type": "ipv4",
                "apn": {
                    "name": "",
                    "username": "",
                    "password": "",
                    "auth_type": "none"
                },
                "pin": "",           # SIM PIN
                "puk": "",           # SIM PUK
                "new_pin": "",       # New PIN when unlocking with PUK
                "auto_unlock": True  # Automatically unlock SIM with stored PIN
            }
        ]
    }

    def __init__(self, interface_number: int, fsm):
        super().__init__("com.igos.IgosModemManager.Interface")
        self.interface_number = interface_number
        self.fsm = fsm

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
                    f"Corrupt configuration file, removing: {je}",
                    extra={'interface_number': self.interface_number,
                           'config_file': self.config_state_file})
                try:
                    os.remove(self.config_state_file)
                except OSError:
                    pass
                return

            logger.info("Restored configuration from persistent storage",
                       extra={'interface_number': self.interface_number,
                              'config_file': self.config_state_file})

            # Apply the restored configuration
            from dbus_next import Variant  # pylint: disable=import-error
            dbus_config = {}
            for key, value in saved_config.items():
                # Convert back to D-Bus variants
                if isinstance(value, bool):
                    dbus_config[key] = Variant('b', value)
                elif isinstance(value, int):
                    dbus_config[key] = Variant('i', value)
                elif isinstance(value, str):
                    dbus_config[key] = Variant('s', value)
                elif isinstance(value, list):
                    # Handle lists - assume string arrays for now
                    dbus_config[key] = Variant('as', value)
                else:
                    dbus_config[key] = Variant('s', str(value))

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

            logger.info("Restored configuration applied successfully",
                       extra={'interface_number': self.interface_number})

        except Exception as e:
            logger.error(f"Failed to apply restored configuration: {e}",
                        extra={'interface_number': self.interface_number})

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
    async def set_configuration(self, config: 'a{sv}') -> 's':
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
                              'active_sim': cfg.get('active_sim_slot', 1),
                              'connectivity_monitoring': cfg.get('connectivity_monitoring', {}).get('enabled', False)})
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
                    merged_slot[key] = (
                        new_slot.get(key) if new_slot else None
                    ) or (
                        current_slot.get(key) if current_slot else None
                    ) or default_slot[key]

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

    def _merge_connectivity_monitoring(self, new_monitoring, current_monitoring, default_monitoring):
        """Merge connectivity monitoring configurations"""
        if not new_monitoring:
            return current_monitoring or default_monitoring

        # Start with default
        merged = default_monitoring.copy()

        # Apply current values
        if current_monitoring:
            merged.update(current_monitoring)

        # Apply new values
        merged.update(new_monitoring)

        return merged

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
        if 'on_demand' in config and config['on_demand'] not in ['enabled', 'disabled']:
            logger.warning("Invalid on_demand value",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'on_demand'})
            raise ValueError("on_demand must be 'enabled' or 'disabled'")

        # Validate active SIM slot
        if 'active_sim_slot' in config:
            slot = config['active_sim_slot']
            if not isinstance(slot, int) or slot not in [1, 2]:
                logger.warning("Invalid active_sim_slot",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'active_sim_slot'})
                raise ValueError("active_sim_slot must be 1 or 2")

        # Validate SIM failover
        if 'sim_failover' in config and config['sim_failover'] not in ['enabled', 'disabled']:
            logger.warning("Invalid sim_failover value",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'sim_failover'})
            raise ValueError("sim_failover must be 'enabled' or 'disabled'")

        # Validate failover
        if 'failover' in config and config['failover'] not in ['enabled', 'disabled']:
            logger.warning("Invalid failover value",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'failover'})
            raise ValueError("failover must be 'enabled' or 'disabled'")

        # Validate SIM slots configuration
        if 'sim_slots' in config:
            sim_slots = config['sim_slots']
            if not isinstance(sim_slots, list):
                logger.warning("Invalid sim_slots type",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_slots'})
                raise ValueError("sim_slots must be a list")

       # Validate connectivity monitoring configuration
        if 'connectivity_monitoring' in config:
            self._validate_connectivity_monitoring(config['connectivity_monitoring'])

        # Validate other parameters (failover timers, data limits, etc.)
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

        # Validate new PIN (for PUK unlock)
        if 'new_pin' in sim_slot:
            new_pin = sim_slot['new_pin']
            if not isinstance(new_pin, str):
                logger.warning("Invalid SIM new_pin type",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_slots',
                                     'sim_slot': slot_num})
                raise ValueError(f"SIM{slot_num} new_pin must be a string")

            if new_pin and not re.match(r'^\d{4,8}$', new_pin):
                logger.warning("Invalid SIM new_pin format",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'sim_slots',
                                     'sim_slot': slot_num})
                raise ValueError(f"SIM{slot_num} new_pin must be 4-8 digits")

        # Validate auto_unlock flag
        if 'auto_unlock' in sim_slot and not isinstance(sim_slot['auto_unlock'], bool):
            logger.warning("Invalid SIM auto_unlock flag",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'sim_slots',
                                 'sim_slot': slot_num})
            raise ValueError(f"SIM{slot_num} auto_unlock must be true or false")

        # Cross-validation: if PUK is provided, new_pin should also be provided
        if sim_slot.get('puk') and not sim_slot.get('new_pin'):
            logger.warning("PUK provided without new_pin",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'sim_slots',
                                 'sim_slot': slot_num})
            raise ValueError(f"SIM{slot_num}: when puk is provided, new_pin must also be provided")

        logger.info("SIM configuration validation passed",
                   extra={'interface_number': self.interface_number,
                          'sim_slot': slot_num,
                          'has_pin': bool(sim_slot.get('pin')),
                          'has_puk': bool(sim_slot.get('puk')),
                          'auto_unlock': sim_slot.get('auto_unlock', True),
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

        # Validate failover_connect_retries
        if 'failover_connect_retries' in config:
            retries = config['failover_connect_retries']
            if not isinstance(retries, int) or retries < 0 or retries > 100:
                logger.warning("Invalid failover_connect_retries",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'failover_connect_retries'})
                raise ValueError("failover_connect_retries must be an integer between 0 and 100")

        # Validate failover_revert_timer
        if 'failover_revert_timer' in config:
            timer = config['failover_revert_timer']
            if not isinstance(timer, int) or timer < 0 or timer > 86400:
                logger.warning("Invalid failover_revert_timer",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'failover_revert_timer'})
                raise ValueError("failover_revert_timer must be an integer between 0 and 86400 seconds")

        # Validate failover_signal_loss_timer
        if 'failover_signal_loss_timer' in config:
            timer = config['failover_signal_loss_timer']
            if not isinstance(timer, int) or timer < 1 or timer > 3600:
                logger.warning("Invalid failover_signal_loss_timer",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'failover_signal_loss_timer'})
                raise ValueError("failover_signal_loss_timer must be an integer between 1 and 3600 seconds")

        # Validate data_limit_billing_date
        if 'data_limit_billing_date' in config:
            date = config['data_limit_billing_date']
            if not isinstance(date, int) or date < 1 or date > 28:
                logger.warning("Invalid data_limit_billing_date",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'data_limit_billing_date'})
                raise ValueError("data_limit_billing_date must be an integer between 1 and 28")

        # Validate data_limit_action
        if 'data_limit_action' in config and config['data_limit_action'] not in ['disable', 'throttle', 'block']:
            logger.warning("Invalid data_limit_action",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'data_limit_action'})
            raise ValueError("data_limit_action must be 'disable', 'throttle', or 'block'")

        # Validate signal threshold
        if 'failover_signal_threshold' in config:
            threshold = config['failover_signal_threshold']
            if not isinstance(threshold, int) or threshold < -120 or threshold > 0:
                logger.warning("Invalid failover_signal_threshold",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'failover_signal_threshold'})
                raise ValueError("failover_signal_threshold must be between -120 and 0 dBm")

        # Validate data_limit_size
        if 'data_limit_size' in config:
            size = config['data_limit_size']
            if not isinstance(size, int) or size <= 0:
                logger.warning("Invalid data_limit_size",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'data_limit_size'})
                raise ValueError("data_limit_size must be a positive integer (bytes)")

        # Validate APN discovery settings
        if 'android_apn_discovery' in config and config['android_apn_discovery'] not in ['enabled', 'disabled']:
            logger.warning("Invalid android_apn_discovery",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'android_apn_discovery'})
            raise ValueError("android_apn_discovery must be 'enabled' or 'disabled'")

        if 'apn_caching' in config and config['apn_caching'] not in ['enabled', 'disabled']:
            logger.warning("Invalid apn_caching",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'apn_caching'})
            raise ValueError("apn_caching must be 'enabled' or 'disabled'")

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

        if 'system_health_check_interval' in config:
            interval = config['system_health_check_interval']
            if not isinstance(interval, int) or interval < 60 or interval > 7200:
                logger.warning("Invalid system_health_check_interval",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'system_health_check_interval'})
                raise ValueError("system_health_check_interval must be between 60 and 7200 seconds")

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

        if 'snmp_monitoring' in config and not isinstance(config['snmp_monitoring'], bool):
            logger.warning("Invalid snmp_monitoring",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'snmp_monitoring'})
            raise ValueError("snmp_monitoring must be true or false")

        if 'detailed_status' in config and not isinstance(config['detailed_status'], bool):
            logger.warning("Invalid detailed_status",
                          extra={'interface_number': self.interface_number,
                                 'validation_field': 'detailed_status'})
            raise ValueError("detailed_status must be true or false")

        # Validate on-demand settings
        if 'on_demand_idle_timeout' in config:
            timeout = config['on_demand_idle_timeout']
            if not isinstance(timeout, int) or timeout < 60 or timeout > 7200:
                logger.warning("Invalid on_demand_idle_timeout",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'on_demand_idle_timeout'})
                raise ValueError("on_demand_idle_timeout must be between 60 and 7200 seconds")

        if 'on_demand_traffic_threshold' in config:
            threshold = config['on_demand_traffic_threshold']
            if not isinstance(threshold, int) or threshold < 100 or threshold > 1000000:
                logger.warning("Invalid on_demand_traffic_threshold",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'on_demand_traffic_threshold'})
                raise ValueError("on_demand_traffic_threshold must be between 100 and 1000000 bytes/second")

        # Validate data usage warning thresholds
        if 'data_usage_warning_thresholds' in config:
            thresholds = config['data_usage_warning_thresholds']
            if not isinstance(thresholds, list):
                logger.warning("Invalid data_usage_warning_thresholds type",
                              extra={'interface_number': self.interface_number,
                                     'validation_field': 'data_usage_warning_thresholds'})
                raise ValueError("data_usage_warning_thresholds must be a list")

            for threshold in thresholds:
                if not isinstance(threshold, (int, float)) or threshold < 1 or threshold > 100:
                    logger.warning("Invalid data usage warning threshold value",
                                  extra={'interface_number': self.interface_number,
                                         'validation_field': 'data_usage_warning_thresholds'})
                    raise ValueError("Each data usage warning threshold must be between 1 and 100 percent")

    def _normalize_connectivity_monitoring(self, config_data):
        """Normalize connectivity monitoring configuration"""
        connectivity = config_data.get('connectivity_monitoring', {})

        if not isinstance(connectivity, dict):
            return {'enabled': False}

        # Normalize with safe defaults
        normalized = {
            'enabled': connectivity.get('enabled', False),
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
                          'enabled': connectivity_config.get('enabled', False),
                          'interval': connectivity_config.get('interval', 60),
                          'test_ipv4': test_ipv4,
                          'test_ipv6': test_ipv6})

    @method()
    async def set_active_sim(self, sim_slot: 'i') -> 's':
        """Switch to a different SIM slot"""
        try:
            if sim_slot not in [1, 2]:
                raise ValueError("SIM slot must be 1 or 2")

            logger.info("Switching active SIM slot",
                       extra={'interface_number': self.interface_number,
                              'sim_slot': sim_slot})

            # Update configuration
            config = getattr(self.fsm, 'config', {})
            config['active_sim_slot'] = sim_slot
            self.fsm.apply_config(config)

            return f"Switched to SIM{sim_slot} on interface {self.interface_number}"

        except Exception as e:
            logger.error("Failed to switch SIM slot",
                        extra={'interface_number': self.interface_number,
                               'sim_slot': sim_slot,
                               'error': str(e)})
            raise DBusError("com.igos.IgosModemManager.SIMSwitchError", str(e))

    @method()
    async def unlock_sim(self, sim_slot: 'i', pin: 's') -> 's':
        """Unlock SIM with PIN"""
        try:
            if sim_slot not in [1, 2]:
                raise ValueError("SIM slot must be 1 or 2")

            if not re.match(r'^\d{4,8}$', pin):
                raise ValueError("PIN must be 4-8 digits")

            logger.info("Unlocking SIM with PIN",
                       extra={'interface_number': self.interface_number,
                              'sim_slot': sim_slot})

            # Store PIN in configuration for future auto-unlock
            config = getattr(self.fsm, 'config', {})
            sim_slots = config.get('sim_slots', [])

            # Update the specific SIM slot with the PIN
            for slot in sim_slots:
                if slot['slot'] == sim_slot:
                    slot['pin'] = pin
                    slot['auto_unlock'] = True
                    break

            self.fsm.apply_config(config)

            # Trigger SIM unlock in state machine
            from vyos.utils.wwan.interfaces_wwan_state_machine import ModemEvent
            self.fsm.transition(ModemEvent.SIM_READY)

            return f"SIM{sim_slot} unlock initiated on interface {self.interface_number}"

        except Exception as e:
            logger.error("Failed to unlock SIM",
                        extra={'interface_number': self.interface_number,
                               'sim_slot': sim_slot,
                               'error': str(e)})
            raise DBusError("com.igos.IgosModemManager.SIMUnlockError", str(e))

    @method()
    async def unlock_sim_with_puk(self, sim_slot: 'i', puk: 's', new_pin: 's') -> 's':
        """Unlock SIM with PUK and set new PIN"""
        try:
            if sim_slot not in [1, 2]:
                raise ValueError("SIM slot must be 1 or 2")

            if not re.match(r'^\d{8}$', puk):
                raise ValueError("PUK must be exactly 8 digits")

            if not re.match(r'^\d{4,8}$', new_pin):
                raise ValueError("New PIN must be 4-8 digits")

            logger.info("Unlocking SIM with PUK",
                       extra={'interface_number': self.interface_number,
                              'sim_slot': sim_slot})

            # Store PUK and new PIN in configuration
            config = getattr(self.fsm, 'config', {})
            sim_slots = config.get('sim_slots', [])

            # Update the specific SIM slot
            for slot in sim_slots:
                if slot['slot'] == sim_slot:
                    slot['puk'] = puk
                    slot['new_pin'] = new_pin
                    slot['pin'] = new_pin  # New PIN becomes the active PIN
                    slot['auto_unlock'] = True
                    break

            self.fsm.apply_config(config)

            # Trigger SIM unlock in state machine
            from vyos.utils.wwan.interfaces_wwan_state_machine import ModemEvent
            self.fsm.transition(ModemEvent.SIM_READY)

            return f"SIM{sim_slot} PUK unlock initiated on interface {self.interface_number}"

        except Exception as e:
            logger.error("Failed to unlock SIM with PUK",
                        extra={'interface_number': self.interface_number,
                               'sim_slot': sim_slot,
                               'error': str(e)})
            raise DBusError("com.igos.IgosModemManager.PUKUnlockError", str(e))

    @method()
    async def connect(self) -> 's':
        """Request connection. Always accepted — the service handles state internally.

        If the FSM is already in a connectable state, fires the transition
        immediately.  Otherwise, sets a ``connect_requested`` flag on the FSM
        so that connection proceeds automatically as soon as the modem is ready.
        The caller never needs to know or care about FSM state.
        """
        try:
            current_state = (
                getattr(self.fsm.machine, 'current_state', 'UNKNOWN')
                if hasattr(self.fsm, 'machine') and self.fsm.machine
                else 'UNKNOWN'
            )

            logger.info("Connect requested",
                       extra={'interface_number': self.interface_number,
                              'current_state': current_state})

            # States where CONNECT transition is valid right now
            connectable_states = {'FAILED'}
            # States where we are already connected / on the way
            already_connected_states = {'CONNECTED', 'CONNECTING', 'USAGE_MONITORING'}

            if current_state == 'CONFIGURING':
                self.fsm.connect_requested = True
                msg = (f"Connect request queued for interface {self.interface_number} "
                       f"while configuration is still in progress.")
                logger.info(msg, extra={'interface_number': self.interface_number,
                                        'current_state': current_state})
                return msg

            if current_state in already_connected_states:
                msg = (f"Interface {self.interface_number} is already "
                       f"in state {current_state} — no action needed")
                logger.info(msg, extra={'interface_number': self.interface_number})
                return msg

            if current_state in connectable_states:
                from vyos.utils.wwan.interfaces_wwan_state_machine import ModemEvent
                self.fsm.transition(ModemEvent.CONNECT)
                return f"connect() on {self.interface_number}"

            # Not ready yet — queue the request so FSM connects when it can
            self.fsm.connect_requested = True
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
    async def disconnect(self) -> 's':
        try:
            logger.info("Disconnecting interface",
                       extra={'interface_number': self.interface_number})
            from vyos.utils.wwan.interfaces_wwan_state_machine import ModemEvent, ModemState

            current_state = self.fsm.machine.current_state if hasattr(self.fsm, 'machine') and self.fsm.machine else 'UNKNOWN'

            # States where disconnect is a no-op (already disconnected or not connected)
            already_disconnected = {
                ModemState.DISCONNECTED.value,
                ModemState.SCANNING.value,
                ModemState.INITIAL.value,
                ModemState.WAITING_FOR_CONFIG.value,
                ModemState.MODEM_FOUND.value,
                ModemState.WAITING_FOR_SIM.value,
            }
            if current_state in already_disconnected:
                msg = f"Interface {self.interface_number} not connected (state: {current_state})"
                logger.info(msg, extra={'interface_number': self.interface_number})
                return msg

            # States where disconnect is valid
            disconnectable = {
                ModemState.CONNECTED.value,
                ModemState.USAGE_MONITORING.value,
                ModemState.SIM_SWITCHING.value,
            }
            if current_state in disconnectable:
                self.fsm.transition(ModemEvent.DISCONNECT)
                return f"disconnect() on {self.interface_number}"

            # Transitional states — log and return gracefully rather than error
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
    async def get_status(self) -> 'a{sv}':
        """Get current interface status"""
        try:
            logger.info("Getting interface status",
                       extra={'interface_number': self.interface_number})

            config = getattr(self.fsm, 'config', {})
            active_sim = config.get('active_sim_slot', 1)

            # Safely get values with proper None handling
            current_state = getattr(self.fsm.machine, 'current_state', 'UNKNOWN') if hasattr(self.fsm, 'machine') and self.fsm.machine else 'UNKNOWN'
            modem_path = getattr(self.fsm, 'modem_path', '') or ''
            bearer_path = getattr(self.fsm, 'bearer_path', '') or ''

            status = {
                'interface_number': Variant('i', self.interface_number or 0),
                'current_state': Variant('s', current_state),
                'modem_path': Variant('s', modem_path),
                'bearer_path': Variant('s', bearer_path),
                'config_applied': Variant('b', bool(config)),
                'active_sim_slot': Variant('i', active_sim or 1),
                'sim_failover_enabled': Variant('b', config.get('sim_failover', 'disabled') == 'enabled')
            }

            return status

        except Exception as e:
            logger.error("Failed to get status",
                        extra={'interface_number': self.interface_number,
                               'error': str(e)})
            raise DBusError("com.igos.IgosModemManager.StatusError", str(e))
