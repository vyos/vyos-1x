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

"""Boot-scoped diagnostic counters for the WWAN manager.

These counters answer "how many times since power on …?" questions that are
useful for field diagnosis:

* ``service_start_count``        — WWAN manager starts (>1 ⇒ crash/restart)
* ``modemmanager_restart_count`` — ModemManager crashes the manager recovered
* ``modem_nuclear_reset_count``  — deliberate MM restarts used as a recovery
                                   tool by an FSM
* ``hardware_reset_count_<N>``   — hardware resets of the modem on interface N

The backing store lives in ``/run/wwan`` (tmpfs), so the counters survive
service crashes/restarts but reset cleanly on a power cycle — exactly the
"since power on" semantics we want, with no cleanup logic required.

All increments happen inside the single-threaded asyncio event loop of the
WWAN manager, so the read-modify-write below is race-free within the process.
op-mode readers consume these values via the FSM status object over D-Bus and
never touch the file directly.
"""

import json
import os

RUN_DIR = '/run/wwan'
COUNTER_FILE = os.path.join(RUN_DIR, 'diag-counters.json')


def _load() -> dict:
    try:
        with open(COUNTER_FILE, 'r') as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        return {}


def _save(data: dict) -> None:
    try:
        os.makedirs(RUN_DIR, exist_ok=True)
        tmp_path = COUNTER_FILE + '.tmp'
        with open(tmp_path, 'w') as f:
            json.dump(data, f)
        os.replace(tmp_path, COUNTER_FILE)
    except Exception:
        # Diagnostics are best-effort; never let a counter write break the
        # control path.
        pass


def increment(key: str, amount: int = 1) -> int:
    """Increment ``key`` by ``amount`` and return the new value."""
    data = _load()
    try:
        current = int(data.get(key, 0))
    except (TypeError, ValueError):
        current = 0
    new_value = current + amount
    data[key] = new_value
    _save(data)
    return new_value


def get(key: str, default: int = 0) -> int:
    """Return the current value of ``key`` (``default`` if unset)."""
    data = _load()
    try:
        return int(data.get(key, default))
    except (TypeError, ValueError):
        return default


def get_all() -> dict:
    """Return a copy of all stored counters."""
    return _load()
