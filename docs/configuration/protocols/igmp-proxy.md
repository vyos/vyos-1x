---
myst:
  html_meta:
    description: |
      The IGMP proxy enables routers to forward multicast traffic, such as
      IPTV or video streams, between different networks like home networks
      and ISPs.
    keywords: igmp, igmp-proxy, multicast, iptv, quickleave, alt-subnet
---

(igmp-proxy)=

# IGMP proxy

The {abbr}`IGMP (Internet Group Management Protocol)` proxy enables routers to
forward multicast traffic, such as IPTV or video streams, between different
networks, such as home networks and ISPs. The IGMP proxy relies on an upstream
interface that faces upstream multicast sources, and one or more downstream
interfaces that face local networks or hosts and forward traffic to requesting
clients.

IGMP proxy configuration requires exactly one upstream interface and at least
one downstream interface.

## Configuration

```{cfgcmd} set protocols igmp-proxy interface \<interface\> role \<upstream | downstream\>

**Configure the operational role for the specified IGMP proxy interface.**

- ``upstream``: Communicates with upstream multicast sources to retrieve the
  multicast traffic. A valid configuration requires exactly one upstream
  interface.
- ``downstream``: Communicates with downstream local subnets or hosts to
  distribute the requested traffic. A valid configuration requires at least
  one downstream interface.
```

Example:

```none
set protocols igmp-proxy interface eth0 role upstream
set protocols igmp-proxy interface eth1 role downstream
```

```{cfgcmd} set protocols igmp-proxy interface \<interface\> alt-subnet \<network\>

**Configure an allowed remote subnet for incoming multicast traffic
on the specified IGMP proxy interface**

By default, the IGMP proxy accepts multicast traffic only from directly
connected subnets. If a multicast source resides on a remote network, you
must explicitly define the allowed remote subnet to permit the traffic.

You can configure multiple remote subnets for an **upstream** IGMP proxy
interface.

Upstream interfaces frequently require this configuration because multicast
sources typically reside on external subnets.
```

Example:

```none
set protocols igmp-proxy interface eth0 alt-subnet 10.0.0.0/8
```

```{cfgcmd} set protocols igmp-proxy interface \<interface\> whitelist \<network\>

**Configure a permitted destination network for multicast traffic requests
on the specified IGMP proxy interface.**

By default, the IGMP proxy accepts requests for all multicast destination
networks. When you define a whitelist, the IGMP proxy forwards requests only
for the specified multicast networks.

You can configure multiple whitelist entries per **downstream** IGMP proxy
interface.
```

Example:

```none
set protocols igmp-proxy interface eth1 whitelist 239.0.0.0/8
```

```{cfgcmd} set protocols igmp-proxy interface \<interface\> threshold \<1-255\>

**Configure the Time-to-Live (TTL) threshold for the specified IGMP proxy
interface.**

The IGMP proxy drops any multicast packet with a TTL value lower than the
configured threshold.
```

Example:

```none
set protocols igmp-proxy interface eth0 threshold 5
```

```{cfgcmd} set protocols igmp-proxy disable-quickleave

**Disable quickleave mode for the IGMP proxy.**

If disabled, the IGMP proxy does not send an upstream Leave message upon
receiving a downstream Leave message, preventing the immediate termination
of upstream multicast traffic. The IGMP proxy also stops querying downstream
interfaces for membership reports. If a downstream client submits a new
report, the IGMP proxy discards the message and does not resume the delivery
of requested traffic.
```

```{note}
Disabling quickleave mode forces the IGMP proxy to act exactly like a
standard multicast client on the upstream interface.
```

```{note}
Disabling quickleave mode increases the risk of network bandwidth
saturation.
```

Example:

```none
set protocols igmp-proxy disable-quickleave
```

```{cfgcmd} set protocols igmp-proxy disable

**Disable the IGMP proxy on the router.**
```

Example:

```none
set protocols igmp-proxy disable
```

## Operation

```{opcmd} restart igmp-proxy

Restart the IGMP proxy process.
```

## Example

In this example, the local LAN on interface eth1 operates behind NAT. To allow
local clients to receive multicast traffic originating from the 198.51.100.0/24
source network on the WAN interface (eth0), configure the IGMP proxy as
follows:

```none
set protocols igmp-proxy interface eth0 role upstream
set protocols igmp-proxy interface eth0 alt-subnet 198.51.100.0/24
set protocols igmp-proxy interface eth1 role downstream
```

