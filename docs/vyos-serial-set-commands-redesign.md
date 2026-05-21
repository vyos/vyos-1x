# Serial CLI — Proposed Restructure (VyOS-idiomatic)

This document proposes a redesigned shape for the `serial` CLI tree.
It does **not** describe what is implemented today — see
[vyos-serial-set-commands.md](vyos-serial-set-commands.md) for that.

The goal: make the tree look and behave like the rest of VyOS
(`service console-server`, `service dhcp-server`, `interfaces ethernet`,
…) so that operators, completion scripts, and conf-mode code can rely
on the same idioms they use everywhere else.

---

## Existing in-tree precedent: `service console-server`

VyOS already ships a serial-port service that is almost exactly our
`ssh-direct` profile, and it is **the strongest signal of how the
VyOS maintainers expect a serial subsystem to look**. See
[interface-definitions/service_console-server.xml.in](../interface-definitions/service_console-server.xml.in)
and [src/conf_mode/service_console-server.py](../src/conf_mode/service_console-server.py).

```
service console-server
  device <ttySxxx | usbxbxpx>                  # tag node
    description <text>
    alias <name>                               # human-friendly console name
    speed <300|…|115200>
    data-bits <7|8>           # default: 8
    stop-bits <1|2>           # default: 1
    parity <even|odd|none>    # default: none
    ssh
      port <1-65535>
```

Three things this tells us, and we should match them exactly:

1. **Top-level lives under `service`, not `interfaces`.** The tag
   node is `service <feature> device <ttyName>`. We should follow
   the same shape — `service serial device <…>` — not invent a
   parallel `interfaces serial` tree.
2. **Hardware leaves are flat on `device`.** No `hardware { … }`
   wrapper. `speed`, `data-bits`, `stop-bits`, `parity` sit
   directly on the device.
3. **The transport is a subtree**, not a discriminator leaf.
   `ssh { port … }` is the SSH transport's configuration; the
   *presence* of the subtree enables the transport. No
   `service ssh-direct` + parallel `service-setting ssh …`
   indirection.

There is also an `alias` concept worth keeping — a stable
human-friendly name that decouples op-mode commands and references
from the kernel device name.

## What feels non-VyOS today

The current tree has five structural problems:

1. **`serial` is its own top-level keyword.**
   VyOS already has a serial subsystem — `service console-server` —
   that uses `service <name> device <ttyName>`. Having a second
   parallel top-level (`serial device <…>`) for the same physical
   ports is confusing and duplicates the device-tag-node shape that
   was already chosen by the project.

2. **`service` is a leaf that selects a profile, but `service-setting`
   is a separate parent that holds the config for *every* profile.**
   This is the biggest footgun. The CLI lets the user populate
   `service-setting modbus …` while `service` is set to `ssh-direct`,
   and the modbus subtree is silently ignored. VyOS convention is
   the opposite: the *presence of a subtree* is what enables a feature,
   and conf-mode rejects ambiguous combinations in `verify()`.

3. **`hardware { … }` artificially groups physical-layer leaves.**
   `service console-server device <tty>` already puts `speed`,
   `data-bits`, `stop-bits`, `parity` directly on the device node.
   Wrapping the same leaves under `hardware { … }` on a different
   tree (and adding more knobs to it) is inconsistent.

4. **`packet-forwarding mode <…>` mixes presets with raw knobs.**
   Three of the four modes are presets that ignore the sibling
   leaves; `custom` is the only mode that consumes them. VyOS
   normally exposes this as either a single preset *or* the raw
   knobs — not both wrapped in a discriminator leaf.

5. **`tls use-global` is a per-port leaf that disables every other
   per-port `tls.*` node.** VyOS handles "use a named template"
   via a referenced node elsewhere in the tree (PKI, named profiles,
   etc.), not via a hidden mode switch on the consumer.

A few smaller niggles:

- `multihost-list host <1-50>` and `udp entry <1-4>` use numeric tag
  IDs. VyOS prefers descriptive name-tag nodes
  (`host <name> { address … port … }`) and only uses numeric IDs
  when ordering is semantically required (firewall rule N).
- `vmodem-phone-list entry <1-8>` is the same shape — should be
  keyed by phone number or by a free-form name.
- Global `keepalive` is referenced by a per-port valueless flag
  (`device <…> keepalive`). VyOS convention is either: every
  consumer has its own `keepalive { interval … retries … }` block
  with defaults, or a *named* keepalive profile that can be selected.

---

## Proposed shape

Top-level merges with `service console-server` under `service serial`,
reusing the `device <ttyName>` tag-node shape that VyOS already uses.
Per-user ACLs stay on `system login user`.

```
set service serial device <ttySxxx | usbxbxpx> ...
set service serial global ...           # system-wide serial daemons / shared state
set system login user <name> serial ... # unchanged — per-user ACL/timeout
```

`service serial global` (new) replaces today's `serial global` for
things that are genuinely system-wide (modbus-tcp gateway, vmodem
phone book, TLS templates, named keepalive profiles).

`service serial device <ttySxxx>` replaces today's `serial device <…>`
**and** subsumes today's `service console-server device <…>` — they
become the same tree, with `ssh-direct` simply being one of the
transport subtrees described below. (Migration script rewrites
`service console-server device X ssh …` into
`service serial device X ssh-direct …`.)

### `service serial device <ttySxxx>`

Hardware leaves are flat on `device` (matching console-server). The
selected transport is a *subtree*, not a leaf, and only one such
subtree may be present (enforced in `verify()`).

```
service serial device <ttySxxx | usbxbxpx>
  │
  ├── disable                                  # valueless
  ├── description <text>
  ├── alias <name>                             # human-friendly handle (from console-server)
  │
  │   # ── Physical layer (flat on device, console-server-style) ─
  ├── speed <300-1843200>                      # default: 9600
  ├── data-bits <5|6|7|8>                      # default: 8
  ├── stop-bits <1|2>                          # default: 1
  ├── parity <none|odd|even|mark|space>        # default: none
  ├── flow-control <none|soft|hard|both>       # default: none
  ├── electrical <rs232|rs422|rs485f|rs485h>   # default: rs232
  │       (renamed from `hardware interface` —
  │        the word "interface" was overloaded)
  ├── line-termination                         # valueless (rs422/rs485 only)
  ├── echo-suppression                         # valueless (rs485 half only)
  ├── monitor-dsr                              # valueless
  ├── monitor-dcd                              # valueless
  ├── flow-in                                  # valueless
  ├── flow-out                                 # valueless
  ├── rts-toggle                               # raise RTS during character transmit
  │     ├── initial-delay <0-1000>             # ms; default: 0
  │     └── final-delay <0-1000>               # ms; default: 0
  │
  │   # ── Frame assembly ────────────────────────────────────
  ├── packet-forwarding
  │     ├── preset <minimize-latency|optimize-throughput|prevent-fragmentation>
  │     │       # mutually exclusive with the raw knobs below
  │     ├── delay-between-messages <0-65535>   # ms; default: 250
  │     ├── forwarding-rule <strip-trigger|trigger|trigger+1|trigger+2>
  │     │                                      # default: trigger
  │     ├── start-of-frame <hex>[..<hex>]      # 1 or 2 bytes
  │     ├── end-of-frame   <hex>[..<hex>]
  │     ├── end-trigger    <hex>[..<hex>]
  │     ├── start-frame-transmit               # valueless
  │     ├── packet-size <0-1024>               # bytes
  │     ├── idle-timer <0-65535>               # ms
  │     └── force-transmit-timer <0-65535>     # ms
  │
  │   # ── Transport — pick exactly one of the following ─────
  │   #    verify(): error if more than one is configured.
  │   #    Presence-of-subtree is what enables the transport;
  │   #    there is no separate selector leaf.
  │
  ├── trueport-server
  │     ├── signal-active                      # valueless
  │     ├── remote
  │     │     ├── primary
  │     │     │     ├── address <ipv4|ipv6|fqdn>
  │     │     │     └── port <1-65535>
  │     │     └── backup <name>                # tag node — replaces multihost-list 1-50
  │     │           ├── address <ipv4|ipv6|fqdn>
  │     │           ├── port <1-65535>
  │     │           └── mode <failover|all-hosts>   # default: failover
  │     └── trueport-lite                      # valueless — enables lite mode (was implicit)
  │
  ├── trueport-client
  │     ├── signal-active                      # valueless
  │     ├── allow-multiple-connection          # valueless (trueport-lite only)
  │     └── listen-port <1-65535>
  │
  ├── modbus-master
  │     ├── protocol <rtu|ascii>               # default: rtu
  │     ├── ascii-crlf                         # valueless
  │     └── slave <name>                       # tag node — replaces numeric 1-16
  │           ├── transport <tcp|udp>          # default: tcp
  │           ├── range-mode <host|gateway>    # default: host
  │           ├── address <ipv4|ipv6>
  │           ├── port <1-65535>
  │           └── uid <1-247|start-end>
  │
  ├── modbus-slave
  │     ├── protocol <rtu|ascii>               # default: rtu
  │     ├── ascii-crlf                         # valueless
  │     ├── uid <1-247|start-end>
  │     └── listen-port <1-65535>
  │
  ├── vmodem
  │     ├── mode <auto|manual>                 # default: auto
  │     ├── echo                               # valueless
  │     ├── failure-string <text, max 30>
  │     ├── success-string <text, max 40>
  │     ├── modem-init-string <text, max 254>
  │     ├── response-delay <0-999>             # s; default: 0
  │     ├── send-connect-status <numeric|verbose|disable>   # default: numeric
  │     ├── auto-connect
  │     │     ├── address <ipv4|ipv6|fqdn>
  │     │     └── port <1-65535>
  │     └── hardware-signals
  │           ├── dtr <always-on|acts-as-dcd|acts-as-ri>    # default: always-on
  │           ├── rts <always-on|acts-as-dcd|acts-as-ri>    # default: always-on
  │           └── dcd <always-on|on-when-host-connect>      # default: always-on
  │
  ├── udp
  │     ├── multicast-interface <ifname>
  │     └── rule <1-4>                         # numeric — order is meaningful
  │           ├── disable                      # valueless
  │           ├── direction <both|lan-serial|serial-lan>
  │           ├── udp-port <auto-learn|any|1-65535>
  │           └── address-range
  │                 ├── start <ipv4|ipv6>
  │                 └── end   <ipv4|ipv6>
  │
  ├── tcp-reverse
  │     ├── auth-user                          # valueless
  │     ├── ip-aliasing                        # valueless
  │     ├── allow-multiple-connection          # valueless
  │     └── listen-port <1-65535>
  │
  ├── tcp-direct
  │     ├── remote
  │     │     ├── primary
  │     │     │     ├── address <ipv4|ipv6|fqdn>
  │     │     │     └── port <1-65535>
  │     │     └── backup <name>                # tag node — replaces tcp.multihost
  │     │           ├── address <ipv4|ipv6|fqdn>
  │     │           ├── port <1-65535>
  │     │           └── mode <failover|all-hosts>   # default: failover
  │     └── initiate                           # exactly one of:
  │           ├── any-char                     # valueless
  │           └── specific-char <hex>
  │
  ├── ssh-reverse
  │     ├── ip-aliasing                        # valueless
  │     ├── multisession-limit <0-16>
  │     └── listen-port <1-65535>
  │
  ├── ssh-direct
  │     ├── remote
  │     │     ├── address <ipv4|ipv6|fqdn>
  │     │     └── port <1-65535>
  │     ├── terminal-type <text, max 17>
  │     ├── login-name <text, max 21>
  │     └── initiate                           # exactly one of:
  │           ├── any-char                     # valueless
  │           └── specific-char <hex>
  │
  ├── telnet-reverse
  │     ├── auth-user                          # valueless
  │     ├── ip-aliasing                        # valueless
  │     ├── multisession-limit <0-16>
  │     └── listen-port <1-65535>
  │
  ├── telnet-direct
  │     ├── remote
  │     │     ├── address <ipv4|ipv6|fqdn>
  │     │     └── port <1-65535>
  │     ├── terminal-type <text, max 17>
  │     ├── map-cr-to-crlf                     # valueless
  │     └── initiate                           # exactly one of:
  │           ├── any-char                     # valueless
  │           └── specific-char <hex>
  │
  ├── serial-tunnel
  │     ├── mode <client|server>               # default: server
  │     ├── break-length <0-65535>             # ms; default: 1000
  │     ├── delay-after-break <0-65535>        # ms; default: 0
  │     ├── listen-port <1-65535>              # server-mode
  │     └── remote                             # client-mode
  │           ├── address <ipv4|ipv6|fqdn>
  │           └── port <1-65535>
  │
  ├── login
  │     │   # presence enables interactive login on this TTY
  │     │   # (no additional leaves — uses banners/timeouts/init/term below)
  │     └── (no children)
  │
  ├── nine-bits
  │     ├── start-trigger-hex-string <2hex>    # 4-digit hex; default: 0000
  │     ├── stop-trigger-hex-string  <2hex>    # 4-digit hex; default: 0000
  │     ├── trigger                            # valueless
  │     ├── delay <0-65535>                    # ms; default: 0
  │     └── remote
  │           ├── address <ipv4|ipv6|fqdn>
  │           └── port <1-65535>
  │
  │   # NOTE: ppp and slip are NOT transports here — they are their
  │   # own interface types (`interfaces ppp <pppN>`, `interfaces slip
  │   # <slN>`) that *attach* to a serial device. See below.
  │
  │   # ── Common cross-cutting options ─────────────────────
  ├── address <ipv4|ipv6>                      # was `inet` — IP alias for the port
  │
  ├── tls
  │     ├── template <name>                    # reference into service.serial.global.tls-template <name>
  │     │       # mutually exclusive with the rest of `tls`
  │     ├── disable                            # valueless
  │     ├── certificate <pki-cert-name>
  │     ├── passphrase <text, max 16>
  │     ├── version <any|tlsv1.2|tlsv1.2b|tlsv1.3>     # default: any
  │     ├── role <client|server>               # default: client
  │     ├── peer-verification
  │     │     ├── disable                      # valueless
  │     │     ├── country <text>
  │     │     ├── state <text>
  │     │     ├── locality <text>
  │     │     ├── organization <text>
  │     │     ├── organization-unit <text>
  │     │     ├── common-name <text>
  │     │     └── email <text>
  │     └── cipher-options <1-5>               # tag node, up to 5 cipher rows
  │           ├── encryption <any|aes|aes-gcm>                                          # default: any
  │           ├── min-key-size <40|56|64|128|168|256>                                   # default: 40
  │           ├── max-key-size <40|56|64|128|168|256>                                   # default: 256
  │           ├── key-exchange <any|rsa|edh-rsa|edh-dss|adh|ecdh-ecdsa>                 # default: any
  │           └── hmac <any|sha1|md5|sha256|sha384>                                     # default: any
  │
  ├── keepalive
  │     ├── template <name>                    # reference into service.serial.global.keepalive-template <name>
  │     │       # mutually exclusive with the leaves below
  │     ├── interval <1-32767>                 # s; default: 180
  │     ├── retries <1-32767>                  # default: 5
  │     └── retry-timeout <1-32767>            # s; default: 5
  │
  ├── data-logging                             # valueless — enable per-port data logging
  ├── init-string <text, max 127>
  ├── terminate-string <text, max 127>
  ├── session-string-delay <0-65535>           # ms; default: 0
  ├── pre-login-banner                         # valueless
  ├── post-login-banner                        # valueless
  ├── send-description-on-connect              # valueless
  ├── idle-timeout <0-4294967>                 # s; default: 0
  └── session-timeout <0-4294967>              # s; default: 0
```

### `service serial global` — system-wide

```
service serial global
  ├── process-break                            # valueless — process Break Signals
  ├── flush-on-close                           # valueless
  │
  ├── modbus-gateway                           # Modbus-TCP-to-serial gateway
  │     ├── port <1-65535>                     # default: 502
  │     ├── address-mode <embedded|remapped>   # default: embedded
  │     ├── remapped-uid <1-247>               # default: 1
  │     ├── ip-aliasing                        # valueless
  │     ├── broadcast                          # valueless
  │     ├── disable-exceptions                 # valueless
  │     ├── disable-request-queuing            # valueless
  │     ├── char-timeout <10-10000>            # ms; default: 30
  │     ├── mess-timeout <10-10000>            # ms; default: 1000
  │     ├── idle-timer <0-300>                 # s;  default: 10
  │     ├── next-request-delay <0-1000>        # ms; default: 50
  │     └── tls-template <name>                # reference, not a flag
  │
  ├── vmodem
  │     └── phone-number <text>                # tag node, keyed by phone number
  │           ├── address <ipv4|ipv6|fqdn>
  │           └── port <1-65535>
  │
  ├── keepalive-template <name>                # tag node
  │     ├── interval <1-32767>                 # s; default: 180
  │     ├── retries <1-32767>                  # default: 5
  │     └── retry-timeout <1-32767>            # s; default: 5
  │
  ├── tls-template <name>                      # tag node
  │     ├── disable                            # valueless
  │     ├── certificate <pki-cert-name>
  │     ├── passphrase <text, max 16>
  │     ├── version <any|tlsv1.2|tlsv1.2b|tlsv1.3>     # default: any
  │     ├── role <client|server>               # default: client
  │     ├── peer-verification
  │     │     ├── disable                      # valueless
  │     │     ├── country <text>
  │     │     ├── state <text>
  │     │     ├── locality <text>
  │     │     ├── organization <text>
  │     │     ├── organization-unit <text>
  │     │     ├── common-name <text>
  │     │     └── email <text>
  │     └── cipher-options <1-5>               # tag node, up to 5 cipher rows
  │           ├── encryption <any|aes|aes-gcm>                                          # default: any
  │           ├── min-key-size <40|56|64|128|168|256>                                   # default: 40
  │           ├── max-key-size <40|56|64|128|168|256>                                   # default: 256
  │           ├── key-exchange <any|rsa|edh-rsa|edh-dss|adh|ecdh-ecdsa>                 # default: any
  │           └── hmac <any|sha1|md5|sha256|sha384>                                     # default: any
  │
  ├── trueport-remap                           # Baud-rate remap table for Trueport
  │     └── speed                              # one sub-node per source baud rate
  │           ├── 50    remap <300-1843200>    # default: 57600
  │           ├── 75    remap <300-1843200>    # default: 300
  │           ├── 110   remap <300-1843200>    # default: 115200
  │           ├── 134   remap <300-1843200>    # default: 230400
  │           ├── 150   remap <300-1843200>    # default: 300
  │           ├── 200   remap <300-1843200>    # default: 300
  │           ├── 300   remap <300-1843200>    # default: 300
  │           ├── 600   remap <300-1843200>    # default: 600
  │           ├── 1200  remap <300-1843200>    # default: 1200
  │           ├── 1800  remap <300-1843200>    # default: 1800
  │           ├── 2400  remap <300-1843200>    # default: 2400
  │           ├── 4800  remap <300-1843200>    # default: 4800
  │           ├── 9600  remap <300-1843200>    # default: 9600
  │           ├── 19200 remap <300-1843200>    # default: 19200
  │           └── 38400 remap <300-1843200>    # default: 38400
  │
  └── port-buffering                           # Global port-buffer logging defaults
        ├── local
        │     └── view-string <text, max 8>    # default: "~show"
        ├── nfs
        │     ├── address <ipv4|ipv6|fqdn>     # was hostname
        │     └── directory <text, max 40>     # default: "/device_server/portlogs"
        ├── syslog
        │     └── level <emergency|alert|critical|error|warning|notice|info|debug>   # default: info
        ├── add-timestamp                      # valueless
        └── keystroke-buffering                # valueless
```

Per-port references look like:

```
set service serial device ttyS0 tls template corp-tls
set service serial device ttyS0 keepalive template default-keep
set service serial global modbus-gateway tls-template corp-tls
```

This matches the VyOS pattern for PKI, NAT translation groups,
firewall groups, IPsec profiles, etc.

### `port-profile <name>` — reusable full-port templates

Customers configuring fleets of identical-purpose ports (RS485
modbus probes, console-server logins, TCP-direct gateways to a peer
class, …) should not have to retype every leaf on every device.
Add a `port-profile <name>` tag node under `service serial global`
and a `profile <name>` reference on each device.

**A profile is a full port definition minus the per-device unique
bits.** Structurally it is identical to the `service serial device
<…>` subtree (same leaves, same validators, same defaults), so
operators learn one schema and the conf-mode merge is trivial.

Two leaves are **not** profilable — they are always per-device:

- `description` — free-form per-device text.
- `alias` — human-friendly name for *this* TTY.

Everything else (line settings, packet-forwarding, tls, keepalive,
banners, timeouts, *and* the selected transport with all its
leaves) is allowed in a profile.

```
service serial global
  …
  └── port-profile <name>                    # tag node
        │
        │   # ── Physical layer (same as device) ─────────────
        ├── speed <300-1843200>
        ├── data-bits <5|6|7|8>
        ├── stop-bits <1|2>
        ├── parity <none|odd|even|mark|space>
        ├── flow-control <none|soft|hard|both>
        ├── electrical <rs232|rs422|rs485f|rs485h>
        ├── line-termination                 # valueless
        ├── echo-suppression                 # valueless
        ├── monitor-dsr                      # valueless
        ├── monitor-dcd                      # valueless
        ├── flow-in                          # valueless
        ├── flow-out                         # valueless
        ├── rts-toggle                       # same shape as device.rts-toggle
        │     ├── initial-delay <0-1000>
        │     └── final-delay   <0-1000>
        │
        │   # ── Frame assembly (same as device) ─────────────
        ├── packet-forwarding { … same shape as device.packet-forwarding … }
        │
        │   # ── Transport — exactly one, same shape as on device ─
        │   #    (verify(): no more than one transport subtree)
        ├── trueport-server   { … }
        ├── trueport-client   { … }
        ├── modbus-master     { … }
        ├── modbus-slave      { … }
        ├── vmodem            { … }
        ├── udp               { … }
        ├── tcp-reverse       { … }
        ├── tcp-direct        { … }
        ├── ssh-reverse       { … }
        ├── ssh-direct        { … }
        ├── telnet-reverse    { … }
        ├── telnet-direct     { … }
        ├── serial-tunnel     { … }
        ├── login             { … }
        ├── nine-bits         { … }
        │
        │   # ── Common cross-cutting options (same as device) ─
        ├── tls               { … same as device.tls … }
        ├── keepalive         { … same as device.keepalive … }
        ├── data-logging                     # valueless
        ├── init-string <text>
        ├── terminate-string <text>
        ├── session-string-delay <0-65535>
        ├── pre-login-banner                 # valueless
        ├── post-login-banner                # valueless
        ├── send-description-on-connect      # valueless
        ├── idle-timeout <0-4294967>
        └── session-timeout <0-4294967>
```

And on the device:

```
service serial device <ttySxxx>
  ├── profile <name>                         # reference into global.port-profile <name>
  ├── description <text>                     # ALWAYS per-device (not profilable)
  ├── alias <name>                           # ALWAYS per-device (not profilable)
  │
  │   # Any other leaf below is OPTIONAL and OVERRIDES the profile.
  │   # The schema is the full device tree from earlier in this doc;
  │   # nothing is required when `profile` is set.
  └── …
```

#### Merge / override semantics

Codified in `verify()` / `get_config()`, not in XML:

| Node kind                                                    | Merge rule                                                                                                          |
|---|---|
| Plain leaves                                                 | Device value wins; else profile value; else XML default.                                                            |
| Sub-blocks of leaves (`tls`, `keepalive`, `rts-toggle`, `packet-forwarding`) | Deep-merge leaf-by-leaf; device wins per leaf. Device can override `tls.certificate` without losing `tls.cipher-options` from the profile. |
| Tag nodes (`backup <name>`, `slave <name>`, `rule <1-4>`, `cipher-options <1-5>`) | **Union by tag value.** If the same tag exists on both sides, deep-merge with device-wins. "Profile gives 3 backup hosts; device adds a 4th." |
| Transport choice (`trueport-server` vs `tcp-direct` vs …)    | **Replace, do not merge.** If the device defines any transport subtree, it replaces the profile's transport entirely. Half-modbus-half-tcp is never a valid state. |
| `verify()` on the device                                     | `profile <name>` must reference an existing `port-profile <name>`.                                                  |
| `verify()` on the profile                                    | At most one transport subtree (same rule as on a device).                                                           |
| Effective config visible to `generate()`                     | Fully merged dict — generator never sees the layering.                                                              |

#### Example: a fleet of modbus probes

Define the profile once:

```
set service serial global port-profile rs485-modbus-probe speed 19200
set service serial global port-profile rs485-modbus-probe parity even
set service serial global port-profile rs485-modbus-probe electrical rs485h
set service serial global port-profile rs485-modbus-probe echo-suppression
set service serial global port-profile rs485-modbus-probe keepalive interval 60
set service serial global port-profile rs485-modbus-probe modbus-slave protocol rtu
set service serial global port-profile rs485-modbus-probe modbus-slave listen-port 5020
```

Per-device config is then a one- or two-liner — only the **unique
bits** appear on the device:

```
set service serial device ttyS1 profile rs485-modbus-probe
set service serial device ttyS1 description "Tank-1 level sensor"
set service serial device ttyS1 alias tank-1
set service serial device ttyS1 modbus-slave uid 17

set service serial device ttyS2 profile rs485-modbus-probe
set service serial device ttyS2 description "Tank-2 level sensor"
set service serial device ttyS2 alias tank-2
set service serial device ttyS2 modbus-slave uid 18
```

ttyS4 wants the same profile but a higher baud — just override
the one leaf:

```
set service serial device ttyS4 profile rs485-modbus-probe
set service serial device ttyS4 alias tank-4
set service serial device ttyS4 speed 38400
set service serial device ttyS4 modbus-slave uid 19
```

In practice the per-device "unique bits" reduce to a very short
list across all transports:

| Transport        | Per-device leaves you'll typically override                       |
|---|---|
| `modbus-slave`   | `uid`                                                             |
| `modbus-master`  | nothing on the master itself; `slave <name>` entries are usually per-device |
| `tcp-direct`     | `remote primary { address port }`                                 |
| `ssh-direct`     | `remote { address port }`, possibly `login-name`                  |
| `trueport-server`| `remote primary { address port }`, `backup <name>` entries        |
| `udp`            | `rule <1-4>` address ranges                                       |
| `vmodem`         | `auto-connect { address port }`                                   |

Everything else (line settings, framing, TLS, keepalive, banners,
timeouts) lives in the profile and is shared.

#### JSON import / export — profiles as a wire format

Customers want to ship a profile to a fleet of routers, often as a
JSON document. Do this **without** introducing a parallel
on-disk store: the profile lives in the config tree (so it gets
rollback, `commit-confirm`, config-sync, backup/restore, op-mode
visibility for free), and JSON is just a transport format used by
op-mode commands.

```
generate serial port-profile from-json file <path>
  → emits the equivalent `set service serial global port-profile …`
    command stream (to stdout, or staged via cli-shell-api)

show serial port-profile <name> json
  → prints the named profile as JSON in the same schema
```

The JSON schema is the XML schema — generated mechanically from
[interface-definitions/include/serial](../interface-definitions/include/serial)
so customers can validate offline.

Example JSON for the modbus-probe profile above:

```json
{
  "port-profile": {
    "rs485-modbus-probe": {
      "speed": "19200",
      "parity": "even",
      "electrical": "rs485h",
      "echo-suppression": {},
      "keepalive": { "interval": "60" },
      "modbus-slave": {
        "protocol": "rtu",
        "listen-port": "5020"
      }
    }
  }
}
```

#### Why not store profiles in a separate JSON file on disk?

It looks tempting (`/config/serial-profiles/*.json` read at commit)
but it breaks every VyOS guarantee:

| Concern                          | Config-tree profile | JSON-file profile |
|---|---|---|
| `show configuration commands`    | Visible             | Invisible         |
| `commit-confirm` / `rollback`    | Rolled back         | Not rolled back   |
| `service config-sync` to HA peer | Replicated          | Not replicated    |
| Backup / restore                 | One file (config.boot) | Two stores      |
| XML validation / completion      | Enforced            | Bypassed          |
| Per-leaf audit trail             | Available           | Lost              |

Use JSON as the **interchange** format (import/export op-mode
commands) and the **config tree** as the source of truth. Best of
both worlds, no rollback foot-guns.

#### Op-mode quality-of-life

Two new op-mode commands make profiles usable in anger:

```
show serial device <tty>
  → prints the RESOLVED config (profile + per-device overrides
    merged), with each leaf annotated as
    [profile:<name>] | [device] | [default].

show serial port-profile <name> referenced-by
  → lists every device that references this profile.
    Critical before editing a profile that touches 50 ports.
```

---

### `interfaces ppp <pppN>` and `interfaces slip <slN>` — promoted out

PPP and SLIP are **not** TTY transports. They are layer-2/3 interfaces
that happen to ride on a serial port. They get their own interface
type, mirroring how `interfaces pppoe pppoe0` works today.

**Where are the port settings (speed, parity, data-bits, …)?** They
stay on the referenced TTY device, under `service serial device <tty>`.
There is exactly one place in the tree that owns physical-layer
settings for a given kernel TTY, and that is `service serial device
<tty>`. PPP/SLIP just *reference* that device.

So a complete PPP-over-serial config looks like:

```
# 1. Declare the physical port (port hardware settings only — no transport)
set service serial device ttyS1 speed 115200
set service serial device ttyS1 data-bits 8
set service serial device ttyS1 stop-bits 1
set service serial device ttyS1 parity none
set service serial device ttyS1 flow-control hard
set service serial device ttyS1 electrical rs232
# (no trueport-*/modbus-*/tcp-*/ssh-*/login/etc. subtree here —
#  the TTY is "raw" and owned by PPP)

# 2. Declare the PPP interface that rides on it
set interfaces ppp ppp0 device ttyS1
set interfaces ppp ppp0 address 10.0.0.1/30
set interfaces ppp ppp0 remote-address 10.0.0.2/30
set interfaces ppp ppp0 authentication protocol chap
set interfaces ppp ppp0 authentication username vyos
set interfaces ppp ppp0 authentication password s3cret
```

`verify()` rules:

- `interfaces ppp <p> device <tty>` requires
  `service serial device <tty>` to exist.
- The referenced TTY must **not** have any transport subtree
  (`trueport-*`, `modbus-*`, `tcp-*`, `ssh-*`, `telnet-*`,
  `serial-tunnel`, `vmodem`, `udp`, `login`, `nine-bits`). It is
  owned by the PPP/SLIP stack.
- A given TTY can be referenced by at most one `interfaces ppp` or
  `interfaces slip` node.

```
interfaces ppp <pppN>                          # tag node, e.g. ppp0
  ├── disable                                  # valueless
  ├── description <text>
  ├── device <ttySxxx | usbxbxpx>              # the TTY that carries the link
  │       # references service.serial.device.<name>; that device
  │       # provides speed/parity/data-bits/stop-bits/flow-control/
  │       # electrical/etc. PPP does NOT redefine them here.
  ├── address <ipv4/prefix>                    # local address (was ppp.local-address)
  ├── remote-address <ipv4/prefix>
  ├── mtu <64-1500>                            # bytes; default: 1500
  │       # NOTE: PPP traditionally exposes this as MRU; we align with
  │       # the rest of VyOS which uses `mtu` on every interface.
  ├── authentication
  │     ├── protocol <chap|pap|none>           # default: chap
  │     ├── chap-challenge-interval <0-255>
  │     ├── username <text>
  │     ├── password <text>
  │     ├── remote-user <text>
  │     ├── remote-password <text>
  │     └── timeout <0-255>
  ├── ipv6
  │     ├── address
  │     │     ├── global-prefix <ipv6>         # was ipv6-global-network-prefix
  │     │     ├── local-identifier <::h:h:h:h>
  │     │     └── remote-identifier <::h:h:h:h>
  │     └── …                                  # other standard `interfaces … ipv6 …` knobs
  ├── ip-address-negotiation                   # valueless
  ├── magic-negotiation                        # valueless
  ├── accm <hex, 8 digits>                     # default: 00000000
  ├── disable-ac-comp                          # valueless
  ├── disable-protocol-comp                    # valueless
  ├── disable-vj-comp                          # valueless
  ├── configure-request
  │     ├── retry <0-255>                      # default: 10
  │     └── timeout <1-255>                    # default: 3
  ├── terminate-request
  │     ├── retry <0-255>                      # default: 2
  │     └── timeout <1-255>                    # default: 3
  ├── echo
  │     ├── retry <0-255>                      # default: 3
  │     └── timeout <0-255>                    # default: 30
  └── nak-retry <0-255>                        # default: 10
```

```
interfaces slip <slN>                          # tag node, e.g. sl0
  ├── disable                                  # valueless
  ├── description <text>
  ├── device <ttySxxx | usbxbxpx>              # references service.serial.device.<name>
  │                                            # (port hardware lives there)
  ├── address <ipv4/prefix>
  ├── remote-address <ipv4/prefix>
  ├── mtu <256-1006>                           # default: 256
  └── disable-vj-comp                          # valueless
```

Why this is correct:

- A PPP/SLIP interface participates in routing, firewall, NAT, QoS,
  and ICMP redirect policy exactly like any other L3 interface. As
  a TTY transport it cannot — there would be no `pppN` name to
  reference from `firewall`, `static route`, `bgp neighbor`, etc.
- The TTY remains a pure raw-bytes transport. Its only obligation
  is "raw bytes in, raw bytes out at the configured line settings"
  — which is exactly what `service serial device <tty>` provides.
- Single source of truth for line settings: speed/parity/data-bits
  live exactly once, on the TTY device, regardless of whether it
  carries PPP, SLIP, ssh-direct, modbus, or anything else.
- `verify()` rule: if a TTY is referenced by `interfaces ppp …
  device` or `interfaces slip … device`, the TTY must **not** have
  any transport subtree configured (it is owned by the PPP/SLIP
  stack).
- Op-mode `show interfaces ppp ppp0` works for free.

---

## Summary of changes vs. today

| Today                                                | Proposed                                          | Why                                          |
|---|---|---|
| `serial device <tty>`                                | `service serial device <tty>`                     | Match existing `service console-server device <tty>` |
| `serial global`                                      | `service serial global`                           | Keep all serial under one `service serial` root |
| `service console-server device <tty>`                | `service serial device <tty> ssh-direct { … }`    | Merge — console-server is just one transport  |
| `serial device <tty> hardware speed 9600`            | `service serial device <tty> speed 9600`          | Flatten — matches console-server today         |
| `service <profile>` (leaf) + `service-setting { … }` | profile sub-tree directly on the interface        | Removes silent-ignore footgun                |
| `hardware interface <rs232\|…>`                       | `electrical <rs232\|…>`                            | Word "interface" was overloaded              |
| `tls use-global` (per port)                          | `tls template <name>` (reference)                 | Named templates are the VyOS pattern         |
| `keepalive` (valueless on port + global params)      | per-port `keepalive { … }` *or* `template <name>` | Same as TLS — no hidden indirection          |
| `inet <addr>`                                        | `address <addr>`                                  | Naming consistency with the rest of VyOS     |
| `multihost-list host <1-50>`                         | `backup <name>` tag node                          | Name-tagged, not numeric                     |
| `vmodem-phone-list entry <1-8>`                      | `phone-number <text>` tag node                    | Keyed by the real natural key                |
| `slave-mapping-list <1-16>`                          | `slave <name>` tag node                           | Name-tagged                                  |
| `packet-forwarding mode custom`                      | `packet-forwarding preset <…>` (optional)         | Preset OR raw knobs, never both              |
| `start-of-frame-value1` / `…-value2`                 | `start-of-frame <hex>[..<hex>]`                   | One leaf instead of two                      |
| `service-setting ppp { … }` (TTY profile)            | `interfaces ppp <pppN> device <tty>`              | PPP is a real L3 interface — must be routable/firewallable |
| `service-setting slip { … }` (TTY profile)           | `interfaces slip <slN> device <tty>`              | Same — SLIP is an L3 interface              |
| every port retyped in full                           | `service serial global port-profile <name>` + `device <tty> profile <name>` | Fleet-friendly; only per-device unique bits on each device |
| (no shared schema across sites)                      | `generate serial port-profile from-json file <path>` / `show … json` | JSON is the wire format; config tree stays the source of truth |

---

## Migration notes

- `verify()` in [src/conf_mode/serial.py](../src/conf_mode/serial.py)
  becomes the single point of enforcement for "exactly one service
  subtree per port". This is a cleaner contract than today's "the
  `service` leaf decides what to read".
- A migration script under
  [src/migration-scripts](../src/migration-scripts) can mechanically
  rewrite existing configs: hoist `hardware.*` and
  `service-setting.<picked>.*` to the device, drop the unused
  `service-setting` siblings, fold `service console-server device X`
  into `service serial device X ssh-direct …`, rename `inet` →
  `address`, etc.
- Existing op-mode commands that walk
  `serial device <…>` continue to work (path is unchanged in shape —
  only the parent `serial` becomes `service serial`).
- Per-user ACLs (`system login user <name> serial …`) are unchanged.

---

## Open questions

1. **Should `service serial` instead be `system serial`?**
   The system-wide block isn't really a network service — it's more
   like `system console` or `system option`. Either fits; `service`
   matches modbus-gateway being a real listening daemon.

2. **Keep `packet-forwarding` as a sub-container or flatten its
   leaves too?** Arguably it deserves its own block because it has
   ~10 related knobs.

3. **TLS / keepalive templates — required, or optional sugar?**
   The minimum-viable redesign can keep TLS fully inline on each
   port and only introduce templates if there is a real reuse case.
