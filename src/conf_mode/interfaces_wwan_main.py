#!/usr/bin/env python3
# filepath: /home/jfeeney/vyos-1x/src/conf_mode/interfaces_wwan_main.py
import asyncio
import subprocess
import sys
import logging
import logging.handlers
import socket
from datetime import datetime, timezone
from dbus_next.aio import MessageBus  # pylint: disable=import-error
from interfaces_wwan_service_manager import ConfigServiceManager
from dbus_next.constants import BusType  # pylint: disable=import-error
from dbus_next.message import Message  # pylint: disable=import-error

class RFC5424Formatter(logging.Formatter):
    """RFC 5424 compliant syslog formatter for SNMP integration"""

    # Facility: local use facilities (16-23)
    FACILITY_MAP = {
        'wwan-manager': 16,    # local0
        'wwan-service': 17,    # local1
        'wwan-config': 18,     # local2
        'wwan-fsm': 19,        # local3
    }

    SEVERITY_MAP = {
        logging.DEBUG: 7,      # debug
        logging.INFO: 6,       # info
        logging.WARNING: 4,    # warning
        logging.ERROR: 3,      # error
        logging.CRITICAL: 2    # critical
    }

    def __init__(self, app_name="wwan-manager"):
        super().__init__()
        self.app_name = app_name
        self.hostname = socket.gethostname()
        self.facility = self.FACILITY_MAP.get(app_name, 16)

    def format(self, record):
        # Calculate priority (facility * 8 + severity)
        severity = self.SEVERITY_MAP.get(record.levelno, 6)
        priority = self.facility * 8 + severity

        # RFC 5424 timestamp with microseconds and timezone
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc)
        timestamp_str = timestamp.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

        # Process ID
        pid = record.process or '-'

        # Message ID based on log content for SNMP categorization
        msgid = self._get_message_id(record)

        # Structured data for SNMP monitoring
        structured_data = self._build_structured_data(record)

        # Format: <priority>version timestamp hostname app-name procid msgid structured-data msg
        rfc5424_msg = (
            f"<{priority}>1 {timestamp_str} {self.hostname} "
            f"{self.app_name} {pid} {msgid} {structured_data} {record.getMessage()}"
        )

        return rfc5424_msg

    def _get_message_id(self, record):
        """Generate message ID for SNMP categorization"""
        msg = record.getMessage().lower()

        # Categorize messages for SNMP monitoring
        if 'modemmanager' in msg and ('crash' in msg or 'stop' in msg):
            return 'MM_CRASH'
        elif 'restart' in msg and 'modemmanager' in msg:
            return 'MM_RESTART'
        elif 'starting wwan' in msg:
            return 'SERVICE_START'
        elif 'stopped' in msg or 'shutting down' in msg:
            return 'SERVICE_STOP'
        elif 'stable again' in msg:
            return 'MM_STABLE'
        elif 'd-bus' in msg and 'available' in msg:
            return 'DBUS_READY'
        elif 'd-bus' in msg and 'responsive' in msg:
            return 'DBUS_READY'
        elif 'interface' in msg and 'add' in msg:
            return 'IFACE_ADD'
        elif 'interface' in msg and 'remove' in msg:
            return 'IFACE_REMOVE'
        elif 'connect' in msg:
            return 'CONN_EVENT'
        elif 'configuration' in msg:
            return 'CONFIG_EVENT'
        elif 'waiting for' in msg and 'initialize' in msg:
            return 'MM_WAIT'
        elif 'error' in msg:
            return 'ERROR_EVENT'
        else:
            return 'GENERAL'

    def _build_structured_data(self, record):
        """Build structured data section for SNMP monitoring"""
        sd_elements = []

        # Add WWAN-specific structured data
        wwan_data = []
        if hasattr(record, 'interface_number'):
            wwan_data.append(f'interface="{record.interface_number}"')
        if hasattr(record, 'restart_attempt'):
            wwan_data.append(f'attempt="{record.restart_attempt}"')
            wwan_data.append(f'max_attempts="{record.max_attempts}"')
        if hasattr(record, 'modem_state'):
            wwan_data.append(f'state="{record.modem_state}"')
        if hasattr(record, 'signal_strength'):
            wwan_data.append(f'signal="{record.signal_strength}"')
        if hasattr(record, 'software'):
            wwan_data.append(f'software="{record.software}"')
        if hasattr(record, 'version'):
            wwan_data.append(f'version="{record.version}"')

        if wwan_data:
            sd_elements.append(f'[wwan@32473 {" ".join(wwan_data)}]')

        # Add origin structured data for SNMP source tracking
        origin_data = [f'software="vyos-wwan"', f'version="1.0"']
        sd_elements.append(f'[origin@32473 {" ".join(origin_data)}]')

        return ''.join(sd_elements) if sd_elements else '-'

def setup_rfc5424_logging():
    """Set up RFC 5424 compliant logging for SNMP integration"""

    # Create formatters for different components
    main_formatter = RFC5424Formatter("wwan-manager")

    # Set up handler for system syslog
    try:
        syslog_handler = logging.handlers.SysLogHandler(address='/dev/log', facility=logging.handlers.SysLogHandler.LOG_LOCAL0)
        syslog_handler.setFormatter(main_formatter)
        use_syslog = True
    except (OSError, IOError):
        use_syslog = False

    # Console handler for debugging (human-readable format)
    console_formatter = logging.Formatter('%(asctime)s %(name)s[%(process)d]: %(levelname)s: %(message)s')
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if use_syslog:
        root_logger.addHandler(syslog_handler)
    root_logger.addHandler(console_handler)

    return root_logger

# Set up RFC 5424 logging for SNMP integration
logger = setup_rfc5424_logging()

class ModemManagerMonitor:
    def __init__(self, service_manager):
        self.service_manager = service_manager
        self.monitoring = False
        self.restart_attempts = 0
        self.max_restart_attempts = 5
        self.restart_delay = 5

    async def monitor_modemmanager(self):
        """Monitor ModemManager and restart if it crashes"""
        self.monitoring = True
        logger.info("ModemManager monitoring started",
                   extra={'max_attempts': self.max_restart_attempts})

        while self.monitoring:
            try:
                # Check if ModemManager is still running
                result = subprocess.run(
                    ["systemctl", "is-active", "ModemManager"],
                    capture_output=True,
                    text=True
                )

                if result.returncode != 0 or result.stdout.strip() != "active":
                    logger.error("ModemManager has crashed or stopped!")
                    await self.handle_modemmanager_crash()
                else:
                    # Reset restart attempts if ModemManager is running fine
                    if self.restart_attempts > 0:
                        logger.info("ModemManager is stable again, resetting restart counter")
                        self.restart_attempts = 0

                # Check every 10 seconds
                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"Error monitoring ModemManager: {e}")
                await asyncio.sleep(5)

    async def handle_modemmanager_crash(self):
        """Handle ModemManager crash by attempting to restart it"""
        if self.restart_attempts >= self.max_restart_attempts:
            logger.error("ModemManager restart attempts exhausted",
                        extra={'restart_attempt': self.restart_attempts,
                               'max_attempts': self.max_restart_attempts})
            await self.service_manager.shutdown()
            return

        self.restart_attempts += 1
        logger.info("Attempting ModemManager restart",
                   extra={'restart_attempt': self.restart_attempts,
                          'max_attempts': self.max_restart_attempts})

        # Try to restart ModemManager
        if await restart_modemmanager():
            logger.info("ModemManager restarted successfully",
                       extra={'restart_attempt': self.restart_attempts})

            # Wait for it to be available on D-Bus
            bus = await wait_for_modemmanager_dbus()
            if bus:
                logger.info("ModemManager is back online, updating service manager")
                # Update the service manager's bus connection
                await self.service_manager.update_bus_connection(bus)
            else:
                logger.error("ModemManager restarted but not available on D-Bus",
                           extra={'restart_attempt': self.restart_attempts})
        else:
            logger.error("Failed to restart ModemManager",
                        extra={'restart_attempt': self.restart_attempts})
            await asyncio.sleep(self.restart_delay)

    def stop_monitoring(self):
        """Stop monitoring ModemManager"""
        self.monitoring = False
        logger.info("ModemManager monitoring stopped")

async def check_and_start_modemmanager():
    """Check if ModemManager is running and start it if necessary"""
    try:
        # Check if ModemManager service is active
        result = subprocess.run(
            ["systemctl", "is-active", "ModemManager"],
            capture_output=True,
            text=True
        )

        if result.returncode == 0 and result.stdout.strip() == "active":
            logger.info("ModemManager is already running")
            return True

        logger.info("ModemManager is not running, attempting to start it...")
        return await restart_modemmanager()

    except Exception as e:
        logger.error(f"Error checking/starting ModemManager: {e}")
        return False

async def restart_modemmanager():
    """Restart ModemManager service with enhanced stability checking"""
    try:
        # First try to stop it cleanly
        stop_result = subprocess.run(
            ["systemctl", "stop", "ModemManager"],
            capture_output=True,
            text=True
        )

        if stop_result.returncode == 0:
            logger.info("ModemManager stopped cleanly")
        else:
            logger.warning(f"ModemManager stop had issues: {stop_result.stderr}")

        # Wait a moment for cleanup
        await asyncio.sleep(2)

        # Start ModemManager
        start_result = subprocess.run(
            ["systemctl", "start", "ModemManager"],
            capture_output=True,
            text=True
        )

        if start_result.returncode == 0:
            logger.info("ModemManager started successfully")

            # ENHANCED: Progressive delay to ensure full initialization
            logger.info("Waiting for ModemManager to fully initialize...")
            await asyncio.sleep(3)  # Basic service start delay

            # Verify it's actually running and stable (not just started)
            for attempt in range(8):  # Check up to 8 times over 8 seconds
                result = subprocess.run(
                    ["systemctl", "is-active", "ModemManager"],
                    capture_output=True, text=True
                )
                if result.stdout.strip() == "active":
                    logger.info(f"ModemManager confirmed active and stable (attempt {attempt + 1})")
                    # Additional stabilization time for D-Bus interface
                    await asyncio.sleep(2)
                    return True

                logger.info(f"ModemManager not yet stable, waiting... (attempt {attempt + 1}/8)")
                await asyncio.sleep(1)

            logger.warning("ModemManager started but stability check failed")
            return True  # Still try to proceed

        else:
            logger.error(f"Failed to start ModemManager: {start_result.stderr}")
            return False

    except Exception as e:
        logger.error(f"Error restarting ModemManager: {e}")
        return False

async def wait_for_modemmanager_dbus():
    """Wait for ModemManager to be available and responsive on D-Bus"""
    bus = None
    max_retries = 20  # Increased from 15
    retry_delay = 2

    logger.info("Waiting for ModemManager D-Bus interface...")

    for attempt in range(max_retries):
        try:
            if bus:
                bus.disconnect()

            bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

            # Try to introspect ModemManager to see if it's ready
            await bus.introspect("org.freedesktop.ModemManager1", "/org/freedesktop/ModemManager1")

            # ENHANCED: Additional verification that MM is fully ready and responsive
            try:
                # Try to call a simple method to verify it's responsive
                # Use ObjectManager.GetManagedObjects instead of Properties.Get
                msg = Message(
                    destination="org.freedesktop.ModemManager1",
                    path="/org/freedesktop/ModemManager1",
                    interface="org.freedesktop.DBus.ObjectManager",
                    member="GetManagedObjects"
                )
                # GetManagedObjects takes no parameters
                reply = await asyncio.wait_for(bus.call(msg), timeout=5.0)

                logger.info("ModemManager is fully available and responsive on D-Bus")
                return bus

            except asyncio.TimeoutError:
                logger.info(f"ModemManager found but not responsive yet (attempt {attempt + 1}/{max_retries})")
            except Exception as e:
                logger.info(f"ModemManager not fully ready yet (attempt {attempt + 1}/{max_retries}): {e}")

        except Exception as e:
            logger.info(f"Waiting for ModemManager on D-Bus (attempt {attempt + 1}/{max_retries}): {e}")

        if bus:
            bus.disconnect()
            bus = None
        await asyncio.sleep(retry_delay)

    logger.error("ModemManager did not become available on D-Bus")
    return None

async def main():
    logger.info("Starting WWAN Interface Manager",
               extra={'software': 'vyos-wwan', 'version': '1.0'})

    # Check and start ModemManager if needed
    if not await check_and_start_modemmanager():
        logger.error("Could not ensure ModemManager is running")
        sys.exit(1)

    # Wait for ModemManager to be available on D-Bus
    bus = await wait_for_modemmanager_dbus()
    if not bus:
        logger.error("ModemManager is not available on D-Bus")
        sys.exit(1)

    manager = None
    monitor = None

    try:
        # Create service manager
        manager = ConfigServiceManager(bus)

        # Create and start ModemManager monitor
        monitor = ModemManagerMonitor(manager)
        monitor_task = asyncio.create_task(monitor.monitor_modemmanager())

        logger.info("Starting WWAN configuration service with ModemManager monitoring...")
        logger.info("Service ready - interfaces will be created via D-Bus calls")

        # Start the service manager without any initial interfaces
        # Interfaces will be created dynamically via D-Bus AddInterface calls
        service_task = asyncio.create_task(manager.run())

        # Wait for either task to complete
        done, pending = await asyncio.wait([monitor_task, service_task], return_when=asyncio.FIRST_COMPLETED)

        # Cancel remaining tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Service error: {e}")
        sys.exit(1)
    finally:
        # Cleanup
        if monitor:
            monitor.stop_monitoring()
        if manager:
            await manager.shutdown()
        if bus:
            bus.disconnect()
        logger.info("WWAN Interface Manager stopped")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(0)
