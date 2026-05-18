# Copyright (C) VyOS Inc.
# SPDX-License-Identifier: LGPL-2.1-or-later
"""
Board logic shared across all igOS hardware images.

The pin map (:mod:`vyos.hardware.pinmap`) is NOT shipped by vyos-1x. It is
overlaid onto the image at build time by vyos-build, per hardware flavor.
This file therefore contains no board-specific data — only the semantic
helpers (modem reset, SIM select, serial protocol) that are common to every
SKU. If a particular SKU needs different sequencing, override here behind a
``VARIANT`` check or move the helper into ``pinmap.py``.

If ``vyos.hardware.pinmap`` is missing (e.g. on a generic cloud image that
never installs a hardware overlay), importing this module still succeeds —
``BOARD`` falls back to a stub that raises a clear error on first use.
"""

from typing import Optional

from vyos.hardware.base import Board


# -----------------------------------------------------------------------------
# THVD4431 transceiver protocol truth table
# -----------------------------------------------------------------------------
_PROTOCOLS = {
    "isolate": {"M2": 0, "M1": 0, "M0": 0, "SHUT": 0},
    "rs232":   {"M2": 0, "M1": 0, "M0": 1, "SHUT": 1},
    "rs485h":  {"M2": 0, "M1": 1, "M0": 0, "SHUT": 1},
    "rs485f":  {"M2": 0, "M1": 1, "M0": 1, "SHUT": 1},
    "rs422":   {"M2": 0, "M1": 1, "M0": 1, "SHUT": 1},
}

_SERIAL_PORTS = ("UARTC0", "UARTC2", "UARTC4", "UARTC5")


class IgosBoard(Board):
    """
    Board implementation parameterised solely by the overlaid ``pinmap``
    module. Pin numbers and the ``VARIANT`` string come from there; all
    operations below are board-agnostic.
    """
    PINS: dict = {}
    NAME: str = "igos_unknown"

    # -------- semantic helpers --------
    def modem_reset(self) -> None:
        self.pulse("CELL_UNCOND_RESET", ms=200, asserted=1)

    def modem_power(self, on: bool) -> None:
        # CELL_SHUTDOWN_N is active-low; physical 1 = run.
        self.set_pin("CELL_SHUTDOWN_N", 1 if on else 0)

    def sim_select(self, slot: int) -> None:
        if slot not in (1, 2):
            raise ValueError(f"sim_select: slot must be 1 or 2, got {slot}")
        # SIM_SELECT1N_2 low → SIM1, high → SIM2
        self.set_pin("SIM_SELECT1N_2", 0 if slot == 1 else 1)

    def serial_protocol(self, port: str, proto: str,
                        term: Optional[bool] = None,
                        slr: Optional[bool] = None) -> None:
        port = port.upper()
        proto = proto.lower()
        if port not in _SERIAL_PORTS:
            raise ValueError(
                f"serial_protocol: unknown port {port!r}, "
                f"expected one of {_SERIAL_PORTS}"
            )
        if proto not in _PROTOCOLS:
            raise ValueError(
                f"serial_protocol: unknown protocol {proto!r}, "
                f"expected one of {list(_PROTOCOLS)}"
            )
        spec = _PROTOCOLS[proto]

        # Defaults: SLR=on (fast), TERM=off
        slr_v = 1 if (slr if slr is not None else True) else 0
        term_v = 1 if (term if term is not None else False) else 0
        if proto == "rs232":
            term_v = 0
        elif proto in ("rs485h", "rs485f", "rs422"):
            slr_v = 1

        targets = {
            f"{port}_MODE2":   spec["M2"],
            f"{port}_MODE1":   spec["M1"],
            f"{port}_MODE0":   spec["M0"],
            f"{port}_TERM_TX": term_v,
            f"{port}_TERM_RX": term_v,
            f"{port}_SLR":     slr_v,
            f"{port}_SHUT_N":  spec["SHUT"],
        }
        for name, val in targets.items():
            self.set_pin(name, val)


class _NoPinmapBoard(Board):
    """Stub used when no pinmap overlay is present on the image."""
    NAME = "igos_no_pinmap"
    PINS: dict = {}

    @staticmethod
    def _fail():
        raise RuntimeError(
            "vyos.hardware: no pinmap overlay is installed on this image. "
            "Hardware control is only available on images built with an "
            "igOS hardware flavor (see vyos-build/data/build-flavors/igos-*)."
        )

    def set_pin(self, name, value):              self._fail()
    def get_pin(self, name):                     self._fail()
    def pulse(self, name, ms=200, asserted=1):   self._fail()
    def apply_defaults(self, names=None):        return None
    def modem_reset(self):                       self._fail()
    def modem_power(self, on):                   self._fail()
    def sim_select(self, slot):                  self._fail()
    def serial_protocol(self, port, proto, term=None, slr=None):
        self._fail()


def _build_board() -> Board:
    try:
        from vyos.hardware import pinmap  # type: ignore
    except ImportError:
        return _NoPinmapBoard()

    variant = getattr(pinmap, "VARIANT", "unknown")
    pins = getattr(pinmap, "PINS", None)
    if not pins:
        return _NoPinmapBoard()

    board = IgosBoard()
    board.PINS = pins
    board.NAME = f"igos_{variant}"
    return board


BOARD: Board = _build_board()
