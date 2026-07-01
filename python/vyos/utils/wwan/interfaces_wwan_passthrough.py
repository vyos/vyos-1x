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
import ipaddress
import logging
import os
import shutil
import signal
import socket
import struct
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

# New priority for the kernel `local` table once passthrough is active.
# By default the kernel installs `local` at pref 0 — *before* every user
# rule — so a packet arriving on wwan<N> destined for the carrier IP is
# delivered locally instead of being matched by our pref-12000 forwarding
# rule.  We move `local` to pref 32765 (just before `main` at 32766) so
# user rules fire first.  This is the same approach used by OpenWrt mwan3
# and most cellular CPE products implementing IP
# Passthrough.  It does NOT affect normal forwarding: any packet that
# does not match a passthrough rule still hits `local` and gets the same
# treatment as before, just at a slightly later priority.
PASSTHRU_LOCAL_TABLE_PRIO = 32765

_DHCP_RELEASE2_WARNED = False
# Module-level: have we already swapped the kernel `local` table from
# pref 0 to pref PASSTHRU_LOCAL_TABLE_PRIO?  Tracked across all
# PassthroughManager instances in this process so multiple WWAN FSMs do
# not fight each other.  Bumped to 1 on first swap; only the instance
# that observed the rising edge (0→1) will restore on teardown.
_LOCAL_TABLE_SWAP_REFCOUNT = 0


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


def _v4_pool_for(carrier_ipv4: str,
                 carrier_prefix: int = 30) -> tuple[str, str, str]:
    """Build a one-host pool centered on the carrier IPv4 for dnsmasq.

    dnsmasq insists on a `dhcp-range` even when handing out a fixed host.
    We give it the carrier address as both start AND end so dnsmasq has
    exactly one IP to offer.  The netmask must define a subnet in which
    the carrier IP is a *host* (not the network or broadcast address);
    otherwise dnsmasq replies "no leases left".

    Cellular carriers commonly hand out /29 or /30 PtP subnets, but the
    carrier IP can land on the network address of a strict /30 (e.g.
    .76 in 10.138.168.76/30 → network=.76).  We therefore widen the
    netmask if necessary until the carrier IP is a leasable host.  The
    actual netmask delivered to the client is overridden via DHCP
    option 1, so this only affects dnsmasq's internal bookkeeping.
    Returns (range_start, range_end, netmask).
    """
    ip = ipaddress.ip_address(carrier_ipv4)
    plen = max(1, min(int(carrier_prefix or 30), 30))
    while plen >= 1:
        net = ipaddress.ip_network(f'{carrier_ipv4}/{plen}', strict=False)
        if ip != net.network_address and ip != net.broadcast_address:
            return carrier_ipv4, carrier_ipv4, str(net.netmask)
        plen -= 1
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

        # Last-known carrier IPs (for change detection + iptables cleanup).
        # Deliberately preserved across `teardown()` so that a SIM swap —
        # which fires teardown() during the bearer-disconnect debounce and
        # then apply() when the new SIM connects — is correctly detected
        # as an IP change on the next apply().  Otherwise apply() sees
        # _last_v4 == None, decides nothing changed, and skips the entire
        # handoff sequence (DHCPFORCERENEW, conntrack flush, iptables
        # block, leases-file wipe).  That manifests as the symptom
        # "Windows /release && /renew never succeeds with the new IP".
        self._last_v4: Optional[str] = None
        self._last_v6: Optional[str] = None
        self._last_v6_prefix: int = 0

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

        # True iff *this* instance performed the kernel-local-table
        # priority swap (from pref 0 → PASSTHRU_LOCAL_TABLE_PRIO).  Only
        # the instance that flipped the bit restores it on teardown.
        self._owns_local_table_swap: bool = False

        # Shadow addresses on the LAN interface from the carrier subnet.
        # dnsmasq will only serve a dhcp-range whose network overlaps an
        # address present on the listening interface.  Since the carrier
        # IP itself is leased to the downstream device (and lives on
        # wwan<N>), the LAN port has no address in the carrier subnet
        # otherwise — dnsmasq refuses with "no address range available".
        # We attach an unused host from the carrier /30 (v4) and a single
        # address from the carrier /64 (v6) with `noprefixroute` so the
        # kernel does NOT auto-create a competing connected route that
        # would steal the carrier-gateway next-hop from wwan<N>.
        # Stored as 'addr/prefix' strings for symmetric add/del.
        self._shadow_v4: Optional[str] = None  # e.g. '10.64.179.125/30'
        self._shadow_v6: Optional[str] = None  # e.g. '2605:b100:112:136c::1/64'

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
                    carrier_v4_prefix: int = 30,
                    ipv4_dns: Optional[list] = None,
                    ipv6_dns: Optional[list] = None,
                    bearer_mtu: Optional[int] = None) -> None:
        """Apply (or update) passthrough for the given carrier addresses.

        Called by the FSM from `_apply_bearer_ip_configuration()` when
        passthrough is enabled.  Idempotent — safe to call repeatedly.

        ``ipv4_dns`` / ``ipv6_dns`` are the carrier-supplied DNS server
        lists from the bearer's IpConfig.  They are advertised to the
        downstream device via DHCP option 6 / option 23 so the client
        sees the carrier's resolvers (standard CPE passthrough behaviour).
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
        #
        # We treat "address went away" (e.g. SIM swap to a v4-only carrier
        # so v6 disappears, or vice-versa) the same as "address rolled to
        # a new value".  Without the *_gone branches, the cleanup helpers
        # are skipped when the new bearer no longer has that family, and
        # the downstream device retains its old SLAAC/DHCP state until
        # the carrier-advertised lifetime expires (~7 days on cellular).
        v4_gone = self._last_v4 is not None and carrier_v4 is None
        v6_gone = self._last_v6 is not None and carrier_v6 is None
        v4_changed = v4_gone or (
            self._last_v4 is not None
            and carrier_v4 is not None
            and self._last_v4 != carrier_v4
        )
        v6_changed = v6_gone or (
            self._last_v6 is not None
            and carrier_v6 is not None
            and self._last_v6 != carrier_v6
        )

        if v4_changed:
            await self._block_v4_saddr(self._last_v4)
            await self._flush_conntrack_v4(self._last_v4)
            await self._remove_inbound_route_v4(self._last_v4)
            # Wipe the dnsmasq leases file so a stale MAC→old-IP entry
            # can never be re-offered after restart/SIGHUP.  Without
            # this, Windows /release && /renew can race with dnsmasq's
            # in-memory lease state and end up with no successful ACK.
            # Gated on lease_count > 0 — only wipe when there's actually
            # something stale on disk so a benign re-apply (no real IP
            # change ever happened, e.g. cold start with stashed state)
            # never touches the file.
            if self._read_active_v4_leases():
                await self._wipe_leases_file()
        if v6_changed:
            await self._block_v6_saddr(self._last_v6)
            await self._flush_conntrack_v6(self._last_v6)
            await self._remove_inbound_route_v6(self._last_v6)
            # Fire a burst of deprecation RAs for the OLD prefix in the
            # background (PIO valid=0, preferred=0 — RFC 4862 §5.5.3).
            # Without this, Windows keeps using the stale carrier v6 SLAAC
            # address until the previously-advertised preferred lifetime
            # expires (≥30 min with our default ra-param) — and when v6
            # disappears entirely the new dnsmasq has no enable-ra so no
            # RA is sent at all and the address effectively never goes
            # away on its own.  Symptom: SIM-swap to a v4-only carrier
            # and the Windows host still shows the previous v6 until a
            # forced /release6.
            if self._last_v6 and self._last_v6_prefix:
                asyncio.create_task(
                    self._send_deprecation_ra_v6(
                        self._last_v6, self._last_v6_prefix,
                    )
                )
        if v6_gone:
            # When v6 disappears entirely the per-instance whitelist must
            # also be torn down — the `if carrier_v6:` install branch
            # below is skipped so the old prefix would otherwise persist.
            await self._remove_src_whitelist_v6()
        if v4_gone:
            await self._remove_src_whitelist_v4()

        # Force the LAN interface admin-up before anything else: dnsmasq
        # with --bind-interfaces refuses to start on a DOWN netdev, and
        # `ip addr add` for the shadow / mgmt address fails silently if
        # the kernel netdev was never set up.
        await self._ensure_lan_link_up()

        # Apply ARP / rp_filter sysctls so the LAN port and wwan<N> do
        # not fight over the carrier IP (LAN-side ARP must be silent for
        # the carrier subnet; wwan<N> reverse-path must be permissive).
        await self._apply_passthrough_sysctls()

        # Ensure mgmt address is on the LAN interface (Policy B).
        await self._ensure_mgmt_address()

        # Attach shadow addresses from the carrier subnets so dnsmasq
        # finds a matching network for its dhcp-range.  Without this,
        # dnsmasq logs "no address range available" and silently drops
        # every DHCP/DHCPv6 request.
        await self._ensure_shadow_addrs(
            carrier_v4, carrier_v6, carrier_v6_prefix,
            carrier_v4_prefix,
        )

        # Render dnsmasq config + (re)start.
        await self._write_dnsmasq_conf(
            carrier_v4, carrier_v6, carrier_v6_prefix,
            ipv4_dns or [], ipv6_dns or [], bearer_mtu,
            carrier_v4_prefix,
        )
        # If the carrier IP changed in either family the dhcp-range
        # changed too, so a hard restart is required — SIGHUP would not
        # re-read the main config and dnsmasq would keep serving the old
        # range (and silently drop every DISCOVER on the new subnet).
        await self._start_or_reload_dnsmasq(
            force_restart=(v4_changed or v6_changed),
        )

        # Install policy-routing so inbound packets to the carrier IP that
        # arrive on wwan<N> are forwarded out the LAN interface to the
        # downstream device, while the address itself stays bound to wwan
        # (so locally-originated traffic still has a valid source).
        # Bump the kernel `local` table out of pref 0 first so our rule
        # at pref 12000 actually fires (otherwise `local` short-circuits
        # the lookup and packets are delivered to the router).
        await self._swap_local_table_priority()
        if carrier_v4:
            await self._install_inbound_route_v4(carrier_v4)
        if carrier_v6:
            await self._install_inbound_route_v6(carrier_v6, carrier_v6_prefix)

        # Install / refresh the persistent source-address whitelist on
        # FORWARD: drops any traffic from the LAN port whose source is
        # not the current carrier IP.  Mirrors PD's ip6tables egress
        # filter so a downstream device that clings to a stale address
        # cannot leak packets after an IP change.
        if carrier_v4:
            await self._install_src_whitelist_v4(carrier_v4)
        if carrier_v6:
            await self._install_src_whitelist_v6(carrier_v6, carrier_v6_prefix)

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
        self._last_v6_prefix = int(carrier_v6_prefix) if carrier_v6 else 0

        logger.info("passthrough: applied carrier IPs (v4=%s v6=%s/%s) → %s",
                    carrier_v4, carrier_v6, carrier_v6_prefix, self.cfg.interface,
                    extra=self._log_extra)

    async def teardown(self) -> None:
        """Stop dnsmasq, drop mgmt addr (if owned), clean up iptables
        and the policy-routing entries used for inbound forwarding."""
        # Send a burst of deprecation RAs FIRST, while dnsmasq is still
        # alive and the LAN interface still has the shadow v6 address —
        # otherwise the SLAAC client (Windows in particular) will keep
        # using the old carrier prefix until the previously-advertised
        # preferred lifetime expires (≥30 min).  Done in the background
        # so a slow burst doesn't delay the rest of teardown.  Skipped
        # silently when no v6 was ever applied.
        if self._last_v6 and self._last_v6_prefix:
            asyncio.create_task(
                self._send_deprecation_ra_v6(
                    self._last_v6, self._last_v6_prefix,
                )
            )

        # Force the downstream v4 client out of BOUND state BEFORE we
        # kill dnsmasq.  Without this, Windows (and other RFC-2131
        # clients) hold the carrier IP in `ipconfig` until the lease
        # expires (60 s default) — visible to the user as "still
        # connected" long after the bearer is gone.  See _force_release_v4
        # for the FORCERENEW + DHCPNAK mechanism.
        await self._force_release_v4()
        await self._stop_dnsmasq()
        await self._remove_mgmt_address()
        await self._remove_shadow_addrs()
        await self._unblock_v4_saddr(self._last_v4)
        await self._unblock_v6_saddr(self._last_v6)
        await self._remove_inbound_route_v4(self._inbound_v4_addr)
        await self._remove_inbound_route_v6(self._inbound_v6_addr)
        await self._restore_local_table_priority()
        await self._remove_src_whitelist_v4()
        await self._remove_src_whitelist_v6()
        await self._remove_mss_clamp()
        await self._restore_passthrough_sysctls()
        # NOTE: _last_v4 / _last_v6 / _last_v6_prefix are NOT cleared here.
        # teardown() runs during the bearer-disconnect debounce on a SIM
        # swap; the next apply() needs the previous IPs to detect the
        # change and run the full handoff sequence.  See the comment on
        # the fields in __init__ for the failure mode this prevents.
        logger.info("passthrough: torn down on %s",
                    self.cfg.interface or '<unset>', extra=self._log_extra)

    # ── dnsmasq lifecycle ───────────────────────────────────────────────
    async def _write_dnsmasq_conf(self, carrier_v4: Optional[str],
                                  carrier_v6: Optional[str],
                                  carrier_v6_prefix: int,
                                  ipv4_dns: list,
                                  ipv6_dns: list,
                                  bearer_mtu: Optional[int] = None,
                                  carrier_v4_prefix: int = 30) -> None:
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
        # 2-message DHCP exchange (RFC 4039 v4 rapid-commit + RFC 8415
        # §5.1 v6 rapid-commit).  Speeds up the initial handshake when the
        # downstream client also supports it.  Note: this is unrelated to
        # DHCPFORCERENEW (RFC 3203) / DHCPv6 Reconfigure (RFC 8415
        # §18.2.11), which are emitted out-of-band on IP change.
        lines.append("dhcp-rapid-commit")
        # Skip the ICMP-echo "is this address free?" check.  In passthrough
        # mode the carrier IP is bound to wwanN locally, so a ping from
        # the router (sourced from the shadow address on the LAN port)
        # routes back out wwanN and the carrier echoes it.  dnsmasq would
        # interpret that reply as "address in use" and refuse every
        # DISCOVER with `no address available`.  We *know* the address is
        # free for the downstream device because we just leased it from
        # the carrier; suppress the probe.
        lines.append("no-ping")

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
            start, end, netmask = _v4_pool_for(carrier_v4, carrier_v4_prefix)
            lines.append(f"dhcp-range=set:passthru4,{start},{end},{netmask},{lease}")
            # 'set:passthru' tag attached so we can target dhcp-options
            tag = 'passthru4'
            if self.cfg.mac:
                # Pinned MAC: only this client gets the carrier IP
                lines.append(
                    f"dhcp-host={self.cfg.mac},{carrier_v4},set:{tag},{lease}"
                )
            # Note: do NOT set `dhcp-lease-max=1` here.  That option is
            # global across the entire dnsmasq process and counts IPv4 +
            # IPv6 IA_NA + IPv6 IA_PD leases together — with =1, once the
            # downstream client takes the v6 NA lease, the v4 range reports
            # "no leases left" and NAKs every DHCPDISCOVER.  First-MAC-wins
            # for v4 is already naturally enforced by the single-IP
            # dhcp-range above (start == end == carrier_v4).
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
            # standard among commercial CPE passthrough products and is
            # accepted by Windows, macOS, iOS, Android, and Linux clients.
            lines.append(
                f"dhcp-option=tag:{tag},121,{gw_v4}/32,0.0.0.0,0.0.0.0/0,{gw_v4}"
            )

        # ── DHCPv6 + RA ──
        if carrier_v6:
            # DOCSIS-modem-equivalent IPv6 handoff:
            #
            #   * Carrier prefix ≤ /64 (the common case — Bell/AT&T/Verizon
            #     LTE/5G all hand out /64): advertise the prefix in RA with
            #     A=1 (SLAAC), exactly like a cable modem in passthrough.
            #     Windows / macOS / Linux SLAAC themselves an address in
            #     the carrier /64 and "just work" with no DHCPv6 dance.
            #     dnsmasq's `slaac` mode also runs DHCPv6 IA_NA on the same
            #     range for stateful clients (M=1).  The bearer's specific
            #     /128 is still pinned via dhcp-host when a MAC is given.
            #
            #   * Carrier prefix == /128 (no prefix at all): IA_NA-only
            #     fallback — there is no /64 to SLAAC into, so we hand out
            #     just the bearer /128.
            if 0 < carrier_v6_prefix <= 64:
                pd_net = ipaddress.ip_network(
                    f"{carrier_v6}/{carrier_v6_prefix}", strict=False
                )
                prefix_base = str(pd_net.network_address)
                # slaac mode: RA prefix info has A=1 (autonomous) + L=1 (on-link).
                # dnsmasq additionally serves IA_NA from the same range so
                # DHCPv6-only clients get a stateful lease.
                lines.append(
                    f"dhcp-range=set:passthru6,{prefix_base},slaac,"
                    f"{carrier_v6_prefix},{lease}"
                )
                # IA_PD — offer the carrier prefix to downstream routers
                # that request it (RFC 8415 §18.2.4: server only includes
                # IA_PD if the client asked for one, so plain hosts like
                # Windows/Linux PCs never see this).  This is the standard
                # "prefix passthrough" handoff used by commercial cellular CPE.
                lines.append(
                    f"dhcp-range=set:passthru6pd,{prefix_base},{prefix_base},"
                    f"{carrier_v6_prefix},{lease}"
                )
            else:
                # /128 carrier — IA_NA-only, no SLAAC possible
                lines.append(
                    f"dhcp-range=set:passthru6,{carrier_v6},{carrier_v6},"
                    f"128,{lease}"
                )
            lines.append("enable-ra")
            # ra-param=<if>,[mtu:N,]<ra-interval>,<router-lifetime>
            # MTU advertised in RA — must match the bearer MTU or v6 PMTUD
            # black-holes for any path that touches the bearer.
            #
            # ra-interval=0 means dnsmasq only replies to RS (no unsolicited
            # RAs), so once the router-lifetime expires the downstream loses
            # its default route until it solicits again — Windows in
            # particular does NOT re-solicit promptly and ends up with v6
            # connectivity but no default gateway.  Use a 60 s unsolicited
            # interval and a 30 min lifetime so default-route refresh is
            # automatic and resilient to short blackouts.
            ra_mtu = int(bearer_mtu) if (bearer_mtu and bearer_mtu > 0) else 1500
            lines.append(f"ra-param={self.cfg.interface},mtu:{ra_mtu},60,1800")
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

    async def _start_or_reload_dnsmasq(self, force_restart: bool = False) -> None:
        """Spawn dnsmasq if not running; otherwise SIGHUP to reload.

        With ``--bind-interfaces`` dnsmasq must find the listen interface
        present AND with at least one address at startup.  If the LAN
        interface (or its mgmt address) was just brought up, the kernel
        may take a moment to settle — retry up to ~3 s before giving up.

        When ``force_restart`` is True, the running instance (if any) is
        killed and a fresh process is spawned.  This is REQUIRED whenever
        ``dhcp-range`` changes — dnsmasq's SIGHUP handler does NOT
        re-read the main config file (only ``/etc/hosts``, ``/etc/ethers``
        and ``--dhcp-hostsfile``/``--addn-hosts``), so on a carrier IP
        change the new dhcp-range would otherwise be ignored and every
        DHCPDISCOVER would be silently dropped because the old range
        no longer matches any address on the LAN interface.
        """
        pid = self._read_pid()
        if force_restart and pid and self._pid_alive(pid):
            logger.info(
                "passthrough: dhcp-range changed — restarting dnsmasq pid=%s",
                pid, extra=self._log_extra,
            )
            await self._stop_dnsmasq()
            pid = None
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

    # ── LAN link-up + sysctls ──────────────────────────────────────────
    async def _ensure_lan_link_up(self) -> None:
        """Force the designated LAN interface admin-up.  No-op if already up."""
        if not self.cfg.interface:
            return
        await _run('ip', 'link', 'set', 'dev', self.cfg.interface, 'up')

    async def _apply_passthrough_sysctls(self) -> None:
        """Apply ARP/rp_filter/forwarding tweaks for DOCSIS-style passthrough.

        Passthrough deliberately puts two unrelated subnets on the LAN
        port: the mgmt prefix (e.g. 192.168.200.0/24) and the carrier
        shadow prefix (e.g. 10.105.235.72/30 from the bearer's /30).
        The downstream device gets the carrier IP with a /32 mask and
        a DHCP option-121 host route to the mgmt gateway, then ARPs
        for the mgmt gateway with src=<carrier-IP> — i.e. cross-subnet
        relative to the LAN port's mgmt address.

        Strict ARP defaults (arp_ignore=2, arp_filter=1, arp_announce=2)
        cause the kernel to refuse to reply to that cross-subnet ARP,
        which manifests as "destination host unreachable" on the
        downstream client even though IPv6 (link-local next-hop) works.
        Relax these on the LAN port:
          - arp_ignore=0    (reply to any local-IP ARP regardless of src)
          - arp_filter=0    (no per-route ARP suppression)
          - arp_announce=0  (no strict source-IP selection)
        rp_filter=1 (strict) on wwan<N> can drop the carrier gateway's
        reply if reverse-path picks the LAN port; same risk on the LAN
        port for the carrier-sourced inbound packets handed off via the
        pref-12000 policy rule, so loosen both:
          - LAN: rp_filter=2 (loose)
          - wwan<N>: rp_filter=2 (loose)
        Forwarding must be on (globally for v4, and on both wwan/LAN
        for v6 since v6 forwarding is per-interface gated) so the
        policy-routing rule that diverts inbound carrier-IP packets to
        the LAN actually forwards them rather than dropping at the IP
        layer:
          - v4: net.ipv4.ip_forward=1 (global)
          - v6: forwarding=1 on all, wwan<N>, and LAN (per-interface)

        Prior values are snapshotted into ``self._sysctl_saved`` so
        teardown can restore them faithfully (admin may have had a
        non-default global ip_forward setting).

        Idempotent and best-effort — failures are logged but do not abort.
        """
        if not self.cfg.interface:
            return
        keys = [
            (f'net.ipv4.conf.{self.cfg.interface}.arp_ignore', '0'),
            (f'net.ipv4.conf.{self.cfg.interface}.arp_filter', '0'),
            (f'net.ipv4.conf.{self.cfg.interface}.arp_announce', '0'),
            (f'net.ipv4.conf.{self.cfg.interface}.rp_filter', '2'),
            (f'net.ipv4.conf.{self._wwan_iface}.rp_filter', '2'),
            ('net.ipv4.ip_forward', '1'),
            ('net.ipv6.conf.all.forwarding', '1'),
            (f'net.ipv6.conf.{self._wwan_iface}.forwarding', '1'),
            (f'net.ipv6.conf.{self.cfg.interface}.forwarding', '1'),
        ]
        # Snapshot existing values so teardown is non-destructive
        if not hasattr(self, '_sysctl_saved') or self._sysctl_saved is None:
            self._sysctl_saved = {}
        for key, _val in keys:
            if key in self._sysctl_saved:
                continue
            rc, out, _err = await _run('sysctl', '-n', key)
            if rc == 0:
                self._sysctl_saved[key] = out.strip()
        for key, val in keys:
            await _run('sysctl', '-q', '-w', f'{key}={val}')

    async def _restore_passthrough_sysctls(self) -> None:
        """Best-effort: restore previously snapshotted sysctls on teardown."""
        if not self.cfg.interface:
            return
        saved = getattr(self, '_sysctl_saved', None) or {}
        # Fallback defaults if snapshot is missing for any key
        defaults = {
            f'net.ipv4.conf.{self.cfg.interface}.arp_ignore': '0',
            f'net.ipv4.conf.{self.cfg.interface}.arp_filter': '0',
            f'net.ipv4.conf.{self.cfg.interface}.arp_announce': '0',
            f'net.ipv4.conf.{self.cfg.interface}.rp_filter': '1',
            f'net.ipv4.conf.{self._wwan_iface}.rp_filter': '1',
        }
        for key, fallback in defaults.items():
            val = saved.get(key, fallback)
            await _run('sysctl', '-q', '-w', f'{key}={val}')
        # For forwarding keys we only restore if we have a snapshot —
        # otherwise leave the kernel as-is (don't risk turning off
        # forwarding the admin had explicitly enabled).
        for key in (
            'net.ipv4.ip_forward',
            'net.ipv6.conf.all.forwarding',
            f'net.ipv6.conf.{self._wwan_iface}.forwarding',
            f'net.ipv6.conf.{self.cfg.interface}.forwarding',
        ):
            if key in saved:
                await _run('sysctl', '-q', '-w', f'{key}={saved[key]}')
        self._sysctl_saved = {}

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

    # ── shadow addresses (dnsmasq dhcp-range matcher) ───────────────────
    @staticmethod
    def _pick_shadow_v4(carrier_v4: str,
                        carrier_prefix: int = 30) -> Optional[str]:
        """Pick an unused host from the carrier subnet to attach to the LAN
        interface so dnsmasq has a matching subnet for its dhcp-range.

        The shadow's prefix must be the SAME as the netmask used in the
        dnsmasq dhcp-range (see _v4_pool_for) so the two networks line up
        from dnsmasq's point of view.  Returns 'a.b.c.d/N' or None if a
        sensible peer cannot be found.
        """
        ip = ipaddress.ip_address(carrier_v4)
        plen = max(1, min(int(carrier_prefix or 30), 30))
        while plen >= 1:
            net = ipaddress.ip_network(f'{carrier_v4}/{plen}', strict=False)
            if ip != net.network_address and ip != net.broadcast_address:
                for host in net.hosts():
                    if host != ip:
                        return f'{host}/{net.prefixlen}'
            plen -= 1
        return None

    @staticmethod
    def _pick_shadow_v6(carrier_v6: str, prefix: int) -> Optional[str]:
        """Pick a v6 host inside the carrier prefix for the LAN interface.

        Uses the carrier-prefix network address + 1, unless that equals
        the carrier IP, in which case + 2.  Returns 'addr/prefix' or None.
        """
        if not carrier_v6 or prefix <= 0 or prefix >= 128:
            return None
        try:
            net = ipaddress.ip_network(f'{carrier_v6}/{prefix}', strict=False)
        except ValueError:
            return None
        carrier = ipaddress.ip_address(carrier_v6)
        cand = net.network_address + 1
        if cand == carrier:
            cand = net.network_address + 2
        return f'{cand}/{net.prefixlen}'

    async def _ensure_shadow_addrs(self, carrier_v4: Optional[str],
                                   carrier_v6: Optional[str],
                                   carrier_v6_prefix: int,
                                   carrier_v4_prefix: int = 30) -> None:
        """Attach (or refresh) shadow addresses on the LAN interface.

        Idempotent: if the desired shadow is already attached, no-op.  If
        a stale shadow from a previous carrier IP is attached, replace it.
        """
        # ── v4 ──
        want_v4 = (self._pick_shadow_v4(carrier_v4, carrier_v4_prefix)
                   if carrier_v4 else None)
        if want_v4 != self._shadow_v4:
            await self._remove_shadow_v4()
            if want_v4:
                rc, _, err = await _run(
                    'ip', 'addr', 'add', want_v4,
                    'dev', self.cfg.interface, 'noprefixroute',
                )
                if rc == 0:
                    self._shadow_v4 = want_v4
                    logger.info(
                        "passthrough: shadow v4 %s on %s (dnsmasq subnet match)",
                        want_v4, self.cfg.interface, extra=self._log_extra,
                    )
                else:
                    logger.warning(
                        "passthrough: failed to add shadow v4 %s on %s: %s",
                        want_v4, self.cfg.interface, err.strip(),
                        extra=self._log_extra,
                    )

        # ── v6 ──
        want_v6 = (self._pick_shadow_v6(carrier_v6, carrier_v6_prefix)
                   if carrier_v6 else None)
        if want_v6 != self._shadow_v6:
            await self._remove_shadow_v6()
            if want_v6:
                rc, _, err = await _run(
                    'ip', '-6', 'addr', 'add', want_v6,
                    'dev', self.cfg.interface, 'noprefixroute',
                )
                if rc == 0:
                    self._shadow_v6 = want_v6
                    logger.info(
                        "passthrough: shadow v6 %s on %s (dnsmasq subnet match)",
                        want_v6, self.cfg.interface, extra=self._log_extra,
                    )
                else:
                    logger.warning(
                        "passthrough: failed to add shadow v6 %s on %s: %s",
                        want_v6, self.cfg.interface, err.strip(),
                        extra=self._log_extra,
                    )

    async def _remove_shadow_v4(self) -> None:
        if self._shadow_v4 and self.cfg.interface:
            await _run('ip', 'addr', 'del', self._shadow_v4,
                       'dev', self.cfg.interface)
        self._shadow_v4 = None

    async def _remove_shadow_v6(self) -> None:
        if self._shadow_v6 and self.cfg.interface:
            await _run('ip', '-6', 'addr', 'del', self._shadow_v6,
                       'dev', self.cfg.interface)
        self._shadow_v6 = None

    async def _remove_shadow_addrs(self) -> None:
        await self._remove_shadow_v4()
        await self._remove_shadow_v6()

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

    async def _wipe_leases_file(self) -> None:
        """Delete the per-instance dnsmasq leases file.

        Called from the v4-changed handoff path so a stale MAC→old-IP
        entry from the previous carrier cannot be re-loaded by dnsmasq
        on its next start (or referenced via SIGHUP) and offered back to
        the same MAC after a Windows /release && /renew cycle.  dnsmasq
        rebuilds the file from new DHCPACKs as clients re-lease.
        """
        try:
            self._leases_path().unlink()
            logger.info("passthrough: wiped stale leases file %s",
                        self._leases_path(), extra=self._log_extra)
        except FileNotFoundError:
            pass
        except OSError as exc:
            logger.warning("passthrough: failed to wipe leases file %s: %s",
                           self._leases_path(), exc, extra=self._log_extra)

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

    async def _force_release_v4(self) -> None:
        """Push the downstream v4 client out of BOUND state immediately.

        Used by ``teardown()`` so the carrier IP disappears from the
        Windows host's ``ipconfig`` (and from the kernel's routing /
        ARP tables) the moment the bearer goes away — without waiting
        for the natural lease expiry (default 60 s).

        Sequence:

        1. Rewrite dnsmasq with a single dummy ``dhcp-range`` whose
           subnet does NOT contain the carrier IP.
        2. Hard-restart dnsmasq with that NAK-only config.
        3. Send DHCPFORCERENEW (RFC 3203) via ``dhcp_release2`` to
           every v4 lease.
        4. The client unicasts a DHCPREQUEST for its current IP.
           dnsmasq sees the request is for an IP outside the dummy
           range and replies with DHCPNAK (RFC 2131 §4.3.2).
        5. Client transitions BOUND → INIT and clears its lease.

        Total time: ~2 s from teardown start to Windows showing
        ``Media disconnected`` for IPv4.

        Skipped silently when:
        - no v4 was ever applied (no leases on file),
        - ``dhcp_release2`` is not installed,
        - the LAN interface is not configured.
        """
        leases = self._read_active_v4_leases()
        if not leases:
            return
        if shutil.which('dhcp_release2') is None:
            return  # already-warned via _force_renew_v4
        if not self.cfg.interface:
            return

        # Write a NAK-only config: dnsmasq is alive on the LAN but its
        # only dhcp-range is a single unallocatable address (RFC 5736
        # IETF Protocol Assignments block).  Any DHCPREQUEST for the
        # real carrier IP is therefore outside the configured range
        # and gets a DHCPNAK.  bind-interfaces + the existing pid/lease
        # paths keep the rest of dnsmasq's behaviour identical.
        lines = [
            "# auto-generated NAK-only mode by interfaces_wwan_passthrough.py",
            f"interface={self.cfg.interface}",
            "bind-interfaces",
            "except-interface=lo",
            "no-resolv",
            "no-hosts",
            f"pid-file={self._pid_path()}",
            f"dhcp-leasefile={self._leases_path()}",
            "port=0",
            "quiet-dhcp",
            "dhcp-authoritative",
            "no-ping",
            # Single-address dummy range (RFC 5736 reserved 192.0.0.0/24).
            # Any DHCPREQUEST for an IP outside this range is NAK'd.
            "dhcp-range=192.0.0.255,192.0.0.255,255.255.255.255,30",
        ]
        try:
            self._conf_path().write_text('\n'.join(lines) + '\n')
        except OSError as exc:
            logger.warning("passthrough: NAK-only conf write failed: %s",
                          exc, extra=self._log_extra)
            return

        await self._start_or_reload_dnsmasq(force_restart=True)
        # Brief settle window: dnsmasq needs to (re)bind the listening
        # socket on the LAN before we trigger the FORCERENEW burst.
        await asyncio.sleep(0.3)

        for mac, ip in leases:
            await _run('dhcp_release2', '--iface', self.cfg.interface,
                       '--client', mac, '--ip', ip)
        logger.info(
            "passthrough: DHCPFORCERENEW + NAK-only dnsmasq → %d v4 client(s) "
            "released",
            len(leases), extra=self._log_extra,
        )

        # Give the client time to receive FORCERENEW, send DHCPREQUEST,
        # receive DHCPNAK, and transition to INIT.  ~1.5 s is enough on
        # a quiet LAN; tcpdump on Windows shows the full cycle in
        # roughly 200-400 ms but we add slack for buffered paths.
        await asyncio.sleep(1.5)

    async def _reconfigure_v6(self) -> None:
        """Trigger DHCPv6 Reconfigure.  dnsmasq does this automatically on
        SIGHUP when the dhcp-range changes — our SIGHUP path already covered
        that.  Nothing further to do here, but kept as a hook for future
        explicit Reconfigure messaging."""
        logger.debug("passthrough: v6 Reconfigure handled via dnsmasq SIGHUP",
                     extra=self._log_extra)

    async def _send_deprecation_ra_v6(
        self, old_v6: str, old_prefix_len: int,
        count: int = 5, interval: float = 1.0,
    ) -> None:
        """Emit a burst of ICMPv6 Router Advertisements carrying a Prefix
        Information Option for ``old_v6/old_prefix_len`` with both valid
        and preferred lifetimes set to zero.

        This is the RFC 4862 §5.5.3 / §6.2.5 mechanism that signals
        SLAAC hosts to immediately deprecate (preferred=0) and remove
        (valid=0) the old carrier prefix.  Windows in particular will
        otherwise keep using a stale carrier IPv6 address until the
        previously-advertised preferred lifetime expires (≥30 min with
        our default ra-param, longer in some Windows builds) — and when
        v6 disappears on a SIM swap to a v4-only carrier the new dnsmasq
        has no `enable-ra` line at all, so without this helper no RA is
        ever sent and the host never deprecates.

        Sent as a small burst (default 5 × 1 s) so a single dropped /
        coalesced RA cannot leave the host stuck on the old address.
        Router Lifetime is set to 0 so we also cancel ourselves as the
        v6 default router for the duration of the burst — when the new
        carrier has v6, the new dnsmasq's RA stream re-establishes the
        default route promptly and the new prefix takes over.
        """
        if old_prefix_len <= 0 or old_prefix_len > 128:
            return
        lan = self.cfg.interface
        if not lan:
            return
        try:
            ifindex = socket.if_nametoindex(lan)
        except OSError as exc:
            logger.warning(
                "passthrough: deprecation RA: if_nametoindex(%s) failed: %s",
                lan, exc, extra=self._log_extra,
            )
            return
        try:
            prefix_net = ipaddress.IPv6Network(
                f"{old_v6}/{old_prefix_len}", strict=False,
            )
        except ValueError:
            return
        prefix_bytes = prefix_net.network_address.packed

        # PIO (RFC 4861 §4.6.2): type=3, len=4 (32 bytes), prefix_length,
        # flags = L|A = 0xC0 (on-link + autonomous).  CRITICAL: A=1 is
        # required — RFC 4862 §5.5.3(a) says hosts MUST silently ignore
        # any PIO with A=0, so a "withdrawal" PIO with flags=0 has no
        # effect on existing SLAAC addresses on the host.  Setting A=1
        # with valid=0 preferred=0 is the correct §5.5.3 deprecation
        # signal — Windows / macOS / Linux honor it within ~1 RTT.
        # valid lifetime=0, preferred lifetime=0, reserved2=0, prefix.
        pio = struct.pack(
            '!BBBBIII16s',
            3, 4, old_prefix_len, 0xC0,
            0, 0, 0, prefix_bytes,
        )
        # RA header (RFC 4861 §4.2): type=134, code=0, checksum=0
        # (kernel fills for IPPROTO_ICMPV6 raw sockets), cur_hop_limit=64,
        # M=0 O=0, router_lifetime=0, reachable_time=0, retrans_timer=0.
        ra = struct.pack('!BBHBBHII', 134, 0, 0, 64, 0, 0, 0, 0) + pio

        def _send_one() -> bool:
            try:
                with socket.socket(
                    socket.AF_INET6, socket.SOCK_RAW, socket.IPPROTO_ICMPV6,
                ) as s:
                    s.setsockopt(
                        socket.IPPROTO_IPV6,
                        socket.IPV6_MULTICAST_HOPS, 255,
                    )
                    s.setsockopt(
                        socket.IPPROTO_IPV6,
                        socket.IPV6_MULTICAST_IF,
                        struct.pack('I', ifindex),
                    )
                    s.sendto(ra, (f'ff02::1%{lan}', 0))
                return True
            except OSError as exc:
                logger.warning(
                    "passthrough: deprecation RA send failed on %s: %s",
                    lan, exc, extra=self._log_extra,
                )
                return False

        loop = asyncio.get_running_loop()
        sent = 0
        for i in range(count):
            if await loop.run_in_executor(None, _send_one):
                sent += 1
            else:
                break
            if i < count - 1:
                await asyncio.sleep(interval)
        if sent:
            logger.info(
                "passthrough: sent %d deprecation RA(s) for old prefix "
                "%s/%d on %s (valid=0 preferred=0)",
                sent, old_v6, old_prefix_len, lan,
                extra=self._log_extra,
            )

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

    async def _swap_local_table_priority(self) -> None:
        """Move the kernel `local` table from pref 0 to a high pref.

        This is the canonical fix for the "passthrough rule never fires"
        problem: by default `local` sits at pref 0 — *before* any user
        rule — so any packet arriving on wwan<N> with dst == carrier IP
        is matched locally and delivered to the router instead of being
        forwarded to the downstream device.  Moving `local` to pref
        ``PASSTHRU_LOCAL_TABLE_PRIO`` (32765) makes user rules fire
        first while still leaving `local` consulted for everything else.

        Idempotent and refcounted: only the first PassthroughManager
        instance that sees the rising edge (refcount 0→1) actually
        performs the rule swap; subsequent calls just bump the count.
        """
        global _LOCAL_TABLE_SWAP_REFCOUNT
        if self._owns_local_table_swap:
            return
        if _LOCAL_TABLE_SWAP_REFCOUNT > 0:
            # Another instance already did the swap — just join the
            # refcount so we do not double-restore on teardown.
            _LOCAL_TABLE_SWAP_REFCOUNT += 1
            self._owns_local_table_swap = True
            return

        # Inspect current state.  If pref 0 `local` is missing (someone
        # else already moved it manually, or a previous run left it
        # moved), do not try to delete it; just record that we joined.
        for family_flag in ('-4', '-6'):
            rc, out, _ = await _run('ip', family_flag, 'rule', 'show')
            if rc != 0:
                continue
            has_pref0_local = any(
                line.lstrip().startswith('0:') and 'lookup local' in line
                for line in out.splitlines()
            )
            if has_pref0_local:
                # Add the new high-pref entry first, then drop pref 0,
                # so there is never a window with no `local` lookup.
                await _run('ip', family_flag, 'rule', 'add',
                           'pref', str(PASSTHRU_LOCAL_TABLE_PRIO),
                           'lookup', 'local')
                await _run('ip', family_flag, 'rule', 'del',
                           'pref', '0', 'lookup', 'local')

        _LOCAL_TABLE_SWAP_REFCOUNT += 1
        self._owns_local_table_swap = True
        logger.info(
            "passthrough: moved kernel `local` table pref 0 → %d",
            PASSTHRU_LOCAL_TABLE_PRIO, extra=self._log_extra,
        )

    async def _restore_local_table_priority(self) -> None:
        """Inverse of _swap_local_table_priority — only acts when the
        last passthrough instance tears down."""
        global _LOCAL_TABLE_SWAP_REFCOUNT
        if not self._owns_local_table_swap:
            return
        self._owns_local_table_swap = False
        _LOCAL_TABLE_SWAP_REFCOUNT -= 1
        if _LOCAL_TABLE_SWAP_REFCOUNT > 0:
            return
        if _LOCAL_TABLE_SWAP_REFCOUNT < 0:
            # Defensive: never let it go negative.
            _LOCAL_TABLE_SWAP_REFCOUNT = 0

        for family_flag in ('-4', '-6'):
            await _run('ip', family_flag, 'rule', 'add',
                       'pref', '0', 'lookup', 'local')
            await _run('ip', family_flag, 'rule', 'del',
                       'pref', str(PASSTHRU_LOCAL_TABLE_PRIO),
                       'lookup', 'local')
        logger.info(
            "passthrough: restored kernel `local` table to pref 0",
            extra=self._log_extra,
        )

    async def _install_inbound_route_v4(self, carrier_v4: str) -> None:
        if self._inbound_v4_addr == carrier_v4:
            return
        # Tear down any prior entry first
        await self._remove_inbound_route_v4(self._inbound_v4_addr)
        # The kernel auto-creates `local <carrier_v4>/32 dev wwanN table
        # local` when the FSM did `ip addr add` on wwan<N>.  The local
        # table is consulted at pref 0 — *before* our rule at pref
        # ~12000 — so without removing it every inbound packet for the
        # carrier IP is delivered locally instead of being forwarded to
        # the downstream device.  Drop the local entry; the address
        # itself stays on wwan<N> so the kernel can still use it as a
        # source for locally-originated traffic (ModemManager probes,
        # NTP, carrier DNS, etc.).  Outbound source-selection does NOT
        # consult the local table.
        await _run('ip', '-4', 'route', 'del',
                   'local', f'{carrier_v4}/32',
                   'dev', self._wwan_iface, 'table', 'local')
        # Route in the per-FSM table
        await _run('ip', '-4', 'route', 'replace',
                   f'{carrier_v4}/32', 'dev', self.cfg.interface,
                   'table', str(self._table_id))
        # Rule that diverts traffic destined to the carrier IP into the
        # per-FSM table.  Intentionally NOT gated on `iif <wwan>`: the
        # carrier IP unambiguously belongs to the downstream device, so
        # *any* packet (inbound from wwan, OR locally-originated from
        # the router itself — e.g. an HTTPS reply from the mgmt address
        # back to the downstream's source IP) must be forwarded out the
        # LAN port.  Without this, the kernel's main table picks the
        # carrier-prefix /30 connected route via wwan (installed by the
        # FSM's `ip addr add`) and ships the reply back to the carrier
        # instead of to the downstream, breaking management access via
        # the passthrough port (https://192.168.200.1, ICMP, etc.).
        await _run('ip', '-4', 'rule', 'add',
                   'priority', str(self._rule_prio),
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
                   'to', f'{carrier_v4}/32',
                   'lookup', str(self._table_id))
        await _run('ip', '-4', 'route', 'del',
                   f'{carrier_v4}/32', 'dev', self.cfg.interface,
                   'table', str(self._table_id))
        if self._inbound_v4_addr == carrier_v4:
            self._inbound_v4_addr = None

    async def _install_inbound_route_v6(self, carrier_v6: str,
                                        carrier_v6_prefix: int = 128) -> None:
        # DOCSIS-style: when the carrier delivers a usable prefix (≤ /64),
        # route the WHOLE prefix to the LAN port — not just the bearer's
        # /128.  Otherwise any address Windows / Linux / macOS SLAACs in
        # the carrier /64 (which is the normal DOCSIS handoff behavior)
        # would arrive on wwan<N> and be silently dropped because no /128
        # entry matches.
        if 0 < carrier_v6_prefix <= 64:
            net = ipaddress.ip_network(
                f"{carrier_v6}/{carrier_v6_prefix}", strict=False
            )
            target = f"{net.network_address}/{net.prefixlen}"
        else:
            target = f"{carrier_v6}/128"
        if self._inbound_v6_addr == target:
            return
        await self._remove_inbound_route_v6(self._inbound_v6_addr)
        # See v4 sibling for rationale: the kernel auto-installs
        # `local <carrier_v6>/128 dev wwanN table local` when the FSM
        # added the address; remove it so our pref-12000 rule actually
        # diverts inbound traffic to the LAN port instead of being
        # short-circuited by the local-table lookup at pref 0.
        await _run('ip', '-6', 'route', 'del',
                   'local', f'{carrier_v6}/128',
                   'dev', self._wwan_iface, 'table', 'local')
        await _run('ip', '-6', 'route', 'replace',
                   target, 'dev', self.cfg.interface,
                   'table', str(self._table_id))
        # See v4 sibling: rule is intentionally NOT gated on iif so that
        # locally-originated replies (HTTPS, ICMPv6, etc.) from the mgmt
        # address back to the downstream also exit via the LAN port.
        await _run('ip', '-6', 'rule', 'add',
                   'priority', str(self._rule_prio),
                   'to', target,
                   'lookup', str(self._table_id))
        self._inbound_v6_addr = target
        logger.info(
            "passthrough: inbound v6 route installed — %s arriving on %s → %s",
            carrier_v6, self._wwan_iface, self.cfg.interface,
            extra=self._log_extra,
        )

    async def _remove_inbound_route_v6(self, carrier_v6: Optional[str]) -> None:
        # carrier_v6 here is the cached *target* string, which may be
        # either '<addr>/128' (carriers that only hand out /128 on the
        # bearer) or '<prefix_base>/<plen>' (DOCSIS-style ≤/64 carriers).
        if not carrier_v6:
            return
        target = carrier_v6 if '/' in carrier_v6 else f'{carrier_v6}/128'
        await _run('ip', '-6', 'rule', 'del',
                   'priority', str(self._rule_prio),
                   'to', target,
                   'lookup', str(self._table_id))
        await _run('ip', '-6', 'route', 'del',
                   target, 'dev', self.cfg.interface,
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

    async def _install_src_whitelist_v6(self, carrier_v6: str,
                                        carrier_v6_prefix: int = 128) -> None:
        chain = self._src_chain_v6()
        if self._src_whitelist_v6_active:
            await _run('ip6tables', '-F', chain)
        else:
            await _run('ip6tables', '-N', chain)
            await _run('ip6tables', '-I', 'FORWARD', '1',
                       '-i', self.cfg.interface, '-j', chain)
            self._src_whitelist_v6_active = True
        # Whitelist the entire carrier prefix, not just the bearer's /128.
        # Downstream clients (Windows/Linux/macOS/etc.) generate their own
        # IID inside the /64 via SLAAC or DHCPv6 IA_NA, so any packet from
        # an IID other than the bearer's would otherwise be dropped here.
        # Cap prefix at /64 — anything shorter than that on the bearer is
        # still treated as a /64 LAN scope for source filtering.
        try:
            net = ipaddress.ip_network(
                f"{carrier_v6}/{min(int(carrier_v6_prefix), 64)}",
                strict=False,
            )
            allowed_src = str(net)
        except (ValueError, TypeError):
            allowed_src = carrier_v6
        await _run('ip6tables', '-A', chain, '-s', allowed_src, '-j', 'RETURN')
        # NDP / link-local must still be permitted for the LAN to function
        await _run('ip6tables', '-A', chain, '-s', 'fe80::/10', '-j', 'RETURN')
        await _run('ip6tables', '-A', chain, '-j', 'DROP')
        logger.info(
            "passthrough: v6 src whitelist active on %s — only %s + link-local permitted",
            self.cfg.interface, allowed_src, extra=self._log_extra,
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
    # Default ON (industry-standard for cellular CPE passthrough
    # implementations).  Disable per-interface via:
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
