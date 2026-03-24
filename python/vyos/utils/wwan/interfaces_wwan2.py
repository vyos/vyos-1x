#!/usr/bin/env python3

import os
import sys
import asyncio
import subprocess
import logging
import logging.handlers
from dbus_next.aio import MessageBus  # pylint: disable=import-error
from dbus_next.constants import BusType  # pylint: disable=import-error
from dbus_next.errors import DBusError  # pylint: disable=import-error
from dbus_next import Variant  # pylint: disable=import-error
from vyos.utils.wwan.rfc5424_logging import RFC5424Formatter as _BaseFormatter


class ClientFormatter(_BaseFormatter):
    """Client (interfaces_wwan2) specific RFC 5424 formatter."""

    def _get_message_id(self, record):
        msg = record.getMessage().lower()
        if 'service' in msg and ('start' in msg or 'running' in msg):
            return 'SERVICE_STATUS'
        elif 'configuration' in msg and ('load' in msg or 'applied' in msg):
            return 'CONFIG_EVENT'
        elif 'd-bus' in msg or 'dbus' in msg:
            return 'DBUS_EVENT'
        elif 'interface' in msg and 'add' in msg:
            return 'IFACE_ADD'
        elif 'connect' in msg:
            return 'CONN_EVENT'
        elif 'error' in msg:
            return 'ERROR_EVENT'
        elif 'complete' in msg or 'success' in msg:
            return 'SUCCESS_EVENT'
        else:
            return 'CONFIG_GENERAL'


def setup_logging_client():
    """Set up RFC 5424 logging for SNMP integration"""
    console_formatter = logging.Formatter('%(asctime)s wwan-config[%(process)d]: %(levelname)s: %(message)s')
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)

    try:
        syslog_handler = logging.handlers.SysLogHandler(address='/dev/log')
        syslog_formatter = ClientFormatter("wwan-config")
        syslog_handler.setFormatter(syslog_formatter)
        use_syslog = True
    except (OSError, IOError):
        use_syslog = False

    # Configure logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    if use_syslog:
        logger.addHandler(syslog_handler)
    logger.addHandler(console_handler)
    logger.propagate = False

    return logger


# Set up logging
logger = setup_logging_client()

# ─── parse_config() ────────────────────────────────────────────────────────
def parse_config(config_path):
    """Parse configuration file into dictionary"""
    cfg = {}
    script_dir = os.path.dirname(os.path.abspath(__file__))
    abs_path = os.path.join(script_dir, config_path)

    try:
        with open(abs_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                s = line.strip()
                if s and not s.startswith("#") and "=" in s:
                    k, v = s.split("=", 1)
                    key = k.strip()
                    value = v.strip()

                    # Handle boolean values
                    if value.lower() in ('true', 'false'):
                        cfg[key] = value.lower() == 'true'
                    # Handle integer values (including negative)
                    elif value.lstrip('-').isdigit():
                        cfg[key] = int(value)
                    # Handle comma-separated lists
                    elif ',' in value and key.endswith(('_targets', '_apns', '_bands', '_thresholds')):
                        items = [item.strip() for item in value.split(',') if item.strip()]
                        # Convert numeric lists to integers
                        if key.endswith('_thresholds'):
                            cfg[key] = [int(item) if item.lstrip('-').isdigit() else item for item in items]
                        else:
                            cfg[key] = items
                    else:
                        cfg[key] = value

        logger.info("Configuration loaded",
                   extra={'config_file': config_path, 'param_count': len(cfg)})
        return cfg

    except FileNotFoundError:
        logger.error("Configuration file not found",
                    extra={'config_path': abs_path})
        return {}
    except Exception as e:
        logger.error("Failed to parse configuration file",
                    extra={'config_path': abs_path, 'error': str(e)})
        return {}

# ─── build_config() ─────────────────────────────────────────────────────────
def build_config(raw_cfg):
    """Build configuration dictionary in the format expected by your D-Bus service"""

    # Build SIM slots configuration
    sim_slots = []

    # SIM Slot 1
    sim1 = {
        'slot': 1,
        'apn': raw_cfg.get('sim_slot_1_apn', ''),
        'username': raw_cfg.get('sim_slot_1_username', ''),
        'password': raw_cfg.get('sim_slot_1_password', ''),
        'auth_type': raw_cfg.get('sim_slot_1_auth_type', 'none'),
        'pdp_type': raw_cfg.get('sim_slot_1_pdp_type', 'ipv4'),
        'roaming': raw_cfg.get('sim_slot_1_roaming', 'disabled'),
        'pin': raw_cfg.get('sim_slot_1_pin', ''),
        'puk': raw_cfg.get('sim_slot_1_puk', ''),
        'supported_bands': raw_cfg.get('sim_slot_1_supported_bands', 'all'),
        'preferred_carrier': raw_cfg.get('sim_slot_1_preferred_carrier', ''),
        'enable_network_scan': raw_cfg.get('sim_slot_1_enable_network_scan', False),
        # Per-SIM data usage limits (fallback to global config)
        'data_limit_size': raw_cfg.get('sim_slot_1_data_limit_size', raw_cfg.get('data_limit_size', 0)),
        'data_limit_action': raw_cfg.get('sim_slot_1_data_limit_action', raw_cfg.get('data_limit_action', 'disable')),
        'data_limit_billing_date': raw_cfg.get('sim_slot_1_data_limit_billing_date', raw_cfg.get('data_limit_billing_date', 1)),
    }
    sim_slots.append(sim1)

    # SIM Slot 2 (if configured)
    if any(key.startswith('sim_slot_2_') for key in raw_cfg.keys()):
        sim2 = {
            'slot': 2,
            'apn': raw_cfg.get('sim_slot_2_apn', ''),
            'username': raw_cfg.get('sim_slot_2_username', ''),
            'password': raw_cfg.get('sim_slot_2_password', ''),
            'auth_type': raw_cfg.get('sim_slot_2_auth_type', 'none'),
            'pdp_type': raw_cfg.get('sim_slot_2_pdp_type', 'ipv4'),
            'roaming': raw_cfg.get('sim_slot_2_roaming', 'disabled'),
            'pin': raw_cfg.get('sim_slot_2_pin', ''),
            'puk': raw_cfg.get('sim_slot_2_puk', ''),
            'supported_bands': raw_cfg.get('sim_slot_2_supported_bands', 'all'),
            'preferred_carrier': raw_cfg.get('sim_slot_2_preferred_carrier', ''),
            'enable_network_scan': raw_cfg.get('sim_slot_2_enable_network_scan', False),
            # Per-SIM data usage limits (fallback to global config)
            'data_limit_size': raw_cfg.get('sim_slot_2_data_limit_size', raw_cfg.get('data_limit_size', 0)),
            'data_limit_action': raw_cfg.get('sim_slot_2_data_limit_action', raw_cfg.get('data_limit_action', 'disable')),
            'data_limit_billing_date': raw_cfg.get('sim_slot_2_data_limit_billing_date', raw_cfg.get('data_limit_billing_date', 1)),
        }
        sim_slots.append(sim2)

    # Build connectivity monitoring configuration
    connectivity_monitoring = {
        'enabled': raw_cfg.get('connectivity_monitoring_enabled', False),
        'interval': raw_cfg.get('connectivity_monitoring_interval', 60),
        'timeout': raw_cfg.get('connectivity_monitoring_timeout', 10),
        'retry_count': raw_cfg.get('connectivity_monitoring_retry_count', 3),
        'failure_threshold': raw_cfg.get('connectivity_monitoring_failure_threshold', 2),
        'test_ipv4': raw_cfg.get('connectivity_monitoring_test_ipv4', True),
        'test_ipv6': raw_cfg.get('connectivity_monitoring_test_ipv6', False),
        'require_both': raw_cfg.get('connectivity_monitoring_require_both', False),
        'ipv4_targets': raw_cfg.get('connectivity_monitoring_ipv4_targets', ['8.8.8.8', '1.1.1.1']),
        'ipv6_targets': raw_cfg.get('connectivity_monitoring_ipv6_targets', ['2001:4860:4860::8888', '2606:4700:4700::1111'])
    }

    # Build interface management configuration
    interface_management = {
        'enabled': raw_cfg.get('interface_management_enabled', True),
        'bearer_disconnect_delay': int(raw_cfg.get('bearer_disconnect_delay', 15)),
        'registration_recovery_delay': int(raw_cfg.get('registration_recovery_delay', 20)),
        'ip_change_delay': float(raw_cfg.get('ip_change_delay', 0.5)),
        'ensure_link_up_on_connect': raw_cfg.get('ensure_link_up_on_connect', True),
        'monitor_bearer_state': raw_cfg.get('monitor_bearer_state', True),
        'monitor_ip_changes': raw_cfg.get('monitor_ip_changes', True),
        'interface_up_timeout': int(raw_cfg.get('interface_up_timeout', 10))
    }

    # Build enhanced reconnection configuration
    enhanced_reconnection = {
        'enabled': raw_cfg.get('enhanced_reconnection', 'disabled') == 'enabled',
        'signal_threshold': raw_cfg.get('reconnection_signal_threshold', -85),
        'retry_interval_good_signal': raw_cfg.get('retry_interval_good_signal', 15),
        'retry_interval_poor_signal': raw_cfg.get('retry_interval_poor_signal', 45),
        'max_wait_for_signal': raw_cfg.get('max_wait_for_signal', 120),
        'signal_check_interval': raw_cfg.get('signal_check_interval', 10),
        'signal_strength_buffer': raw_cfg.get('signal_strength_buffer', 5)
    }

    # Build complete configuration
    config = {
        # Basic interface settings
        'active_sim_slot': raw_cfg.get('active_sim_slot', 1),
        'connection_mode': raw_cfg.get('connection_mode', 'always-on'),

        # Enhanced reconnection strategy
        'enhanced_reconnection': enhanced_reconnection,

        # APN discovery settings
        'android_apn_discovery': raw_cfg.get('android_apn_discovery', 'disabled'),

        # SIM failover settings (global enable + policy)
        'sim_failover': raw_cfg.get('sim_failover', 'disabled'),
        'sim_failover_connect_retries': raw_cfg.get('sim_failover_connect_retries', 3),
        'sim_failover_revert_timer': raw_cfg.get('sim_failover_revert_timer', 300),
        'sim_failover_signal_loss_timer': raw_cfg.get('sim_failover_signal_loss_timer', 60),
        'sim_failover_signal_threshold': raw_cfg.get('sim_failover_signal_threshold', -90),

        # SIM failback settings — automatically return to primary SIM after sim-failover
        'sim_failback_enabled': raw_cfg.get('sim_failback_enabled', 'disabled') == 'enabled',
        'sim_failback_check_interval': int(raw_cfg.get('sim_failback_check_interval', 600)),

        # Data usage settings (per-SIM only — see sim_slots entries)
        'data_usage_monitoring_interval': raw_cfg.get('data_usage_monitoring_interval', 30),
        'data_usage_warning_thresholds': raw_cfg.get('data_usage_warning_thresholds', [75, 90, 95]),

        # Hardware management settings
        'hardware_reset_enabled': raw_cfg.get('hardware_reset_enabled', True),
        'max_hardware_resets': raw_cfg.get('max_hardware_resets', 3),
        'hardware_reset_cooldown': raw_cfg.get('hardware_reset_cooldown', 300),

        # Connection and timeout settings
        'connection_timeout': raw_cfg.get('connection_timeout', 120),
        'registration_timeout': raw_cfg.get('registration_timeout', 180),
        'network_scan_timeout': raw_cfg.get('network_scan_timeout', 60),
        'network_mode': raw_cfg.get('network_mode', 'auto'),

        # Global modem-level radio technology selection (2G, 3G, LTE, 5G, all)
        'radio_technology': raw_cfg.get('radio_technology', 'all'),

        # Monitoring intervals
        'normal_monitoring_interval': raw_cfg.get('normal_monitoring_interval', 30),
        'system_health_check_interval': raw_cfg.get('system_health_check_interval', 300),

        # Logging and monitoring settings
        'verbose_logging': raw_cfg.get('verbose_logging', True),
        'log_level': raw_cfg.get('log_level', 'info'),
        'snmp_monitoring': raw_cfg.get('snmp_monitoring', True),
        'detailed_status': raw_cfg.get('detailed_status', True),

        # SIM slots, connectivity monitoring, and interface management
        'sim_slots': sim_slots,
        'connectivity_monitoring': connectivity_monitoring,
        'interface_management': interface_management
    }

    return config

# ─── D-Bus variant conversion ──────────────────────────────────────────────
def python_to_dbus_variant(value):
    """Convert Python values to D-Bus Variant objects recursively"""
    if isinstance(value, dict):
        # Convert dictionary to D-Bus variant dictionary
        return Variant('a{sv}', {k: python_to_dbus_variant(v) for k, v in value.items()})
    elif isinstance(value, list):
        if not value:
            # Empty list - use string array as default
            return Variant('as', [])
        elif all(isinstance(x, str) for x in value):
            # String array
            return Variant('as', value)
        elif all(isinstance(x, int) for x in value):
            # Integer array
            return Variant('ai', value)
        elif all(isinstance(x, (int, float)) for x in value):
            # Number array (convert to doubles)
            return Variant('ad', [float(x) for x in value])
        else:
            # Mixed array - convert each element
            return Variant('av', [python_to_dbus_variant(x) for x in value])
    elif isinstance(value, bool):
        return Variant('b', value)
    elif isinstance(value, int):
        # Handle large integers that exceed INT32 range
        if -2147483648 <= value <= 2147483647:
            return Variant('i', value)  # INT32
        else:
            return Variant('x', value)  # INT64
    elif isinstance(value, float):
        return Variant('d', value)
    elif isinstance(value, str):
        return Variant('s', value)
    else:
        # Fallback: convert to string
        return Variant('s', str(value))

# ─── service management ─────────────────────────────────────────────────────
async def ensure_service_running():
    """Ensure the WWAN D-Bus service is running"""

    # Check if service is already running
    try:
        chk = subprocess.run(
            ["pgrep", "-f", "interfaces_wwan_main.py"],
            capture_output=True,
            text=True
        )

        if chk.returncode == 0:
            logger.info("WWAN service already running",
                       extra={'pid': chk.stdout.strip()})
            return True

    except Exception as e:
        logger.warning("Error checking service status",
                      extra={'error': str(e)})

    # Start the service
    logger.info("Starting WWAN D-Bus service")
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        service_path = os.path.join(script_dir, "interfaces_wwan_main.py")

        if not os.path.exists(service_path):
            logger.error("Service script not found",
                        extra={'service_path': service_path})
            return False

        # Start service in background
        subprocess.Popen([
            "python3", service_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Wait for service to start
        logger.info("Waiting for service to initialize")
        await asyncio.sleep(3)

        # Verify service started
        chk = subprocess.run(
            ["pgrep", "-f", "interfaces_wwan_main.py"],
            capture_output=True,
            text=True
        )

        if chk.returncode == 0:
            logger.info("Service started successfully",
                       extra={'pid': chk.stdout.strip()})
            return True
        else:
            logger.error("Service failed to start")
            return False

    except Exception as e:
        logger.error("Failed to start service",
                    extra={'error': str(e)})
        return False

# ─── configuration logic ─────────────────────────────────────────────────────
async def configure_interface(config):
    """Configure the WWAN interface via D-Bus"""

    interface_number = config.get('interface_number', 0)
    bus_name = "com.igos.IgosModemManager"

    try:
        # Connect to D-Bus
        logger.info("Connecting to D-Bus")
        bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

        # Wait for D-Bus service to be available with retry loop
        logger.info("Waiting for WWAN service to be available")
        ctrl_path = "/com/igos/IgosModemManager/Control"
        max_retries = 30  # 30 seconds max wait
        retry_interval = 1  # 1 second between retries

        for attempt in range(max_retries):
            try:
                intro = await bus.introspect(bus_name, ctrl_path)
                ctrl_obj = bus.get_proxy_object(bus_name, ctrl_path, intro)
                ctrl_iface = ctrl_obj.get_interface("com.igos.IgosModemManager.Control")
                logger.info("WWAN service is available",
                           extra={'attempt': attempt + 1})
                break
            except DBusError as e:
                if attempt < max_retries - 1:
                    logger.debug("Service not ready yet, waiting",
                                extra={'attempt': attempt + 1, 'max_attempts': max_retries})
                    await asyncio.sleep(retry_interval)
                else:
                    logger.error("WWAN service did not become available",
                                extra={'max_wait_seconds': max_retries, 'error': str(e)})
                    return False

        # Add interface if it doesn't exist
        logger.info("Adding interface",
                   extra={'interface_number': interface_number})
        try:
            result = await asyncio.wait_for(ctrl_iface.call_add_interface(interface_number), timeout=30.0)
            logger.info("Interface added",
                       extra={'interface_number': interface_number, 'result': result})

        except asyncio.TimeoutError:
            logger.error("Adding interface timed out",
                        extra={'interface_number': interface_number, 'timeout_seconds': 30})
            return False
        except DBusError as e:
            error_str = str(e).lower()
            if "already exists" in error_str or "already exported" in error_str:
                logger.info("Interface already exists, continuing with configuration",
                           extra={'interface_number': interface_number})
            else:
                logger.error("Error adding interface",
                            extra={'interface_number': interface_number, 'error': str(e)})
                return False

        # Wait for interface to be ready
        await asyncio.sleep(1)

        # Configure the interface
        logger.info("Applying configuration",
                   extra={'interface_number': interface_number})
        obj_path = f"/com/igos/IgosModemManager/Interface{interface_number}"

        try:
            intro2 = await bus.introspect(bus_name, obj_path)
            cfg_obj = bus.get_proxy_object(bus_name, obj_path, intro2)
            cfg_iface = cfg_obj.get_interface("com.igos.IgosModemManager.Interface")

            # Apply configuration using your current D-Bus interface
            # Convert config to D-Bus variants
            dbus_config = {k: python_to_dbus_variant(v) for k, v in config.items()}
            result = await cfg_iface.call_set_configuration(dbus_config)
            logger.info("Configuration applied",
                       extra={'interface_number': interface_number, 'result': result})

            # Connection is managed by the FSM based on connection_mode:
            # always-on / dial-on-demand: auto-connects after configuration
            # connect-on-demand: parks at REGISTERED_IDLE, waits for D-Bus connect()

            return True

        except DBusError as e:
            logger.error("Error configuring interface",
                        extra={'interface_number': interface_number, 'error': str(e)})
            return False

    except Exception as e:
        logger.error("D-Bus configuration failed",
                    extra={'interface_number': interface_number, 'error': str(e)})
        return False

# ─── status monitoring ─────────────────────────────────────────────────────
async def monitor_status(interface_number, duration=30):
    """Monitor interface status for a specified duration"""

    bus_name = "com.igos.IgosModemManager"
    obj_path = f"/com/igos/IgosModemManager/Interface{interface_number}"

    try:
        bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        intro = await bus.introspect(bus_name, obj_path)
        obj = bus.get_proxy_object(bus_name, obj_path, intro)
        iface = obj.get_interface("com.igos.IgosModemManager.Interface")

        logger.info("Starting status monitoring",
                   extra={'interface_number': interface_number, 'duration_seconds': duration})
        logger.info("=" * 60)

        for i in range(duration):
            try:
                status = await iface.call_get_status()
                logger.info(f"[{i+1:2d}s] Status: {status}")
                await asyncio.sleep(1)

            except Exception as e:
                logger.warning(f"[{i+1:2d}s] Error getting status: {e}")
                await asyncio.sleep(1)

        logger.info("=" * 60)
        logger.info("Status monitoring complete",
                   extra={'interface_number': interface_number})

    except Exception as e:
        logger.error("Status monitoring failed",
                    extra={'interface_number': interface_number, 'error': str(e)})

# ─── main execution ─────────────────────────────────────────────────────────
async def main():
    """Main execution function"""

    logger.info("WWAN Interface Configuration Tool started")
    logger.info("=" * 50)

    # Parse configuration
    raw_cfg = parse_config("my_config.conf")
    if not raw_cfg:
        logger.error("Failed to load configuration")
        return 1

    config = build_config(raw_cfg)
    interface_number = raw_cfg.get('interface_number', 0)

    logger.info("Configuration summary",
               extra={
                   'interface_number': interface_number,
                   'active_sim_slot': config['active_sim_slot'],
                   'connectivity_monitoring': config['connectivity_monitoring']['enabled']
               })

    # Ensure service is running
    if not await ensure_service_running():
        logger.error("Could not start WWAN service")
        return 1

    # Configure interface
    if not await configure_interface(config):
        logger.error("Interface configuration failed",
                    extra={'interface_number': interface_number})
        return 1

    logger.info("Configuration complete!",
               extra={'interface_number': interface_number})

    # Optional: Monitor status
    monitor_duration = raw_cfg.get('monitor_duration', 0)
    if monitor_duration > 0:
        await monitor_status(interface_number, monitor_duration)

    return 0

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.critical("Fatal error",
                       extra={'error': str(e)})
        sys.exit(1)
