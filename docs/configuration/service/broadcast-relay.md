---
myst:
  html_meta:
    description: |
      UDP broadcast relay is a VyOS service that forwards UDP broadcast
      packets between subnets. It enables applications that rely on
      broadcast-based peer or service discovery to operate across
      Layer 3 boundaries.
    keywords: udp broadcast relay, broadcast forwarding, service discovery
---

(udp-broadcast-relay)=

# UDP broadcast relay

Certain applications use UDP broadcasts to discover peers or services
within a local subnet. Since IP routers do not forward broadcast packets
between subnets, applications in different subnets cannot use broadcast
discovery.

The UDP broadcast relay service bridges this gap. When an application
sends a UDP broadcast packet to discover peers or services, the relay
listens for that message on any of its configured interfaces and
rebroadcasts it on the others, reaching the subnets they connect to.

The unit of configuration is a UDP relay instance. Each instance is
defined by the following settings:

- a numeric ID in the range 1–99 that identifies the instance
- a single UDP port number that the instance relays
- two or more interfaces across which the instance operates

Every interface in the instance must be assigned an IPv4 address.

```{note}
Multiple routers may run UDP broadcast relay on a shared subnet,
provided that any routers relaying the same UDP port use the same
instance ID. Multiple routers relaying the same UDP port with different
instance IDs will produce a relay loop and a packet storm.
```

## Configuration

```{cfgcmd} set service broadcast-relay id \<1-99\> description \<description\>

**Configure a description for the specified relay instance.**
```

Example:

```none
set service broadcast-relay id 1 description 'SONOS discovery'
```

```{cfgcmd} set service broadcast-relay id \<1-99\> interface \<interface\>

**Add an interface to the specified relay instance.**

Repeat the command to add additional interfaces.
```

```{note}
At least two interfaces must be configured per instance, and each
interface must be assigned an IPv4 address.
```

Example:

```none
set service broadcast-relay id 1 interface eth1
set service broadcast-relay id 1 interface eth2
```

```{cfgcmd} set service broadcast-relay id \<1-99\> address \<ipv4-address\>

**Configure the source IPv4 address used in forwarded packets.**

If unset, the original sender's source IP address is preserved.
```

Example:

```none
set service broadcast-relay id 1 address 192.0.2.1
```

```{cfgcmd} set service broadcast-relay id \<1-99\> port \<1-65535\>

**Configure the UDP destination port for the specified relay instance.**

The relay listens for broadcasts on this port on any of the instance's
interfaces and forwards them to the same port on the others.
```

```{note}
This setting is mandatory for each relay instance. Otherwise, the
commit is rejected.
```

Example:

```none
set service broadcast-relay id 1 port 1900
```

```{cfgcmd} set service broadcast-relay id \<1-99\> disable

**Administratively disable the specified relay instance while preserving
its configuration.**
```

Example:

```none
set service broadcast-relay id 1 disable
```

```{cfgcmd} set service broadcast-relay disable

**Administratively disable the UDP broadcast relay service on the router
without removing its configured instances.**
```

Example:

```none
set service broadcast-relay disable
```

## Example

The following example shows how to configure the UDP broadcast relay to
forward broadcasts on UDP port 1900 between `eth1`, `eth2`, and `eth3`.
A broadcast received on any of these interfaces is forwarded to the
other two. Each interface must already have an IPv4 address configured.

```none
set service broadcast-relay id 1 description 'SONOS discovery'
set service broadcast-relay id 1 port '1900'
set service broadcast-relay id 1 interface 'eth1'
set service broadcast-relay id 1 interface 'eth2'
set service broadcast-relay id 1 interface 'eth3'
```
