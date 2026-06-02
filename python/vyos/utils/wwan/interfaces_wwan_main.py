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
    """Restart ModemManager service with enhanced stability checking.

    Performance-sensitive: this runs in the boot path (once per boot
    when there is no existing MM running) and may also be invoked as a
    crash-recovery nuclear option later.  Steps that exist purely for
    the "MM is currently running and possibly wedged" case are skipped
    when MM is inactive, saving ~2s on the cold-start case.
    """
    try:
        # Detect whether MM is currently up.  When it is NOT, the
        # `systemctl stop` + cleanup sleep below are pure waste -- we
        # are about to start it fresh, there is nothing to stop and
        # nothing to drain.  Skipping them shaves ~2s off cold boot.
        is_active = subprocess.run(
            ["systemctl", "is-active", "--quiet", "ModemManager"],
        ).returncode == 0

        if is_active:
            # First try to stop it cleanly
            stop_result = subprocess.run(
                ["systemctl", "stop", "ModemManager"],
                capture_output=True,
                text=True
            )

            if stop_result.returncode == 0:
                logger.info("ModemManager stopped cleanly")
            else:
                logger.warning(
                    f"ModemManager stop had issues: {stop_result.stderr}")

            # Wait a moment for cleanup of the previous instance.
            await asyncio.sleep(2)
        else:
            logger.info("ModemManager is not running, fresh start (no drain)")

        # Re-trigger USB udev rules before starting MM.
        #
        # Why: at cold boot, udev runs the rules for the modem's parent
        # usb_device but in some cases does NOT persist a /run/udev/data
        # entry for it (we have observed +usb:1-1:1.N entries for the
        # USB interfaces but no +usb:1-1 entry for the parent device).
        # MM uses libgudev which reads /run/udev/data/<...> files, so
        # without a parent-device entry MM never sees ID_MM_PHYSDEV_UID
        # and the modem ends up identified by sysfs path instead of by
        # the physical-slot UID we set in 60-Perle-usb-modem.rules.
        #
        # Re-triggering the usb subsystem with action=change forces udev
        # to re-evaluate the rules AND persist the resulting properties
        # to /run/udev/data/+usb:*.  We then `settle` to make sure all
        # workers finish before we hand off to MM.
        #
        # This is cheap (a couple hundred ms on this hardware) and only
        # runs in the MM-start path -- it does not affect steady-state
        # operation.
        logger.info("Re-triggering udev for USB devices before MM start")
        try:
            subprocess.run(
                ["udevadm", "trigger", "--action=change",
                 "--subsystem-match=usb"],
                capture_output=True, text=True, timeout=10,
            )
            subprocess.run(
                ["udevadm", "settle", "--timeout=10"],
                capture_output=True, text=True, timeout=15,
            )
        except Exception as exc:  # noqa: BLE001 -- best effort
            logger.warning(f"udevadm trigger/settle failed: {exc}")

        # Start ModemManager
        start_result = subprocess.run(
            ["systemctl", "start", "ModemManager"],
            capture_output=True,
            text=True
        )

        if start_result.returncode == 0:
            logger.info("ModemManager started successfully")

            # We intentionally do NOT sleep here.  The next step in main()
            # is wait_for_modemmanager_dbus(), which polls the actual
            # ObjectManager interface -- that's the only "ready" signal
            # that matters to us.  The old code added a 3s blanket sleep
            # plus a 1s-per-attempt is-active loop plus a 2s post-confirm
            # sleep before returning to that D-Bus wait, which was 5-8s
            # of pure paranoia on top of the wait it then performed
            # anyway.  Cold-boot impact: ~5s saved.
            return True
        else:
            logger.error(
                f"Failed to start ModemManager: {start_result.stderr}")
            return False

    except Exception as e:
        logger.error(f"Error restarting ModemManager: {e}")
        return False

async def wait_for_modemmanager_dbus():
    """Wait for ModemManager to be available and responsive on D-Bus.

    Tight, monotonic-deadline poll of the ObjectManager interface.
    Back-off progressively starting from 100ms, capped at 1s, so the
    common boot-time case (MM responsive on the first probe once we've
    already started it) returns immediately rather than waiting a full
    poll interval.  Total wall-time upper bound is ~30s, but typical
    happy-path time
    drops from 2-4s to well under 500ms.
    """
    import time

    overall_deadline = time.monotonic() + 30.0
    delay = 0.1
    attempt = 0
    bus = None

    logger.info("Waiting for ModemManager D-Bus interface...")
    while time.monotonic() < overall_deadline:
        attempt += 1
        try:
            if bus:
                bus.disconnect()
            bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
            await bus.introspect(
                "org.freedesktop.ModemManager1",
                "/org/freedesktop/ModemManager1")
            msg = Message(
                destination="org.freedesktop.ModemManager1",
                path="/org/freedesktop/ModemManager1",
                interface="org.freedesktop.DBus.ObjectManager",
                member="GetManagedObjects",
            )
            await asyncio.wait_for(bus.call(msg), timeout=5.0)
            logger.info(
                "ModemManager is fully available and responsive on D-Bus")
            return bus
        except Exception as e:  # noqa: BLE001 -- intentional broad catch
            logger.debug(
                f"MM D-Bus not ready (attempt {attempt}): {e}")
        if bus:
            bus.disconnect()
            bus = None
        await asyncio.sleep(delay)
        delay = min(delay * 2, 1.0)

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
