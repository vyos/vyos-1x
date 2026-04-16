#!/usr/bin/env python3
# filepath: /home/jfeeney/vyos-1x/python/vyos/utils/wwan/interfaces_wwan_main.py
import asyncio
import subprocess
import sys
from dbus_next.aio import MessageBus  # pylint: disable=import-error
from vyos.utils.wwan.interfaces_wwan_service_manager import ConfigServiceManager
from dbus_next.constants import BusType  # pylint: disable=import-error
from dbus_next.message import Message  # pylint: disable=import-error
from vyos.utils.wwan.wwan_logging import setup_logging


# Set up logging — use root logger for manager so all module logs are captured
logger = setup_logging("", "wwan-manager")

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
                await asyncio.wait_for(bus.call(msg), timeout=5.0)

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
