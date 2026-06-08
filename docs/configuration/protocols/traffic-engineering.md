---
myst:
  html_meta:
    description: |
      Traffic Engineering (TE) is a set of techniques for steering traffic
      along paths different from the shortest path computed by the IGP.
    keywords: traffic engineering, te, isis, mpls, srv6, admin-group,
      bandwidth, ted
---

(traffic-engineering)=

# Traffic Engineering

{abbr}`TE (Traffic Engineering)` is a set of techniques for steering traffic
along paths different from the shortest path computed by the
{abbr}`IGP (Interior Gateway Protocol)`.

To enforce these paths, TE typically uses a form of source routing, such as
{abbr}`MPLS (Multiprotocol Label Switching)` labels or
{abbr}`SRv6 (Segment Routing over IPv6)` extension headers, combined with
path constraints, such as administrative groups or bandwidth requirements,
and a method to map traffic to TE paths.

Use the commands below to configure link-level TE attributes (administrative
groups and bandwidth) and enable TE in the IGP (specifically, IS-IS) so this
information is distributed across the network.

## Common link parameters

The following commands define link-level TE attributes that can be advertised
by both IS-IS and OSPF (not supported yet).

```{cfgcmd} set protocols traffic-engineering admin-group \<admin-group-name\> bit-position \<0-31\>

**Configure an administrative group and associate it with a bit position.**

These groups can then be referenced by the per-interface commands below.
```

```{note}
Two administrative groups cannot share the same `bit-position` value.
```

Example:

```none
set protocols traffic-engineering admin-group primary bit-position 0
set protocols traffic-engineering admin-group backup bit-position 1
```

```{cfgcmd} set protocols traffic-engineering interface \<ifname\> admin-group \<admin-group-name\>

**Configure an administrative group on the specified interface.**

You can configure multiple administrative groups on the same interface.
```

Example:

```none
set protocols traffic-engineering interface eth0 admin-group primary
```

```{cfgcmd} set protocols traffic-engineering interface \<ifname\> metric \<1-4294967295\>

**Configure the TE metric for the specified interface (distinct from the
OSPF/ISIS metric).**
```

Example:

```none
set protocols traffic-engineering interface eth0 metric 100
```

```{cfgcmd} set protocols traffic-engineering interface \<ifname\> max-bandwidth \<1-4294967295\>

**Configure the maximum bandwidth, in Mbps, for the specified interface.**
```

Example:

```none
set protocols traffic-engineering interface eth0 max-bandwidth 1000
```

```{cfgcmd} set protocols traffic-engineering interface \<ifname\> max-reservable-bandwidth \<1-4294967295\>

**Configure the maximum reservable bandwidth, in Mbps, for the specified
interface.**
```

Example:

```none
set protocols traffic-engineering interface eth0 max-reservable-bandwidth 800
```

## IS-IS TE configuration

The following commands enable TE for IS-IS.

```{cfgcmd} set protocols isis traffic-engineering enable

**Enable Traffic Engineering for IS-IS.**
```

Example:

```none
set protocols isis traffic-engineering enable
```

```{cfgcmd} set protocols isis traffic-engineering export

**Export the local {abbr}`TED (Traffic Engineering Database)` to other FRR
daemons.**
```

Example:

```none
set protocols isis traffic-engineering export
```

```{cfgcmd} set protocols isis traffic-engineering address \<ipv4-address\>

**Configure the IPv4 address used as the TE Router ID for MPLS-TE.**
```

Example:

```none
set protocols isis traffic-engineering address 198.51.100.1
```
