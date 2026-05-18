# Copyright (C) VyOS Inc.
# SPDX-License-Identifier: LGPL-2.1-or-later
"""
Stable, board-agnostic facade. Import this from conf-mode scripts, the WWAN
FSM, serial helpers, etc.
"""

from typing import Optional

from vyos.hardware.board import BOARD as _b


def board_name() -> str:
    return _b.NAME


# --- low-level pin ops (use sparingly; prefer semantic helpers below) -------
def set_pin(name: str, value: int) -> None:
    _b.set_pin(name, value)


def get_pin(name: str) -> int:
    return _b.get_pin(name)


def pulse(name: str, ms: int = 200, asserted: int = 1) -> None:
    _b.pulse(name, ms, asserted)


def apply_defaults(*names: str) -> None:
    _b.apply_defaults(names or None)


# --- semantic helpers (board-agnostic verbs) --------------------------------
def modem_reset() -> None:
    _b.modem_reset()


def modem_power(on: bool) -> None:
    _b.modem_power(on)


def sim_select(slot: int) -> None:
    _b.sim_select(slot)


def serial_protocol(port: str, proto: str,
                    term: Optional[bool] = None,
                    slr: Optional[bool] = None) -> None:
    """
    Configure a serial transceiver for one of: ``isolate``, ``rs232``,
    ``rs485h``, ``rs485f``, ``rs422``.
    """
    _b.serial_protocol(port, proto, term=term, slr=slr)
