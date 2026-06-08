---
myst:
  html_meta:
    description: |
      RIP is a distance-vector routing protocol based on the Bellman-Ford
      algorithm. It determines the best route based on hop count and
      periodically advertises the routing table to neighbors.
    keywords: rip, ripv1, ripv2, distance-vector, bellman-ford,
      redistribute
---

(rip)=

# RIP

Developed in the 1970s at Xerox Labs, RIP is a distance-vector routing
protocol based on the Bellman-Ford algorithm.

RIP determines the best route based on hop count (number of routers
traversed). RIP-enabled routers periodically advertise their entire routing
table to neighbors, along with the metric (hop count) for each destination.

Supported versions:

- RIPv1: As described in
  [RFC 1058](https://datatracker.ietf.org/doc/html/rfc1058)
- RIPv2: As described in
  [RFC 2453](https://datatracker.ietf.org/doc/html/rfc2453)

## General configuration

```{cfgcmd} set protocols rip network \<A.B.C.D/M\>

**Enable RIP on all interfaces whose IP addresses fall within the specified
network.**
```

Example:

```none
set protocols rip network 192.0.2.0/24
```

```{cfgcmd} set protocols rip interface \<interface\>

**Enable RIP on the specified interface.**

Once applied, the interface sends and receives RIP packets.
```

Example:

```none
set protocols rip interface eth0
```

```{cfgcmd} set protocols rip neighbor \<A.B.C.D\>

**Configure a RIP neighbor using its IP address.**

Use this command when a neighbor cannot process multicast RIP updates. Once
configured, the local router sends updates directly to the specified
neighbor as unicast packets.
```

Example:

```none
set protocols rip neighbor 192.0.2.2
```

```{cfgcmd} set protocols rip passive-interface \<interface\>

**Enable passive mode for the specified interface.**

This prevents the router from sending outgoing RIP updates on the
interface, except to explicitly configured neighbors. Incoming RIP updates
are still accepted and processed.
```

Example:

```none
set protocols rip passive-interface eth0
```

```{cfgcmd} set protocols rip passive-interface default

**Enable passive mode for all interfaces.**

This prevents the router from sending outgoing RIP updates on all
interfaces, except to explicitly configured neighbors. The router still
receives and processes incoming RIP updates normally.
```

Example:

```none
set protocols rip passive-interface default
```

## Optional configuration

```{cfgcmd} set protocols rip default-distance \<1-255\>

**Configure the administrative distance for all RIP-learned routes.**

The administrative distance determines how RIP-learned routes are
prioritized against routes learned from other sources (such as BGP, OSPF,
or static routes) when multiple paths to the same destination exist.
```

```{note}
Routes assigned a distance of 255 are disabled and will not be installed
in the kernel forwarding table.
```

Example:

```none
set protocols rip default-distance 100
```

```{cfgcmd} set protocols rip network-distance \<A.B.C.D/M\> distance \<1-255\>

**Configure an administrative distance for RIP routes whose source IP
address falls within the specified network.**
```

Example:

```none
set protocols rip network-distance 192.0.2.0/24 distance 80
```

```{cfgcmd} set protocols rip network-distance \<A.B.C.D/M\> access-list \<name\>

**Restrict administrative distance assignments to RIP routes whose source
IP address matches the specified network and the route itself matches the
specified access-list.**
```

Example:

```none
set protocols rip network-distance 192.0.2.0/24 distance 80
set protocols rip network-distance 192.0.2.0/24 access-list 10
```

```{cfgcmd} set protocols rip default-information originate

**Generate and advertise a default route (`0.0.0.0/0`) to all RIP
neighbors.**
```

Example:

```none
set protocols rip default-information originate
```

```{cfgcmd} set protocols rip distribute-list access-list \<in|out\> \<0-4294967295\>

**Apply an access-list to filter RIP routes in the inbound or outbound
direction.**

- `in`: Filters routes received from RIP neighbors.
- `out`: Filters routes advertised to RIP neighbors.
```

Example:

```none
set protocols rip distribute-list access-list in 20
```

```{cfgcmd} set protocols rip distribute-list interface \<interface\> access-list \<in|out\> \<0-4294967295\>

**Apply an access-list to filter RIP routes in the inbound or outbound
direction on the specified interface.**

- `in`: Filters routes received from RIP neighbors on this interface.
- `out`: Filters routes advertised to RIP neighbors on this interface.
```

Example:

```none
set protocols rip distribute-list interface eth0 access-list in 20
```

```{cfgcmd} set protocols rip distribute-list prefix-list \<in|out\> \<name\>

**Apply a prefix-list to filter RIP routes in the inbound or outbound
direction.**

- `in`: Filters routes received from RIP neighbors.
- `out`: Filters routes advertised to RIP neighbors.
```

Example:

```none
set protocols rip distribute-list prefix-list in INBOUND-FILTER
```

```{cfgcmd} set protocols rip distribute-list interface \<interface\> prefix-list \<in|out\> \<name\>

**Apply a prefix-list to filter RIP routes on the specified interface in
the inbound or outbound direction.**

- `in`: Filters routes received from RIP neighbors on this interface.
- `out`: Filters routes advertised to RIP neighbors on this interface.
```

Example:

```none
set protocols rip distribute-list interface eth0 prefix-list in RIP-IN
```

```{cfgcmd} set protocols rip route \<A.B.C.D/M\>

**Add a static route to the RIP routing process.**

The route is created only inside RIP.

This command is specific to FRR and VyOS and should only be used by
advanced users with a strong understanding of the RIP protocol.

For most deployments, the recommended approach is to create a standard
static route and redistribute it into RIP using
`set protocols rip redistribute static`.
```

Example:

```none
set protocols rip route 192.0.2.0/24
```

```{cfgcmd} set protocols rip timers update \<5-2147483647\>

**Configure the RIP update timer, in seconds.**

The update timer defines how often the router sends unsolicited Response
messages to its RIP neighbors. Each Response contains the complete RIP
routing table.

The default value is 30 seconds.
```

Example:

```none
set protocols rip timers update 60
```

```{cfgcmd} set protocols rip timers timeout \<5-2147483647\>

**Configure the RIP route timeout, in seconds.**

If a route is not refreshed by an incoming update within this interval, it
becomes invalid. The router temporarily retains the invalid route in the
RIP routing table so that neighbors learn the route has been dropped.

The default value is 180 seconds.
```

Example:

```none
set protocols rip timers timeout 300
```

```{cfgcmd} set protocols rip timers garbage-collection \<5-2147483647\>

**Configure the RIP garbage-collection timer, in seconds.**

This timer starts when a route becomes invalid. When the timer expires,
the route is removed from the routing table.

The default value is 120 seconds.
```

Example:

```none
set protocols rip timers garbage-collection 60
```

## Redistribution configuration

```{cfgcmd} set protocols rip redistribute \<babel|bgp|connected|isis|kernel|nhrp|ospf|static\>

**Redistribute routes from the specified source into RIP.**

Routes learned from the chosen source are imported into the RIP routing
table and advertised to RIP neighbors as if they had been learned through
RIP itself.

The supported sources are:

- `babel`: Routes learned via Babel.
- `bgp`: Routes learned via BGP.
- `connected`: Directly connected routes.
- `isis`: Routes learned via IS-IS.
- `kernel`: Routes installed in the kernel routing table.
- `nhrp`: Routes learned via NHRP.
- `ospf`: Routes learned via OSPF.
- `static`: Routes configured statically.
```

Example:

```none
set protocols rip redistribute static
```

```{cfgcmd} set protocols rip redistribute \<babel|bgp|connected|isis|kernel|nhrp|ospf|static\> metric \<1-16\>

**Configure the metric for routes redistributed from the specified
source.**
```

Example:

```none
set protocols rip redistribute static metric 5
```

```{cfgcmd} set protocols rip redistribute \<babel|bgp|connected|isis|kernel|nhrp|ospf|static\> route-map \<name\>

**Apply a route-map to filter routes redistributed from the specified
source.**
```

Example:

```none
set protocols rip redistribute static route-map RIP-REDISTRIBUTE
```

```{cfgcmd} set protocols rip default-metric \<1-16\>

**Configure the default metric (hop count) applied to redistributed
routes.**

The default value is 1.
```

```{note}
This command does not affect connected routes redistributed via
`set protocols rip redistribute connected`. To configure the metric for
connected routes, use `set protocols rip redistribute connected metric`
explicitly.
```

Example:

```none
set protocols rip default-metric 5
```

## Interfaces configuration

```{cfgcmd} set protocols rip interface \<interface\> authentication plaintext-password \<text\>

**Enable simple password authentication for RIPv2 on the specified
interface and set a password.**

The password must not exceed 16 characters.
```

Example:

```none
set protocols rip interface eth0 authentication plaintext-password vyos-secret
```

```{cfgcmd} set protocols rip interface \<interface\> authentication md5 \<id\> password \<text\>

**Enable {abbr}`MD5 (Message-Digest Algorithm 5)` authentication for RIPv2
on the specified interface and set the MD5 key.**

The MD5 key must not exceed 16 characters.
```

Example:

```none
set protocols rip interface eth0 authentication md5 1 password vyos-secret
```

```{cfgcmd} set protocols rip interface \<interface\> split-horizon disable

**Disable split-horizon on the specified interface.**

By default, VyOS does not advertise RIP routes back through the interface
on which they were learned (split horizon). This command turns off that
default.
```

Example:

```none
set protocols rip interface eth0 split-horizon disable
```

```{cfgcmd} set protocols rip interface \<interface\> split-horizon poison-reverse

**Enable split horizon with poison reverse on the specified interface.**

If enabled, the router advertises the learned routes as unreachable on the
interface where they were learned.
```

Example:

```none
set protocols rip interface eth0 split-horizon poison-reverse
```

## Operational mode commands

```{opcmd} show ip rip

**Show all RIP routes.**
```

```none
vyos@vyos-1:~$ show ip rip
Codes: K - kernel route, C - connected, L - local, S - static,
       R - RIP, O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, F - PBR,
       f - OpenFabric, t - Table-Direct
Sub-codes:
      (n) - normal, (s) - static, (d) - default, (r) - redistribute,
      (i) - interface

Network            Next Hop         Metric From            Tag Time
C(i) 192.0.2.0/24       0.0.0.0               1 self              0
C(i) 198.51.100.0/24    0.0.0.0               1 self              0
R(n) 203.0.113.0/24     192.0.2.2             2 192.0.2.2         0 02:53
```

```{opcmd} show ip rip status

**Show the current RIP status.**
```

```none
Routing Protocol is "rip"
  Sending updates every 30 seconds with +/-50%, next due in 11 seconds
  Timeout after 180 seconds, garbage collect after 120 seconds
  Outgoing update filter list for all interface is not set
  Incoming update filter list for all interface is not set
  Default redistribution metric is 1
  Redistributing:
  Default version control: send version 2, receive any version
    Interface        Send  Recv   Key-chain
    eth0             2     1 2
    eth2             2     1 2
  Routing for Networks:
    192.0.2.0/24
    eth0
  Routing Information Sources:
    Gateway          BadPackets BadRoutes  Distance Last Update
    192.0.2.2               0         0       120   00:00:11
  Distance: (default is 120)
```

## Example

The following example demonstrates a basic RIP configuration between two
routers, where directly connected networks are redistributed into RIP.

**Node 1:**

```none
set interfaces ethernet eth0 address '198.51.100.1/24'
set interfaces loopback lo address '192.0.2.1/32'
set protocols rip network 198.51.100.0/24
set protocols rip redistribute connected
```

**Node 2:**

```none
set interfaces ethernet eth0 address '198.51.100.2/24'
set interfaces loopback lo address '192.0.2.2/32'
set protocols rip network 198.51.100.0/24
set protocols rip redistribute connected
```
