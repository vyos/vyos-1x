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
Stable, board-agnostic facade. Import this from conf-mode scripts, the WWAN
FSM, serial helpers, etc.
"""

from typing import List, Optional

from vyos.hardware.board import BOARD as _b


# --- wwan netdev <-> pinmap modem binding -----------------------------------
# The board ships udev .link + .rules files that pin a physical USB slot to a
# fixed netdev name (``wwanN``) and a fixed ModemManager UID (``modemN``).
# When that contract holds, the FSM may use the trailing integer of the
# netdev name as the pinmap modem index. ``verify_wwan_binding`` asserts the
# contract is intact; ``wwan_to_modem`` is the convenience wrapper the FSM
# calls per interface.

# Canonical pinmap naming convention used by ``wwan_to_modem`` /
# ``verify_wwan_binding``. Override at runtime if a board uses a different
# prefix (e.g. ``CELL``) by setting ``vyos.hardware.api.MODEM_NAME_FMT``.
MODEM_NAME_FMT: str = "MODEM{idx}"


def wwan_to_modem(ifname: str) -> str:
    """
    Translate a kernel netdev name (``wwan0``, ``wwan3``, \u2026) into the
    pinmap modem name (``MODEM0``, ``MODEM3``, \u2026).

    This is a *pure* name transform; it does NOT verify that the netdev is
    actually wired to that physical slot. Call :func:`verify_wwan_binding`
    once at startup to assert the udev contract.
    """
    import re
    m = re.fullmatch(r"wwan(\d+)", ifname)
    if not m:
        raise ValueError(f"wwan_to_modem: {ifname!r} is not a wwanN name")
    return MODEM_NAME_FMT.format(idx=int(m.group(1)))


def verify_wwan_binding(
    ifname: str,
    *,
    expected_bus_substr: Optional[str] = None,
) -> str:
    """
    Assert that ``ifname`` is bound to its expected physical slot and that
    the pinmap declares the matching modem. Returns the pinmap modem name
    (e.g. ``MODEM0``) for use with :func:`modem_reset` /
    :func:`modem_power` / :func:`sim_select` / :func:`sim_detect_pins`.

    Raises :class:`RuntimeError` with a precise diagnosis on any failure:

    * netdev does not exist (kernel never created it)
    * netdev is not on the platform USB bus the .link file pins it to
      (udev rule / .link file missing, or hardware in wrong slot)
    * pinmap does not declare the matching modem name

    ``expected_bus_substr`` is a substring that must appear in the
    resolved ``/sys/class/net/<ifname>/device`` path. Defaults to the
    Perle AM64x bus prefix (``platform-xhci-hcd.4.auto-usb``). Pass a
    different value for other boards, or ``""`` to skip the bus check.
    """
    from pathlib import Path
    if expected_bus_substr is None:
        expected_bus_substr = "platform-xhci-hcd.4.auto-usb"

    expected_modem = wwan_to_modem(ifname)

    sysfs = Path(f"/sys/class/net/{ifname}")
    if not sysfs.exists():
        raise RuntimeError(
            f"{ifname}: netdev does not exist; "
            "is the modem powered, enumerated, and is the .link file installed?"
        )

    if expected_bus_substr:
        dev_link = sysfs / "device"
        if not dev_link.exists():
            raise RuntimeError(
                f"{ifname}: no /sys/class/net/{ifname}/device link "
                "(virtual or stub interface?)"
            )
        try:
            resolved = dev_link.resolve(strict=True)
        except OSError as exc:
            raise RuntimeError(
                f"{ifname}: cannot resolve sysfs device path: {exc}"
            ) from exc
        if expected_bus_substr not in str(resolved):
            raise RuntimeError(
                f"{ifname}: bound to {resolved}, expected substring "
                f"{expected_bus_substr!r}; .link file missing or hardware "
                "in unexpected slot?"
            )

    if expected_modem not in list_modems():
        raise RuntimeError(
            f"{ifname}: pinmap declares no {expected_modem!r} "
            f"(known: {list_modems() or '<none>'})"
        )
    return expected_modem


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
def modem_reset(modem: Optional[str] = None) -> None:
    _b.modem_reset(modem=modem)


def modem_power(on: bool, modem: Optional[str] = None) -> None:
    _b.modem_power(on, modem=modem)


def sim_select(slot: int, modem: Optional[str] = None) -> None:
    _b.sim_select(slot, modem=modem)


def sim_select_state(modem: Optional[str] = None) -> Optional[int]:
    """Return the slot the SIM mux currently selects (1 or 2), or None.

    None means the board has no ``sim_select`` GPIO for ``modem`` (it is
    not a GPIO-mux board).
    """
    return _b.sim_select_state(modem=modem)


def modem_signal_level(level: int, modem: Optional[str] = None) -> None:
    """Map signal level (0..7) to board modem STAT LED display."""
    _b.modem_signal_level(level=level, modem=modem)


def list_modems() -> List[str]:
    """Return every modem name declared by the active pinmap."""
    return _b.list_modems()


def sim_detect_pins(modem: Optional[str] = None) -> List[str]:
    """
    Return the SIM-detect input pin names for ``modem`` (or the only
    modem if omitted). Pass the result to a watcher backed by
    :meth:`vyos.hardware.base.Board.watch_pins` to receive SIM
    insert/remove events without polling.
    """
    return _b.sim_detect_pins(modem=modem)


def modem_capabilities(modem: Optional[str] = None) -> frozenset:
    """
    Return the hardware-control roles the active pinmap declares for
    ``modem`` (or the only modem if omitted): any of ``"reset"``,
    ``"power"``, ``"sim_select"``, ``"sim_detect"``.

    The WWAN FSM calls this to decide whether a modem needs GPIO-mux SIM
    switching: ``"sim_select"`` present means the board selects the SIM
    slot via an external GPIO mux (only one SIM interface is exposed to
    the modem), so the FSM must drive switching + reboot itself rather
    than calling ModemManager's ``SetPrimarySimSlot``.
    """
    return _b.modem_capabilities(modem=modem)


def watch_pins(
    names,
    *,
    stop_fd: Optional[int] = None,
    debounce_us: Optional[int] = 20_000,
    settle_ms: Optional[int] = 750,
    coalesce: bool = True,
):
    """
    Yield ``(name, level, timestamp_ns)`` tuples for edge events on the
    listed input pins. Blocks; run from a dedicated thread.

    Two layers of debounce, both per-pin overridable on :class:`Pin`:

    * ``debounce_us`` \u2014 kernel hardware debounce (libgpiod
      ``LineSettings.debounce_period``). Suppresses contact bounce in
      the \u00b5s\u2013ms range; defaults to 20\u202fms.
    * ``settle_ms`` \u2014 userspace quiet period. After any edge the
      watcher waits this long for the line to stop changing before
      emitting; with ``coalesce=True`` (default) only the final stable
      level is emitted. Default 750\u202fms \u2014 well above typical SIM-tray
      bounce.

    ``stop_fd`` is one end of an :func:`os.pipe` you can write to from
    a shutdown handler; the iterator returns cleanly and releases the
    GPIO requests when it becomes readable.

    Pass ``settle_ms=0, coalesce=False`` for fire-fast mode (every
    kernel-debounced edge is emitted immediately).
    """
    return _b.watch_pins(
        names,
        stop_fd=stop_fd,
        debounce_us=debounce_us,
        settle_ms=settle_ms,
        coalesce=coalesce,
    )


def watch_sim_detect(
    modem: Optional[str] = None,
    *,
    stop_fd: Optional[int] = None,
    debounce_us: Optional[int] = 20_000,
    settle_ms: Optional[int] = 750,
):
    """
    Convenience wrapper around :func:`watch_pins` for SIM-detect events.

    Yields ``(pin_name, event, timestamp_ns)`` where ``event`` is the
    string ``"INSERTED"`` or ``"REMOVED"`` \u2014 mapped from the line level
    according to ``Pin.active_low`` so the FSM never has to reason about
    raw polarity.

    Tray-bounce on insertion can last tens to a few hundred ms; the
    default 750\u202fms userspace settle window comfortably coalesces those
    into a single event per physical action.
    """
    pins = _b.sim_detect_pins(modem=modem)
    if not pins:
        return
    # Resolve active_low once so the inner loop is O(1).
    pin_table = getattr(_b, "PINS", {}) or {}
    active_low = {n: bool(getattr(pin_table.get(n), "active_low", False))
                  for n in pins}
    for name, level, ts in _b.watch_pins(
        pins,
        stop_fd=stop_fd,
        debounce_us=debounce_us,
        settle_ms=settle_ms,
        coalesce=True,
    ):
        # libgpiod already inverts the raw electrical level when
        # active_low=True, so ``level`` here is the *logical* state.
        # Logical 1 on a SIM-detect line conventionally means
        # "card present"; map that to INSERTED.
        event = "INSERTED" if level else "REMOVED"
        # active_low is retained in the dict for diagnostics only; the
        # libgpiod-applied inversion already took care of polarity.
        _ = active_low  # noqa: F841 \u2014 reserved for future per-pin overrides
        yield name, event, ts


def serial_protocol(port: str, proto: str,
                    term: Optional[bool] = None,
                    slr: Optional[bool] = None) -> None:
    """
    Configure a serial transceiver for one of: ``isolate``, ``rs232``,
    ``rs485h``, ``rs485f``, ``rs422``.
    """
    _b.serial_protocol(port, proto, term=term, slr=slr)


def list_serial_ports() -> List[str]:
    """
    Return every serial port name declared by the active pinmap. There is
    no hardcoded limit \u2014 a pinmap can expose as many ports as the board
    physically provides.
    """
    return _b.list_serial_ports()

def serial_port_info(port: str) -> dict:
    """
    Return ``{name, roles, meta}`` for ``port`` as declared in the
    pinmap. ``roles`` maps internal roles (``shut``, ``m2`` …) to
    physical pin names; ``meta`` carries application-facing identity
    (``tty``, ``by_path``, ``alias``, ``label``).
    """
    return _b.serial_port_info(port)


def serial_port_tty(port: str) -> str:
    """
    Canonical device path an application should ``open()`` for ``port``.
    Prefers the explicit ``tty`` value, falling back to ``by_path``.
    Example: ``serial_port_tty("UARTC2") -> "/dev/ttyS1"``.
    """
    return _b.serial_port_tty(port)


def serial_port_for_tty(path: str) -> str:
    """
    Reverse lookup: given any device path the developer has
    (``/dev/ttyS1``, a ``by-path`` symlink, a friendly alias under
    ``/dev/igos/``), return the pinmap port name.

    Strict — raises ``ValueError`` if ``path`` does not resolve to any
    declared port. The comparison uses ``realpath`` on both sides so any
    symlink chain that lands on the right kernel node will match.
    """
    return _b.serial_port_for_tty(path)


def serial_port_type(port: str) -> str:
    """
    Return the transceiver type for ``port`` \u2014 e.g. ``"thvd4431"``
    (mode-switchable) or ``"fixed_rs232"`` (plain RS-232 part). Higher
    layers can use this to decide whether to expose RS-485/RS-422 in the
    UI for the port.
    """
    return _b.serial_port_type(port)


def serial_port_supported_protocols(port: str) -> list:
    """
    Return the list of protocols ``port`` accepts. ``fixed_rs232`` ports
    return ``["isolate", "rs232"]``; ``thvd4431`` ports return the full
    set the part supports. Use this to validate user input before
    calling :func:`serial_protocol`.
    """
    return _b.serial_port_supported_protocols(port)


def verify_serial_bindings(*, strict: bool = True) -> dict:
    """
    Assert that every port whose pinmap entry declares a ``dt_node``
    resolves to that device-tree node via ``/sys/class/tty/<N>/device/of_node``.

    This is the bridge between the pinmap (which controls the
    transceiver) and the kernel's ``/dev/ttySN`` numbering (which the
    application opens). Without this check a typo in the pinmap's
    ``tty`` value would silently re-wire the wrong UART to the wrong
    transceiver.

    Call once at FSM/daemon startup. ``strict=True`` (default) raises
    ``RuntimeError`` on the first mismatch; ``strict=False`` returns a
    ``{port: 'ERROR: ...'}`` dict so callers can log every problem at
    once. Soft-skips on build hosts / CI where ``/sys/class/tty`` is
    absent.
    """
    return _b.verify_serial_bindings(strict=strict)
