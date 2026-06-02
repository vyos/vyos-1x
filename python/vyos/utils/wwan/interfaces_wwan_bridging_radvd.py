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

from __future__ import annotations

import asyncio
import logging
import os
import signal
from pathlib import Path
from typing import Optional, Sequence

logger = logging.getLogger(__name__)

RUN_DIR = Path('/run/wwan')
RADVD = '/usr/sbin/radvd'

# Defaults used when the carrier RA lifetimes are not surfaced to the FSM.
# Kept short so SLAAC clients renumber quickly if we ever do miss a
# prefix change.  Operators do not configure these — they are not knobs.
DEFAULT_PREFERRED_LIFETIME = 1800   # 30 min
DEFAULT_VALID_LIFETIME = 3600       # 60 min
DEPRECATE_VALID_LIFETIME = 30       # used when deprecating the previous prefix


class BridgingRadvdManager:
    """Owns a scoped radvd instance for one wwan FSM's bridged LAN.

    Lifecycle:
        apply(lan, prefix, plen, ...) — write conf, start or SIGHUP
        deprecate(lan, prev_prefix, prev_plen) — one-shot conf advertising
            preferred_lft=0 valid_lft=DEPRECATE_VALID_LIFETIME so SLAAC
            clients drop the old prefix before we install the new one
        stop() — SIGTERM the daemon and remove conf/pid

    All state lives in the run dir under interface-scoped filenames so
    multiple WWAN FSMs do not collide.
    """

    def __init__(self, interface_number: int):
        self.interface_number = interface_number
        self._wwan = f'wwan{interface_number}'
        self._last_lan: Optional[str] = None
        self._last_prefix: Optional[str] = None
        self._last_plen: Optional[int] = None
        self._log_extra = {'interface_number': interface_number}
        RUN_DIR.mkdir(parents=True, exist_ok=True)

    # ── path helpers ───────────────────────────────────────────────────

    def _conf_path(self) -> Path:
        return RUN_DIR / f'bridging-radvd-{self._wwan}.conf'

    def _pid_path(self) -> Path:
        return RUN_DIR / f'bridging-radvd-{self._wwan}.pid'

    # ── public API ─────────────────────────────────────────────────────

    async def apply(self,
                    lan: str,
                    prefix: str,
                    plen: int,
                    dns_servers: Optional[Sequence[str]] = None,
                    preferred_lft: int = DEFAULT_PREFERRED_LIFETIME,
                    valid_lft: int = DEFAULT_VALID_LIFETIME) -> None:
        """Write conf and start/reload radvd to advertise prefix on lan.

        If the LAN interface name changed since last apply, a hard restart
        is performed — radvd's SIGHUP path does not handle interface-name
        swaps cleanly.
        """
        if not lan or not prefix or not plen:
            return

        force_restart = (
            self._last_lan is not None and self._last_lan != lan
        )
        self._write_conf(lan, prefix, plen, dns_servers or (),
                         preferred_lft=preferred_lft,
                         valid_lft=valid_lft)
        await self._start_or_reload(force_restart=force_restart)

        self._last_lan = lan
        self._last_prefix = prefix
        self._last_plen = plen

    async def deprecate_previous(self) -> None:
        """One-shot RA burst advertising preferred_lft=0 on the previous prefix.

        Triggers SLAAC clients to mark the old global address deprecated so
        they prefer the soon-to-arrive new prefix.  Sleeps briefly to let
        radvd emit at least one RA before the caller overwrites the conf.
        """
        if not self._last_lan or not self._last_prefix or not self._last_plen:
            return

        self._write_conf(
            self._last_lan, self._last_prefix, self._last_plen, (),
            preferred_lft=0,
            valid_lft=DEPRECATE_VALID_LIFETIME,
        )
        await self._start_or_reload(force_restart=False)

        # Let radvd send at least one unsolicited RA (MinDelayBetweenRAs
        # is ~3 s by default but radvd usually emits within ~1 s on HUP).
        await asyncio.sleep(1.5)

    async def stop(self) -> None:
        """Stop radvd and remove its conf/pid files."""
        pid = self._read_pid()
        if pid and self._pid_alive(pid):
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            for _ in range(20):
                if not self._pid_alive(pid):
                    break
                await asyncio.sleep(0.1)
            else:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            logger.info("bridging-radvd: stopped pid=%s", pid,
                        extra=self._log_extra)

        for p in (self._pid_path(), self._conf_path()):
            try:
                p.unlink()
            except FileNotFoundError:
                pass

        self._last_lan = None
        self._last_prefix = None
        self._last_plen = None

    # ── conf rendering ─────────────────────────────────────────────────

    def _write_conf(self,
                    lan: str,
                    prefix: str,
                    plen: int,
                    dns_servers: Sequence[str],
                    preferred_lft: int,
                    valid_lft: int) -> None:
        """Render a minimal SLAAC+RDNSS radvd.conf for one interface."""
        # Clamp: valid must be >= preferred per RFC 4861.
        if preferred_lft > valid_lft:
            preferred_lft = valid_lft

        rdnss_block = ''
        if dns_servers:
            rdnss_block = (
                '    RDNSS ' + ' '.join(dns_servers) + ' {\n'
                f'        AdvRDNSSLifetime {valid_lft};\n'
                '    };\n'
            )

        body = (
            f'# FSM-managed — do not edit; rewritten on every prefix change.\n'
            f'# Generated for {self._wwan} → {lan}\n'
            f'interface {lan}\n'
            '{\n'
            '    AdvSendAdvert on;\n'
            '    MinRtrAdvInterval 3;\n'
            '    MaxRtrAdvInterval 10;\n'
            '    AdvManagedFlag off;\n'
            '    AdvOtherConfigFlag off;\n'
            '    AdvDefaultLifetime 60;\n'
            f'    prefix {prefix}/{plen}\n'
            '    {\n'
            '        AdvOnLink on;\n'
            '        AdvAutonomous on;\n'
            '        AdvRouterAddr on;\n'
            f'        AdvPreferredLifetime {preferred_lft};\n'
            f'        AdvValidLifetime {valid_lft};\n'
            '    };\n'
            f'{rdnss_block}'
            '};\n'
        )
        self._conf_path().write_text(body)
        logger.debug("bridging-radvd: wrote %s", self._conf_path(),
                     extra=self._log_extra)

    # ── process management ─────────────────────────────────────────────

    async def _start_or_reload(self, force_restart: bool) -> None:
        pid = self._read_pid()

        if force_restart and pid and self._pid_alive(pid):
            logger.info("bridging-radvd: interface changed — restarting pid=%s",
                        pid, extra=self._log_extra)
            await self.stop()
            pid = None

        if pid and self._pid_alive(pid):
            try:
                os.kill(pid, signal.SIGHUP)
                logger.info("bridging-radvd: SIGHUP pid=%s", pid,
                            extra=self._log_extra)
            except ProcessLookupError:
                pid = None

        if not pid or not self._pid_alive(pid):
            await self._spawn()

    async def _spawn(self) -> None:
        """Spawn radvd as a daemon writing its pid to our pidfile."""
        # radvd: --config, --pidfile, daemonises by default.
        proc = await asyncio.create_subprocess_exec(
            RADVD,
            '--config', str(self._conf_path()),
            '--pidfile', str(self._pid_path()),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error("bridging-radvd: spawn failed (%d): %s",
                         proc.returncode,
                         stderr.decode(errors='replace').strip(),
                         extra=self._log_extra)
            return
        # radvd has daemonised by the time the exec returns success.
        new_pid = self._read_pid()
        logger.info("bridging-radvd: started pid=%s", new_pid,
                    extra=self._log_extra)

    def _read_pid(self) -> Optional[int]:
        try:
            return int(self._pid_path().read_text().strip())
        except (FileNotFoundError, ValueError):
            return None

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
