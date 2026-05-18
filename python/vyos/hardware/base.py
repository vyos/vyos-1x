# Copyright (C) VyOS Inc.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
"""
Base classes shared by all board modules under ``vyos.hardware.boards``.

A board file declares a ``PINS`` mapping of logical name → :class:`Pin` and
instantiates a single ``BOARD = MyBoard()`` at module scope. The base
:class:`Board` provides a libgpiod-backed implementation of ``set_pin``,
``get_pin``, ``pulse`` and ``apply_defaults``. Subclasses override
``semantic_*`` helpers (modem power, SIM select, serial protocol, …) as
needed.

libgpiod is imported lazily so that simply importing ``vyos.hardware`` on a
machine without ``python3-libgpiod`` (e.g. a generic cloud image whose flavor
is ``generic``) does not raise.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Dict, Iterable, Optional


@dataclass(frozen=True)
class Pin:
    """Static description of a single GPIO line on a board."""
    bank: int
    line: int
    dir: str = "out"               # "in" | "out"
    active_low: bool = False
    bias: str = "as-is"            # "pull-up" | "pull-down" | "as-is"
    default: Optional[int] = None  # initial value for outputs (0/1) or None
    group: str = ""                # free-form tag for grouping in listings


class Board:
    """
    Abstract board. Subclasses set ``NAME`` and ``PINS``.

    Concrete operations are implemented here using libgpiod v2. If a board
    needs special sequencing (e.g. assert reset then wait then release), it
    overrides the corresponding ``semantic_*`` method.
    """
    NAME: str = "abstract"
    PINS: Dict[str, Pin] = {}

    # ------------------------------------------------------------------ libgpiod
    def __init__(self) -> None:
        self._bank_paths: Dict[int, str] = {}

    @staticmethod
    def _list_chips() -> list[str]:
        return sorted(
            os.path.join("/dev", c)
            for c in os.listdir("/dev")
            if c.startswith("gpiochip")
        )

    def _resolve_bank(self, bank: int) -> str:
        if bank in self._bank_paths:
            return self._bank_paths[bank]
        chips = self._list_chips()
        if not chips:
            raise RuntimeError("vyos.hardware: no /dev/gpiochip* present")
        # Match the original Perle convention: bank 0 → chips[1], etc.
        path = chips[bank + 1] if len(chips) > bank + 1 else chips[-1]
        self._bank_paths[bank] = path
        return path

    @staticmethod
    def _gpiod():
        import gpiod  # noqa: WPS433 — lazy import
        return gpiod

    @classmethod
    def _line_settings(cls, **kw):
        gpiod = cls._gpiod()
        try:
            return gpiod.LineSettings(**kw)
        except AttributeError:
            return gpiod.line.LineSettings(**kw)  # older API

    # ------------------------------------------------------------------- basics
    def _require(self, name: str) -> Pin:
        try:
            return self.PINS[name]
        except KeyError as exc:
            raise KeyError(
                f"{self.NAME}: unknown GPIO {name!r}"
            ) from exc

    def set_pin(self, name: str, value: int) -> None:
        pin = self._require(name)
        gpiod = self._gpiod()
        v = gpiod.line.Value.ACTIVE if value else gpiod.line.Value.INACTIVE
        with gpiod.request_lines(
            self._resolve_bank(pin.bank),
            consumer=f"vyos-hw/{self.NAME}",
            config={pin.line: self._line_settings(
                direction=gpiod.line.Direction.OUTPUT,
                output_value=v,
            )},
        ):
            pass  # request → set → release leaves the line latched

    def get_pin(self, name: str) -> int:
        pin = self._require(name)
        gpiod = self._gpiod()
        with gpiod.request_lines(
            self._resolve_bank(pin.bank),
            consumer=f"vyos-hw/{self.NAME}",
            config={pin.line: self._line_settings(
                direction=gpiod.line.Direction.AS_IS,
            )},
        ) as req:
            return 1 if req.get_value(pin.line) == gpiod.line.Value.ACTIVE else 0

    def pulse(self, name: str, ms: int = 200, asserted: int = 1) -> None:
        self.set_pin(name, asserted)
        time.sleep(ms / 1000.0)
        self.set_pin(name, 0 if asserted else 1)

    def apply_defaults(self, names: Optional[Iterable[str]] = None) -> None:
        targets = list(names) if names else list(self.PINS.keys())
        for n in targets:
            p = self.PINS.get(n)
            if p is None or p.dir != "out" or p.default is None:
                continue
            self.set_pin(n, p.default)

    # ------------------------------------------------------------------ semantic
    # Subclasses override these board-agnostic verbs. Defaults raise so a
    # caller using a generic board gets a clear error.
    def modem_reset(self) -> None:
        raise NotImplementedError(f"{self.NAME}: modem_reset not supported")

    def modem_power(self, on: bool) -> None:
        raise NotImplementedError(f"{self.NAME}: modem_power not supported")

    def sim_select(self, slot: int) -> None:
        raise NotImplementedError(f"{self.NAME}: sim_select not supported")

    def serial_protocol(self, port: str, proto: str,
                        term: Optional[bool] = None,
                        slr: Optional[bool] = None) -> None:
        raise NotImplementedError(f"{self.NAME}: serial_protocol not supported")
