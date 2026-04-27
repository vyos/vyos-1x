# VyOS WWAN — Feature Roadmap

Forward-looking work items for the WWAN subsystem.  Each item is independently
shippable.  Listed roughly in priority order; reorder as customer asks change.

---

## Stage 0 — Done / In tree

- [x] FSM-native PD design (see `wwan-fsm-pd-design.md`):
      `dhcpv6-options pd N interface X sla-id Y` honored by FSM, no dhcp6c.
- [x] SIM failover on live state transitions (`_handle_failed_state_event`).
- [x] SIM failover on attach when modem is *already* in FAILED/sim-missing
      (`_dispatch_initial_modem_state`).
- [x] Carrier-friendly retry/backoff defaults
      (`[600, 1800, 3600, 7200]`, max 7200, cooldown 600, backoff 3600).
- [x] AlertBus + envelope (see `docs/alerts/ROADMAP.md` for alert delivery).

---

## Stage 1 — IP Passthrough modes (this document's primary focus)

Goal: parity with Cradlepoint / Sierra / Pepwave "IP Passthrough" so a
downstream router on an Ethernet port can receive the carrier-issued public
IPv4 and/or IPv6 transparently — looks to its WAN interface like it owns
the cellular bearer's address(es).

### Background — modes we will support

| Mode | What downstream gets | Carrier requirement | Multi-device |
|---|---|---|---|
| **PD (default v6)** | Sub-prefix carved from carrier prefix | IA_PD support (most enterprise APNs, growing on consumer) | Yes |
| **IPv4 single-address passthrough** | Carrier `/32` via DHCPv4 + proxy-ARP | Any (always works) | No (one device) |
| **IPv6 single-address passthrough** | Carrier `/128` via DHCPv6 IA_NA + proxy-NDP | Any (always works) | No (one device) |
| **IPv6 bridge `/64` (proxy-NDP stretch)** | Devices SLAAC from carrier `/64` | Any | Yes |

Cradlepoint default is **PD** (already in tree); they expose
**single-address passthrough** as the explicit opt-in mode.  We mirror that.

### 1.1 CLI — unified passthrough knob

- [ ] New XML node under `interfaces wwan wwanN`:
      ```
      passthrough {
        interface <ethN>          # required: downstream LAN interface
        mode <ipv4|ipv6|dual|ipv6-bridge>  # which family/families to pass through
        client-mac <MAC>          # required for ipv4 / dual (DHCP reservation key)
        client-duid <DUID>        # required for ipv6 / dual (DHCPv6 reservation key)
      }
      ```
- [ ] Mutually exclusive with v4 NAT/masquerade on same interface
      (validate in conf-mode).
- [ ] Mutually exclusive with `dhcpv6-options pd … interface <same eth>`
      for the v6 path (one or the other, not both).

### 1.2 IPv4 single-address passthrough (Flavour B / "Cradlepoint IP Passthrough")

- [ ] FSM: when passthrough mode includes `ipv4`, **suppress** `ip -4 addr add`
      on `wwan0` for the bearer address (keep link up, no v4 on WAN).
- [ ] Generate `kea-dhcp4` config on `<eth>` with single reservation:
      - `hw-address` = configured client-MAC
      - `ip-address` = carrier-assigned bearer v4 address
      - subnet = `/32` (or `/30` with synthetic neighbor for dumb clients)
      - `valid-lifetime` short (60–120 s) for fast IP-rotation recovery
      - default-gateway option = synthetic value (`<wan_ip - 1>` or carrier gw)
      - DNS option = carrier DNS list
      - MTU option (26) = bearer-negotiated MTU
- [ ] Add host route: `ip -4 route add <wan_ip>/32 dev <eth>`.
- [ ] Default v4 route: `default via <carrier-gw> dev <eth>` (gateway reachable
      via proxy-ARP on `<eth>`).
- [ ] Enable proxy-ARP on `<eth>` for the synthetic gateway IP:
      `sysctl net.ipv4.conf.<eth>.proxy_arp=1` plus a static published ARP entry.
- [ ] On bearer IP change (carrier rotates v4): regenerate kea reservation,
      replace host route, signal client via short lease so it re-DHCPs.
- [ ] On SIM failover: same path — new bearer IP, new reservation.
- [ ] Spool/quiesce traffic during the brief renumber window so existing
      flows don't black-hole.

### 1.3 IPv6 single-address passthrough (Flavour B for v6)

- [ ] FSM: when passthrough mode includes `ipv6`, **suppress** `ip -6 addr add`
      of the bearer `/128` on `wwan0` (keep link up, retain link-local).
- [ ] Generate `kea-dhcp6` config on `<eth>` with single IA_NA reservation:
      - `duid` = configured client-DUID
      - `ip-addresses` = `[<bearer_v6_addr>/128]`
      - `valid-lifetime` short (300 s); `preferred-lifetime` shorter
      - DNS, domain-search options propagated from carrier
- [ ] Add host route: `ip -6 route add <bearer_v6_addr>/128 dev <eth>`.
- [ ] Configure RA/`radvd` (or kea-dhcp6 RA) on `<eth>` advertising the
      carrier's link-local gateway as default route (or pass via DHCPv6
      option 23/24 if the downstream supports DHCPv6-only).
- [ ] Enable proxy-NDP via `ndppd`:
      - listen on `wwan0` for NS targeting `<bearer_v6_addr>`
      - reply with `<eth>` MAC (router answers on behalf of downstream)
      - on `<eth>`, proxy NS for the carrier's link-local gateway back toward
        `wwan0`
- [ ] `sysctl net.ipv6.conf.all.proxy_ndp=1` and per-interface flips.
- [ ] On bearer IP change: regenerate kea reservation, replace host route,
      update ndppd config, signal client via short lease.

### 1.4 IPv6 bridge `/64` (Flavour C — multiple downstream devices on carrier `/64`)

- [ ] FSM: keep `wwan0` link-local only; do not assign any GUA from the `/64`.
- [ ] Run `radvd` (or kea-dhcp6 RA) on `<eth>` advertising the carrier's
      `/64` with `M=0, O=0` (SLAAC).
- [ ] `ndppd` proxies *all* NDP for `<carrier-/64>` between `wwan0` and `<eth>`.
- [ ] No DHCPv6 server on `<eth>` (SLAAC-only).
- [ ] Track downstream neighbor cache to bound the proxy table.
- [ ] On carrier-prefix rotation: send RA with old prefix lifetime=0 + new
      prefix; clean up stale neighbor entries.

### 1.5 Dual-stack (`mode dual`)

- [ ] Combine 1.2 (v4 DHCP passthrough) + 1.3 (v6 single-`/128` passthrough)
      on the same downstream interface.
- [ ] kea-dhcp4 + kea-dhcp6 both running on `<eth>` with reservations keyed
      separately by MAC and DUID.

### 1.6 Operational visibility

- [ ] Extend `show interfaces wwan wwanN status` with a "Passthrough" section:
      mode, downstream interface, current lease state (assigned / lease
      expiry), client connection status (last DHCP request seen).
- [ ] Op-mode `show interfaces wwan wwanN passthrough` showing kea lease
      file, ndppd table, host routes.
- [ ] Alerts: emit `WWAN_PASSTHROUGH_LEASE_RENEWED`, `_LEASE_EXPIRED`,
      `_CLIENT_DISCONNECTED` via existing AlertBus.

### 1.7 Edge cases & failure handling

- [ ] Carrier IP change while passthrough lease is mid-renewal — coordinate
      so client doesn't get a stale IP.
- [ ] SIM failover with passthrough — entire passthrough config rebuilds
      against new bearer IP; expect ~5–10 s downtime acceptable.
- [ ] What happens when passthrough is configured but bearer is down — kea
      should not hand out a stale reservation.  Stop kea-dhcp{4,6} on
      `<eth>` while bearer down; restart on bearer up.
- [ ] Customer device offline / no DHCP request — keep config primed,
      no warnings (idle is fine).
- [ ] Validation: refuse passthrough config if `<eth>` already has v4 / v6
      addresses configured (would conflict with kea handing them out).

---

## Stage 2 — Carrier back-off awareness (deferred)

- [ ] Read `bearer.ConnectionError` and `Modem3gpp.RegistrationState` reject
      cause on every FAILED transition — log + classify.
- [ ] Three-bucket cause classification:
      - *Auth/subscription* (cause 7, 8, 11, 14, 25, 33) → trigger SIM failover,
        mark slot bad, suppress retry on this PLMN.
      - *Network-mandated wait* (cause 22 / T3346 active) → clamp retry
        interval to ≥ `failed_retry_max_interval`.
      - *Normal* → existing schedule.
- [ ] In-memory PLMN blacklist with TTL (no persistence in v1).
- [ ] Telit AT+CEER fallback only if QMI cause unavailable (deferred — not
      worth complexity for v1).

---

## Stage 3 — APN cascade safety (small)

- [ ] Cap APN candidate iteration in `connection_manager.try_apn_candidates`
      (slice `candidates[:4]`) to bound worst-case attempts/hour.
- [ ] CLI knob: `apn-discovery max-candidates <1-10>` (default 4).
- [ ] Token-bucket rate limiter at SIM level — refuse new connect attempts
      when bucket empty, regardless of FSM state.
- [ ] Surface bucket state in `show interfaces wwan wwanN detail`.

---

## Stage 4 — Bearer-flap detection (medium)

- [ ] Track bearer up→down→up transitions in a sliding window.
- [ ] If N flaps in M minutes (configurable, default 5/600s), enter
      "stabilization hold" — full retry pause for `failover_backoff_seconds`.
- [ ] Emit `WWAN_BEARER_FLAPPING` alert.

---

## Stage 5 — Persisted carrier knowledge (later)

- [ ] `/run/vyos/wwan/wwanN/blacklist.json` — PLMN/APN blacklist with TTLs,
      survives FSM restart.
- [ ] `/run/vyos/wwan/wwanN/last-cause.json` — last known reject cause per
      slot for op-mode display.
- [ ] Cleanup task on SIM change / config reload.

---

## Stage 6 — CLI ergonomics (medium)

- [ ] `show interfaces wwan wwanN passthrough` (covered in 1.6).
- [ ] `show interfaces wwan wwanN backoff` — current retry attempt, next
      retry time, last cause, blacklist contents.
- [ ] `clear interfaces wwan wwanN backoff` — reset retry state, blacklist,
      flap window (operator override after hardware change).

---

## References

- `python/vyos/utils/wwan/interfaces_wwan_state_machine.py` —
  `_apply_bearer_ip_configuration` (~line 8564) is where passthrough's
  `ip addr add` suppression branch goes.
- `python/vyos/utils/wwan/connection_manager.py` —
  `try_apn_candidates` (line 40) for Stage 3 candidate cap.
- `python/vyos/utils/wwan/wwan_configuration.py` —
  add `PassthroughConfig` dataclass alongside `EnhancedReconnectionConfig`.
- `interface-definitions/interfaces_wwan.xml.in` — add `<node name="passthrough">`
  block.
- Cradlepoint reference: their default is PD, opt-in is single-address
  passthrough — our design mirrors this.
- `wwan-fsm-pd-design.md` (memory) — existing PD design that passthrough
  mode coexists with.
