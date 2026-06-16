---
myst:
  html_meta:
    description: |
      IS-IS is a link-state interior gateway protocol that uses Dijkstra's
      Shortest Path First algorithm to build a network topology database
      and compute the shortest path to each destination.
    keywords: isis, link-state, igp, dijkstra, spf, lfa, ti-lfa, srv6
---

(isis)=

# IS-IS

Intermediate System-to-Intermediate System (IS-IS) is a link-state
{abbr}`IGP (Interior Gateway Protocol)` described in ISO/IEC 10589,
[RFC 1195](https://datatracker.ietf.org/doc/html/rfc1195), and
[RFC 5308](https://datatracker.ietf.org/doc/html/rfc5308). It uses
Dijkstra's {abbr}`SPF (Shortest Path First)` algorithm to build a network
topology database ({abbr}`LSDB (Link State Database)`) and compute the
shortest path to each destination.

In an IS-IS network, routers are called Intermediate Systems (ISs). They
exchange topology information with directly connected neighbors via the
IS-IS protocol, whose PDUs are carried directly in Layer 2 frames rather
than over IP. IS-IS routers are identified by a
{abbr}`NET (Network Entity Title)`, which ranges from 8 to 20 bytes
(typically 10 bytes).

## IS-IS vs OSPF

IS-IS builds an LSDB from link-state information flooded by other routers
and computes routing paths using Dijkstra's algorithm, just like OSPF.
Because both protocols share the same link-state architecture, they make
nearly identical path-selection decisions. Given the similarities between
IS-IS and OSPF, comparing their routing behaviors is an effective way to
understand how a network will respond with either IGP.

## Configuration

### Mandatory settings

Each IS-IS router must be configured with a unique NET, the
{abbr}`CLNS (Connectionless Network Service)` equivalent of a Router ID.
The 6-byte system identifier portion of the NET must be unique across the
IS-IS routing domain.

```{cfgcmd} set protocols isis net \<network-entity-title\>

**Configure the Network Entity Title (NET) for the router.**

A typical NET looks like `49.0001.1921.6800.1002.00`.

The NET consists of the following parts:

- {abbr}`AFI (Authority and Format Identifier)` (`49`): IS-IS
  conventionally uses AFI value 49 for private addressing.
- Area identifier (`0001`): The area number within the IS-IS routing
  domain (in this example, Area 1).
- System identifier (`1921.6800.1002`): Uniquely identifies the router
  within the IS-IS routing domain. We recommend deriving this value from
  the router IP address or MAC address. To construct the system identifier
  from an IPv4 address (for example, `192.168.1.2`):

  - Pad each octet with leading zeros: `192.168.1.2` → `192.168.001.002`.
  - Regroup the digits into three 4-digit blocks: `192.168.001.002` →
    `1921.6800.1002`.

- NET selector (`00`): Must always be `00` to indicate the local system.
```

Example:

```none
set protocols isis net 49.0001.1921.6800.1002.00
```

```{cfgcmd} set protocols isis interface \<interface\>

**Enable IS-IS on the specified interface.**

This enables the router to form adjacencies with directly connected peers.
```

Example:

```none
set protocols isis interface eth0
```

### IS-IS global configuration

```{cfgcmd} set protocols isis dynamic-hostname

**Enable Dynamic Hostname {abbr}`TLV (Type-Length-Value)` support on the
router ([RFC 5301](https://datatracker.ietf.org/doc/html/rfc5301)).**

This enables the router to include its human-readable system name
alongside its System ID in IS-IS advertisements for easier peer
identification.
```

Example:

```none
set protocols isis dynamic-hostname
```

```{cfgcmd} set protocols isis level \<level-1 | level-1-2 | level-2\>

**Configure the IS-IS level at which the router operates:**

- `level-1`: Participates exclusively in Level-1 (intra-area) routing.
- `level-1-2`: Participates in both Level-1 (intra-area) and Level-2
  (inter-area) routing.
- `level-2`: Participates exclusively in Level-2 (inter-area) routing.
```

Example:

```none
set protocols isis level level-1
```

```{cfgcmd} set protocols isis lsp-mtu \<128-4352\>

**Configure the {abbr}`MTU (Maximum Transmission Unit)` size, in bytes,
for originating or receiving IS-IS {abbr}`LSPs (Link State PDUs)`.**
```

Example:

```none
set protocols isis lsp-mtu 1400
```

```{cfgcmd} set protocols isis metric-style \<narrow | transition | wide\>

**Configure the TLV format (metric style) the router uses when originating
or processing IS-IS LSPs:**

- `narrow`: Originates and processes only the original ISO/IEC 10589 TLVs.
- `transition`: Originates and processes both narrow and wide TLV formats.
- `wide`: Originates and processes only extended TLVs.
```

Example:

```none
set protocols isis metric-style wide
```

```{cfgcmd} set protocols isis purge-originator

**Enable {abbr}`POI (Purge Originator Identification)`
([RFC 6232](https://datatracker.ietf.org/doc/html/rfc6232)) for IS-IS
purges triggered by the router.**

When enabled, the router includes the POI TLV with its System ID in each
purge it triggers. This identifies which
{abbr}`IS (Intermediate System)` triggered the purge.
```

Example:

```none
set protocols isis purge-originator
```

```{cfgcmd} set protocols isis set-attached-bit

**Configure the L1/L2 IS-IS router to set the ATT (Attached) bit in the
Level-1 LSPs it originates
([RFC 3787](https://datatracker.ietf.org/doc/html/rfc3787)).**

This signals to pure Level-1 routers that this L1/L2 router has Level-2
reachability.
```

Example:

```none
set protocols isis set-attached-bit
```

```{cfgcmd} set protocols isis set-overload-bit

**Configure the router to set the OL (LSP Database Overload) bit in LSPs
it originates ([RFC 3787](https://datatracker.ietf.org/doc/html/rfc3787)).**

When configured, other IS-IS routers stop sending transit traffic through
this router but can still reach its directly connected networks.
```

Example:

```none
set protocols isis set-overload-bit
```

```{cfgcmd} set protocols isis advertise-high-metrics

**Configure the router to advertise a high metric value on all of its IS-IS
interfaces, regardless of the metric configured on each interface.**

The advertised value depends on the metric style: 63 for `narrow`, 16777215
for `wide`, and 62 for `transition`.
```

Example:

```none
set protocols isis advertise-high-metrics
```

```{cfgcmd} set protocols isis advertise-passive-only

**Configure the router to advertise in its LSPs only the IP prefixes of
passive interfaces.**

Prefixes of non-passive interfaces are not advertised, but those interfaces
are still used to form adjacencies and participate in SPF.
```

Example:

```none
set protocols isis advertise-passive-only
```

```{cfgcmd} set protocols isis log-adjacency-changes

**Configure the router to log IS-IS adjacency state changes to syslog.**
```

Example:

```none
set protocols isis log-adjacency-changes
```

```{cfgcmd} set protocols isis topology \<ipv4-multicast | ipv4-mgmt | ipv6-unicast | ipv6-multicast | ipv6-mgmt | ipv6-dstsrc\>

**Enable an additional IS-IS Multi-Topology for the router:**

- `ipv4-multicast`: IPv4 multicast topology (MT 3).
- `ipv4-mgmt`: IPv4 management topology (MT 1).
- `ipv6-unicast`: IPv6 unicast topology (MT 2).
- `ipv6-multicast`: IPv6 multicast topology (MT 4).
- `ipv6-mgmt`: IPv6 management topology (MT 5).
- `ipv6-dstsrc`: IPv6 destination/source routing topology.

The default IPv4-unicast topology (MT 0) is always present and does not
need to be explicitly configured.
```

Example:

```none
set protocols isis topology ipv6-unicast
```

#### Authentication

IS-IS supports two protocol-wide passwords: 

- **area-password**: applied to Level-1 LSPs/SNPs (within the area).
- **domain-password**: applied to Level-2 LSPs/SNPs (across the Level-2
  backbone).

These are distinct from the per-interface `password` command (see
[Interface configuration](#interface-configuration)). That command
authenticates only the Hello (IIH) PDUs exchanged with the neighbor on the
interface where it is configured.

```{cfgcmd} set protocols isis area-password plaintext-password \<text\>

**Configure a plaintext password used to authenticate Level-1 LSPs and
SNPs originated and received by this router.**

All Level-1 routers in the area must be configured with the same
password.
```

Example:

```none
set protocols isis area-password plaintext-password mysharedsecret
```

```{cfgcmd} set protocols isis area-password md5 \<text\>

**Configure an HMAC-MD5 key used to authenticate Level-1 LSPs and SNPs
originated and received by this router.**

All Level-1 routers in the area must be configured with the same key.
```

```{note}
For each of `area-password` and `domain-password`, configure either
`plaintext-password` or `md5`, but not both.
```

Example:

```none
set protocols isis area-password md5 mysharedsecret
```

```{cfgcmd} set protocols isis domain-password plaintext-password \<text\>

**Configure a plaintext password used to authenticate Level-2 LSPs and
SNPs originated and received by this router.**

All Level-2 routers in the routing domain must be configured with the
same password.
```

Example:

```none
set protocols isis domain-password plaintext-password mysharedsecret
```

```{cfgcmd} set protocols isis domain-password md5 \<text\>

**Configure an HMAC-MD5 key used to authenticate Level-2 LSPs and SNPs
originated and received by this router.**

All Level-2 routers in the routing domain must be configured with the
same key.
```

Example:

```none
set protocols isis domain-password md5 mysharedsecret
```

#### Default route advertisement

##### Level-1 IPv4

```{cfgcmd} set protocols isis default-information originate ipv4 level-1

**Configure the router to originate the IPv4 default route (`0.0.0.0/0`)
and advertise it in locally generated LSPs throughout the Level-1 area.**
```

```{note}
This command requires the router's IS-IS level to be set to `level-1` or
`level-1-2`.
```

Example:

```none
set protocols isis default-information originate ipv4 level-1
```

```{cfgcmd} set protocols isis default-information originate ipv4 level-1 always

**Configure the router to unconditionally originate the IPv4 default route
and advertise it throughout the Level-1 area, even if the router lacks a
default route in its {abbr}`RIB (Routing Information Base)`.**
```

```{note}
This command requires the router's IS-IS level to be set to `level-1` or
`level-1-2`.
```

Example:

```none
set protocols isis default-information originate ipv4 level-1 always
```

```{cfgcmd} set protocols isis default-information originate ipv4 level-1 metric \<0-16777215\>

**Configure the IS-IS metric for the IPv4 default route advertised at
Level 1.**
```

```{note}
This command requires the router's IS-IS level to be set to `level-1` or
`level-1-2`.
```

Example:

```none
set protocols isis default-information originate ipv4 level-1 metric 100
```

```{cfgcmd} set protocols isis default-information originate ipv4 level-1 route-map \<name\>

**Apply a route-map to the IPv4 default route advertised at Level 1.**

The route-map can permit or deny the advertisement and, if permitted,
modify the route's metric.
```

```{note}
This command requires the router's IS-IS level to be set to `level-1` or
`level-1-2`.
```

Example:

```none
set protocols isis default-information originate ipv4 level-1 route-map ISIS-DEFAULT
```

##### Level-1 IPv6

```{cfgcmd} set protocols isis default-information originate ipv6 level-1

**Configure the router to originate the IPv6 default route (`::/0`) and
advertise it in locally generated LSPs throughout the Level-1 area.**
```

```{note}
This command requires the router's IS-IS level to be set to `level-1` or
`level-1-2`.
```

Example:

```none
set protocols isis default-information originate ipv6 level-1
```

```{cfgcmd} set protocols isis default-information originate ipv6 level-1 always

**Configure the router to unconditionally originate the IPv6 default route
and advertise it throughout the Level-1 area, even if the router lacks a
default route in its RIB.**
```

```{note}
This command requires the router's IS-IS level to be set to `level-1` or
`level-1-2`.
```

Example:

```none
set protocols isis default-information originate ipv6 level-1 always
```

```{cfgcmd} set protocols isis default-information originate ipv6 level-1 metric \<0-16777215\>

**Configure the IS-IS metric for the IPv6 default route advertised at
Level 1.**
```

```{note}
This command requires the router's IS-IS level to be set to `level-1` or
`level-1-2`.
```

Example:

```none
set protocols isis default-information originate ipv6 level-1 metric 100
```

```{cfgcmd} set protocols isis default-information originate ipv6 level-1 route-map \<name\>

**Apply a route-map to the IPv6 default route advertised at Level 1.**

The route-map can permit or deny the advertisement and, if permitted,
modify the route's metric.
```

```{note}
This command requires the router's IS-IS level to be set to `level-1` or
`level-1-2`.
```

Example:

```none
set protocols isis default-information originate ipv6 level-1 route-map ISIS-DEFAULT
```

##### Level-2 IPv4

```{cfgcmd} set protocols isis default-information originate ipv4 level-2

**Configure the router to originate the IPv4 default route (`0.0.0.0/0`)
and advertise it in locally generated LSPs throughout the Level-2
backbone.**
```

```{note}
This command requires the router's IS-IS level to be set to `level-2` or
`level-1-2`.
```

Example:

```none
set protocols isis default-information originate ipv4 level-2
```

```{cfgcmd} set protocols isis default-information originate ipv4 level-2 always

**Configure the router to unconditionally originate the IPv4 default route
and advertise it throughout the Level-2 backbone, even if the router lacks
a default route in its RIB.**
```

```{note}
This command requires the router's IS-IS level to be set to `level-2` or
`level-1-2`.
```

Example:

```none
set protocols isis default-information originate ipv4 level-2 always
```

```{cfgcmd} set protocols isis default-information originate ipv4 level-2 metric \<0-16777215\>

**Configure the IS-IS metric for the IPv4 default route advertised into
the Level-2 backbone.**
```

```{note}
This command requires the router's IS-IS level to be set to `level-2` or
`level-1-2`.
```

Example:

```none
set protocols isis default-information originate ipv4 level-2 metric 100
```

```{cfgcmd} set protocols isis default-information originate ipv4 level-2 route-map \<name\>

**Apply a route-map to the IPv4 default route advertised into the Level-2
backbone.**

The route-map can permit or deny the advertisement and, if permitted,
modify the route's metric.
```

```{note}
This command requires the router's IS-IS level to be set to `level-2` or
`level-1-2`.
```

Example:

```none
set protocols isis default-information originate ipv4 level-2 route-map ISIS-DEFAULT
```

##### Level-2 IPv6

```{cfgcmd} set protocols isis default-information originate ipv6 level-2

**Configure the router to originate the IPv6 default route (`::/0`) and
advertise it in locally generated LSPs throughout the Level-2 backbone.**
```

```{note}
This command requires the router's IS-IS level to be set to `level-2` or
`level-1-2`.
```

Example:

```none
set protocols isis default-information originate ipv6 level-2
```

```{cfgcmd} set protocols isis default-information originate ipv6 level-2 always

**Configure the router to unconditionally originate the IPv6 default route
and advertise it throughout the Level-2 backbone, even if the router lacks
a default route in its RIB.**
```

```{note}
This command requires the router's IS-IS level to be set to `level-2` or
`level-1-2`.
```

Example:

```none
set protocols isis default-information originate ipv6 level-2 always
```

```{cfgcmd} set protocols isis default-information originate ipv6 level-2 metric \<0-16777215\>

**Configure the IS-IS metric for the IPv6 default route advertised into
the Level-2 backbone.**
```

```{note}
This command requires the router's IS-IS level to be set to `level-2` or
`level-1-2`.
```

Example:

```none
set protocols isis default-information originate ipv6 level-2 metric 100
```

```{cfgcmd} set protocols isis default-information originate ipv6 level-2 route-map \<name\>

**Apply a route-map to the IPv6 default route advertised into the Level-2
backbone.**

The route-map can permit or deny the advertisement and, if permitted,
modify the route's metric.
```

```{note}
This command requires the router's IS-IS level to be set to `level-2` or
`level-1-2`.
```

Example:

```none
set protocols isis default-information originate ipv6 level-2 route-map ISIS-DEFAULT
```

#### LDP synchronization

```{cfgcmd} set protocols isis ldp-sync

**Enable LDP IGP synchronization
([RFC 5443](https://datatracker.ietf.org/doc/html/rfc5443)) for the IS-IS
routing process.**

When enabled, all operational IS-IS interfaces automatically participate
in synchronization, except for loopback interfaces.
```

```{note}
LDP must be configured and functional on the router for synchronization
to operate.
```

Example:

```none
set protocols isis ldp-sync
```

```{cfgcmd} set protocols isis ldp-sync holddown \<0-10000\>

**Configure the time, in seconds, that IS-IS keeps any of its interfaces
at max-metric while waiting for LDP-IGP synchronization to complete.**

When this time expires on an interface, IS-IS restores the configured
interface metric even if LDP-IGP synchronization has not completed.

The default value is 0, which causes IS-IS to wait indefinitely.
```

Example:

```none
set protocols isis ldp-sync holddown 60
```

### Interface configuration

```{cfgcmd} set protocols isis interface \<interface\> circuit-type \<level-1 | level-1-2 | level-2-only\>

**Configure the IS-IS level at which the router can form adjacencies on
the specified interface:**

- `level-1`: Permits only Level-1 (intra-area) adjacencies.
- `level-2-only`: Permits only Level-2 (inter-area) adjacencies.
- `level-1-2`: Permits both Level-1 (intra-area) and Level-2 (inter-area)
  adjacencies.
```

```{note}
The selected level must be supported by the router's IS-IS process.
```

Example:

```none
set protocols isis interface eth0 circuit-type level-1
```

```{cfgcmd} set protocols isis interface \<interface\> hello-interval \<1-600\>

**Configure the interval, in seconds, between successive IS-IS Hello PDUs
(IIH) sent on the specified interface.**
```

Example:

```none
set protocols isis interface eth1 hello-interval 5
```

```{cfgcmd} set protocols isis interface \<interface\> hello-multiplier \<2-100\>

**Configure the multiplier applied to the Hello interval to derive the
Holding Time advertised in IS-IS Hello PDUs (IIH) sent on the specified
interface.**

The receiving neighbor uses the advertised Holding Time as its adjacency
timeout. If no IIH arrives within that period, the adjacency is declared
down.
```

Example:

```none
set protocols isis interface eth1 hello-multiplier 5
```

```{cfgcmd} set protocols isis interface \<interface\> hello-padding

**Enable padding of IS-IS Hello PDUs (IIH) sent on the specified interface
to that interface's full MTU
([RFC 3719](https://datatracker.ietf.org/doc/html/rfc3719)).**

This ensures that neighbors with asymmetric MTUs cannot establish an
adjacency. Without padding, asymmetric MTUs bypass detection during
adjacency setup.
```

Example:

```none
set protocols isis interface eth0 hello-padding
```

```{cfgcmd} set protocols isis interface \<interface\> metric \<0-16777215\>

**Configure the IS-IS metric (cost) advertised for the specified
interface.**

The SPF algorithm uses this value to calculate the optimal routing path
to destinations.

The valid range depends on the configured metric style: `narrow` limits
the metric to 0-63, while `wide` extends it to 0-16777215.

The default value is 10.
```

Example:

```none
set protocols isis interface eth1 metric 100
```

```{cfgcmd} set protocols isis interface \<interface\> network point-to-point

**Configure the IS-IS network type for the specified interface as
point-to-point.**

The default network type is broadcast.
```

```{note}
The neighboring interface must be configured with the same network type;
otherwise, the adjacency does not form.
```

Example:

```none
set protocols isis interface eth1 network point-to-point
```

```{cfgcmd} set protocols isis interface \<interface\> passive

**Enable passive mode for the specified interface.**

On a passive interface, the router neither sends nor processes IS-IS Hello
PDUs (IIH), so no adjacency forms. The interface's IP prefix is still
advertised in this router's LSP.
```

Example:

```none
set protocols isis interface lo passive
```

```{cfgcmd} set protocols isis interface \<interface\> password plaintext-password \<text\>

**Configure the plaintext authentication password for the specified
interface.**

This password is included in IS-IS Hello (IIH) PDUs sent on the interface
and validated on IIH PDUs received from neighbors.

A mismatch prevents adjacency formation and tears down an established
adjacency.
```

Example:

```none
set protocols isis interface eth1 password plaintext-password mysharedsecret
```

```{cfgcmd} set protocols isis interface \<interface\> password md5 \<text\>

**Configure the MD5 authentication key for the specified interface.**

This key is used to generate a cryptographic hash that is included in
IS-IS Hello (IIH) PDUs sent on the interface and validated in IIH PDUs
received from neighbors.

A mismatch prevents adjacency formation and tears down an established
adjacency.
```

Example:

```none
set protocols isis interface eth1 password md5 mysharedsecret
```

```{cfgcmd} set protocols isis interface \<interface\> priority \<0-127\>

**Configure the IS-IS {abbr}`DIS (Designated Intermediate System)`
election priority for the specified interface.**

The priority is used in DIS election on the broadcast (LAN) segment. The
router whose interface advertises the highest priority wins.

The default priority is 64.
```

```{note}
The configured value applies only to broadcast interfaces and has no
effect on point-to-point interfaces.
```

Example:

```none
set protocols isis interface eth1 priority 100
```

```{cfgcmd} set protocols isis interface \<interface\> psnp-interval \<0-127\>

**Configure the interval, in seconds, between successive IS-IS
{abbr}`PSNP (Partial Sequence Number PDU)` transmissions on the
specified interface.**
```

Example:

```none
set protocols isis interface eth1 psnp-interval 2
```

```{cfgcmd} set protocols isis interface \<interface\> no-three-way-handshake

**Disable the Three-Way Handshake for Point-to-Point (P2P) adjacencies
([RFC 5303](https://datatracker.ietf.org/doc/html/rfc5303)).**

The three-way handshake is enabled by default.
```

```{note}
This command applies only to point-to-point interfaces and has no effect
on broadcast interfaces.
```

Example:

```none
set protocols isis interface eth1 no-three-way-handshake
```

```{cfgcmd} set protocols isis interface \<interface\> ldp-sync disable

**Disable LDP-IGP synchronization on the specified IS-IS interface.**

With LDP-IGP synchronization enabled, IS-IS advertises a maximum metric
on the interface while LDP is not yet synchronized on it.

Disabling it on this interface causes IS-IS to advertise the configured
metric regardless of LDP synchronization state.
```

```{note}
This command applies only if LDP-IGP synchronization is enabled for the
IS-IS routing process.
```

Example:

```none
set protocols isis interface eth1 ldp-sync disable
```

```{cfgcmd} set protocols isis interface \<interface\> ldp-sync holddown \<0-10000\>

**Configure the time, in seconds, that IS-IS keeps the specified interface
at max-metric while waiting for LDP-IGP synchronization to complete.**

When this time expires, IS-IS restores the configured interface metric
even if LDP-IGP synchronization has not completed.

The default value is 0, which causes IS-IS to wait indefinitely.
```

```{note}
This setting overrides the LDP-IGP synchronization hold-down time
configured for the IS-IS routing process.
```

Example:

```none
set protocols isis interface eth1 ldp-sync holddown 60
```

```{cfgcmd} set protocols isis interface \<interface\> bfd profile \<profile-name\>

**Attach a BFD profile to the IS-IS adjacency on the specified
interface.**

When configured, IS-IS uses the BFD session described by the named
profile to detect adjacency failure. If BFD reports the session down,
the IS-IS adjacency is torn down immediately rather than waiting for
the Hello holding time to expire.

The profile itself is configured under
`set protocols bfd profile <profile-name>`.
```

Example:

```none
set protocols isis interface eth1 bfd profile ISIS-FAST
```

#### Level-1 fast-reroute

```{cfgcmd} set protocols isis interface \<interface\> fast-reroute lfa level-1 enable

**Enable Level-1 {abbr}`LFA (Loop-Free Alternate)` computation on the
specified interface.**

When enabled, IS-IS precomputes a backup next-hop for each Level-1
destination reached through this interface. If the primary next-hop
fails, the router uses the precomputed backup instead.
```

Example:

```none
set protocols isis interface eth1 fast-reroute lfa level-1 enable
```

```{cfgcmd} set protocols isis interface \<interface-1\> fast-reroute lfa level-1 exclude interface \<interface-2\>

**Exclude an interface from being selected as a Level-1 LFA backup
next-hop on the specified interface.**

In the command syntax, `<interface-1>` identifies the protected interface,
and `<interface-2>` identifies the interface that must not be used as an
LFA backup next-hop.
```

Example:

```none
set protocols isis interface eth1 fast-reroute lfa level-1 exclude interface eth2
```

```{cfgcmd} set protocols isis interface \<interface\> fast-reroute remote-lfa level-1 tunnel mpls-ldp

**Enable Level-1 remote LFA computation using MPLS-LDP tunnels on the
specified interface.**

Remote LFA provides backup paths when local LFA cannot find a loop-free
alternate neighbor.

If the primary next-hop fails, the router sends traffic into an MPLS-LDP
tunnel to a precomputed remote LFA node. From there, normal IS-IS
forwarding delivers it to the destination.
```

```{note}
Remote LFA requires the corresponding local LFA to be configured on this
interface.
```

```{note}
Remote LFA requires all potential remote LFA endpoints in the IS-IS
routing instance to accept targeted LDP Hello messages.
```

Example:

```none
set protocols isis interface eth1 fast-reroute remote-lfa level-1 tunnel mpls-ldp
```

```{cfgcmd} set protocols isis interface \<interface\> fast-reroute remote-lfa level-1 maximum-metric \<1-16777215\>

**Configure the maximum metric for Level-1 remote LFA node selection on
the specified interface.**

Remote LFA nodes with a metric exceeding this value are excluded from
selection.
```

```{note}
The maximum metric applies only when the corresponding remote LFA is
enabled on this interface.
```

Example:

```none
set protocols isis interface eth1 fast-reroute remote-lfa level-1 maximum-metric 100
```

```{cfgcmd} set protocols isis interface \<interface\> fast-reroute ti-lfa level-1

**Enable Level-1 {abbr}`TI-LFA (Topology Independent Loop-Free Alternate)`
computation on the specified interface.**

By default, TI-LFA operates in link protection mode, computing backup
paths that protect against the failure of this interface's link.
```

```{note}
LFA and TI-LFA cannot be configured at the same level on the same
interface.
```

Example:

```none
set protocols isis interface eth1 fast-reroute ti-lfa level-1
```

```{cfgcmd} set protocols isis interface \<interface\> fast-reroute ti-lfa level-1 node-protection

**Enable node protection mode for Level-1 TI-LFA on the specified
interface.**

In node protection mode, TI-LFA computes backup paths that protect
against the failure of the next-hop node.
```

```{note}
LFA and TI-LFA cannot be configured at the same level on the same
interface.
```

Example:

```none
set protocols isis interface eth0 fast-reroute ti-lfa level-1 node-protection
```

```{cfgcmd} set protocols isis interface \<interface\> fast-reroute ti-lfa level-1 node-protection link-fallback

**Enable link-protection fallback for Level-1 TI-LFA on the specified
interface.**

When node protection cannot compute a backup path, the computation falls
back to link protection.
```

Example:

```none
set protocols isis interface eth1 fast-reroute ti-lfa level-1 node-protection link-fallback
```

#### Level-2 fast-reroute

```{cfgcmd} set protocols isis interface \<interface\> fast-reroute lfa level-2 enable

**Enable Level-2 LFA computation on the specified interface.**

When enabled, IS-IS precomputes a backup next-hop for each Level-2
destination reached through this interface. If the primary next-hop
fails, the router uses the precomputed backup instead.
```

Example:

```none
set protocols isis interface eth1 fast-reroute lfa level-2 enable
```

```{cfgcmd} set protocols isis interface \<interface-1\> fast-reroute lfa level-2 exclude interface \<interface-2\>

**Exclude an interface from being selected as a Level-2 LFA backup
next-hop on the specified interface.**

In the command syntax, `<interface-1>` identifies the protected interface,
and `<interface-2>` identifies the interface that must not be used as an
LFA backup next-hop.
```

Example:

```none
set protocols isis interface eth1 fast-reroute lfa level-2 exclude interface eth2
```

```{cfgcmd} set protocols isis interface \<interface\> fast-reroute remote-lfa level-2 tunnel mpls-ldp

**Enable Level-2 remote LFA computation using MPLS-LDP tunnels on the
specified interface.**

Remote LFA provides backup paths when local LFA cannot find a loop-free
alternate neighbor.

If the primary next-hop fails, the router sends traffic into an MPLS-LDP
tunnel to a precomputed remote LFA node. From there, normal IS-IS
forwarding delivers it to the destination.
```

```{note}
Remote LFA requires the corresponding local LFA to be configured on this
interface.
```

```{note}
Remote LFA requires all potential remote LFA endpoints in the IS-IS
routing instance to accept targeted LDP Hello messages.
```

Example:

```none
set protocols isis interface eth1 fast-reroute remote-lfa level-2 tunnel mpls-ldp
```

```{cfgcmd} set protocols isis interface \<interface\> fast-reroute remote-lfa level-2 maximum-metric \<1-16777215\>

**Configure the maximum metric for Level-2 remote LFA node selection on
the specified interface.**

Remote LFA nodes with a metric exceeding this value are excluded from
selection.
```

```{note}
The maximum metric applies only when the corresponding remote LFA is
enabled on this interface.
```

Example:

```none
set protocols isis interface eth1 fast-reroute remote-lfa level-2 maximum-metric 100
```

```{cfgcmd} set protocols isis interface \<interface\> fast-reroute ti-lfa level-2

**Enable Level-2 TI-LFA computation on the specified interface.**

By default, TI-LFA operates in link protection mode, computing backup
paths that protect against the failure of this interface's link.
```

```{note}
LFA and TI-LFA cannot be configured at the same level on the same
interface.
```

Example:

```none
set protocols isis interface eth1 fast-reroute ti-lfa level-2
```

```{cfgcmd} set protocols isis interface \<interface\> fast-reroute ti-lfa level-2 node-protection

**Enable node protection mode for Level-2 TI-LFA on the specified
interface.**

In node protection mode, TI-LFA computes backup paths that protect
against the failure of the next-hop node.
```

```{note}
LFA and TI-LFA cannot be configured at the same level on the same
interface.
```

Example:

```none
set protocols isis interface eth0 fast-reroute ti-lfa level-2 node-protection
```

```{cfgcmd} set protocols isis interface \<interface\> fast-reroute ti-lfa level-2 node-protection link-fallback

**Enable link-protection fallback for Level-2 TI-LFA on the specified
interface.**

When node protection cannot compute a backup path, the computation falls
back to link protection.
```

```{note}
LFA and TI-LFA cannot be configured at the same level on the same
interface.
```

Example:

```none
set protocols isis interface eth1 fast-reroute ti-lfa level-2 node-protection link-fallback
```

### Route redistribution

#### Level-1 IPv4

```{cfgcmd} set protocols isis redistribute ipv4 \<bgp | connected | kernel | nhrp | ospf | rip | babel | static\> level-1

**Configure the redistribution of IPv4 routing information from the
specified route source into IS-IS Level-1.**
```

```{note}
This command requires the router's IS-IS level to be set to `level-1` or
`level-1-2`.
```

Example:

```none
set protocols isis redistribute ipv4 bgp level-1
```

```{cfgcmd} set protocols isis redistribute ipv4 \<bgp | connected | kernel | nhrp | ospf | rip | babel | static\> level-1 metric \<0-16777215\>

**Configure the IS-IS metric for IPv4 routes redistributed from the
specified route source into IS-IS Level-1.**
```

```{note}
This command requires the router's IS-IS level to be set to `level-1` or
`level-1-2`.
```

Example:

```none
set protocols isis redistribute ipv4 bgp level-1 metric 50
```

```{cfgcmd} set protocols isis redistribute ipv4 \<bgp | connected | kernel | nhrp | ospf | rip | babel | static\> level-1 route-map \<name\>

**Apply a route-map to IPv4 routes redistributed from the specified route
source into IS-IS Level-1.**

Only routes permitted by the route-map are redistributed. The route-map
can modify the metric and tag of permitted routes.
```

```{note}
This command requires the router's IS-IS level to be set to `level-1` or
`level-1-2`.
```

Example:

```none
set protocols isis redistribute ipv4 bgp level-1 route-map BGP-TO-ISIS
```

#### Level-1 IPv6

```{cfgcmd} set protocols isis redistribute ipv6 \<bgp | connected | kernel | ospf6 | ripng | babel | static\> level-1

**Configure the redistribution of IPv6 routing information from the
specified route source into IS-IS Level-1.**
```

```{note}
This command requires the router's IS-IS level to be set to `level-1` or
`level-1-2`.
```

Example:

```none
set protocols isis redistribute ipv6 bgp level-1
```

```{cfgcmd} set protocols isis redistribute ipv6 \<bgp | connected | kernel | ospf6 | ripng | babel | static\> level-1 metric \<0-16777215\>

**Configure the IS-IS metric for IPv6 routes redistributed from the
specified route source into IS-IS Level-1.**
```

```{note}
This command requires the router's IS-IS level to be set to `level-1` or
`level-1-2`.
```

Example:

```none
set protocols isis redistribute ipv6 bgp level-1 metric 50
```

```{cfgcmd} set protocols isis redistribute ipv6 \<bgp | connected | kernel | ospf6 | ripng | babel | static\> level-1 route-map \<name\>

**Apply a route-map to IPv6 routes redistributed from the specified route
source into IS-IS Level-1.**

Only routes permitted by the route-map are redistributed. The route-map
can modify the metric and tag of permitted routes.
```

```{note}
This command requires the router's IS-IS level to be set to `level-1` or
`level-1-2`.
```

Example:

```none
set protocols isis redistribute ipv6 bgp level-1 route-map BGP-TO-ISIS
```

#### Level-2 IPv4

```{cfgcmd} set protocols isis redistribute ipv4 \<bgp | connected | kernel | nhrp | ospf | rip | babel | static\> level-2

**Configure the redistribution of IPv4 routing information from the
specified route source into IS-IS Level-2.**
```

```{note}
This command requires the router's IS-IS level to be set to `level-2` or
`level-1-2`.
```

Example:

```none
set protocols isis redistribute ipv4 bgp level-2
```

```{cfgcmd} set protocols isis redistribute ipv4 \<bgp | connected | kernel | nhrp | ospf | rip | babel | static\> level-2 metric \<0-16777215\>

**Configure the IS-IS metric for IPv4 routes redistributed from the
specified route source into IS-IS Level-2.**
```

```{note}
This command requires the router's IS-IS level to be set to `level-2` or
`level-1-2`.
```

Example:

```none
set protocols isis redistribute ipv4 bgp level-2 metric 50
```

```{cfgcmd} set protocols isis redistribute ipv4 \<bgp | connected | kernel | nhrp | ospf | rip | babel | static\> level-2 route-map \<name\>

**Apply a route-map to IPv4 routes redistributed from the specified route
source into IS-IS Level-2.**

Only routes permitted by the route-map are redistributed. The route-map
can modify the metric and tag of permitted routes.
```

```{note}
This command requires the router's IS-IS level to be set to `level-2` or
`level-1-2`.
```

Example:

```none
set protocols isis redistribute ipv4 bgp level-2 route-map BGP-TO-ISIS
```

#### Level-2 IPv6

```{cfgcmd} set protocols isis redistribute ipv6 \<bgp | connected | kernel | ospf6 | ripng | babel | static\> level-2

**Configure the redistribution of IPv6 routing information from the
specified route source into IS-IS Level-2.**
```

```{note}
This command requires the router's IS-IS level to be set to `level-2` or
`level-1-2`.
```

Example:

```none
set protocols isis redistribute ipv6 bgp level-2
```

```{cfgcmd} set protocols isis redistribute ipv6 \<bgp | connected | kernel | ospf6 | ripng | babel | static\> level-2 metric \<0-16777215\>

**Configure the IS-IS metric for IPv6 routes redistributed from the
specified route source into IS-IS Level-2.**
```

```{note}
This command requires the router's IS-IS level to be set to `level-2` or
`level-1-2`.
```

Example:

```none
set protocols isis redistribute ipv6 bgp level-2 metric 50
```

```{cfgcmd} set protocols isis redistribute ipv6 \<bgp | connected | kernel | ospf6 | ripng | babel | static\> level-2 route-map \<name\>

**Apply a route-map to IPv6 routes redistributed from the specified route
source into IS-IS Level-2.**

Only routes permitted by the route-map are redistributed. The route-map
can modify the metric and tag of permitted routes.
```

```{note}
This command requires the router's IS-IS level to be set to `level-2` or
`level-1-2`.
```

Example:

```none
set protocols isis redistribute ipv6 bgp level-2 route-map BGP-TO-ISIS
```

### Timers

```{cfgcmd} set protocols isis lsp-gen-interval \<1-120\>

**Configure the minimum interval, in seconds, between consecutive
regenerations of this router's own LSP.**

Regenerations triggered by events, such as network topology changes, are
postponed until the specified interval has elapsed since the previous
regeneration.

The default interval is 30 seconds.
```

Example:

```none
set protocols isis lsp-gen-interval 5
```

```{cfgcmd} set protocols isis lsp-refresh-interval \<2-65235\>

**Configure the maximum interval, in seconds, between consecutive
regenerations of this router's own LSP.**

When this interval elapses, the router regenerates its LSP even if no
event has triggered a regeneration.
```

```{note}
The value must be less than the configured `max-lsp-lifetime` so that the
LSP is refreshed before its remaining lifetime expires.
```

Example:

```none
set protocols isis lsp-refresh-interval 600
```

```{cfgcmd} set protocols isis max-lsp-lifetime \<350-65535\>

**Configure the lifetime, in seconds, of LSPs originated by this router.**

The default is 1200 seconds.
```

```{note}
This value must be greater than `lsp-refresh-interval` so that LSPs are
refreshed before their lifetime expires.
```

Example:

```none
set protocols isis max-lsp-lifetime 1500
```

```{cfgcmd} set protocols isis spf-interval \<1-120\>

**Configure the interval, in seconds, between consecutive SPF calculations
on this router.**

SPF calculations triggered by events, such as network topology changes,
are postponed until the specified interval has elapsed since the previous
calculation.
```

Example:

```none
set protocols isis spf-interval 5
```

The following commands implement the IETF SPF delay algorithm for IS-IS
described in [RFC 8405](https://datatracker.ietf.org/doc/html/rfc8405).
They control how quickly the router runs the SPF calculation after topology
changes are detected.

```{note}
All five `spf-delay-ietf` parameters must be configured; setting only some
of them causes a commit failure.
```

```{cfgcmd} set protocols isis spf-delay-ietf holddown \<0-60000\>

**Configure the interval, in milliseconds, that must elapse without
topology changes before the router considers the network stable.**

Once this time passes, the router returns to its initial response state
and applies `init-delay` to the next SPF calculation.
```

Example:

```none
set protocols isis spf-delay-ietf holddown 10000
```

```{cfgcmd} set protocols isis spf-delay-ietf init-delay \<0-60000\>

**Configure the interval, in milliseconds, that the router waits before
running the first SPF calculation when a new topology change arrives
after the network is considered stable.**
```

Example:

```none
set protocols isis spf-delay-ietf init-delay 500
```

```{cfgcmd} set protocols isis spf-delay-ietf time-to-learn \<0-60000\>

**Configure the learning interval, in milliseconds, that begins when the
first topology change is received.**

Within this window, the router applies the `short-delay` before performing
SPF recalculations triggered by additional topology changes.

If topology changes continue to arrive after this window expires, the
router considers the network unstable and delays subsequent SPF
recalculations by the configured `long-delay`.
```

Example:

```none
set protocols isis spf-delay-ietf time-to-learn 5000
```

```{cfgcmd} set protocols isis spf-delay-ietf long-delay \<0-60000\>

**Configure the interval, in milliseconds, the router applies before
running an SPF calculation when topology changes arrive after the
`time-to-learn` window expires.**
```

Example:

```none
set protocols isis spf-delay-ietf long-delay 10000
```

```{cfgcmd} set protocols isis spf-delay-ietf short-delay \<0-60000\>

**Configure the interval, in milliseconds, the router applies before
running subsequent SPF calculations triggered by additional topology
changes within the `time-to-learn` window.**

The first SPF in the window is delayed by `init-delay`.
```

Example:

```none
set protocols isis spf-delay-ietf short-delay 1000
```

### Loop-Free Alternate (LFA)

#### Level-1

```{cfgcmd} set protocols isis fast-reroute lfa remote prefix-list \<name\> level-1

**Filter which PQ nodes the router evaluates as Remote LFA tunnel
endpoints for IS-IS Level-1 using the specified prefix-list.**

Only PQ nodes permitted by the prefix-list are evaluated as potential
backup routers.
```

Example:

```none
set protocols isis fast-reroute lfa remote prefix-list CRITICAL-ROUTES level-1
```

```{cfgcmd} set protocols isis fast-reroute lfa local load-sharing disable level-1

**Disable load sharing across multiple local LFAs for IS-IS Level-1.**

When multiple LFAs are available to back up a given destination, the
router uses only one LFA instead of distributing rerouted traffic across
all of them.
```

Example:

```none
set protocols isis fast-reroute lfa local load-sharing disable level-1
```

```{cfgcmd} set protocols isis fast-reroute lfa local tiebreaker \<downstream | lowest-backup-metric | node-protecting\> index \<1-255\> level-1

**Configure a tiebreaker rule for selecting a single LFA when multiple
local LFAs exist for an IS-IS Level-1 prefix.**

Tiebreaker rules with lower index numbers are evaluated first. You can
choose one of the following tiebreaker behaviors:

- `downstream`: Prefers an alternate that is closer to the destination
  than this router.
- `lowest-backup-metric`: Prefers the alternate with the shortest path to
  the destination.
- `node-protecting`: Prefers an alternate that bypasses the primary
  next-hop router, protecting against a complete node failure rather than
  just link failure.
```

Example:

```none
set protocols isis fast-reroute lfa local tiebreaker node-protecting index 10 level-1
```

```{cfgcmd} set protocols isis fast-reroute lfa local priority-limit \<critical | high | medium\> level-1

**Configure the priority limit for calculating local LFAs in IS-IS
Level-1.**

The router calculates LFAs only for prefixes with a priority greater than
or equal to the specified limit. For example, setting the limit to `high`
protects both `high` and `critical` prefixes.
```

```{note}
Prefixes carry one of the following priorities: `low`, `medium`, `high`,
or `critical`. By default, the router assigns `medium` priority to
loopbacks and `low` priority to all other prefixes. The limit itself
accepts only `medium`, `high`, or `critical`.
```

Example:

```none
set protocols isis fast-reroute lfa local priority-limit critical level-1
```

#### Level-2

```{cfgcmd} set protocols isis fast-reroute lfa remote prefix-list \<name\> level-2

**Filter which PQ nodes the router evaluates as Remote LFA tunnel
endpoints for IS-IS Level-2 using the specified prefix-list.**

Only PQ nodes permitted by the prefix-list are evaluated as potential
backup routers.
```

Example:

```none
set protocols isis fast-reroute lfa remote prefix-list CRITICAL-ROUTES level-2
```

```{cfgcmd} set protocols isis fast-reroute lfa local load-sharing disable level-2

**Disable load sharing across multiple local LFAs for IS-IS Level-2.**

When multiple LFAs are available to back up a given destination, the
router uses only one LFA instead of distributing rerouted traffic across
all of them.
```

Example:

```none
set protocols isis fast-reroute lfa local load-sharing disable level-2
```

```{cfgcmd} set protocols isis fast-reroute lfa local tiebreaker \<downstream | lowest-backup-metric | node-protecting\> index \<1-255\> level-2

**Configure a tiebreaker rule for selecting a single LFA when multiple
local LFAs exist for an IS-IS Level-2 prefix.**

Tiebreaker rules with lower index numbers are evaluated first. You can
choose one of the following tiebreaker behaviors:

- `downstream`: Prefers an alternate that is closer to the destination
  than this router.
- `lowest-backup-metric`: Prefers the alternate with the shortest path to
  the destination.
- `node-protecting`: Prefers an alternate that bypasses the primary
  next-hop router, protecting against a complete node failure rather than
  just link failure.
```

Example:

```none
set protocols isis fast-reroute lfa local tiebreaker node-protecting index 10 level-2
```

```{cfgcmd} set protocols isis fast-reroute lfa local priority-limit \<critical | high | medium\> level-2

**Configure the priority limit for calculating local LFAs in IS-IS
Level-2.**
```

```{note}
Prefixes carry one of the following priorities: `low`, `medium`, `high`,
or `critical`. By default, the router assigns `medium` priority to
loopbacks and `low` priority to all other prefixes. The limit itself
accepts only `medium`, `high`, or `critical`.
```

Example:

```none
set protocols isis fast-reroute lfa local priority-limit critical level-2
```

### Segment Routing over IPv6 (SRv6)

```{cfgcmd} set protocols isis segment-routing srv6 interface \<interface\>

**Enable IS-IS Segment Routing over IPv6 (SRv6) on the specified
interface.**

Once enabled, IS-IS allocates and advertises an adjacency SID for each
IS-IS neighbor reached through this interface, so other routers can steer
SRv6 traffic over it.
```

Example:

```none
set protocols isis segment-routing srv6 interface eth1
```

```{cfgcmd} set protocols isis segment-routing srv6 locator \<locator\>

**Configure IS-IS to use a globally defined SRv6 locator.**

The locator itself must be configured separately using
`set protocols segment-routing srv6 locator <name> prefix <ipv6-prefix>`.

Once you attach the locator to IS-IS, the routing process automatically:

- Allocates a node SID for the router and an adjacency SID for each of
  its IS-IS neighbors.
- Advertises the locator and these SIDs to the network so other routers
  can route SRv6 traffic through this node.
```

Example:

```none
set protocols isis segment-routing srv6 locator MAIN-LOCATOR
```

```{cfgcmd} set protocols isis segment-routing srv6 node-msd max-end-d \<0-255\>

**Configure the Maximum End D MSD value advertised by the router
([RFC 9352](https://datatracker.ietf.org/doc/html/rfc9352)).**

This value indicates the maximum number of SIDs in the SRH that this
router can handle when performing a decapsulation behavior (e.g.,
`End.DX6`, `End.DT4`, `End.DT46`, `End with USD`, `End.X with USD`)
defined in [RFC 8986](https://datatracker.ietf.org/doc/html/rfc8986).

If this value is set to 0 or left unconfigured, the router advertises
that it cannot decapsulate and forward packets when an SRH is present.
```

Example:

```none
set protocols isis segment-routing srv6 node-msd max-end-d 8
```

```{cfgcmd} set protocols isis segment-routing srv6 node-msd max-end-pop \<0-255\>

**Configure the Maximum End Pop MSD value advertised by the router
([RFC 9352](https://datatracker.ietf.org/doc/html/rfc9352)).**

This value indicates the maximum number of SIDs in the received SRH to
which this router can apply the PSP (Penultimate Segment Pop) or USP
(Ultimate Segment Pop) flavors defined in
[RFC 8986, §4.16](https://datatracker.ietf.org/doc/html/rfc8986#section-4.16).

If this value is set to 0 or left unconfigured, the router advertises
that it cannot apply the PSP or USP flavors.
```

Example:

```none
set protocols isis segment-routing srv6 node-msd max-end-pop 16
```

```{cfgcmd} set protocols isis segment-routing srv6 node-msd max-h-encaps \<0-255\>

**Configure the Maximum H.Encaps MSD value advertised by the router
([RFC 9352](https://datatracker.ietf.org/doc/html/rfc9352)).**

This value indicates the maximum number of SIDs that this router can
insert into a new {abbr}`SRH (Segment Routing Header)` when encapsulating
traffic (the H.Encaps behavior), as defined in
[RFC 8986](https://datatracker.ietf.org/doc/html/rfc8986).

If set to 0 or left unconfigured, the router advertises that it can only
apply an SR Policy containing a single segment, without inserting an SRH.
```

Example:

```none
set protocols isis segment-routing srv6 node-msd max-h-encaps 8
```

```{cfgcmd} set protocols isis segment-routing srv6 node-msd max-segs-left \<0-255\>

**Configure the Maximum Segments Left MSD value advertised by the router
([RFC 9352](https://datatracker.ietf.org/doc/html/rfc9352)).**

This value indicates the maximum Segments Left value
([RFC 8754](https://datatracker.ietf.org/doc/html/rfc8754)) in the SRH of
a received packet that this router can process before applying the
Endpoint behavior associated with a SID.

If set to 0 or left unconfigured, the router advertises that it can only
be the last segment of an SRv6 path. Set a value greater than 0 to also
allow the router to be used as a segment in the middle of a path.
```

Example:

```none
set protocols isis segment-routing srv6 node-msd max-segs-left 8
```

## Examples

### Enable IS-IS

The following example demonstrates a basic IS-IS routing protocol setup between
two VyOS routers.

**Node 1:**

```none
set interfaces loopback lo address '198.51.100.1/32'
set interfaces ethernet eth1 address '192.0.2.1/24'

set protocols isis interface eth1
set protocols isis interface lo
set protocols isis net '49.0001.1980.5110.0001.00'
```

**Node 2:**

```none
set interfaces loopback lo address '198.51.100.2/32'
set interfaces ethernet eth1 address '192.0.2.2/24'

set protocols isis interface eth1
set protocols isis interface lo
set protocols isis net '49.0001.1980.5110.0002.00'
```

This gives us the following neighborships, Level 1 and Level 2:

```none
Node-1@vyos:~$ show isis neighbor
Area VyOS:
 System Id           Interface   L  State        Holdtime SNPA
 vyos                eth1        1  Up            28       0c87.6c09.0001
 vyos                eth1        2  Up            28       0c87.6c09.0001

Node-2@vyos:~$ show isis neighbor
Area VyOS:
 System Id           Interface   L  State        Holdtime SNPA
 vyos                eth1        1  Up            29       0c33.0280.0001
 vyos                eth1        2  Up            28       0c33.0280.0001
```

Here's the IP routes that are populated. Just the loopback:

```none
Node-1@vyos:~$ show ip route isis
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, F - PBR,
       f - OpenFabric,
       > - selected route, * - FIB route, q - queued, r - rejected, b - backup
       t - trapped, o - offload failure

I   192.0.2.0/24 [115/20] via 192.0.2.2, eth1 inactive, weight 1, 00:02:22
I>* 198.51.100.2/32 [115/20] via 192.0.2.2, eth1, weight 1, 00:02:22

Node-2@vyos:~$ show ip route isis
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, F - PBR,
       f - OpenFabric,
       > - selected route, * - FIB route, q - queued, r - rejected, b - backup
       t - trapped, o - offload failure

I   192.0.2.0/24 [115/20] via 192.0.2.1, eth1 inactive, weight 1, 00:02:21
I>* 198.51.100.1/32 [115/20] via 192.0.2.1, eth1, weight 1, 00:02:21
```

### Enable IS-IS and redistribute routes not natively in IS-IS

The following example demonstrates a basic IS-IS setup between two VyOS
routers, with Node 1 also redistributing a connected network that isn't running
IS-IS.

**Node 1:**

```none
set interfaces dummy dum0 address '203.0.113.1/24'
set interfaces ethernet eth1 address '192.0.2.1/24'

set policy prefix-list EXPORT-ISIS rule 10 action 'permit'
set policy prefix-list EXPORT-ISIS rule 10 prefix '203.0.113.0/24'
set policy route-map EXPORT-ISIS rule 10 action 'permit'
set policy route-map EXPORT-ISIS rule 10 match ip address prefix-list 'EXPORT-ISIS'

set protocols isis interface eth1
set protocols isis net '49.0001.2030.0011.3001.00'
set protocols isis redistribute ipv4 connected level-2 route-map 'EXPORT-ISIS'
```

**Node 2:**

```none
set interfaces ethernet eth1 address '192.0.2.2/24'

set protocols isis interface eth1
set protocols isis net '49.0001.1920.0000.2002.00'
```

Routes on Node 2:

```none
Node-2@r2:~$ show ip route isis
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,
       F - PBR, f - OpenFabric,
       > - selected route, * - FIB route, q - queued route, r - rejected route

I   203.0.113.0/24 [115/10] via 192.0.2.1, eth1, 00:03:42
```

### Enable IS-IS and IGP-LDP synchronization

The following example demonstrates an IS-IS setup with IGP-LDP synchronization
enabled on Node 1.

**Node 1:**

```none
set interfaces loopback lo address 198.51.100.1/32
set interfaces ethernet eth0 address 192.0.2.1/24

set protocols isis interface eth0
set protocols isis interface lo passive
set protocols isis ldp-sync
set protocols isis net 49.0001.1980.5110.0001.00

set protocols mpls interface eth0
set protocols mpls ldp discovery transport-ipv4-address 198.51.100.1
set protocols mpls ldp interface lo
set protocols mpls ldp interface eth0
set protocols mpls ldp parameters transport-prefer-ipv4
set protocols mpls ldp router-id 198.51.100.1
```

This gives us IGP-LDP synchronization for all non-loopback interfaces with
a holddown timer of zero seconds:

```none
Node-1@vyos:~$  show isis mpls ldp-sync
eth0
  LDP-IGP Synchronization enabled: yes
  holddown timer in seconds: 0
  State: Sync achieved
```

### Enable IS-IS with Segment Routing (experimental)

The following example demonstrates IS-IS with segment routing between two VyOS
routers.

**Node 1:**

```none
set interfaces loopback lo address '198.51.100.1/32'
set interfaces ethernet eth1 address '192.0.2.1/24'

set protocols isis interface eth1
set protocols isis interface lo
set protocols isis net '49.0001.1980.5110.0001.00'
set protocols isis segment-routing global-block high-label-value '599'
set protocols isis segment-routing global-block low-label-value '550'
set protocols isis segment-routing prefix 198.51.100.1/32 index value '1'
set protocols isis segment-routing prefix 198.51.100.1/32 index explicit-null
set protocols mpls interface 'eth1'
```

**Node 2:**

```none
set interfaces loopback lo address '198.51.100.2/32'
set interfaces ethernet eth1 address '192.0.2.2/24'

set protocols isis interface eth1
set protocols isis interface lo
set protocols isis net '49.0001.1980.5110.0002.00'
set protocols isis segment-routing global-block high-label-value '599'
set protocols isis segment-routing global-block low-label-value '550'
set protocols isis segment-routing prefix 198.51.100.2/32 index value '2'
set protocols isis segment-routing prefix 198.51.100.2/32 index explicit-null
set protocols mpls interface 'eth1'
```

This gives us MPLS segment routing enabled and labels for far end loopbacks:

```none
Node-1@vyos:~$ show mpls table
 Inbound Label  Type        Nexthop                Outbound Label
 ----------------------------------------------------------------------
 552            SR (IS-IS)  192.0.2.2              IPv4 Explicit Null <-- Node-2 loopback learned on Node-1
 15000          SR (IS-IS)  192.0.2.2              implicit-null
 15001          SR (IS-IS)  fe80::e87:6cff:fe09:1  implicit-null
 15002          SR (IS-IS)  192.0.2.2              implicit-null
 15003          SR (IS-IS)  fe80::e87:6cff:fe09:1  implicit-null

Node-2@vyos:~$ show mpls table
 Inbound Label  Type        Nexthop               Outbound Label
 ---------------------------------------------------------------------
 551            SR (IS-IS)  192.0.2.1             IPv4 Explicit Null <-- Node-1 loopback learned on Node-2
 15000          SR (IS-IS)  192.0.2.1             implicit-null
 15001          SR (IS-IS)  fe80::e33:2ff:fe80:1  implicit-null
 15002          SR (IS-IS)  192.0.2.1             implicit-null
 15003          SR (IS-IS)  fe80::e33:2ff:fe80:1  implicit-null
```

Here is the routing tables showing the MPLS segment routing label operations:

```none
Node-1@vyos:~$ show ip route isis
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, F - PBR,
       f - OpenFabric,
       > - selected route, * - FIB route, q - queued, r - rejected, b - backup
       t - trapped, o - offload failure

I   192.0.2.0/24 [115/20] via 192.0.2.2, eth1 inactive, weight 1, 00:07:48
I>* 198.51.100.2/32 [115/20] via 192.0.2.2, eth1, label IPv4 Explicit Null, weight 1, 00:03:39

Node-2@vyos:~$ show ip route isis
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, F - PBR,
       f - OpenFabric,
       > - selected route, * - FIB route, q - queued, r - rejected, b - backup
       t - trapped, o - offload failure

I   192.0.2.0/24 [115/20] via 192.0.2.1, eth1 inactive, weight 1, 00:07:46
I>* 198.51.100.1/32 [115/20] via 192.0.2.1, eth1, label IPv4 Explicit Null, weight 1, 00:03:43
```

### Enable IS-IS with Segment Routing over IPv6 (experimental)

The following example demonstrates IS-IS with Segment Routing over IPv6
between two VyOS routers.

**Node 1:**

```none
set interfaces dummy dum6 description "SRv6 IS-IS"
set interfaces ethernet eth1 address '192.0.2.1/24'
set interfaces loopback lo address '198.51.100.1/32'

set protocols segment-routing srv6 locator MAIN prefix 2001:db8:1::/64
set protocols segment-routing interface eth1

set protocols isis interface eth1
set protocols isis interface lo
set protocols isis net '49.0001.1980.5110.0001.00'
set protocols isis segment-routing srv6 locator MAIN
set protocols isis segment-routing srv6 interface dum6
```

**Node 2:**

```none
set interfaces dummy dum6 description "SRv6 IS-IS"
set interfaces ethernet eth1 address '192.0.2.2/24'
set interfaces loopback lo address '198.51.100.2/32'

set protocols segment-routing srv6 locator MAIN prefix 2001:db8:2::/64
set protocols segment-routing interface eth1

set protocols isis interface eth1
set protocols isis interface lo
set protocols isis net '49.0001.1980.5110.0002.00'
set protocols isis segment-routing srv6 locator MAIN
set protocols isis segment-routing srv6 interface dum6
```

### Enable IS-IS with Segment Routing over IPv6 (uSID) (experimental)

The following example demonstrates IS-IS with SRv6 uSID (micro-SID) between two
VyOS routers.

**Node 1:**

```none
set interfaces dummy dum6 description "SRv6 IS-IS"
set interfaces ethernet eth1 address '192.0.2.1/24'
set interfaces loopback lo address '198.51.100.1/32'

set protocols segment-routing interface eth1
set protocols segment-routing srv6 locator MAIN prefix 2001:db8:1::/48
set protocols segment-routing srv6 locator MAIN behavior-usid
set protocols segment-routing srv6 locator MAIN block-len 32
set protocols segment-routing srv6 locator MAIN format usid-f3216
set protocols segment-routing srv6 locator MAIN func-bits 16
set protocols segment-routing srv6 locator MAIN node-len 16

set protocols isis interface eth1
set protocols isis interface lo
set protocols isis net '49.0001.1980.5110.0001.00'
set protocols isis segment-routing srv6 interface dum6
set protocols isis segment-routing srv6 locator MAIN
```

**Node 2:**

```none
set interfaces dummy dum6 description "SRv6 IS-IS"
set interfaces ethernet eth1 address '192.0.2.2/24'
set interfaces loopback lo address '198.51.100.2/32'

set protocols segment-routing interface eth1
set protocols segment-routing srv6 locator MAIN prefix 2001:db8:2::/48
set protocols segment-routing srv6 locator MAIN behavior-usid
set protocols segment-routing srv6 locator MAIN block-len 32
set protocols segment-routing srv6 locator MAIN format usid-f3216
set protocols segment-routing srv6 locator MAIN func-bits 16
set protocols segment-routing srv6 locator MAIN node-len 16

set protocols isis interface eth1
set protocols isis interface lo
set protocols isis net '49.0001.1980.5110.0002.00'
set protocols isis segment-routing srv6 interface dum6
set protocols isis segment-routing srv6 locator MAIN
```
