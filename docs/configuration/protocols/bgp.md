---
myst:
  html_meta:
    description: |
      BGP is the path-vector exterior gateway protocol used to exchange
      routing and reachability information between autonomous systems on
      the internet.
    keywords: bgp, ebgp, ibgp, asn, route-reflector, confederation, peer-group
---

(bgp)=

# BGP

Border Gateway Protocol (BGP) is the path-vector exterior gateway protocol
used to exchange routing and reachability information between
{abbr}`ASs (Autonomous Systems)` on the Internet. BGP-4, the current
version, is specified in
[RFC 4271](https://datatracker.ietf.org/doc/html/rfc4271). Multiprotocol
extensions to BGP, which allow it to carry routing information for address
families beyond IPv4 unicast, are defined in
[RFC 4760](https://datatracker.ietf.org/doc/html/rfc4760).


## Basic concepts

### Autonomous systems

An {abbr}`AS (Autonomous System)` is a connected group of IP prefixes
managed by one or more network operators under a single, clearly defined
routing policy
([RFC 1930](https://datatracker.ietf.org/doc/html/rfc1930)).

Every AS is identified by an {abbr}`ASN (Autonomous System Number)`. ASNs
were originally two-byte values (1-65535), with the range 64512-65534
reserved for private use
([RFC 6996](https://datatracker.ietf.org/doc/html/rfc6996)) and prohibited
on the global Internet. The two-byte pool has since been exhausted, so
regional Internet registries now allocate four-byte ASNs (1-4,294,967,295) by
default, as defined in
[RFC 6793](https://datatracker.ietf.org/doc/html/rfc6793).

ASNs are essential elements of BGP. As a path-vector protocol, BGP records
the chain of ASNs a route has crossed in the AS_PATH attribute and uses
that chain both as a metric in best path selection (shorter AS_PATH wins,
other criteria being equal) and as a loop-detection mechanism.

### Address families

Multiprotocol BGP extensions enable BGP to carry routing information for
multiple network-layer protocols. Each address family is identified by an
{abbr}`AFI (Address Family Identifier)`/
{abbr}`SAFI (Subsequent Address Family Identifier)`
pair: the AFI names the network-layer protocol (IPv4, IPv6, etc.), and the
SAFI names the route type (unicast, multicast, MPLS-labeled, VPN, etc.).

VyOS supports IPv4 and IPv6 unicast, multicast, labeled unicast, VPN
(MPLS L3VPN), and flowspec address families, plus the L2VPN-EVPN and
BGP Link-State families. This document covers configuration of the IPv4
and IPv6 unicast address families, which are the most common in
inter-domain routing.

### Route selection

FRR's BGP implementation selects routes by applying the following decision
criteria, in order from top to bottom, until one is applicable.

1. **Weight check:** Prefer the route with the higher local weight.
2. **Local preference check:** Prefer the route with the higher
   LOCAL_PREF.
3. **Local route check:** Prefer locally originated routes (statics,
   aggregates, redistributed) over received routes.
4. **AS path length check:** Prefer the route with the shortest AS_PATH
   length.
5. **Origin check:** Prefer the route with the lowest origin type
   (IGP < EGP < Incomplete).
6. **MED check:** When multiple routes are received from the same
   neighboring AS, prefer the route with the lowest
   {abbr}`MED (Multi-Exit Discriminator)` value.
7. **External check:** Prefer the route received from an external (eBGP)
   peer over routes received from other types of peers.
8. **IGP cost check:** Prefer the route with the lower IGP cost to the
   next hop.
9. **Multi-path check:** If multi-path routing is enabled, check whether the
   routes not yet distinguished in preference may be considered equal. If
   `bestpath as-path multipath-relax` is set, all such routes are
   considered equal; otherwise, routes received via iBGP with identical
   AS_PATHs, or routes received from eBGP neighbors in the same AS, are
   considered equal.
10. **Already-selected external check:** When both routes are received
    from eBGP peers, prefer the route that was already selected. This
    check is skipped if `bestpath compare-routerid` is configured. It can
    prevent some cases of route oscillation.
11. **Router ID check:** Prefer the route with the lowest router ID. If
    the route has an ORIGINATOR_ID attribute (set during iBGP
    reflection), that value is used; otherwise, the router ID of the peer
    the route was received from is used.
12. **Cluster list length check:** Prefer the route with the shortest
    CLUSTER_LIST length. The cluster list reflects the iBGP reflection
    path the route has taken.
13. **Peer address:** Prefer the route received from the peer with the
    lowest transport-layer IP address, as a last-resort tie-breaker.

### Capability advertisement

BGP-4 originally had no mechanism for a speaker to advertise which optional
protocol features it supports. Capability advertisement, defined in
[RFC 5492](https://datatracker.ietf.org/doc/html/rfc5492), addresses this
by allowing each BGP speaker to list its supported capabilities in the
OPEN message. Capabilities cover features such as multiprotocol
extensions, route refresh, 4-byte ASN support, graceful restart, and
ADD-PATH.

By default, a BGP implementation brings up a peering with the minimal
capabilities that are common to both sides. For example, if the local
router supports both unicast and multicast and the remote router
supports only unicast, the session is established with unicast
capability only. When the two sides share no common capabilities, one
side sends an Unsupported Capability error and terminates the session.

If a peer is configured exclusively as an IPv4 unicast neighbor and no
other optional features require capability negotiation, VyOS' BGP
implementation does not send any capability advertisements.

## Configuration

### Local BGP router configuration

Configure the local BGP router with its ASN. The BGP process uses the ASN
to determine if a session is internal (iBGP) or external (eBGP).

```{cfgcmd} set protocols bgp system-as \<1-4294967294\>

**Configure the Autonomous System Number (ASN) for the local BGP router.**

This setting is mandatory. ASN 0 and ASN 4294967295 are reserved
([RFC 7607](https://datatracker.ietf.org/doc/html/rfc7607),
[RFC 7300](https://datatracker.ietf.org/doc/html/rfc7300)) and cannot be
configured.
```

Example:

```none
set protocols bgp system-as 64512
```

### Peer configuration

#### Defining peers

```{cfgcmd} set protocols bgp neighbor \<address | interface\> remote-as \<1-4294967294 | auto | external | internal\>

**Configure the ASN of the specified BGP neighbor.**

The neighbor identity can be an IPv4 address, an IPv6 address (including a
link-local address), or an interface name for unnumbered peering.

The ASN can be configured as:

- An explicit number in the range 1 to 4294967294.
- `auto`: automatically detect the neighbor's ASN from the OPEN
  message.
- `external`: reject the connection if the peer's ASN matches the
  local AS (eBGP session).
- `internal`: reject the connection if the peer's ASN differs from
  the local AS (iBGP session).
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 remote-as 64513
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> remote-as internal

**Configure the specified neighbor as an iBGP peer.**

The peer's AS number must match the locally configured `system-as`. If it
does not, the BGP peering session with this neighbor is rejected.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 remote-as internal
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> remote-as external

**Configure the specified neighbor as an eBGP peer.**

The peer's AS number must differ from the locally configured `system-as`.
If it matches, the BGP peering session with this neighbor is rejected.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 remote-as external
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> remote-as auto

**Configure a BGP neighbor whose ASN is learned from the OPEN message
this neighbor sends at session setup.**
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 remote-as auto
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> port \<1-65535\>

**Configure the TCP destination port used when initiating the BGP session
with the specified peer.**

By default, BGP uses TCP port 179 (IANA-assigned).
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 port 1179
```

```{cfgcmd} set protocols bgp neighbor \<interface\> interface source-interface \<interface\>

**Configure the local source interface used for the unnumbered BGP
session.**
```

```{note}
This command applies only when the neighbor is specified by interface
name (unnumbered peering).
```

Example:

```none
set protocols bgp neighbor eth1 interface source-interface eth1
```

```{cfgcmd} set protocols bgp neighbor \<interface\> interface v6only remote-as \<1-4294967294 | auto | external | internal\>

**Configure an IPv6 link-local-only unnumbered peering on the specified
interface and set the neighbor's ASN.**

With `v6only`, the BGP session is established over the IPv6 link-local
address of the interface without requiring any globally routable
address on either side.

The ASN can be configured as:

- An explicit number in the range 1 to 4294967294.
- `auto`: automatically detect the neighbor's ASN from the OPEN
  message.
- `external`: Any non-local ASN, treated as eBGP.
- `internal`: The same ASN as the local router, treated as iBGP.
```

Example:

```none
set protocols bgp neighbor eth1 interface v6only remote-as external
```

```{cfgcmd} set protocols bgp neighbor \<interface\> interface v6only peer-group \<name\>

**Assign an IPv6-link-local-only unnumbered peering on the specified
interface to a peer group.**

The unnumbered peering inherits all parameters from the peer group.
```

```{note}
The peer group must already be configured.
```

Example:

```none
set protocols bgp neighbor eth1 interface v6only peer-group FABRIC
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> local-role \<customer | peer | provider | rs-client | rs-server\> [strict]

**Configure the local BGP role for the session
([RFC 9234](https://datatracker.ietf.org/doc/html/rfc9234)).**

Each side advertises its role via the BGP Role capability, and the
following two roles form a valid pairing:

- Provider <-> Customer
- RS-Server <-> RS-Client
- Peer <-> Peer

If the roles do not pair correctly, the session is rejected with a Role
Mismatch notification.

When `strict` is set, the session requires the neighbor to advertise its
role. If the neighbor does not include the BGP Role capability, the
session is rejected. Enable this option when you want to be sure the
other side is also role-configured.

Once the local role is set, the BGP daemon automatically applies the
{abbr}`OTC (Only-to-Customer)` attribute to detect and prevent route
leaks:

- Routes sent to a Customer, RS-Client, or Peer are tagged with OTC.
- Routes already carrying OTC are not sent back up to a Provider,
  RS-Server, or Peer.
- Between two peers, a received route with OTC is accepted only if the
  OTC value equals the peer's ASN.
- Routes received from a Customer or RS-Client that already carry OTC are
  treated as route leaks and rejected.

No extra policy configuration is needed; the rules apply automatically.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 local-role customer strict
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> shutdown

**Administratively disable the BGP session with the specified peer.**

To re-enable the session, use the `delete` form of this command.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 shutdown
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> description \<text\>

**Configure a free-form description for the specified peer.**

The description may be up to 255 characters.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 description 'Upstream provider'
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> update-source \<address | interface\>

**Configure the source IP address used by the local BGP speaker when
opening the TCP connection to the specified neighbor.**

The source IP address can be specified either as an IP address or as an
interface name.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 update-source 192.0.2.1
```

#### Capability negotiation

```{cfgcmd} set protocols bgp neighbor \<address | interface\> capability dynamic

**Enable Dynamic Capability negotiation with the specified peer.**

This enables updating active capabilities during an established BGP
session without resetting the session.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 capability dynamic
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> capability extended-nexthop

**Enable the Extended Next Hop capability
([RFC 8950](https://datatracker.ietf.org/doc/html/rfc8950)) negotiation
with the specified peer.**

When the BGP session runs over an IPv6 link-local address, this capability
is enabled automatically. When the session runs over an IPv6 global
address, enabling this capability allows BGP to install IPv4 routes with
IPv6 next hops, which is useful when no IPv4 addresses are configured on
the transit interfaces.
```

Example:

```none
set protocols bgp neighbor 2001:db8::2 capability extended-nexthop
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> capability software-version

**Configure BGP to advertise the Software Version capability to the
specified peer.**

This causes the local router to include the name and version of the
software that implements BGP in the OPEN message. It is sent for
purely informational purposes and does not affect BGP behavior.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 capability software-version
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> disable-capability-negotiation

**Suppress sending capability advertisements as OPEN message optional
parameters to the specified peer.**

The session is established using only the basic BGP-4 feature set, as if
capabilities had never been introduced.
```

```{note}
To use the locally configured capabilities regardless of what the peer
advertises, use `override-capability` instead.
```

```{note}
Suppressing capability negotiation disables every BGP feature that
depends on capability exchange, including BGP unnumbered, hostname
support, 4-byte ASNs, ADD-PATH, Route Refresh, ORF, Dynamic Capabilities,
and Graceful Restart. Use this option only when interoperating with a
peer that cannot accept capabilities.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 disable-capability-negotiation
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> override-capability

**Configure the session with the specified peer to use the locally
configured capabilities, ignoring capabilities advertised by the peer.**
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 override-capability
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> strict-capability-match

**Configure the session with the specified peer to require an exact
match between the local and remote capability sets.**

If the two sets differ, the router sends an Unsupported Capability
notification and resets the connection.

If the peer does not implement capability advertisement at all, use
`disable-capability-negotiation` to suppress local advertisement.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 strict-capability-match
```

#### Peer parameters

```{cfgcmd} set protocols bgp neighbor \<address | interface\> address-family \<ipv4-unicast | ipv6-unicast\> allowas-in number \<1-10\>

**Configure the session with the specified peer to accept incoming routes
whose AS_PATH contains the local AS, up to the given number of
occurrences.**

This is useful when the same ASN is reused across multiple sites that
cannot be connected directly. The `number` parameter (1-10) sets the
maximum allowed occurrences of the local AS in the AS_PATH.
```

```{note}
This option applies only to eBGP peers and cannot be applied to peer
groups.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 address-family ipv4-unicast allowas-in number 2
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> address-family \<ipv4-unicast | ipv6-unicast\> as-override

**Configure the session with the specified peer to replace the peer's
ASN in the AS_PATH of advertised routes with the local ASN.**

This is typically used on a {abbr}`PE (Provider Edge)` router to replace
the incoming customer ASN in advertisements to a connected
{abbr}`CE (Customer Edge)`, so customers can reuse the same ASN across
all their sites.
```

```{note}
This option applies only to eBGP peers.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 address-family ipv4-unicast as-override
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> address-family \<ipv4-unicast | ipv6-unicast\> attribute-unchanged \<as-path | med | next-hop\>

**Configure BGP to advertise the specified path attribute (`as-path`,
`med`, or `next-hop`) to the peer or peer group unchanged.**
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 address-family ipv4-unicast attribute-unchanged next-hop
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> address-family \<ipv4-unicast | ipv6-unicast\> maximum-prefix \<1-4294967295\>

**Configure the maximum number of prefixes that the local BGP speaker
will accept from the specified peer.**

If the number of received prefixes exceeds this limit, the BGP session is
torn down.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 address-family ipv4-unicast maximum-prefix 1000
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> address-family \<ipv4-unicast | ipv6-unicast\> nexthop-self

**Configure the local BGP speaker to advertise itself as the NEXT_HOP
for all routes advertised to the specified peer.**

By default, the local speaker rewrites NEXT_HOP to its own IP address
only when advertising to an eBGP peer and preserves the received NEXT_HOP
when advertising to an iBGP peer. This option overrides the iBGP default.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 address-family ipv4-unicast nexthop-self
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> address-family \<ipv4-unicast | ipv6-unicast\> nexthop-self force

**Force the local route reflector to set itself as the NEXT_HOP on
routes reflected to its route-reflector clients.**

By default, a route reflector preserves the NEXT_HOP of reflected
routes. This option overrides that behavior for the specified peer,
which must be configured as a route-reflector client for the option to
take effect.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 address-family ipv4-unicast nexthop-self force
```
<!--
`nexthop-local unchanged` does not work as expected on the live VyOS 
```{cfgcmd} set protocols bgp neighbor \<address | interface\> address-family ipv6-unicast nexthop-local unchanged
-->

```{cfgcmd} set protocols bgp neighbor \<address | interface\> address-family \<ipv4-unicast | ipv6-unicast\> remove-private-as

**Configure the local BGP speaker to strip private ASNs from the AS_PATH
of routes advertised to the specified eBGP peer.**

Private ASNs are removed only if the AS_PATH consists entirely of
private ASNs. If any public ASN is present in the path, no private ASN
is removed.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 address-family ipv4-unicast remove-private-as
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> address-family \<ipv4-unicast | ipv6-unicast\> remove-private-as all

**Configure the local BGP speaker to strip all private ASNs from the
AS_PATH of routes advertised to the specified eBGP peer.**

Unlike `remove-private-as` without `all`, this option removes private
ASNs unconditionally — even when public ASNs are also present in the
path.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 address-family ipv4-unicast remove-private-as all
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> address-family \<ipv4-unicast | ipv6-unicast\> soft-reconfiguration inbound

**Enable inbound soft reconfiguration for the specified peer and address
family.**

When enabled, the router stores incoming updates from the peer unmodified
before any inbound policy is applied. If the inbound policy is changed,
the stored updates are reprocessed locally to produce a new inbound
state, so the session does not need to be cleared to apply policy
changes.
```

```{note}
Storing updates requires memory, and enabling inbound soft
reconfiguration for multiple neighbors can significantly increase memory
usage.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 address-family ipv4-unicast soft-reconfiguration inbound
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> address-family \<ipv4-unicast | ipv6-unicast\> weight \<1-65535\>

**Configure the default weight applied to routes received from the
specified peer.**

Weight is a purely local attribute. It is never carried in BGP messages and is not
advertised to other peers. Among the best path decision criteria, it is
considered before everything else, and the highest weight wins.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 address-family ipv4-unicast weight 100
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> advertisement-interval \<0-600\>

**Configure the minimum interval, in seconds, between successive route
advertisements sent to the specified peer for the same destination.**
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 advertisement-interval 5
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> disable-connected-check

**Allow eBGP sessions to establish regardless of the number of hops
between peers.**

By default, eBGP packets are sent with a TTL of 1, which precludes
sourcing from a non-connected address. This
option bypasses the check.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 disable-connected-check
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> address-family \<ipv4-unicast | ipv6-unicast\> disable-send-community \<extended | standard\>

**Disable sending the specified community attributes to the peer.**

By default, both standard and extended community attributes are sent.
```

Example:

```none
set protocols bgp neighbor 192.0.2.1 address-family ipv4-unicast disable-send-community standard
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> ebgp-multihop \<1-255\>

**Allow an eBGP session with a peer that is not directly connected by
raising the TTL of outbound BGP packets to the specified value.**

By default, eBGP packets are sent with TTL 1, so a peer more than one hop
away is unreachable unless this option is set. Accepted values are
1-255, where 1 is equivalent to the default (single-hop) behavior.
```

```{note}
This command is mutually exclusive with `ttl-security hops`.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 ebgp-multihop 5
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> local-as \<1-4294967294\> [no-prepend [replace-as]]

**Configure an alternate local ASN for the BGP session with the specified
peer. This command applies only to eBGP peers.**

Without modifiers, the `local-as` is prepended to the received AS_PATH
when receiving updates from the peer, and to the outgoing AS_PATH (on
top of the router's real ASN) when sending routes to the peer.

With `no-prepend`, the `local-as` is not prepended to the AS_PATH of
incoming updates from the peer.

With `replace-as`, only the `local-as` is prepended to outgoing updates
to the peer; the router's real ASN is omitted. The `replace-as` modifier
requires `no-prepend` and cannot be used on its own.
```

```{note}
This command applies only to eBGP peers.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 local-as 64600 no-prepend replace-as
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> passive

**Configure the local BGP speaker to only accept inbound TCP connections
from the specified peer and never initiate an outbound connection.**
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 passive
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> password \<text\>

**Configure a TCP MD5 authentication password for the session with the
specified peer.**

Both sides of the session must be configured with the same password for
the connection to be established.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 password mysharedsecret
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> ttl-security hops \<1-254\>

**Enable the {abbr}`GTSM (Generalized TTL Security Mechanism)` on the
session with the specified peer, as defined in
[RFC 5082](https://datatracker.ietf.org/doc/html/rfc5082).**

When enabled, outbound BGP packets are sent with TTL 255, and inbound
packets are accepted only from peers within the configured number of
hops.
```

```{note}
This command is mutually exclusive with `ebgp-multihop`.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 ttl-security hops 1
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> bfd [profile \<name\>]

**Enable {abbr}`BFD (Bidirectional Forwarding Detection)` on the session
with the specified peer.**

When BFD declares the path to the peer down, the BGP session is reset
immediately rather than waiting for the BGP hold timer to expire.
Optionally, a BFD profile (configured under `set protocols bfd profile`)
can be applied to control detection timers and other parameters. Without
a profile, the default BFD parameters apply.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 bfd profile FAST-LINK
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> bfd check-control-plane-failure

**Configure BGP to set and inspect the BFD C-bit (Control Plane
Independent bit) for the session with the specified peer. This option is
intended for use with BGP Graceful Restart.**

The local router sets the C-bit on outgoing BFD packets and checks it on
incoming packets to distinguish between BFD failures caused by
control plane disruptions and those caused by data plane failures.

Consequently, a BFD-down event caused by a control plane restart on the
peer does not tear down the BGP session if the peer is still forwarding
traffic.

Without this option, every BFD-down event resets the BGP session.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 bfd check-control-plane-failure
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> bfd strict

**Require BFD to be up before the BGP session with the specified peer
reaches the Established state (strict-mode BFD).**

Without strict mode, BGP establishes the session independently, and BFD
only monitors it once both are up. With strict mode, BGP delays session
establishment until BFD declares the path to the peer up. This prevents
the BGP session from being established over a path that BFD will
subsequently report as down.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 bfd strict
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> bfd strict hold-time \<1-4294967295\>

**Configure how long, in seconds, BGP waits before tearing down the
session after BFD reports the path down.**

This timer applies only when the BGP hold-time is `0`. Otherwise, a
BFD-down event causes immediate BGP session teardown.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 bfd strict hold-time 30
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> enforce-first-as

**Require that the first ASN in the AS_PATH of every UPDATE received
from the specified eBGP peer matches that peer's ASN.**

If the first ASN does not match, the UPDATE is rejected.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 enforce-first-as
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> path-attribute discard \<1-255\>

**Drop the specified BGP path attribute from incoming UPDATE messages
received from this peer.**

The UPDATE is then processed without that attribute. The number
`<1-255>` is the path attribute type code per the IANA BGP Path
Attributes registry.

Multiple attributes can be discarded by issuing the command repeatedly
with different numbers.
```

```{note}
The following attributes cannot be discarded: 1 (ORIGIN), 2 (AS_PATH),
3 (NEXT_HOP), 4 (MED), 8 (COMMUNITIES), 14 (MP_REACH_NLRI),
15 (MP_UNREACH_NLRI), and 16 (EXTENDED_COMMUNITIES).
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 path-attribute discard 128
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> path-attribute treat-as-withdraw \<1-255\>

**Treat any incoming UPDATE that contains the specified BGP path
attribute as a withdrawal of the routes it carries.**

Use this to recover gracefully when a peer advertises malformed or
unexpected attributes that would otherwise tear down the session.
```

```{note}
The following attributes cannot be specified: 1 (ORIGIN), 2 (AS_PATH),
3 (NEXT_HOP), 4 (MED), 8 (COMMUNITIES), 14 (MP_REACH_NLRI),
15 (MP_UNREACH_NLRI), and 16 (EXTENDED_COMMUNITIES).
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 path-attribute treat-as-withdraw 32
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> address-family \<ipv4-unicast | ipv6-unicast\> maximum-prefix-out \<1-4294967295\>

**Configure the maximum number of prefixes the local BGP speaker will
advertise to the specified peer.**

Unlike `maximum-prefix`, which limits inbound prefixes and tears down
the session when the limit is exceeded, `maximum-prefix-out` simply
stops sending additional prefixes outbound once the limit is reached.
The session remains up.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 address-family ipv4-unicast maximum-prefix-out 5000
```

#### Peer groups

Peer groups serve two purposes. First, they simplify configuration:
parameters applied to a group are inherited by all its members, so
common settings have to be configured only once and in one place.
Second, they improve scalability by computing outgoing update
information once per group rather than for each group member.

As a side effect, a route advertised by one group member is
re-advertised to all group members, including the sender itself. The
originator identifier attribute is included in such updates so that the
originating peer can recognize its own routes and ignore them.

Peers not explicitly assigned to any peer group are treated as members
of the default peer group and share updates with that group.

```{cfgcmd} set protocols bgp peer-group \<name\>

**Configure a BGP peer group.**

A peer group accepts the same parameters that can be applied to
individual neighbors.
```

```{note}
A parameter applied directly to an individual neighbor IP address
overrides the same parameter applied to a peer group that includes that
neighbor.
```

Example:

```none
set protocols bgp peer-group UPSTREAM
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> peer-group \<name\>

**Assign the specified neighbor to a peer group.**

The neighbor inherits all parameters configured on the peer group.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 peer-group UPSTREAM
```

### Network advertisement configuration

```{cfgcmd} set protocols bgp address-family \<ipv4-unicast | ipv6-unicast\> network \<prefix\>

**Configure BGP to originate and advertise the specified IPv4 or IPv6
prefix.**
```

```{note}
By default, BGP advertises a prefix configured via the `network` statement
even if the prefix is not present in the routing table. To make BGP verify
that the prefix exists in the RIB before advertising it (the behavior of
some other vendors' routers), enable the `network-import-check` option.
```

Example:

```none
set protocols bgp address-family ipv4-unicast network 198.51.100.0/24
```

```{cfgcmd} set protocols bgp address-family \<ipv4-unicast | ipv6-unicast\> network \<prefix\> route-map \<name\>

**Apply a route-map to set attributes on, or suppress, the locally
originated network route.**

The `route-map` is evaluated when BGP originates the route and can set
communities, MED, LOCAL_PREF, or other path attributes on the originated
route. If the `route-map` denies the prefix, BGP does not originate the
route.
```

Example:

```none
set protocols bgp address-family ipv4-unicast network 198.51.100.0/24 route-map SET-COMMUNITY
```

```{cfgcmd} set protocols bgp address-family ipv6-unicast network \<prefix\> path-limit \<0-255\>

**Configure the AS_PATHLIMIT attribute on the originated IPv6 route.**

The AS_PATHLIMIT attribute sets an upper bound on the number of ASes the
route may traverse before being dropped. A value of `0` disables the
limit.
```

Example:

```none
set protocols bgp address-family ipv6-unicast network 2001:db8::/48 path-limit 8
```

```{cfgcmd} set protocols bgp parameters network-import-check

**Configure BGP to verify that a prefix defined by the `network` command
exists in the routing table (RIB) before it is advertised to BGP peers.**
```

Example:

```none
set protocols bgp parameters network-import-check
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> address-family \<ipv4-unicast | ipv6-unicast\> default-originate [route-map \<name\>]

**Configure BGP to advertise a default route (`0.0.0.0/0` or `::/0`) to
the specified peer.**

By default, VyOS does not advertise a default route even if one is
present in the routing table.

When a `route-map` is used, the default route is only advertised if the
conditions specified in the `route-map` are met.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 address-family ipv4-unicast default-originate
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> address-family \<ipv4-unicast | ipv6-unicast\> addpath-tx-all

**Configure BGP to use ADD-PATH to advertise every known path for each
prefix to the specified peer, not only the best path.**
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 address-family ipv4-unicast addpath-tx-all
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> address-family \<ipv4-unicast | ipv6-unicast\> addpath-tx-per-as

**Configure BGP to use ADD-PATH to advertise the best path per
neighboring AS to the specified peer.**
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 address-family ipv4-unicast addpath-tx-per-as
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> address-family \<ipv4-unicast | ipv6-unicast\> conditionally-advertise advertise-map \<name\>

**Configure BGP to advertise the prefixes allowed by the specified
`route-map` only when the `exist-map` or `non-exist-map` condition is
met.**
```

```{note}
This option must be used together with either
`conditionally-advertise exist-map` or
`conditionally-advertise non-exist-map`, as `advertise-map` alone does
not enable conditional advertisement.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 address-family ipv4-unicast conditionally-advertise advertise-map BACKUP-ROUTES
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> address-family \<ipv4-unicast | ipv6-unicast\> conditionally-advertise exist-map \<name\>

**Specify the route-map that defines the trigger condition for
`advertise-map`.**

The condition is met when at least one prefix allowed by the specified
`route-map` is present in the BGP RIB.
```

```{note}
`exist-map` and `non-exist-map` are mutually exclusive.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 address-family ipv4-unicast conditionally-advertise exist-map AGGREGATE-PRESENT
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> address-family \<ipv4-unicast | ipv6-unicast\> conditionally-advertise non-exist-map \<name\>

**Specify the route-map that defines the trigger condition for
`advertise-map`.**

The condition is met when no prefix allowed by the specified `route-map`
is present in the BGP RIB.
```

```{note}
`exist-map` and `non-exist-map` are mutually exclusive.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 address-family ipv4-unicast conditionally-advertise non-exist-map PRIMARY-UP
```

### Route aggregation configuration

```{cfgcmd} set protocols bgp address-family \<ipv4-unicast | ipv6-unicast\> aggregate-address \<prefix\>

**Configure BGP to advertise an aggregate route for the specified IPv4
or IPv6 prefix.**

By default, BGP also advertises more-specific routes that fall within
the aggregate.
```

Example:

```none
set protocols bgp address-family ipv4-unicast aggregate-address 198.51.100.0/22
```

```{cfgcmd} set protocols bgp address-family \<ipv4-unicast | ipv6-unicast\> aggregate-address \<prefix\> as-set

**Configure BGP to advertise an aggregate route with an AS_SET segment
in its AS_PATH for the specified IPv4 or IPv6 prefix.**

The AS_SET contains the AS numbers from the AS_PATHs of all contributing
more specific routes.
```

Example:

```none
set protocols bgp address-family ipv4-unicast aggregate-address 198.51.100.0/22 as-set
```

```{cfgcmd} set protocols bgp address-family \<ipv4-unicast | ipv6-unicast\> aggregate-address \<prefix\> summary-only

**Configure BGP to advertise only the aggregate route and suppress
advertisement of more-specific contributing routes.**
```

Example:

```none
set protocols bgp address-family ipv4-unicast aggregate-address 198.51.100.0/22 summary-only
```

```{cfgcmd} set protocols bgp address-family \<ipv4-unicast | ipv6-unicast\> aggregate-address \<prefix\> route-map \<name\>

**Apply a `route-map` to set or modify BGP path attributes on the aggregate
route before it is advertised.**

Attribute changes apply only to the aggregate route and do not affect more
specific contributing routes. Use the `route-map` to set communities, MED,
LOCAL_PREF, or other attributes carried by the summary advertisement.
```

Example:

```none
set protocols bgp address-family ipv4-unicast aggregate-address 198.51.100.0/22 route-map AGGREGATE-ATTRS
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> address-family \<ipv4-unicast | ipv6-unicast\> unsuppress-map \<name\>

**Apply a route-map to selectively advertise to the specified peer
more specific routes that were suppressed by the `summary-only` option.**
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 address-family ipv4-unicast unsuppress-map UNSUPPRESS-MORE-SPECIFIC
```

### Redistribution configuration

```{cfgcmd} set protocols bgp address-family ipv4-unicast redistribute \<babel | connected | isis | kernel | nhrp | ospf | rip | static\>

**Redistribute IPv4 unicast routes from the specified source into BGP.**
```

Example:

```none
set protocols bgp address-family ipv4-unicast redistribute connected
```

```{cfgcmd} set protocols bgp address-family ipv4-unicast redistribute table \<id\>

**Redistribute IPv4 routes from the specified non-main kernel routing
table (identified by `<id>`, configured under
`set protocols static table`) into the BGP IPv4 unicast address family.**
```

Example:

```none
set protocols bgp address-family ipv4-unicast redistribute table 100
```

```{cfgcmd} set protocols bgp address-family ipv6-unicast redistribute \<babel | connected | isis | kernel | nhrp | ospfv3 | ripng | static\>

**Redistribute IPv6 unicast routes from the specified source into BGP.**
```

Example:

```none
set protocols bgp address-family ipv6-unicast redistribute connected
```

```{cfgcmd} set protocols bgp address-family ipv6-unicast redistribute table \<id\>

**Redistribute IPv6 routes from the specified non-main kernel routing
table (identified by `<id>`, configured under
`set protocols static table`) into the BGP IPv6 unicast address family.**
```

Example:

```none
set protocols bgp address-family ipv6-unicast redistribute table 100
```

```{cfgcmd} set protocols bgp address-family ipv4-unicast redistribute \<babel | connected | isis | kernel | nhrp | ospf | rip | static\> metric \<1-4294967295\>

**Redistribute IPv4 unicast routes from the specified source into BGP,
setting the MED attribute on the redistributed routes to the specified
value.**
```

Example:

```none
set protocols bgp address-family ipv4-unicast redistribute static metric 100
```

```{cfgcmd} set protocols bgp address-family ipv4-unicast redistribute table \<id\> metric \<1-4294967295\>

**Redistribute IPv4 routes from the specified non-main kernel routing
table into the BGP IPv4 unicast address family, setting the MED attribute
on the redistributed routes to the specified value.**
```

Example:

```none
set protocols bgp address-family ipv4-unicast redistribute table 100 metric 100
```

```{cfgcmd} set protocols bgp address-family ipv6-unicast redistribute \<babel | connected | isis | kernel | nhrp | ospfv3 | ripng | static\> metric \<1-4294967295\>

**Redistribute IPv6 unicast routes from the specified source into BGP,
setting the MED attribute on the redistributed routes to the specified
value.**
```

Example:

```none
set protocols bgp address-family ipv6-unicast redistribute static metric 100
```

```{cfgcmd} set protocols bgp address-family ipv6-unicast redistribute table \<id\> metric \<1-4294967295\>

**Redistribute IPv6 routes from the specified non-main kernel routing
table into the BGP IPv6 unicast address family, setting the MED attribute
on the redistributed routes to the specified value.**
```

Example:

```none
set protocols bgp address-family ipv6-unicast redistribute table 100 metric 100
```

```{cfgcmd} set protocols bgp address-family ipv4-unicast redistribute \<babel | connected | isis | kernel | nhrp | ospf | rip | static\> route-map \<name\>

**Apply a route-map to filter and modify IPv4 unicast routes
redistributed from the specified source.**
```

Example:

```none
set protocols bgp address-family ipv4-unicast redistribute static route-map FILTER-STATIC
```

```{cfgcmd} set protocols bgp address-family ipv4-unicast redistribute table \<id\> route-map \<name\>

**Apply a `route-map` to filter and modify IPv4 routes redistributed from
the specified non-main kernel routing table into the BGP IPv4 unicast
address family.**
```

Example:

```none
set protocols bgp address-family ipv4-unicast redistribute table 100 route-map FILTER-STATIC
```

```{cfgcmd} set protocols bgp address-family ipv6-unicast redistribute \<babel | connected | isis | kernel | nhrp | ospfv3 | ripng | static\> route-map \<name\>

**Apply a `route-map` to filter and modify IPv6 unicast routes
redistributed from the specified source.**
```

Example:

```none
set protocols bgp address-family ipv6-unicast redistribute static route-map FILTER-STATIC
```

```{cfgcmd} set protocols bgp address-family ipv6-unicast redistribute table \<id\> route-map \<name\>

**Apply a `route-map` to filter and modify IPv6 routes redistributed from
the specified non-main kernel routing table into the BGP IPv6 unicast
address family.**
```

Example:

```none
set protocols bgp address-family ipv6-unicast redistribute table 100 route-map FILTER-STATIC
```

### General configuration

#### Common parameters

```{cfgcmd} set protocols bgp parameters allow-martian-nexthop

**Configure BGP to accept UPDATE messages whose NEXT_HOP attribute is
a Martian address.**

A Martian address is one that cannot legitimately appear as a BGP
next hop, such as an all-zero or unspecified address (e.g., `0.0.0.0/8`
or `::`), a loopback address (e.g., `127.0.0.0/8` or `::1`), a
multicast address, or an address of the local router itself.

By default, BGP rejects such routes.
```

Example:

```none
set protocols bgp parameters allow-martian-nexthop
```

```{cfgcmd} set protocols bgp parameters router-id \<id\>

**Configure the BGP router-ID as a 32-bit identifier in IPv4 address
notation.**

If no router ID is configured, VyOS uses the highest IPv4 address on the
loopback interface. If no loopback address is configured, VyOS uses the
highest IPv4 address on any other interface.
```

Example:

```none
set protocols bgp parameters router-id 192.0.2.1
```

```{cfgcmd} set protocols bgp address-family \<ipv4-unicast | ipv6-unicast\> maximum-paths \<ebgp | ibgp\> \<1-256\>

**Configure the maximum number of parallel BGP paths that can be
installed for the same destination
({abbr}`ECMP (Equal-Cost Multi-Path)`).**

For paths to be considered equal for multipath purposes, the following
must match: weight, local preference, AS_PATH content and length, origin
code, MED, and IGP metric. Each path must also have a distinct next hop
IP address.
```

Example:

```none
set protocols bgp address-family ipv4-unicast maximum-paths ebgp 4
```

```{cfgcmd} set protocols bgp parameters no-hard-administrative-reset

**Suppress sending a Hard Reset CEASE notification for Administrative
Reset events.**

When this option is enabled, routes are retained across an administrative
reset, provided the Graceful Restart Notification capability has been
negotiated between the peers.
```

Example:

```none
set protocols bgp parameters no-hard-administrative-reset
```

```{cfgcmd} set protocols bgp parameters log-neighbor-changes

**Configure BGP to log neighbor up/down state changes and reset reasons
to syslog.**
```

Example:

```none
set protocols bgp parameters log-neighbor-changes
```

```{cfgcmd} set protocols bgp parameters no-client-to-client-reflection

**Disable route reflection between route-reflector clients on this
router.**

By default, a route reflector reflects routes received from one client
to all other clients. If the clients are fully meshed with iBGP, this
reflection is unnecessary and can be disabled with this option.
```

Example:

```none
set protocols bgp parameters no-client-to-client-reflection
```

```{cfgcmd} set protocols bgp parameters no-fast-external-failover

**Disable immediate session reset when the connected link to an eBGP
peer goes down.**

By default, BGP resets the session immediately on link-down events. With
this option set, the session is held until the hold timer expires.
```

Example:

```none
set protocols bgp parameters no-fast-external-failover
```

```{cfgcmd} set protocols bgp parameters no-ipv6-auto-ra

**Suppress automatic IPv6 Router Advertisement (RA) on interfaces used
for BGP.**

By default, FRR sends RAs on an interface when its BGP session has
negotiated the Extended Next Hop capability, or when a BGP neighbor is
configured by interface name (Unnumbered BGP).
```

```{note}
Setting this option may prevent Unnumbered BGP sessions from
establishing.
```

Example:

```none
set protocols bgp parameters no-ipv6-auto-ra
```

```{cfgcmd} set protocols bgp listen range \<prefix\> peer-group \<name\>

**Configure BGP to accept inbound connections from any source IP address
within the specified prefix and associate them with the specified peer
group.**

This removes the need to statically define each BGP neighbor. When a TCP
connection and OPEN message arrive from a source IP address within the
specified prefix, the local router accepts the session using the peer
group's parameters.
```

```{note}
For each listen range, the referenced peer group must exist before the
configuration is committed.
```

Example:

```none
set protocols bgp listen range 192.0.2.0/24 peer-group UPSTREAM
```

```{cfgcmd} set protocols bgp listen limit \<1-5000\>

**Configure the maximum number of dynamic BGP neighbors the local router
will accept via configured listen ranges.**
```

Example:

```none
set protocols bgp listen limit 100
```

```{cfgcmd} set protocols bgp parameters ebgp-requires-policy

**Require an explicit policy in each direction on eBGP sessions before
exchanging routes
([RFC 8212](https://datatracker.ietf.org/doc/html/rfc8212)).**

By default, VyOS disables this RFC 8212 behavior for backward
compatibility with older VyOS versions. Enabling it brings VyOS into
compliance with the default route propagation behavior expected by
RFC 8212.
```

Example:

```none
set protocols bgp parameters ebgp-requires-policy
```

```{cfgcmd} set protocols bgp parameters labeled-unicast \<explicit-null | ipv4-explicit-null | ipv6-explicit-null\>

**Configure {abbr}`BGP-LU (BGP Labeled Unicast)` to advertise locally
originated prefixes with an explicit-null label instead of the default
implicit-null label, preserving the MPLS label at the egress.**
```

Example:

```none
set protocols bgp parameters labeled-unicast explicit-null
```
<!-- CLI path not accepted on live VyOS
```{cfgcmd} set protocols bgp parameters as-notation \<asdot | asdot+ | asplain\>

- `asplain`: Print every ASN in plain decimal. This is the default.
- `asdot`: Print ASNs greater than 65535 in dotted notation (e.g.,
  `65540` becomes `1.4`). ASNs at or below 65535 are printed in plain
  decimal.
- `asdot+`: Print every ASN in dotted notation.
```

Example:

```none
set protocols bgp parameters as-notation asdot
```
-->

```{cfgcmd} set protocols bgp parameters disable-ebgp-connected-route-check

**Allow eBGP-learned routes whose NEXT_HOP is not directly connected to
be installed in the RIB.**

By default, BGP requires the next hop of an eBGP-learned route to be
reachable through a directly connected route. This option removes
that restriction.
```

Example:

```none
set protocols bgp parameters disable-ebgp-connected-route-check
```

```{cfgcmd} set protocols bgp parameters fast-convergence

**Configure BGP to tear down its sessions immediately whenever the
local router detects that a peer has become unreachable.**

This triggers on both direct link-down events and NEXT_HOP reachability
changes signaled by the IGP.
```

Example:

```none
set protocols bgp parameters fast-convergence
```

```{cfgcmd} set protocols bgp parameters no-suppress-duplicates

**Disable suppression of duplicate UPDATE messages for routes whose
attributes have not changed.**

By default, BGP suppresses repeated advertisements of the same route
with unchanged attributes. Setting this option disables that
suppression.
```

Example:

```none
set protocols bgp parameters no-suppress-duplicates
```

```{cfgcmd} set protocols bgp parameters reject-as-sets

**Configure BGP to reject incoming UPDATE messages whose AS_PATH
contains an AS_SET or AS_CONFED_SET segment.**

AS_SET segments are deprecated for most modern deployments.
```

Example:

```none
set protocols bgp parameters reject-as-sets
```

```{cfgcmd} set protocols bgp parameters suppress-fib-pending

**Configure BGP not to advertise a route to peers until the route is
installed in the kernel forwarding table (FIB).**

This prevents the local router from advertising a route it cannot yet
forward.
```

Example:

```none
set protocols bgp parameters suppress-fib-pending
```

```{cfgcmd} set protocols bgp parameters shutdown

**Administratively shut down the entire BGP instance on this router.**

This terminates all BGP sessions belonging to this instance.
```

Example:

```none
set protocols bgp parameters shutdown
```

```{cfgcmd} set protocols bgp parameters input-queue-limit \<messages\>

**Set the BGP input queue limit for all peers during message parsing.**

Increase this only if you have the memory to handle large queues of
messages at once. The default is 10000.
```

Example:

```none
set protocols bgp parameters input-queue-limit 10000
```

```{cfgcmd} set protocols bgp parameters output-queue-limit \<messages\>

**Set the BGP output queue limit for all peers during message parsing.**

Increase this only if you have the memory to handle large queues of
messages at once. The default is 10000.
```

Example:

```none
set protocols bgp parameters output-queue-limit 10000
```

#### Graceful restart and shutdown

```{cfgcmd} set protocols bgp parameters graceful-restart stalepath-time \<1-3600\>

**Configure the maximum time, in seconds, that the local router retains
stale routes from a restarting peer.**

When a BGP peer signals Graceful Restart, the local router marks the
peer's routes as stale and continues forwarding traffic on them while
the session is down. If the peer does not complete the Graceful Restart
(re-establish the session and send the End-of-RIB marker) within
`stalepath-time`, the stale routes are removed.
```

Example:

```none
set protocols bgp parameters graceful-restart stalepath-time 360
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> graceful-restart \<enable | disable | restart-helper\>

**Configure the Graceful Restart role for the specified peer:**

- `enable`: Advertises the GR capability and allows both restart and
  helper roles.
- `disable`: Disables GR for this peer.
- `restart-helper`: Advertises only the helper role. The local router
  retains the peer's routes across a peer restart but does not advertise
  the restart capability for itself.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 graceful-restart restart-helper
```

```{cfgcmd} set protocols bgp parameters graceful-shutdown

**Configure BGP to tag all outbound routes with the GRACEFUL_SHUTDOWN
community, signaling to neighbors that they should prefer alternative
paths.**
```

Example:

```none
set protocols bgp parameters graceful-shutdown
```

#### Administrative distance

```{cfgcmd} set protocols bgp parameters distance global \<external | internal | local\> \<1-255\>

**Configure the administrative distance assigned to BGP routes of the
specified category.**

`external` covers eBGP-learned routes, `internal` covers iBGP-learned
routes, and `local` covers locally originated BGP routes.
```

Example:

```none
set protocols bgp parameters distance global external 20
```

```{cfgcmd} set protocols bgp parameters distance prefix \<subnet\> distance \<1-255\>

**Override the BGP administrative distance for routes matching the
specified prefix.**
```

```{note}
A distance value of 255 effectively disables the route. It is not
installed in the kernel forwarding table.
```

Example:

```none
set protocols bgp parameters distance prefix 198.51.100.0/24 distance 200
```

The commands above set process-wide BGP distances under `parameters
distance`. Per-address-family distances can also be configured under each
`address-family` node and override the process-wide values for routes in
that address family.

```{cfgcmd} set protocols bgp address-family \<ipv4-unicast | ipv6-unicast\> distance \<external | internal | local\> \<1-255\>

**Configure the administrative distance assigned to BGP routes of the
specified category within the selected address family.**

`external` covers eBGP-learned routes, `internal` covers iBGP-learned
routes, and `local` covers locally originated BGP routes.

Per-address-family values configured here override the corresponding
values set by `set protocols bgp parameters distance global` for that
address family.
```

Example:

```none
set protocols bgp address-family ipv4-unicast distance external 20
```

```{cfgcmd} set protocols bgp address-family \<ipv4-unicast | ipv6-unicast\> distance prefix \<subnet\> distance \<1-255\>

**Override the BGP administrative distance for routes matching the
specified prefix within the selected address family.**

Per-address-family values configured here override the corresponding
values set by `set protocols bgp parameters distance prefix` for that
address family.
```

```{note}
A distance value of 255 effectively disables the route. It is not
installed in the kernel forwarding table.
```

Example:

```none
set protocols bgp address-family ipv4-unicast distance prefix 198.51.100.0/24 distance 200
```

#### Timers

```{cfgcmd} set protocols bgp timers holdtime \<0-65535\>

**Configure the BGP hold time, in seconds.**

The default is 180 seconds. Setting the value to 0 disables the hold
timer and keepalive exchange entirely.
[RFC 4271](https://datatracker.ietf.org/doc/html/rfc4271) section 4.2
requires the Hold Time to be either 0 or at least 3 seconds; the VyOS
CLI accepts values of 1 and 2, but a session established with such a
value will not be standards-compliant.
```

Example:

```none
set protocols bgp timers holdtime 90
```

```{cfgcmd} set protocols bgp timers keepalive \<1-65535\>

**Configure the BGP keepalive interval, in seconds.**
```

Example:

```none
set protocols bgp timers keepalive 30
```

```{cfgcmd} set protocols bgp parameters minimum-holdtime \<1-65535\>

**Configure BGP to reject incoming OPEN messages from peers that
propose a hold time shorter than the specified value, in seconds.**
```

Example:

```none
set protocols bgp parameters minimum-holdtime 30
```

```{cfgcmd} set protocols bgp parameters tcp-keepalive idle \<1-65535\>

**Configure the TCP keepalive idle time, in seconds, on BGP sessions.**

Once no TCP packets have been exchanged in either direction on the BGP
session for this period, the BGP process starts sending TCP keepalive
probes.
```

```{note}
Must be set together with `tcp-keepalive interval` and
`tcp-keepalive probes`.
```

Example:

```none
set protocols bgp parameters tcp-keepalive idle 60
```

```{cfgcmd} set protocols bgp parameters tcp-keepalive interval \<1-65535\>

**Configure the interval, in seconds, between TCP keepalive probes on
BGP sessions.**

After the BGP process begins sending TCP keepalive probes (see
`tcp-keepalive idle`), subsequent probes are sent at this interval.
```

```{note}
Must be set together with `tcp-keepalive idle` and
`tcp-keepalive probes`.
```

Example:

```none
set protocols bgp parameters tcp-keepalive interval 10
```

```{cfgcmd} set protocols bgp parameters tcp-keepalive probes \<1-30\>

**Configure the maximum number of unanswered TCP keepalive probes
before the TCP connection is dropped.**
```

```{note}
Must be set together with `tcp-keepalive idle` and
`tcp-keepalive interval`.
```

Example:

```none
set protocols bgp parameters tcp-keepalive probes 5
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> timers holdtime \<0-65535\>

**Override the BGP hold time for the specified peer, in seconds.**

This option takes precedence over the process-wide `set protocols bgp
timers holdtime`. Setting the value to `0` disables the hold timer and
keepalive exchange for this peer.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 timers holdtime 30
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> timers keepalive \<1-65535\>

**Override the BGP keepalive interval for the specified peer, in
seconds.**

This option takes precedence over the process-wide `set protocols bgp
timers keepalive`.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 timers keepalive 10
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> timers connect \<0-65535\>

**Configure the BGP ConnectRetry timer for the specified peer, in
seconds.**

This is the interval the local BGP speaker waits between TCP connection
attempts to a peer that is not yet in the Established state. Setting the
value to `0` disables the ConnectRetry timer.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 timers connect 5
```

#### BGP read-only mode

```{cfgcmd} set protocols bgp parameters update-delay max-delay \<0-3600\>

**Enable BGP read-only mode after a BGP process restart or after clearing
all BGP sessions, and configure the mode's maximum delay.**

In read-only mode, BGP suspends best-path selection and does not send
routing updates to peers. The mode ends when the router receives all
expected {abbr}`EOR (End-of-RIB)` messages from BGP peers or when the
maximum delay is reached, whichever occurs first.

The router expects EOR messages from all configured BGP peers except
those that are administratively shut down. If the `establish-wait`
parameter is configured, the router waits for EOR messages only from BGP
peers that reach the Established state within the `establish-wait`
window.

By default, BGP read-only mode is disabled.
```

Example:

```none
set protocols bgp parameters update-delay max-delay 120
```

```{cfgcmd} set protocols bgp parameters update-delay establish-wait \<1-3600\>

**Configure how long the router waits for BGP peers to reach the
Established state after read-only mode begins.**

The router waits for EOR messages only from BGP peers that reach the
Established state within the `establish-wait` window. The
`establish-wait` value must not exceed the `max-delay` value.
```

```{note}
This parameter requires `max-delay` to be configured.
```

Example:

```none
set protocols bgp parameters update-delay establish-wait 90
```

#### Route dampening

When a route fails, a withdrawal update is sent across the network. When
the route returns, an advertisement is sent. A route that repeatedly
fails and returns (flaps) generates substantial protocol traffic.

Route dampening, described in
[RFC 2439](https://datatracker.ietf.org/doc/html/rfc2439), identifies
unstable routes and suppresses them. Each time a route flaps, it incurs a
penalty (1000 per flap). When the accumulated penalty exceeds the
suppress threshold, the router stops advertising the route.

The penalty decays exponentially over time (halving every half-life
interval). When it drops below the reuse threshold, the route is
unsuppressed and becomes eligible for advertisement and use again. No
route is suppressed indefinitely. The `max-suppress-time` is the upper
bound on suppression duration.

```{cfgcmd} set protocols bgp parameters dampening half-life \<1-45\>

**Configure the route dampening half-life, in minutes.**

This is the interval over which a route's accumulated penalty is halved.
```

Example:

```none
set protocols bgp parameters dampening half-life 15
```

```{cfgcmd} set protocols bgp parameters dampening re-use \<1-20000\>

**Configure the penalty threshold below which a suppressed route is
reused.**

Once the decaying penalty falls below this value, the route becomes
eligible for use and is advertised to peers again.
```

Example:

```none
set protocols bgp parameters dampening re-use 750
```

```{cfgcmd} set protocols bgp parameters dampening start-suppress-time \<1-20000\>

**Configure the penalty threshold above which a route is suppressed.**

Once a route's accumulated penalty exceeds this value, it is no longer
advertised to peers or used locally until the penalty decays below the
reuse threshold.
```

Example:

```none
set protocols bgp parameters dampening start-suppress-time 2000
```

```{cfgcmd} set protocols bgp parameters dampening max-suppress-time \<1-255\>

**Configure the maximum time, in minutes, that a route may remain
suppressed by dampening.**

Once this limit is reached, the route becomes eligible for use and
advertisement again, regardless of its remaining penalty.
```

Example:

```none
set protocols bgp parameters dampening max-suppress-time 60
```

#### Route selection configuration

```{cfgcmd} set protocols bgp parameters always-compare-med

**Configure BGP to compare the MED attribute between routes received
from different neighboring ASs during best-path selection.**

By default, MED is only compared between routes received from the same
neighboring AS.
```

```{note}
Setting this option can make path selection more predictable, but it
does not prevent MED-induced oscillation and can cause it in some
topologies.
```

Example:

```none
set protocols bgp parameters always-compare-med
```

```{cfgcmd} set protocols bgp parameters bestpath as-path confed

**Configure BGP to include the length of confederation path segments
(AS_CONFED_SEQUENCE and AS_CONFED_SET) in the AS_PATH length used during
best-path selection.**

By default, these segments are not counted.
```

Example:

```none
set protocols bgp parameters bestpath as-path confed
```

```{cfgcmd} set protocols bgp parameters bestpath as-path multipath-relax

**Configure BGP to treat paths with equal AS_PATH length but different
AS_PATH content as equal for load balancing.**

Without this option, the entire AS_PATH content must match.
```

Example:

```none
set protocols bgp parameters bestpath as-path multipath-relax
```

```{cfgcmd} set protocols bgp parameters bestpath as-path ignore

**Configure BGP to ignore AS_PATH length entirely during best-path
selection.**
```

Example:

```none
set protocols bgp parameters bestpath as-path ignore
```

```{cfgcmd} set protocols bgp parameters bestpath compare-routerid

**Configure BGP to use the lowest router ID as the tie-breaker between
otherwise-equal eBGP routes, instead of the already-selected check.**

When this option is enabled, the already-selected check is skipped. If a
route has been reflected (i.e., has an ORIGINATOR_ID attribute), that
value is used. Otherwise, the router-ID of the peer that sent the route
is used.

The advantage is that route selection becomes more deterministic. The
disadvantage is that a single low-ID router may attract traffic that
would otherwise be spread across multiple equal-cost paths. The option
can also increase the risk of MED- or IGP-induced oscillation. The exact
behavior is sensitive to the iBGP and reflection topology.
```

Example:

```none
set protocols bgp parameters bestpath compare-routerid
```

```{cfgcmd} set protocols bgp parameters bestpath med confed

**Configure BGP to consider the MED attribute when comparing routes
received via different sub-ASs within the same BGP confederation.**

By default, MED is only compared between routes received from the same
sub-AS.
```

Example:

```none
set protocols bgp parameters bestpath med confed
```

```{cfgcmd} set protocols bgp parameters bestpath med missing-as-worst

**Configure BGP to treat a missing MED attribute as the worst possible
value during best-path selection.**

By default, a missing MED is treated as 0, the best possible value.
```

Example:

```none
set protocols bgp parameters bestpath med missing-as-worst
```

```{cfgcmd} set protocols bgp parameters default local-pref \<0-4294967295\>

**Configure the default LOCAL_PREF value assigned to eBGP-learned and
locally-originated routes.**

iBGP-learned routes always carry LOCAL_PREF and are not affected.
```

Example:

```none
set protocols bgp parameters default local-pref 100
```

```{cfgcmd} set protocols bgp parameters deterministic-med

**Configure BGP to group routes by the neighboring AS (the AS the route
was received from) before comparing MED values during best-path
selection.**

When configured, BGP first selects the best route within each
neighbor-AS group and then compares those per-AS bests.
```

Example:

```none
set protocols bgp parameters deterministic-med
```

```{cfgcmd} set protocols bgp address-family ipv4-unicast network \<prefix\> backdoor

**Mark the specified IPv4 prefix as a backdoor route so that an IGP path
to it is preferred over an eBGP-learned path.**
```

Example:

```none
set protocols bgp address-family ipv4-unicast network 198.51.100.0/24 backdoor
```

```{cfgcmd} set protocols bgp parameters bestpath bandwidth \<default-weight-for-missing | ignore | skip-missing\>

**Configure how BGP uses the Link Bandwidth extended community in
weighted-ECMP load balancing:**

- `default-weight-for-missing`: Assigns a low default weight (1) to
  paths that do not carry a link bandwidth attribute.
- `ignore`: Disables weighted ECMP entirely and uses regular ECMP.
- `skip-missing`: Excludes paths without link bandwidth from ECMP when
  at least one other path carries it.
```

Example:

```none
set protocols bgp parameters bestpath bandwidth skip-missing
```

```{cfgcmd} set protocols bgp parameters bestpath peer-type multipath-relax

**Configure BGP to allow load sharing across paths learned from
different peer types (eBGP and iBGP) for the same destination.**

Without this option, multipath is restricted to peers of the same type
(eBGP-only or iBGP-only).
```

Example:

```none
set protocols bgp parameters bestpath peer-type multipath-relax
```

```{cfgcmd} set protocols bgp parameters conditional-advertisement timer \<5-240\>

**Configure the interval, in seconds, at which the BGP process
re-evaluates `conditionally-advertise` conditions.**

The default is 60 seconds.
```

Example:

```none
set protocols bgp parameters conditional-advertisement timer 30
```

### Route filtering configuration

To control and modify routing information exchanged between peers, you
can use a `route-map`, `filter-list`, `prefix-list`, or `distribute-list`.

Inbound updates are evaluated in the following order: `route-map`,
`filter-list`, then either `prefix-list` or `distribute-list`. Outbound
updates are evaluated in the following order: either `prefix-list` or
`distribute-list`, `filter-list`, then `route-map`.

```{note}
`prefix-list` and `distribute-list` are mutually exclusive. Only one of
the two can be applied to each inbound or outbound direction for a
particular neighbor.
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> address-family \<ipv4-unicast | ipv6-unicast\> distribute-list \<export | import\> \<1-65535\>

**Apply the specified `access-list` to filter routing information received
from or advertised to the specified peer.**

`export` applies the filter to outbound advertisements, and `import`
applies it to inbound updates.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 address-family ipv4-unicast distribute-list import 10
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> address-family \<ipv4-unicast | ipv6-unicast\> prefix-list \<export | import\> \<name\>

**Apply the specified `prefix-list` to filter routing information received
from or advertised to the specified peer.**

`export` applies the filter to outbound advertisements, and `import`
applies it to inbound updates.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 address-family ipv4-unicast prefix-list import PEER-IN
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> address-family \<ipv4-unicast | ipv6-unicast\> route-map \<export | import\> \<name\>

**Apply the specified `route-map` to control and modify routing
information received from or advertised to the specified peer.**

`export` applies the `route-map` to outbound advertisements, and `import`
applies it to inbound updates.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 address-family ipv4-unicast route-map import PEER-IN
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> address-family \<ipv4-unicast | ipv6-unicast\> filter-list \<export | import\> \<name\>

**Apply the specified AS-path access-list to filter routing information
received from or advertised to the specified peer.**

`export` applies the filter to outbound advertisements, and `import`
applies it to inbound updates.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 address-family ipv4-unicast filter-list import AS-PATH-IN
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> address-family \<ipv4-unicast | ipv6-unicast\> capability orf prefix-list \<receive | send\>

**Enable the {abbr}`ORF (Outbound Route Filter)` capability on the
local router and advertise it to the specified peer.**

`receive` configures the router to accept ORF filters sent by the peer
and use them to filter its own outbound updates. `send` configures the
router to push its inbound prefix-list to the peer as an ORF, so the
peer can filter its outbound updates before sending them.
```

```{note}
To use the `send` option, an inbound prefix-list must already be
configured for that peer on this router.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 address-family ipv4-unicast capability orf prefix-list send
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> solo

**Prevent the local BGP speaker from advertising prefixes learned from
the specified neighbor back to that neighbor.**
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 solo
```

```{cfgcmd} set protocols bgp neighbor \<address | interface\> address-family \<ipv4-unicast | ipv6-unicast\> route-server-client

**Configure the specified neighbor as a route-server client.**

A route server, typically deployed at internet exchange points, peers
with many participants and redistributes their routes between them
while leaving AS_PATH, NEXT_HOP, and other BGP attributes untouched.
Configuring a peer as `route-server-client` suppresses the standard
eBGP outbound rewrites of these attributes for that peer.
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 address-family ipv4-unicast route-server-client
```

### BGP scaling configuration

Within an autonomous system (AS), BGP routers form iBGP sessions. To
prevent routing loops, an iBGP speaker does not re-advertise iBGP-learned
routes to other iBGP speakers. Consequently, iBGP requires a full mesh of
sessions between all speakers, which scales poorly in large networks.

The following mechanisms allow you to eliminate the need for a full iBGP
mesh: route reflectors and confederations.

#### Route reflector configuration

{abbr}`RRs (Route Reflectors)` eliminate the need for a full iBGP mesh
between clients.

A route reflector treats its iBGP peers as either clients (whose routes
are reflected to other clients and non-clients) or non-clients (regular
iBGP peers, which still require a full mesh among themselves). The route
reflector mechanism is described in
[RFC 4456](https://datatracker.ietf.org/doc/html/rfc4456), with later
refinements to error handling in
[RFC 7606](https://datatracker.ietf.org/doc/html/rfc7606).

```{cfgcmd} set protocols bgp neighbor \<address\> address-family \<ipv4-unicast | ipv6-unicast\> route-reflector-client

**Configure the specified neighbor as a route-reflector client for the
selected address family.**
```

Example:

```none
set protocols bgp neighbor 192.0.2.2 address-family ipv4-unicast route-reflector-client
```

```{cfgcmd} set protocols bgp parameters cluster-id \<id\>

**Configure the BGP cluster-ID used by route reflectors to identify a
collection of reflectors and clients and to detect reflection loops.**

By default, the cluster-ID is set to the BGP router-ID. It can be
overridden with any 32-bit value in IPv4 address notation.
```

Example:

```none
set protocols bgp parameters cluster-id 192.0.2.10
```

```{cfgcmd} set protocols bgp parameters route-reflector-allow-outbound-policy

**Allow outbound route-maps (and other outbound policy) to apply to
routes the local route reflector reflects to its route reflector
clients.**

By default, FRR does not apply outbound policy to reflected routes, to
preserve the reflector's transparency. Enabling this option allows
outbound policy to take effect on reflected routes.
```

Example:

```none
set protocols bgp parameters route-reflector-allow-outbound-policy
```

#### Confederation configuration

A BGP confederation divides an AS into sub-ASs (member-ASs) to reduce the
number of required iBGP peerings. Within each sub-AS, a full iBGP mesh is
still required. Between sub-ASs, speakers use intra-confederation eBGP
sessions that preserve iBGP-style handling of NEXT_HOP, LOCAL_PREF, and
MED.

The confederation mechanism is described in
[RFC 5065](https://datatracker.ietf.org/doc/html/rfc5065).

```{cfgcmd} set protocols bgp parameters confederation identifier \<1-4294967294\>

**Configure the externally visible BGP confederation identifier (the ASN
that the entire confederation presents to other autonomous systems).**
```

Example:

```none
set protocols bgp parameters confederation identifier 65000
```

```{cfgcmd} set protocols bgp parameters confederation peers \<1-4294967294\>

**Configure the ASNs of other (not local) sub-ASs within the same BGP
confederation.**

This command is multi-value: issue it once per remote sub-AS to add each
member-AS to the confederation peer list. The local sub-AS (configured
via `system-as`) must not be listed here.
```

Example:

```none
set protocols bgp parameters confederation peers 65001
set protocols bgp parameters confederation peers 65002
set protocols bgp parameters confederation peers 65003
```

## Operation

### Show

```{opcmd} show bgp \<ipv4 | ipv6\>

**Show the BGP routing table for the specified address family.**
```

Example output:

```none
BGP table version is 10, local router ID is 192.0.2.3, vrf id 0
Default local pref 100, local AS 64496
Status codes:  s suppressed, d damped, h history, * valid, > best, = multipath,
               i internal, r RIB-failure, S Stale, R Removed
Nexthop codes: @NNN nexthop's vrf id, < announce-nh-self
Origin codes:  i - IGP, e - EGP, ? - incomplete
RPKI validation codes: V valid, I invalid, N Not found
   Network          Next Hop            Metric LocPrf Weight Path
*> 198.51.100.0/24  192.0.2.4                0             0 64500 i
*> 203.0.113.0/24   192.0.2.5                0             0 64501 i
Displayed  2 routes and 2 total paths
```

```{opcmd} show bgp \<ipv4 | ipv6\> \<address | prefix\>

**Show detailed BGP information for the specified prefix.**
```

Example output:

```none
BGP routing table entry for 198.51.100.0/24
Paths: (1 available, best #1, table default)
  Advertised to non peer-group peers:
  192.0.2.1 192.0.2.2 192.0.2.4 192.0.2.5
  64504
    192.0.2.4 from 192.0.2.4 (192.0.2.4)
      Origin IGP, metric 0, valid, external, best (First path received)
      Last update: Wed Jan  6 12:18:53 2021
```

```{opcmd} show bgp cidr-only

**Show BGP routes with non-natural (non-classful) prefix lengths.**
```

```{opcmd} show bgp \<ipv4 | ipv6\> community \<value\>

**Show BGP routes carrying the specified community value in their
COMMUNITIES attribute.**

Valid values are:

- a decimal number (1-4294967200)
- an `AA:NN` pair, where `AA` is an autonomous system number, and `NN`
  is a 2-byte community value (e.g., `65001:100`)
- one of the well-known community names, such as `no-export`,
  `no-advertise`, or `local-as`.
```

```{opcmd} show bgp \<ipv4 | ipv6\> community-list \<name\>

**Show BGP routes permitted by the specified community-list.**
```

```{opcmd} show bgp \<ipv4 | ipv6\> dampening dampened-paths

**Show BGP routes currently suppressed by dampening.**
```

```{opcmd} show bgp \<ipv4 | ipv6\> dampening flap-statistics

**Show flap statistics for BGP routes tracked by dampening (any route
with an accumulated penalty).**
```

```{opcmd} show bgp \<ipv4 | ipv6\> filter-list \<name\>

**Show BGP routes permitted by the specified AS-path access-list.**
```

```{opcmd} show bgp \<ipv4 | ipv6\> neighbors \<address\> advertised-routes

**Show the BGP routes advertised by the local router to the specified
neighbor.**
```

```{opcmd} show bgp \<ipv4 | ipv6\> neighbors \<address\> received-routes

**Show the BGP routes received from the specified neighbor before the
inbound policy is applied.**

Requires inbound `soft-reconfiguration` to be enabled for that neighbor
on the local router.
```

```{opcmd} show bgp \<ipv4 | ipv6\> neighbors \<address\> routes

**Show the BGP routes received from the specified neighbor that were
accepted after inbound filtering.**
```

```{opcmd} show bgp \<ipv4 | ipv6\> neighbors \<address\> dampened-routes

**Show dampened BGP routes received from the specified neighbor.**
```

```{opcmd} show bgp \<ipv4 | ipv6\> regexp \<text\>

**Show BGP routes whose AS_PATH matches the specified regular
expression.**
```

```{opcmd} show bgp \<ipv4 | ipv6\> summary

**Show a summary of all BGP sessions.**
```

Example output:

```none
IPv4 Unicast Summary:
BGP router identifier 192.0.2.3, local AS number 64500 vrf-id 0
BGP table version 11
RIB entries 5, using 920 bytes of memory
Peers 4, using 82 KiB of memory

Neighbor        V         AS MsgRcvd MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd
192.0.2.1       4      64500     148     159        0    0    0 02:16:01            0
192.0.2.2       4      64500     136     143        0    0    0 02:13:21            0
192.0.2.4       4      64504     161     163        0    0    0 02:16:01            1
192.0.2.5       4      64505     162     166        0    0    0 02:16:01            1

Total number of neighbors 4
```

### Reset

```{opcmd} reset bgp \<ipv4 | ipv6\> \<address\> [soft [in | out]]

**Reset the BGP session with the specified neighbor.**

With `soft`, the router performs a soft reset rather than tearing down
the TCP session. Without `in` or `out`, soft reset is applied in both
directions.
```

```{opcmd} reset bgp all

**Reset all BGP sessions on this router.**
```

```{opcmd} reset bgp \<ipv4 | ipv6\> external

**Reset all external (eBGP) sessions on this router for the specified
address family.**
```

```{opcmd} reset bgp \<ipv4 | ipv6\> peer-group \<name\> [soft [in | out]]

**Reset BGP sessions with all members of the specified peer group.**

With `soft`, the router performs a soft reset rather than tearing down
the TCP sessions. Without `in` or `out`, soft reset is applied in both
directions.
```

## Examples

### IPv4 peering

The following example demonstrates a simple eBGP peering between two VyOS
routers.

**Node 1:**

```none
set protocols bgp system-as 64512
set protocols bgp neighbor 192.0.2.2 ebgp-multihop '2'
set protocols bgp neighbor 192.0.2.2 remote-as '64513'
set protocols bgp neighbor 192.0.2.2 update-source '192.0.2.1'
set protocols bgp neighbor 192.0.2.2 address-family ipv4-unicast
set protocols bgp address-family ipv4-unicast network '198.51.100.0/24'
set protocols bgp parameters router-id '192.0.2.1'
```

**Node 2:**

```none
set protocols bgp system-as 64513
set protocols bgp neighbor 192.0.2.1 ebgp-multihop '2'
set protocols bgp neighbor 192.0.2.1 remote-as '64512'
set protocols bgp neighbor 192.0.2.1 update-source '192.0.2.2'
set protocols bgp neighbor 192.0.2.1 address-family ipv4-unicast
set protocols bgp address-family ipv4-unicast network '203.0.113.0/24'
set protocols bgp parameters router-id '192.0.2.2'
```

The CIDR declared in the `network` statement must exist in the routing
table (either dynamic or static). The simplest way to ensure that is to
create a blackhole static route:

**Node 1:**

```none
set protocols static route 198.51.100.0/24 blackhole distance '254'
```

**Node 2:**

```none
set protocols static route 203.0.113.0/24 blackhole distance '254'
```

### IPv6 peering

The following example demonstrates a simple eBGP peering over IPv6.

**Node 1:**

```none
set protocols bgp system-as 64512
set protocols bgp neighbor 2001:db8::2 ebgp-multihop '2'
set protocols bgp neighbor 2001:db8::2 remote-as '64513'
set protocols bgp neighbor 2001:db8::2 update-source '2001:db8::1'
set protocols bgp neighbor 2001:db8::2 address-family ipv6-unicast
set protocols bgp address-family ipv6-unicast network '2001:db8:1::/48'
set protocols bgp parameters router-id '192.0.2.1'
```

**Node 2:**

```none
set protocols bgp system-as 64513
set protocols bgp neighbor 2001:db8::1 ebgp-multihop '2'
set protocols bgp neighbor 2001:db8::1 remote-as '64512'
set protocols bgp neighbor 2001:db8::1 update-source '2001:db8::2'
set protocols bgp neighbor 2001:db8::1 address-family ipv6-unicast
set protocols bgp address-family ipv6-unicast network '2001:db8:2::/48'
set protocols bgp parameters router-id '192.0.2.2'
```

As with IPv4, the prefix declared in the `network` statement must exist
in the routing table. A blackhole static route is the simplest way to
ensure this:

**Node 1:**

```none
set protocols static route6 2001:db8:1::/48 blackhole distance '254'
```

**Node 2:**

```none
set protocols static route6 2001:db8:2::/48 blackhole distance '254'
```

### Route filtering

The following example applies inbound and outbound route filters to both
IPv4 and IPv6 BGP sessions using route-maps that reference prefix-lists.

**Node 1:**

```none
set policy prefix-list AS64513-IN rule 10 action 'permit'
set policy prefix-list AS64513-IN rule 10 prefix '203.0.113.0/24'
set policy prefix-list AS64513-OUT rule 10 action 'deny'
set policy prefix-list AS64513-OUT rule 10 prefix '198.51.100.0/24'
set policy prefix-list6 AS64513-IN rule 10 action 'permit'
set policy prefix-list6 AS64513-IN rule 10 prefix '2001:db8:2::/48'
set policy prefix-list6 AS64513-OUT rule 10 action 'deny'
set policy prefix-list6 AS64513-OUT rule 10 prefix '2001:db8:1::/48'

set policy route-map AS64513-IN rule 10 action 'permit'
set policy route-map AS64513-IN rule 10 match ip address prefix-list 'AS64513-IN'
set policy route-map AS64513-IN rule 10 match ipv6 address prefix-list 'AS64513-IN'
set policy route-map AS64513-IN rule 20 action 'deny'
set policy route-map AS64513-OUT rule 10 action 'deny'
set policy route-map AS64513-OUT rule 10 match ip address prefix-list 'AS64513-OUT'
set policy route-map AS64513-OUT rule 10 match ipv6 address prefix-list 'AS64513-OUT'
set policy route-map AS64513-OUT rule 20 action 'permit'

set protocols bgp system-as 64512
set protocols bgp neighbor 2001:db8::2 address-family ipv4-unicast route-map export 'AS64513-OUT'
set protocols bgp neighbor 2001:db8::2 address-family ipv4-unicast route-map import 'AS64513-IN'
set protocols bgp neighbor 2001:db8::2 address-family ipv6-unicast route-map export 'AS64513-OUT'
set protocols bgp neighbor 2001:db8::2 address-family ipv6-unicast route-map import 'AS64513-IN'
```

**Node 2:**

```none
set policy prefix-list AS64512-IN rule 10 action 'permit'
set policy prefix-list AS64512-IN rule 10 prefix '198.51.100.0/24'
set policy prefix-list AS64512-OUT rule 10 action 'deny'
set policy prefix-list AS64512-OUT rule 10 prefix '203.0.113.0/24'
set policy prefix-list6 AS64512-IN rule 10 action 'permit'
set policy prefix-list6 AS64512-IN rule 10 prefix '2001:db8:1::/48'
set policy prefix-list6 AS64512-OUT rule 10 action 'deny'
set policy prefix-list6 AS64512-OUT rule 10 prefix '2001:db8:2::/48'

set policy route-map AS64512-IN rule 10 action 'permit'
set policy route-map AS64512-IN rule 10 match ip address prefix-list 'AS64512-IN'
set policy route-map AS64512-IN rule 10 match ipv6 address prefix-list 'AS64512-IN'
set policy route-map AS64512-IN rule 20 action 'deny'
set policy route-map AS64512-OUT rule 10 action 'deny'
set policy route-map AS64512-OUT rule 10 match ip address prefix-list 'AS64512-OUT'
set policy route-map AS64512-OUT rule 10 match ipv6 address prefix-list 'AS64512-OUT'
set policy route-map AS64512-OUT rule 20 action 'permit'

set protocols bgp system-as 64513
set protocols bgp neighbor 2001:db8::1 address-family ipv4-unicast route-map export 'AS64512-OUT'
set protocols bgp neighbor 2001:db8::1 address-family ipv4-unicast route-map import 'AS64512-IN'
set protocols bgp neighbor 2001:db8::1 address-family ipv6-unicast route-map export 'AS64512-OUT'
set protocols bgp neighbor 2001:db8::1 address-family ipv6-unicast route-map import 'AS64512-IN'
```

This pattern can be extended in the `rule 20` deny clauses to also
filter link-local and multicast prefixes.
