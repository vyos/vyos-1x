# VyOS WWAN Enhanced Interface — `set` Command Reference

This document defines the VyOS CLI `set` commands that map to the
`my_config.conf` parameters for the enhanced WWAN interface management service.

All commands are under:
```
set interfaces wwan <wwanN> ...
```

This definition replaces the upstream VyOS WWAN tree.  The legacy per-interface
`apn`, `authentication`, `connect-on-demand`, `address`, and `dhcp-options`
nodes are removed — those functions are handled per-SIM by the enhanced service.
`pd` is a direct child of the wwan interface for IPv6 Prefix Delegation
(FSM-native, no dhcp6c).  VyOS infrastructure features (`description`,
`disable`, `vrf`, `ip`, `ipv6`, `mirror`, `redirect`, `mtu`) are retained.

---

## Configuration Tree

```
interfaces
  └── wwan <wwanN>
        ├── description <text>                            # max 255 characters
        ├── disable                                       # valueless — admin shutdown
        ├── mtu <576-1500>                                # fallback MTU if carrier does not provide one (default: 1420); also ceiling
        ├── vrf <name>                                    # VRF instance name
        ├── redirect <interface>                          # redirect incoming packets to interface
        ├── connection-mode <always-on|connect-on-demand|dial-on-demand>
        ├── network-mode <auto|lte|5g|3g|2g>              # modem-level RAT selection
        │
        ├── ip                                            # IPv4 routing parameters (kernel-level)
        │     ├── adjust-mss <bytes|clamp-mss-to-pmtu>
        │     ├── disable-forwarding                      # valueless
        │     └── source-validation <strict|loose|disable>
        │
        ├── ipv6                                          # IPv6 routing parameters (kernel-level)
        │     ├── adjust-mss <bytes|clamp-mss-to-pmtu>
        │     ├── disable-forwarding                      # valueless
        │     └── source-validation <strict|loose|disable>
        │
        ├── pd <instance>                                # IPv6 prefix delegation (FSM-native, no dhcp6c)
        │     └── interface <name>                        # delegate to this LAN interface
        │           ├── address <id>                      # interface address within delegated prefix
        │           ├── sla-id <0-65535>                  # site-level aggregation ID
        │           └── sla-len <0-64>                    # bits for SLA subdivision (default: 64 − carrier prefix; 0 = whole prefix)
        │
        ├── pd-reconciliation-interval <seconds>          # safety-net timer for late-appearing LAN interfaces (default: 10)
        │
        ├── ip-passthrough                                # DOCSIS-modem-style: hand carrier IP to one downstream device
        │     ├── interface <name>                        # designated LAN port (required)
        │     ├── mac <xx:xx:xx:xx:xx:xx>                 # optional — pin to a specific downstream MAC (default: first-MAC-wins)
        │     ├── lease-time <30-600>                     # DHCP lease seconds (default: 60)
        │     ├── management-address <ipv4/prefix>        # FSM-provisioned mgmt v4 (default: 192.168.200.1/24; Policy B: skipped if 'interfaces ethernet <if> address' is set)
        │     ├── management-address-ipv6 <ipv6/prefix>   # FSM-provisioned mgmt v6 (default: fd00:6c61:6e30::1/64; same Policy B)
        │     ├── dns-server <ipv4|ipv6> (multi)          # override DNS advertised to downstream (precedence: user > carrier > 8.8.8.8/1.1.1.1)
        │     └── disable-mss-clamp                       # valueless — turn off TCP MSS clamp-to-PMTU on WWAN egress (on by default)
        │
        ├── mirror                                        # packet mirroring
        │     ├── ingress <interface>
        │     └── egress <interface>
        │
        ├── sim                                           # SIM management
        │     ├── primary-slot <1|2>
        │     │
        │     ├── slot <1|2>                              #   per-SIM tag node
        │     │     ├── disable                           #   valueless — turn off this slot (both slots enabled by default)
        │     │     ├── iccid <19-20 digits>              #   ICCID lock — only accept this SIM (tamper prevention)
        │     │     ├── apn <name>                        #   default: '' (use APN discovery)
        │     │     ├── username <text>                   #   default: ''
        │     │     ├── password <text>                   #   default: ''
        │     │     ├── auth-type <none|pap|chap|both>    #   default: none
        │     │     ├── pdp-type <ipv4|ipv6|ipv4v6>       #   default: ipv4v6
        │     │     ├── disable-roaming                   #   valueless — default: roaming enabled (set to turn off)
        │     │     ├── pin <4-8 digits>                  #   if set, SIM is auto-unlocked
        │     │     ├── puk <8 digits>                    #   PUK for auto-recovery (resets PIN)
        │     │     ├── supported-bands <all|band,band,...> #   default: all
        │     │     ├── preferred-carrier <MCCMNC|name>   #   e.g. '302610' or 'Bell'; default: '' (auto)
        │     │     ├── enable-network-scan               #   valueless — diagnostic scan; results in status
        │     │     ├── mtu <bytes>                       #   per-SIM MTU override (0 = use interface mtu)
        │     │     └── data-limit
        │     │           ├── size <bytes>                #   0 = unlimited (default)
        │     │           ├── action <none|disable|sim-failover|sim-failover-sticky>  #   default: none
        │     │           ├── billing-date <1-28>         #   default: 1
        │     │           └── warning <pct,pct,...>       #   e.g. '75,90,95'; empty = no warnings
        │     │
        │     ├── sim-failback
        │     |     ├── disable                           #   valueless — turn off failback
        │     |     └── check-interval <seconds>          #   default: 600
        │     │
        │     └── sim-failover
        │           ├── disable                           #   valueless — turn off failover
        │           ├── connect-retries <count>           #   default: 3
        │           ├── revert-timer <seconds>            #   default: 300
        │           ├── signal-loss-timer <seconds>       #   default: 60
        │           └── signal-threshold <dBm>            #   default: -90
        │
        ├── apn-discovery
        │     └── disable                                #   valueless — disable Android APN DB (enabled by default)
        │
        ├── reconnection
        │     ├── disable-enhanced                        #   valueless — fall back to basic fixed-interval reconnection (enhanced by default)
        │     ├── signal-threshold <dBm>                  #   default: -85
        │     ├── retry-interval
        │     │     ├── good-signal <seconds>             #   default: 30
        │     │     └── poor-signal <seconds>             #   default: 120
        │     ├── max-wait-for-signal <seconds>           #   default: 120
        │     ├── signal-check-interval <seconds>         #   default: 10
        │     └── signal-strength-buffer <dBm>            #   default: 5
        │
        ├── interface-management
        │     ├── disable                                 #   valueless — turn off interface management (on by default)
        │     ├── bearer-disconnect-delay <seconds>       #   default: 15
        │     ├── registration-recovery-delay <seconds>   #   default: 20
        │     ├── registration-flap-count <count>          #   default: 5 (0 = disabled)
        │     ├── registration-flap-window <seconds>       #   default: 360
        │     ├── ip-change-delay <milliseconds>           #   default: 500
        │     ├── disable-ensure-link-up-on-connect       #   valueless — turn off link-up enforcement (on by default)
        │     ├── disable-monitor-bearer-state            #   valueless — turn off bearer-state tracking (on by default)
        │     ├── disable-monitor-ip-changes              #   valueless — turn off IP-change detection (on by default)
        │     └── interface-up-timeout <seconds>          #   default: 10
        │
        ├── connectivity-monitoring
        │     ├── disable                                 #   valueless — turn off connectivity monitoring (on by default)
        │     ├── interval <seconds>                      #   default: 60
        │     ├── timeout <seconds>                       #   default: 10
        │     ├── retry-count <count>                     #   default: 3
        │     ├── failure-threshold <count>               #   default: 2
        │     ├── disable-test-ipv4                       #   valueless — turn off IPv4 ping testing (on by default)
        │     ├── test-ipv6                               #   valueless — enable IPv6 ping testing (off by default)
        │     ├── require-both                            #   valueless
        │     ├── ipv4-targets <addr,addr,...>            #   default: 8.8.8.8,1.1.1.1
        │     └── ipv6-targets <addr,addr,...>            #   default: 2001:4860:4860::8888,...
        │
        ├── data-usage
        │     ├── monitoring-interval <seconds>           #   default: 30
        │     ├── size <bytes>                            #   default: 0 (unlimited); global fallback for per-SIM
        │     ├── action <none|disable|sim-failover|sim-failover-sticky>  #   default: none
        │     ├── billing-date <1-28>                    #   default: 1
        │     └── warning <pct,pct,...>                   #   default: (empty)
        │
        ├── hardware-reset
        │     ├── disable                                 #   valueless — turn off hardware reset (on by default)
        │     ├── max-attempts <count>                    #   default: 3
        │     └── cooldown <seconds>                      #   default: 300
        │
        ├── failed-retry
        │     ├── disable                                 #   valueless — turn off periodic retry from FAILED state (on by default)
        │     ├── intervals <sec,sec,...>                  #   default: 600,1800,3600,7200  (10, 30, 60, 120 min)
        │     ├── max-interval <seconds>                  #   default: 7200  (cap once list exhausted, 2 hr)
        │     └── escalation-threshold <count>             #   default: 3  (disable/enable cycle after N failures; 0 = never)
        │
        ├── network-scan
        │     └── timeout <seconds>                       #   default: 60
        │
        ├── timeouts
        │     ├── connection <seconds>                    #   default: 120
        │     ├── registration <seconds>                  #   default: 180
        │     └── normal-monitoring-interval <seconds>    #   default: 30
        │
        └── logging
              ├── level <debug|info|warning|error>        #   default: info
              ├── sink <both|journal|syslog>              #   default: both
              ├── disable-verbose                        #   valueless (default: on)
              ├── disable-snmp-monitoring                 #   valueless (default: on)
              ├── disable-detailed-status                 #   valueless (default: on)
              └── health-check-interval <seconds>         #   default: 300
```

---

## Default Behavior — Zero Configuration

If no `set interfaces wwan wwanN …` commands are issued beyond bringing the
interface up, the following defaults apply.  The modem will attempt to connect
automatically using a 4-priority APN discovery chain:

| Feature | Default (nothing configured) | Effect |
|---|---|---|
| **Description** | `(empty)` | No interface description |
| **Disable** | not set | Interface is admin-up |
| **VRF** | not set | Interface is in the default VRF |
| **Redirect** | not set | No packet redirect |
| **Mirror** | not set | No ingress/egress mirroring |
| **IPv4 options** | VyOS defaults | Forwarding enabled, source-validation disabled |
| **IPv6 options** | VyOS defaults | Forwarding enabled, source-validation disabled |
| **IPv6 PD** | not configured | No prefix delegation; configure `pd` to have the FSM subdivide the carrier prefix and delegate to LAN interfaces |
| **PD reconciliation** | `10 s` | Safety-net timer re-checks pending LAN interfaces; netlink watch provides instant detection |
| **Active SIM slot** | `1` | Slot 1 is used |
| **APN** | per-SIM only, `(empty)` — triggers auto-discovery | Priority chain: 1) per-SIM configured APN, 1.5) in-memory last-connected APN, 3) Android APN DB (enabled by default), 4) automatic (let the network assign) |
| **Authentication** | per-SIM only, default `none` | No PPP auth; auth-type/username/password configured per SIM slot |
| **PDP type** | per-SIM only, default `ipv4v6` | Dual-stack bearer per slot unless overridden |
| **Roaming** | per-SIM only, default `enabled` | Roaming is permitted by default so aggregator/MVNO SIMs (e.g. roaming-style Rogers-on-Bell) work out of the box. Use `disable-roaming` per slot to forbid visited networks. |
| **Network mode** | `auto` | Modem selects best available RAT (5G→LTE→3G→2G) |
| **MTU** | `1420` (fallback) | Carrier-negotiated bearer MTU is used when available; 1420 is used only if the carrier does not provide one; also acts as a ceiling; per-SIM `mtu` overrides when active |
| **Per-SIM MTU** | `0` (use interface mtu) | Optional per-SIM override; when the SIM is active, this value is used instead |
| **SIM PIN** | per-SIM only | If a PIN is configured, the FSM always sends it automatically when the SIM is locked |
| **SIM failover** | per-SIM, `enabled` | Automatic switch to backup SIM on failure; use `disable` to turn off |
| **SIM failback** | `enabled` | After sim-failover fires, automatic return to primary SIM; use `disable` to turn off |
| **APN discovery (Android)** | `enabled` | Android APN database lookup, configured APNs, and automatic (network-assigned) APNs are all tried |
| **Connection mode** | `always-on` | Modem connects immediately at boot and stays connected |
| **Enhanced reconnection** | `enabled` | Signal-quality-aware reconnection; use `disable-enhanced` to fall back to basic fixed-interval |
| **Reconnection retry** | good-signal `15 s`, poor-signal `45 s` | Active by default (enhanced reconnection is on) |
| **Signal threshold** | `-85 dBm` | Boundary between "good" and "poor" reconnection strategies |
| **Bearer disconnect delay** | `15 s` | Grace period before tearing down a disconnected bearer |
| **Registration recovery delay** | `20 s` | Debounce for registration-lost flaps |
| **Registration flap detection** | count `5`, window `360 s` | If ≥5 debounced registration losses in 360 s, trigger SIM failover (0 = disabled) |
| **IP change delay** | `500 ms` | Settle time after IP re-assignment |
| **Interface management** | `enabled` | Master on/off for bearer, registration, IP monitoring subsystem |
| **Link / bearer / IP monitoring** | all `enabled` | Interface-up enforcement, bearer-state tracking, IP-change detection all active; use `disable-*` to turn off individually |
| **Interface-up timeout** | `10 s` | Max wait for kernel interface to come up after bearer connect |
| **Connectivity monitoring** | `enabled` | Active ping probes detect dead paths even when bearer stays up |
| **Connectivity ping targets** | IPv4: `8.8.8.8, 1.1.1.1`; IPv6: Google/Cloudflare DNS | (only effective when monitoring is enabled) |
| **SIM Failover** | `enabled` | Automatic switchover on signal loss or connect failures; use `disable` to turn off |
| **Data limits (per-SIM)** | size `0` (unlimited), action `none`, billing-date `1`, warning `(empty)` | No data cap enforcement; no warnings logged |
| **Data limits (global fallback)** | size `0`, action `none`, billing-date `1`, warning `(empty)` | Applies when per-SIM values are not set |
| **Data usage monitoring** | interval `30 s` | Counters tracked per billing cycle |
| **Hardware reset** | `enabled`, max `3` attempts, cooldown `300 s` | Modem power-cycles after repeated unrecoverable failures; use `disable` to turn off |
| **Failed-state retry** | `enabled`, intervals `600,1800,3600,7200`, cap `7200 s`, escalation threshold `3` | Periodically reattempts connection from FAILED state (data-plan top-up, carrier provisioning, transient errors); carrier-friendly backoff (~10 attempts/hour worst case) avoids triggering Verizon/AT&T throttling; after 3 consecutive failures, escalates to modem disable/enable cycle to clear stale EPS context |
| **Band selection** | `all` | All modem-supported radio technologies enabled |
| **Network scan timeout** | `60 s` | Max wait for network scan completion |
| **Connection timeout** | `120 s` | Max wait for MM `Simple.Connect()` to succeed |
| **Registration timeout** | `180 s` | Max wait for network registration |
| **Normal monitoring interval** | `30 s` | Polling cycle in CONNECTED state |
| **Logging** | level `info`, sink `both`, verbose `on`, SNMP `on`, detailed-status `on` | Logs go to both journal and syslog by default |
| **Health-check interval** | `300 s` | Periodic self-diagnostic cycle |

### Minimum Viable Configuration

To connect a single SIM with a known APN and no other features:

```
set interfaces wwan wwan0 sim slot 1 apn 'your.carrier.apn'
```

Everything else uses the defaults above.  If the carrier requires authentication:

```
set interfaces wwan wwan0 sim slot 1 apn 'your.carrier.apn'
set interfaces wwan wwan0 sim slot 1 username 'user'
set interfaces wwan wwan0 sim slot 1 password 'pass'
set interfaces wwan wwan0 sim slot 1 auth-type 'chap'
```

If the SIM is PIN-locked:

```
set interfaces wwan wwan0 sim slot 1 pin '1234'
```

---

## Full `set` Command Listing

### Interface Parameters

> **If unconfigured:** Network-mode auto, MTU from carrier (fallback 1420 if carrier does not provide one).  APN, auth-type, PDP-type, roaming, username/password are all per-SIM only.

```
# Interface description (friendly name, max 255 characters)
set interfaces wwan wwan0 description 'Primary LTE uplink — Bell Canada'

# Admin shutdown — presence disables the interface
# set interfaces wwan wwan0 disable

# VRF binding
set interfaces wwan wwan0 vrf 'CELLULAR'

# Redirect all incoming packets to another interface
# set interfaces wwan wwan0 redirect 'eth0'

# Network mode — modem RAT selection
set interfaces wwan wwan0 network-mode 'auto'

# MTU — fallback if carrier does not provide one; also ceiling (per-SIM mtu overrides when that SIM is active)
set interfaces wwan wwan0 mtu 1420
```

### IPv4 Options

> **If unconfigured:** VyOS kernel defaults — forwarding enabled, source-validation disabled.

```
set interfaces wwan wwan0 ip adjust-mss '1380'
# set interfaces wwan wwan0 ip disable-forwarding
set interfaces wwan wwan0 ip source-validation 'strict'
```

### IPv6 Options

> **If unconfigured:** VyOS kernel defaults — forwarding enabled, source-validation disabled.
> DAD and `address no-default-link-local` are omitted — DAD is meaningless on
> a /128 point-to-point carrier link, and suppressing the fe80:: link-local
> would break IPv6 NDP routing on wwan.

```
set interfaces wwan wwan0 ipv6 adjust-mss '1380'
# set interfaces wwan wwan0 ipv6 disable-forwarding
set interfaces wwan wwan0 ipv6 source-validation 'strict'
```

### IPv6 Prefix Delegation

> **If unconfigured:** No prefix delegation.  The FSM applies the bearer's
> IPv6 address directly; `pd` tells the FSM to subdivide the carrier prefix
> and delegate sub-prefixes to LAN interfaces.  No DHCPv6 client (dhcp6c) is
> involved — the FSM performs PD math natively using the bearer's `Ip6Config`
> prefix.
>
> **How it works:** The carrier assigns a prefix (e.g. /56) via the bearer.
> The FSM reads the actual prefix length from the bearer's `Ip6Config` —
> there is no `length` knob because the carrier decides the prefix size,
> not the user.  The FSM applies a /128 on wwan0 (point-to-point) and
> delegates address space to LAN interfaces using the SLA-ID and SLA-LEN.
> The delegated prefix length is `carrier_prefix_len + sla-len`.  By
> default `sla-len` is `64 − carrier_prefix_len`, which produces /64
> subnets.  Set `sla-len 0` to delegate the entire carrier prefix to a
> single interface.
>
> If the carrier prefix is /64 (and default sla-len), only one LAN
> interface can be delegated.  If the carrier prefix is /128, no
> delegation is possible (address-only mode).
>
> **SLA-LEN examples (carrier /56):**
>
> | `sla-len` | Delegated prefix | Subnets | Use case |
> |---|---|---|---|
> | `8` (default) | /64 | 256 | One /64 per LAN — standard SLAAC |
> | `4` | /60 | 16 | Each LAN gets 16 /64s |
> | `0` | /56 | 1 | Entire prefix to one interface |
>
> **Late-appearing LAN interfaces:**  A delegated LAN interface (e.g. `br0`)
> may not exist when the bearer connects and PD is first applied.  The FSM
> handles this with two mechanisms:
>
> 1. **Netlink watch** — an asyncio task listens for `RTM_NEWLINK` events.
>    When a pending interface appears, its delegated prefix is applied
>    instantly.  Always active when any `pd` instance is configured.
> 2. **Periodic reconciliation** — a safety-net timer (`pd-reconciliation-interval`,
>    default 10 s) re-checks the pending set on each tick.  Catches edge
>    cases the netlink watch might miss (e.g. interface destroyed and
>    re-created between events).
>
> Interfaces that are destroyed (`RTM_DELLINK`) have their delegated prefix
> moved back to the pending set and are re-applied when the interface
> reappears.  Bearer disconnect removes all delegated prefixes; bearer
> reconnect re-applies them (or pends them if the LAN interface is gone).

```
# Split carrier prefix into /64s (default sla-len, most common)
set interfaces wwan wwan0 pd 0 interface eth0 address '1'
set interfaces wwan wwan0 pd 0 interface eth0 sla-id '0'

# Second LAN gets the next /64
set interfaces wwan wwan0 pd 0 interface eth1 address '1'
set interfaces wwan wwan0 pd 0 interface eth1 sla-id '1'

# Delegate the whole carrier prefix to br0 — no subdivision
set interfaces wwan wwan0 pd 0 interface br0 address '1'
set interfaces wwan wwan0 pd 0 interface br0 sla-id '0'
set interfaces wwan wwan0 pd 0 interface br0 sla-len '0'

# Reconciliation interval — safety-net for late-appearing interfaces (default 10 s)
set interfaces wwan wwan0 pd-reconciliation-interval 10
```

### IP Passthrough (DOCSIS-Modem-Style)

> **If unconfigured:** No passthrough.  The carrier IP lives on `wwanN` and
> the router NATs/forwards normally.
>
> **What it does:** When a downstream device must own the public carrier IP
> directly (single-host CPE, IoT gateway behind a customer firewall,
> telematics, point-of-sale terminals that demand a "real" public address),
> the FSM hands the carrier-assigned IPv4 and IPv6 to one wired client via
> a tiny isolated DHCP/RA service on a designated LAN interface.  The
> downstream NIC sees the carrier address as if it were directly attached.
>
> **Why this is not a true L2 bridge:**  3GPP PDN bearers are L3-only — no
> Ethernet frames cross the modem.  Every cellular vendor (Cradlepoint,
> Digi, Sierra, Peplink) implements "IP Passthrough" as a DHCP handoff,
> not a bridge.  The FSM does the same: bearer L3 → dnsmasq → downstream
> NIC.
>
> **Architecture (FSM-owned, single CLI knob):**
>
> 1. The FSM brings a per-passthrough `dnsmasq` instance up on the
>    designated interface (`--bind-interfaces`, scoped PID file in
>    `/run/wwan/passthru-<if>.pid`).
> 2. **DHCPv4** offers exactly one lease — the carrier IPv4 — to the first
>    MAC seen (or to a pinned MAC).  Lease time defaults to 60 s so an IP
>    change propagates within one renewal window.  The carrier-supplied
>    DNS servers from the bearer's `Ip4Config` are advertised via DHCP
>    option 6 (with `8.8.8.8/1.1.1.1` as a last-resort fallback if the
>    bearer didn't provide any).
> 3. **DHCPv6 IA_NA + IA_PD + RA (M=1, O=1)** offers the carrier IPv6 to
>    the same client.  RA advertises the FSM as the default gateway with
>    DNS via option 23, again sourced from the bearer's `Ip6Config`.
>    Both stateful options are always offered; per RFC 8415 §18.2.4 the
>    server only returns an IA_PD if the client requested one, so the
>    behavior is fully automatic:
>
>    | Downstream device | What it asks for | What it gets |
>    |---|---|---|
>    | Windows / Linux / macOS PC | IA_NA only | Carrier `/128` + RA + DNS |
>    | OpenWrt / pfSense / VyOS / Cradlepoint | IA_NA + IA_PD | Carrier `/128` + carrier prefix as PD + RA + DNS |
>
>    IA_PD is emitted whenever the carrier delivers any prefix `/64` or
>    shorter.  Common cases:
>
>    | Carrier prefix | What gets delegated | Typical case |
>    |---|---|---|
>    | `/56`, `/60` | Whole carrier prefix as one PD | Enterprise / fixed-wireless |
>    | `/64` | Whole `/64` as one PD | Most LTE / 5G mobile (Bell, AT&T, Verizon) |
>    | `/128` (no prefix) | None — IA_NA only | Carriers that hand out a single host |
>
>    For the `/64` case the downstream router puts the carrier `/128` on its
>    WAN (from IA_NA) and the carrier `/64` on its LAN (from IA_PD); IPv6
>    longest-prefix-match resolves the apparent overlap correctly.  This
>    matches Cradlepoint NCOS "PD-Pass-Through", Digi TransPort, and
>    Peplink 8.3+ behavior.
> 4. **Inbound forwarding via policy routing** — the carrier IP stays
>    bound to `wwanN` so the router itself still has a working source
>    for outbound traffic (ModemManager probes, NTP, DNS, etc.).  Inbound
>    packets to the carrier IP are diverted to the LAN interface via:
>
>    ```
>    ip rule add iif wwanN to <carrier_ip> lookup passthruN
>    ip route add <carrier_ip> dev <lan_if> table passthruN
>    ```
>
>    The rule fires *before* the local table is consulted, so packets
>    arriving on `wwanN` for the carrier IP are forwarded to the
>    downstream device (whose MAC is resolved via normal ARP/NDP since
>    it received the IP via DHCP).  Locally-originated traffic doesn't
>    match `iif wwanN` and continues to use the local table.
> 5. **Management address** — because the carrier IP is leased away, the
>    LAN interface still needs an address for SSH/HTTPS to the router.
>    The FSM auto-provisions `192.168.200.1/24` (v4) and
>    `fd00:6c61:6e30::1/64` (v6) by default.  These are configurable.
> 6. **Persistent source-address whitelist** — mirrors the PD ip6tables
>    egress filter.  A per-FSM chain on FORWARD drops any traffic
>    arriving on the LAN interface whose source is not the current
>    carrier IP (link-local is always permitted on v6 so NDP keeps
>    working).  This is *persistent*, not just during a swap — if a
>    downstream device clings to a stale address after the carrier
>    rolls the IP, packets are dropped continuously, not just during
>    the 5 s grace window.  The whitelist is rewritten in place on
>    every IP change.
> 7. **Policy B coexistence:** if the user has set
>    `interfaces ethernet <if> address ...` explicitly, the FSM defers
>    entirely — no auto-mgmt address is added.  Silent → FSM provides
>    defaults.  This avoids fighting VyOS's own ethernet config.
>
> **Carrier IP changes (the hard part):**  When the carrier reassigns an
> address (renew, handover, reconnect), stale connections must die
> immediately or the downstream device will black-hole until its lease
> expires.  The FSM applies this sequence:
>
> 1. `iptables` rule blocks egress with `saddr == old_carrier_ip` (v4 + v6).
> 2. `conntrack -D -s old_carrier_ip` flushes existing flows.
> 3. Old policy-routing entry (`ip rule` + table route) is removed.
> 4. dnsmasq config rewritten + `SIGHUP`.
> 5. New policy-routing entry installed for the new carrier IP.
> 6. **DHCPFORCERENEW** (RFC 3203) for v4 — sent via the `dhcp_release2`
>    helper from `dnsmasq-utils`.  If the helper is missing, the FSM
>    logs a one-time warning and the downstream device renews at T1
>    (`lease/2`, ≤30 s with the default 60 s lease).  DHCPv6 Reconfigure
>    (RFC 8415 §18.2.11) is handled implicitly by dnsmasq's SIGHUP.
> 7. After downstream renewal is observed (or a 5 s grace window
>    elapses), the `iptables` block is removed.
>
> **Bearer down:**  dnsmasq is stopped, mgmt address (if FSM-owned) is
> removed, iptables rules are torn down.  No stale lease remains advertised.
>
> **Restrictions:**
>  - The designated interface must not be in a bridge or bond.
>  - PD (`set interfaces wwan wwan0 pd ...`) is mutually exclusive with
>    passthrough — both consume the bearer's IPv6.  Use passthrough's
>    built-in IA_PD (above) to delegate the carrier prefix to the
>    downstream router instead.
>  - The interface should be wired (not Wi-Fi) — DHCPFORCERENEW behaviour
>    on wireless drivers is unreliable.

```
# Single CLI knob — designate the LAN port
set interfaces wwan wwan0 ip-passthrough interface 'eth1'

# Optional: pin to a specific MAC (otherwise first-MAC-wins on lease)
set interfaces wwan wwan0 ip-passthrough mac 'aa:bb:cc:dd:ee:ff'

# Optional: tune lease (default 60 s, range 30–600)
set interfaces wwan wwan0 ip-passthrough lease-time '60'

# Optional: override the auto-provisioned management addresses
#   (only takes effect if 'interfaces ethernet <if> address' is unset —
#    Policy B: explicit user config always wins)
set interfaces wwan wwan0 ip-passthrough management-address '192.168.200.1/24'
set interfaces wwan wwan0 ip-passthrough management-address-ipv6 'fd00:6c61:6e30::1/64'

# Optional: override DNS advertised to the downstream device (multi-value).
#   Precedence: user override > carrier-supplied DNS > 8.8.8.8/1.1.1.1 fallback.
#   Mix v4 and v6 freely — they are split automatically into DHCPv4 option 6
#   and DHCPv6 option 23 / RA RDNSS. Use this for NextDNS, OpenDNS, internal
#   resolvers, or carrier-mandated DNS for compliance.
#   IPv6 addresses must be fully formed (RFC 5952 form, with `::` shorthand
#   permitted, e.g. '2606:4700:4700::1111' is the fully formed form of
#   '2606:4700:4700:0000:0000:0000:0000:1111'). One address per `set` command —
#   comma- or space-separated lists in a single value are not accepted.
set interfaces wwan wwan0 ip-passthrough dns-server '1.1.1.1'
set interfaces wwan wwan0 ip-passthrough dns-server '9.9.9.9'
set interfaces wwan wwan0 ip-passthrough dns-server '2606:4700:4700::1111'

# Optional: disable TCP MSS clamp-to-PMTU on WWAN egress.
#   Clamping is ON BY DEFAULT — this matches Cradlepoint/Peplink/Sierra/Digi
#   passthrough behavior and transparently fixes oversized-TCP-segment drops
#   for downstream clients that ignore DHCP option 26 / RA MTU. The clamp
#   uses --clamp-mss-to-pmtu so it auto-tracks the bearer MTU dynamically.
#   Only disable for PMTUD black-hole debugging.
# set interfaces wwan wwan0 ip-passthrough disable-mss-clamp
```

### Packet Mirroring

> **If unconfigured:** No mirroring — neither ingress nor egress traffic is copied.

```
set interfaces wwan wwan0 mirror ingress 'eth2'
set interfaces wwan wwan0 mirror egress 'eth2'
```

### SIM Configuration

> **If unconfigured:** Slot 1 active, sim-failover and sim-failback enabled, dual-SIM ready.  PIN/PUK are per-SIM only (no global default).

```
set interfaces wwan wwan0 sim primary-slot 1

# Per-SIM slot configuration
set interfaces wwan wwan0 sim slot 1 apn 'pda.bell.ca'
set interfaces wwan wwan0 sim slot 1 username ''
set interfaces wwan wwan0 sim slot 1 password ''
set interfaces wwan wwan0 sim slot 1 auth-type 'chap'
set interfaces wwan wwan0 sim slot 1 pdp-type 'ipv4v6'
set interfaces wwan wwan0 sim slot 1 disable-roaming
set interfaces wwan wwan0 sim slot 1 pin '1234'
set interfaces wwan wwan0 sim slot 1 puk '12345678'
set interfaces wwan wwan0 sim slot 1 iccid '89302610123456789012'
set interfaces wwan wwan0 sim slot 1 supported-bands 'all'
set interfaces wwan wwan0 sim slot 1 preferred-carrier '302610'
set interfaces wwan wwan0 sim slot 1 enable-network-scan
set interfaces wwan wwan0 sim slot 1 mtu 1500
set interfaces wwan wwan0 sim slot 1 data-limit size 5000000000
set interfaces wwan wwan0 sim slot 1 data-limit action 'disable'
set interfaces wwan wwan0 sim slot 1 data-limit billing-date 1
set interfaces wwan wwan0 sim slot 1 data-limit warning '75,90,95'

set interfaces wwan wwan0 sim slot 2 apn 'backup.apn'
set interfaces wwan wwan0 sim slot 2 auth-type 'none'
set interfaces wwan wwan0 sim slot 2 pdp-type 'ipv4'
set interfaces wwan wwan0 sim slot 2 pin '5678'
set interfaces wwan wwan0 sim slot 2 data-limit size 0
set interfaces wwan wwan0 sim slot 2 data-limit action 'sim-failover'
set interfaces wwan wwan0 sim slot 2 data-limit billing-date 1
set interfaces wwan wwan0 sim slot 2 data-limit warning '75,90'

# SIM failback (enabled by default; use 'disable' to turn off)
# set interfaces wwan wwan0 sim sim-failback disable
set interfaces wwan wwan0 sim sim-failback check-interval 600

# SIM failover (enabled by default; use 'disable' to turn off)
# set interfaces wwan wwan0 sim sim-failover disable
set interfaces wwan wwan0 sim sim-failover connect-retries 3
set interfaces wwan wwan0 sim sim-failover revert-timer 300
set interfaces wwan wwan0 sim sim-failover signal-loss-timer 60
set interfaces wwan wwan0 sim sim-failover signal-threshold -90
```

### APN Discovery

> **If unconfigured:** Android APN database lookup is enabled by default.  The full priority chain is used: configured APN, in-memory last-connected APN, Android APN DB, and automatic (network-assigned) APN.

```
# APN discovery is on by default — to disable:
# set interfaces wwan wwan0 apn-discovery disable
```

### Connection Mode

> **If unconfigured:** `always-on` — modem connects at boot and stays connected.

```
set interfaces wwan wwan0 connection-mode 'always-on'
```

### Connection Mode Design Notes

Three connection modes are available (choose one):

| Mode | Startup bearer | D-Bus `connect_bearer()` | D-Bus `disconnect_bearer()` | D-Bus `get_bearer_status()` |
|---|---|---|---|---|
| **always-on** (default) | yes, auto | reconnect from FAILED | full disconnect | `"connected"` / `"disconnected"` |
| **connect-on-demand** | **no** (REGISTERED_IDLE) | bring up bearer | drop bearer → REGISTERED_IDLE | `"connected"` / `"disconnected"` |
| **dial-on-demand** | **yes**, auto | bring up bearer | drop bearer → REGISTERED_IDLE | `"connected"` / `"disconnected"` |

**always-on** — Current default.  Modem registers, bearer is established, Linux
interface comes up, and stays connected indefinitely.

**connect-on-demand** — VyOS-compatible explicit mode.  The FSM registers the
modem on the network but does **not** establish a bearer.  The modem sits idle
at `REGISTERED_IDLE` until an external application issues a D-Bus
`connect_bearer()` call.  Once connected, the bearer stays up until an explicit
`disconnect_bearer()` or a failure.  SMS is available while parked at
`REGISTERED_IDLE`.

**dial-on-demand** — Auto-connect with external bearer management.  The FSM
registers the modem **and** establishes the bearer automatically at startup
(identical to always-on).  An external application can then:

1. Call D-Bus `disconnect_bearer()` → bearer drops, modem parks at
   `REGISTERED_IDLE` (registered, SMS available, no data).
2. Call D-Bus `connect_bearer()` → bearer is re-established.
3. Poll D-Bus `get_bearer_status()` → returns `"connected"` or `"disconnected"`.

During normal connection procedure, `dial-on-demand` will continue to bring
the bearer up automatically.  Auto-reconnect suppression only applies after an
explicit bearer disconnect command (`disconnect_bearer()` / on-demand
`disconnect()`) has been issued.

All three bearer methods (`connect_bearer`, `disconnect_bearer`,
`get_bearer_status`) are always available regardless of connection mode.
`connect_bearer()` and `disconnect_bearer()` always return `"accepted"`;
the caller polls `get_bearer_status()` to observe the actual state.

The legacy `connect()` and `disconnect()` D-Bus methods also remain.  In
`connect-on-demand` and `dial-on-demand` modes they behave identically to
the bearer methods (fire-and-forget `"accepted"` responses).

**Silent disconnect behaviour (both on-demand modes):**
- Bearer is released via MM `Simple.Disconnect()`
- Linux interface stays present (link-layer up, no IP or stale IP)
- No routing withdrawal — upstream apps see the interface as "available"
- Next `connect_bearer()` re-establishes the bearer transparently
- Registration-loss events still propagate normally (interface goes down)

> **Status:** All three connection modes are **fully implemented**.

### Enhanced Reconnection Strategy

> **If unconfigured:** Signal-quality-aware reconnection is active.  To fall back to basic fixed-interval reconnection, set `reconnection disable-enhanced`.

```
# Enhanced reconnection is enabled by default — no command needed to activate.
# To disable: set interfaces wwan wwan0 reconnection disable-enhanced
set interfaces wwan wwan0 reconnection signal-threshold -85
set interfaces wwan wwan0 reconnection retry-interval good-signal 15
set interfaces wwan wwan0 reconnection retry-interval poor-signal 45
set interfaces wwan wwan0 reconnection max-wait-for-signal 120
set interfaces wwan wwan0 reconnection signal-check-interval 10
set interfaces wwan wwan0 reconnection signal-strength-buffer 5
```

### Interface Management

> **If unconfigured:** All monitors active (bearer-state, IP-changes, link-up enforcement).  Delays: bearer-disconnect 15 s, registration-recovery 20 s, IP-change 500 ms, interface-up timeout 10 s.

```
set interfaces wwan wwan0 interface-management disable
set interfaces wwan wwan0 interface-management bearer-disconnect-delay 15
set interfaces wwan wwan0 interface-management registration-recovery-delay 20
set interfaces wwan wwan0 interface-management registration-flap-count 5
set interfaces wwan wwan0 interface-management registration-flap-window 360
set interfaces wwan wwan0 interface-management ip-change-delay 500
# Link-up enforcement, bearer-state tracking, and IP-change detection are on by default.
# To disable individually:
# set interfaces wwan wwan0 interface-management disable-ensure-link-up-on-connect
# set interfaces wwan wwan0 interface-management disable-monitor-bearer-state
# set interfaces wwan wwan0 interface-management disable-monitor-ip-changes
set interfaces wwan wwan0 interface-management interface-up-timeout 10
```

### Connectivity Health Monitoring

> **If unconfigured:** Enabled — active ping probes to detect dead paths.  Interval 60 s, timeout 10 s, failure-threshold 2, IPv4 targets: 8.8.8.8 + 1.1.1.1.

```
# To disable connectivity monitoring:
# set interfaces wwan wwan0 connectivity-monitoring disable
set interfaces wwan wwan0 connectivity-monitoring interval 60
set interfaces wwan wwan0 connectivity-monitoring timeout 10
set interfaces wwan wwan0 connectivity-monitoring retry-count 3
set interfaces wwan wwan0 connectivity-monitoring failure-threshold 2
# test-ipv4 is on by default — to disable:
# set interfaces wwan wwan0 connectivity-monitoring disable-test-ipv4
set interfaces wwan wwan0 connectivity-monitoring test-ipv6
set interfaces wwan wwan0 connectivity-monitoring require-both
set interfaces wwan wwan0 connectivity-monitoring ipv4-targets '8.8.8.8,1.1.1.1,9.9.9.9'
set interfaces wwan wwan0 connectivity-monitoring ipv6-targets '2001:4860:4860::8888,2606:4700:4700::1111'
```

### SIM Failover Policy

> **If unconfigured:** Enabled — automatic SIM switchover on sustained signal loss or repeated connect failures.  Use `disable` to turn off.

```
# To disable failover:
# set interfaces wwan wwan0 sim sim-failover disable
set interfaces wwan wwan0 sim sim-failover connect-retries 3
set interfaces wwan wwan0 sim sim-failover revert-timer 300
set interfaces wwan wwan0 sim sim-failover signal-loss-timer 60
set interfaces wwan wwan0 sim sim-failover signal-threshold -90
```

### Data Usage Monitoring

> **If unconfigured:** Counters tracked every 30 s.  No enforcement action unless a per-SIM `data-limit` is configured.  Set `data-usage warning` (global fallback) or per-SIM `data-limit warning` with comma-separated percentages to log warnings as usage climbs toward the limit.

**Data-limit actions:**
| Action | Behaviour |
|---|---|
| `none` | Log warning when limit hit but take no action (default) |
| `disable` | Disconnect bearer when limit hit |
| `sim-failover` | Switch to backup SIM; failback resumes normally when `sim-failback` is enabled |
| `sim-failover-sticky` | Switch to backup SIM **and suppress failback** until the billing cycle resets — avoids overage charges on the primary SIM |

```
set interfaces wwan wwan0 data-usage monitoring-interval 30
set interfaces wwan wwan0 data-usage size 0
set interfaces wwan wwan0 data-usage action 'none'
set interfaces wwan wwan0 data-usage billing-date 1
set interfaces wwan wwan0 data-usage warning '75,90,95'
```

### Hardware Reset

> **If unconfigured:** Enabled — up to 3 modem power-cycle attempts with 300 s cooldown on unrecoverable failures.

```
# Hardware reset is enabled by default — to disable:
# set interfaces wwan wwan0 hardware-reset disable
set interfaces wwan wwan0 hardware-reset max-attempts 3
set interfaces wwan wwan0 hardware-reset cooldown 300
```

### Failed-State Retry

> **If unconfigured:** Enabled — backoff intervals 5, 10, 20, 30 minutes; capped at 30 minutes indefinitely.
>
> When the FSM enters the FAILED state (e.g. data plan exhausted, carrier
> provisioning delay for a new SIM, transient network-side error), it
> automatically retries the APN connection cascade using stepped backoff.
> This covers scenarios where the user tops up their data plan, the monthly
> billing cycle resets, or the carrier completes provisioning.

```
# Failed-state retry is enabled by default — to disable:
# set interfaces wwan wwan0 failed-retry disable
set interfaces wwan wwan0 failed-retry intervals '600,1800,3600,7200'
set interfaces wwan wwan0 failed-retry max-interval 7200
set interfaces wwan wwan0 failed-retry escalation-threshold 3
```

### Carrier / Network Scan

> **If unconfigured:** Network-mode auto (all technologies), network scanning disabled, scan timeout 60 s.
>
> **Network-mode vs Per-SIM bands:**
> The `network-mode` setting (see Basic Commands above) controls which radio
> technologies (2G/3G/LTE/5G) the modem hardware is allowed to use via the
> ModemManager `SetCurrentModes` API.  This is a modem-level setting.
> Specific band names (e.g. `eutran-7`, `ngran-78`) are **per-SIM only**
> because different carriers use different frequencies.
> Use per-SIM `supported-bands` for carrier-specific band restrictions.
> The final active band set is: per-SIM ∩ modem-supported.
>
> `preferred-carrier` and `enable-network-scan` are **per-SIM only** settings
> because each SIM has its own carrier.  Configure them under
> `sim slot N preferred-carrier` and `sim slot N enable-network-scan`.
>
> `preferred-carrier` accepts two formats:
> - **MCCMNC code** (e.g. `'302610'` for Bell) — used for direct `Register()`; fast, no scan needed.
> - **Friendly name** (e.g. `'Bell'`) — matched as a case-insensitive substring against `operator-long` from a network scan.  A scan is performed **automatically** when a friendly name is used; no separate `network-scan enable` is required.
>
> MCCMNC is preferred because it avoids the 2+ minute scan delay.
>
> **Network scan behaviour:**
> - **`preferred-carrier` with a friendly name** → scan runs automatically to resolve the name to an MCCMNC code for registration.
> - **`preferred-carrier` with an MCCMNC code** → direct `Register()`, no scan.
> - **`network-scan enable` (with or without preferred-carrier)** → a diagnostic scan is performed and the results are cached in the status output under `available_networks`.  Each entry includes operator name, MCCMNC code, availability status, and access technology.
> - If both a friendly name **and** `network-scan enable` are set, a single scan serves both purposes.

```
set interfaces wwan wwan0 network-scan timeout 60
```

#### Band Name Reference

Band names use the **3GPP band number** (the industry-standard number from
Wikipedia / carrier specs) prefixed with the technology.  The code translates
these to ModemManager `MM_MODEM_BAND_*` uint32 constants internally — users
never type the MM constant directly.

The prefix is required because the same band number can exist across
technologies (e.g. Band 1 exists in UMTS, LTE, and 5G NR).

**Example:** `set interfaces wwan wwan0 sim slot 1 supported-bands 'eutran-7,eutran-28,ngran-78'`

| Technology | Band Name | MM Constant | Frequency |
|---|---|---|---|
| **2G (GSM)** | `gsm-850` | 1 | 850 MHz |
| | `gsm-900` | 2 | 900 MHz |
| | `gsm-1800` | 3 | 1800 MHz |
| | `gsm-1900` | 4 | 1900 MHz |
| **3G (UMTS)** | `umts-1` | 5 | 2100 MHz |
| | `umts-2` | 6 | 1900 MHz PCS |
| | `umts-3` | 7 | 1800 MHz DCS |
| | `umts-4` | 8 | 1700/2100 MHz AWS |
| | `umts-5` | 9 | 850 MHz |
| | `umts-6` | 10 | 800 MHz |
| | `umts-7` | 11 | 2600 MHz |
| | `umts-8` | 12 | 900 MHz |
| | `umts-9` | 13 | 1700 MHz |
| | `umts-10` | 14 | 1700/2100 MHz |
| **LTE (EUTRAN)** | `eutran-1` | 31 | 2100 MHz |
| | `eutran-2` | 32 | 1900 MHz PCS |
| | `eutran-3` | 33 | 1800 MHz DCS |
| | `eutran-4` | 34 | 1700/2100 MHz AWS |
| | `eutran-5` | 35 | 850 MHz |
| | `eutran-6` | 36 | 800 MHz |
| | `eutran-7` | 37 | 2600 MHz |
| | `eutran-8` | 38 | 900 MHz |
| | `eutran-9` | 39 | 1800 MHz |
| | `eutran-10` | 40 | 1700/2100 MHz |
| | `eutran-11` | 41 | 1500 MHz |
| | `eutran-12` | 42 | 700 MHz a |
| | `eutran-13` | 43 | 700 MHz c |
| | `eutran-14` | 44 | 700 MHz PS |
| | `eutran-17` | 47 | 700 MHz b |
| | `eutran-18` | 48 | 800 MHz |
| | `eutran-19` | 49 | 800 MHz |
| | `eutran-20` | 50 | 800 MHz DD |
| | `eutran-21` | 51 | 1500 MHz |
| | `eutran-25` | 55 | 1900 MHz+ |
| | `eutran-26` | 56 | 850 MHz+ |
| | `eutran-28` | 58 | 700 MHz APT |
| | `eutran-41` | 71 | 2500 MHz |
| | `eutran-66` | 96 | 1700/2100 MHz |
| | `eutran-71` | 101 | 600 MHz |
| **5G NR (NGRAN)** | `ngran-1` | 301 | 2100 MHz |
| | `ngran-2` | 302 | 1900 MHz |
| | `ngran-3` | 303 | 1800 MHz |
| | `ngran-5` | 305 | 850 MHz |
| | `ngran-7` | 307 | 2600 MHz |
| | `ngran-8` | 308 | 900 MHz |
| | `ngran-12` | 312 | 700 MHz |
| | `ngran-13` | 313 | 700 MHz c |
| | `ngran-14` | 314 | 700 MHz PS |
| | `ngran-18` | 318 | 800 MHz |
| | `ngran-20` | 320 | 800 MHz DD |
| | `ngran-25` | 325 | 1900 MHz |
| | `ngran-26` | 326 | 850 MHz |
| | `ngran-28` | 328 | 700 MHz APT |
| | `ngran-29` | 329 | 700 MHz SDL |
| | `ngran-30` | 330 | 2300 MHz |
| | `ngran-34` | 334 | 2010 MHz TDD |
| | `ngran-38` | 338 | 2600 MHz TDD |
| | `ngran-39` | 339 | 1900 MHz TDD |
| | `ngran-40` | 340 | 2300 MHz TDD |
| | `ngran-41` | 341 | 2500 MHz TDD |
| | `ngran-48` | 348 | 3600 MHz CBRS |
| | `ngran-50` | 350 | 1500 MHz SDL |
| | `ngran-51` | 351 | 1500 MHz |
| | `ngran-53` | 353 | 2400 MHz |
| | `ngran-65` | 365 | 2100 MHz |
| | `ngran-66` | 366 | 1700/2100 MHz AWS |
| | `ngran-67` | 367 | 700 MHz EU SDL |
| | `ngran-70` | 370 | 1700/2100 MHz |
| | `ngran-71` | 371 | 600 MHz |
| | `ngran-74` | 374 | 1400 MHz SDL |
| | `ngran-75` | 375 | 1500 MHz SDL |
| | `ngran-76` | 376 | 1500 MHz SDL |
| | `ngran-77` | 377 | 3700 MHz TDD |
| | `ngran-78` | 378 | 3500 MHz TDD |
| | `ngran-79` | 379 | 4700 MHz TDD |
| | `ngran-80` | 380 | 1800 MHz SUL |
| | `ngran-81` | 381 | 900 MHz SUL |
| | `ngran-82` | 382 | 800 MHz SUL |
| | `ngran-83` | 383 | 700 MHz SUL |
| | `ngran-84` | 384 | 2100 MHz SUL |
| | `ngran-86` | 386 | 1700 MHz SUL |
| | `ngran-89` | 389 | 800 MHz SUL |
| | `ngran-90` | 390 | 2500 MHz TDD |
| | `ngran-91` | 391 | 800/1400 MHz |
| | `ngran-92` | 392 | 800/700 MHz |
| | `ngran-93` | 393 | 900/1500 MHz |
| | `ngran-94` | 394 | 880/1400 MHz |
| | `ngran-95` | 395 | 2100 MHz SUL |
| **5G NR FR2 (mmWave)** | `ngran-257` | 557 | 28 GHz mmWave |
| | `ngran-258` | 558 | 26 GHz mmWave |
| | `ngran-260` | 560 | 39 GHz mmWave |
| | `ngran-261` | 561 | 28 GHz mmWave |

### Timeouts

> **If unconfigured:** Connection 120 s, registration 180 s, CONNECTED-state poll every 30 s.

```
set interfaces wwan wwan0 timeouts connection 120
set interfaces wwan wwan0 timeouts registration 180
set interfaces wwan wwan0 timeouts normal-monitoring-interval 30
```

### Logging and Monitoring

> **If unconfigured:** Level `info`, sink `both` (journal + syslog), verbose on, SNMP on, detailed-status on, health-check every 300 s.

```
set interfaces wwan wwan0 logging level 'info'
set interfaces wwan wwan0 logging sink 'both'
set interfaces wwan wwan0 logging health-check-interval 300
# To disable (all on by default):
# set interfaces wwan wwan0 logging disable-verbose
# set interfaces wwan wwan0 logging disable-snmp-monitoring
# set interfaces wwan wwan0 logging disable-detailed-status
```

---

## Config Mapping Reference

> Parameters marked *(VyOS conf_mode)* are handled by the VyOS configuration
> script directly (kernel sysctl / ip commands) and do not appear in
> `my_config.conf`.

| VyOS `set` Command | `my_config.conf` Key | Default |
|---|---|---|
| **VyOS Infrastructure** | | |
| `description` | *(VyOS conf_mode)* | `(empty)` |
| `disable` | `interface_disabled` | `false` (admin-up) |
| `vrf` | *(VyOS conf_mode)* | not set (default VRF) |
| `redirect` | *(VyOS conf_mode)* | not set |
| `mirror ingress` | *(VyOS conf_mode)* | not set |
| `mirror egress` | *(VyOS conf_mode)* | not set |
| `ip adjust-mss` | *(VyOS conf_mode)* | not set |
| `ip disable-forwarding` | *(VyOS conf_mode)* | not set (forwarding on) |
| `ip source-validation` | *(VyOS conf_mode)* | `disable` |
| `ipv6 adjust-mss` | *(VyOS conf_mode)* | not set |
| `ipv6 disable-forwarding` | *(VyOS conf_mode)* | not set (forwarding on) |
| `ipv6 source-validation` | *(VyOS conf_mode)* | `disable` |
| `pd N interface X address` | *(FSM native PD)* | EUI-64 |
| `pd N interface X sla-id` | *(FSM native PD)* | not set |
| `pd N interface X sla-len` | *(FSM native PD)* | `64 − carrier prefix len` (→ /64s) |
| `pd-reconciliation-interval` | `pd_reconciliation_interval` | `10` |
| **WWAN Service** | | |
| `sim primary-slot` | `primary_sim_slot` | `1` |
| `sim sim-failback disable` | `sim_failback_enabled` | `enabled` |
| `sim sim-failback check-interval` | `sim_failback_check_interval` | `600` |
| `sim sim-failover disable` | `sim_failover` | `enabled` |
| `sim sim-failover connect-retries` | `sim_failover_connect_retries` | `3` |
| `sim sim-failover revert-timer` | `sim_failover_revert_timer` | `300` |
| `sim sim-failover signal-loss-timer` | `sim_failover_signal_loss_timer` | `60` |
| `sim sim-failover signal-threshold` | `sim_failover_signal_threshold` | `-90` |
| `sim slot N apn` | `sim_slot_N_apn` | `(empty)` |
| `sim slot N username` | `sim_slot_N_username` | `(empty)` |
| `sim slot N password` | `sim_slot_N_password` | `(empty)` |
| `sim slot N auth-type` | `sim_slot_N_auth_type` | `none` |
| `sim slot N pdp-type` | `sim_slot_N_pdp_type` | `ipv4` |
| `sim slot N disable-roaming` | `sim_slot_N_roaming` | `enabled` |
| `sim slot N pin` | `sim_slot_N_pin` | `(empty)` |
| `sim slot N puk` | `sim_slot_N_puk` | `(empty)` |
| `sim slot N iccid` | `sim_slot_N_iccid` | `(empty)` |
| `sim slot N supported-bands` | `sim_slot_N_supported_bands` | `all` |
| `sim slot N preferred-carrier` | `sim_slot_N_preferred_carrier` | `(empty)` |
| `sim slot N enable-network-scan` | `sim_slot_N_enable_network_scan` | `false` |
| `sim slot N mtu` | `sim_slot_N_mtu` | `0` (use interface mtu) |
| `sim slot N data-limit size` | `sim_slot_N_data_limit_size` | `0` |
| `sim slot N data-limit action` | `sim_slot_N_data_limit_action` | `none` |
| `sim slot N data-limit billing-date` | `sim_slot_N_data_limit_billing_date` | `1` |
| `sim slot N data-limit warning` | `sim_slot_N_data_limit_warning` | `(empty)` |
| `sim slot N disable` | *(D-Bus only)* | both enabled (no `disable` set) |
| `apn-discovery disable` | `android_apn_discovery` | `enabled` |
| `connection-mode` | `connection_mode` | `always-on` |
| `reconnection disable-enhanced` | `enhanced_reconnection` | `enabled` |
| `reconnection signal-threshold` | `reconnection_signal_threshold` | `-85` |
| `reconnection retry-interval good-signal` | `retry_interval_good_signal` | `30` |
| `reconnection retry-interval poor-signal` | `retry_interval_poor_signal` | `120` |
| `reconnection max-wait-for-signal` | `max_wait_for_signal` | `120` |
| `reconnection signal-check-interval` | `signal_check_interval` | `10` |
| `reconnection signal-strength-buffer` | `signal_strength_buffer` | `5` |
| `interface-management disable` | `interface_management_enabled` | `true` |
| `interface-management bearer-disconnect-delay` | `bearer_disconnect_delay` | `15` |
| `interface-management registration-recovery-delay` | `registration_recovery_delay` | `20` |
| `interface-management registration-flap-count` | `registration_flap_count` | `5` |
| `interface-management registration-flap-window` | `registration_flap_window` | `360` |
| `interface-management ip-change-delay` | `ip_change_delay` | `500` |
| `interface-management disable-ensure-link-up-on-connect` | `ensure_link_up_on_connect` | `true` |
| `interface-management disable-monitor-bearer-state` | `monitor_bearer_state` | `true` |
| `interface-management disable-monitor-ip-changes` | `monitor_ip_changes` | `true` |
| `interface-management interface-up-timeout` | `interface_up_timeout` | `10` |
| `connectivity-monitoring disable` | `connectivity_monitoring_enabled` | `true` |
| `connectivity-monitoring interval` | `connectivity_monitoring_interval` | `60` |
| `connectivity-monitoring timeout` | `connectivity_monitoring_timeout` | `10` |
| `connectivity-monitoring retry-count` | `connectivity_monitoring_retry_count` | `3` |
| `connectivity-monitoring failure-threshold` | `connectivity_monitoring_failure_threshold` | `2` |
| `connectivity-monitoring disable-test-ipv4` | `connectivity_monitoring_test_ipv4` | `true` |
| `connectivity-monitoring test-ipv6` | `connectivity_monitoring_test_ipv6` | `false` |
| `connectivity-monitoring require-both` | `connectivity_monitoring_require_both` | `false` |
| `connectivity-monitoring ipv4-targets` | `connectivity_monitoring_ipv4_targets` | `8.8.8.8,1.1.1.1` |
| `connectivity-monitoring ipv6-targets` | `connectivity_monitoring_ipv6_targets` | `2001:4860:...` |
| `data-usage monitoring-interval` | `data_usage_monitoring_interval` | `30` |
| `data-usage size` | `data_limit_size` | `0` |
| `data-usage action` | `data_limit_action` | `none` |
| `data-usage billing-date` | `data_limit_billing_date` | `1` |
| `data-usage warning` | `data_limit_warning` | `(empty)` |
| `hardware-reset disable` | `hardware_reset_enabled` | `true` |
| `hardware-reset max-attempts` | `max_hardware_resets` | `3` |
| `hardware-reset cooldown` | `hardware_reset_cooldown` | `300` |
| `failed-retry disable` | `failed_retry_enabled` | `true` |
| `failed-retry intervals` | `failed_retry_intervals` | `600,1800,3600,7200` |
| `failed-retry max-interval` | `failed_retry_max_interval` | `7200` |
| `failed-retry escalation-threshold` | `failed_retry_escalation_threshold` | `3` |
| `network-mode` | `network_mode` | `auto` |
| `mtu` | `mtu` | `1420` |
| `network-scan timeout` | `network_scan_timeout` | `60` |
| `timeouts connection` | `connection_timeout` | `120` |
| `timeouts registration` | `registration_timeout` | `180` |
| `timeouts normal-monitoring-interval` | `normal_monitoring_interval` | `30` |
| `logging level` | `log_level` | `info` |
| `logging sink` | `log_sink` | `both` |
| `logging disable-verbose` | `verbose_logging` | `true` |
| `logging disable-snmp-monitoring` | `snmp_monitoring` | `true` |
| `logging disable-detailed-status` | `detailed_status` | `true` |
| `logging health-check-interval` | `system_health_check_interval` | `300` |

---

## Example: Bell Canada Dual-SIM with Monitoring

```
set interfaces wwan wwan0 description 'Primary LTE uplink — Bell Canada'
set interfaces wwan wwan0 mtu 1420

set interfaces wwan wwan0 sim primary-slot 1
set interfaces wwan wwan0 sim slot 1 apn 'pda.bell.ca'
set interfaces wwan wwan0 sim slot 1 auth-type 'chap'
set interfaces wwan wwan0 sim slot 1 pdp-type 'ipv4v6'
set interfaces wwan wwan0 sim slot 1 pin '1234'
set interfaces wwan wwan0 sim slot 1 data-limit size 5000000000
set interfaces wwan wwan0 sim slot 1 data-limit action 'disable'
set interfaces wwan wwan0 sim slot 1 data-limit billing-date 1

set interfaces wwan wwan0 sim slot 2 pin '5678'
set interfaces wwan wwan0 sim slot 2 data-limit action 'sim-failover'

# sim-failover and sim-failback are enabled by default — no 'enable' command needed
# To disable: set interfaces wwan wwan0 sim sim-failover disable

# apn-discovery is enabled by default — to disable:
# set interfaces wwan wwan0 apn-discovery disable
# reconnection enhanced is on by default — to disable:
# set interfaces wwan wwan0 reconnection disable-enhanced
set interfaces wwan wwan0 reconnection signal-threshold -85

# connectivity-monitoring and interface-management are enabled by default
set interfaces wwan wwan0 connectivity-monitoring interval 60
set interfaces wwan wwan0 connectivity-monitoring failure-threshold 2
set interfaces wwan wwan0 connectivity-monitoring ipv4-targets '8.8.8.8,1.1.1.1,9.9.9.9'

set interfaces wwan wwan0 interface-management registration-recovery-delay 20
set interfaces wwan wwan0 interface-management bearer-disconnect-delay 15

# hardware-reset is on by default — to disable:
# set interfaces wwan wwan0 hardware-reset disable
set interfaces wwan wwan0 logging level 'info'
```
