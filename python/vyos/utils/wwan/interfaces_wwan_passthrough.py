#!/usr/bin/env python3
#
# Copyright (C) 2026 IGOS and contributors
# SPDX-License-Identifier: GPL-2.0-or-later
#
# interfaces_wwan_passthrough.py — DOCSIS-modem-style IP Passthrough.
#
# When configured, the FSM hands the carrier-assigned IPv4 and IPv6 addresses
# directly to a single downstream device on a designated LAN interface via a
# tightly-scoped dnsmasq instance.  This mirrors the behaviour of cellular
# vendor "IP Passthrough" features (Cradlepoint / Digi / Sierra / Peplink),
# which all hand off via DHCP because 3GPP PDN bearers are L3-only and a
# true L2 bridge is impossible.
#
# Architecture
# ------------
#  * One dnsmasq instance per passthrough interface, --bind-interfaces,
#    PID file in /run/wwan/passthru-<if>.pid, conf in /run/wwan/passthru-<if>.conf,
#    leases in /run/wwan/passthru-<if>.leases.
#  * DHCPv4: single lease, address == carrier IPv4, default lease 60s.
#  * DHCPv6 IA_NA + RA (M=1, O=1): hands off carrier IPv6/128 + RDNSS.
#  * Management address (Policy B): if the user has set
#    'interfaces ethernet <if> address ...' explicitly we leave the iface
#    alone; otherwise we add 192.168.200.1/24 + fd00:6c61:6e30::1/64.
#  * IP-change protection: iptables saddr DROP + conntrack flush + SIGHUP
#    + DHCPFORCERENEW (RFC 3203) + DHCPv6 Reconfigure (RFC 8415 §18.2.11),
#    then unblock once downstream renews (or after a 5 s grace window).
#  * Bearer-down: stop dnsmasq, drop mgmt addr (if FSM-owned), tear down
#    iptables rules.

from __future__ import annotations

import asyncio
import ipaddress
import logging
import os
import shutil
import signal
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

RUN_DIR = Path('/run/wwan')
DNSMASQ = '/usr/sbin/dnsmasq'
GRACE_AFTER_RENEW_S = 5

# Policy-routing table id used to forward inbound traffic for the carrier IP
# from wwan<N> to the downstream LAN interface.  Per-instance to allow
# multiple WWAN FSMs to coexist.  Tables 200-299 are used; outside the
# usual VyOS range to avoid clashes.
PASSTHRU_TABLE_BASE = 200
# Routing-rule priority — must be higher (numerically lower) than the main
# table lookup priority (32766) to take effect.
PASSTHRU_RULE_PRIO_BASE = 12000

_DHCP_RELEASE2_WARNED = False


# ---------------------------------------------------------------------------
# config dataclass
# ---------------------------------------------------------------------------

@dataclass
class PassthroughConfig:
    """Validated passthrough configuration extracted from FSM config dict."""
    enabled: bool = False
    interface: str = ''
    mac: str = ''                   # '' = first-MAC-wins
    lease_time: int = 60
    management_address: str = ''    # '' if user owns ethernet
    management_address_ipv6: str = ''
    mgmt_owned_by_user: bool = False
    # Pre-resolved bare-IP forms of the management address (without CIDR).
    # Used as DHCPv4 option 3 (router) and option 121 next-hop so RFC-strict
    # clients (Windows) accept the lease.  Populated by conf_mode regardless
    # of whether mgmt is FSM-owned or user-owned.
    mgmt_v4_ip: str = ''
    mgmt_v6_ip: str = ''
    # TCP MSS clamping on the WWAN egress — ON by default.  Mirrors
    # commercial passthrough products which all clamp to PMTU so that
    # non-compliant downstream clients (those that ignore DHCP option 26
    # / RA MTU) do not generate oversized frames that the kernel must
    # drop with ICMP Frag-Needed / Packet-Too-Big.
    mss_clamp_enabled: bool = True
    # User-supplied DNS overrides.  When non-empty, these are advertised to
    # the downstream device instead of the carrier-supplied DNS list.
    # Mixed v4/v6 addresses are split internally.
    dns_servers: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: Optional[dict]) -> 'PassthroughConfig':
        raw = raw or {}
        dns_raw = raw.get('dns_servers') or []
        if isinstance(dns_raw, str):
            dns_raw = [d.strip() for d in dns_raw.split(',') if d.strip()]
        return cls(
            enabled=bool(raw.get('enabled', False)),
            interface=str(raw.get('interface', '') or ''),
            mac=str(raw.get('mac', '') or '').lower(),
            lease_time=int(raw.get('lease_time', 60) or 60),
            management_address=str(raw.get('management_address', '') or ''),
            management_address_ipv6=str(raw.get('management_address_ipv6', '') or ''),
            mgmt_owned_by_user=bool(raw.get('mgmt_owned_by_user', False)),
            mgmt_v4_ip=str(raw.get('mgmt_v4_ip', '') or ''),
            mgmt_v6_ip=str(raw.get('mgmt_v6_ip', '') or ''),
            mss_clamp_enabled=bool(raw.get('mss_clamp_enabled', True)),
            dns_servers=[str(d) for d in dns_raw if d],
        )

    def is_active(self) -> bool:
        return self.enabled and bool(self.interface)

    def split_dns(self) -> tuple[list, list]:
        """Split user-supplied DNS into (v4, v6) lists."""
        v4, v6 = [], []
        for d in self.dns_servers:
            try:
                ip = ipaddress.ip_address(d)
            except ValueError:
                continue
            (v4 if ip.version == 4 else v6).append(str(ip))
        return v4, v6


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

async def _run(*args, check: bool = False) -> tuple[int, str, str]:
    """Run a shell command; never raise unless check=True."""
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    rc = proc.returncode
    if rc != 0:
        msg = err.decode(errors='replace').strip()
        if check:
            raise RuntimeError(f"command failed ({rc}): {' '.join(args)} — {msg}")
        logger.debug("cmd rc=%s %s — %s", rc, ' '.join(args), msg)
    return rc, out.decode(errors='replace'), err.decode(errors='replace')


def _split_cidr(addr: str) -> tuple[str, int]:
    """'192.168.200.1/24' → ('192.168.200.1', 24).  Raises on garbage."""
    iface = ipaddress.ip_interface(addr)
    return str(iface.ip), iface.network.prefixlen


def _v4_pool_for(carrier_ipv4: str) -> tuple[str, str, str]:
    """Build a one-host pool centered on the carrier IPv4 for dnsmasq.

    dnsmasq insists on a `dhcp-range` even when handing out a fixed host.
    We give it the carrier address as both start AND end so dnsmasq has
    exactly one IP to offer regardless of where the carrier IP sits inside
    its /30.  Netmask sent here is dnsmasq's own subnet bookkeeping; the
    actual netmask delivered to the client is overridden via DHCP option 1.
    Returns (range_start, range_end, netmask).
    """
    return carrier_ipv4, carrier_ipv4, '255.255.255.252'


# ---------------------------------------------------------------------------
# manager
# ---------------------------------------------------------------------------

class PassthroughManager:
    """Owns the dnsmasq instance, iptables rules and mgmt address for one
    passthrough interface.  One instance per WWAN FSM."""

    def __init__(self, interface_number: int):
        self.interface_number = interface_number
        self._log_extra = {'interface_number': interface_number}
        self._wwan_iface = f'wwan{interface_number}'
        self._table_id = PASSTHRU_TABLE_BASE + interface_number
        self._rule_prio = PASSTHRU_RULE_PRIO_BASE + interface_number

        self.cfg = PassthroughConfig()
        self._dnsmasq_pid: Optional[int] = None
        self._mgmt_v4_added: bool = False
        self._mgmt_v6_added: bool = False

        # Last-known carrier IPs (for change detection + iptables cleanup)
        self._last_v4: Optional[str] = None
        self._last_v6: Optional[str] = None

        # iptables saddr-block state (set during a swap)
        self._v4_block_active: bool = False
        self._v6_block_active: bool = False

        # Persistent source-address whitelist state — mirrors PD's
        # ip6tables egress filter.  When active, FORWARD traffic arriving on
        # the LAN interface is dropped unless its source is the current
        # carrier IP.  Survives across IP changes; entries are rewritten
        # in-place when the carrier address rolls over.
        self._src_whitelist_v4_active: bool = False
        self._src_whitelist_v6_active: bool = False

        # TCP MSS clamp state — one rule each (v4 and v6) on the WWAN
        # egress interface, installed once when passthrough activates and
        # removed at teardown.  --clamp-mss-to-pmtu auto-tracks the kernel
        # interface MTU, so bearer MTU changes are picked up without us
        # having to rewrite the rule.
        self._mss_clamp_v4_active: bool = False
        self._mss_clamp_v6_active: bool = False

        # Inbound forwarding state (policy routing rules + table entries)
        self._inbound_v4_addr: Optional[str] = None
        self._inbound_v6_addr: Optional[str] = None

        RUN_DIR.mkdir(parents=True, exist_ok=True)

    # ── path helpers ────────────────────────────────────────────────────
    def _conf_path(self) -> Path:
        return RUN_DIR / f'passthru-{self.cfg.interface}.conf'

    def _pid_path(self) -> Path:
        return RUN_DIR / f'passthru-{self.cfg.interface}.pid'

    def _leases_path(self) -> Path:
        return RUN_DIR / f'passthru-{self.cfg.interface}.leases'

    # ── public surface ──────────────────────────────────────────────────
    def update_config(self, raw: Optional[dict]) -> bool:
        """Replace the configuration; returns True if interface changed."""
        new_cfg = PassthroughConfig.from_dict(raw)
        old_iface = self.cfg.interface
        self.cfg = new_cfg
        return old_iface and old_iface != new_cfg.interface

    async def apply(self, carrier_v4: Optional[str], carrier_v6: Optional[str],
                    carrier_v6_prefix: int = 128,
                    ipv4_dns: Optional[list] = None,
                    ipv6_dns: Optional[list] = None,
                    bearer_mtu: Optional[int] = None) -> None:
        """Apply (or update) passthrough for the given carrier addresses.

        Called by the FSM from `_apply_bearer_ip_configuration()` when
        passthrough is enabled.  Idempotent — safe to call repeatedly.

        ``ipv4_dns`` / ``ipv6_dns`` are the carrier-supplied DNS server
        lists from the bearer's IpConfig.  They are advertised to the
        downstream device via DHCP option 6 / option 23 so the client
        sees the carrier's resolvers (matches Cradlepoint behaviour).
        """
        if not self.cfg.is_active():
            await self.teardown()
            return

        if not (carrier_v4 or carrier_v6):
            logger.warning("passthrough: no carrier IP available; tearing down",
                           extra=self._log_extra)
            await self.teardown()
            return

        # Detect IP change ─ trigger the handoff sequence if needed.
        v4_changed = (self._last_v4 is not None
                      and carrier_v4 is not None
                      and self._last_v4 != carrier_v4)
        v6_changed = (self._last_v6 is not None
                      and carrier_v6 is not None
                      and self._last_v6 != carrier_v6)

        if v4_changed:
            await self._block_v4_saddr(self._last_v4)
            await self._flush_conntrack_v4(self._last_v4)
            await self._remove_inbound_route_v4(self._last_v4)
        if v6_changed:
            await self._block_v6_saddr(self._last_v6)
            await self._flush_conntrack_v6(self._last_v6)
            await self._remove_inbound_route_v6(self._last_v6)

        # Ensure mgmt address is on the LAN interface (Policy B).
        await self._ensure_mgmt_address()

        # Render dnsmasq config + (re)start.
        await self._write_dnsmasq_conf(
            carrier_v4, carrier_v6, carrier_v6_prefix,
            ipv4_dns or [], ipv6_dns or [], bearer_mtu,
        )
        await self._start_or_reload_dnsmasq()

        # Install policy-routing so inbound packets to the carrier IP that
        # arrive on wwan<N> are forwarded out the LAN interface to the
        # downstream device, while the address itself stays bound to wwan
        # (so locally-originated traffic still has a valid source).
        if carrier_v4:
            await self._install_inbound_route_v4(carrier_v4)
        if carrier_v6:
            await self._install_inbound_route_v6(carrier_v6)

        # Install / refresh the persistent source-address whitelist on
        # FORWARD: drops any traffic from the LAN port whose source is
        # not the current carrier IP.  Mirrors PD's ip6tables egress
        # filter so a downstream device that clings to a stale address
        # cannot leak packets after an IP change.
        if carrier_v4:
            await self._install_src_whitelist_v4(carrier_v4)
        if carrier_v6:
            await self._install_src_whitelist_v6(carrier_v6)

        # TCP MSS clamping on WWAN egress — industry-standard fix for
        # downstream clients that ignore DHCP option 26 / RA MTU.
        if self.cfg.mss_clamp_enabled:
            await self._install_mss_clamp()
        else:
            await self._remove_mss_clamp()

        # Push the new lease to the downstream device.
        if v4_changed:
            await self._force_renew_v4()
        if v6_changed:
            await self._reconfigure_v6()

        # Schedule the unblock after the renewal grace window.
        if v4_changed:
            asyncio.create_task(self._unblock_v4_after_grace(self._last_v4))
        if v6_changed:
            asyncio.create_task(self._unblock_v6_after_grace(self._last_v6))

        self._last_v4 = carrier_v4
        self._last_v6 = carrier_v6

        logger.info("passthrough: applied carrier IPs (v4=%s v6=%s/%s) → %s",
                    carrier_v4, carrier_v6, carrier_v6_prefix, self.cfg.interface,
                    extra=self._log_extra)

    async def teardown(self) -> None:
        """Stop dnsmasq, drop mgmt addr (if owned), clean up iptables
        and the policy-routing entries used for inbound forwarding."""
        await self._stop_dnsmasq()
        await self._remove_mgmt_address()
        await self._unblock_v4_saddr(self._last_v4)
        await self._unblock_v6_saddr(self._last_v6)
        await self._remove_inbound_route_v4(self._inbound_v4_addr)
        await self._remove_inbound_route_v6(self._inbound_v6_addr)
        await self._remove_src_whitelist_v4()
        await self._remove_src_whitelist_v6()
        await self._remove_mss_clamp()
        self._last_v4 = None
        self._last_v6 = None
        logger.info("passthrough: torn down on %s",
                    self.cfg.interface or '<unset>', extra=self._log_extra)

    # ── dnsmasq lifecycle ───────────────────────────────────────────────
    async def _write_dnsmasq_conf(self, carrier_v4: Optional[str],
                                  carrier_v6: Optional[str],
                                  carrier_v6_prefix: int,
                                  ipv4_dns: list,
                                  ipv6_dns: list,
                                  bearer_mtu: Optional[int] = None) -> None:
        """Render the per-instance dnsmasq.conf."""
        lines: list[str] = []
        lines.append("# auto-generated by interfaces_wwan_passthrough.py — do not edit")
        lines.append(f"interface={self.cfg.interface}")
        lines.append("bind-interfaces")
        lines.append("except-interface=lo")
        lines.append("no-resolv")
        lines.append("no-hosts")
        lines.append(f"pid-file={self._pid_path()}")
        lines.append(f"dhcp-leasefile={self._leases_path()}")
        lines.append("port=0")  # disable DNS — DHCP/RA only
        # Quiet logging: a 60 s lease means renewals every ~30 s; log-dhcp
        # would flood syslog.  Errors and config issues are still emitted.
        lines.append("quiet-dhcp")
        lines.append("quiet-dhcp6")
        lines.append("quiet-ra")
        lines.append("dhcp-authoritative")
        # enable Reconfigure for v6 and FORCERENEW awareness for v4
        lines.append("dhcp-rapid-commit")

        lease = self.cfg.lease_time
        # Choose a gateway IP for DHCPv4 option 3 / option 121 next-hop.
        # RFC-strict clients (notably Windows) reject leases with router=
        # 0.0.0.0, and option 121 next-hops of 0.0.0.0 are interpreted
        # inconsistently across stacks.  Prefer the router's mgmt v4 IP
        # (FSM-owned 192.168.200.1 by default, or the user's own ethernet
        # address under Policy B).  Only fall back to 0.0.0.0 when the
        # admin has explicitly removed every v4 address from the LAN port.
        gw_v4 = self.cfg.mgmt_v4_ip or '0.0.0.0'

        # ── DHCPv4 ──
        if carrier_v4:
            start, end, netmask = _v4_pool_for(carrier_v4)
            lines.append(f"dhcp-range=set:passthru4,{start},{end},{netmask},{lease}")
            # 'set:passthru' tag attached so we can target dhcp-options
            tag = 'passthru4'
            if self.cfg.mac:
                # Pinned MAC: only this client gets the carrier IP
                lines.append(
                    f"dhcp-host={self.cfg.mac},{carrier_v4},set:{tag},{lease}"
                )
            else:
                # First-MAC-wins: dnsmasq will hand out the single address in
                # the range to whatever MAC asks first; subsequent MACs get NAK.
                # Lock the lease via dhcp-ignore-names + max-leases
                lines.append("dhcp-ignore-names")
                lines.append("dhcp-lease-max=1")
            # Override DHCP options so the downstream device thinks it has the
            # carrier IP as a host (/32) with the router's mgmt IP as default.
            lines.append(f"dhcp-option=tag:{tag},1,255.255.255.255")     # netmask /32
            lines.append(f"dhcp-option=tag:{tag},3,{gw_v4}")             # router
            # DNS option 6 — three-tier precedence:
            #   1. user override (CLI dns-server) — wins always
            #   2. carrier-supplied resolvers from the bearer
            #   3. public anycast last-resort fallback
            user_v4, _user_v6 = self.cfg.split_dns()
            v4_dns = (
                user_v4
                or [d for d in (ipv4_dns or []) if d]
                or ['8.8.8.8', '1.1.1.1']
            )
            lines.append(f"dhcp-option=tag:{tag},6,{','.join(v4_dns)}")
            lines.append(f"dhcp-option=tag:{tag},51,{lease}")            # lease time
            lines.append(f"dhcp-option=tag:{tag},58,{lease // 2}")       # T1
            lines.append(f"dhcp-option=tag:{tag},59,{(lease * 7) // 8}") # T2
            # MTU (option 26) — clamp to bearer MTU so PMTUD doesn't black-hole
            if bearer_mtu and bearer_mtu > 0:
                lines.append(f"dhcp-option=tag:{tag},26,{int(bearer_mtu)}")
            # Classless static route (option 121): host route to the gateway
            # via dev (link-only), then default via gateway.  This pattern is
            # what Cradlepoint/Peplink emit and is accepted by Windows, macOS,
            # iOS, Android, and Linux clients.
            lines.append(
                f"dhcp-option=tag:{tag},121,{gw_v4}/32,0.0.0.0,0.0.0.0/0,{gw_v4}"
            )

        # ── DHCPv6 + RA ──
        if carrier_v6:
            # Explicit /128 prefix-len: without it dnsmasq defaults to /64
            # and the carrier prefix would be advertised as on-link, breaking
            # routing for any v6 destination inside that /64.
            v6_pool = f"{carrier_v6},{carrier_v6},128,{lease}"
            lines.append(f"dhcp-range=set:passthru6,{v6_pool}")
            lines.append("enable-ra")
            # ra-param=<if>,[mtu:N,]<interval>,<lifetime>
            # MTU advertised in RA — must match the bearer MTU or v6 PMTUD
            # black-holes for any path that touches the bearer.
            ra_mtu = int(bearer_mtu) if (bearer_mtu and bearer_mtu > 0) else 1500
            lines.append(f"ra-param={self.cfg.interface},mtu:{ra_mtu},0,60")
            # DNS option 23 (DHCPv6) + RDNSS in RA — user override beats carrier
            _user_v4, user_v6 = self.cfg.split_dns()
            v6_dns = user_v6 or [d for d in (ipv6_dns or []) if d]
            if v6_dns:
                lines.append(
                    "dhcp-option=option6:dns-server,"
                    + ','.join(f"[{d}]" for d in v6_dns)
                )
            if self.cfg.mac:
                # DHCPv6 client-id pinning is hard without DUID; fall back to
                # MAC-based reservation (dnsmasq supports this via dhcp-host
                # with a v6 address).
                lines.append(
                    f"dhcp-host={self.cfg.mac},[{carrier_v6}],set:passthru6,{lease}"
                )

        self._conf_path().write_text('\n'.join(lines) + '\n')
        logger.debug("passthrough: wrote %s", self._conf_path(),
                     extra=self._log_extra)

    async def _start_or_reload_dnsmasq(self) -> None:
        """Spawn dnsmasq if not running; otherwise SIGHUP to reload.

        With ``--bind-interfaces`` dnsmasq must find the listen interface
        present AND with at least one address at startup.  If the LAN
        interface (or its mgmt address) was just brought up, the kernel
        may take a moment to settle — retry up to ~3 s before giving up.
        """
        pid = self._read_pid()
        if pid and self._pid_alive(pid):
            os.kill(pid, signal.SIGHUP)
            self._dnsmasq_pid = pid
            logger.info("passthrough: SIGHUP dnsmasq pid=%s", pid,
                        extra=self._log_extra)
            return

        # Stale pidfile or never started — wait for interface readiness then start
        last_err = ''
        for attempt in range(6):  # 6 × 0.5 s = 3 s total
            rc, _, err = await _run(
                DNSMASQ,
                f'--conf-file={self._conf_path()}',
                '--keep-in-foreground=no',
            )
            if rc == 0:
                break
            last_err = err.strip()
            # Common transient: "unknown interface" / "no suitable address"
            if attempt < 5:
                logger.debug(
                    "passthrough: dnsmasq start attempt %d/6 failed (%s); retrying",
                    attempt + 1, last_err, extra=self._log_extra,
                )
                await asyncio.sleep(0.5)
        else:
            logger.error("passthrough: dnsmasq failed to start after retries: %s",
                         last_err, extra=self._log_extra)
            return
        # dnsmasq daemonises and writes its pidfile
        self._dnsmasq_pid = self._read_pid()
        logger.info("passthrough: dnsmasq started pid=%s on %s",
                    self._dnsmasq_pid, self.cfg.interface,
                    extra=self._log_extra)

    async def _stop_dnsmasq(self) -> None:
        pid = self._dnsmasq_pid or self._read_pid()
        if not pid:
            return
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        # Give it a moment to exit cleanly
        for _ in range(20):
            if not self._pid_alive(pid):
                break
            await asyncio.sleep(0.1)
        else:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        self._dnsmasq_pid = None
        try:
            self._pid_path().unlink()
        except FileNotFoundError:
            pass
        logger.info("passthrough: dnsmasq stopped (pid=%s)", pid,
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

    # ── management address (Policy B) ───────────────────────────────────
    async def _ensure_mgmt_address(self) -> None:
        if self.cfg.mgmt_owned_by_user:
            return  # user wins — do nothing
        if self.cfg.management_address and not self._mgmt_v4_added:
            await _run('ip', 'addr', 'add', self.cfg.management_address,
                       'dev', self.cfg.interface)
            self._mgmt_v4_added = True
            logger.info("passthrough: mgmt v4 %s on %s",
                        self.cfg.management_address, self.cfg.interface,
                        extra=self._log_extra)
        if self.cfg.management_address_ipv6 and not self._mgmt_v6_added:
            await _run('ip', '-6', 'addr', 'add', self.cfg.management_address_ipv6,
                       'dev', self.cfg.interface)
            self._mgmt_v6_added = True
            logger.info("passthrough: mgmt v6 %s on %s",
                        self.cfg.management_address_ipv6, self.cfg.interface,
                        extra=self._log_extra)

    async def _remove_mgmt_address(self) -> None:
        if self._mgmt_v4_added and self.cfg.management_address:
            await _run('ip', 'addr', 'del', self.cfg.management_address,
                       'dev', self.cfg.interface)
            self._mgmt_v4_added = False
        if self._mgmt_v6_added and self.cfg.management_address_ipv6:
            await _run('ip', '-6', 'addr', 'del', self.cfg.management_address_ipv6,
                       'dev', self.cfg.interface)
            self._mgmt_v6_added = False

    # ── iptables saddr blocks (during IP swap) ──────────────────────────
    async def _block_v4_saddr(self, old_v4: Optional[str]) -> None:
        if not old_v4 or self._v4_block_active:
            return
        await _run('iptables', '-I', 'FORWARD', '1',
                   '-s', old_v4, '-j', 'DROP')
        self._v4_block_active = True
        logger.info("passthrough: blocked stale v4 saddr=%s", old_v4,
                    extra=self._log_extra)

    async def _unblock_v4_saddr(self, old_v4: Optional[str]) -> None:
        if not old_v4 or not self._v4_block_active:
            return
        await _run('iptables', '-D', 'FORWARD', '-s', old_v4, '-j', 'DROP')
        self._v4_block_active = False

    async def _block_v6_saddr(self, old_v6: Optional[str]) -> None:
        if not old_v6 or self._v6_block_active:
            return
        await _run('ip6tables', '-I', 'FORWARD', '1',
                   '-s', old_v6, '-j', 'DROP')
        self._v6_block_active = True
        logger.info("passthrough: blocked stale v6 saddr=%s", old_v6,
                    extra=self._log_extra)

    async def _unblock_v6_saddr(self, old_v6: Optional[str]) -> None:
        if not old_v6 or not self._v6_block_active:
            return
        await _run('ip6tables', '-D', 'FORWARD', '-s', old_v6, '-j', 'DROP')
        self._v6_block_active = False

    async def _flush_conntrack_v4(self, old_v4: Optional[str]) -> None:
        if not old_v4:
            return
        await _run('conntrack', '-D', '-s', old_v4)
        await _run('conntrack', '-D', '-d', old_v4)

    async def _flush_conntrack_v6(self, old_v6: Optional[str]) -> None:
        if not old_v6:
            return
        await _run('conntrack', '-D', '-f', 'ipv6', '-s', old_v6)
        await _run('conntrack', '-D', '-f', 'ipv6', '-d', old_v6)

    # ── DHCPFORCERENEW / Reconfigure ────────────────────────────────────
    async def _force_renew_v4(self) -> None:
        """Best-effort DHCPFORCERENEW.  Requires dnsmasq-utils' dhcp_release2
        helper; if the binary isn't on PATH we log once and rely on the
        downstream device's own renewal at T1 (lease/2 — ≤30 s with the
        default 60 s lease)."""
        global _DHCP_RELEASE2_WARNED
        leases = self._read_active_v4_leases()
        if not leases:
            return
        if shutil.which('dhcp_release2') is None:
            if not _DHCP_RELEASE2_WARNED:
                logger.warning(
                    "passthrough: dhcp_release2 not installed — DHCPFORCERENEW "
                    "unavailable.  Install the 'dnsmasq-utils' package for "
                    "sub-second IP-change handoff; otherwise downstream will "
                    "renew at T1 (~%s s).",
                    self.cfg.lease_time // 2, extra=self._log_extra,
                )
                _DHCP_RELEASE2_WARNED = True
            return
        for mac, ip in leases:
            await _run('dhcp_release2', '--iface', self.cfg.interface,
                       '--client', mac, '--ip', ip)
        logger.info("passthrough: DHCPFORCERENEW sent to %d v4 client(s)",
                    len(leases), extra=self._log_extra)

    async def _reconfigure_v6(self) -> None:
        """Trigger DHCPv6 Reconfigure.  dnsmasq does this automatically on
        SIGHUP when the dhcp-range changes — our SIGHUP path already covered
        that.  Nothing further to do here, but kept as a hook for future
        explicit Reconfigure messaging."""
        logger.debug("passthrough: v6 Reconfigure handled via dnsmasq SIGHUP",
                     extra=self._log_extra)

    def _read_active_v4_leases(self) -> list[tuple[str, str]]:
        """Parse dnsmasq leases file: returns [(mac, ip), ...]"""
        try:
            text = self._leases_path().read_text()
        except FileNotFoundError:
            return []
        out = []
        for line in text.splitlines():
            parts = line.split()
            # format: <expiry> <mac> <ip> <hostname> <client-id>
            if len(parts) >= 3 and ':' in parts[1] and '.' in parts[2]:
                out.append((parts[1], parts[2]))
        return out

    # ── grace timers ────────────────────────────────────────────────────
    async def _unblock_v4_after_grace(self, old_v4: Optional[str]) -> None:
        await asyncio.sleep(GRACE_AFTER_RENEW_S)
        await self._unblock_v4_saddr(old_v4)

    async def _unblock_v6_after_grace(self, old_v6: Optional[str]) -> None:
        await asyncio.sleep(GRACE_AFTER_RENEW_S)
        await self._unblock_v6_saddr(old_v6)

    # ── inbound forwarding via policy routing ───────────────────────────
    #
    # The carrier IP stays bound to wwan<N> (kernel needs a local source for
    # outbound traffic from the router itself — ModemManager probes, NTP,
    # carrier DNS, etc.).  But inbound packets arriving on wwan<N> destined
    # for the carrier IP must be *forwarded* to the downstream LAN interface
    # rather than delivered locally.
    #
    # We accomplish this with a per-FSM routing rule:
    #
    #     ip rule add iif wwan<N> to <carrier_ip> lookup passthru<N>
    #     ip route add <carrier_ip> dev <lan_if> table passthru<N>
    #
    # The rule fires *before* the local table is consulted, so packets are
    # routed to the LAN device.  Locally-originated traffic (which doesn't
    # match `iif wwan<N>`) still hits the local table and the carrier IP
    # remains usable as a source.

    async def _install_inbound_route_v4(self, carrier_v4: str) -> None:
        if self._inbound_v4_addr == carrier_v4:
            return
        # Tear down any prior entry first
        await self._remove_inbound_route_v4(self._inbound_v4_addr)
        # Route in the per-FSM table
        await _run('ip', '-4', 'route', 'replace',
                   f'{carrier_v4}/32', 'dev', self.cfg.interface,
                   'table', str(self._table_id))
        # Rule that diverts inbound traffic to the table
        await _run('ip', '-4', 'rule', 'add',
                   'priority', str(self._rule_prio),
                   'iif', self._wwan_iface,
                   'to', f'{carrier_v4}/32',
                   'lookup', str(self._table_id))
        self._inbound_v4_addr = carrier_v4
        logger.info(
            "passthrough: inbound v4 route installed — %s arriving on %s → %s",
            carrier_v4, self._wwan_iface, self.cfg.interface,
            extra=self._log_extra,
        )

    async def _remove_inbound_route_v4(self, carrier_v4: Optional[str]) -> None:
        if not carrier_v4:
            return
        await _run('ip', '-4', 'rule', 'del',
                   'priority', str(self._rule_prio),
                   'iif', self._wwan_iface,
                   'to', f'{carrier_v4}/32',
                   'lookup', str(self._table_id))
        await _run('ip', '-4', 'route', 'del',
                   f'{carrier_v4}/32', 'dev', self.cfg.interface,
                   'table', str(self._table_id))
        if self._inbound_v4_addr == carrier_v4:
            self._inbound_v4_addr = None

    async def _install_inbound_route_v6(self, carrier_v6: str) -> None:
        if self._inbound_v6_addr == carrier_v6:
            return
        await self._remove_inbound_route_v6(self._inbound_v6_addr)
        await _run('ip', '-6', 'route', 'replace',
                   f'{carrier_v6}/128', 'dev', self.cfg.interface,
                   'table', str(self._table_id))
        await _run('ip', '-6', 'rule', 'add',
                   'priority', str(self._rule_prio),
                   'iif', self._wwan_iface,
                   'to', f'{carrier_v6}/128',
                   'lookup', str(self._table_id))
        self._inbound_v6_addr = carrier_v6
        logger.info(
            "passthrough: inbound v6 route installed — %s arriving on %s → %s",
            carrier_v6, self._wwan_iface, self.cfg.interface,
            extra=self._log_extra,
        )

    async def _remove_inbound_route_v6(self, carrier_v6: Optional[str]) -> None:
        if not carrier_v6:
            return
        await _run('ip', '-6', 'rule', 'del',
                   'priority', str(self._rule_prio),
                   'iif', self._wwan_iface,
                   'to', f'{carrier_v6}/128',
                   'lookup', str(self._table_id))
        await _run('ip', '-6', 'route', 'del',
                   f'{carrier_v6}/128', 'dev', self.cfg.interface,
                   'table', str(self._table_id))
        if self._inbound_v6_addr == carrier_v6:
            self._inbound_v6_addr = None

    # ── persistent source-address whitelist (mirrors PD egress filter) ──
    #
    # Structure (v4 example, chain name PASSTHRU_<IF>_SRC4):
    #   FORWARD  -i <lan_if>  -j PASSTHRU_<IF>_SRC4
    #   chain:
    #     -s <current_carrier_v4>  -j RETURN     # allow current
    #     -j DROP                                 # block stale sources
    #
    # IPv6 chain additionally allows fe80::/10 so NDP/RA continue to work.
    # Updates are atomic per chain: flush + repopulate, jump rule stays.

    def _src_chain_v4(self) -> str:
        # iptables chain names ≤ 28 chars
        return f"PT_{self.cfg.interface.upper()[:20]}_S4"

    def _src_chain_v6(self) -> str:
        return f"PT_{self.cfg.interface.upper()[:20]}_S6"

    async def _install_src_whitelist_v4(self, carrier_v4: str) -> None:
        chain = self._src_chain_v4()
        if self._src_whitelist_v4_active:
            await _run('iptables', '-F', chain)
        else:
            await _run('iptables', '-N', chain)
            await _run('iptables', '-I', 'FORWARD', '1',
                       '-i', self.cfg.interface, '-j', chain)
            self._src_whitelist_v4_active = True
        await _run('iptables', '-A', chain, '-s', carrier_v4, '-j', 'RETURN')
        await _run('iptables', '-A', chain, '-j', 'DROP')
        logger.info(
            "passthrough: v4 src whitelist active on %s — only %s permitted",
            self.cfg.interface, carrier_v4, extra=self._log_extra,
        )

    async def _remove_src_whitelist_v4(self) -> None:
        if not self._src_whitelist_v4_active:
            return
        chain = self._src_chain_v4()
        await _run('iptables', '-D', 'FORWARD',
                   '-i', self.cfg.interface, '-j', chain)
        await _run('iptables', '-F', chain)
        await _run('iptables', '-X', chain)
        self._src_whitelist_v4_active = False

    async def _install_src_whitelist_v6(self, carrier_v6: str) -> None:
        chain = self._src_chain_v6()
        if self._src_whitelist_v6_active:
            await _run('ip6tables', '-F', chain)
        else:
            await _run('ip6tables', '-N', chain)
            await _run('ip6tables', '-I', 'FORWARD', '1',
                       '-i', self.cfg.interface, '-j', chain)
            self._src_whitelist_v6_active = True
        await _run('ip6tables', '-A', chain, '-s', carrier_v6, '-j', 'RETURN')
        # NDP / link-local must still be permitted for the LAN to function
        await _run('ip6tables', '-A', chain, '-s', 'fe80::/10', '-j', 'RETURN')
        await _run('ip6tables', '-A', chain, '-j', 'DROP')
        logger.info(
            "passthrough: v6 src whitelist active on %s — only %s + link-local permitted",
            self.cfg.interface, carrier_v6, extra=self._log_extra,
        )

    async def _remove_src_whitelist_v6(self) -> None:
        if not self._src_whitelist_v6_active:
            return
        chain = self._src_chain_v6()
        await _run('ip6tables', '-D', 'FORWARD',
                   '-i', self.cfg.interface, '-j', chain)
        await _run('ip6tables', '-F', chain)
        await _run('ip6tables', '-X', chain)
        self._src_whitelist_v6_active = False

    # ------------------------------------------------------------------
    # TCP MSS clamping (mangle/FORWARD)
    #
    # Industry-standard fix for downstream clients that ignore DHCP
    # option 26 / RA MTU and emit oversized TCP segments.  The kernel
    # rewrites the MSS option in SYN/SYN-ACK to fit the WWAN egress
    # PMTU; --clamp-mss-to-pmtu auto-tracks the wwan<N> MTU so a bearer
    # MTU change is picked up without rewriting the rule.
    #
    # Default ON (matches Cradlepoint/Peplink/Sierra/Digi passthrough
    # behavior).  Disable per-interface via:
    #   set interfaces wwan wwanN ip-passthrough disable-mss-clamp
    # ------------------------------------------------------------------

    async def _install_mss_clamp(self) -> None:
        if not self._mss_clamp_v4_active:
            await _run('iptables', '-t', 'mangle', '-A', 'FORWARD',
                       '-o', self._wwan_iface,
                       '-p', 'tcp', '--tcp-flags', 'SYN,RST', 'SYN',
                       '-j', 'TCPMSS', '--clamp-mss-to-pmtu')
            self._mss_clamp_v4_active = True
        if not self._mss_clamp_v6_active:
            await _run('ip6tables', '-t', 'mangle', '-A', 'FORWARD',
                       '-o', self._wwan_iface,
                       '-p', 'tcp', '--tcp-flags', 'SYN,RST', 'SYN',
                       '-j', 'TCPMSS', '--clamp-mss-to-pmtu')
            self._mss_clamp_v6_active = True
        logger.info(
            "passthrough: MSS clamp-to-PMTU active on %s (v4+v6)",
            self._wwan_iface, extra=self._log_extra,
        )

    async def _remove_mss_clamp(self) -> None:
        if self._mss_clamp_v4_active:
            await _run('iptables', '-t', 'mangle', '-D', 'FORWARD',
                       '-o', self._wwan_iface,
                       '-p', 'tcp', '--tcp-flags', 'SYN,RST', 'SYN',
                       '-j', 'TCPMSS', '--clamp-mss-to-pmtu')
            self._mss_clamp_v4_active = False
        if self._mss_clamp_v6_active:
            await _run('ip6tables', '-t', 'mangle', '-D', 'FORWARD',
                       '-o', self._wwan_iface,
                       '-p', 'tcp', '--tcp-flags', 'SYN,RST', 'SYN',
                       '-j', 'TCPMSS', '--clamp-mss-to-pmtu')
            self._mss_clamp_v6_active = False
