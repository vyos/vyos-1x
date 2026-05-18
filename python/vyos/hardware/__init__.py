"""
Hardware-platform abstraction for fork-only board support (GPIO, serial
muxes, modem power control, etc.).

This package ships in the main ``vyos-1x`` package and contains only
hardware-AGNOSTIC code:

  * :mod:`vyos.hardware.api`   — stable facade for callers
  * :mod:`vyos.hardware.base`  — ``Pin`` dataclass + libgpiod-backed ``Board``
  * :mod:`vyos.hardware.board` — semantic helpers (modem reset, SIM, serial)

The pin map (:mod:`vyos.hardware.pinmap`) is NOT shipped here. It is
overlaid onto the image at build time by vyos-build, per hardware flavor
(see ``vyos-build/data/build-flavors/igos-*``). On images without an
overlay, ``BOARD`` is a stub that raises a clear error on first use, so
this module remains importable everywhere.

Typical caller usage::

    from vyos.hardware import api as hw
    hw.modem_reset()
    hw.set_pin("UARTC0_MODE0", 1)
"""

from vyos.hardware.board import BOARD  # noqa: F401
