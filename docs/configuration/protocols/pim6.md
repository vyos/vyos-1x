---
myst:
  html_meta:
    description: |
      VyOS supports IPv6 multicast routing through PIMv6 (Protocol
      Independent Multicast for IPv6) and MLD (Multicast Listener
      Discovery) versions 1 and 2.
    keywords: pimv6, pim6, mld, multicast, ipv6, rendezvous point
---

(pimv6)=

# PIMv6

VyOS supports IPv6 multicast routing through
{abbr}`PIMv6 (Protocol Independent Multicast for IPv6)` and
{abbr}`MLD (Multicast Listener Discovery)` versions 1 and 2.

PIMv6 operates similarly to its IPv4 counterpart: it uses the existing unicast
IPv6 routing table for path decisions, and traffic from multicast sources is
forwarded toward a {abbr}`RP (Rendezvous Point)`. IPv6 multicast receivers use
MLD to signal their local router which groups they want to receive, and the
router uses PIMv6 to pull that traffic from the RP via a shared distribution
tree.

A working PIMv6 deployment requires:

- PIMv6 enabled on every interface participating in IPv6 multicast
  forwarding.
- The location of the Rendezvous Point (RP) declared identically on every
  router in the PIMv6 domain.
- MLD enabled on interfaces facing multicast receivers.

## Basic commands

Use the following commands for a basic PIMv6 setup.

```{cfgcmd} set protocols pim6 interface \<interface-name\>

**Enable PIMv6 on the specified PIMv6 interface.**

This command also enables MLD, allowing the router to process MLD queries
and reports from IPv6 multicast receivers.
```

Example:

```none
set protocols pim6 interface eth0
```

```{cfgcmd} set protocols pim6 interface \<interface-name\> mld disable

**Disable MLD on the specified PIMv6 interface.**

This command turns off MLD processing on the interface while keeping PIMv6
enabled.
```

Example:

```none
set protocols pim6 interface eth0 mld disable
```

## Tuning commands

You can also tune multicast with the following commands.

```{cfgcmd} set protocols pim6 interface \<interface-name\> mld interval \<1-65535\>

**Configure the MLD Query Interval, in seconds, on the specified
interface.**

This setting determines how often the router sends MLD queries to discover
which IPv6 multicast groups have active listeners on the attached network.

The default value is 125 seconds.
```

Example:

```none
set protocols pim6 interface eth0 mld interval 100
```

```{cfgcmd} set protocols pim6 interface \<interface-name\> mld join \<multicast-address\>

**Configure the interface to join a specific IPv6 multicast group.**
```

Example:

```none
set protocols pim6 interface eth0 mld join ff0e::db8:0:1234
```

```{cfgcmd} set protocols pim6 interface \<interface-name\> mld join \<multicast-address\> source \<source-address\>

**Configure the interface to join a specific (S,G) channel.**

A channel is identified by the combination of a source IPv6 address (S)
and a multicast IPv6 address (G).
```

Example:

```none
set protocols pim6 interface eth0 mld join ff3e::1234 source 2001:db8::1
```

```{cfgcmd} set protocols pim6 interface \<interface-name\> mld last-member-query-count \<1-255\>

**Configure the number of MLD Last Listener Queries the router sends on
the specified interface after a listener leaves a multicast group.**

The default value is 2.
```

Example:

```none
set protocols pim6 interface eth0 mld last-member-query-count 3
```

```{cfgcmd} set protocols pim6 interface \<interface-name\> mld last-member-query-interval \<100-6553500\>

**Configure the MLD Last Listener Query Interval, in milliseconds, on the
specified interface.**

This setting determines how long the router waits between Last Listener
Queries.

The default value is 1000 milliseconds.
```

Example:

```none
set protocols pim6 interface eth0 mld last-member-query-interval 500
```

```{cfgcmd} set protocols pim6 interface \<interface-name\> mld max-response-time \<100-6553500\>

**Configure the MLD maximum response delay, in milliseconds, on the
specified interface.**

This value is inserted in MLD queries and specifies the maximum time hosts
have to respond with a membership report. If no report is received within
the specified window, PIMv6 assumes there are no longer any active local
receivers and may time out the associated (\*,G) or (S,G) state.
```

Example:

```none
set protocols pim6 interface eth0 mld max-response-time 5000
```

```{cfgcmd} set protocols pim6 interface \<interface-name\> mld version \<1-2\>

**Configure the MLD version on the specified interface.**

The default version is 2.
```

Example:

```none
set protocols pim6 interface eth0 mld version 1
```

## Configuration example

To enable PIMv6 on interfaces eth0 and eth1 (which also enables MLD
automatically, allowing the router to process MLD queries and reports from
connected IPv6 multicast listeners):

```none
set protocols pim6 interface eth0
set protocols pim6 interface eth1
```

The following configuration explicitly joins the IPv6 multicast group
ff0e::db8:0:1234 on interface eth0, and the (S,G) channel
(2001:db8::1, ff3e::5678) on interface eth1:

```none
set protocols pim6 interface eth0 mld join ff0e::db8:0:1234
set protocols pim6 interface eth1 mld join ff3e::5678 source 2001:db8::1
```
