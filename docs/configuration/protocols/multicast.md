---
myst:
  html_meta:
    description: |
      Static multicast routes (mroutes) explicitly define the expected upstream
      path for Reverse-Path Forwarding (RPF) checks on arriving multicast
      traffic.
    keywords: multicast, mroute, rpf, mrib, rib
---

(routing-static-multicast)=

# Multicast

Static multicast routes (``mroutes``) explicitly define the expected
upstream path (either a next-hop IP address or an incoming interface) for
{abbr}`RPF (Reverse-Path Forwarding)` checks on arriving multicast traffic,
overriding the default RPF behavior.

When a multicast packet arrives, the router performs the RPF check against the
matching ``mroute`` in the dedicated **multicast** routing table
({abbr}`MRIB (Multicast Routing Information Base)`), rather than looking up
the standard **unicast** routing table
({abbr}`RIB (Routing Information Base)`).

If the packet arrives via the expected upstream path defined in the MRIB, the
RPF check passes, and the packet is forwarded toward the multicast receivers.
Otherwise, the packet is dropped.

Administrators build the MRIB by manually configuring ``mroutes``. The ZEBRA
routing daemon uses these entries exclusively for multicast RPF lookups. ZEBRA
neither evaluates ``mroutes`` in the unicast RIB nor installs them into the
kernel {abbr}`FIB (Forwarding Information Base)`.

## Configuration

Use the following commands to configure ``mroutes`` for a specific multicast
source subnet.

```{note}
Because ``mroutes`` bypass standard forwarding logic, they may cause
unpredictable network behavior. Use ``mroutes`` with caution; in most cases,
overriding the default RPF check is unnecessary.
```

### Next-hop mroutes

```{cfgcmd} set protocols static mroute \<subnet\> next-hop \<address\>

**Configure the next-hop IP address for the specified source subnet.**

When multicast traffic originates from this subnet, the router expects it to
arrive from the upstream neighbor at the specified IP address.

You can configure multiple next-hop IP addresses for the same source subnet.
```

Example:

```none
set protocols static mroute 192.0.2.0/24 next-hop 203.0.113.1
```

```{cfgcmd} set protocols static mroute \<subnet\> next-hop \<address\> distance \<1-255\>

**Configure the administrative distance for the mroute via the specified
next-hop IP address.**

``Mroutes`` with a lower administrative distance are prioritized over
``mroutes`` with a higher distance.

The allowed range is 1 to 255.
```

Example:

```none
set protocols static mroute 192.0.2.0/24 next-hop 203.0.113.1 distance 50
```

```{cfgcmd} set protocols static mroute \<subnet\> next-hop \<address\> disable

**Disable the mroute via the specified next-hop IP address.**

This command temporarily deactivates the ``mroute`` while preserving the
configured subnet, next-hop, and distance parameters.
```

Example:

```none
set protocols static mroute 192.0.2.0/24 next-hop 203.0.113.1 disable
```

### Interface mroutes

```{cfgcmd} set protocols static mroute \<subnet\> interface \<interface\>

**Configure the valid interface for the specified source subnet.**

When multicast traffic originates from this subnet, the router expects it to
arrive on the specified interface.

You can configure multiple interfaces for the same source subnet.
```

Example:

```none
set protocols static mroute 192.0.2.0/24 interface eth0
```

```{cfgcmd} set protocols static mroute \<subnet\> interface \<interface\> distance \<1-255\>

**Configure the administrative distance for the mroute via the specified
interface.**

``Mroutes`` with a lower administrative distance are prioritized over
``mroutes`` with a higher distance.

The allowed range is 1 to 255.
```

Example:

```none
set protocols static mroute 192.0.2.0/24 interface eth0 distance 30
```

```{cfgcmd} set protocols static mroute \<subnet\> interface \<interface\> disable

**Disable the mroute via the specified interface.**

This command temporarily deactivates the ``mroute`` while preserving the
configured subnet, interface, and distance parameters.
```

Example:

```none
set protocols static mroute 192.0.2.0/24 interface eth0 disable
```
