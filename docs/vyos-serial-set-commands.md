# VyOS Serial — `set` Command Reference

This document defines the VyOS CLI `set` commands as currently implemented by
`interface-definitions/serial.xml.in` (driven by
`src/conf_mode/serial.py`).  It is the source-of-truth structural reference
for code that emits or consumes `set serial …` commands.

Top-level tree lives under:
```
set serial ...
set system login user <name> serial ...   # per-user serial access (separate subtree)
```

User-facing serial access ACLs (`access`, `timeout`) are attached to the
system-login user node, not to the serial node — see
[interface-definitions/system_login.xml.in](../interface-definitions/system_login.xml.in)
which includes
[include/serial/user/serial-access.xml.i](../interface-definitions/include/serial/user/serial-access.xml.i)
and
[include/serial/user/serial-timeout.xml.i](../interface-definitions/include/serial/user/serial-timeout.xml.i).

---

## Configuration Tree

```
serial
  │
  ├── global                                              # System-wide serial settings
  │     │
  │     ├── process-break                                 # valueless — process Break Signals
  │     ├── flush-on-close                                # valueless — flush on close
  │     │
  │     ├── keepalive                                     # Global TCP keepalive (also used by service-level keepalive)
  │     │     ├── interval <1-32767>                      # default: 180 (s)
  │     │     ├── retries <1-32767>                       # default: 5
  │     │     └── retry-timeout <1-32767>                 # default: 5 (s)
  │     │
  │     ├── modbus-gateway                                # Modbus-TCP-to-serial gateway
  │     │     ├── ip-aliasing                             # valueless
  │     │     ├── addr-mode <embedded|re-mapped>          # default: embedded
  │     │     ├── broadcast                               # valueless — enable serial Modbus broadcasts
  │     │     ├── char-timeout <10-10000>                 # ms; default: 30
  │     │     ├── disable-exceptions                      # valueless
  │     │     ├── idle-timer <0-300>                      # s; default: 10
  │     │     ├── mess-timeout <10-10000>                 # ms; default: 1000
  │     │     ├── next-request-delay <0-1000>             # ms; default: 50
  │     │     ├── port <1-65535>                          # default: 502
  │     │     ├── remapped-uid <1-247>                    # default: 1
  │     │     ├── disable-request-queuing                 # valueless
  │     │     └── tls                                     # valueless — enable TLS
  │     │
  │     ├── vmodem-phone-list                             # Phone-number → host map (vmodem profile)
  │     │     └── entry <1-8>                             # tag node
  │     │           ├── hostname <ipv4|ipv6|fqdn>
  │     │           ├── port <1-65535>
  │     │           └── phone-number <text, max 31>
  │     │
  │     ├── tls                                           # Global TLS profile (template for ports using use-global)
  │     │     ├── disable                                 # valueless
  │     │     ├── certificate <pki-cert-name>
  │     │     ├── passphrase <text, max 16>
  │     │     ├── version <any|tlsv1.2|tlsv1.2b|tlsv1.3>  # default: any
  │     │     ├── role <client|server>                    # default: client
  │     │     ├── peer-verification
  │     │     │     ├── disable                           # valueless
  │     │     │     ├── country <text>
  │     │     │     ├── state <text>
  │     │     │     ├── locality <text>
  │     │     │     ├── organization <text>
  │     │     │     ├── organization-unit <text>
  │     │     │     ├── common-name <text>
  │     │     │     └── email <text>
  │     │     └── cipher-options <1-5>                    # tag node, up to 5 cipher rows
  │     │           ├── encryption <any|aes|aes-gcm>      # default: any
  │     │           ├── min-key-size <40|56|64|128|168|256>   # default: 40
  │     │           ├── max-key-size <40|56|64|128|168|256>   # default: 256
  │     │           ├── key-exchange <any|rsa|edh-rsa|edh-dss|adh|ecdh-ecdsa>  # default: any
  │     │           └── hmac <any|sha1|md5|sha256|sha384>     # default: any
  │     │
  │     ├── trueport-remap                                # Baud-rate remap table for Trueport
  │     │     └── speed                                   # one sub-node per source baud rate
  │     │           ├── 50  remap <300-1843200>           # default: 57600
  │     │           ├── 75  remap <300-1843200>           # default: 300
  │     │           ├── 110 remap <300-1843200>           # default: 115200
  │     │           ├── 134 remap <300-1843200>           # default: 230400
  │     │           ├── 150 remap <300-1843200>           # default: 300
  │     │           ├── 200 remap <300-1843200>           # default: 300
  │     │           ├── 300 remap <300-1843200>           # default: 300
  │     │           ├── 600 remap <300-1843200>           # default: 600
  │     │           ├── 1200 remap <300-1843200>          # default: 1200
  │     │           ├── 1800 remap <300-1843200>          # default: 1800
  │     │           ├── 2400 remap <300-1843200>          # default: 2400
  │     │           ├── 4800 remap <300-1843200>          # default: 4800
  │     │           ├── 9600 remap <300-1843200>          # default: 9600
  │     │           ├── 19200 remap <300-1843200>         # default: 19200
  │     │           └── 38400 remap <300-1843200>         # default: 38400
  │     │
  │     └── port-buffering                                # Global port-buffer logging defaults
  │           ├── local
  │           │     └── view-string <text, max 8>         # default: "~show"
  │           ├── nfs
  │           │     ├── hostname <ipv4|ipv6|fqdn>
  │           │     └── directory <text, max 40>          # default: "/device_server/portlogs"
  │           ├── syslog
  │           │     └── level <emergency|alert|critical|error|warning|notice|info|debug>   # default: info
  │           ├── add-timestamp                           # valueless
  │           └── keystroke-buffering                     # valueless
  │
  └── device <ttySxxx>                                    # tag node — per physical TTY port
        ├── disable                                       # valueless
        ├── description <text>                            # generic description
        │
        ├── hardware                                      # Physical-layer (UART) settings
        │     ├── speed <300-1843200>                     # default: 9600
        │     ├── flow-control <none|soft|hard|both>      # default: none
        │     ├── data-bits <5|6|7|8>                     # default: 8
        │     ├── parity <none|odd|even|mark|space>       # default: none
        │     ├── stop-bits <1|2>                         # default: 1
        │     ├── interface <rs232|rs422|rs485f|rs485h>   # default: rs232
        │     ├── line-termination                        # valueless (rs422/rs485 only)
        │     ├── echo-suppression                        # valueless (rs485 half only)
        │     ├── monitor-dsr                             # valueless
        │     ├── monitor-dcd                             # valueless
        │     ├── flow-in                                 # valueless
        │     ├── flow-out                                # valueless
        │     └── rts-toggle                              # raise RTS during character transmit
        │           ├── final-delay <0-1000>              # ms; default: 0
        │           └── initial-delay <0-1000>            # ms; default: 0
        │
        ├── packet-forwarding                             # Frame assembly & forwarding
        │     ├── mode <minimize-latency|optimize-network-throughput|prevent-message-fragmentation|custom>
        │     │                                           # default: minimize-latency
        │     ├── delay-between-messages <0-65535>        # ms; default: 250
        │     ├── forwarding-rule <strip-trigger|trigger|trigger+1|trigger+2>
        │     │                                           # default: trigger
        │     ├── start-of-frame-value1 <hex>
        │     ├── start-of-frame-value2 <hex>
        │     ├── end-of-frame-value1 <hex>
        │     ├── end-of-frame-value2 <hex>
        │     ├── start-frame-transmit                    # valueless
        │     ├── packet-size <0-1024>                    # bytes
        │     ├── idle-timer <0-65535>                    # ms
        │     ├── force-transmit-timer <0-65535>          # ms
        │     ├── end-trigger-value1 <hex>
        │     └── end-trigger-value2 <hex>
        │
        ├── service <profile>                             # Active service on this port
        │   #  one of:
        │   #    trueport-server | trueport-client
        │   #    modbus-master | modbus-slave
        │   #    vmodem
        │   #    udp
        │   #    tcp-reverse | tcp-direct
        │   #    serial-tunnel
        │   #    ppp | slip
        │   #    ssh-reverse | telnet-reverse
        │   #    ssh-direct | telnet-direct
        │   #    login
        │   #    nine-bits
        │
        ├── service-setting                               # Profile-specific configuration
        │     │
        │     ├── trueport                                # used by trueport-server / trueport-client
        │     │     ├── signal-active                     # valueless
        │     │     ├── allow-multiple-connection         # valueless (client init, trueport-lite only)
        │     │     ├── main-hostport <1-65535>           # server-init only
        │     │     ├── main-hostname <ipv4|ipv6|fqdn>    # server-init only
        │     │     └── multihost                         # server-init only, trueport-lite only
        │     │           ├── mode <backup-failover|all-hosts|disable>   # default: disable
        │     │           ├── backup-hostname <ipv4|ipv6|fqdn>
        │     │           └── backup-hostport <1-65535>
        │     │
        │     ├── reverse                                 # used by tcp-reverse / ssh-reverse / telnet-reverse
        │     │     ├── auth-user                         # valueless (tcp/telnet only)
        │     │     ├── ip-aliasing                       # valueless
        │     │     ├── multisession-limit <0-16>         # ssh/telnet only
        │     │     └── allow-multiple-connection         # valueless (tcp only)
        │     │
        │     ├── direct                                  # used by tcp-direct / ssh-direct / telnet-direct
        │     │     ├── main-hostport <1-65535>
        │     │     ├── main-hostname <ipv4|ipv6|fqdn>
        │     │     ├── tcp
        │     │     │     └── multihost                   # tcp only
        │     │     │           ├── mode <backup-failover|all-hosts|disable>   # default: disable
        │     │     │           ├── backup-hostname <ipv4|ipv6|fqdn>
        │     │     │           └── backup-hostport <1-65535>
        │     │     ├── telnet
        │     │     │     ├── terminal-type <text, max 17>
        │     │     │     └── map-cr-to-crlf              # valueless
        │     │     ├── ssh
        │     │     │     ├── terminal-type <text, max 17>
        │     │     │     └── login-name <text, max 21>
        │     │     ├── initiate-any-char                 # valueless (main only)
        │     │     └── initiate-specific-char <hex>      # main only
        │     │
        │     ├── modbus                                  # used by modbus-master / modbus-slave
        │     │     ├── ascii-crlf                        # valueless
        │     │     ├── protocol <rtu|ascii>              # default: rtu
        │     │     ├── uid <1-247|start-end>             # slave only
        │     │     └── slave-mapping-list <1-16>         # tag node, master only
        │     │           ├── protocol <tcp|udp>          # default: tcp
        │     │           ├── range-mode <host|gateway>   # default: host
        │     │           ├── port <1-65535>
        │     │           ├── slave-ip <ipv4|ipv6>
        │     │           └── uid <1-247|start-end>
        │     │
        │     ├── vmodem                                  # used by vmodem
        │     │     ├── echo                              # valueless
        │     │     ├── failure-string <text, max 30>
        │     │     ├── success-string <text, max 40>
        │     │     ├── modem-init-string <text, max 254>
        │     │     ├── auto-connect-hostport <1-65535>
        │     │     ├── auto-connect-hostname <ipv4|ipv6|fqdn>
        │     │     ├── mode <auto|manual>                # default: auto
        │     │     ├── response-delay <0-999>            # s; default: 0
        │     │     ├── send-connect-status <numeric|verbose|disable>  # default: numeric
        │     │     └── hardware-signals
        │     │           ├── dtr <always-on|acts-as-dcd|acts-as-ri>   # default: always-on
        │     │           ├── rts <always-on|acts-as-dcd|acts-as-ri>   # default: always-on
        │     │           └── dcd <always-on|on-when-host-connect>     # default: always-on
        │     │
        │     ├── udp                                     # used by udp
        │     │     ├── multicast-interface <ethN>
        │     │     └── entry <1-4>                       # tag node — up to 4 UDP rules
        │     │           ├── disable                     # valueless
        │     │           ├── direction <both|lan-serial|serial-lan>
        │     │           ├── udp-port <auto-learn|any|1-65535>
        │     │           ├── start-address <ipv4|ipv6>
        │     │           └── end-address <ipv4|ipv6>
        │     │
        │     ├── serial-tunnel                           # used by serial-tunnel
        │     │     ├── break-length <0-65535>            # ms; default: 1000
        │     │     ├── mode <client|server>              # default: server
        │     │     ├── delay-after-break <0-65535>       # ms; default: 0
        │     │     └── client                            # client-mode endpoint
        │     │           ├── connect-hostport <1-65535>
        │     │           └── connect-hostname <ipv4|ipv6|fqdn>
        │     │
        │     ├── ppp                                     # used by ppp
        │     │     ├── authentication
        │     │     │     ├── protocol <chap|pap|none>            # default: chap
        │     │     │     ├── chap-challenge-interval <0-255>     # min; default: 0
        │     │     │     ├── username <text, max 255>
        │     │     │     ├── password <text, max 17>
        │     │     │     ├── remote-user <text, max 255>
        │     │     │     ├── remote-password <text, max 17>
        │     │     │     └── timeout <0-255>                     # min; default: 1
        │     │     ├── local-address <ipv4/prefix>
        │     │     ├── remote-address <ipv4/prefix>
        │     │     ├── accm <hex, 8 digits>                      # default: 00000000
        │     │     ├── disable-ac-comp                           # valueless
        │     │     ├── configure-request-retry <0-255>           # default: 10
        │     │     ├── configure-request-timeout <1-255>         # s; default: 3
        │     │     ├── echo-retry <0-255>                        # default: 3
        │     │     ├── echo-timeout <0-255>                      # s; default: 30
        │     │     ├── ip-address-negotiation                    # valueless
        │     │     ├── ipv6-global-network-prefix <ipv6>
        │     │     ├── ipv6-local-interface-identifier <::h:h:h:h>
        │     │     ├── ipv6-remote-interface-identifier <::h:h:h:h>
        │     │     ├── magic-negotiation                         # valueless
        │     │     ├── mru <64-1500>                             # bytes; default: 1500
        │     │     ├── nak-retry <0-255>                         # default: 10
        │     │     ├── disable-protocol-comp                     # valueless
        │     │     ├── terminate-request-retry <0-255>           # default: 2
        │     │     ├── terminate-request-timeout <1-255>         # s; default: 3
        │     │     └── disable-vj-comp                           # valueless
        │     │
        │     ├── slip                                   # used by slip
        │     │     ├── local-address <ipv4/prefix>
        │     │     ├── remote-address <ipv4/prefix>
        │     │     ├── mtu <256-1006>                            # bytes; default: 256
        │     │     └── disable-vj-comp                           # valueless
        │     │
        │     └── nine-bits                               # used by nine-bits
        │           ├── start-trigger-hex-string <2hex>           # 4-digit hex; default: 0000
        │           ├── stop-trigger-hex-string <2hex>            # 4-digit hex; default: 0000
        │           ├── trigger                                   # valueless
        │           ├── delay <0-65535>                           # ms; default: 0
        │           ├── hostport <1-65535>
        │           └── hostname <ipv4|ipv6|fqdn>
        │
        ├── tls                                           # Per-port TLS (overrides global unless use-global)
        │     ├── use-global                              # valueless — use serial.global.tls instead
        │     ├── disable                                 # valueless
        │     ├── certificate <pki-cert-name>
        │     ├── passphrase <text, max 16>
        │     ├── version <any|tlsv1.2|tlsv1.2b|tlsv1.3>  # default: any
        │     ├── role <client|server>                    # default: client
        │     ├── peer-verification
        │     │     ├── disable                           # valueless
        │     │     ├── country <text>
        │     │     ├── state <text>
        │     │     ├── locality <text>
        │     │     ├── organization <text>
        │     │     ├── organization-unit <text>
        │     │     ├── common-name <text>
        │     │     └── email <text>
        │     └── cipher-options <1-5>                    # tag node
        │           ├── encryption <any|aes|aes-gcm>      # default: any
        │           ├── min-key-size <40|56|64|128|168|256>   # default: 40
        │           ├── max-key-size <40|56|64|128|168|256>   # default: 256
        │           ├── key-exchange <any|rsa|edh-rsa|edh-dss|adh|ecdh-ecdsa>  # default: any
        │           └── hmac <any|sha1|md5|sha256|sha384>     # default: any
        │
        ├── keepalive                                     # valueless — enable TCP keepalive (uses global keepalive params)
        ├── data-logging                                  # valueless — enable per-port data logging
        ├── init-string <text, max 127>                   # session init string
        ├── terminate-string <text, max 127>              # session termination string
        ├── session-string-delay <0-65535>                # ms; default: 0
        ├── listen-port <1-65535>                         # listen port for inbound profiles
        ├── send-description-on-connect                   # valueless
        ├── multihost-list                                # used by multihost / trueport server-init
        │     └── host <1-50>                             # tag node, up to 50 hosts
        │           ├── name <ipv4|ipv6|fqdn>
        │           └── port <1-65535>
        ├── inet <ipv4|ipv6>                              # IP alias for the port (aliasing-address)
        ├── pre-login-banner                              # valueless
        ├── post-login-banner                             # valueless
        ├── idle-timeout <0-4294967>                      # s; default: 0
        └── session-timeout <0-4294967>                   # s; default: 0


# ----- Separate subtree: per-user serial access ACL/timeout ----------------

set system login user <name> serial
  ├── access <start-end | ttySxxx>                        # tag node — TTY range/name to which mode applies
  │     └── mode <read-in|read-out|read-write|disable>    # multi-valued; default: "read-in read-write read-out"
  └── timeout
        ├── session <0-4294967>                           # s; default: 0
        └── idle    <0-4294967>                           # s; default: 0
```

---

## Notes on Structure

1. **`service` vs `service-setting`** — `service` is a single-valued leaf selecting *which* profile is active; `service-setting` is a parent containing **all** profile-specific config sub-trees. Only the sub-tree matching the selected `service` is consumed by `conf_mode/serial.py`; other sub-trees are ignored but allowed in the config.

2. **TLS resolution** — when a port's `tls use-global` is set, the port's other `tls.*` nodes are ignored and `serial global tls …` is used instead. Otherwise the per-port `tls` block applies.

3. **Keepalive** — per-port `device <ttySxxx> keepalive` is a valueless enable flag; the actual interval/retries/retry-timeout values live in `serial global keepalive`.

4. **Port range** — `device` is a tag node validated by the `tty-port` validator; `system login user <name> access` is validated by `tty-port-range` (allows ranges like `ttyS0-ttyS3`).

5. **Hex value format** — `start-of-frame-valueN`, `end-of-frame-valueN`, `end-trigger-valueN`, `initiate-specific-char` take a single ASCII hex byte (validator `hex`); `nine-bits start/stop-trigger-hex-string` takes two hex bytes encoded as a 4-digit string (validator `2hex`).

6. **PPP/SLIP IPv6** — only `ppp` supports IPv6 directly (`ipv6-global-network-prefix`, `ipv6-local-interface-identifier`, `ipv6-remote-interface-identifier`); `slip` is IPv4-only.

7. **Modbus** — `modbus uid` applies to slave mode only; `modbus slave-mapping-list` applies to master mode only.

8. **Multihost** — used by both `trueport multihost` (server-init, trueport-lite) and `direct tcp multihost` (tcp-direct only).

9. **No defaults at parent nodes** — every `<defaultValue>` is at the leaf. Optional parent nodes (e.g. `rts-toggle`, `peer-verification`) do not auto-materialize their children unless the user touches at least one leaf below them.

---

## Source-of-Truth Files

| File | Role |
|---|---|
| [interface-definitions/serial.xml.in](../interface-definitions/serial.xml.in) | Root of the `serial` CLI tree (global + device tag node) |
| [interface-definitions/include/serial/general/*.xml.i](../interface-definitions/include/serial/general/) | Global subtrees (hardware, keepalive, modbus-gateway, packet-forwarding, port-buffering, tls-global, trueport-remap, vmodem-phonebook) |
| [interface-definitions/include/serial/service/*.xml.i](../interface-definitions/include/serial/service/) | Service-profile subtrees (direct, modbus, nine-bits, ppp, reverse, serial-tunnel, slip, trueport, udp, vmodem) |
| [interface-definitions/include/serial/service/utils/*.xml.i](../interface-definitions/include/serial/service/utils/) | Shared leaf/sub-tree fragments (tls-common, multihost, host-info, keepalive flag, banners, timeouts, etc.) |
| [interface-definitions/include/serial/user/*.xml.i](../interface-definitions/include/serial/user/) | `system login user … serial` ACL/timeout fragments |
| [interface-definitions/system_login.xml.in](../interface-definitions/system_login.xml.in) | Mount-point of the per-user serial access fragments |
| [src/conf_mode/serial.py](../src/conf_mode/serial.py) | Conf-mode handler that consumes the resulting config tree |
