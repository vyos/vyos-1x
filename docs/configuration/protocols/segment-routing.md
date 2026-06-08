---
myst:
  html_meta:
    description: |
      Segment Routing (SR) is a source-routing network architecture in
      which the ingress router attaches a list of Segment Identifiers
      (SIDs) to each packet to define its forwarding path.
    keywords: segment routing, sr, sid, srgb, srlb, mpls, isis, ospf
---

(segment-routing)=

# Segment Routing

{abbr}`SR (Segment Routing)` is a network architecture similar to source
routing. The ingress router attaches a list of segments, known as
{abbr}`SIDs (Segment Identifiers)`, to each packet as it enters the network.

The SID list explicitly defines the path the packet will follow. At each
node, the router reads the first SID, executes its forwarding instruction,
and typically removes it so the next node can process the subsequent SID.

SR relies on {abbr}`IGPs (Interior Gateway Protocols)` such as IS-IS or OSPF
to advertise SIDs across the network.

```{note}
SR defines a control plane architecture and can be applied to existing
MPLS-based data planes. In MPLS networks, segments are encoded as MPLS
labels and applied at the ingress router. These labels are then
distributed across the routing domain by IGPs such as IS-IS (as described
in [RFC 8667](https://datatracker.ietf.org/doc/html/rfc8667)) or OSPF.

SR for the MPLS data plane supports IPv4, IPv6, and
{abbr}`ECMP (Equal-Cost Multi-Path)`, and has been tested with Cisco and
Juniper routers. However, this deployment is still experimental for FRR.
```

## IS-IS SR configuration

Use the following commands to enable SR on IS-IS.

Known limitations:

- No support for level redistribution (L1 to L2 or L2 to L1).
- No support for {abbr}`BSID (Binding SID)`.
- Only a single {abbr}`SRGB (Segment Routing Global Block)` and the default
  {abbr}`SPF (Shortest Path First)` algorithm are supported.

```{cfgcmd} set protocols isis segment-routing global-block high-label-value \<16-1048575\>

**Configure the upper bound of the Segment Routing Global Block (SRGB).**

The SRGB defines the range of MPLS labels reserved for mapping global
segments, such as Prefix-SIDs, to FIB entries.

The range cannot exceed 65535 labels.
```

Example:

```none
set protocols isis segment-routing global-block high-label-value 23999
```

```{cfgcmd} set protocols isis segment-routing global-block low-label-value \<16-1048575\>

**Configure the lower bound of the Segment Routing Global Block (SRGB).**

The SRGB defines the range of MPLS labels reserved for mapping global
segments, such as Prefix-SIDs, to FIB entries.

The range cannot exceed 65535 labels.
```

Example:

```none
set protocols isis segment-routing global-block low-label-value 16000
```

```{cfgcmd} set protocols isis segment-routing local-block high-label-value \<16-1048575\>

**Configure the upper bound of the Segment Routing Local Block (SRLB).**

The SRLB defines the range of MPLS labels that a router reserves for its
local segments, such as Adjacency-SIDs.

The range cannot exceed 65535 labels.
```

Example:

```none
set protocols isis segment-routing local-block high-label-value 15999
```

```{cfgcmd} set protocols isis segment-routing local-block low-label-value \<16-1048575\>

**Configure the lower bound of the Segment Routing Local Block (SRLB).**

The SRLB defines the range of MPLS labels that a router reserves for its
local segments, such as Adjacency-SIDs.

The range cannot exceed 65535 labels.
```

Example:

```none
set protocols isis segment-routing local-block low-label-value 15000
```

```{note}
SR label blocks have the following configuration constraints:

- Both bounds (`high-label-value` and `low-label-value`) must be set.
  Removing either bound also removes the other.
- `local-block` requires `global-block` to be configured.
- The SRGB and SRLB ranges must not overlap.

Violating any of these causes the commit to fail.
```

```{cfgcmd} set protocols isis segment-routing maximum-label-depth \<1-16\>

**Configure the {abbr}`MSD (Maximum SID Depth)` supported by the router.**

The value depends on the MPLS data plane.
```

Example:

```none
set protocols isis segment-routing maximum-label-depth 10
```

```{cfgcmd} set protocols isis segment-routing prefix \<address\> index value \<0-65535\>

**Configure a Prefix-SID with an index value for the specified IP prefix.**

A Prefix-SID is a Segment Identifier associated with an IP prefix and
distributed by the IGP (IS-IS).
```

Example:

```none
set protocols isis segment-routing prefix 192.0.2.1/32 index value 1
```

```{cfgcmd} set protocols isis segment-routing prefix \<address\> index \<no-php-flag | explicit-null\>

**Configure a label processing flag for the indexed Prefix-SID associated
with the specified IP prefix:**

- `no-php-flag`: Requests the upstream neighbor not to pop the Prefix-SID
  label before forwarding the packet.
- `explicit-null`: Requests that the upstream neighbor forwards the packet
  with the Explicit-Null label.
```

Example:

```none
set protocols isis segment-routing prefix 192.0.2.1/32 index no-php-flag
```

```{cfgcmd} set protocols isis segment-routing prefix \<address\> absolute value \<16-1048575\>

**Configure a Prefix-SID with an absolute value for the specified IP
prefix**

A Prefix-SID is a Segment Identifier associated with an IP prefix and
distributed by the IGP (IS-IS).
```

Example:

```none
set protocols isis segment-routing prefix 192.0.2.1/32 absolute value 16001
```

```{cfgcmd} set protocols isis segment-routing prefix \<address\> absolute \<no-php-flag | explicit-null\>

**Configure a label processing flag for the absolute Prefix-SID associated
with the specified IP prefix:**

* `no-php-flag`: Requests the upstream neighbor not to pop the Prefix-SID
  label before forwarding the packet.
* `explicit-null`: Requests that the upstream neighbor forwards the packet
  with the Explicit-Null label.
```

Example:

```none
set protocols isis segment-routing prefix 192.0.2.1/32 absolute no-php-flag
```

### Operational commands

```{opcmd} show isis segment-routing node

**Show all learned SR nodes.**
```

```{opcmd} show isis route prefix-sid

**Show all learned Prefix-SIDs and their MPLS labels.**
```

```{note}
For more information, see {ref}`isis`.
```

## OSPF SR configuration

Use the following commands to enable SR on OSPF.

```{cfgcmd} set protocols ospf parameters opaque-lsa

**Enable Opaque {abbr}`LSA (Link State Advertisement)`
([RFC 2370](https://datatracker.ietf.org/doc/html/rfc2370)) in OSPF.**

Opaque LSAs are required to transport MPLS labels via OSPF.
```

Example:

```none
set protocols ospf parameters opaque-lsa
```

```{cfgcmd} set protocols ospf segment-routing global-block high-label-value \<16-1048575\>

**Configure the upper bound of the Segment Routing Global Block (SRGB).**

The SRGB defines the range of MPLS labels reserved for mapping Prefix-SIDs
to FIB entries.

The range cannot exceed 65535 labels.
```

Example:

```none
set protocols ospf segment-routing global-block high-label-value 23999
```

```{cfgcmd} set protocols ospf segment-routing global-block low-label-value \<16-1048575\>

**Configure the lower bound of the Segment Routing Global Block (SRGB).**

The SRGB defines the range of MPLS labels reserved for mapping Prefix-SIDs
to FIB entries.

The range cannot exceed 65535 labels.
```

Example:

```none
set protocols ospf segment-routing global-block low-label-value 16000
```

```{cfgcmd} set protocols ospf segment-routing local-block high-label-value \<16-1048575\>

**Configure the upper bound of the Segment Routing Local Block (SRLB).**

The SRLB defines the range of MPLS labels that a router reserves for its
local segments, such as Adjacency-SIDs.

The range cannot exceed 65535 labels.
```

Example:

```none
set protocols ospf segment-routing local-block high-label-value 15999
```

```{cfgcmd} set protocols ospf segment-routing local-block low-label-value \<16-1048575\>

**Configure the lower bound of the Segment Routing Local Block (SRLB).**

The SRLB defines the range of MPLS labels that a router reserves for its
local segments, such as Adjacency-SIDs.

The range cannot exceed 65535 labels.
```

Example:

```none
set protocols ospf segment-routing local-block low-label-value 15000
```

```{note}
SR label blocks have the following configuration constraints:

- Both bounds (`high-label-value` and `low-label-value`) must be set.
  Removing either bound also removes the other.
- `local-block` requires `global-block` to be configured.
- The SRGB and SRLB ranges must not overlap.

Violating any of these causes the commit to fail.
```

```{cfgcmd} set protocols ospf segment-routing maximum-label-depth \<1-16\>

**Configure the {abbr}`MSD (Maximum SID Depth)` supported by the router.**

The value depends on the MPLS data plane.
```

Example:

```none
set protocols ospf segment-routing maximum-label-depth 10
```

```{cfgcmd} set protocols ospf segment-routing prefix \<address\> index value \<0-65535\>

**Configure a Prefix-SID for the specified IP prefix.**

A Prefix-SID is a Segment Identifier associated with an IP prefix and
distributed by the IGP (OSPF).

Prefix-SIDs are unique within an SR domain.
```

Example:

```none
set protocols ospf segment-routing prefix 192.0.2.1/32 index value 1
```

```{cfgcmd} set protocols ospf segment-routing prefix \<address\> index \<no-php-flag | explicit-null\>

**Configure a label processing flag for the Prefix-SID associated with the
specified IP prefix:**

- `no-php-flag`: Requests the upstream neighbor not to pop the Prefix-SID
  label before forwarding the packet.
- `explicit-null`: Requests that the upstream neighbor forwards the packet
  with the Explicit-Null label.
```

Example:

```none
set protocols ospf segment-routing prefix 192.0.2.1/32 index no-php-flag
```

```{note}
For more information, see {ref}`ospf`.
```

## Examples

### Enable SR on IS-IS (experimental)

The following example demonstrates a basic two-node SR topology using IS-IS.

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

The following outputs show that MPLS Segment Routing is enabled and that
each router has learned MPLS labels for the other router's loopback:

```none
Node-1@vyos:~$ show mpls table
 Inbound Label  Type        Nexthop                Outbound Label
 ----------------------------------------------------------------------
 552            SR (IS-IS)  192.0.2.2              IPv4 Explicit Null     <-- Node-2 loopback learned on Node-1
 15000          SR (IS-IS)  192.0.2.2              implicit-null
 15001          SR (IS-IS)  fe80::e87:6cff:fe09:1  implicit-null
 15002          SR (IS-IS)  192.0.2.2              implicit-null
 15003          SR (IS-IS)  fe80::e87:6cff:fe09:1  implicit-null
```

```none
Node-2@vyos:~$ show mpls table
 Inbound Label  Type        Nexthop               Outbound Label
 ---------------------------------------------------------------------
 551            SR (IS-IS)  192.0.2.1             IPv4 Explicit Null     <-- Node-1 loopback learned on Node-2
 15000          SR (IS-IS)  192.0.2.1             implicit-null
 15001          SR (IS-IS)  fe80::e33:2ff:fe80:1  implicit-null
 15002          SR (IS-IS)  192.0.2.1             implicit-null
 15003          SR (IS-IS)  fe80::e33:2ff:fe80:1  implicit-null
```

The following outputs show MPLS Segment Routing label assignments for IP
routes:

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
```

```none
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

### Enable SR on OSPF (experimental)

The following example demonstrates a basic two-node SR topology using OSPF.

**Node 1:**

```none
set interfaces loopback lo address 198.51.100.1/32
set interfaces ethernet eth0 address 192.0.2.1/24
set protocols ospf area 0 network '192.0.2.0/24'
set protocols ospf area 0 network '198.51.100.1/32'
set protocols ospf parameters opaque-lsa
set protocols ospf parameters router-id '198.51.100.1'
set protocols ospf segment-routing global-block high-label-value '1100'
set protocols ospf segment-routing global-block low-label-value '1000'
set protocols ospf segment-routing prefix 198.51.100.1/32 index explicit-null
set protocols ospf segment-routing prefix 198.51.100.1/32 index value '1'
```

**Node 2:**

```none
set interfaces loopback lo address 198.51.100.2/32
set interfaces ethernet eth0 address 192.0.2.2/24
set protocols ospf area 0 network '192.0.2.0/24'
set protocols ospf area 0 network '198.51.100.2/32'
set protocols ospf parameters opaque-lsa
set protocols ospf parameters router-id '198.51.100.2'
set protocols ospf segment-routing global-block high-label-value '1100'
set protocols ospf segment-routing global-block low-label-value '1000'
set protocols ospf segment-routing prefix 198.51.100.2/32 index explicit-null
set protocols ospf segment-routing prefix 198.51.100.2/32 index value '2'
```

The following outputs show MPLS Segment Routing label assignments:

```none
Node-1@vyos:~$ show mpls table
 Inbound Label  Type       Nexthop      Outbound Label
 -----------------------------------------------------------
 1002           SR (OSPF)  192.0.2.2    IPv4 Explicit Null  <-- Node-2 loopback learned on Node-1
 15000          SR (OSPF)  192.0.2.2    implicit-null
 15001          SR (OSPF)  192.0.2.2    implicit-null
```

```none
Node-2@vyos:~$ show mpls table
 Inbound Label  Type       Nexthop      Outbound Label
 -----------------------------------------------------------
 1001           SR (OSPF)  192.0.2.1    IPv4 Explicit Null  <-- Node-1 loopback learned on Node-2
 15000          SR (OSPF)  192.0.2.1    implicit-null
 15001          SR (OSPF)  192.0.2.1    implicit-null
```

The following outputs show MPLS Segment Routing label assignments for IP
routes:

```none
Node-1@vyos:~$ show ip route ospf
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, F - PBR,
       f - OpenFabric,
       > - selected route, * - FIB route, q - queued, r - rejected, b - backup
       t - trapped, o - offload failure

O   198.51.100.1/32 [110/0] is directly connected, lo, weight 1, 00:03:43
O>* 198.51.100.2/32 [110/1] via 192.0.2.2, eth0, label IPv4 Explicit Null, weight 1, 00:03:32
O   192.0.2.0/24 [110/1] is directly connected, eth0, weight 1, 00:03:43
```

```none
Node-2@vyos:~$ show ip route ospf
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, F - PBR,
       f - OpenFabric,
       > - selected route, * - FIB route, q - queued, r - rejected, b - backup
       t - trapped, o - offload failure

O>* 198.51.100.1/32 [110/1] via 192.0.2.1, eth0, label IPv4 Explicit Null, weight 1, 00:03:36
O   198.51.100.2/32 [110/0] is directly connected, lo, weight 1, 00:03:51
O   192.0.2.0/24 [110/1] is directly connected, eth0, weight 1, 00:03:51
```
