---
myst:
  html_meta:
    description: |
      Bidirectional Forwarding Detection (BFD) is a network protocol that
      detects communication failures between two connected routing devices
      in milliseconds.
    keywords: bfd, bidirectional forwarding detection, bgp, ospf, isis,
      multihop, echo-mode
---

(routing-bfd)=

# BFD

{abbr}`BFD (Bidirectional Forwarding Detection)` is a network protocol that
detects communication failures between two connected routing devices in mere
milliseconds — far faster than traditional routing protocols.
BFD does not route traffic itself. Instead, it provides rapid failure detection
for other protocols, such as {abbr}`BGP (Border Gateway Protocol)`,
{abbr}`OSPF (Open Shortest Path First)`, and static routes.

BFD is described and extended by the following RFCs: {rfc}`5880`, {rfc}`5881`
and {rfc}`5883`.

**How BFD works**

BFD establishes a session between two peers and exchanges rapid
{abbr}`UDP (User Datagram Protocol)` control packets at a negotiated interval
(e.g., 300 ms between consecutive packets). If a peer doesn't receive these
packets within the detection time (the negotiated interval multiplied by a
detection multiplier), BFD assumes a connection failure and notifies the
routing protocols.

## Configuration

```{cfgcmd} set protocols bfd peer \<address\>

**Configure the IPv4 or IPv6 address of the BFD peer.**

You can configure multiple BFD peers by specifying a different IP address
for each neighbor you want to monitor.
```

```{note}
For IPv6 peers, you must configure a source IP address or interface.
```

Example:

```none
set protocols bfd peer 198.51.100.33
```

```{cfgcmd} set protocols bfd peer \<address\> echo-mode

**Enable BFD echo transmission mode for the peer at the specified IP
address.**
```

Example:

```none
set protocols bfd peer 198.51.100.33 echo-mode
```

```{cfgcmd} set protocols bfd peer \<address\> multihop

**Configure the peer at the specified IP address as a multi-hop neighbor.**
```

```{note}
For BFD multi-hop peers, you must configure a local source IP address.
```

Example:

```none
set protocols bfd peer 198.51.100.33 multihop
set protocols bfd peer 198.51.100.33 source address 198.51.100.1
```

```{cfgcmd} set protocols bfd peer \<address\> source address \<address\>

**Configure the source IP address for the BFD session with the peer at the
specified IP address.**
```

```{note}
Configuring a source IP address or interface is mandatory for IPv6 BFD
peers.
```

Example:

```none
set protocols bfd peer 198.51.100.33 source address 198.51.100.1
```

```{cfgcmd} set protocols bfd peer \<address\> source interface \<interface\>

**Configure the source interface for the BFD session with the peer at the
specified IP address.**
```

```{note}
Configuring a source IP address or interface is mandatory for IPv6 BFD
peers.
```

Example:

```none
set protocols bfd peer 2001:db8::2 source interface eth0
```

```{cfgcmd} set protocols bfd peer \<address\> interval echo-interval \<10-60000\>

**Configure the minimum interval, in milliseconds, at which the local system
can receive echo packets from the peer at the specified IP address.**
```

Example:

```none
set protocols bfd peer 198.51.100.33 interval echo-interval 50
```

```{cfgcmd} set protocols bfd peer \<address\> interval multiplier \<2-255\>

**Configure the detection multiplier for the peer at the specified IP
address.**

BFD multiplies the negotiated interval by this value to calculate the
detection time — the period after which it declares the session down if no
control packets arrive.
```

Example:

```none
set protocols bfd peer 192.0.2.1 interval multiplier 3
```

```{cfgcmd} set protocols bfd peer \<address\> interval receive \<10-60000\>

**Configure the interval, in milliseconds, at which the local system can
receive BFD control packets from the peer at the specified IP address.**
```

Example:

```none
set protocols bfd peer 192.0.2.1 interval receive 300
```

```{cfgcmd} set protocols bfd peer \<address\> interval transmit \<10-60000\>

**Configure the interval, in milliseconds, at which you want the local
system to transmit BFD control packets to the peer at the specified IP
address.**
```

Example:

```none
set protocols bfd peer 192.0.2.1 interval transmit 300
```

```{cfgcmd} set protocols bfd peer \<address\> shutdown

**Disable the BFD session with the peer at the specified IP address.**
```

Example:

```none
set protocols bfd peer 198.51.100.33 shutdown
```

```{cfgcmd} set protocols bfd peer \<address\> minimum-ttl \<1-254\>

**Configure the minimum {abbr}`TTL (Time to Live)` value that incoming BFD
control packets must have to be accepted from the peer at the specified IP
address.**

BFD discards any packet whose TTL is below this threshold.
```

```{note}
This setting applies only to multi-hop sessions.
```

Example:

```none
set protocols bfd peer 192.0.2.1 minimum-ttl 250
```

```{cfgcmd} set protocols bfd peer \<address\> passive

**Configure the BFD session with the peer at the specified IP address to
operate in passive mode.**

In passive mode, the local system does not initiate the BFD session.
Instead, it waits to receive the first BFD control packet from the remote
peer.
```

```{note}
At least one of the two peers must remain in active mode for the session
to establish. If both peers are passive, neither will initiate, and the
session never establishes.
```

Example:

```none
set protocols bfd peer 198.51.100.33 passive
```

```{cfgcmd} set protocols bfd peer \<address\> profile \<profile\>

**Apply settings from a designated BFD profile to the peer at the specified
IP address.**
```

Example:

```none
set protocols bfd peer 192.0.2.1 profile datacenter-fast
```

```{cfgcmd} set protocols bfd peer \<address\> vrf \<vrf\>

**Bind the BFD session with the peer at the specified IP address to a
specific {abbr}`VRF (Virtual Routing and Forwarding)` instance.**
```

Example:

```none
set protocols bfd peer 192.0.2.1 vrf customer-a
```

### Enable BFD in BGP

```{cfgcmd} set protocols bgp neighbor \<neighbor\> bfd

**Enable BFD failure detection for the BGP session with the neighbor at the
specified IP address.**
```

Example:

```none
set protocols bgp neighbor 192.0.2.1 bfd
```

```{cfgcmd} set protocols bgp peer-group \<neighbor\> bfd

**Enable BFD failure detection for all neighbors in the specified BGP peer
group.**
```

Example:

```none
set protocols bgp peer-group INTERNAL-PEERS bfd
```

### Enable BFD in OSPF

```{cfgcmd} set protocols ospf interface \<interface\> bfd

**Enable BFD failure detection for OSPF neighbors discovered on the specified
interface.**

When OSPF forms an adjacency with a neighbor on this interface, it requests
BFD to establish a session with that neighbor.
```

Example:

```none
set protocols ospf interface eth0 bfd
```

```{cfgcmd} set protocols ospfv3 interface \<interface\> bfd

**Enable BFD failure detection for OSPFv3 neighbors discovered on the
specified interface.**

When OSPFv3 forms an adjacency with a neighbor on this interface, it
requests BFD to establish a session with that neighbor.
```

Example:

```none
set protocols ospfv3 interface eth0 bfd
```

### Enable BFD in IS-IS

```{cfgcmd} set protocols isis interface \<interface\> bfd

**Enable BFD failure detection for IS-IS neighbors discovered on the
specified interface.**

When IS-IS forms an adjacency with a neighbor on this interface, it requests
BFD to establish a session with that neighbor.
```

Example:

```none
set protocols isis interface eth0 bfd
```

## Operation

```{opcmd} show bfd peers

**Show all BFD peers.**
```

```none
vyos@vyos:~$ show bfd peers
BFD Peers:
        peer 198.51.100.33 vrf default
                ID: 4182341893
                Remote ID: 3267892964
                Active mode
                Status: up
                Uptime: 1 month(s), 16 hour(s), 29 minute(s), 38 second(s)
                Diagnostics: ok
                Remote diagnostics: ok
                Peer Type: configured
                RTT min/avg/max: 245/267/289 usec
                Local timers:
                        Detect-multiplier: 3
                        Receive interval: 300ms
                        Transmission interval: 300ms
                        Echo receive interval: 50ms
                        Echo transmission interval: disabled
                Remote timers:
                        Detect-multiplier: 3
                        Receive interval: 300ms
                        Transmission interval: 300ms
                        Echo receive interval: disabled

        peer 198.51.100.55 multihop local-address 198.51.100.1 vrf default
                ID: 3618932327
                Remote ID: 3312345688
                Active mode
                Minimum TTL: 254
                Status: up
                Uptime: 20 hour(s), 16 minute(s), 19 second(s)
                Diagnostics: ok
                Remote diagnostics: ok
                Peer Type: configured
                RTT min/avg/max: 1240/1289/1356 usec
                Local timers:
                        Detect-multiplier: 3
                        Receive interval: 300ms
                        Transmission interval: 300ms
                        Echo receive interval: 50ms
                        Echo transmission interval: disabled
                Remote timers:
                        Detect-multiplier: 3
                        Receive interval: 1000ms
                        Transmission interval: 1000ms
                        Echo receive interval: disabled
```

## BFD static route monitoring

A monitored static route is present in the
{abbr}`RIB (Routing Information Base)` only when the BFD session is up. If
the session goes down, the route is removed.

```{cfgcmd} set protocols static route \<subnet\> next-hop \<address\> bfd profile \<profile\>

**Configure BFD failure detection for a single-hop static route.**

BFD uses the next-hop IP address as the BFD peer IP address and applies
settings from the specified BFD profile.
```

Example:

```none
set protocols static route 10.0.0.0/24 next-hop 192.0.2.1 bfd profile datacenter-fast
```

```{cfgcmd} set protocols static route \<subnet\> next-hop \<address\> bfd multi-hop source-address \<address\>

**Configure BFD failure detection for a multi-hop static route.**

BFD uses the next-hop IP address as the BFD peer IP address and the
multi-hop source IP address as the local source IP for outgoing BFD packets.
```

Example:

```none
set protocols static route 10.0.0.0/24 next-hop 198.51.100.33 bfd multi-hop source-address 198.51.100.1
```

```{cfgcmd} set protocols static route6 \<subnet\> next-hop \<address\> bfd profile \<profile\>

**Configure BFD failure detection for a single-hop IPv6 static route.**

BFD uses the next-hop IPv6 address as the BFD peer IPv6 address and applies
settings from the specified BFD profile.
```

Example:

```none
set protocols static route6 2001:db8:1::/64 next-hop 2001:db8::1 bfd profile datacenter-fast
```

```{cfgcmd} set protocols static route6 \<subnet\> next-hop \<address\> bfd multi-hop source-address \<address\>

**Configure BFD failure detection for a multi-hop IPv6 static route.**

BFD uses the next-hop IPv6 address as the BFD peer IPv6 address and the
multi-hop source IPv6 address as the local source IPv6 address for outgoing
BFD packets.
```

Example:

```none
set protocols static route6 2001:db8:1::/64 next-hop 2001:db8:100::33 bfd multi-hop source-address 2001:db8::1
```
