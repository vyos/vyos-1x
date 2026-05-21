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

import datetime
import os
import signal
import time
from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, Optional, Tuple


# Where hold_pin() stashes the PID of each per-pin holder process so a
# subsequent hold_pin() / release_pin() can find and replace it. A holder
# is only spawned when the requested value FIGHTS the board pull declared
# in ``Pin.bias`` — values matching the pull are just released and the
# board hardware keeps the line where we want.
_PIN_HOLD_DIR = "/run/vyos/hw/pins"


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
            pass  # momentary drive; board pull retains the value on release

    @staticmethod
    def _pull_value(pin: "Pin") -> Optional[int]:
        """
        Return the physical level the line settles to with no consumer,
        derived from the board pull documented in ``Pin.bias``. Returns
        ``None`` if the bias is ``as-is`` (we can't know — caller must
        treat as "unknown, always hold").
        """
        if pin.bias == "pull-up":
            return 1
        if pin.bias == "pull-down":
            return 0
        return None

    def hold_pin(self, name: str, value: int) -> None:
        """
        Drive ``name`` to ``value`` and KEEP it there.

        If ``value`` matches the board pull declared in ``Pin.bias`` the
        line will hold itself with no consumer, so we simply drop any
        prior holder and return — zero long-lived processes.

        If ``value`` fights the board pull, a small detached holder
        process is forked. It claims the gpiod line at ``value`` and
        blocks on a signal. A subsequent ``hold_pin`` / ``release_pin``
        for the same pin sends SIGTERM to retire the prior holder before
        the new one (if any) takes over.
        """
        pin = self._require(name)
        # Always retire any prior holder so the new value (or release)
        # takes effect even if the old holder was driving the opposite.
        self._release_pin(name)
        pull = self._pull_value(pin)
        if pull == value:
            # Board pull already produces the requested level; touching
            # the line at all is unnecessary. Be quiet.
            return
        # Either pull fights us, or bias is "as-is" (unknown). Either
        # way we need a long-lived consumer to hold the line.
        self._spawn_pin_holder(name, pin, value)

    def release_pin(self, name: str) -> bool:
        """
        Public entry point: stop holding ``name`` so the board pull
        re-takes the line. Returns True if a holder was retired, False
        if no holder was active.
        """
        # Validate the name so callers get a clear error for typos.
        self._require(name)
        return self._release_pin(name)

    def _release_pin(self, name: str) -> bool:
        pidfile = os.path.join(_PIN_HOLD_DIR, f"{name}.pid")
        try:
            with open(pidfile) as f:
                pid = int(f.read().strip())
        except (FileNotFoundError, ValueError):
            return False
        alive = True
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            alive = False
        if alive:
            # Wait briefly for the holder to drop its gpiod claim.
            for _ in range(100):
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.01)
        try:
            os.unlink(pidfile)
        except FileNotFoundError:
            pass
        return True

    def _spawn_pin_holder(self, name: str, pin: "Pin", value: int) -> None:
        try:
            os.makedirs(_PIN_HOLD_DIR, exist_ok=True)
        except PermissionError as exc:
            raise PermissionError(
                f"{self.NAME}: cannot create {_PIN_HOLD_DIR} "
                f"(run as root): {exc}"
            ) from exc

        # Child writes 1 (claim succeeded) or 0 (failed) before parent
        # returns — guarantees the new value is observable immediately.
        r_fd, w_fd = os.pipe()
        pid = os.fork()
        if pid > 0:
            # ---- parent ----
            os.close(w_fd)
            try:
                ready = os.read(r_fd, 1)
            finally:
                os.close(r_fd)
            if ready != b"1":
                try:
                    os.waitpid(pid, os.WNOHANG)
                except ChildProcessError:
                    pass
                raise RuntimeError(
                    f"{self.NAME}: failed to hold {name!r} at {value}"
                )
            return

        # ---- child ----
        os.close(r_fd)
        try:
            os.setsid()
        except OSError:
            pass
        try:
            devnull = os.open(os.devnull, os.O_RDWR)
            for fd in (0, 1, 2):
                os.dup2(devnull, fd)
            if devnull > 2:
                os.close(devnull)
        except OSError:
            pass

        pidfile = os.path.join(_PIN_HOLD_DIR, f"{name}.pid")
        try:
            with open(pidfile, "w") as f:
                f.write(f"{os.getpid()}\n")
        except OSError:
            try:
                os.write(w_fd, b"0")
            finally:
                os._exit(1)

        gpiod = self._gpiod()
        v = gpiod.line.Value.ACTIVE if value else gpiod.line.Value.INACTIVE
        consumer = f"vyos-hw/{name}"[:31]  # libgpiod v2 caps at 31 bytes
        try:
            req = gpiod.request_lines(
                self._resolve_bank(pin.bank),
                consumer=consumer,
                config={pin.line: self._line_settings(
                    direction=gpiod.line.Direction.OUTPUT,
                    output_value=v,
                )},
            )
        except BaseException:
            try:
                os.unlink(pidfile)
            except FileNotFoundError:
                pass
            try:
                os.write(w_fd, b"0")
            finally:
                pass
            os._exit(1)

        def _stop(*_a):
            try:
                req.release()
            except Exception:
                pass
            try:
                os.unlink(pidfile)
            except FileNotFoundError:
                pass
            os._exit(0)

        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)

        try:
            os.write(w_fd, b"1")
        finally:
            os.close(w_fd)

        while True:
            signal.pause()

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

        bias_map = {
            "pull-up": gpiod.line.Bias.PULL_UP,
            "pull-down": gpiod.line.Bias.PULL_DOWN,
            "as-is": gpiod.line.Bias.AS_IS,
        }

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
                        bias=bias_map.get(p.bias, gpiod.line.Bias.AS_IS),
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
