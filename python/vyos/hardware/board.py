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
Board logic shared across all igOS hardware images.

Serial protocol switching (THVD4431-style mode-programmable transceiver):
the M[2:0]/TERM/SLR lines must only be changed while the transceiver is in
shutdown, otherwise the part may momentarily drive a wrong combination onto
the bus during the transition (RS-485 contention, RS-232 receiver glitch).
``serial_protocol`` therefore always:

1. asserts SHUT_N=0 first (force transceiver into shutdown),
2. waits a short settle window for the driver to actually disable,
3. programs M2/M1/M0/TERM/SLR to the new values,
4. drives SHUT_N to the target state (1 for active protocols, 0 for
   ``isolate``).

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

from typing import Dict, List, Optional
import os
import threading
import time
import re

from vyos.hardware.base import Board, Pin

# Time the THVD4431 needs to actually enter shutdown after SHUT_N is driven
# low before we are allowed to reprogram M[2:0]. The datasheet quotes tens
# of µs; we use 2 ms for ample margin (this only runs on CLI mode changes,
# not in a hot path).
_SHUT_SETTLE_MS: int = 2

# Pin-name suffixes that make up one modem. A modem is discovered from the
# pinmap when at least the RESET pin is present; the other roles are
# optional. ``sim_detect`` is a *family* of inputs (any number per modem)
# identified by the prefix ``_SIM_DETECT`` — ``_SIM_DETECT``,
# ``_SIM_DETECT_0``, ``_SIM_DETECT_1`` … are all accepted.
_MODEM_PIN_SUFFIXES = {
    "reset":      "_UNCOND_RESET",
    "power":      "_SHUTDOWN_N",      # active-low; 1 = run
    "sim_select": "_SIM_SELECT_1N_OR_2",  # 0 = slot 1, 1 = slot 2
}
_MODEM_SIM_DETECT_PREFIX = "_SIM_DETECT"

# Pin-name suffixes that make up one THVD4431-style serial port. A port is
# discovered from the pinmap when at least the SHUT pin is present; the
# other pins are looked up on demand. A pinmap that wants to expose a port
# with non-standard suffixes can declare it explicitly via ``SERIAL_PORTS``
# (see :func:`_discover_serial_ports`).
_PORT_PIN_SUFFIXES = {
    "shut":  "_SHUT_N",
    "m2":    "_MODE2",
    "m1":    "_MODE1",
    "m0":    "_MODE0",
    "term_tx": "_TERM_TX",
    "term_rx": "_TERM_RX",
    "slr":   "_SLR",
}

# Metadata keys allowed in pinmap.SERIAL_PORTS alongside pin-role keys. These
# describe the *application-facing* identity of a port — the tty device,
# stable by-path symlink, friendly alias and a human label — so an app dev
# only ever sees a path like /dev/ttyS1 or /dev/igos/uartc2 and never the
# underlying GPIO pin names.
_PORT_META_KEYS = frozenset({
    "type", "tty", "by_path", "alias", "label", "dt_node",
})


# -----------------------------------------------------------------------------
# Transceiver handlers.
#
# Every serial port is associated with a transceiver "type" that decides
# (a) which ``proto`` values are accepted, (b) which pins must be present,
# and (c) what to write in step 3 of the SHUT → settle → program → SHUT
# sequence. The SHUT primitive is identical for every type because *every*
# board ships transceivers off at boot and software brings them up on
# configuration; the only thing that differs between types is what gets
# programmed while SHUT is asserted.
# -----------------------------------------------------------------------------

# THVD4431 truth table (M2 M1 M0 → mode + final SHUT level)
_THVD4431_PROTOCOLS = {
    "isolate": {"M2": 0, "M1": 0, "M0": 0, "SHUT": 0},
    "rs232":   {"M2": 0, "M1": 0, "M0": 1, "SHUT": 1},
    "rs485h":  {"M2": 0, "M1": 1, "M0": 0, "SHUT": 1},
    "rs485f":  {"M2": 0, "M1": 1, "M0": 1, "SHUT": 1},
    "rs422":   {"M2": 0, "M1": 1, "M0": 1, "SHUT": 1},
}

# A type's "required" roles must be present on every port classified as
# that type; "optional" roles are programmed if present, otherwise
# silently skipped.
class _TransceiverHandler:
    name: str = ""
    accepts: frozenset = frozenset()
    required_roles: tuple = ("shut",)
    optional_roles: tuple = ()

    def plan(self, proto: str, *, term: Optional[bool], slr: Optional[bool]
             ) -> tuple:
        """
        Return ``(role_values, final_shut)`` for ``proto``:
          * ``role_values``: dict of role → 0/1 to write in step 3 (SHUT
            already asserted low; only listed roles are written, and only
            if the port actually declared that role pin).
          * ``final_shut``: 0 or 1 — the level to drive on ``shut`` in
            step 4 (0 = stay in shutdown, used by ``isolate``).
        """
        raise NotImplementedError


class _Thvd4431Handler(_TransceiverHandler):
    name = "thvd4431"
    accepts = frozenset(_THVD4431_PROTOCOLS)
    required_roles = ("shut", "m2", "m1", "m0")
    optional_roles = ("term_tx", "term_rx", "slr")

    def plan(self, proto, *, term, slr):
        spec = _THVD4431_PROTOCOLS[proto]
        # Defaults: SLR=on (fast), TERM=off. Overridden by RS-232/RS-485
        # convention so callers don't have to think about it.
        slr_v = 1 if (slr if slr is not None else True) else 0
        term_v = 1 if (term if term is not None else False) else 0
        if proto == "rs232":
            term_v = 0
        elif proto in ("rs485h", "rs485f", "rs422"):
            slr_v = 1
        plan = {
            "m2":      spec["M2"],
            "m1":      spec["M1"],
            "m0":      spec["M0"],
            "term_tx": term_v,
            "term_rx": term_v,
            "slr":     slr_v,
        }
        return plan, spec["SHUT"]


class _FixedRs232Handler(_TransceiverHandler):
    name = "fixed_rs232"
    # Plain RS-232 part — only verbs that make sense are 'rs232' (on) and
    # 'isolate' (off). Boards may optionally wire TERM pins; we accept
    # them but real RS-232 wiring almost never has them populated.
    accepts = frozenset({"isolate", "rs232"})
    required_roles = ("shut",)
    optional_roles = ("term_tx", "term_rx")

    def plan(self, proto, *, term, slr):
        if proto == "isolate":
            return {}, 0
        # proto == "rs232"
        term_v = 1 if (term if term is not None else False) else 0
        return {"term_tx": term_v, "term_rx": term_v}, 1


_TRANSCEIVER_HANDLERS: Dict[str, _TransceiverHandler] = {
    h.name: h for h in (_Thvd4431Handler(), _FixedRs232Handler())
}


def _auto_detect_type(roles: Dict[str, str]) -> str:
    """
    Classify a port from its discovered pin set:
      * all three M2/M1/M0 present → ``thvd4431``
      * none of M2/M1/M0 present  → ``fixed_rs232``
      * partial mode pins         → raise (caller turns into clear error)
    """
    mode_present = {r for r in ("m2", "m1", "m0") if r in roles}
    if not mode_present:
        return "fixed_rs232"
    if mode_present == {"m2", "m1", "m0"}:
        return "thvd4431"
    raise ValueError(
        "partial mode pins ("
        f"{sorted(mode_present)}); declare 'type' explicitly in "
        "SERIAL_PORTS to disambiguate"
    )


def _discover_serial_ports(
    pins: Dict[str, Pin],
    explicit: Optional[Dict[str, Dict[str, str]]] = None,
) -> tuple:
    """
    Return ``(ports, meta)`` where ``ports`` is ``{name: {role: pin_name}}``
    and ``meta`` is ``{name: {tty, by_path, alias, label}}`` (only keys the
    pinmap declared are present; ``alias`` and ``label`` are optional, but
    at least one of ``tty`` / ``by_path`` is **required** for every port).

    Two discovery sources, combined:

    * **Implicit** — any pin whose name ends in ``_SHUT_N`` defines a port
      named by its prefix. The remaining roles are looked up using the
      canonical ``_PORT_PIN_SUFFIXES`` suffixes.
    * **Explicit** — ``pinmap.SERIAL_PORTS`` may supply
      ``{port_name: {role_or_meta: value}}`` to override pin suffixes
      (e.g. ``{"shut": "FRONT_TXEN_N"}``) and/or to supply application
      metadata (``tty``, ``by_path``, ``alias``, ``label``). Pin-role
      values must be names of pins present in ``PINS``; metadata values
      are strings stored as-is.

    Raises ``ValueError`` on:
      * unknown keys in an explicit entry,
      * a pin-role value that doesn’t exist in ``PINS``,
      * a declared port missing both ``tty`` and ``by_path``.
    A port without a ``shut`` pin is silently dropped (it can’t be
    switched safely).
    """
    valid_keys = set(_PORT_PIN_SUFFIXES) | _PORT_META_KEYS
    ports: Dict[str, Dict[str, str]] = {}
    meta: Dict[str, Dict[str, str]] = {}

    # Implicit: scan for *_SHUT_N pins.
    shut_suffix = _PORT_PIN_SUFFIXES["shut"]
    for pin_name in pins:
        if not pin_name.endswith(shut_suffix):
            continue
        port = pin_name[: -len(shut_suffix)]
        roles: Dict[str, str] = {}
        for role, suffix in _PORT_PIN_SUFFIXES.items():
            candidate = f"{port}{suffix}"
            if candidate in pins:
                roles[role] = candidate
        ports[port] = roles
        meta.setdefault(port, {})

    # Explicit: pinmap.SERIAL_PORTS overrides / adds.
    if explicit:
        for port, decl in explicit.items():
            existing_roles = ports.get(port, {})
            existing_meta = meta.get(port, {})
            for key, value in decl.items():
                if key not in valid_keys:
                    raise ValueError(
                        f"pinmap SERIAL_PORTS[{port!r}]: unknown key "
                        f"{key!r}, expected one of {sorted(valid_keys)}"
                    )
                if key in _PORT_PIN_SUFFIXES:
                    if value not in pins:
                        raise ValueError(
                            f"pinmap SERIAL_PORTS[{port!r}][{key!r}] = "
                            f"{value!r}: pin not defined in PINS"
                        )
                    existing_roles[key] = value
                else:
                    if not isinstance(value, str) or not value:
                        raise ValueError(
                            f"pinmap SERIAL_PORTS[{port!r}][{key!r}]: "
                            f"expected non-empty string, got {value!r}"
                        )
                    existing_meta[key] = value
            ports[port] = existing_roles
            meta[port] = existing_meta

    # Drop ports without a SHUT pin — they can’t be switched safely.
    ports = {p: r for p, r in ports.items() if "shut" in r}
    meta = {p: meta.get(p, {}) for p in ports}

    # Require at least one device handle per port.
    missing = [
        p for p, m in meta.items()
        if not (m.get("tty") or m.get("by_path"))
    ]
    if missing:
        raise ValueError(
            "pinmap SERIAL_PORTS: every declared serial port must supply "
            f"'tty' and/or 'by_path' \u2014 missing on: {missing}. "
            "Add the entry, e.g. SERIAL_PORTS={'UARTC2': {'tty': "
            "'/dev/ttyS1', 'by_path': '/dev/serial/by-path/...'}, ...}"
        )

    # Resolve and validate the transceiver type for every port.
    types: Dict[str, str] = {}
    for port, roles in ports.items():
        declared = meta[port].pop("type", None)  # type isn't user-facing meta
        if declared is not None:
            if declared not in _TRANSCEIVER_HANDLERS:
                raise ValueError(
                    f"pinmap SERIAL_PORTS[{port!r}]['type'] = "
                    f"{declared!r}: unknown transceiver type; "
                    f"known: {sorted(_TRANSCEIVER_HANDLERS)}"
                )
            t = declared
        else:
            try:
                t = _auto_detect_type(roles)
            except ValueError as exc:
                raise ValueError(
                    f"pinmap SERIAL_PORTS[{port!r}]: {exc}"
                ) from None
        handler = _TRANSCEIVER_HANDLERS[t]

        # Required roles must all be present.
        missing_req = [r for r in handler.required_roles if r not in roles]
        if missing_req:
            raise ValueError(
                f"pinmap SERIAL_PORTS[{port!r}]: transceiver type "
                f"{t!r} requires roles {list(handler.required_roles)} "
                f"but missing {missing_req}"
            )
        # Forbid roles that don't belong to this type.
        allowed = set(handler.required_roles) | set(handler.optional_roles)
        forbidden = [r for r in roles if r not in allowed]
        if forbidden:
            raise ValueError(
                f"pinmap SERIAL_PORTS[{port!r}]: transceiver type "
                f"{t!r} does not use roles {sorted(forbidden)}; "
                "did you mean a different 'type' or are these pins "
                "named with the wrong suffix?"
            )
        types[port] = t

        # Safety: every board must ship transceivers in shutdown so a
        # cold boot never drives a wrong protocol on the bus. ``default``
        # is the *logical* level (active_low is applied below it), so a
        # SHUT-asserted cold boot is either default=None (Hi-Z + bias) or
        # default=1 on an active_low pin / default=0 on an active_high
        # pin. The opposite polarity would deassert SHUT at boot.
        shut_pin = pins[roles["shut"]]
        shipped_in_shutdown = (
            shut_pin.default is None
            or (shut_pin.active_low and shut_pin.default == 1)
            or (not shut_pin.active_low and shut_pin.default == 0)
        )
        if not shipped_in_shutdown:
            raise ValueError(
                f"pinmap SERIAL_PORTS[{port!r}]: SHUT pin "
                f"{roles['shut']!r} has "
                f"Pin(default={shut_pin.default!r}, "
                f"active_low={shut_pin.active_low!r}); cold boot would "
                "deassert SHUT and drive the bus. Transceiver must ship "
                "in shutdown; software enables the port when the user "
                "configures it."
            )

    return ports, meta, types


def _discover_modems(
    pins: Dict[str, Pin],
    explicit: Optional[Dict[str, Dict[str, object]]] = None,
) -> Dict[str, Dict[str, object]]:
    """
    Return ``{modem_name: roles}`` where ``roles`` has keys ``reset``
    (required), ``power``, ``sim_select`` (each str) and ``sim_detect``
    (list[str], possibly empty).

    Two discovery sources, combined:

    * **Implicit** — any pin whose name ends in ``_UNCOND_RESET`` defines
      a modem named by its prefix. Sibling role pins are matched by
      suffix; SIM-detect inputs are matched by the
      ``<prefix>_SIM_DETECT*`` family and returned as a sorted list.
    * **Explicit** — ``pinmap.MODEMS`` may supply
      ``{modem_name: {role: pin_name | [pin_name, …]}}`` for boards that
      don’t follow the suffix convention. Validated against PINS.

    A modem without a ``reset`` pin is dropped (nothing safe to do).
    """
    modems: Dict[str, Dict[str, object]] = {}

    reset_suffix = _MODEM_PIN_SUFFIXES["reset"]
    for pin_name in pins:
        if not pin_name.endswith(reset_suffix):
            continue
        modem = pin_name[: -len(reset_suffix)]
        roles: Dict[str, object] = {"reset": pin_name}
        for role, suffix in _MODEM_PIN_SUFFIXES.items():
            if role == "reset":
                continue
            candidate = f"{modem}{suffix}"
            if candidate in pins:
                roles[role] = candidate
        # SIM detect family
        detect_prefix = f"{modem}{_MODEM_SIM_DETECT_PREFIX}"
        roles["sim_detect"] = sorted(
            p for p in pins if p.startswith(detect_prefix)
        )
        modems[modem] = roles

    if explicit:
        valid_roles = set(_MODEM_PIN_SUFFIXES) | {"sim_detect"}
        for modem, decl in explicit.items():
            roles = {"sim_detect": []}  # default
            for role, value in decl.items():
                if role not in valid_roles:
                    raise ValueError(
                        f"pinmap MODEMS[{modem!r}]: unknown role "
                        f"{role!r}, expected one of {sorted(valid_roles)}"
                    )
                if role == "sim_detect":
                    names = list(value) if isinstance(value, (list, tuple)) \
                        else [value]
                    for pin_name in names:
                        if pin_name not in pins:
                            raise ValueError(
                                f"pinmap MODEMS[{modem!r}][sim_detect]: "
                                f"pin {pin_name!r} not defined in PINS"
                            )
                    roles["sim_detect"] = list(names)
                else:
                    if value not in pins:
                        raise ValueError(
                            f"pinmap MODEMS[{modem!r}][{role!r}] = "
                            f"{value!r}: pin not defined in PINS"
                        )
                    roles[role] = value
            modems[modem] = roles

    return {m: r for m, r in modems.items() if "reset" in r}


class IgosBoard(Board):
    """
    Board implementation parameterised solely by the overlaid ``pinmap``
    module. Pin numbers, the ``VARIANT`` string and the set of serial
    ports all come from there; this class is board-agnostic.
    """
    PINS: dict = {}
    NAME: str = "igos_unknown"

    # AM64x SoC GPIO controllers — match by the kernel label rather than
    # /dev/gpiochipN index ordering (which is not stable across kernels).
    # Pinmap ``bank=0`` → main_gpio0 (87 lines), ``bank=1`` → main_gpio1
    # (89 lines). Labels come from k3-am64-main.dtsi:
    #     gpio0: gpio@600000 ;
    #     gpio1: gpio@601000 ;
    # The pinmap overlay may override this by setting ``BANK_LABELS`` on
    # the ``pinmap`` module itself (handled in _build_board()).
    BANK_LABELS = {
        0: "600000.gpio",
        1: "601000.gpio",
    }

    def __init__(self) -> None:
        super().__init__()
        # Port table populated by _build_board() after PINS is assigned.
        # Shape: {port_name: {role: pin_name}}.
        self._serial_ports: Dict[str, Dict[str, str]] = {}
        # Parallel metadata: {port_name: {tty, by_path, alias, label}}.
        # 'tty' and/or 'by_path' is guaranteed present for every entry; the
        # other two are optional. Populated by _build_board().
        self._serial_meta: Dict[str, Dict[str, str]] = {}
        # Per-port transceiver type, e.g. 'thvd4431' or 'fixed_rs232'.
        self._serial_types: Dict[str, str] = {}
        # Lazy per-port mutex so concurrent switches on the same port
        # serialise their SHUT → program → un-SHUT sequence. Released as
        # soon as the with-block exits.
        self._serial_locks: Dict[str, threading.Lock] = {}
        self._serial_locks_guard = threading.Lock()
        # Modem table populated by _build_board().
        # Shape: {modem_name: {reset, power?, sim_select?, sim_detect: [..]}}.
        self._modems: Dict[str, Dict[str, object]] = {}

    def _serial_lock(self, port: str) -> threading.Lock:
        lock = self._serial_locks.get(port)
        if lock is None:
            with self._serial_locks_guard:
                lock = self._serial_locks.get(port)
                if lock is None:
                    lock = threading.Lock()
                    self._serial_locks[port] = lock
        return lock

    def list_serial_ports(self) -> List[str]:
        """Return all serial port names declared by the active pinmap."""
        return sorted(self._serial_ports)

    def serial_port_info(self, port: str) -> Dict[str, object]:
        """
        Return a full description of ``port``: roles (pin assignments) and
        metadata (tty / by_path / alias / label) as declared in the
        pinmap. Raises ``ValueError`` if the port is unknown.
        """
        port = port.upper()
        if port not in self._serial_ports:
            known = ", ".join(self.list_serial_ports()) or "<none>"
            raise ValueError(
                f"unknown serial port {port!r}; declared: {known}"
            )
        return {
            "name":  port,
            "type":  self._serial_types.get(port, "unknown"),
            "roles": dict(self._serial_ports[port]),
            "meta":  dict(self._serial_meta.get(port, {})),
        }

    def serial_port_type(self, port: str) -> str:
        """Return the transceiver type for ``port`` (e.g. ``thvd4431``)."""
        return self.serial_port_info(port)["type"]  # type: ignore[return-value]

    def serial_port_supported_protocols(self, port: str) -> List[str]:
        """
        Return the protocols ``port`` accepts, ordered. For a
        ``fixed_rs232`` port this is ``['isolate', 'rs232']``; for a
        ``thvd4431`` port it includes every mode the part supports.
        """
        t = self.serial_port_type(port)
        return sorted(_TRANSCEIVER_HANDLERS[t].accepts)

    def serial_port_tty(self, port: str) -> str:
        """
        Return the canonical device path an app should ``open()`` for
        ``port``. Prefers the explicit ``tty`` declaration, falling back
        to ``by_path`` (which is itself a stable symlink).
        """
        meta = self.serial_port_info(port)["meta"]
        path = meta.get("tty") or meta.get("by_path")  # type: ignore[union-attr]
        if not path:
            # _discover_serial_ports enforces this; defensive only.
            raise RuntimeError(
                f"serial port {port!r} declares no tty / by_path "
                "(pinmap inconsistent at runtime)"
            )
        return path  # type: ignore[return-value]

    def serial_port_for_tty(self, path: str) -> str:
        """
        Reverse lookup: given any device path the developer happens to
        have (``/dev/ttyS1``, the by-path symlink, an alias symlink),
        return the pinmap port name (``UARTC2``, …).

        Strict: raises ``ValueError`` if no declared port matches. The
        comparison uses ``os.path.realpath`` on both sides, so any
        symlink under any name resolves correctly as long as it
        eventually points at the same kernel device node.
        """
        try:
            wanted = os.path.realpath(path)
        except OSError as exc:
            raise ValueError(
                f"serial_port_for_tty: cannot resolve {path!r}: {exc}"
            ) from exc
        for port, meta in self._serial_meta.items():
            for key in ("tty", "by_path"):
                cand = meta.get(key)
                if not cand:
                    continue
                try:
                    if os.path.realpath(cand) == wanted:
                        return port
                except OSError:
                    continue
        raise ValueError(
            f"{path!r} (-> {wanted!r}) is not bound to any pinmap port; "
            f"declared: {self.list_serial_ports() or '<none>'}"
        )

    # -------- runtime tty <-> port verification --------
    def verify_serial_bindings(self, *, strict: bool = True) -> Dict[str, str]:
        """
        Assert that every port whose pinmap entry declares a ``dt_node``
        actually resolves to that device-tree node via ``/sys/class/tty``.

        This is the missing link between the GPIO-controlled transceiver
        (mode/shut pins) and the kernel's ``/dev/ttySN`` numbering — without
        it, a typo in the pinmap's ``tty`` value would silently re-wire the
        wrong UART to the wrong transceiver.

        Returns ``{port: realpath_of_node}`` for every port that was
        successfully verified. Ports without ``dt_node`` are skipped.

        ``strict=True`` (default) raises ``RuntimeError`` on the first
        mismatch. ``strict=False`` collects and returns
        ``{port: 'ERROR: ...'}`` entries instead so callers can log
        everything at startup.

        Soft-skips silently when:
          * ``/sys/class/tty/<name>`` is absent (e.g. running this code
            on a build host or in CI),
          * the tty's ``device/of_node`` symlink is absent
            (non-DT system).
        """
        import os
        result: Dict[str, str] = {}
        for port, meta in self._serial_meta.items():
            dt_node = meta.get("dt_node")
            tty = meta.get("tty") or meta.get("by_path")
            if not dt_node or not tty:
                continue
            # Resolve the tty to a /sys/class/tty/<name> entry.
            try:
                tty_real = os.path.realpath(tty)
            except OSError:
                continue
            tty_name = os.path.basename(tty_real)
            sys_of = f"/sys/class/tty/{tty_name}/device/of_node"
            if not os.path.exists(sys_of):
                continue  # not a DT system, or tty not yet present
            try:
                of_real = os.path.realpath(sys_of)
            except OSError as exc:
                msg = f"{port}: cannot resolve {sys_of}: {exc}"
                if strict:
                    raise RuntimeError(msg) from exc
                result[port] = f"ERROR: {msg}"
                continue
            # dt_node is declared as the leaf path (e.g.
            # '/bus@f4000/serial@2810000'); accept either an exact tail
            # match against /sys/firmware/devicetree/base/... or against
            # the of_node symlink target itself.
            wanted = dt_node.rstrip("/")
            if of_real.endswith(wanted):
                result[port] = of_real
                continue
            msg = (
                f"{port}: pinmap claims tty={tty!r} is at dt_node={dt_node!r}, "
                f"but {tty_name} resolves to {of_real!r}. "
                "Pinmap and device tree disagree — fix the pinmap or "
                "the .dts before continuing."
            )
            if strict:
                raise RuntimeError(msg)
            result[port] = f"ERROR: {msg}"
        return result

    # -------- modems --------
    def list_modems(self) -> List[str]:
        """Return every modem name declared by the active pinmap."""
        return sorted(self._modems)

    def _resolve_modem(self, modem: Optional[str]) -> Dict[str, object]:
        if not self._modems:
            raise RuntimeError(
                f"{self.NAME}: no modems declared in pinmap"
            )
        if modem is None:
            if len(self._modems) == 1:
                return next(iter(self._modems.values()))
            raise ValueError(
                f"{self.NAME}: multiple modems present "
                f"({', '.join(self.list_modems())}); pass modem=<name>"
            )
        try:
            return self._modems[modem]
        except KeyError as exc:
            known = ", ".join(self.list_modems()) or "<none>"
            raise ValueError(
                f"unknown modem {modem!r}; declared: {known}"
            ) from exc

    def sim_detect_pins(self, modem: Optional[str] = None) -> List[str]:
        """
        Return the SIM-detect input pin names for ``modem`` (or the only
        modem if ``modem`` is None). Suitable to pass to
        :meth:`Board.watch_pins`.
        """
        return list(self._resolve_modem(modem).get("sim_detect", []))  # type: ignore[arg-type]

    def modem_capabilities(self, modem: Optional[str] = None) -> frozenset:
        """
        Return the set of hardware-control roles the pinmap declares for
        ``modem`` (or the only modem if ``modem`` is None).

        Possible members: ``"reset"``, ``"power"``, ``"sim_select"``,
        ``"sim_detect"``. The presence of ``"sim_select"`` is what the WWAN
        FSM uses to decide it must drive SIM switching itself (GPIO-mux
        mode) instead of delegating to ModemManager's ``SetPrimarySimSlot``.
        """
        roles = self._resolve_modem(modem)
        caps = set()
        for role in ("reset", "power", "sim_select"):
            if roles.get(role):
                caps.add(role)
        if roles.get("sim_detect"):
            caps.add("sim_detect")
        return frozenset(caps)

    # -------- semantic helpers --------
    def modem_reset(self, modem: Optional[str] = None) -> None:
        roles = self._resolve_modem(modem)
        self.pulse(roles["reset"], ms=200, asserted=1)  # type: ignore[arg-type]

    def modem_power(self, on: bool, modem: Optional[str] = None) -> None:
        roles = self._resolve_modem(modem)
        pin = roles.get("power")
        if pin is None:
            name = modem or next(iter(self._modems))
            raise RuntimeError(
                f"{self.NAME}: modem {name!r} has no power pin in pinmap"
            )
        # Power pin (e.g. MODEM0_SHUTDOWN_N) follows the standard ``_N``
        # active-low hardware naming: physical line high = run, low =
        # shutdown. vyos.hardware passes physical levels through (no
        # software inversion), so 1 = run / 0 = off matches what a scope
        # would show on the line.
        # The kernel controller register holds direction+value after our
        # libgpiod request is released, so a single set_pin() is enough —
        # the line stays driven at the chosen level until something else
        # reprograms it.
        self.set_pin(pin, 1 if on else 0)  # type: ignore[arg-type]

    def sim_select(self, slot: int, modem: Optional[str] = None) -> None:
        if slot not in (1, 2):
            raise ValueError(f"sim_select: slot must be 1 or 2, got {slot}")
        roles = self._resolve_modem(modem)
        pin = roles.get("sim_select")
        if pin is None:
            name = modem or next(iter(self._modems))
            raise RuntimeError(
                f"{self.NAME}: modem {name!r} has no sim_select pin in pinmap"
            )
        # sim_select low → SIM1, high → SIM2. The kernel GPIO controller
        # retains the level after release, so the slot stays selected with
        # no long-lived process required.
        self.set_pin(pin, 0 if slot == 1 else 1)  # type: ignore[arg-type]

    def sim_select_state(self, modem: Optional[str] = None) -> Optional[int]:
        """Return the slot the SIM mux is currently selecting (1 or 2).

        Reads the ``sim_select`` GPIO line back (low → slot 1, high →
        slot 2).  Returns ``None`` when the modem has no ``sim_select`` pin
        (i.e. not a GPIO-mux board).
        """
        roles = self._resolve_modem(modem)
        pin = roles.get("sim_select")
        if pin is None:
            return None
        return 2 if self.get_pin(pin) else 1  # type: ignore[arg-type]

    def _resolve_modem_stat_prefix(self, modem: Optional[str] = None) -> str:
        """Resolve the pin prefix for RGB modem status LEDs.

        Supports either per-modem naming (e.g. ``MODEM0_STAT_RED``) or
        shared naming (e.g. ``MODEM_STAT_RED``).
        """
        prefixes = []
        for pin_name in self.PINS:
            if not pin_name.endswith("_STAT_RED"):
                continue
            prefix = pin_name[:-len("_STAT_RED")]
            if (f"{prefix}_STAT_GREEN" in self.PINS and
                    f"{prefix}_STAT_BLUE" in self.PINS):
                prefixes.append(prefix)

        if not prefixes:
            raise RuntimeError(
                f"{self.NAME}: no *_STAT_(RED|GREEN|BLUE) modem LED pins declared"
            )

        if modem:
            if modem in prefixes:
                return modem
            base = re.sub(r"\d+$", "", modem)
            if base and base in prefixes:
                return base
            if len(prefixes) == 1:
                return prefixes[0]
            raise RuntimeError(
                f"{self.NAME}: cannot resolve STAT LED prefix for modem {modem!r}; "
                f"available prefixes: {sorted(prefixes)}"
            )

        if len(prefixes) == 1:
            return prefixes[0]
        if "MODEM" in prefixes:
            return "MODEM"
        raise RuntimeError(
            f"{self.NAME}: multiple modem STAT LED prefixes present "
            f"({sorted(prefixes)}); pass modem=<name>"
        )

    def modem_signal_level(self, level: int, modem: Optional[str] = None) -> None:
        """Display modem signal level on RGB STAT LEDs.

        ``level`` is clamped to 0..7 and converted to RGB output by policy.
        The ladder is monotonic and uses a "blue = weak, amber = middling,
        green = good" convention so a strong signal clearly reads "good":
        - 0: all off (no signal)
        - 1..2: blue   (weak / barely usable — cold, but NOT a fault)
        - 3..4: amber  (middling — getting there)
        - 5..7: green  (the strong / "good" zone — reassuring, incl. maximum)

        IMPORTANT — physical-LED constraint that drove this palette:
        with simple on/off GPIO (no PWM) the blue die visually DOMINATES, so
        ANY colour that lights the blue channel together with another channel
        (cyan, magenta, white) reads as plain "blue" on the bench.  The old
        palette put cyan at level 4 and white at level 7, which made a strong
        signal look identical to a weak one.  This ladder therefore only ever
        uses "safe" combinations: pure blue, pure green, or amber (red+green
        with NO blue).  No blue-containing mixes are used, so each zone is
        visually distinct and a strong signal is unambiguous green.
        """
        level = max(0, min(7, int(level)))

        # Safe colours only (never mix blue with another channel — see
        # docstring): pure blue (weak), amber = red+green/no-blue (middling),
        # pure green (good).  Green spans the whole strong zone 5-7 so the
        # maximum still reads green, not a blue-tinted "white".  Add
        # board-specific PWM later for finer within-zone gradients.
        palette = {
            0: (0, 0, 0),  # off    — no signal
            1: (0, 0, 1),  # blue   — barely usable (weakest usable)
            2: (0, 0, 1),  # blue   — very poor
            3: (1, 1, 0),  # amber  — poor (no blue → reads yellow, not blue)
            4: (1, 1, 0),  # amber  — fair (slow-RAT cap lands here)
            5: (0, 1, 0),  # green  — good
            6: (0, 1, 0),  # green  — very good
            7: (0, 1, 0),  # green  — excellent / maximum
        }

        prefix = self._resolve_modem_stat_prefix(modem)
        red_v, green_v, blue_v = palette[level]
        self.set_pin(f"{prefix}_STAT_RED", red_v)
        self.set_pin(f"{prefix}_STAT_GREEN", green_v)
        self.set_pin(f"{prefix}_STAT_BLUE", blue_v)

    def serial_protocol(self, port: str, proto: str,
                        term: Optional[bool] = None,
                        slr: Optional[bool] = None) -> None:
        port = port.upper()
        proto = proto.lower()
        roles = self._serial_ports.get(port)
        if roles is None:
            known = ", ".join(self.list_serial_ports()) or "<none>"
            raise ValueError(
                f"serial_protocol: unknown port {port!r}. "
                f"Ports declared by the active pinmap: {known}"
            )
        ptype = self._serial_types[port]
        handler = _TRANSCEIVER_HANDLERS[ptype]
        if proto not in handler.accepts:
            raise ValueError(
                f"serial_protocol: port {port!r} is {ptype!r}; "
                f"protocol {proto!r} not supported. "
                f"Accepted: {sorted(handler.accepts)}"
            )

        plan, final_shut = handler.plan(proto, term=term, slr=slr)
        shut_pin = roles["shut"]  # presence guaranteed by discovery

        with self._serial_lock(port):
            # 1. Force transceiver into shutdown BEFORE touching any
            #    mode/term/slr pins. Universal across all transceiver
            #    types — boards boot in shutdown and software brings
            #    each port up explicitly here.
            self.set_pin(shut_pin, 0)

            # 2. Let the driver actually disable. set_pin() returns once
            #    the line is latched, so this delay is wall-clock real.
            time.sleep(_SHUT_SETTLE_MS / 1000.0)

            # 3. Program the new mode while the transceiver is off-bus.
            #    Only roles the pinmap actually declared are written.
            for role, value in plan.items():
                pin_name = roles.get(role)
                if pin_name is not None:
                    self.set_pin(pin_name, value)

            # 4. Drive SHUT to its final level (1 for active protocols,
            #    0 for 'isolate').
            self.set_pin(shut_pin, final_shut)


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
    def modem_reset(self, modem=None):           self._fail()
    def modem_power(self, on, modem=None):       self._fail()
    def sim_select(self, slot, modem=None):      self._fail()
    def sim_select_state(self, modem=None):      return None
    def modem_signal_level(self, level, modem=None): self._fail()
    def serial_protocol(self, port, proto, term=None, slr=None):
        self._fail()

    def list_serial_ports(self) -> list:
        return []

    def serial_port_info(self, port):       self._fail()
    def serial_port_tty(self, port):        self._fail()
    def serial_port_for_tty(self, path):    self._fail()
    def serial_port_type(self, port):       self._fail()
    def serial_port_supported_protocols(self, port):  return []

    def verify_serial_bindings(self, *, strict=True):
        return {}

    def list_modems(self) -> list:
        return []

    def sim_detect_pins(self, modem=None) -> list:
        return []

    def modem_capabilities(self, modem=None) -> frozenset:
        return frozenset()


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
    # Pinmap may optionally override the bank-label table (e.g. a board
    # with a different SoC). Default to IgosBoard.BANK_LABELS (AM64x).
    bank_labels = getattr(pinmap, "BANK_LABELS", None)
    if bank_labels:
        board.BANK_LABELS = dict(bank_labels)
    # Pinmap may optionally declare ports explicitly (non-standard suffixes,
    # tty/by_path metadata, friendly aliases, transceiver type).
    explicit_ports = getattr(pinmap, "SERIAL_PORTS", None)
    (board._serial_ports,
     board._serial_meta,
     board._serial_types) = _discover_serial_ports(pins, explicit_ports)
    # Same idea for modems.
    explicit_modems = getattr(pinmap, "MODEMS", None)
    board._modems = _discover_modems(pins, explicit_modems)
    return board


BOARD: Board = _build_board()
