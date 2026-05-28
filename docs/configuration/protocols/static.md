---
myst:
  html_meta:
    description: |
      Static routing allows network administrators to manually configure fixed
      paths for traffic to reach specific destinations.
    keywords: static route, ipv4, ipv6, next-hop, blackhole, reject, bfd
---

(routing-static)=

# Static

Static routes are manually configured entries in the router's {abbr}`RIB (Routing Information Base)`
that define how traffic should reach specific destinations. Unlike dynamic
routing protocols, static routes are not automatically updated when the network
topology changes.

Static routes are best suited for simple network topologies or to override
dynamic routing protocol behavior for a limited number of routes.

The {abbr}`RIB (Routing Information Base)` stores all routing information,
including manually configured static routes and any dynamically learned routes.
From the {abbr}`RIB (Routing Information Base)`, the router derives unicast
routes to build the {abbr}`FIB (Forwarding Information Base)`.

## IPv4 unicast routes

IPv4 unicast routes direct traffic destined for a single IPv4 host or subnet
toward a specific next hop. Use the following commands to configure IPv4
unicast routes for a specific remote subnet.

```{cfgcmd} set protocols static route \<subnet\> next-hop \<address\>

**Configure the next-hop IP address for the specified subnet.**

You can configure multiple next-hop IP addresses for the same destination
subnet.
```

Example:

```none
set protocols static route 192.0.2.0/24 next-hop 10.0.0.254
```

```{cfgcmd} set protocols static route \<subnet\> next-hop \<address\> disable

**Disable the route via the specified next-hop IP address.**

This command temporarily deactivates the route while preserving the
configured subnet, next-hop, and distance parameters.
```

Example:

```none
set protocols static route 192.0.2.0/24 next-hop 10.0.0.254 disable
```

```{cfgcmd} set protocols static route \<subnet\> next-hop \<address\> distance \<distance\>

**Configure the administrative distance for the route via the specified
next-hop IP address.**

Routes with a lower administrative distance are prioritized over routes with
a higher distance.

The allowed range is 1 to 255. The default distance is 1.
```

```{note}
Routes with a distance of 255 are disabled and not used for packet
forwarding.
```

Example:

```none
set protocols static route 192.0.2.0/24 next-hop 10.0.0.254 distance 10
```

### IPv4 interface routes

IPv4 interface routes direct traffic destined for a single IPv4 host or subnet
out of a specific local interface. Use the following commands to configure IPv4
interface routes for a specific remote subnet.

```{cfgcmd} set protocols static route \<subnet\> interface \<interface\>

**Configure the next-hop interface for the specified subnet.**

You can configure multiple next-hop interfaces for the same destination
subnet.
```

Example:

```none
set protocols static route 192.0.2.0/24 interface eth0
```

```{cfgcmd} set protocols static route \<subnet\> interface \<interface\> disable

**Disable the route via the specified next-hop interface.**

This command temporarily deactivates the route while preserving the
configured subnet, interface, and distance parameters.
```

Example:

```none
set protocols static route 192.0.2.0/24 interface eth0 disable
```

```{cfgcmd} set protocols static route \<subnet\> interface \<interface\> distance \<distance\>

**Configure the administrative distance for the route via the specified
next-hop interface.**

Routes with a lower administrative distance are prioritized over routes with
a higher distance.

The allowed range is 1 to 255. The default distance is 1.
```

Example:

```none
set protocols static route 192.0.2.0/24 interface eth0 distance 10
```

### IPv4 BFD

{abbr}`BFD (Bidirectional Forwarding Detection)` monitors the reachability
of a static route's next-hop IP address. Use the following commands to
configure {abbr}`BFD (Bidirectional Forwarding Detection)` parameters for your
IPv4 static routes.

```{cfgcmd} set protocols static route \<subnet\> next-hop \<address\> bfd

**Enable BFD monitoring for the route via the specified next-hop IP address.**

The system uses the next-hop IP address as the BFD peer destination.
```

Example:

```none
set protocols static route 192.0.2.0/24 next-hop 10.0.0.254 bfd
```

```{cfgcmd} set protocols static route \<subnet\> next-hop \<address\> bfd profile \<profile\>

**Apply the settings from a designated BFD profile to the BFD session that monitors
the specified next-hop IP address.**
```

Example:

```none
set protocols static route 192.0.2.0/24 next-hop 10.0.0.254 bfd profile custom-profile
```

```{cfgcmd} set protocols static route \<subnet\> next-hop \<address\> bfd multi-hop source-address \<source-address\>

**Enable a multi-hop BFD session to monitor the reachability of the
specified next-hop IP address.**

The system initiates the BFD session from the specified local source IPv4
address.
```

Example:

```none
set protocols static route 192.0.2.0/24 next-hop 10.0.0.254 bfd multi-hop source-address 172.16.1.1
```

### DHCP interface routes

DHCP interface routes direct traffic destined for a single IPv4 host or subnet
toward a next-hop gateway obtained from a DHCP-enabled interface. Use the
following command to configure DHCP interface routes.

```{cfgcmd} set protocols static route \<subnet\> dhcp-interface \<interface\>

**Configure a static route that derives its next-hop IP address from
the specified DHCP-enabled interface.**
```

Example:

```none
set protocols static route 192.0.2.0/24 dhcp-interface eth0
```

### IPv4 reject routes

IPv4 reject routes explicitly drop traffic destined for a single IPv4 host or
subnet and return an ICMP unreachable message to the sending device. Use the
following commands to configure IPv4 reject routes.

```{cfgcmd} set protocols static route \<subnet\> reject

**Configure a reject route for the specified subnet.**

The system discards traffic destined for this subnet and returns an ICMP
destination unreachable message to the sending device.
```

Example:

```none
set protocols static route 192.0.2.0/24 reject
```

```{cfgcmd} set protocols static route \<subnet\> reject distance \<distance\>

**Configure the administrative distance for the reject route.**

Routes with a lower administrative distance are prioritized over routes with
a higher distance.

The allowed range is 1 to 255.
```

Example:

```none
set protocols static route 192.0.2.0/24 reject distance 200
```

```{cfgcmd} set protocols static route \<subnet\> reject tag \<tag\>

**Configure a numeric tag for the reject route.**

The allowed range is 1 to 4294967295.
```

Example:

```none
set protocols static route 192.0.2.0/24 reject tag 100
```

### IPv4 blackhole routes

Blackhole routes silently discard traffic destined for a specific subnet.
Unlike a reject route, which notifies the sender with an ICMP destination
unreachable message, a blackhole route drops the packets without generating
any response.

```{cfgcmd} set protocols static route \<subnet\> blackhole

**Configure a blackhole route for the specified subnet.**

The system silently discards matching packets without sending an ICMP
response to the source.
```

Example:

```none
set protocols static route 10.0.0.0/8 blackhole
```

```{cfgcmd} set protocols static route \<subnet\> blackhole distance \<distance\>

**Configure the administrative distance for the blackhole route.**

Routes with a lower administrative distance are prioritized over routes with
a higher distance.

The allowed range is 1 to 255.
```

Example:

```none
set protocols static route 10.0.0.0/8 blackhole distance 200
```

```{cfgcmd} set protocols static route \<subnet\> blackhole tag \<tag\>

**Configure a numeric tag for the blackhole route.**

The allowed range is 1 to 4294967295.
```

Example:

```none
set protocols static route 10.0.0.0/8 blackhole tag 100
```

## IPv6 unicast routes

IPv6 unicast routes direct traffic destined for a single IPv6 host or subnet
toward a specific next hop. Use the following commands to configure IPv6
unicast routes for a specific remote subnet.

```{cfgcmd} set protocols static route6 \<subnet\> next-hop \<address\>

**Configure the next-hop IPv6 address for the specified subnet.**

You can configure multiple next-hop IPv6 addresses for the same destination
subnet.
```

Example:

```none
set protocols static route6 2001:db8:1::/64 next-hop 2001:db8:100::1
```

```{cfgcmd} set protocols static route6 \<subnet\> next-hop \<address\> disable

**Disable the route via the specified next-hop IPv6 address.**

This command temporarily deactivates the route while preserving the
configured subnet, next-hop, and distance parameters.
```

Example:

```none
set protocols static route6 2001:db8:1::/64 next-hop 2001:db8:100::1 disable
```

```{cfgcmd} set protocols static route6 \<subnet\> next-hop \<address\> distance \<distance\>

**Configure the administrative distance for the route via the
specified next-hop IPv6 address.**

Routes with a lower administrative distance are prioritized over routes with
a higher distance.

The allowed range is 1 to 255. The default distance is 1.
```

```{note}
Routes with a distance of 255 are disabled and not used for packet
forwarding.
```

Example:

```none
set protocols static route6 2001:db8:1::/64 next-hop 2001:db8:100::1 distance 10
```

```{cfgcmd} set protocols static route6 \<subnet\> next-hop \<address\> segments \<segments\>

**Configure an IPv6 unicast route that utilizes Segment Routing over IPv6 (SRv6)
to reach the destination subnet.**

Use a forward slash (`/`) to separate multiple IPv6 segment identifiers
(SIDs) in your sequence.
```

Example:

```none
set protocols static route6 2001:db8:1000::/36 next-hop 2001:db8:201::ffff segments '2001:db8:aaaa::7/2002::4/2002::3/2002::2'
```

```none
vyos@vyos:~$ show ipv6 route
Codes: K - kernel route, C - connected, S - static, R - RIPng,
       O - OSPFv3, I - IS-IS, B - BGP, N - NHRP, T - Table,
       v - VNC, V - VNC-Direct, A - Babel, F - PBR,
       f - OpenFabric,
       > - selected route, * - FIB route, q - queued, r - rejected, b - backup
       t - trapped, o - offload failure
 C>* 2001:db8:201::/64 is directly connected, eth0.201, 00:00:46
 S>* 2001:db8:1000::/36 [1/0] via 2001:db8:201::ffff, eth0.201, seg6 2001:db8:aaaa::7,2002::4,2002::3,2002::2, weight 1, 00:00:08
```

### IPv6 interface routes

IPv6 interface routes direct traffic destined for a single IPv6 host or subnet
out of a specific local interface. Use the following commands to configure IPv6
interface routes for a specific remote subnet.

```{cfgcmd} set protocols static route6 \<subnet\> interface \<interface\>

**Configure the next-hop interface for the specified subnet.**

You can configure multiple next-hop interfaces for the same destination
subnet.
```

Example:

```none
set protocols static route6 2001:db8:1::/64 interface eth0
```

```{cfgcmd} set protocols static route6 \<subnet\> interface \<interface\> disable

**Disable the route via the specified next-hop interface.**

This command temporarily deactivates the route while preserving the
configured subnet, interface, and distance parameters.
```

Example:

```none
set protocols static route6 2001:db8:1::/64 interface eth0 disable
```

```{cfgcmd} set protocols static route6 \<subnet\> interface \<interface\> distance \<distance\>

**Configure the administrative distance for the route via the
specified next-hop interface.**

Routes with a lower administrative distance are prioritized over routes with
a higher distance.

The allowed range is 1 to 255. The default distance is 1.
```

Example:

```none
set protocols static route6 2001:db8:1::/64 interface eth0 distance 10
```

```{cfgcmd} set protocols static route6 \<subnet\> interface \<interface\> segments \<segments\>

**Configure an IPv6 interface route that utilizes Segment Routing over IPv6
(SRv6) to reach a destination subnet.**

Use a forward slash (`/`) to separate multiple IPv6 segment identifiers
(SIDs) in your sequence.
```

Example:

```none
set protocols static route6 2001:db8:1000::/36 interface eth0 segments '2001:db8:aaaa::7/2002::4/2002::3/2002::2'
```

### IPv6 BFD

{abbr}`BFD (Bidirectional Forwarding Detection)` monitors the reachability
of a static route's next-hop IPv6 address. Use the following commands to
configure {abbr}`BFD (Bidirectional Forwarding Detection)` parameters for your
IPv6 static routes.

```{cfgcmd} set protocols static route6 \<subnet\> next-hop \<address\> bfd

**Enable BFD monitoring for the route via the specified next-hop IPv6
address.**

The system uses the next-hop IPv6 address as the BFD peer destination.
```

Example:

```none
set protocols static route6 2001:db8:1::/64 next-hop 2001:db8:100::1 bfd
```

```{cfgcmd} set protocols static route6 \<subnet\> next-hop \<address\> bfd profile \<profile\>

**Apply the settings from a designated BFD profile to the BFD session
that monitors the specified next-hop IPv6 address.**
```

Example:

```none
set protocols static route6 2001:db8:1::/64 next-hop 2001:db8:100::1 bfd profile custom-profile
```

```{cfgcmd} set protocols static route6 \<subnet\> next-hop \<address\> bfd multi-hop source-address \<source-address\>

**Enable a multi-hop BFD session to monitor the reachability of the
specified next-hop IPv6 address.**

The system initiates the BFD session from the specified local source IPv6
address.
```

Example:

```none
set protocols static route6 2001:db8:1::/64 next-hop 2001:db8:100::1 bfd multi-hop source-address 2001:db8:200::1
```

### IPv6 reject routes

IPv6 reject routes explicitly drop traffic destined for a single IPv6 host or
subnet and return an ICMPv6 unreachable message to the sending device. Use the
following commands to configure IPv6 reject routes.

```{cfgcmd} set protocols static route6 \<subnet\> reject

**Configure a reject route for the specified subnet.**

The system discards traffic destined for this subnet and returns an ICMPv6
destination unreachable message to the sending device.
```

Example:

```none
set protocols static route6 2001:db8:1::/64 reject
```

```{cfgcmd} set protocols static route6 \<subnet\> reject distance \<distance\>

**Configure the administrative distance for the reject route.**

Routes with a lower administrative distance are prioritized over routes with
a higher distance.

The allowed range is 1 to 255.
```

Example:

```none
set protocols static route6 2001:db8:1::/64 reject distance 200
```

```{cfgcmd} set protocols static route6 \<subnet\> reject tag \<tag\>

**Configure a numeric tag for the reject route.**

The allowed range is 1 to 4294967295.
```

Example:

```none
set protocols static route6 2001:db8:1::/64 reject tag 100
```

### IPv6 blackhole routes

Blackhole routes silently discard traffic destined for a specific subnet.
Unlike a reject route, which notifies the sender with an ICMPv6 destination
unreachable message, a blackhole route drops the packets without generating
any response.

```{cfgcmd} set protocols static route6 \<subnet\> blackhole

**Configure a blackhole route for the specified subnet.**

The system silently discards matching packets without sending an ICMPv6
response to the source.
```

Example:

```none
set protocols static route6 2001:db8:1::/64 blackhole
```

```{cfgcmd} set protocols static route6 \<subnet\> blackhole distance \<distance\>

**Configure the administrative distance for the blackhole route.**

Routes with a lower administrative distance are prioritized over routes with
a higher distance.

The allowed range is 1 to 255.
```

Example:

```none
set protocols static route6 2001:db8:1::/64 blackhole distance 200
```

```{cfgcmd} set protocols static route6 \<subnet\> blackhole tag \<tag\>

**Configure a numeric tag for the blackhole route.**

The allowed range is 1 to 4294967295.
```

Example:

```none
set protocols static route6 2001:db8:1::/64 blackhole tag 100
```

## Alternate routing tables

Alternate routing tables are utilized to implement both Policy-Based Routing
(PBR) and Virtual Routing and Forwarding ({ref}`vrf`).
