---
myst:
  html_meta:
    description: |
      Protocol Independent Multicast (PIM) routes multicast traffic between
      routers using the existing unicast routing table for path decisions.
      VyOS supports PIM Sparse Mode (PIM-SM) and IGMP versions 2 and 3.
    keywords: pim, pim-sm, multicast, igmp, rendezvous point, rp
---

(pim)=

# PIM

{abbr}`PIM (Protocol Independent Multicast)` routes multicast traffic between
routers using the existing unicast routing table for path decisions. VyOS
supports PIM Sparse Mode (PIM-SM) and IGMP versions 2 and 3.

In PIM-SM, traffic from multicast sources is forwarded toward the
{abbr}`RP (Rendezvous Point)`. Multicast receivers use IGMP to signal their
local router which groups they want to receive, and the router uses PIM to
pull that traffic from the RP via a shared tree.

A working PIM-SM deployment requires:

- PIM enabled on every interface along the multicast path.
- The location of the RP declared identically on every router in the PIM
  domain.
- IGMP enabled on interfaces facing multicast receivers.

## Configuration

### PIM-SM

```{cfgcmd} set protocols pim ecmp

**Enable {abbr}`ECMP (Equal-Cost Multipath)` routing for multicast traffic.**

When a specific {abbr}`RPF (Reverse Path Forwarding)` lookup returns
multiple equal-cost next-hops, enabling this feature distributes (S,G)
multicast flows across all of them.

If ECMP is not enabled, PIM defaults to using only the first next-hop
returned by the RPF lookup.
```

Example:

```none
set protocols pim ecmp
```

```{cfgcmd} set protocols pim ecmp rebalance

**Enable automatic rebalancing of all PIM (S,G) multicast flows when an
ECMP next-hop interface fails.**

When ECMP is enabled, and one of the interfaces used by PIM goes down,
this feature forces PIM to redistribute all existing (S,G) flows across
the remaining equal-cost interfaces.

If rebalancing is not configured, PIM only reroutes the specific flows
that were actively using the failed interface.
```

Example:

```none
set protocols pim ecmp rebalance
```

```{cfgcmd} set protocols pim join-prune-interval \<1-65535\>

**Configure the interval, in seconds, at which PIM sends Join/Prune
messages to upstream neighbors.**

The default interval is 60 seconds. Setting a value below 60 seconds can
negatively impact convergence at scale.
```

Example:

```none
set protocols pim join-prune-interval 120
```

```{cfgcmd} set protocols pim keep-alive-timer \<1-65535\>

**Configure the keep-alive timeout interval, in seconds, for (S,G)
multicast flow state.**
```

```{note}
Some hardware cannot detect traffic flowing in intervals shorter than 30
seconds. For such hardware, ensure the value is set to 31 seconds or
higher.
```

Example:

```none
set protocols pim keep-alive-timer 60
```

```{cfgcmd} set protocols pim packets \<1-255\>

**Configure the number of incoming PIM packets processed consecutively
from a neighbor before the system moves to the next task.**

The default value is 3 packets. This command is only useful in
deployments with a high number of PIM control packets.
```

Example:

```none
set protocols pim packets 10
```

```{cfgcmd} set protocols pim register-accept-list prefix-list \<prefix-list\>

**Configure a prefix-list to filter incoming PIM Register messages.**

When PIM receives a Register packet, the multicast source IP address is
evaluated against the specified prefix-list. If the source IP address is
permitted, normal PIM processing continues. If the source IP address is
denied, a Register-Stop message is sent to the sender.
```

Example:

```none
set protocols pim register-accept-list prefix-list MULTICAST-SOURCES
```

```{cfgcmd} set protocols pim register-suppress-time \<1-65535\>

**Configure the duration, in seconds, during which a
{abbr}`FHR (First-Hop Router)` suppresses sending PIM Register messages.**
```

Example:

```none
set protocols pim register-suppress-time 60
```

```{cfgcmd} set protocols pim rp address \<ip-address\> group \<prefix\>

**Configure a Rendezvous Point (RP) for the specified multicast group
range.**

To use PIM, you must configure an RP to receive Join messages. VyOS
currently supports only static RP configuration.

The `<address>` parameter defines the RP's IP address, and the `<group>`
parameter defines the prefix of the multicast group range served by this
RP.

A single RP can serve multiple group ranges. Repeat the command with
different `<group>` prefixes to map several ranges to the same RP.
```

Example:

% stop_vyoslinter
```none
set protocols pim rp address 192.0.2.1 group 239.0.0.0/8
```
% start_vyoslinter

```{cfgcmd} set protocols pim rp keep-alive-timer \<1-65535\>

**Configure the keep-alive timeout interval, in seconds, for (S,G)
multicast flow state at the Rendezvous Point (RP).**

This value must be at least equal to the register-suppression-time;
otherwise, the RP may time out the (S,G) state before the next
Null-Register message arrives from the FHR.

When a Register-Stop is sent, the KAT(S,G) at the RP is set to the maximum
of the global Keepalive_Period and the RP_Keepalive_Period.

The default value is 210 seconds.

See [RFC 7761, Section 4.1](https://datatracker.ietf.org/doc/html/rfc7761#section-4.1)
for details.
```

```{note}
As some hardware platforms cannot detect data flowing in intervals shorter
than 30 seconds, ensure the value is set to 31 seconds or higher.
```

Example:

```none
set protocols pim rp keep-alive-timer 300
```

```{cfgcmd} set protocols pim no-v6-secondary

**Disable sending IPv6 secondary addresses in PIM Hello messages.**

By default, PIM Hello messages include all IPv6 secondary addresses
configured on the interface, allowing PIM neighbors to use them as IPv6
next-hops for RPF lookups.
```

Example:

```none
set protocols pim no-v6-secondary
```

```{cfgcmd} set protocols pim spt-switchover infinity-and-beyond prefix-list \<list\>

**On the {abbr}`LHR (Last-Hop Router)`, suppress the switchover from the
shared (*,G) tree to the source-specific (S,G)
{abbr}`SPT (Shortest-Path Tree)`.**

The optional `prefix-list` controls which groups are affected: groups
matched by a *permit* entry stay on the shared tree, groups matched by a
*deny* entry switch over normally. Without a prefix-list, the suppression
applies to all groups.
```

Example:

```none
set protocols pim spt-switchover infinity-and-beyond
set protocols pim spt-switchover infinity-and-beyond prefix-list SHARED-TREE-GROUPS
```

```{cfgcmd} set protocols pim ssm prefix-list \<list\>

**Configure a prefix-list with the range of multicast group IP addresses
that operate in {abbr}`SSM (Source-Specific Multicast)` mode.**
```

Example:

```none
set protocols pim ssm prefix-list SSM-RANGE
```

#### Interface-specific commands

```{cfgcmd} set protocols pim interface \<interface\> bfd

**Enable {abbr}`BFD (Bidirectional Forwarding Detection)` for each PIM
neighbor discovered on the specified interface.**

When BFD detects a link failure, the PIM neighbor relationship is torn
down, and all associated multicast (S,G) entries are removed.
```

Example:

```none
set protocols pim interface eth0 bfd
```

```{cfgcmd} set protocols pim interface \<interface\> bfd profile \<name\>

**Apply the specified BFD profile to BFD sessions on this PIM interface.**
```

Example:

```none
set protocols pim interface eth0 bfd profile fast-failover
```

```{cfgcmd} set protocols pim interface \<interface\> dr-priority \<1-4294967295\>

**Configure the {abbr}`DR (Designated Router)` priority for the specified
interface.**

The router with the highest interface priority is elected as the DR for a
LAN segment.
```

Example:

```none
set protocols pim interface eth0 dr-priority 100
```

```{cfgcmd} set protocols pim interface \<interface\> hello \<1-180\>

**Configure the PIM Hello interval, in seconds, for the specified
interface.**

PIM Hello messages are sent periodically on the interface to discover and
maintain PIM neighbor relationships. The hold time (the duration after
which a neighbor is considered dead if no Hello is received) is calculated
based on the Hello interval.
```

Example:

```none
set protocols pim interface eth0 hello 10
```

```{cfgcmd} set protocols pim interface \<interface\> no-bsm

**Disable processing of PIM {abbr}`BSMs (Bootstrap Messages)` on the
specified interface.**
```

Example:

```none
set protocols pim interface eth0 no-bsm
```

```{cfgcmd} set protocols pim interface \<interface\> no-unicast-bsm

**Disable processing of unicast PIM BSMs on this interface.**
```

Example:

```none
set protocols pim interface eth0 no-unicast-bsm
```

```{cfgcmd} set protocols pim interface \<interface\> passive

**Disable sending and receiving PIM control packets on this interface.**
```

Example:

```none
set protocols pim interface eth0 passive
```

```{cfgcmd} set protocols pim interface \<interface\> source-address \<ip-address\>

**Configure the source IP address PIM uses for control messages sent on
the specified interface.**

This command is useful when multiple IP addresses are configured on a
single interface.
```

Example:

```none
set protocols pim interface eth0 source-address 192.0.2.10
```

### IGMP

```{cfgcmd} set protocols pim igmp watermark-warning \<1-65535\>

**Configure watermark warning generation based on the number of joined
IGMP groups.**

When the total number of joined IGMP groups reaches this specified limit,
the router generates a warning.
```

Example:

```none
set protocols pim igmp watermark-warning 500
```

#### Interface-specific commands

```{cfgcmd} set protocols pim interface \<interface\> igmp

**Enable IGMP on the specified interface.**
```

Example:

```none
set protocols pim interface eth0 igmp
```

```{cfgcmd} set protocols pim interface \<interface\> igmp disable

**Administratively disable IGMP on the specified interface without removing
the existing IGMP configuration.**
```

Example:

```none
set protocols pim interface eth0 igmp disable
```

```{cfgcmd} set protocols pim interface \<interface\> igmp join \<multicast-address\> source-address \<IP-address\>

**Configure the interface to join a specific (S,G) channel.**

Specify both the multicast IP address (G) and the source IP address (S).
Each command joins one (S,G) channel. To join multiple channels sharing
the same group, repeat the command with different `source-address` values.
```

Example:

% stop_vyoslinter
```none
set protocols pim interface eth0 igmp join 232.1.1.100 source-address 192.0.2.50
set protocols pim interface eth0 igmp join 232.1.1.100 source-address 192.0.2.51
```
% start_vyoslinter

```{cfgcmd} set protocols pim interface \<interface\> igmp query-interval \<1-1800\>

**Configure the IGMP Host Query Interval, in seconds, on the specified
interface.**

This setting determines the interval between IGMP queries sent by the
router to discover which multicast groups have active listeners on the
attached network.
```

Example:

```none
set protocols pim interface eth1 igmp query-interval 125
```

```{cfgcmd} set protocols pim interface \<interface\> igmp query-max-response-time \<10-250\>

**Configure the IGMP maximum query response time, in deciseconds, on the
specified interface.**

This value is inserted in IGMP queries and specifies the maximum time
hosts have to respond with a membership report. If no report is received
within the specified window, PIM assumes there are no longer any active
local receivers and may time out the associated (\*,G) or (S,G) state
(see [RFC 7761, Section 4.1](https://datatracker.ietf.org/doc/html/rfc7761#section-4.1)).
```

Example:

```none
set protocols pim interface eth0 igmp query-max-response-time 50
```

```{cfgcmd} set protocols pim interface \<interface\> igmp version \<2-3\>

**Configure the IGMP version on the specified interface.**

The default version is 3.
```

Example:

```none
set protocols pim interface eth0 igmp version 2
```

## Example

The following example demonstrates a basic PIM Sparse Mode (PIM-SM) multicast
deployment across three routers, showing how to configure each router's role
within a multicast domain. Together, the three routers form a complete
multicast distribution path from sources to receivers, with one router acting
as the Rendezvous Point (RP).

### Topology and roles

- Router 1 is the {abbr}`LHR (Last-Hop Router)`.
- Router 3 is the {abbr}`RP (Rendezvous Point)`.
- Router 2 is the {abbr}`FHR (First-Hop Router)`.

**Router 1:**

```none
set interfaces ethernet eth2 address '198.51.100.1/30'
set interfaces ethernet eth1 address '192.0.2.1/24'
set protocols ospf area 0 network '198.51.100.0/30'
set protocols ospf area 0 network '192.0.2.0/24'
set protocols pim interface eth1
set protocols pim interface eth1 igmp
set protocols pim interface eth2
set protocols pim rp address 203.0.113.1 group '224.0.0.0/4'
```

**Router 3:**

```none
set interfaces dummy dum0 address '203.0.113.1/32'
set interfaces ethernet eth0 address '198.51.100.2/30'
set interfaces ethernet eth1 address '198.51.100.5/30'
set protocols ospf area 0 network '198.51.100.0/30'
set protocols ospf area 0 network '203.0.113.1/32'
set protocols ospf area 0 network '198.51.100.4/30'
set protocols pim interface dum0
set protocols pim interface eth0
set protocols pim interface eth1
set protocols pim rp address 203.0.113.1 group '224.0.0.0/4'
```

**Router 2:**

```none
set interfaces ethernet eth1 address '203.0.113.129/25'
set interfaces ethernet eth2 address '198.51.100.6/30'
set protocols ospf area 0 network '203.0.113.128/25'
set protocols ospf area 0 network '198.51.100.4/30'
set protocols pim interface eth1
set protocols pim interface eth2
set protocols pim rp address 203.0.113.1 group '224.0.0.0/4'
```
