---
myst:
  html_meta:
    description: |
      DHCP relay forwards DHCP requests from clients on one network to
      a DHCP server on another network. VyOS provides independent
      relay services for IPv4 and IPv6.
    keywords: dhcp-relay, dhcpv6-relay, dhcp, dhcpv6, relay-agent
---

(dhcp-relay)=

# DHCP relay

A DHCP relay agent enables a single DHCP server to serve clients on
remote subnets, eliminating the need for a separate server on each
subnet.

The DHCP relay agent receives client requests on one interface,
forwards them as unicasts to the designated server on another network,
and delivers the server's replies back to the originating clients.

VyOS provides two independent DHCP relay services:

- `service dhcp-relay`: Relays messages between IPv4 clients and
  servers.
- `service dhcpv6-relay`: Relays messages between IPv6 clients and
  servers.

The two services are configured separately and share no settings. On a
dual-stack network where clients of both address families need DHCP,
configure both.

## IPv4 relay

### Configuration

```{cfgcmd} set service dhcp-relay listen-interface \<interface\>

**Configure a listen interface on which the DHCPv4 relay receives
client broadcast requests.**

Repeat the command to configure multiple listen interfaces.
```

```{note}
At least one `listen-interface` and one `upstream-interface` must be
configured for a successful commit.
```

Example:

```none
set service dhcp-relay listen-interface eth1
```

```{cfgcmd} set service dhcp-relay upstream-interface \<interface\>

**Configure an upstream interface through which the DHCPv4 relay
forwards client requests toward the DHCP server.**

Repeat the command to configure multiple upstream interfaces.
```

```{note}
At least one `listen-interface` and one `upstream-interface` must be
configured for a successful commit.
```

Example:

```none
set service dhcp-relay upstream-interface eth2
```

```{cfgcmd} set service dhcp-relay server \<ipv4-address\>

**Configure the IPv4 address of a DHCPv4 server to which the relay
forwards client requests.**

Repeat the command to forward client requests to multiple DHCPv4
servers.
```

```{note}
At least one DHCPv4 server must be configured for a successful commit.
```

Example:

```none
set service dhcp-relay server 203.0.113.4
```

```{cfgcmd} set service dhcp-relay interface \<interface\>

**Configure an interface that participates in DHCPv4 relaying.**

Interfaces configured under this legacy command operate
bidirectionally, receiving DHCPv4 client broadcasts and forwarding
requests to the server.
```

```{warning}
This command is deprecated and remains available only to support
existing configurations. New deployments should use
`listen-interface` and `upstream-interface`, which cannot be combined
with this command. A deprecation warning appears upon commit.
```

```{note}
The loopback interface (`lo`) is not accepted as a valid value for
this command.
```

Example:

```none
set service dhcp-relay interface eth1
set service dhcp-relay interface eth2
```

```{cfgcmd} set service dhcp-relay disable

**Administratively disable the DHCPv4 relay service without removing
its configuration.**
```

Example:

```none
set service dhcp-relay disable
```

### Relay options

```{cfgcmd} set service dhcp-relay relay-options hop-count \<1-255\>

**Configure the DHCPv4 hop count at which relayed packets are
discarded.**

A DHCPv4 relay that receives a client message sets the hop count to
0. Each subsequent DHCPv4 relay along the packet path increments it.
Packets whose hop count has reached the specified value are silently
dropped.

The default is 10.
```

Example:

```none
set service dhcp-relay relay-options hop-count 4
```

```{cfgcmd} set service dhcp-relay relay-options max-size \<64-1400\>

**Configure the maximum size, in bytes, that a DHCPv4 packet may
reach with the Relay Agent Information option added.**

If the packet with the appended option exceeds this size, the option
is omitted, and the packet is forwarded without it.

The default is 576.
```

Example:

```none
set service dhcp-relay relay-options max-size 1400
```

```{cfgcmd} set service dhcp-relay relay-options relay-agents-packets \<append | discard | forward | replace\>

**Configure the policy applied to incoming DHCPv4 packets that
already carry a Relay Agent Information option:**

- `append`: Adds the local Relay Agent Information option while
  preserving the existing Relay Agent Information option.
- `discard`: Drops packets carrying a Relay Agent Information option.
- `forward`: Forwards packets with their existing Relay Agent
  Information option unchanged.
- `replace`: Strips the existing Relay Agent Information option and
  inserts the local Relay Agent Information option.

The default is `forward`.
```

Example:

```none
set service dhcp-relay relay-options relay-agents-packets discard
```

### Operation

```{opcmd} restart dhcp relay-agent

Restart the DHCPv4 relay service.
```

### Example

The following configuration forwards DHCP client requests received on
`eth1` (the client-facing interface) via `eth2` (the server-facing
interface) to a DHCP server at `203.0.113.4`. Packets that already
contain Relay Agent Information are dropped, so that only requests
originating directly from clients are forwarded.

:::{figure} /_static/images/service_dhcp-relay01.webp
:alt: DHCPv4 relay topology
:scale: 80 %
DHCPv4 relay topology
:::

```none
set interfaces ethernet eth1 address '192.0.2.1/24'
set interfaces ethernet eth2 address '198.51.100.1/24'
set service dhcp-relay listen-interface 'eth1'
set service dhcp-relay upstream-interface 'eth2'
set service dhcp-relay server '203.0.113.4'
set service dhcp-relay relay-options relay-agents-packets discard
```

The equivalent configuration using the deprecated `interface` syntax,
retained only for backward compatibility, is:

```none
set interfaces ethernet eth1 address '192.0.2.1/24'
set interfaces ethernet eth2 address '198.51.100.1/24'
set service dhcp-relay interface 'eth1'
set service dhcp-relay interface 'eth2'
set service dhcp-relay server '203.0.113.4'
set service dhcp-relay relay-options relay-agents-packets discard
```

## IPv6 relay

(dhcp-relay-ipv6-configuration)=

### Configuration

```{cfgcmd} set service dhcpv6-relay listen-interface \<interface\>

**Configure a listen interface on which the DHCPv6 relay receives
client multicast requests.**

The interface must already have a global unicast IPv6 address
assigned.

Repeat the command to configure multiple listen interfaces.
```

```{note}
At least one `listen-interface` and one `upstream-interface` must be
configured for a successful commit.
```

Example:

```none
set service dhcpv6-relay listen-interface eth1
```

```{cfgcmd} set service dhcpv6-relay listen-interface \<interface\> address \<ipv6-address\>

**Configure the IPv6 address the DHCPv6 relay uses to identify the
client-facing network to the DHCPv6 server.**

The address must be a non-link-local IPv6 address already assigned to
the specified listen interface.

If the address is not set, the DHCPv6 relay uses the first
non-link-local IPv6 address found on that listen interface.
```

Example:

```none
set service dhcpv6-relay listen-interface eth1 address 2001:db8:1::1
```

```{cfgcmd} set service dhcpv6-relay upstream-interface \<interface\> address \<ipv6-address\>

**Configure the IPv6 address of a DHCPv6 server (or another relay
agent) to which the DHCPv6 relay forwards client messages via the
specified upstream interface.**

Repeat the command to forward client messages to multiple servers (or
relay agents).
```

```{note}
At least one server (or relay agent) address must be configured for
each upstream interface for a successful commit.
```

Example:

```none
set service dhcpv6-relay upstream-interface eth2 address 2001:db8:2::4
```

(dhcp-relay-ipv6-options)=

```{cfgcmd} set service dhcpv6-relay disable

**Administratively disable the DHCPv6 relay service without removing
its configuration.**
```

Example:

```none
set service dhcpv6-relay disable
```

(dhcp-relay-v6-options)=

### Relay options

```{cfgcmd} set service dhcpv6-relay max-hop-count \<1-255\>

**Configure the DHCPv6 hop count at which relayed packets are
discarded.**

A DHCPv6 relay that receives a client message sets the hop count to
0. Each subsequent DHCPv6 relay along the packet path increments it.
Packets whose hop count has reached the specified value are silently
dropped.

The default is 10.
```

Example:

```none
set service dhcpv6-relay max-hop-count 4
```

```{cfgcmd} set service dhcpv6-relay use-interface-id-option

**Enable insertion of the Interface-ID option into every
Relay-forward message.**

The Interface-ID option is inserted automatically whenever more than
one listen interface is configured on a relay, regardless of this
setting.
```

Example:

```none
set service dhcpv6-relay use-interface-id-option
```

(dhcp-relay-ipv6-op-cmd)=

### Operation

```{opcmd} restart dhcpv6 relay-agent

Restart the DHCPv6 relay service.
```

(dhcp-relay-ipv6-example)=

### Example

The following configuration forwards DHCPv6 client requests received
on `eth1` (the client-facing interface) via `eth2` (the server-facing
interface) to a DHCPv6 server at `2001:db8:2::4`.

:::{figure} /_static/images/service_dhcpv6-relay01.webp
:alt: DHCPv6 relay topology
:scale: 80 %
DHCPv6 relay topology
:::

```none
set interfaces ethernet eth1 address '2001:db8:1::1/64'
set interfaces ethernet eth2 address '2001:db8:2::1/64'
set service dhcpv6-relay listen-interface 'eth1'
set service dhcpv6-relay upstream-interface 'eth2' address '2001:db8:2::4'
```
