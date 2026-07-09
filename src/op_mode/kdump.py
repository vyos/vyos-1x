#!/usr/bin/env python3
#
# Copyright (C) VyOS Inc.
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

import os
import sys
from datetime import datetime

import vyos.opmode
from tabulate import tabulate
from vyos.configquery import ConfigTreeQuery
from vyos.defaults import systemd_services
from vyos.utils.convert import bytes_to_human
from vyos.utils.boot import get_kernel_boot_args
from vyos.utils.file import read_file
from vyos.utils.process import is_systemd_service_active

# Kernel interface files exposing crash kernel state at runtime
KEXEC_CRASH_LOADED = '/sys/kernel/kexec_crash_loaded'
KEXEC_CRASH_SIZE = '/sys/kernel/kexec_crash_size'

# systemd unit managed by kdump-tools that loads the capture kernel
# and handles vmcore saving after a panic
KDUMP_SERVICE = systemd_services['kdump']

# Base path to boot files related to kdump
KDUMP_LIB_PATH = '/var/lib/kdump'

DEFAULT_TIME_FORMAT = '%Y-%m-%d %H:%M:%S'

conf = ConfigTreeQuery()
base = ['system', 'option', 'kdump']


def _get_config() -> dict:
    """Return the effective kdump config dict, or {} when unconfigured"""

    if not conf.exists(base):
        return {}

    return conf.get_config_dict(
        base, key_mangling=('-', '_'), get_first_key=True, with_recursive_defaults=True
    )


def _crash_kernel_loaded() -> bool:
    """Return True when a capture kernel is currently loaded via kexec"""
    return read_file(KEXEC_CRASH_LOADED, defaultonfailure='0') == '1'


def _crash_kernel_size() -> int:
    """Return the number of bytes reserved for the capture kernel"""

    raw = read_file(KEXEC_CRASH_SIZE, defaultonfailure='0')
    return int(raw) if raw.isdigit() else -1


def _cmdline_value() -> str:
    """Return the crashkernel= value from the current kernel command line"""
    return get_kernel_boot_args('crashkernel') or ''


def _read_link(symlink_path: str) -> str | None:
    """Read the destination of the symbolic link"""
    try:
        destination_path = os.readlink(symlink_path)
    except OSError:
        return None

    # os.readlink() may return a relative target.
    # Interpret it relative to the link directory
    if not os.path.isabs(destination_path):
        destination_path = os.path.join(os.path.dirname(symlink_path), destination_path)

    destination_path = os.path.realpath(destination_path)
    return destination_path if os.path.isfile(destination_path) else None


def _list_dumps(dump_path: str) -> list[dict]:
    """Return a sorted list of vmcore entries found under *dump_path*.

    kdump-tools stores each capture in its own timestamped sub-directory
    using the layout:

        <dump_path>/<YYYYMMDDHHMM>/dump.<YYYYMMDDHHMM>
        <dump_path>/<YYYYMMDDHHMM>/dmesg.<YYYYMMDDHHMM>  (optional)

    The reported size is the combined size of both files when the dmesg
    companion file is present.
    """

    entries = []
    if not os.path.isdir(dump_path):
        return entries

    # Each sub-directory name is the timestamp of the crash event
    for name in sorted(os.listdir(dump_path)):
        sub = os.path.join(dump_path, name)
        if not os.path.isdir(sub):
            continue

        dump = os.path.join(sub, f'dump.{name}')
        dmesg = os.path.join(sub, f'dmesg.{name}')

        if os.path.isfile(dump):
            stat_dump = os.stat(dump)
            stat_dmesg = os.stat(dmesg) if os.path.isfile(dmesg) else None
            full_size = stat_dump.st_size + (stat_dmesg.st_size if stat_dmesg else 0)

            entry = {
                'directory': sub,
                'size_bytes': full_size,
                'size_human': bytes_to_human(full_size),
                'modify_time': stat_dump.st_mtime,
            }

            entries.append(entry)

    return entries


def _get_raw_status() -> dict:
    """Collect all kdump runtime and configuration data into a single dict"""

    cfg = _get_config()

    dump_path = cfg.get('dump_path')
    dumps = _list_dumps(dump_path) if dump_path else []
    last_dump = dumps[-1] if dumps else None

    return {
        'configured': bool(cfg),
        'service_active': is_systemd_service_active(KDUMP_SERVICE),
        'crash_kernel_loaded': _crash_kernel_loaded(),
        'crash_kernel_size': _crash_kernel_size(),
        'cmdline_value': _cmdline_value(),
        'vmlinuz_path': _read_link(f'{KDUMP_LIB_PATH}/vmlinuz'),
        'initrd_path': _read_link(f'{KDUMP_LIB_PATH}/initrd.img'),
        'memory': cfg.get('memory'),
        'dump_path': dump_path,
        'last_dump': last_dump,
    }


def _get_raw_dumps() -> list[dict]:
    cfg = _get_config()
    dump_path = cfg.get('dump_path')
    return _list_dumps(dump_path) if dump_path else []


def _verify_config():
    """Raise UnconfiguredSubsystem when kdump has not been configured"""

    cfg = _get_config()
    if not cfg:
        conf_command = ' '.join(['set'] + base)
        raise vyos.opmode.UnconfiguredSubsystem(
            f'kdump is not configured - use "{conf_command}" to enable it.'
        )


def _format_status(data: dict) -> str:
    """Render the kdump status dict as a human-readable plain-text table"""

    header = 'Kernel crash dump (kdump) status'

    cfg_str = 'configured' if data['configured'] else 'not configured'
    svc_str = 'active' if data['service_active'] else 'inactive'
    loaded_str = 'loaded' if data['crash_kernel_loaded'] else 'not loaded'

    rows = [
        ('Configuration', cfg_str),
        ('Systemd service', svc_str),
        ('Crash kernel', loaded_str),
    ]

    if data['crash_kernel_loaded']:
        # Show reserved memory size and the boot argument that produced it

        raw = data['crash_kernel_size']
        value = bytes_to_human(raw) if raw >= 0 else ''
        rows.append(('Reserved memory', value))

        rows.append(("Boot 'crashkernel' value", data['cmdline_value']))
    else:
        # Capture kernel is not loaded and memory reservation requires a reboot
        rows.append(('Reserved memory', 'none (reboot required to reserve memory)'))

    if data['configured']:
        rows.append(('Memory parameter', data['memory']))
        rows.append(('Directory to save dumps', data['dump_path']))

        # Display the latest date of created dump
        last_dump_date = 'none'
        if data['last_dump']:
            dt = datetime.fromtimestamp(data['last_dump']['modify_time'])
            last_dump_date = dt.strftime(DEFAULT_TIME_FORMAT)
        rows.append(('Last dump date', last_dump_date))

    # Show `initrd.img` and `vmlinuz` status which are critical
    # for a successful boot process
    rows.append(('Initial RAM disk image', data['initrd_path'] or 'none'))
    rows.append(('Linux kernel executable file', data['vmlinuz_path'] or 'none'))

    # Expand each row to a three-column tuple so tabulate can align the
    # separator colon independently of the label and value columns
    rows = [(header, ':', value) for header, value in rows]
    table = tabulate(rows, tablefmt='plain')

    return f'{header}\n\n{table}'


def _format_dumps(entries: list[dict]) -> str:
    """Render the crash dump list as a human-readable table"""

    if not entries:
        return 'No kernel crash dumps recorded'

    headers = ['DIRECTORY', 'SIZE', 'TIME']
    rows = []

    for entry in entries:
        dt = datetime.fromtimestamp(entry['modify_time'])
        row = (
            entry['directory'],
            entry['size_human'],
            dt.strftime(DEFAULT_TIME_FORMAT),
        )
        rows.append(row)

    # Append a blank separator row followed by an aggregate totals row
    total = sum(entry['size_bytes'] for entry in entries)
    rows.append(('', '', ''))
    rows.append((f'Total: {len(entries)} dump(s)', bytes_to_human(total), ''))

    return tabulate(rows, headers, tablefmt='simple')


def show_status(raw: bool):
    """Show kdump service status and configuration summary"""

    _verify_config()

    data = _get_raw_status()
    return data if raw else _format_status(data)


def show_dumps(raw: bool):
    """Show recorded kernel crash dumps"""

    _verify_config()

    data = _get_raw_dumps()
    return data if raw else _format_dumps(data)


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
