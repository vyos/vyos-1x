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

"""
SIM-slot control strategy for the WWAN FSM.

Two hardware models exist, and the FSM must behave identically at the
*policy* level (failover, failback, cooldowns) regardless of which one a
given board uses.  Only the *mechanism* differs, and that mechanism is
isolated behind :class:`SimController`:

* **ModemManager-managed** (``ModemManagedSimController``) — the modem
  exposes both SIM slots to ModemManager.  Presence is read from the
  ``SimSlots`` D-Bus property and the active slot is changed with
  ``SetPrimarySimSlot``.  This is the historical behavior; the controller
  is a thin pass-through to the existing FSM methods so nothing changes.

* **GPIO-mux** (``GpioMuxSimController``) — the modem supports two SIMs but
  exposes only ONE SIM interface; an external GPIO mux selects which
  physical slot is wired to it.  The modem cannot see the unselected slot
  and cannot detect insertion, so:

  - SIM presence for BOTH slots comes from board ``SIM_DETECT`` GPIO lines
    (ModemManager structurally cannot answer "is the other slot
    populated?").
  - Switching the active slot drives the ``sim_select`` GPIO and then
    reboots the modem (the modem only re-reads the SIM at boot).
  - Insertion is observed via edge-triggered, debounced GPIO events
    (``watch_sim_detect``) rather than any ModemManager signal.

The board capability ``"sim_select"`` (from the active pinmap) is the sole
discriminator: present → GPIO-mux, absent → ModemManager-managed.

The controller holds a back-reference to the owning FSM so the
ModemManager-managed implementation can reuse the FSM's existing,
well-tested SimSlots logic verbatim, and so the GPIO implementation can
schedule SIM-detect events back onto the FSM's asyncio loop.
"""

import asyncio
import os
import threading

from vyos.utils.wwan.wwan_logging import setup_logging

logger = setup_logging(__name__, "wwan-fsm")


# Detect-pin → slot mapping convention (confirmed against hardware):
#   <MODEM>_SIM_DETECT_0 → slot 1
#   <MODEM>_SIM_DETECT_1 → slot 2
# The pinmap returns the detect pins as a sorted list with no slot
# semantics, so the mapping is applied here.
_DETECT_SUFFIX_TO_SLOT = {
    "_SIM_DETECT_0": 1,
    "_SIM_DETECT_1": 2,
}


class SimController:
    """Base strategy: ModemManager-managed behavior (historical default).

    Every method is safe to call regardless of FSM state.  The base class
    IS the ModemManager-managed implementation so callers that never touch
    GPIO hardware keep working unchanged.
    """

    mode = "modem-managed"
    is_gpio_mux = False

    def __init__(self, fsm):
        self.fsm = fsm

    # --- presence (read) -------------------------------------------------
    async def is_present(self, slot: int) -> bool:
        """Return True if a SIM is present in ``slot``.

        Delegates to the FSM's existing ModemManager ``SimSlots`` probe.
        """
        return await self.fsm._check_primary_sim_available(slot)

    async def present_slots(self) -> set:
        """Return the set of slots that currently have a SIM present."""
        present = set()
        for slot in self._configured_slots():
            try:
                if await self.is_present(slot):
                    present.add(slot)
            except Exception:
                pass
        return present

    # --- switch ----------------------------------------------------------
    async def switch_to(self, slot: int) -> bool:
        """Make ``slot`` the active SIM.

        Base implementation is unused: the FSM's ``_sim_switch_hardware``
        keeps issuing ``SetPrimarySimSlot`` directly in ModemManager-managed
        mode.  Provided for interface completeness.
        """
        iface = self.fsm.proxy.get_interface(
            "org.freedesktop.ModemManager1.Modem")
        await iface.call_set_primary_sim_slot(slot)
        return True

    async def force_select_slot(self, slot: int) -> bool:
        """Best-effort explicit slot selection without implying reboot.

        ModemManager-managed mode has no external mux line to force, so this
        is a no-op that reports success.
        """
        return True

    async def current_selected_slot(self):
        """Return the slot currently wired to the modem, or None.

        Base (ModemManager-managed) has no external mux, so this returns
        None and callers use ModemManager's ``PrimarySimSlot`` instead.
        """
        return None

    # --- events / lifecycle ---------------------------------------------
    async def sample_initial(self) -> None:
        """No-op for ModemManager-managed modems."""
        return None

    async def refresh_presence(self, attempts: int = 1, delay: float = 0.0) -> None:
        """Best-effort refresh of SIM presence telemetry.

        Base implementation delegates to ``sample_initial`` so callers can
        safely request a refresh without branching on controller type.
        """
        await self.sample_initial()

    def start_watch(self) -> None:
        """No-op for ModemManager-managed modems."""
        return None

    def stop_watch(self) -> None:
        """No-op for ModemManager-managed modems."""
        return None

    # --- helpers ---------------------------------------------------------
    def _configured_slots(self):
        cfg = self.fsm.config or {}
        slots = [s.get("slot") for s in cfg.get("sim_slots", [])
                 if s.get("slot")]
        return slots or [1, 2]

    # Presence-confidence helpers (GPIO-mux uses SIM_DETECT; MM-managed
    # presence probes are authoritative by construction).
    def slot_presence_known(self, slot: int) -> bool:
        return True

    def has_reliable_presence(self) -> bool:
        return True


class GpioMuxSimController(SimController):
    """GPIO-mux SIM control: presence, switch+reboot, and detect watching.

    SIM presence is maintained in ``self._present`` ({slot: bool}), seeded
    once by :meth:`sample_initial` (edges only report *changes*) and kept
    current by a background :meth:`watch_sim_detect` thread.  All presence
    reads are answered from this model, which is the single source of truth
    for the whole failover/failback policy layer in this mode.
    """

    mode = "gpio-mux"
    is_gpio_mux = True

    def __init__(self, fsm, modem_name: str, hw_api):
        super().__init__(fsm)
        self.modem_name = modem_name
        self._hw = hw_api
        # slot -> bool present
        self._present = {}
        # slots with at least one successful sample/event update
        self._known_slots = set()
        # detect pin name -> slot
        self._pin_slot = {}
        self._watch_thread = None
        self._stop_r = None
        self._stop_w = None
        self._loop = None
        self._resolve_detect_pins()

    def _resolve_detect_pins(self):
        """Map this modem's SIM_DETECT pins to slot numbers."""
        try:
            pins = self._hw.sim_detect_pins(self.modem_name)
        except Exception as e:
            logger.warning("Could not read SIM-detect pins for GPIO-mux modem",
                           extra={'interface_number': self.fsm.interface_number,
                                  'modem': self.modem_name, 'error': str(e)})
            pins = []
        for pin in pins:
            slot = None
            for suffix, s in _DETECT_SUFFIX_TO_SLOT.items():
                if pin.endswith(suffix):
                    slot = s
                    break
            if slot is None:
                logger.warning("Unrecognized SIM-detect pin suffix — ignoring",
                               extra={'interface_number': self.fsm.interface_number,
                                      'pin': pin})
                continue
            self._pin_slot[pin] = slot
        logger.info("GPIO-mux SIM-detect pins resolved",
                    extra={'interface_number': self.fsm.interface_number,
                           'modem': self.modem_name,
                           'pin_slot': dict(self._pin_slot)})

    # --- presence --------------------------------------------------------
    async def is_present(self, slot: int) -> bool:
        return bool(self._present.get(slot, False))

    async def present_slots(self) -> set:
        return {s for s, present in self._present.items() if present}

    async def sample_initial(self) -> None:
        """Seed the presence model with detect-line reads.

        Edge events only report *changes*, so without this initial sample
        the FSM would be blind to whatever SIMs are already inserted at
        startup until one is physically moved.
        """
        await self.refresh_presence(attempts=3, delay=0.2)

    async def refresh_presence(self, attempts: int = 1, delay: float = 0.0) -> None:
        """Re-sample SIM_DETECT pins with retries.

        GPIO access can fail transiently during early boot or while GPIO
        consumers settle. Retrying avoids leaving slots permanently
        "unknown" when both SIMs were physically stable all along.
        """
        attempts = max(1, int(attempts))
        delay = max(0.0, float(delay))

        last_errors = {}
        for attempt in range(1, attempts + 1):
            any_success = False
            for pin, slot in self._pin_slot.items():
                try:
                    level = await asyncio.to_thread(self._hw.get_pin, pin)
                    self._present[slot] = bool(level)
                    self._known_slots.add(slot)
                    any_success = True
                    last_errors.pop(pin, None)
                except Exception as e:
                    last_errors[pin] = str(e)
                    self._present.setdefault(slot, False)

            if any_success and len(self._known_slots) == len(self._pin_slot):
                break

            if attempt < attempts and delay > 0:
                await asyncio.sleep(delay)

        if last_errors:
            for pin, error in last_errors.items():
                slot = self._pin_slot.get(pin)
                logger.warning("SIM-detect sample failed for pin",
                               extra={'interface_number': self.fsm.interface_number,
                                      'pin': pin,
                                      'slot': slot,
                                      'attempts': attempts,
                                      'error': error})

        logger.info("GPIO-mux initial SIM presence sampled",
                    extra={'interface_number': self.fsm.interface_number,
                           'present': dict(self._present),
                           'known_slots': sorted(self._known_slots),
                           'attempts': attempts})

    # --- switch ----------------------------------------------------------
    async def switch_to(self, slot: int) -> bool:
        """Drive the mux to ``slot`` and reboot the modem to enumerate it.

        The reboot uses the FSM's existing escalation ladder
        (``modem_reset``): orderly ModemManager disable+reset first, then
        the board GPIO ``UNCOND_RESET`` pulse, then the nuclear option.
        This is the only place a reboot is issued on a SIM becoming active.
        """
        mux_before = None
        try:
            mux_before = await self.current_selected_slot()
        except Exception:
            mux_before = None

        logger.info("GPIO-mux SIM switch start",
                    extra={'interface_number': self.fsm.interface_number,
                           'modem': self.modem_name,
                           'from_slot': mux_before,
                           'target_slot': slot})
        # 1. Select the slot on the mux (kernel GPIO controller retains the
        #    level after the libgpiod request is released).
        await asyncio.to_thread(self._hw.sim_select, slot, self.modem_name)

        mux_after_select = None
        try:
            mux_after_select = await self.current_selected_slot()
        except Exception:
            mux_after_select = None

        # 1.5 Allow the external mux and SIM rails to settle before reset.
        # Some boards/modems sample the SIM very early during reboot; a short
        # guard avoids racing the line transition.
        settle_ms = 250
        try:
            if self.fsm.config:
                settle_ms = int(self.fsm.config.get('sim_switch_settle_ms', settle_ms))
        except (TypeError, ValueError):
            settle_ms = 250
        settle_ms = max(0, min(settle_ms, 5000))
        if settle_ms > 0:
            await asyncio.sleep(settle_ms / 1000.0)

        # 2. Reboot the modem so it re-reads the now-selected SIM.  Reuse the
        #    FSM's reset ladder (orderly mmcli reset → board GPIO → nuclear).
        from vyos.utils.wwan.interfaces_wwan_util import modem_reset
        ok = await modem_reset(self.fsm.interface_number)

        logger.info("GPIO-mux SIM switch summary",
                    extra={'interface_number': self.fsm.interface_number,
                           'modem': self.modem_name,
                           'from_slot': mux_before,
                           'target_slot': slot,
                           'mux_after_select': mux_after_select,
                           'settle_ms': settle_ms,
                           'reset_success': ok})

        if not ok:
            logger.warning("GPIO-mux modem reboot after SIM select reported "
                           "no working reset method",
                           extra={'interface_number': self.fsm.interface_number,
                                  'target_slot': slot})
        return ok

    async def force_select_slot(self, slot: int) -> bool:
        """Force the mux line to ``slot`` without rebooting the modem.

        Used during boot-time deterministic setup while the modem is disabled,
        so the selected slot is guaranteed before the modem is enabled.
        """
        await asyncio.to_thread(self._hw.sim_select, slot, self.modem_name)
        return True

    async def current_selected_slot(self):
        """Return the slot the mux currently selects (1 or 2), or None."""
        try:
            return await asyncio.to_thread(
                self._hw.sim_select_state, self.modem_name)
        except Exception as e:
            logger.debug("Could not read sim_select state",
                         extra={'interface_number': self.fsm.interface_number,
                                'error': str(e)})
            return None

    def slot_presence_known(self, slot: int) -> bool:
        return slot in self._known_slots

    def has_reliable_presence(self) -> bool:
        return bool(self._known_slots)

    # --- detect watcher --------------------------------------------------
    def start_watch(self) -> None:
        """Spawn the background SIM-detect watcher thread.

        The watcher blocks in libgpiod edge polling (kernel hardware
        debounce + userspace settle window) and pushes each debounced
        INSERTED/REMOVED event onto the FSM's asyncio loop.
        """
        if not self._pin_slot:
            logger.info("GPIO-mux has no SIM-detect pins — watcher not started",
                        extra={'interface_number': self.fsm.interface_number})
            return
        if self._watch_thread is not None:
            return
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None
        self._stop_r, self._stop_w = os.pipe()
        self._watch_thread = threading.Thread(
            target=self._watch_run, name=f"wwan{self.fsm.interface_number}-simdetect",
            daemon=True)
        self._watch_thread.start()
        logger.info("GPIO-mux SIM-detect watcher started",
                    extra={'interface_number': self.fsm.interface_number,
                           'modem': self.modem_name})

    def stop_watch(self) -> None:
        """Stop the watcher thread and release its GPIO requests."""
        if self._stop_w is not None:
            try:
                os.write(self._stop_w, b"x")
            except OSError:
                pass
        thread = self._watch_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=3)
        self._watch_thread = None
        for fd in (self._stop_r, self._stop_w):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
        self._stop_r = self._stop_w = None

    def _watch_run(self):
        """Thread body: yield debounced detect events to the FSM loop."""
        try:
            for pin_name, event, _ts in self._hw.watch_sim_detect(
                    self.modem_name, stop_fd=self._stop_r):
                slot = self._pin_slot.get(pin_name)
                if slot is None:
                    continue
                present = (event == "INSERTED")
                # Update the presence model from the watcher thread.  Dict
                # item assignment is atomic under CPython, and the FSM only
                # ever reads this map, so no lock is needed.
                self._present[slot] = present
                self._known_slots.add(slot)
                logger.info("GPIO-mux SIM-detect event",
                            extra={'interface_number': self.fsm.interface_number,
                                   'slot': slot, 'event': event})
                if self._loop is not None:
                    self._loop.call_soon_threadsafe(
                        self.fsm._on_sim_detect_event, slot, present)
        except Exception as e:
            logger.warning("GPIO-mux SIM-detect watcher exited with error",
                           extra={'interface_number': self.fsm.interface_number,
                                  'error': str(e)})


def make_sim_controller(fsm) -> SimController:
    """Build the appropriate SimController for ``fsm``'s modem.

    Resolution is purely capability-driven from the active pinmap: if the
    board declares a ``sim_select`` GPIO for this modem, the board uses an
    external SIM mux and the FSM must drive switching itself (GPIO-mux);
    otherwise the modem exposes both slots to ModemManager (managed mode).

    Never raises — any error (no pinmap overlay, generic cloud image,
    libgpiod missing, modem not declared) falls back to the safe
    ModemManager-managed default.
    """
    try:
        from vyos.hardware import api as hw_api
        modem_name = hw_api.wwan_to_modem(f"wwan{fsm.interface_number}")
        caps = hw_api.modem_capabilities(modem_name)
        if "sim_select" in caps:
            logger.info("Using GPIO-mux SIM controller (pinmap declares "
                        "sim_select)",
                        extra={'interface_number': fsm.interface_number,
                               'modem': modem_name,
                               'capabilities': sorted(caps)})
            return GpioMuxSimController(fsm, modem_name, hw_api)
        logger.info("Using ModemManager-managed SIM controller",
                    extra={'interface_number': fsm.interface_number,
                           'modem': modem_name,
                           'capabilities': sorted(caps)})
    except Exception as e:
        logger.info("SIM controller capability probe failed — defaulting to "
                    "ModemManager-managed",
                    extra={'interface_number': fsm.interface_number,
                           'error': str(e)})
    return SimController(fsm)
