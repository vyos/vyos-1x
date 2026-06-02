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

import datetime
import os
import time
from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, Optional, Tuple


# NOTE on persistence
# -------------------
# Under the libgpiod v2 / character-device interface, releasing a
# ``LineRequest`` drops only the *consumer claim* in the kernel — it does
# NOT reprogram the GPIO controller. Direction and output value remain
# whatever we last wrote, indefinitely, until something else (another
# consumer, a driver reprobe, suspend/resume on some SoCs, or a reboot)
# touches the controller. There is therefore no need to keep a long-lived
# process holding the line just to "remember" its state — write the value
# once and exit. The pin retains it.


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
    # Per-pin debounce overrides used by Board.watch_pins(). When the caller
    # passes None for the corresponding watch_pins() argument these values
    # are used. None here means "fall back to the watch_pins() default".
    debounce_us: Optional[int] = None  # kernel hardware debounce, microseconds
    settle_ms: Optional[int] = None    # userspace quiet period, milliseconds


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

    # Per-board override for resolving ``Pin.bank`` to a kernel gpiochip.
    # Subclasses may set this to a dict mapping bank-index → kernel chip
    # label (the string reported in ``/sys/class/gpio/gpiochipN/label`` /
    # ``gpiod.Chip.get_info().label``). When set, this is consulted first;
    # otherwise we fall back to /dev/gpiochipN ordering (bank N → chips[N]).
    BANK_LABELS: Dict[int, str] = {}

    def _resolve_bank(self, bank: int) -> str:
        if bank in self._bank_paths:
            return self._bank_paths[bank]
        chips = self._list_chips()
        if not chips:
            raise RuntimeError("vyos.hardware: no /dev/gpiochip* present")

        # Preferred path: match by kernel label. /dev/gpiochipN ordering
        # is not ABI-stable across kernels / probe orders, so when the
        # board declares BANK_LABELS we resolve by label.
        wanted = self.BANK_LABELS.get(bank)
        if wanted:
            gpiod = self._gpiod()
            for c in chips:
                try:
                    with gpiod.Chip(c) as ch:
                        label = ch.get_info().label
                except Exception:  # noqa: BLE001 -- diagnostic resolution
                    continue
                if label == wanted:
                    self._bank_paths[bank] = c
                    return c
            raise RuntimeError(
                f"vyos.hardware: no gpiochip with label {wanted!r} "
                f"(bank {bank}); have: "
                + ", ".join(self._chip_labels(chips))
            )

        # Fallback: positional. bank N → chips[N]. No "+1" shim — there is
        # no GPIO expander on AM64x; gpiochip0 IS main_gpio0.
        if bank >= len(chips):
            raise RuntimeError(
                f"vyos.hardware: bank {bank} requested but only "
                f"{len(chips)} /dev/gpiochip* present"
            )
        path = chips[bank]
        self._bank_paths[bank] = path
        return path

    def _chip_labels(self, chips: Iterable[str]) -> list[str]:
        gpiod = self._gpiod()
        out = []
        for c in chips:
            try:
                with gpiod.Chip(c) as ch:
                    out.append(f"{c}={ch.get_info().label}")
            except Exception:  # noqa: BLE001
                out.append(f"{c}=?")
        return out

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

    # Map ``Pin.bias`` strings to gpiod Bias values. Unknown / unset →
    # AS_IS so the line keeps whatever pinctrl/DT bias the kernel
    # already programmed.
    @classmethod
    def _bias_for(cls, pin: Pin):
        gpiod = cls._gpiod()
        return {
            "pull-up":   gpiod.line.Bias.PULL_UP,
            "pull-down": gpiod.line.Bias.PULL_DOWN,
            "as-is":     gpiod.line.Bias.AS_IS,
            "none":      gpiod.line.Bias.AS_IS,
            "":          gpiod.line.Bias.AS_IS,
        }.get(pin.bias, gpiod.line.Bias.AS_IS)

    def set_pin(self, name: str, value: int) -> None:
        """
        Drive ``name`` to ``value`` (logical level) and exit.

        ``value`` is the *logical* level: for ``active_low=True`` pins,
        ``value=1`` means "asserted/active" and drives the physical
        line low. The kernel GPIO controller retains direction and
        output level after our libgpiod request is released, so the
        line stays at ``value`` indefinitely — until some other
        consumer reprograms it. There is no "hold" vs "set" distinction
        needed.
        """
        pin = self._require(name)
        gpiod = self._gpiod()
        v = gpiod.line.Value.ACTIVE if value else gpiod.line.Value.INACTIVE
        with gpiod.request_lines(
            self._resolve_bank(pin.bank),
            consumer=f"vyos-hw/{self.NAME}",
            config={pin.line: self._line_settings(
                direction=gpiod.line.Direction.OUTPUT,
                output_value=v,
                active_low=pin.active_low,
                bias=self._bias_for(pin),
            )},
        ):
            pass  # controller register keeps direction+value after release

    def get_pin(self, name: str) -> int:
        """
        Return the *logical* level of ``name`` (1 = asserted, 0 = not).
        For ``active_low=True`` pins this is the inverse of the
        physical line level.
        """
        pin = self._require(name)
        gpiod = self._gpiod()
        # Read without reprogramming the line: direction=AS_IS keeps
        # whatever the kernel currently has configured (the pin may be
        # an output we just drove, or an input). Bias is NOT passed
        # here — gpiolib rejects bias with AS_IS as EINVAL.
        with gpiod.request_lines(
            self._resolve_bank(pin.bank),
            consumer=f"vyos-hw/{self.NAME}",
            config={pin.line: self._line_settings(
                direction=gpiod.line.Direction.AS_IS,
                active_low=pin.active_low,
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

    def modem_signal_level(self, level: int,
                           modem: Optional[str] = None) -> None:
        raise NotImplementedError(
            f"{self.NAME}: modem_signal_level not supported"
        )

    def serial_protocol(self, port: str, proto: str,
                        term: Optional[bool] = None,
                        slr: Optional[bool] = None) -> None:
        raise NotImplementedError(f"{self.NAME}: serial_protocol not supported")

    # ------------------------------------------------------------------ events
    def watch_pins(
        self,
        names: Iterable[str],
        *,
        stop_fd: Optional[int] = None,
        debounce_us: Optional[int] = 20_000,
        settle_ms: Optional[int] = 750,
        coalesce: bool = True,
    ) -> Iterator[Tuple[str, int, int]]:
        """
        Yield ``(name, level, timestamp_ns)`` tuples for edge events on the
        named input pins. Blocks; designed to be driven from a single
        background thread that pushes events onto the FSM queue.

        Two layers of debounce:

        * ``debounce_us`` — kernel hardware debounce applied per line via
          libgpiod ``LineSettings.debounce_period``. Suppresses contact
          bounce in the µs–ms range; never reaches userspace.
        * ``settle_ms`` — userspace quiet period per pin. After any edge,
          the watcher waits this long for the line to stop changing before
          emitting an event. With ``coalesce=True`` (default) only the
          final stable level is emitted, so a remove→insert→remove burst
          inside the window produces a single ``REMOVE``.

        Per-pin overrides on :class:`Pin` (``debounce_us`` / ``settle_ms``)
        take precedence over the function arguments when not ``None``.

        ``stop_fd`` is an optional file descriptor (e.g. one end of
        ``os.pipe()``) that, when made readable, causes the iterator to
        return cleanly and release all GPIO requests.

        Pass ``settle_ms=0`` and ``coalesce=False`` for fire-fast mode
        (every kernel-debounced edge is emitted immediately).
        """
        import selectors

        gpiod = self._gpiod()

        # Resolve pins, group by bank, and compute per-line effective
        # debounce/settle values (Pin override > caller arg > builtin).
        by_bank: Dict[int, Dict[int, str]] = {}
        eff_settle_ms: Dict[str, int] = {}
        for n in names:
            p = self._require(n)
            if p.dir != "in":
                raise ValueError(
                    f"{self.NAME}: watch_pins {n!r} is not an input pin"
                )
            by_bank.setdefault(p.bank, {})[p.line] = n
            eff_settle_ms[n] = (
                p.settle_ms if p.settle_ms is not None else (settle_ms or 0)
            )

        requests = []  # list[(req, {line: name})]
        try:
            for bank, lines in by_bank.items():
                cfg = {}
                for line, name in lines.items():
                    p = self.PINS[name]
                    eff_db = (
                        p.debounce_us
                        if p.debounce_us is not None
                        else (debounce_us or 0)
                    )
                    cfg[line] = self._line_settings(
                        direction=gpiod.line.Direction.INPUT,
                        edge_detection=gpiod.line.Edge.BOTH,
                        bias=self._bias_for(p),
                        active_low=p.active_low,
                        debounce_period=datetime.timedelta(microseconds=eff_db),
                    )
                req = gpiod.request_lines(
                    self._resolve_bank(bank),
                    consumer=f"vyos-hw/{self.NAME}/watch",
                    config=cfg,
                )
                requests.append((req, lines))

            sel = selectors.DefaultSelector()
            for req, lines in requests:
                sel.register(req.fd, selectors.EVENT_READ, (req, lines))
            if stop_fd is not None:
                sel.register(stop_fd, selectors.EVENT_READ, None)

            # pin name -> (last_seen_level, monotonic deadline)
            pending: Dict[str, Tuple[int, float]] = {}
            # pin name -> last level we actually yielded
            last_emitted: Dict[str, int] = {}

            rising = gpiod.EdgeEvent.Type.RISING_EDGE

            while True:
                # Block until the next deadline (or forever if nothing pending)
                now = time.monotonic()
                if pending:
                    timeout = max(
                        0.0,
                        min(d for _, d in pending.values()) - now,
                    )
                else:
                    timeout = None

                events = sel.select(timeout=timeout)

                # 1. drain kernel-debounced edges into the pending map
                for key, _ in events:
                    if key.data is None:
                        return  # stop_fd fired
                    req, lines = key.data
                    for ev in req.read_edge_events():
                        name = lines[ev.line_offset]
                        level = 1 if ev.event_type == rising else 0
                        if not coalesce and last_emitted.get(name) != level:
                            last_emitted[name] = level
                            yield name, level, ev.timestamp_ns
                        deadline = (
                            time.monotonic()
                            + eff_settle_ms[name] / 1000.0
                        )
                        pending[name] = (level, deadline)

                # 2. flush any pin whose quiet window has elapsed
                now = time.monotonic()
                expired = [n for n, (_, d) in pending.items() if d <= now]
                for name in expired:
                    level, _ = pending.pop(name)
                    if last_emitted.get(name) != level:
                        last_emitted[name] = level
                        yield name, level, time.monotonic_ns()
        finally:
            for req, _ in requests:
                try:
                    req.release()
                except Exception:
                    pass
