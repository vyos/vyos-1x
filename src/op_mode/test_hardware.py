#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Operational diagnostics for board hardware: serial transceivers, modems,
# and raw GPIO pins. Intended for bench / field bring-up — NOT to be called
# by conf-mode. Lives behind ``test hardware ...`` so it's clearly out-of-
# band from the configured state.
#
# Examples
# --------
#   test hardware show serial
#   test hardware show modem
#   test hardware show pin
#   test hardware show pin UARTC2_SHUT_N
#   test hardware serial UARTC2 protocol rs485h
#   test hardware serial UARTC2 protocol rs485h termination on
#   test hardware modem MODEM0 reset
#   test hardware modem MODEM0 power off
#   test hardware modem MODEM0 sim 2
#   test hardware pin UARTC2_MODE0 set 1
#   test hardware pin UARTC2_SHUT_N pulse

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
    if name:
        if name not in all_names:
            _die(f'unknown pin {name!r}; try `show pin` for the full list')
        print(f'{name} = {hw.get_pin(name)}')
        return
    fmt = '{:<28} {:>5}'
    print(fmt.format('PIN', 'VALUE'))
    for n in all_names:
        try:
            v = hw.get_pin(n)
        except Exception as exc:  # noqa: BLE001 -- diagnostic tool
            v = f'err:{exc}'
        print(fmt.format(n, v))


# --- serial -----------------------------------------------------------------

def serial_protocol(args) -> None:
    term = _tristate(args.termination)
    slr  = _tristate(args.slew_rate)
    port = args.port.upper()
    try:
        hw.serial_protocol(port, args.protocol, term=term, slr=slr)
    except (ValueError, RuntimeError) as exc:
        _die(str(exc))
    print(f'OK: {port} -> {args.protocol}'
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


def pin_hold(args) -> None:
    try:
        hw.hold_pin(args.name, int(args.value))
    except (ValueError, RuntimeError, PermissionError) as exc:
        _die(str(exc))
    print(f'OK: holding {args.name} at {args.value}')


def pin_release(args) -> None:
    try:
        released = hw.release_pin(args.name)
    except (ValueError, RuntimeError, KeyError) as exc:
        _die(str(exc))
    print(f'OK: {args.name} released' if released
          else f'{args.name}: no holder active')


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

    s = sub.add_parser('pin_hold')
    s.set_defaults(fn=pin_hold)
    s.add_argument('--name', required=True)
    s.add_argument('--value', required=True)

    s = sub.add_parser('pin_release')
    s.set_defaults(fn=pin_release)
    s.add_argument('--name', required=True)

    args = p.parse_args()
    args.fn(args)


if __name__ == '__main__':
    main()
