---
myst:
  html_meta:
    description: |
      Multiprotocol Label Switching (MPLS) is a packet-forwarding method
      that forwards traffic using exact-match lookups on MPLS labels
      rather than IP address lookups.
    keywords: mpls, ldp, label distribution protocol, lsp, label switching
---

(mpls)=

# MPLS

{abbr}`MPLS (Multiprotocol Label Switching)` is a packet-forwarding method
that differs from traditional IP forwarding. Instead of performing IP address
lookups, MPLS routers forward traffic using exact-match lookups on MPLS labels
inserted between the Layer 2 (Ethernet) and Layer 3 (IP) headers.

MPLS labels can be assigned statically or dynamically. This section focuses on
dynamic label allocation using label distribution protocols such as the
{abbr}`LDP (Label Distribution Protocol)` and
{abbr}`RSVP-TE (Resource Reservation Protocol for Traffic Engineering)`, or
via {abbr}`SR (Segment Routing)` extensions to OSPF or IS-IS.

These protocols establish a unidirectional path called a
{abbr}`LSP (Label-Switched Path)` across the network. When a packet enters
the MPLS network, the ingress router pushes an MPLS label onto it based on
the destination and forwards the packet along the LSP. Each intermediate
router uses the incoming label to look up the outgoing interface and next
label value, swaps the label, and forwards the packet on that interface. The
egress router pops the label and forwards the original packet using normal
IP routing.

## MPLS support in VyOS

MPLS support in VyOS is under development, so its feature set is currently
limited. Basic MPLS forwarding is functional, as the underlying FRR routing
stack supports [RFC 3031](https://datatracker.ietf.org/doc/html/rfc3031).

Supported features:

- **LDP**: Implemented according to
  [RFC 5036](https://datatracker.ietf.org/doc/html/rfc5036).

```{note}
Other related LDP standards include RFCs
[6720](https://datatracker.ietf.org/doc/html/rfc6720),
[6667](https://datatracker.ietf.org/doc/html/rfc6667),
[5919](https://datatracker.ietf.org/doc/html/rfc5919),
[5561](https://datatracker.ietf.org/doc/html/rfc5561), and
[7552](https://datatracker.ietf.org/doc/html/rfc7552).
```

Current limitations:

- **MPLS VPNs**: No support yet for MPLS-enabled VPN services, such as
  L2VPNs and mVPNs.
- **RSVP-TE**: Not supported, as the underlying FRR stack does not currently
  implement it.

## Label Distribution Protocol (LDP)

MPLS supports various protocols for path creation. VyOS implements LDP via
the underlying FRR routing stack, per
[RFC 5036](https://datatracker.ietf.org/doc/html/rfc5036).

LDP is a TCP-based MPLS signaling protocol that dynamically distributes
labels to create label-switched paths. It is not a routing protocol and
depends on existing routing protocols for forwarding decisions and
communication with other LDP-enabled routers.

To exchange label advertisements, LDP establishes TCP sessions with
automatically discovered or statically configured neighbors. Each session is
formed using the peer's transport address, which must be present in the routing
table and continuously reachable.

```{note}
It is recommended to use the same address for both the LDP router
ID and the discovery transport address. For MPLS LDP to function in VyOS,
both parameters must be explicitly configured.
```

```{note}
LDP has no mechanism to refresh an existing session. To apply a
configuration change or a change to negotiated session capabilities, the
LDP neighbor must be reset on the local router.
```

## Configuration

```{cfgcmd} set protocols mpls interface \<interface\>

**Enable MPLS on the specified interface.**
```

Example:

```none
set protocols mpls interface eth1
```

```{cfgcmd} set protocols mpls parameters no-propagate-ttl

**Disable propagation of the IP TTL into the MPLS header at label
imposition.**
```

Example:

```none
set protocols mpls parameters no-propagate-ttl
```

```{cfgcmd} set protocols mpls parameters maximum-ttl \<1-255\>

**Configure the maximum TTL value for MPLS packets.**

This value is used when the TTL is not propagated from the IP header.
The default is 255.
```

Example:

```none
set protocols mpls parameters maximum-ttl 15
```

```{cfgcmd} set protocols mpls ldp interface \<interface\>

**Enable LDP on the specified interface.**
```

Example:

```none
set protocols mpls ldp interface eth1
```

```{cfgcmd} set protocols mpls ldp interface \<interface\> disable-establish-hello

**Disable the triggered Hello that the router sends on the specified
interface in response to receiving an LDP Hello from a peer.**
```

Example:

```none
set protocols mpls ldp interface eth0 disable-establish-hello
```

```{cfgcmd} set protocols mpls ldp router-id \<address\>

**Configure the IP address used as the LDP router ID for the local device.**
```

Example:

```none
set protocols mpls ldp router-id 192.0.2.1
```

```{cfgcmd} set protocols mpls ldp discovery transport-ipv4-address \<address\>

**Configure the IPv4 transport address for IPv4 LDP connections.**
```

Example:

```none
set protocols mpls ldp discovery transport-ipv4-address 192.0.2.1
```

```{cfgcmd} set protocols mpls ldp discovery transport-ipv6-address \<address\>

**Configure the IPv6 transport address for IPv6 LDP connections.**
```

Example:

```none
set protocols mpls ldp discovery transport-ipv6-address 2001:db8::1
```

```{cfgcmd} set protocols mpls ldp neighbor \<ipv4-address\> password \<password\>

**Configure authentication for the LDP session with the specified
neighbor.**
```

```{note}
For the session to establish successfully, both peers must be configured
with the same password.
```

Example:

```none
set protocols mpls ldp neighbor 192.0.2.2 password mysharedsecret
```

```{cfgcmd} set protocols mpls ldp neighbor \<ipv4-address\> session-holdtime \<15-65535\>

**Configure the LDP session hold time, in seconds, advertised to the
specified neighbor.**

The neighbor must be reset for this change to take effect.
```

Example:

```none
set protocols mpls ldp neighbor 192.0.2.2 session-holdtime 180
```

```{cfgcmd} set protocols mpls ldp neighbor \<ipv4-address\> ttl-security \<disable | 1-254\>

**Configure TTL security ({abbr}`GTSM (Generalized TTL Security Mechanism)`)
for the LDP session with the specified neighbor.**

Use `disable` to turn off TTL security, or set a hop-count value (1-254) to
restrict which incoming packets are accepted based on their TTL.
```

Example:

```none
set protocols mpls ldp neighbor 192.0.2.2 ttl-security 5
```

```{cfgcmd} set protocols mpls ldp discovery hello-ipv4-interval \<1-65535\>

**Configure the interval, in seconds, at which the router sends IPv4 LDP
Hello messages.**
```

Example:

```none
set protocols mpls ldp discovery hello-ipv4-interval 5
```

```{cfgcmd} set protocols mpls ldp discovery hello-ipv4-holdtime \<1-65535\>

**Configure the hold time, in seconds, advertised in IPv4 LDP Hello
messages.**
```

Example:

```none
set protocols mpls ldp discovery hello-ipv4-holdtime 15
```

```{cfgcmd} set protocols mpls ldp discovery hello-ipv6-interval \<1-65535\>

**Configure the interval, in seconds, at which the router sends IPv6 LDP
Hello messages.**
```

Example:

```none
set protocols mpls ldp discovery hello-ipv6-interval 5
```

```{cfgcmd} set protocols mpls ldp discovery hello-ipv6-holdtime \<1-65535\>

**Configure the hold time, in seconds, advertised in IPv6 LDP Hello
messages.**
```

Example:

```none
set protocols mpls ldp discovery hello-ipv6-holdtime 15
```

```{cfgcmd} set protocols mpls ldp discovery session-ipv4-holdtime \<15-65535\>

**Configure the LDP session hold time, in seconds, advertised in IPv4 LDP
Initialization messages.**
```

Example:

```none
set protocols mpls ldp discovery session-ipv4-holdtime 180
```

```{cfgcmd} set protocols mpls ldp discovery session-ipv6-holdtime \<15-65535\>

**Configure the LDP session hold time, in seconds, advertised in IPv6 LDP
Initialization messages.**
```

Example:

```none
set protocols mpls ldp discovery session-ipv6-holdtime 180
```

```{cfgcmd} set protocols mpls ldp import ipv4 import-filter filter-access-list \<1-2699\>

**Filter the IPv4 label bindings (associations between an IPv4 prefix and
an MPLS label) from LDP peers using the specified access list.**

Only label bindings whose prefix is permitted by the access list are
accepted.
```

Example:

```none
set protocols mpls ldp import ipv4 import-filter filter-access-list 10
```

```{cfgcmd} set protocols mpls ldp import ipv4 import-filter neighbor-access-list \<1-2699\>

**Filter the IPv4 label bindings (associations between an IPv4 prefix
and an MPLS label) from LDP peers using the specified access list.**

Only label bindings received from a peer whose IPv4 address is permitted
by the access list are accepted.
```

Example:

```none
set protocols mpls ldp import ipv4 import-filter neighbor-access-list 20
```

```{cfgcmd} set protocols mpls ldp import ipv6 import-filter filter-access-list6 \<1-2699\>

**Filter the IPv6 label bindings (associations between an IPv6 prefix and
an MPLS label) from LDP peers using the specified access list.**

Only label bindings whose prefix is permitted by the access list are
accepted.
```

Example:

```none
set protocols mpls ldp import ipv6 import-filter filter-access-list6 10
```

```{cfgcmd} set protocols mpls ldp import ipv6 import-filter neighbor-access-list6 \<1-2699\>

**Filter the IPv6 label bindings (associations between an IPv6 prefix
and an MPLS label) from LDP peers using the specified access list.**

Only label bindings received from a peer whose IPv6 address is permitted
by the access list are accepted.
```

Example:

```none
set protocols mpls ldp import ipv6 import-filter neighbor-access-list6 20
```

```{cfgcmd} set protocols mpls ldp export ipv4 export-filter filter-access-list \<1-2699\>

**Filter the IPv4 label bindings (associations between an IPv4 prefix and
an MPLS label) advertised to LDP peers using the specified access list.**

Only label bindings whose prefix is permitted by the access list are
advertised.
```

Example:

```none
set protocols mpls ldp export ipv4 export-filter filter-access-list 10
```

```{cfgcmd} set protocols mpls ldp export ipv4 export-filter neighbor-access-list \<1-2699\>

**Filter the IPv4 label bindings (associations between an IPv4 prefix
and an MPLS label) advertised to LDP peers using the specified access
list.**

Label bindings are advertised only to peers whose IPv4 address is
permitted by the access list.
```

Example:

```none
set protocols mpls ldp export ipv4 export-filter neighbor-access-list 20
```

```{cfgcmd} set protocols mpls ldp export ipv6 export-filter filter-access-list6 \<1-2699\>

**Filter the IPv6 label bindings (associations between an IPv6 prefix and
an MPLS label) advertised to LDP peers using the specified access list.**

Only label bindings whose prefix is permitted by the access list are
advertised.
```

Example:

```none
set protocols mpls ldp export ipv6 export-filter filter-access-list6 10
```

```{cfgcmd} set protocols mpls ldp export ipv6 export-filter neighbor-access-list6 \<1-2699\>

**Filter the IPv6 label bindings (associations between an IPv6 prefix
and an MPLS label) advertised to LDP peers using the specified access
list.**

Label bindings are advertised only to peers whose IPv6 address is
permitted by the access list.
```

Example:

```none
set protocols mpls ldp export ipv6 export-filter neighbor-access-list6 20
```

```{cfgcmd} set protocols mpls ldp export ipv4 explicit-null

**Configure the router to advertise the Explicit Null label for its
directly connected IPv4 prefixes to LDP neighbors.**

This instructs the penultimate-hop router to forward labeled packets
unchanged without removing the MPLS label.
```

Example:

```none
set protocols mpls ldp export ipv4 explicit-null
```

```{cfgcmd} set protocols mpls ldp export ipv6 explicit-null

**Configure the router to advertise the Explicit Null label for its
directly connected IPv6 prefixes to LDP neighbors.**

This instructs the penultimate-hop router to forward labeled packets
unchanged without removing the MPLS label.
```

Example:

```none
set protocols mpls ldp export ipv6 explicit-null
```

```{cfgcmd} set protocols mpls ldp allocation ipv4 access-list \<1-2699\>

**Restrict MPLS label allocation to IPv4 prefixes permitted by the
specified access list.**

By default, LDP allocates a label for every IPv4 prefix in the routing
table. A common best practice is to limit allocation to loopback
addresses.
```

Example:

```none
set protocols mpls ldp allocation ipv4 access-list 10
```

```{cfgcmd} set protocols mpls ldp allocation ipv6 access-list6 \<1-2699\>

**Restrict MPLS label allocation to IPv6 prefixes permitted by the
specified access list.**

By default, LDP allocates a label for every IPv6 prefix in the routing
table. A common best practice is to limit allocation to loopback
addresses.
```

Example:

```none
set protocols mpls ldp allocation ipv6 access-list6 10
```

```{cfgcmd} set protocols mpls ldp parameters cisco-interop-tlv

**Configure the router to negotiate the Dual-Stack capability
{abbr}`TLV (Type-Length-Value)`
([RFC 7552](https://datatracker.ietf.org/doc/html/rfc7552)) using a Cisco
non-compliant format for dual-stack LDP sessions.**
```

Example:

```none
set protocols mpls ldp parameters cisco-interop-tlv
```

```{cfgcmd} set protocols mpls ldp parameters ordered-control

**Enable LDP Ordered Label Distribution Control mode
([RFC 5036](https://datatracker.ietf.org/doc/html/rfc5036)) for the
router.**

By default, the router operates in Independent Label Distribution Control
mode.
```

Example:

```none
set protocols mpls ldp parameters ordered-control
```

```{cfgcmd} set protocols mpls ldp parameters transport-prefer-ipv4

**Configure the router to prefer an IPv4 TCP transport connection for LDP
peering when LDP is configured for dual-stack operation (both IPv4 and
IPv6 address families are enabled).**
```

Example:

```none
set protocols mpls ldp parameters transport-prefer-ipv4
```

```{cfgcmd} set protocols mpls ldp targeted-neighbor ipv4 enable

**Enable the router to accept targeted IPv4 LDP sessions.**

This allows the router to establish LDP adjacencies with non-directly
connected peers by responding to inbound targeted (unicast) LDP Hello
messages.
```

Example:

```none
set protocols mpls ldp targeted-neighbor ipv4 enable
```

```{cfgcmd} set protocols mpls ldp targeted-neighbor ipv6 enable

**Enable the router to accept targeted IPv6 LDP sessions.**

This allows the router to establish LDP adjacencies with non-directly
connected peers by responding to inbound targeted (unicast) LDP Hello
messages.
```

Example:

```none
set protocols mpls ldp targeted-neighbor ipv6 enable
```

```{cfgcmd} set protocols mpls ldp targeted-neighbor ipv4 address \<address\>

**Configure the router to initiate a targeted IPv4 LDP session with the
specified remote {abbr}`LSR (Label Switching Router)`.**
```

Example:

```none
set protocols mpls ldp targeted-neighbor ipv4 address 192.0.2.5
```

```{cfgcmd} set protocols mpls ldp targeted-neighbor ipv6 address \<address\>

**Configure the router to initiate a targeted IPv6 LDP session with the
specified remote LSR.**
```

Example:

```none
set protocols mpls ldp targeted-neighbor ipv6 address 2001:db8::5
```

```{cfgcmd} set protocols mpls ldp targeted-neighbor ipv4 hello-holdtime \<1-65535\>

**Configure the hold time, in seconds, advertised in targeted IPv4 LDP
Hello messages.**
```

Example:

```none
set protocols mpls ldp targeted-neighbor ipv4 hello-holdtime 45
```

```{cfgcmd} set protocols mpls ldp targeted-neighbor ipv4 hello-interval \<1-65535\>

**Configure the interval, in seconds, between targeted IPv4 LDP Hello
messages sent to remote LSRs.**
```

Example:

```none
set protocols mpls ldp targeted-neighbor ipv4 hello-interval 15
```

```{cfgcmd} set protocols mpls ldp targeted-neighbor ipv6 hello-holdtime \<1-65535\>

**Configure the hold time, in seconds, advertised in targeted IPv6 LDP
Hello messages.**
```

Example:

```none
set protocols mpls ldp targeted-neighbor ipv6 hello-holdtime 45
```

```{cfgcmd} set protocols mpls ldp targeted-neighbor ipv6 hello-interval \<1-65535\>

**Configure the interval, in seconds, between targeted IPv6 LDP Hello
messages sent to remote LSRs.**
```

Example:

```none
set protocols mpls ldp targeted-neighbor ipv6 hello-interval 15
```

## Operation

When LDP is established, you can view label assignments directly within the
`show ip route` or `show ipv6 route` outputs. To inspect LDP operational
states, use the following commands.

### Show

```{opcmd} show mpls ldp binding

Show the {abbr}`LIB (Label Information Base)`.
```

```{opcmd} show mpls ldp binding \<prefix\>

Show LDP label bindings for the specified prefix.

The `<prefix>` parameter accepts an IPv4 prefix (`x.x.x.x/x`) or IPv6
prefix (`h:h:h:h:h:h:h:h/h`).
```

```{opcmd} show mpls ldp binding detail

Show detailed LDP Label Information Base (LIB) entries.
```

```{opcmd} show mpls ldp binding neighbor \<address\>

Show LDP label bindings learned from the specified peer.

The `<address>` parameter accepts an IPv4 or IPv6 address.
```

```{opcmd} show mpls ldp binding local-label \<label\>

Show LDP label bindings associated with the specified locally
assigned label value.
```

```{opcmd} show mpls ldp binding remote-label \<label\>

Show LDP label bindings associated with the specified remotely
assigned label value.
```

```{opcmd} show mpls ldp discovery

Show LDP discovery Hello information.
```

```{opcmd} show mpls ldp discovery detail

Show detailed LDP discovery Hello information.
```

```{opcmd} show mpls ldp interface

Show LDP interface information.
```

```{opcmd} show mpls ldp neighbor

Show basic LDP neighbor information.
```

```{opcmd} show mpls ldp neighbor detail

Show detailed LDP neighbor information.
```

```{opcmd} show mpls ldp neighbor capabilities

Show the LDP capabilities negotiated with each peer during session
initialization.
```

```{opcmd} show mpls ldp neighbor \<address\>

Show LDP neighbor information for the specified peer.

The `<address>` parameter accepts an IPv4 or IPv6 address.
```

```{opcmd} show mpls ldp neighbor \<address\> detail

Show detailed LDP session information for the specified peer.
```

```{opcmd} show mpls ldp neighbor \<address\> capabilities

Show the LDP capabilities negotiated with the specified peer.
```

```{opcmd} show mpls table

Show the MPLS table.
```

```{opcmd} show mpls pseudowire

Show MPLS pseudowire interfaces.
```

### Reset

```{opcmd} reset mpls ldp neighbor \<address\>

Reset the established LDP session with the specified neighbor.

The `<address>` parameter accepts an IPv4 or IPv6 address.
```

## Example

The following configuration sets up a basic MPLS LDP-enabled router.
OSPF is used as the underlying IGP to provide reachability between LDP
peers' loopback addresses, which are then used as the LDP transport
addresses and router IDs. MPLS forwarding and LDP are enabled on the
interface connecting to the network.

```none
set protocols ospf area 0 network '192.0.2.1/32'
set protocols ospf area 0 network '192.0.2.4/31'
set protocols ospf parameters router-id '192.0.2.1'
set protocols mpls interface 'eth1'
set protocols mpls ldp discovery transport-ipv4-address '192.0.2.1'
set protocols mpls ldp interface 'eth1'
set protocols mpls ldp interface 'lo'
set protocols mpls ldp router-id '192.0.2.1'
set interfaces ethernet eth1 address '192.0.2.5/31'
set interfaces loopback lo address '192.0.2.1/32'
```

```{note}
This example assumes a transit (P-router) role: MPLS forwarding is
enabled on the transit interface only, not on the loopback. If the
router needs to terminate MPLS-encapsulated traffic on its loopback
(PE-router role), also configure `set protocols mpls interface 'lo'`.
```

Apply the same configuration on the LDP peer (using its own loopback and
transit interface addresses) to establish a basic LDP session.
