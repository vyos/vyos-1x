#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

from sys import exit
from pathlib import Path
from typing import Optional

from vyos.config import Config
from vyos.base import Warning
from vyos.template import render
from vyos.utils.kernel import load_module
from vyos.utils.process import call, cmd
from vyos import ConfigError
from vyos import airbag

airbag.enable()

watchdog_config_dir = Path('/run/systemd/system.conf.d')
watchdog_config_file = watchdog_config_dir / 'watchdog.conf'
modules_load_directory = Path('/run/modules-load.d')
modules_load_file = modules_load_directory / 'watchdog.conf'
WATCHDOG_DEV = Path('/dev/watchdog0')
WATCHDOG_SYSFS = Path('/sys/class/watchdog/watchdog0')


def _get_watchdog_driver_module_name() -> Optional[str]:
    """Return the kernel module name backing watchdog0, if discoverable."""

    module_link = WATCHDOG_SYSFS / 'device/driver/module'
    if not module_link.exists():
        return None

    try:
        resolved = module_link.resolve()
    except OSError:
        return None

    # Expected to resolve to /sys/module/<module_name>
    module_name = resolved.name.strip()
    return module_name or None


def _read_sysfs_int(path: Path) -> Optional[int]:
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None


def _get_watchdog_timeout_limits() -> tuple[int, int]:
    """Return (min_timeout, max_timeout) from sysfs if available.

    If sysfs is unavailable (device not present/loaded yet) or zero, fall back to a
    conservative common kernel max of 65535 seconds.
    """

    if not WATCHDOG_SYSFS.exists():
        return 1, 65535

    min_timeout = _read_sysfs_int(WATCHDOG_SYSFS / 'min_timeout')
    max_timeout = _read_sysfs_int(WATCHDOG_SYSFS / 'max_timeout')

    # Some drivers may not expose min/max. Fall back to sane defaults.
    min_timeout = min_timeout if min_timeout and min_timeout > 0 else 1
    max_timeout = max_timeout if max_timeout and max_timeout > 0 else 65535

    return min_timeout, max_timeout


def _verify_watchdog_module(module: str) -> None:
    # Dry-run modprobe (-n) in quiet mode (-q) verifies availability without loading
    if load_module(module, quiet=True, dry_run=True) != 0:
        raise ConfigError(
            f"Watchdog driver module '{module}' was not found or cannot be loaded"
        )

    # Ensure the module looks like a watchdog driver and not an arbitrary module.
    # Use modinfo filename location as the heuristic.
    filename = cmd(['modinfo', '-F', 'filename', module], raising=ConfigError)
    filename_l = filename.strip().lower()

    # Accept modules located under drivers/watchdog, plus explicit exception for
    # ipmi_watchdog which lives in drivers/char/ipmi.
    is_watchdog_driver = '/watchdog/' in filename_l or filename_l.endswith(
        '/ipmi_watchdog.ko'
    )

    if not is_watchdog_driver:
        raise ConfigError(
            f"Kernel module '{module}' does not look like a watchdog driver module (modinfo filename: {filename.strip()})"
        )


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['system', 'watchdog']

    if not conf.exists(base):
        return None

    watchdog = conf.get_config_dict(
        base, key_mangling=('-', '_'), get_first_key=True, with_recursive_defaults=True
    )

    return watchdog


def verify(watchdog):
    if watchdog is None:
        return None

    module = watchdog.get('module')
    device_exists = WATCHDOG_DEV.exists()

    # Require a usable watchdog: either device already present or a module provided
    if not module and not device_exists:
        raise ConfigError(
            "No watchdog device found at /dev/watchdog0 and no module configured. "
            "Use 'system watchdog module <name>' to load the required watchdog driver for your system."
        )

    # If a module is provided, ensure it exists and is a watchdog module
    if module:
        _verify_watchdog_module(module)

    # Validate runtime watchdog timeout against kernel driver limits if available.
    # Shutdown/Reboot watchdog settings are systemd-level timers and are not
    # constrained by the watchdog device driver's min/max.
    if 'timeout' in watchdog:
        try:
            value = int(watchdog['timeout'])
        except (TypeError, ValueError):
            raise ConfigError("Invalid value for 'timeout'")

        min_timeout, max_timeout = _get_watchdog_timeout_limits()
        if value < min_timeout:
            raise ConfigError(
                f"'timeout' must be >= {min_timeout} seconds (driver minimum)"
            )
        if value > max_timeout:
            raise ConfigError(
                f"'timeout' must be <= {max_timeout} seconds (driver maximum)"
            )

    return None


def generate(watchdog):
    # If watchdog node removed entirely, clean up everything
    if watchdog is None:
        watchdog_config_file.unlink(missing_ok=True)
        modules_load_file.unlink(missing_ok=True)
        return None

    # Persist kernel module autoload on boot if specified (even if not enabled)
    module = watchdog.get('module')
    if module:
        try:
            modules_load_directory.mkdir(parents=True, exist_ok=True)
            modules_load_file.write_text(f"{module}\n")
        except OSError as e:
            Warning(f"Failed writing modules-load configuration: {e}")
    else:
        # If module option removed, drop persisted autoload file
        modules_load_file.unlink(missing_ok=True)

    # Try to load kernel module if specified and /dev/watchdog0 is missing
    if not WATCHDOG_DEV.exists():
        if module:
            # Try to load the module using vyos call wrapper for logging/airbag integration
            try:
                rc = load_module(module, quiet=True, dry_run=False)
            except OSError as e:
                Warning(
                    f"Could not execute modprobe for watchdog module '{module}': {e}"
                )
            else:
                if rc != 0:
                    Warning(
                        f"Could not load watchdog module '{module}' (modprobe exit code {rc})"
                    )
    # Re-check for device
    if not WATCHDOG_DEV.exists():
        Warning("/dev/watchdog0 not found. Systemd watchdog will not be enabled.")
        watchdog_config_file.unlink(missing_ok=True)
        return None

    # If a module was configured explicitly, warn if the actual driver module
    # bound to watchdog0 differs from what the user configured.
    if module and WATCHDOG_SYSFS.exists():
        actual_module = _get_watchdog_driver_module_name()
        if actual_module and actual_module != module:
            Warning(
                f"Configured watchdog driver module '{module}' does not match watchdog0 driver module '{actual_module}'"
            )

    # Ensure the directory exists
    watchdog_config_dir.mkdir(parents=True, exist_ok=True)

    # Pass through configured time values directly as seconds
    render(str(watchdog_config_file), 'system/watchdog.conf.j2', watchdog)

    return None


def apply(watchdog):
    # Reload systemd daemon to apply/unload the watchdog configuration
    # The watchdog settings take immediate effect after systemd is reloaded
    call('systemctl daemon-reload')

    return None


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
