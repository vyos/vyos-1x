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

"""
WWAN Interface Utilities

This module provides utility functions for WWAN interface management,
including hardware reset capabilities and other common operations.
"""

import asyncio
import logging
import time
from pathlib import Path

from vyos.hardware import api as hw_api
from vyos.utils.wwan import interfaces_wwan_diag as wwan_diag

logger = logging.getLogger(__name__)


def _count_hardware_reset(interface_number: int) -> None:
    """Record a successful modem hardware reset in the boot-scoped counters."""
    try:
        wwan_diag.increment(f'hardware_reset_count_{interface_number}')
    except Exception:
        pass


async def _bring_interface_down_safe(interface_name: str) -> bool:
    """
    Safely bring down network interface before USB reset operations.

    This prevents network stack corruption when USB devices disappear abruptly.
    Critical for VM stability during USB reset operations.

    Args:
        interface_name: Interface name (e.g., "wwan0")

    Returns:
        bool: True if interface was brought down or didn't exist, False on error
    """
    try:
        # Check if interface exists first
        check_cmd = ["ip", "link", "show", interface_name]
        result = await asyncio.create_subprocess_exec(
            *check_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()

        if result.returncode != 0:
            # Interface doesn't exist, that's fine
            logger.debug(f"Interface {interface_name} doesn't exist, nothing to bring down")
            return True

        # Check if interface is UP
        interface_info = stdout.decode()
        if "state UP" not in interface_info and ",UP," not in interface_info:
            logger.debug(f"Interface {interface_name} already down")
            return True

        # Bring interface down
        logger.info(f"Bringing interface {interface_name} down before USB reset")
        down_cmd = ["ip", "link", "set", interface_name, "down"]
        result = await asyncio.create_subprocess_exec(
            *down_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()

        if result.returncode == 0:
            logger.info(f"Interface {interface_name} brought down successfully")
            return True
        else:
            logger.warning(f"Failed to bring interface {interface_name} down: {stderr.decode().strip()}")
            return False

    except Exception as e:
        logger.error(f"Error bringing interface {interface_name} down: {e}")
        return False


def _is_running_in_vm() -> bool:
    """Detect if we're running in a virtual machine"""
    try:
        # Check common VM indicators
        vm_indicators = [
            '/sys/class/dmi/id/product_name',
            '/sys/class/dmi/id/sys_vendor',
            '/sys/class/dmi/id/board_vendor'
        ]

        for path in vm_indicators:
            try:
                with open(path, 'r') as f:
                    content = f.read().lower()
                    if any(vm in content for vm in ['qemu', 'kvm', 'virtualbox', 'vmware', 'xen', 'hyper-v']):
                        return True
            except (OSError, IOError):
                continue

        # Check for VM-specific devices
        try:
            with open('/proc/cpuinfo', 'r') as f:
                if 'hypervisor' in f.read().lower():
                    return True
        except (OSError, IOError):
            pass

        return False
    except Exception:
        return False

async def modem_reset(interface_number: int) -> bool:
    """
    Perform hardware reset of the modem for the specified interface.

    This function attempts various reset methods depending on the hardware
    and system configuration available.

    VM CRASH PROTECTION: Automatically detects VMs and uses safer reset methods.

    Args:
        interface_number: The interface number (e.g., 0 for wwan0)

    Returns:
        bool: True if reset was attempted, False if no reset method available
    """
    logger.info(f"Attempting hardware reset for interface {interface_number}")

    # VM CRASH PROTECTION: Disable hardware resets in VMs
    if _is_running_in_vm():
        logger.warning(f"VM detected - hardware reset disabled for safety (interface {interface_number})")
        logger.info("Using nuclear reset (ModemManager restart) instead of hardware reset")
        return await modem_reset_nuclear(interface_number)

    try:
        # Method 1: Try ModemManager reset command
        if await _try_modemmanager_reset(interface_number):
            logger.info(f"ModemManager reset successful for interface {interface_number}")
            _count_hardware_reset(interface_number)
            return True

        # Method 2: Try board hardware API reset using the modem naming
        # convention (modem0 -> wwan0, modem1 -> wwan1, etc.). This is the
        # unconditional hardware reset path that the board implementation
        # owns, so WWAN does not need to guess at GPIO details itself.
        if await _try_board_modem_reset(interface_number):
            logger.info(f"Board hardware reset successful for interface {interface_number}")
            _count_hardware_reset(interface_number)
            return True

        # Method 3: Nuclear option - restart ModemManager
        logger.warning(f"All standard reset methods failed for interface {interface_number}, trying nuclear option...")
        if await modem_reset_nuclear(interface_number):
            logger.info(f"Nuclear reset (ModemManager restart) successful for interface {interface_number}")
            return True

        logger.error(f"All reset methods failed for interface {interface_number}")
        return False

    except Exception as e:
        logger.error(f"Error during modem reset for interface {interface_number}: {e}")
        return False


async def _try_modemmanager_reset(interface_number: int) -> bool:
    """Try to reset modem using ModemManager"""
    try:
        # Find modem by PhysDevUID

        # Use mmcli to find and reset the modem
        find_cmd = ["mmcli", "-L"]
        result = await asyncio.create_subprocess_exec(
            *find_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()

        if result.returncode != 0:
            logger.debug("mmcli not available or failed")
            return False

        # Parse mmcli output to find modem with matching PhysDevUID
        modem_id = None
        for line in stdout.decode().split('\n'):
            if '/Modem/' in line:
                # Extract modem ID from line like "/org/freedesktop/ModemManager1/Modem/0"
                parts = line.split('/')
                if len(parts) > 0:
                    try:
                        potential_id = parts[-1].split()[0]
                        if potential_id.isdigit():
                            modem_id = potential_id
                            break
                    except (IndexError, ValueError):
                        continue

        if modem_id is None:
            logger.debug("No modem found in ModemManager")
            return False

        # Step 1: Disable the modem to ensure clean bearer teardown
        logger.info(f"Disabling modem {modem_id} before reset")
        disable_cmd = ["mmcli", "-m", modem_id, "--disable"]
        result = await asyncio.create_subprocess_exec(
            *disable_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()

        if result.returncode != 0:
            logger.warning(f"Modem disable failed (continuing with reset): {stderr.decode().strip()}")
        else:
            logger.info(f"Modem {modem_id} disabled successfully")
            # Wait a moment for clean shutdown
            await asyncio.sleep(2)

        # Step 2: Reset the modem
        logger.info(f"Resetting modem {modem_id}")
        reset_cmd = ["mmcli", "-m", modem_id, "--reset"]
        result = await asyncio.create_subprocess_exec(
            *reset_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()

        if result.returncode == 0:
            logger.info(f"Modem {modem_id} reset successfully")
        else:
            logger.error(f"Modem reset failed: {stderr.decode().strip()}")

        if result.returncode != 0:
            return False

        return await _wait_for_modemmanager_reenumeration(interface_number)

    except Exception as e:
        logger.debug(f"ModemManager reset failed: {e}")
        return False


async def _try_board_modem_reset(interface_number: int) -> bool:
    """Try to reset the modem through the board hardware API.

    The board implementation owns the actual GPIO/pulse details. WWAN only
    maps its interface number to the board modem naming convention
    (modem0 -> wwan0, modem1 -> wwan1, ...).
    """
    modem_name = f"modem{interface_number}"

    try:
        logger.info(f"Performing board hardware reset for {modem_name}")
        await asyncio.to_thread(hw_api.modem_reset, modem=modem_name)
    except Exception as e:
        logger.debug(f"Board hardware reset failed for {modem_name}: {e}")
        return False

    # A reset pulse alone is not enough — wait until the modem is back in a
    # state that ModemManager can see again.
    if await _wait_for_modemmanager_reenumeration(interface_number):
        return True

    logger.warning(f"Board hardware reset completed but modem did not re-enumerate in ModemManager for interface {interface_number}")
    return False


async def _try_usb_reset(interface_number: int) -> bool:
    """Try to reset modem via USB device reset"""
    try:
        # Look for USB device paths that might correspond to the modem
        usb_devices = Path("/sys/bus/usb/devices")
        if not usb_devices.exists():
            return False

        # Common patterns for modem device paths
        device_patterns = [
            f"ttyUSB{interface_number}",
            f"cdc-wdm{interface_number}",
            f"wwan{interface_number}"
        ]

        # Find USB device associated with this interface
        for device_dir in usb_devices.iterdir():
            if device_dir.is_dir():
                # Check if this USB device has our interface
                for pattern in device_patterns:
                    if (device_dir / "**" / pattern).exists():
                        # Found matching device, try to reset it
                        reset_file = device_dir / "authorized"
                        if reset_file.exists():
                            # CRITICAL: Bring down network interface before USB reset
                            # This prevents network stack corruption and VM crashes
                            interface_name = f"wwan{interface_number}"
                            await _bring_interface_down_safe(interface_name)

                            # Disable and re-enable device
                            try:
                                logger.info(f"Performing USB reset on device {device_dir.name}")

                                # Deauthorize device (this makes USB device disappear)
                                reset_file.write_text("0")
                                await asyncio.sleep(2)

                                # Re-authorize device (this triggers USB re-enumeration)
                                reset_file.write_text("1")
                                await asyncio.sleep(3)

                                logger.info(f"USB reset completed for device {device_dir.name}")
                                return True
                            except PermissionError:
                                logger.debug("Permission denied for USB reset")
                                return False

        return False

    except Exception as e:
        logger.debug(f"USB reset failed: {e}")
        return False


async def _try_gpio_reset(interface_number: int) -> bool:
    """Try to reset modem via GPIO control"""
    try:
        # Look for GPIO reset pins in common locations
        gpio_paths = [
            f"/sys/class/gpio/modem{interface_number}_reset",
            f"/sys/class/gpio/wwan{interface_number}_reset",
            "/sys/class/gpio/modem_reset",
            "/sys/class/gpio/cellular_reset"
        ]

        for gpio_path in gpio_paths:
            gpio_dir = Path(gpio_path)
            if gpio_dir.exists():
                value_file = gpio_dir / "value"
                if value_file.exists():
                    try:
                        # CRITICAL: Bring down interface before GPIO reset
                        interface_name = f"wwan{interface_number}"
                        await _bring_interface_down_safe(interface_name)

                        logger.info(f"Performing GPIO reset using {gpio_path}")

                        # Pull reset low, wait, then high
                        value_file.write_text("0")
                        await asyncio.sleep(1)
                        value_file.write_text("1")
                        await asyncio.sleep(2)

                        logger.info(f"GPIO reset completed using {gpio_path}")
                        return True
                    except PermissionError:
                        logger.debug(f"Permission denied for GPIO reset at {gpio_path}")

        return False

    except Exception as e:
        logger.debug(f"GPIO reset failed: {e}")
        return False


async def _try_usb_power_cycle(interface_number: int) -> bool:
    """Try to power cycle modem via USB hub control"""
    try:
        # Look for uhubctl or other USB hub control utilities
        uhubctl_cmd = ["uhubctl", "--action", "cycle", "--delay", "2"]

        # Try to find uhubctl
        which_result = await asyncio.create_subprocess_exec(
            "which", "uhubctl",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await which_result.communicate()

        if which_result.returncode != 0:
            logger.debug("uhubctl not available")
            return False

        # CRITICAL: Bring down interface before USB power cycle
        interface_name = f"wwan{interface_number}"
        await _bring_interface_down_safe(interface_name)

        logger.info(f"Performing USB power cycle for interface {interface_number}")

        # Execute power cycle
        result = await asyncio.create_subprocess_exec(
            *uhubctl_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await result.communicate()

        return result.returncode == 0

    except Exception as e:
        logger.debug(f"USB power cycle failed: {e}")
        return False


def get_interface_device_path(interface_number: int) -> str:
    """
    Get the device path for a WWAN interface.

    Args:
        interface_number: The interface number

    Returns:
        str: Device path (e.g., /dev/ttyUSB0) or empty string if not found
    """
    common_patterns = [
        f"/dev/ttyUSB{interface_number}",
        f"/dev/cdc-wdm{interface_number}",
        f"/dev/wwan{interface_number}",
        f"/dev/ttyACM{interface_number}"
    ]

    for pattern in common_patterns:
        if Path(pattern).exists():
            return pattern

    return ""


def get_interface_sysfs_path(interface_number: int) -> str:
    """
    Get the sysfs path for a WWAN interface.

    Args:
        interface_number: The interface number

    Returns:
        str: Sysfs path or empty string if not found
    """
    common_patterns = [
        f"/sys/class/net/wwan{interface_number}",
        f"/sys/class/wwan/wwan{interface_number}"
    ]

    for pattern in common_patterns:
        if Path(pattern).exists():
            return pattern

    return ""


async def wait_for_interface_ready(interface_number: int, timeout: int = 30) -> bool:
    """
    Wait for interface to become ready after reset.

    Args:
        interface_number: The interface number
        timeout: Maximum time to wait in seconds

    Returns:
        bool: True if interface became ready, False if timeout
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        # Check if device path exists
        device_path = get_interface_device_path(interface_number)
        if device_path:
            # Additional check: try to access the device
            try:
                path_obj = Path(device_path)
                if path_obj.exists() and path_obj.is_char_device():
                    logger.info(f"Interface {interface_number} ready at {device_path}")
                    return True
            except Exception:
                pass

        await asyncio.sleep(1)

    logger.warning(f"Interface {interface_number} not ready after {timeout} seconds")
    return False


async def _wait_for_modemmanager_reenumeration(interface_number: int, timeout: int = 60) -> bool:
    """Wait until ModemManager sees the modem again after a hardware reset."""
    deadline = time.time() + timeout
    modem_name = f"modem{interface_number}"

    while time.time() < deadline:
        # Check that the underlying device node has come back first.
        if not await wait_for_interface_ready(interface_number, timeout=1):
            await asyncio.sleep(1)
            continue

        # Then verify ModemManager can enumerate at least one modem again.
        try:
            result = await asyncio.create_subprocess_exec(
                "mmcli", "-L",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            if result.returncode == 0 and "/Modem/" in stdout.decode():
                logger.info(f"ModemManager re-detected modem after reset for {modem_name}")
                return True
        except Exception as e:
            logger.debug(f"ModemManager re-enumeration check failed for {modem_name}: {e}")

        await asyncio.sleep(1)

    return False


# Synchronous wrapper for callers outside an asyncio event loop
def modem_reset_sync(interface_number: int) -> bool:
    """
    Synchronous wrapper around :func:`modem_reset` for callers that are
    not running inside an asyncio event loop.

    Args:
        interface_number: The interface number

    Returns:
        bool: True if reset was attempted
    """
    try:
        return asyncio.run(modem_reset(interface_number))
    except Exception as e:
        logger.error(f"Synchronous modem reset failed: {e}")
        return False


async def modem_reset_nuclear(interface_number: int) -> bool:
    """
    Nuclear option: Restart ModemManager entirely to recover from QMI issues.

    This is a last resort when normal modem reset fails due to corrupted
    QMI interface state. It will:
    1. Stop ModemManager service
    2. Wait for cleanup
    3. Restart ModemManager service
    4. Wait for modem re-detection

    Args:
        interface_number: The interface number (e.g., 0 for wwan0)

    Returns:
        bool: True if ModemManager restart succeeded, False otherwise
    """
    logger.warning(f"Attempting nuclear reset (ModemManager restart) for interface {interface_number}")

    try:
        # Step 1: Stop ModemManager
        logger.info("Stopping ModemManager service...")
        stop_cmd = ["sudo", "systemctl", "stop", "ModemManager"]
        result = await asyncio.create_subprocess_exec(
            *stop_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await result.communicate()

        if result.returncode != 0:
            logger.error("Failed to stop ModemManager")
            return False

        # Step 2: Wait for cleanup
        logger.info("Waiting for ModemManager cleanup...")
        await asyncio.sleep(5)

        # Step 3: Start ModemManager
        logger.info("Starting ModemManager service...")
        start_cmd = ["sudo", "systemctl", "start", "ModemManager"]
        result = await asyncio.create_subprocess_exec(
            *start_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await result.communicate()

        if result.returncode != 0:
            logger.error("Failed to start ModemManager")
            return False

        # Step 4: Wait for modem re-detection
        logger.info("Waiting for modem re-detection...")
        await asyncio.sleep(10)

        if await _wait_for_modemmanager_reenumeration(interface_number):
            logger.info(f"Nuclear reset completed for interface {interface_number}")
            try:
                wwan_diag.increment('modem_nuclear_reset_count')
            except Exception:
                pass
            return True

        logger.warning(f"Modem did not re-enumerate after ModemManager restart for interface {interface_number}")
        return False

    except Exception as e:
        logger.error(f"Nuclear reset failed for interface {interface_number}: {e}")
        return False
