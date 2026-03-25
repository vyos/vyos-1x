# VyOS WWAN Enhanced Interface — `set` Command Reference

This document defines the VyOS CLI `set` commands that map to the
`my_config.conf` parameters for the enhanced WWAN interface management service.

All commands are under:
```
set interfaces wwan <wwanN> ...
```

The existing upstream VyOS WWAN commands (`apn`, `authentication`, `connect-on-demand`,
`address`, `mtu`, `vrf`, etc.) are preserved. The new commands extend the hierarchy.

---

## Configuration Tree

```
interfaces
  └── wwan <wwanN>
        ├── connection-mode <always-on|connect-on-demand|dial-on-demand>  # NEW
        ├── network-mode <auto|lte|5g|3g|2g>              # NEW — modem-level RAT selection
        │
        ├── sim                                           # NEW — SIM management
        │     ├── active-slot <1|2>
        │     │
        │     ├── slot <1|2>                              #   per-SIM tag node
        │     │     ├── enable                            #   valueless, default: on (slot 1), off (slot 2)
        │     │     ├── apn <name>
        │     │     ├── username <text>
        │     │     ├── password <text>
        │     │     ├── auth-type <none|pap|chap|both>
        │     │     ├── pdp-type <ipv4|ipv6|ipv4v6>
        │     │     ├── roaming                           #   valueless
        │     │     ├── pin <4-8 digits>                  #   if set, SIM is auto-unlocked
        │     │     ├── puk <8 digits>                     #   PUK for auto-recovery (resets PIN)
        │     │     ├── supported-bands <all|band,band,...>
        │     │     ├── preferred-carrier <MCCMNC|name>  #   e.g. '302610' or 'Bell'
        │     │     ├── enable-network-scan               #   valueless — diagnostic scan; results in status
        │     │     └── data-limit
        │     │           ├── size <bytes>                #   0 = unlimited
        │     │           ├── action <disable|alert|block|sim-failover|sim-failover-sticky>
        │     │           └── billing-date <1-28>
        │     │
        │     ├── sim-failback
        │     |     ├── enable                            #   valueless
        │     |     └── check-interval <seconds>          #   default: 600
        │     │
        │     └── sim-failover
        │           ├── enable                            #   valueless
        │           ├── connect-retries <count>           #   default: 3
        │           ├── revert-timer <seconds>            #   default: 300
        │           ├── signal-loss-timer <seconds>       #   default: 60
        │           └── signal-threshold <dBm>            #   default: -90
        │
        ├── apn-discovery
        │     └── android                                 #   valueless — enable Android APN DB
        │
        ├── reconnection
        │     ├── enhanced                                #   valueless — enable signal-aware reconnection
        │     ├── signal-threshold <dBm>                  #   default: -85
        │     ├── retry-interval
        │     │     ├── good-signal <seconds>             #   default: 15
        │     │     └── poor-signal <seconds>             #   default: 45
        │     ├── max-wait-for-signal <seconds>           #   default: 120
        │     ├── signal-check-interval <seconds>         #   default: 10
        │     └── signal-strength-buffer <dBm>            #   default: 5
        │
        ├── interface-management
        │     ├── enable                                  #   valueless, default: on
        │     ├── bearer-disconnect-delay <seconds>       #   default: 15
        │     ├── registration-recovery-delay <seconds>   #   default: 20
        │     ├── ip-change-delay <seconds>               #   default: 0.5
        │     ├── ensure-link-up-on-connect               #   valueless, default: on
        │     ├── monitor-bearer-state                    #   valueless, default: on
        │     ├── monitor-ip-changes                      #   valueless, default: on
        │     └── interface-up-timeout <seconds>          #   default: 10
        │
        ├── connectivity-monitoring
        │     ├── enable                                  #   valueless
        │     ├── interval <seconds>                      #   default: 60
        │     ├── timeout <seconds>                       #   default: 10
        │     ├── retry-count <count>                     #   default: 3
        │     ├── failure-threshold <count>               #   default: 2
        │     ├── test-ipv4                               #   valueless, default: on
        │     ├── test-ipv6                               #   valueless
        │     ├── require-both                            #   valueless
        │     ├── ipv4-targets <addr,addr,...>            #   default: 8.8.8.8,1.1.1.1
        │     └── ipv6-targets <addr,addr,...>            #   default: 2001:4860:4860::8888,...
        │
        ├── data-usage
        │     ├── monitoring-interval <seconds>           #   default: 30
        │     ├── warning-thresholds <pct,pct,...>        #   default: 75,90,95
        │     └── default-limit                           #   global fallback for per-SIM
        │           ├── size <bytes>                      #   default: 0 (unlimited)
        │           ├── action <disable|alert|block|sim-failover|sim-failover-sticky>  #   default: disable
        │           └── billing-date <1-28>               #   default: 1
        │
        ├── hardware-reset
        │     ├── enable                                  #   valueless, default: on
        │     ├── max-attempts <count>                    #   default: 3
        │     └── cooldown <seconds>                      #   default: 300
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
              ├── verbose                                 #   valueless
              ├── snmp-monitoring                         #   valueless
              ├── detailed-status                         #   valueless
              └── health-check-interval <seconds>         #   default: 300
```

---

## Default Behavior — Zero Configuration

If no `set interfaces wwan wwanN …` commands are issued beyond bringing the
interface up, the following defaults apply.  The modem will attempt to connect
automatically using a 4-priority APN discovery chain:

| Feature | Default (nothing configured) | Effect |
|---|---|---|
| **Active SIM slot** | `1` | Slot 1 is used |
| **APN** | per-SIM only, `(empty)` — triggers auto-discovery | Priority chain: 1) per-SIM configured APN, 1.5) in-memory last-connected APN, 3) Android APN DB (if enabled), 4) automatic (let the network assign) |
| **Authentication** | per-SIM only, default `none` | No PPP auth; auth-type/username/password configured per SIM slot |
| **PDP type** | per-SIM only, default `ipv4` | IPv4-only bearer per slot unless overridden |
| **Roaming** | per-SIM only, default `disabled` | Modem will not register on visited networks unless enabled per slot |
| **Network mode** | `auto` | Modem selects best available RAT (5G→LTE→3G→2G) |
| **SIM PIN** | per-SIM only | If a PIN is configured, the FSM always sends it automatically when the SIM is locked |
| **SIM failover** | per-SIM, `disabled` | Enable per slot: allows automatic switch to another SIM on failure |
| **SIM failback** | `disabled` | Even if sim-failover fires, no automatic return to primary |
| **APN discovery (Android)** | `disabled` | Only configured / automatic APNs are tried |
| **Connection mode** | `always-on` | Modem connects immediately at boot and stays connected |
| **Enhanced reconnection** | `disabled` | Fixed retry intervals; no signal-quality awareness |
| **Reconnection retry** | good-signal `15 s`, poor-signal `45 s` | (only effective when enhanced reconnection is enabled) |
| **Signal threshold** | `-85 dBm` | Boundary between "good" and "poor" reconnection strategies |
| **Bearer disconnect delay** | `15 s` | Grace period before tearing down a disconnected bearer |
| **Registration recovery delay** | `20 s` | Debounce for registration-lost flaps |
| **IP change delay** | `0.5 s` | Settle time after IP re-assignment |
| **Interface management** | `enabled` | Master on/off for bearer, registration, IP monitoring subsystem |
| **Link / bearer / IP monitoring** | all `enabled` | Interface-up enforcement, bearer-state tracking, IP-change detection all active |
| **Interface-up timeout** | `10 s` | Max wait for kernel interface to come up after bearer connect |
| **Connectivity monitoring** | `disabled` | No active ping probes; dead path undetected until bearer drops |
| **Connectivity ping targets** | IPv4: `8.8.8.8, 1.1.1.1`; IPv6: Google/Cloudflare DNS | (only effective when monitoring is enabled) |
| **SIM Failover** | `disabled` | No automatic switchover on signal loss or connect failures |
| **Data limits (per-SIM)** | size `0` (unlimited), action `disable`, billing-date `1` | No data cap enforcement |
| **Data limits (global fallback)** | size `0`, action `disable`, billing-date `1` | Applies when per-SIM values are not set |
| **Data usage monitoring** | interval `30 s`, thresholds `75%, 90%, 95%` | Counters tracked; warnings logged at thresholds (no action) |
| **Hardware reset** | `enabled`, max `3` attempts, cooldown `300 s` | Modem power-cycles after repeated unrecoverable failures |
| **Band selection** | `all` | All modem-supported radio technologies enabled |
| **Network scan timeout** | `60 s` | Max wait for network scan completion |
| **Connection timeout** | `120 s` | Max wait for MM `Simple.Connect()` to succeed |
| **Registration timeout** | `180 s` | Max wait for network registration |
| **Normal monitoring interval** | `30 s` | Polling cycle in CONNECTED state |
| **Logging** | level `info`, verbose `on`, SNMP `on`, detailed-status `on` | Full operational logging enabled by default |
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

### Basic / Existing Commands

> **If unconfigured:** Network-mode auto.  APN, auth-type, PDP-type, roaming, username/password are all per-SIM only.

```
set interfaces wwan wwan0 network-mode 'auto'
```

### SIM Configuration

> **If unconfigured:** Slot 1 active, no sim-failover, single-SIM operation.  PIN/PUK are per-SIM only (no global default).

```
set interfaces wwan wwan0 sim active-slot 1

# Per-SIM slot configuration
set interfaces wwan wwan0 sim slot 1 enable
set interfaces wwan wwan0 sim slot 1 apn 'pda.bell.ca'
set interfaces wwan wwan0 sim slot 1 username ''
set interfaces wwan wwan0 sim slot 1 password ''
set interfaces wwan wwan0 sim slot 1 auth-type 'chap'
set interfaces wwan wwan0 sim slot 1 pdp-type 'ipv4v6'
set interfaces wwan wwan0 sim slot 1 roaming
set interfaces wwan wwan0 sim slot 1 pin '1234'
set interfaces wwan wwan0 sim slot 1 puk '12345678'
set interfaces wwan wwan0 sim slot 1 supported-bands 'all'
set interfaces wwan wwan0 sim slot 1 preferred-carrier '302610'
set interfaces wwan wwan0 sim slot 1 enable-network-scan
set interfaces wwan wwan0 sim slot 1 data-limit size 5000000000
set interfaces wwan wwan0 sim slot 1 data-limit action 'disable'
set interfaces wwan wwan0 sim slot 1 data-limit billing-date 1

set interfaces wwan wwan0 sim slot 2 apn 'backup.apn'
set interfaces wwan wwan0 sim slot 2 auth-type 'none'
set interfaces wwan wwan0 sim slot 2 pdp-type 'ipv4'
set interfaces wwan wwan0 sim slot 2 pin '5678'
set interfaces wwan wwan0 sim slot 2 data-limit size 0
set interfaces wwan wwan0 sim slot 2 data-limit action 'sim-failover'
set interfaces wwan wwan0 sim slot 2 data-limit billing-date 1

# SIM failback
set interfaces wwan wwan0 sim sim-failback enable
set interfaces wwan wwan0 sim sim-failback check-interval 600

# SIM failover
set interfaces wwan wwan0 sim sim-failover enable
set interfaces wwan wwan0 sim sim-failover connect-retries 3
set interfaces wwan wwan0 sim sim-failover revert-timer 300
set interfaces wwan wwan0 sim sim-failover signal-loss-timer 60
set interfaces wwan wwan0 sim sim-failover signal-threshold -90
```

### APN Discovery

> **If unconfigured:** Android APN database lookup is disabled.  Only configured APN, in-memory last-connected APN, and automatic (network-assigned) APN are tried.

```
set interfaces wwan wwan0 apn-discovery android
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

> **If unconfigured:** Basic fixed-interval reconnection.  Signal-quality-aware retry spacing only activates when `reconnection enhanced` is set.

```
set interfaces wwan wwan0 reconnection enhanced
set interfaces wwan wwan0 reconnection signal-threshold -85
set interfaces wwan wwan0 reconnection retry-interval good-signal 15
set interfaces wwan wwan0 reconnection retry-interval poor-signal 45
set interfaces wwan wwan0 reconnection max-wait-for-signal 120
set interfaces wwan wwan0 reconnection signal-check-interval 10
set interfaces wwan wwan0 reconnection signal-strength-buffer 5
```

### Interface Management

> **If unconfigured:** All monitors active (bearer-state, IP-changes, link-up enforcement).  Delays: bearer-disconnect 15 s, registration-recovery 20 s, IP-change 0.5 s, interface-up timeout 10 s.

```
set interfaces wwan wwan0 interface-management enable
set interfaces wwan wwan0 interface-management bearer-disconnect-delay 15
set interfaces wwan wwan0 interface-management registration-recovery-delay 20
set interfaces wwan wwan0 interface-management ip-change-delay 0.5
set interfaces wwan wwan0 interface-management ensure-link-up-on-connect
set interfaces wwan wwan0 interface-management monitor-bearer-state
set interfaces wwan wwan0 interface-management monitor-ip-changes
set interfaces wwan wwan0 interface-management interface-up-timeout 10
```

### Connectivity Health Monitoring

> **If unconfigured:** Disabled — no active ping probes.  A dead path (e.g. carrier-side routing failure) goes undetected until the bearer itself drops.

```
set interfaces wwan wwan0 connectivity-monitoring enable
set interfaces wwan wwan0 connectivity-monitoring interval 60
set interfaces wwan wwan0 connectivity-monitoring timeout 10
set interfaces wwan wwan0 connectivity-monitoring retry-count 3
set interfaces wwan wwan0 connectivity-monitoring failure-threshold 2
set interfaces wwan wwan0 connectivity-monitoring test-ipv4
set interfaces wwan wwan0 connectivity-monitoring test-ipv6
set interfaces wwan wwan0 connectivity-monitoring require-both
set interfaces wwan wwan0 connectivity-monitoring ipv4-targets '8.8.8.8,1.1.1.1,9.9.9.9'
set interfaces wwan wwan0 connectivity-monitoring ipv6-targets '2001:4860:4860::8888,2606:4700:4700::1111'
```

### SIM Failover Policy

> **If unconfigured:** Disabled — no automatic SIM switchover on sustained signal loss or repeated connect failures.

```
set interfaces wwan wwan0 sim sim-failover enable
set interfaces wwan wwan0 sim sim-failover connect-retries 3
set interfaces wwan wwan0 sim sim-failover revert-timer 300
set interfaces wwan wwan0 sim sim-failover signal-loss-timer 60
set interfaces wwan wwan0 sim sim-failover signal-threshold -90
```

### Data Usage Monitoring

> **If unconfigured:** Counters still tracked (30 s interval, thresholds 75/90/95%).  Warnings logged but no enforcement action unless a per-SIM `data-limit` is configured.

**Data-limit actions:**
| Action | Behaviour |
|---|---|
| `disable` | Disconnect bearer when limit hit |
| `alert` | Log warning only — no enforcement |
| `block` | *(reserved for future use)* |
| `sim-failover` | Switch to backup SIM; failback resumes normally when `sim-failback` is enabled |
| `sim-failover-sticky` | Switch to backup SIM **and suppress failback** until the billing cycle resets — avoids overage charges on the primary SIM |

```
set interfaces wwan wwan0 data-usage monitoring-interval 30
set interfaces wwan wwan0 data-usage warning-thresholds '75,90,95'
set interfaces wwan wwan0 data-usage default-limit size 0
set interfaces wwan wwan0 data-usage default-limit action 'disable'
set interfaces wwan wwan0 data-usage default-limit billing-date 1
```

### Hardware Reset

> **If unconfigured:** Enabled — up to 3 modem power-cycle attempts with 300 s cooldown on unrecoverable failures.

```
set interfaces wwan wwan0 hardware-reset enable
set interfaces wwan wwan0 hardware-reset max-attempts 3
set interfaces wwan wwan0 hardware-reset cooldown 300
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
| **5G NR (NGRAN)** | `ngran-1` | 128 | 2100 MHz |
| | `ngran-2` | 129 | 1900 MHz |
| | `ngran-3` | 130 | 1800 MHz |
| | `ngran-5` | 132 | 850 MHz |
| | `ngran-7` | 134 | 2600 MHz |
| | `ngran-8` | 135 | 900 MHz |
| | `ngran-12` | 139 | 700 MHz |
| | `ngran-20` | 147 | 800 MHz |
| | `ngran-25` | 152 | 1900 MHz |
| | `ngran-28` | 155 | 700 MHz |
| | `ngran-41` | 168 | 2500 MHz |
| | `ngran-66` | 193 | 1700/2100 MHz |
| | `ngran-71` | 198 | 600 MHz |
| | `ngran-77` | 204 | 3700 MHz |
| | `ngran-78` | 205 | 3500 MHz |
| | `ngran-79` | 206 | 4700 MHz |

### Timeouts

> **If unconfigured:** Connection 120 s, registration 180 s, CONNECTED-state poll every 30 s.

```
set interfaces wwan wwan0 timeouts connection 120
set interfaces wwan wwan0 timeouts registration 180
set interfaces wwan wwan0 timeouts normal-monitoring-interval 30
```

### Logging and Monitoring

> **If unconfigured:** Level `info`, verbose on, SNMP on, detailed-status on, health-check every 300 s.

```
set interfaces wwan wwan0 logging level 'info'
set interfaces wwan wwan0 logging verbose
set interfaces wwan wwan0 logging snmp-monitoring
set interfaces wwan wwan0 logging detailed-status
set interfaces wwan wwan0 logging health-check-interval 300
```

---

## Config Mapping Reference

| VyOS `set` Command | `my_config.conf` Key | Default |
|---|---|---|
| `sim active-slot` | `active_sim_slot` | `1` |
| `sim sim-failback enable` | `sim_failback_enabled` | `disabled` |
| `sim sim-failback check-interval` | `sim_failback_check_interval` | `600` |
| `sim sim-failover enable` | `sim_failover` | `disabled` |
| `sim sim-failover connect-retries` | `sim_failover_connect_retries` | `3` |
| `sim sim-failover revert-timer` | `sim_failover_revert_timer` | `300` |
| `sim sim-failover signal-loss-timer` | `sim_failover_signal_loss_timer` | `60` |
| `sim sim-failover signal-threshold` | `sim_failover_signal_threshold` | `-90` |
| `sim slot N apn` | `sim_slot_N_apn` | `(empty)` |
| `sim slot N username` | `sim_slot_N_username` | `(empty)` |
| `sim slot N password` | `sim_slot_N_password` | `(empty)` |
| `sim slot N auth-type` | `sim_slot_N_auth_type` | `none` |
| `sim slot N pdp-type` | `sim_slot_N_pdp_type` | `ipv4` |
| `sim slot N roaming` | `sim_slot_N_roaming` | `disabled` |
| `sim slot N pin` | `sim_slot_N_pin` | `(empty)` |
| `sim slot N puk` | `sim_slot_N_puk` | `(empty)` |
| `sim slot N supported-bands` | `sim_slot_N_supported_bands` | `all` |
| `sim slot N preferred-carrier` | `sim_slot_N_preferred_carrier` | `(empty)` |
| `sim slot N enable-network-scan` | `sim_slot_N_enable_network_scan` | `false` |
| `sim slot N data-limit size` | `sim_slot_N_data_limit_size` | `0` |
| `sim slot N data-limit action` | `sim_slot_N_data_limit_action` | `disable` |
| `sim slot N data-limit billing-date` | `sim_slot_N_data_limit_billing_date` | `1` |
| `sim slot N enable` | *(D-Bus only)* | slot 1: `true`, slot 2: `false` |
| `apn-discovery android` | `android_apn_discovery` | `disabled` |
| `connection-mode` | `connection_mode` | `always-on` |
| `reconnection enhanced` | `enhanced_reconnection` | `disabled` |
| `reconnection signal-threshold` | `reconnection_signal_threshold` | `-85` |
| `reconnection retry-interval good-signal` | `retry_interval_good_signal` | `15` |
| `reconnection retry-interval poor-signal` | `retry_interval_poor_signal` | `45` |
| `reconnection max-wait-for-signal` | `max_wait_for_signal` | `120` |
| `reconnection signal-check-interval` | `signal_check_interval` | `10` |
| `reconnection signal-strength-buffer` | `signal_strength_buffer` | `5` |
| `interface-management enable` | `interface_management_enabled` | `true` |
| `interface-management bearer-disconnect-delay` | `bearer_disconnect_delay` | `15` |
| `interface-management registration-recovery-delay` | `registration_recovery_delay` | `20` |
| `interface-management ip-change-delay` | `ip_change_delay` | `0.5` |
| `interface-management ensure-link-up-on-connect` | `ensure_link_up_on_connect` | `true` |
| `interface-management monitor-bearer-state` | `monitor_bearer_state` | `true` |
| `interface-management monitor-ip-changes` | `monitor_ip_changes` | `true` |
| `interface-management interface-up-timeout` | `interface_up_timeout` | `10` |
| `connectivity-monitoring enable` | `connectivity_monitoring_enabled` | `false` |
| `connectivity-monitoring interval` | `connectivity_monitoring_interval` | `60` |
| `connectivity-monitoring timeout` | `connectivity_monitoring_timeout` | `10` |
| `connectivity-monitoring retry-count` | `connectivity_monitoring_retry_count` | `3` |
| `connectivity-monitoring failure-threshold` | `connectivity_monitoring_failure_threshold` | `2` |
| `connectivity-monitoring test-ipv4` | `connectivity_monitoring_test_ipv4` | `true` |
| `connectivity-monitoring test-ipv6` | `connectivity_monitoring_test_ipv6` | `false` |
| `connectivity-monitoring require-both` | `connectivity_monitoring_require_both` | `false` |
| `connectivity-monitoring ipv4-targets` | `connectivity_monitoring_ipv4_targets` | `8.8.8.8,1.1.1.1` |
| `connectivity-monitoring ipv6-targets` | `connectivity_monitoring_ipv6_targets` | `2001:4860:...` |
| `data-usage monitoring-interval` | `data_usage_monitoring_interval` | `30` |
| `data-usage warning-thresholds` | `data_usage_warning_thresholds` | `75,90,95` |
| `data-usage default-limit size` | `data_limit_size` | `0` |
| `data-usage default-limit action` | `data_limit_action` | `disable` |
| `data-usage default-limit billing-date` | `data_limit_billing_date` | `1` |
| `hardware-reset enable` | `hardware_reset_enabled` | `true` |
| `hardware-reset max-attempts` | `max_hardware_resets` | `3` |
| `hardware-reset cooldown` | `hardware_reset_cooldown` | `300` |
| `network-mode` | `network_mode` | `auto` |
| `network-scan timeout` | `network_scan_timeout` | `60` |
| `timeouts connection` | `connection_timeout` | `120` |
| `timeouts registration` | `registration_timeout` | `180` |
| `timeouts normal-monitoring-interval` | `normal_monitoring_interval` | `30` |
| `apn` | `apn` | *(removed — per-SIM only)* |
| `authentication username` | `username` | *(removed — per-SIM only)* |
| `authentication password` | `password` | *(removed — per-SIM only)* |
| `auth-type` | `auth_type` | *(removed — per-SIM only)* |
| `pdp-type` | `pdp_type` | *(removed — per-SIM only)* |
| `roaming` | `roaming` | *(removed — per-SIM only)* |
| `sim pin` | `pin` | *(removed — per-SIM only)* |
| `sim puk` | `puk` | *(removed — per-SIM only)* |
| `logging level` | `log_level` | `info` |
| `logging verbose` | `verbose_logging` | `true` |
| `logging snmp-monitoring` | `snmp_monitoring` | `true` |
| `logging detailed-status` | `detailed_status` | `true` |
| `logging health-check-interval` | `system_health_check_interval` | `300` |

---

## Example: Bell Canada Dual-SIM with Monitoring

```
set interfaces wwan wwan0 sim active-slot 1
set interfaces wwan wwan0 sim slot 1 apn 'pda.bell.ca'
set interfaces wwan wwan0 sim slot 1 auth-type 'chap'
set interfaces wwan wwan0 sim slot 1 pdp-type 'ipv4v6'
set interfaces wwan wwan0 sim slot 1 pin '1234'
set interfaces wwan wwan0 sim slot 1 data-limit size 5000000000
set interfaces wwan wwan0 sim slot 1 data-limit action 'disable'
set interfaces wwan wwan0 sim slot 1 data-limit billing-date 1

set interfaces wwan wwan0 sim slot 2 pin '5678'
set interfaces wwan wwan0 sim slot 2 data-limit action 'sim-failover'

set interfaces wwan wwan0 sim sim-failover enable

set interfaces wwan wwan0 apn-discovery android
set interfaces wwan wwan0 reconnection enhanced
set interfaces wwan wwan0 reconnection signal-threshold -85

set interfaces wwan wwan0 connectivity-monitoring enable
set interfaces wwan wwan0 connectivity-monitoring interval 60
set interfaces wwan wwan0 connectivity-monitoring failure-threshold 2
set interfaces wwan wwan0 connectivity-monitoring ipv4-targets '8.8.8.8,1.1.1.1,9.9.9.9'

set interfaces wwan wwan0 interface-management registration-recovery-delay 20
set interfaces wwan wwan0 interface-management bearer-disconnect-delay 15

set interfaces wwan wwan0 hardware-reset enable
set interfaces wwan wwan0 logging level 'info'
```
