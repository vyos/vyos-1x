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

import sys

from vyos.hardware import api as hw


def _die(msg: str, code: int = 1) -> None:
    print(f'error: {msg}', file=sys.stderr)
    sys.exit(code)


# --- show -------------------------------------------------------------------

def show_serial(args) -> None:
    ports = sorted(hw.list_serial_ports())
    if not ports:
        print('No serial ports declared by the active pinmap.')
        return
    fmt = '{:<16} {:<14} {:<22} {}'
    print(fmt.format('PORT', 'TYPE', 'TTY', 'PROTOCOLS'))
    for p in ports:
        info = hw.serial_port_info(p)
        tty = info['meta'].get('tty') or info['meta'].get('by_path') or '-'
        protos = ','.join(hw.serial_port_supported_protocols(p))
        print(fmt.format(p, info['type'], tty, protos))


def show_modem(args) -> None:
    modems = sorted(hw.list_modems())
    if not modems:
        print('No modems declared by the active pinmap.')
        return
    for m in modems:
        sims = hw.sim_detect_pins(modem=m)
        print(f'{m}  sim-detect-pins: {", ".join(sims) or "<none>"}')


def show_pin(args) -> None:
    name = getattr(args, 'name', None)
    # api.py intentionally doesn't expose the raw pin table; go through BOARD.
    from vyos.hardware.board import BOARD
    all_names = sorted(BOARD.PINS) if getattr(BOARD, 'PINS', None) else []
    if not all_names:
        print('No pins declared by the active pinmap.')
        return

    # Build a pin -> "owner" reverse map so each row can show which
    # logical device the pin belongs to (e.g. UARTC2/ttyS2, MODEM0).
    owner = _build_pin_owner_map(BOARD)

    if name:
        if name not in all_names:
            _die(f'unknown pin {name!r}; try `show pin` for the full list')
        own = owner.get(name, '')
        suffix = f'  [{own}]' if own else ''
        print(f'{name} = {hw.get_pin(name)}{suffix}')
        return

    fmt = '{:<28} {:>5}  {}'
    print(fmt.format('PIN', 'VALUE', 'OWNER'))
    for n in all_names:
        try:
            v = hw.get_pin(n)
        except Exception as exc:  # noqa: BLE001 -- diagnostic tool
            v = f'err:{exc}'
        print(fmt.format(n, v, owner.get(n, '')))


def _build_pin_owner_map(board) -> dict:
    """
    Return ``{pin_name: 'owner_label'}`` so every pin can be cross-
    referenced with the logical device it belongs to:

      * Serial-port pins  -> ``UARTC2 (/dev/ttyS2)`` (tty path appended
        when the pinmap declares one).
      * Modem pins        -> ``MODEM0``.

    Pins that don't belong to any discovered serial port or modem get
    no owner label.
    """
    owner: dict = {}

    # Serial ports: roles map {role -> pin_name}; metadata has the tty.
    serial_ports = getattr(board, '_serial_ports', {}) or {}
    serial_meta  = getattr(board, '_serial_meta',  {}) or {}
    for port, roles in serial_ports.items():
        meta = serial_meta.get(port, {})
        tty = meta.get('tty') or meta.get('by_path') or ''
        label = f'{port} ({tty})' if tty else port
        for pin_name in roles.values():
            if pin_name:
                owner[pin_name] = label

    # Modems: roles map {role -> pin_name | [pin_names]}.
    modems = getattr(board, '_modems', {}) or {}
    for modem, roles in modems.items():
        for v in roles.values():
            if isinstance(v, (list, tuple, set)):
                for pin_name in v:
                    owner.setdefault(pin_name, modem)
            elif v:
                owner.setdefault(v, modem)

    # Generic per-device grouping for pins not already owned by a
    # serial port or modem. Any pin whose name begins with a known
    # device prefix followed by an instance index is attributed to
    # that device. Pinmap convention is ``<FAMILY><N>_…`` so WiFi
    # appears as WIFI0_PD_N, WIFI1_RESET_N, etc. ``MODEM`` is also
    # listed here so that modem pins which don't match one of the
    # known modem role suffixes (reset / power / sim_select /
    # sim_detect) — e.g. MODEM0_PWR_IND, MODEM0_WAKE — still get
    # attributed to their modem rather than showing a blank OWNER.
    # Adding another peripheral family is a one-line change to
    # ``device_prefixes``.
    import re
    device_prefixes = ('WIFI', 'MODEM')
    pattern = re.compile(
        r'^(' + '|'.join(device_prefixes) + r')(\d+)_'
    )
    for pin_name in board.PINS:
        if pin_name in owner:
            continue
        m = pattern.match(pin_name)
        if m:
            owner[pin_name] = f'{m.group(1)}{m.group(2)}'

    return owner


# --- serial -----------------------------------------------------------------

def _resolve_port(arg: str) -> str:
    """
    Accept either a pinmap port name (``UARTC2``) or any device path
    that resolves to a declared port's tty (``/dev/ttyS2``,
    ``/dev/igos/uartc2``, an app-installed alias symlink, …) and return
    the canonical pinmap port name.
    """
    s = arg.strip()
    # Path-like: hand to the reverse lookup so any symlink chain works.
    if s.startswith('/'):
        try:
            return hw.serial_port_for_tty(s)
        except (ValueError, RuntimeError) as exc:
            _die(str(exc))
    # Bare name: uppercase and validate against the declared ports.
    name = s.upper()
    if name not in hw.list_serial_ports():
        _die(f'unknown serial port {arg!r}; '
             f'declared: {", ".join(sorted(hw.list_serial_ports())) or "<none>"}')
    return name


def serial_protocol(args) -> None:
    term = _tristate(args.termination)
    slr  = _tristate(args.slew_rate)
    port = _resolve_port(args.port)
    try:
        hw.serial_protocol(port, args.protocol, term=term, slr=slr)
    except (ValueError, RuntimeError) as exc:
        _die(str(exc))
    tty = hw.serial_port_tty(port)
    print(f'OK: {port} ({tty}) -> {args.protocol}'
          + (f' term={"on" if term else "off"}' if term is not None else '')
          + (f' slr={"on" if slr else "off"}'   if slr  is not None else ''))


def _tristate(v):
    if v is None:
        return None
    s = str(v).lower()
    if s in ('on', 'true', '1', 'enable', 'enabled'):
        return True
    if s in ('off', 'false', '0', 'disable', 'disabled'):
        return False
    _die(f'expected on/off, got {v!r}')


# --- modem ------------------------------------------------------------------

def modem_reset(args) -> None:
    modem = args.modem.upper()
    try:
        hw.modem_reset(modem=modem)
    except (ValueError, RuntimeError) as exc:
        _die(str(exc))
    print(f'OK: {modem} reset pulse issued')


def modem_power(args) -> None:
    on = _tristate(args.state)
    modem = args.modem.upper()
    try:
        hw.modem_power(on, modem=modem)
    except (ValueError, RuntimeError) as exc:
        _die(str(exc))
    print(f'OK: {modem} power {"on" if on else "off"}')


def modem_sim(args) -> None:
    modem = args.modem.upper()
    try:
        hw.sim_select(int(args.slot), modem=modem)
    except (ValueError, RuntimeError) as exc:
        _die(str(exc))
    print(f'OK: {modem} sim slot {args.slot}')


# --- raw pin ----------------------------------------------------------------

def pin_set(args) -> None:
    try:
        hw.set_pin(args.name, int(args.value))
    except (ValueError, RuntimeError) as exc:
        _die(str(exc))
    print(f'OK: {args.name} = {args.value}')


def pin_pulse(args) -> None:
    try:
        hw.pulse(args.name, ms=int(args.ms), asserted=int(args.asserted))
    except (ValueError, RuntimeError) as exc:
        _die(str(exc))
    print(f'OK: pulsed {args.name} for {args.ms} ms')


# --- arg dispatch -----------------------------------------------------------

def main() -> None:
    import argparse
    p = argparse.ArgumentParser(prog='test_hardware')
    sub = p.add_subparsers(dest='cmd', required=True)

    # show ...
    s = sub.add_parser('show_serial')
    s.set_defaults(fn=show_serial)
    s = sub.add_parser('show_modem')
    s.set_defaults(fn=show_modem)
    s = sub.add_parser('show_pin')
    s.set_defaults(fn=show_pin)
    s.add_argument('--name', default=None)

    # serial UARTC2 protocol rs485h [term ...] [slr ...]
    s = sub.add_parser('serial_protocol')
    s.set_defaults(fn=serial_protocol)
    s.add_argument('--port', required=True)
    s.add_argument('--protocol', required=True)
    s.add_argument('--termination', default=None)
    s.add_argument('--slew-rate', dest='slew_rate', default=None)

    # modem MODEM0 ...
    s = sub.add_parser('modem_reset')
    s.set_defaults(fn=modem_reset)
    s.add_argument('--modem', required=True)

    s = sub.add_parser('modem_power')
    s.set_defaults(fn=modem_power)
    s.add_argument('--modem', required=True)
    s.add_argument('--state', required=True)

    s = sub.add_parser('modem_sim')
    s.set_defaults(fn=modem_sim)
    s.add_argument('--modem', required=True)
    s.add_argument('--slot', required=True)

    # pin <NAME> set <0|1> | pulse [...]
    s = sub.add_parser('pin_set')
    s.set_defaults(fn=pin_set)
    s.add_argument('--name', required=True)
    s.add_argument('--value', required=True)

    s = sub.add_parser('pin_pulse')
    s.set_defaults(fn=pin_pulse)
    s.add_argument('--name', required=True)
    s.add_argument('--ms', default='200')
    s.add_argument('--asserted', default='1')

    args = p.parse_args()
    args.fn(args)


if __name__ == '__main__':
    main()
