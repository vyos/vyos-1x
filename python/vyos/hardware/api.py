# Copyright (C) VyOS Inc.
# SPDX-License-Identifier: LGPL-2.1-or-later
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
