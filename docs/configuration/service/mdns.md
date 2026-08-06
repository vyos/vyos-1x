---
myst:
  html_meta:
    description: |
      The mDNS repeater is a VyOS service that retransmits mDNS packets
      between configured interfaces, so mDNS-based service discovery
      works across multiple broadcast domains on the same router. It
      re-originates each repeated packet from the sending interface's IP
      address.
    keywords: mdns, mdns repeater, multicast dns, dns-sd, vrrp
---

(mdns-repeater)=

# mDNS repeater

Devices that rely on {abbr}`mDNS (Multicast DNS)` discovery, such as
network printers, Apple AirPlay receivers, Chromecast devices, and
various IP-based home-automation devices, discover peers only within the
same broadcast domain (typically a single VLAN). This restriction exists
because mDNS uses the link-local multicast addresses `224.0.0.251`
(IPv4) and `ff02::fb` (IPv6), and routers do not forward packets sent to
these addresses.

The mDNS repeater bridges that gap. It retransmits mDNS packets received
on one configured interface to all other configured interfaces, so
mDNS-based discovery works across multiple broadcast domains on the same
VyOS router.

mDNS conveys an advertised host's IP address in the A (IPv4) or AAAA
(IPv6) resource records inside the packet, so a client reads the address
from those records rather than from the packet's source IP address. The
repeater therefore re-originates each packet from the sending
interface's IP address.

```{note}
Never run more than one mDNS repeater between the same networks, for
example on both routers of a VRRP pair, because the repeaters reflect
each other's packets and cause an mDNS packet storm.

In VRRP setups, configure `set service mdns repeater vrrp-disable` so a
router repeats mDNS only while its VRRP interfaces are in the MASTER
state.
```

## Configuration

```{cfgcmd} set service mdns repeater interface \<interface\>

**Configure an interface on which the mDNS repeater receives and
retransmits mDNS packets.**

Packets received on any configured interface are repeated to all other
configured interfaces.

Repeat the command to configure multiple interfaces.

At least two interfaces must be configured for a successful commit.
Every configured interface must have an IP address of each address
family enabled by `ip-version`.
```

Example:

```none
set service mdns repeater interface eth0
set service mdns repeater interface eth1
```

```{cfgcmd} set service mdns repeater disable

**Disable the mDNS repeater without removing its configuration.**
```

Example:

```none
set service mdns repeater disable
```

```{cfgcmd} set service mdns repeater ip-version \<ipv4 | ipv6 | both\>

**Configure the IP address family (or families) on which the mDNS
repeater listens and repeats mDNS packets.**

The default is `both`.
```

Example:

```none
set service mdns repeater ip-version ipv4
```

```{cfgcmd} set service mdns repeater allow-service \<service\>

**Restrict repeating to mDNS packets that match the specified service.**

The value matches either a {abbr}`DNS-SD (DNS-Based Service Discovery)`
service type (e.g., `_airplay._tcp`) or the name of the machine
providing the service.

Repeat the command to allow multiple services.

When unset, no service filter is applied, and all mDNS packets are
repeated.
```

Example:

```none
set service mdns repeater allow-service _airplay._tcp
```

```{cfgcmd} set service mdns repeater browse-domain \<domain\>

**Repeat mDNS packets for an additional domain, in addition to the
default local domain.**

Repeat the command to add multiple domains.
```

Example:

```none
set service mdns repeater browse-domain openthread.thread.home.arpa
```

```{cfgcmd} set service mdns repeater cache-entries \<0-65535\>

**Configure the maximum number of resource records cached per
interface.**

Larger values allow mDNS to work correctly in large LANs but increase
memory consumption.

Setting 0 disables caching. The default is 4096.
```

Example:

```none
set service mdns repeater cache-entries 8192
```

```{cfgcmd} set service mdns repeater vrrp-disable

**Exclude interfaces whose VRRP instance is not in MASTER state from
mDNS repeating.**

This option takes effect only when VRRP (`high-availability vrrp`) is
configured.

If fewer than two interfaces remain after exclusion, the repeater stops,
as it requires at least two interfaces to operate. VRRP state changes
automatically reconfigure the repeater.
```

Example:

```none
set service mdns repeater vrrp-disable
```

## Firewall recommendations

The repeater receives mDNS packets on the local system and re-originates
them locally. It does not route repeated packets. mDNS repeater traffic
therefore never traverses the firewall `forward` hook. Instead, it is
processed by the following hooks:

- `input`: mDNS packets received by the router.
- `output`: repeated mDNS packets sent by the router.

To control mDNS repeater traffic, define rules for the `input` and
`output` directions. Rules for the `forward` direction do not affect
this traffic.

```none
set firewall ipv4 input filter rule 10 action 'accept'
set firewall ipv4 input filter rule 10 destination address '224.0.0.251'
set firewall ipv4 input filter rule 10 destination port '5353'
set firewall ipv4 input filter rule 10 protocol 'udp'
set firewall ipv4 output filter rule 10 action 'accept'
set firewall ipv4 output filter rule 10 destination address '224.0.0.251'
set firewall ipv4 output filter rule 10 destination port '5353'
set firewall ipv4 output filter rule 10 protocol 'udp'
set firewall ipv6 input filter rule 10 action 'accept'
set firewall ipv6 input filter rule 10 destination address 'ff02::fb'
set firewall ipv6 input filter rule 10 destination port '5353'
set firewall ipv6 input filter rule 10 protocol 'udp'
set firewall ipv6 output filter rule 10 action 'accept'
set firewall ipv6 output filter rule 10 destination address 'ff02::fb'
set firewall ipv6 output filter rule 10 destination port '5353'
set firewall ipv6 output filter rule 10 protocol 'udp'
```

## Operation

```{opcmd} restart mdns repeater

**Restart the mDNS repeater service.**

If the service is not configured or disabled, or a configuration commit
is in progress, the command prints an error message and exits.
```

```{opcmd} show log mdns repeater

**Show the log of the mDNS repeater service.**
```

```{opcmd} monitor log mdns repeater

**Follow the log output of the mDNS repeater service in real time.**
```

## Example

The following example sets up an mDNS repeater between `eth0` and `eth1`
and restricts repeating to two service types: `_airplay._tcp` (Apple
AirPlay) and `_ipp._tcp` (network printing).

```none
set service mdns repeater interface 'eth0'
set service mdns repeater interface 'eth1'
set service mdns repeater allow-service '_airplay._tcp'
set service mdns repeater allow-service '_ipp._tcp'
```
