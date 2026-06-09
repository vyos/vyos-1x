---
myst:
  html_meta:
    description: |
      OpenFabric is a routing protocol derived from IS-IS that provides
      link-state routing with optimized flooding, making it well-suited
      for spine-leaf topologies.
    keywords: openfabric, isis, link-state, spine-leaf, fabric, net, lsp
---

(openfabric)=

# OpenFabric

% stop_vyoslinter
OpenFabric, specified in [draft-white-openfabric-06.txt](https://datatracker.ietf.org/doc/html/draft-white-openfabric-06),
% start_vyoslinter
is a routing protocol derived from IS-IS. It provides link-state routing with
optimized flooding, making it well-suited for spine-leaf topologies.

OpenFabric is a dual-stack protocol. A single instance can simultaneously
route both IPv4 and IPv6 traffic.

## Configuration

### Mandatory settings

Each OpenFabric router must be configured with a unique
{abbr}`NET (Network Entity Title)`, the
{abbr}`CLNS (Connectionless Network Service)` equivalent of a Router ID. The
6-byte system identifier portion of the NET must be unique across the fabric.

```{cfgcmd} set protocols openfabric net \<network-entity-title\>

**Configure the Network Entity Title (NET) for the router.**

A typical NET looks like ``49.0001.1921.6800.1002.00``.

The NET consists of the following parts:

- **{abbr}`AFI (Authority and Format Identifier)`** (`49`): OpenFabric
  conventionally uses AFI value 49 for private addressing.
- **Area identifier** (`0001`): The area number within the fabric (in this
  case, Area 1).
- **System identifier** (`1921.6800.1002`): Uniquely identifies the router
  within the fabric. We recommend deriving this value from the router IP
  address or MAC address. To construct the system identifier from an IPv4
  address (for example, `192.168.1.2`):

  - Pad each octet with leading zeros: `192.168.1.2` → `192.168.001.002`.
  - Regroup the digits into three 4-digit blocks: `192.168.001.002` →
    `1921.6800.1002`.

- **NET selector** (`00`): Must always be `00` to indicate the local system.
```

Example:

```none
set protocols openfabric net 49.0001.1921.6800.1002.00
```

```{cfgcmd} set protocols openfabric domain \<name\> interface \<interface\> address-family \<ipv4|ipv6\>

**Configure the named OpenFabric domain on a specific interface for the
given address family (IPv4 or IPv6).**

For dual-stack operation, run the command twice: once with `ipv4` and once
with `ipv6`.
```

Example:

```none
set protocols openfabric domain fabric1 interface eth1 address-family ipv4
set protocols openfabric domain fabric1 interface eth1 address-family ipv6
```

### OpenFabric global configuration

```{cfgcmd} set protocols openfabric domain \<name\> domain-password \<plaintext-password|md5\> \<password\>

**Configure the authentication password for the specified OpenFabric
domain.**

The password can be specified as either plain text or
an {abbr}`MD5 (Message-Digest Algorithm 5)` hash.
```

Example:

```none
set protocols openfabric domain fabric1 domain-password md5 'shared-secret'
```

```{cfgcmd} set protocols openfabric domain \<name\> purge-originator

**Enable {abbr}`POI (Purge Originator Identification)` for the specified
OpenFabric domain.**

POI is defined in RFC 6232.
```

Example:

```none
set protocols openfabric domain fabric1 purge-originator
```

```{cfgcmd} set protocols openfabric domain \<name\> set-overload-bit

**Configure the overload bit for the specified OpenFabric domain.**

This instructs other routers in the domain not to use this router for
transit traffic.
```

Example:

```none
set protocols openfabric domain fabric1 set-overload-bit
```

```{cfgcmd} set protocols openfabric domain \<name\> log-adjacency-changes

**Enable logging of adjacency state changes in the specified OpenFabric
domain.**
```

Example:

```none
set protocols openfabric domain fabric1 log-adjacency-changes
```

```{cfgcmd} set protocols openfabric domain \<name\> fabric-tier \<0-14\>

**Configure a static tier number for the specified OpenFabric domain.**

The router advertises the tier value to indicate its location in the
OpenFabric domain.
```

Example:

```none
set protocols openfabric domain fabric1 fabric-tier 1
```

### Interface configuration

```{cfgcmd} set protocols openfabric domain \<name\> interface \<interface\> hello-interval \<1-600\>

**Configure the interval, in seconds, at which the router transmits Hello
packets on this interface.**

Hello packets are exchanged with neighbors to establish and maintain
adjacencies.
```

Example:

```none
set protocols openfabric domain fabric1 interface eth0 hello-interval 5
```

```{cfgcmd} set protocols openfabric domain \<name\> interface \<interface\> hello-multiplier \<2-100\>

**Configure the multiplier used to compute the Hello hold time on the
specified interface.**
```

Example:

```none
set protocols openfabric domain fabric1 interface eth0 hello-multiplier 3
```

```{cfgcmd} set protocols openfabric domain \<name\> interface \<interface\> metric \<0-16777215\>

**Configure the routing metric for the specified interface.**

This metric is used in path selection to determine the most efficient
route. Lower metrics indicate preferred paths.
```

Example:

```none
set protocols openfabric domain fabric1 interface eth0 metric 100
```

```{cfgcmd} set protocols openfabric domain \<name\> interface \<interface\> passive

**Enable passive mode for the specified interface.**

In passive mode, the router does not send Hello packets on the interface
and does not form adjacencies.
```

Example:

```none
set protocols openfabric domain fabric1 interface eth0 passive
```

```{cfgcmd} set protocols openfabric domain \<name\> interface \<interface\> password \<plaintext-password|md5\> \<password\>

**Configure the authentication password for the specified interface.**

The password can be specified as either plain text or
an {abbr}`MD5 (Message-Digest Algorithm 5)` hash.
```

Example:

```none
set protocols openfabric domain fabric1 interface eth0 password plaintext-password link-secret
```

```{cfgcmd} set protocols openfabric domain \<name\> interface \<interface\> csnp-interval \<1-600\>

**Configure the interval, in seconds, at which
{abbr}`CSNPs (Complete Sequence Number PDUs)` are sent on the specified
interface.**
```

Example:

```none
set protocols openfabric domain fabric1 interface eth0 csnp-interval 10
```

```{cfgcmd} set protocols openfabric domain \<name\> interface \<interface\> psnp-interval \<0-120\>

**Configure the interval, in seconds, at which
{abbr}`PSNPs (Partial Sequence Number PDUs)` are sent on the specified
interface.**
```

Example:

```none
set protocols openfabric domain fabric1 interface eth0 psnp-interval 2
```

### Timers

```{cfgcmd} set protocols openfabric domain \<name\> lsp-gen-interval \<1-120\>

**Configure the minimum interval, in seconds, between successive
generations of the same {abbr}`LSP (Link State PDU)` in the OpenFabric
domain.**
```

Example:

```none
set protocols openfabric domain fabric1 lsp-gen-interval 5
```

```{cfgcmd} set protocols openfabric domain \<name\> lsp-refresh-interval \<1-65235\>

**Configure the LSP refresh interval, in seconds, for the OpenFabric
domain.**
```

```{note}
The value must be lower than `max-lsp-lifetime`. Otherwise, LSPs will
time out before they can be refreshed.
```

Example:

```none
set protocols openfabric domain fabric1 lsp-refresh-interval 900
```

```{cfgcmd} set protocols openfabric domain \<name\> max-lsp-lifetime \<360-65535\>

**Configure the maximum lifetime, in seconds, for LSPs in the OpenFabric
domain.**

By default, LSPs remain in the link-state database for 1200 seconds and
are deleted if they are not refreshed.
```

Example:

```none
set protocols openfabric domain fabric1 max-lsp-lifetime 1200
```

```{cfgcmd} set protocols openfabric domain \<name\> spf-interval \<1-120\>

**Configure the minimum interval, in seconds, between consecutive
{abbr}`SPF (Shortest Path First)` calculations in the OpenFabric domain.**
```

Example:

```none
set protocols openfabric domain fabric1 spf-interval 5
```

## Example

The following example demonstrates a basic OpenFabric configuration between
two routers.

**Node 1:**

```none
set interfaces loopback lo address '198.51.100.1/32'
set interfaces ethernet eth1 address '192.0.2.1/24'

set protocols openfabric domain VyOS interface eth1 address-family ipv4
set protocols openfabric domain VyOS interface lo address-family ipv4
set protocols openfabric domain VyOS interface lo passive
set protocols openfabric net '49.0001.1980.5110.0001.00'
```

**Node 2:**

```none
set interfaces loopback lo address '198.51.100.2/32'
set interfaces ethernet eth1 address '192.0.2.2/24'

set protocols openfabric domain VyOS interface eth1 address-family ipv4
set protocols openfabric domain VyOS interface lo address-family ipv4
set protocols openfabric domain VyOS interface lo passive
set protocols openfabric net '49.0001.1980.5110.0002.00'
```

After committing the configuration, verify the neighbor adjacencies on both
nodes: 

```none
vyos@node-1:~$ show openfabric neighbor
show openfabric neighbor
Area VyOS:
  System Id           Interface   L  State        Holdtime SNPA
  node-2              eth1        2  Up            27      2020.2020.2020


vyos@node-2:~$ show openfabric neighbor
show openfabric neighbor
Area VyOS:
  System Id           Interface   L  State        Holdtime SNPA
  node-1              eth1        2  Up            30      2020.2020.2020
```

Verify that the OpenFabric routes have successfully populated:

```none
vyos@node-1:~$ show ip route openfabric
show ip route openfabric
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, F - PBR,
       f - OpenFabric,
       > - selected route, * - FIB route, q - queued, r - rejected, b - backup
       t - trapped, o - offload failure

f   192.0.2.0/24 [115/20] via 192.0.2.2, eth1 onlink, weight 1, 00:00:10
f>* 198.51.100.2/32 [115/20] via 192.0.2.2, eth1 onlink, weight 1, 00:00:10

vyos@node-2:~$ show ip route openfabric
show ip route openfabric
Codes: K - kernel route, C - connected, S - static, R - RIP,
       O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
       T - Table, v - VNC, V - VNC-Direct, A - Babel, F - PBR,
       f - OpenFabric,
       > - selected route, * - FIB route, q - queued, r - rejected, b - backup
       t - trapped, o - offload failure

f   192.0.2.0/24 [115/20] via 192.0.2.1, eth1 onlink, weight 1, 00:00:48
f>* 198.51.100.1/32 [115/20] via 192.0.2.1, eth1 onlink, weight 1, 00:00:48
```
