---
myst:
  html_meta:
    description: |
      The IPoE server provides managed IP connectivity to subscribers
      over Ethernet, authenticating them, assigning addresses, and
      enforcing per-subscriber bandwidth limits.
    keywords: ipoe-server, ipoe, radius, dhcp, coa, prefix-delegation, vlan
---

(ipoe-server)=

# IPoE server

The {abbr}`IPoE (IP over Ethernet)` server provides managed IP
connectivity to subscribers connected over an Ethernet network.
Service providers use it to authenticate individual subscribers,
assign them IP addresses, account for their traffic, and enforce
per-subscriber bandwidth limits. Unlike PPPoE, IPoE requires no
session client on the subscriber's device. The subscriber connects to
the network, obtains an IP address from the server via DHCP, and the
server manages the connection from there.

The IPoE server is configured under `service ipoe-server`. It listens
on the configured interfaces and starts sessions according to the
interface's `start-session` setting: upon receiving a DHCPv4 Discover
message, upon receiving an IP packet from an unknown source address,
also known as an unclassified packet, or automatically when the
interface comes up. Sessions are authenticated in one of the following
ways: locally, via a
{abbr}`RADIUS (Remote Authentication Dial-In User Service)` server, or
not at all.

```{note}
Most configuration changes cannot be applied at runtime. Every commit
that changes the `service ipoe-server` configuration restarts the
server, which terminates all active IPoE sessions.
```

## Configuration

### Interfaces

Use the following commands to configure the interfaces on which the
IPoE server accepts clients and how sessions are started on them.

```{cfgcmd} set service ipoe-server interface \<interface\>

**Configure an interface on which the IPoE server listens for DHCPv4
requests or unclassified packets.**

Repeat the command to listen on several interfaces.

At least one interface must be configured for the IPoE server.
Otherwise, the commit fails.
```

Example:

```none
set service ipoe-server interface eth1
```

```{cfgcmd} set service ipoe-server interface \<interface\> mode \<l2 | l3\>

**Configure the client connectivity mode for the specified
interface:**

- `l2`: Clients are located on the same subnet as the interface.
- `l3`: Clients are located behind an intermediate router, in a
  different subnet than the interface.

The default is `l2`.
```

Example:

```none
set service ipoe-server interface eth1 mode l3
```

```{cfgcmd} set service ipoe-server interface \<interface\> network \<shared | vlan\>

**Define the network model for IPoE clients on the specified
interface:**

- `shared`: Clients share the same network.
- `vlan`: Each client has a dedicated VLAN.

The default is `shared`.
```

Example:

```none
set service ipoe-server interface eth1 network vlan
```

```{cfgcmd} set service ipoe-server interface \<interface\> vlan \<1-4094 | start-end\>

**Configure a VLAN ID or VLAN range served on the specified
interface.**

The server then accepts clients on the matching VLAN interfaces (for
example, `eth1.100`) rather than on the base interface (for example,
`eth1`).

Repeat the command to add several VLAN IDs or ranges.

This option cannot be combined with `client-subnet`.
```

Example:

```none
set service ipoe-server interface eth1 vlan 100
set service ipoe-server interface eth1 vlan 200-300
```

```{cfgcmd} set service ipoe-server interface \<interface\> vlan-mon

**Enable automatic creation of the VLAN interfaces matched by
`vlan`.**

Requires `vlan` to be set on the same interface. Otherwise, the
commit fails.
```

Example:

```none
set service ipoe-server interface eth1 vlan-mon
```

```{cfgcmd} set service ipoe-server interface \<interface\> start-session \<auto | dhcp | unclassified-packet\>

**Configure the event that starts an IPoE session on the specified
interface:**

- `dhcp`: The session starts when a DHCPv4 Discover message is
  received.
- `unclassified-packet`: The session starts when an unclassified
  packet is received.
- `auto`: The session starts automatically, without waiting for a
  DHCPv4 Discover message or an unclassified packet. Typically
  combined with `vlan` and `vlan-mon`.

The default is `dhcp`.
```

Example:

```none
set service ipoe-server interface eth1 start-session unclassified-packet
```

```{cfgcmd} set service ipoe-server interface \<interface\> client-subnet \<x.x.x.x/x\>

**Configure a local IPv4 subnet from which the IPoE server assigns
addresses to clients on the specified interface.**

The first address of the subnet is used as the router address.

This option cannot be combined with `vlan`. For more flexible address
assignment, use `client-ip-pool` instead.
```

Example:

```none
set service ipoe-server interface eth1 client-subnet 192.0.2.0/24
```

```{cfgcmd} set service ipoe-server interface \<interface\> external-dhcp dhcp-relay \<ipv4-address\>

**Forward DHCPv4 requests received on the specified interface to the
specified external DHCP server.**

`external-dhcp giaddr` must also be configured on the interface.
Otherwise, the commit fails.
```

Example:

```none
set service ipoe-server interface eth1 external-dhcp dhcp-relay 198.51.100.10
```

```{cfgcmd} set service ipoe-server interface \<interface\> external-dhcp giaddr \<ipv4-address\>

**Configure the relay agent IP address (giaddr) used when forwarding
DHCPv4 requests to the external DHCP server.**
```

Example:

```none
set service ipoe-server interface eth1 external-dhcp giaddr 192.0.2.1
```

### Authentication

The IPoE server authenticates sessions locally, via RADIUS, or not at
all. With local authentication, a client is identified by the
combination of the interface on which the session is started (for
example, `eth1.100`) and the client's MAC address. Both values are
matched against the entries configured with `authentication
interface`.

```{cfgcmd} set service ipoe-server authentication mode \<local | radius | noauth\>

**Configure the authentication mode used by the IPoE server for all
client sessions:**

- `local`: Authenticates sessions against the interface and MAC
  address entries configured with `authentication interface`.
- `radius`: Authenticates sessions against the configured RADIUS
  servers.
- `noauth`: Accepts sessions without authentication.

The default is `local`.
```

```{note}
With the `local` and `noauth` modes, an address source must be
configured: a `client-ip-pool`, a `client-ipv6-pool`, a per-interface
`client-subnet`, or an external DHCP relay. Otherwise, the commit
fails.
```

Example:

```none
set service ipoe-server authentication mode radius
```

```{cfgcmd} set service ipoe-server authentication interface \<interface\> mac \<mac-address\>

**Create a local IPoE authentication entry for the specified
interface and MAC address.**

Repeat the command for each client.

When the authentication mode is `local`, at least one entry must be
configured. Otherwise, the commit fails.
```

Example:

```none
set service ipoe-server authentication interface eth1.100 mac 00:00:5e:00:53:01
```

```{cfgcmd} set service ipoe-server authentication interface \<interface\> mac \<mac-address\> vlan \<1-4094\>

**Limit the interface/MAC entry to a single VLAN.**

The client is then authorized only on the matching VLAN
subinterface. For example, `interface eth1 … vlan 100` authorizes the
client only when its traffic arrives on `eth1.100`.
```

Example:

```none
set service ipoe-server authentication interface eth1 mac 00:00:5e:00:53:01 vlan 100
```

```{cfgcmd} set service ipoe-server authentication interface \<interface\> mac \<mac-address\> ip-address \<ipv4-address\>

**Assign a fixed IPv4 address to the client with the specified MAC
address.**
```

Example:

```none
set service ipoe-server authentication interface eth1.100 mac 00:00:5e:00:53:01 ip-address 192.0.2.50
```

```{cfgcmd} set service ipoe-server authentication interface \<interface\> mac \<mac-address\> rate-limit download \<1-4294967295\>

**Configure the download bandwidth limit, in kbit/s, for the client
with the specified MAC address.**

Both `download` and `upload` must be configured for the limit to be
applied.
```

Example:

```none
set service ipoe-server authentication interface eth1.100 mac 00:00:5e:00:53:01 rate-limit download 50000
```

```{cfgcmd} set service ipoe-server authentication interface \<interface\> mac \<mac-address\> rate-limit upload \<1-4294967295\>

**Configure the upload bandwidth limit, in kbit/s, for the client
with the specified MAC address.**

Both `download` and `upload` must be configured for the limit to be
applied.
```

Example:

```none
set service ipoe-server authentication interface eth1.100 mac 00:00:5e:00:53:01 rate-limit upload 10000
```

```{cfgcmd} set service ipoe-server lua-file \<filename\>

**Configure a Lua script file used to construct session usernames
from client DHCP packets.**

The file must be located in the `/config/scripts` directory.
```

Example:

```none
set service ipoe-server lua-file /config/scripts/ipoe-username.lua
```

```{cfgcmd} set service ipoe-server interface \<interface\> lua-username \<function-name\>

**Configure the name of the Lua function used to construct the
session username for clients on the specified interface.**

Requires `lua-file` to be set, and is available only with RADIUS
authentication. Otherwise, the commit fails.
```

Example:

```none
set service ipoe-server interface eth1 lua-username username_from_option82
```

### RADIUS

To use RADIUS authentication, set the authentication mode to `radius`
and configure at least one RADIUS server with its shared secret.
Entries configured for local authentication remain in the
configuration but are not used in this mode.

```{cfgcmd} set service ipoe-server authentication radius server \<ipv4-address\> key \<secret\>

**Configure a RADIUS server, with its shared secret, for
authentication and accounting.**

The shared secret can be up to 128 characters long.

Repeat the command to configure multiple servers. Requests are then
distributed among the servers according to their priority. An
unresponsive server is skipped for the time configured with
`fail-time`, and servers marked `backup` are used only when all other
servers are unavailable.
```

```{note}
RADIUS servers typically restrict which clients may send requests.
Make sure the VyOS router (its RADIUS source address) is present in
the server's client list.
```

Example:

```none
set service ipoe-server authentication radius server 198.51.100.9 key 'radius-secret'
```

```{cfgcmd} set service ipoe-server authentication radius server \<ipv4-address\> port \<1-65535\>

**Configure the UDP port used for authentication requests to the
specified RADIUS server.**

The default is 1812.
```

Example:

```none
set service ipoe-server authentication radius server 198.51.100.9 port 1645
```

```{cfgcmd} set service ipoe-server authentication radius server \<ipv4-address\> acct-port \<1-65535\>

**Configure the UDP port used for accounting requests to the
specified RADIUS server.**

The default is 1813.
```

Example:

```none
set service ipoe-server authentication radius server 198.51.100.9 acct-port 1646
```

```{cfgcmd} set service ipoe-server authentication radius server \<ipv4-address\> disable

**Disable the specified RADIUS server without removing it from the
configuration.**
```

Example:

```none
set service ipoe-server authentication radius server 198.51.100.9 disable
```

```{cfgcmd} set service ipoe-server authentication radius server \<ipv4-address\> disable-accounting

**Disable RADIUS accounting to the specified server.**

Authentication requests are still sent to the server.
```

Example:

```none
set service ipoe-server authentication radius server 198.51.100.9 disable-accounting
```

```{cfgcmd} set service ipoe-server authentication radius server \<ipv4-address\> fail-time \<0-600\>

**Mark the specified RADIUS server as unavailable for the given time,
in seconds, after it fails to respond.**

The default is 0.
```

Example:

```none
set service ipoe-server authentication radius server 198.51.100.9 fail-time 60
```

```{cfgcmd} set service ipoe-server authentication radius server \<ipv4-address\> priority \<1-255\>

**Configure the priority (weight) of the specified server, used to
distribute requests when multiple RADIUS servers are configured.**
```

Example:

```none
set service ipoe-server authentication radius server 198.51.100.9 priority 10
```

```{cfgcmd} set service ipoe-server authentication radius server \<ipv4-address\> backup

**Configure the specified RADIUS server as a backup, used only when
all other RADIUS servers are unavailable.**
```

Example:

```none
set service ipoe-server authentication radius server 198.51.100.9 backup
```

```{cfgcmd} set service ipoe-server authentication radius source-address \<ipv4-address\>

**Configure the source IPv4 address used in all queries to RADIUS
servers.**

The address must exist on the router. A loopback or dummy interface
address is commonly used.
```

Example:

```none
set service ipoe-server authentication radius source-address 192.0.2.1
```

```{cfgcmd} set service ipoe-server authentication radius timeout \<1-60\>

**Configure the time, in seconds, to wait for a reply to
Access-Request and Accounting-Request queries sent to a RADIUS
server.**

If no reply arrives within this time, the request is resent. The
number of attempts is limited by `max-try`.

The default is 3.
```

Example:

```none
set service ipoe-server authentication radius timeout 10
```

```{cfgcmd} set service ipoe-server authentication radius max-try \<1-20\>

**Configure the maximum number of attempts to send Access-Request and
Accounting-Request queries to a RADIUS server.**

After this many attempts without a reply, the server is considered
unresponsive.

The default is 3.
```

Example:

```none
set service ipoe-server authentication radius max-try 5
```

```{cfgcmd} set service ipoe-server authentication radius acct-timeout \<0-60\>

**Configure the time, in seconds, to wait for a reply to
Interim-Update accounting packets before terminating the session.**

Setting the value to 0 keeps the session active regardless of
accounting replies.

The default is 3.
```

Example:

```none
set service ipoe-server authentication radius acct-timeout 30
```

```{cfgcmd} set service ipoe-server authentication radius accounting-interim-interval \<1-3600\>

**Configure the interval, in seconds, at which Interim-Update
accounting packets are sent to the RADIUS server.**

The value may be overridden by the `Acct-Interim-Interval` attribute
received from the RADIUS server.
```

Example:

```none
set service ipoe-server authentication radius accounting-interim-interval 300
```

```{cfgcmd} set service ipoe-server authentication radius acct-interim-jitter \<1-60\>

**Configure the maximum jitter, in seconds, applied to the
`accounting-interim-interval`.**
```

Example:

```none
set service ipoe-server authentication radius acct-interim-jitter 10
```

```{cfgcmd} set service ipoe-server authentication radius nas-identifier \<identifier\>

**Configure the value the IPoE server sends to the RADIUS server in
the NAS-Identifier attribute.**

The IPoE server accepts incoming
{abbr}`CoA (Change of Authorization)` and Disconnect requests from the
RADIUS server only if they carry a matching value.
```

Example:

```none
set service ipoe-server authentication radius nas-identifier ipoe-gw01
```

```{cfgcmd} set service ipoe-server authentication radius nas-ip-address \<ipv4-address\>

**Configure the IPv4 address the IPoE server sends to the RADIUS
server in the NAS-IP-Address attribute.**

The IPoE server accepts incoming CoA and Disconnect requests from the
RADIUS server only if they carry a matching address.
```

Example:

```none
set service ipoe-server authentication radius nas-ip-address 192.0.2.1
```

```{cfgcmd} set service ipoe-server authentication radius dynamic-author server \<ipv4-address\>

**Configure the local IPv4 address on which the
{abbr}`DAE (Dynamic Authorization Extension)` server accepts RADIUS
CoA and Disconnect requests.**

The DAE server lets the RADIUS server reauthorize or disconnect active
sessions.

`dynamic-author key` must also be configured. Otherwise, the commit
fails.
```

Example:

```none
set service ipoe-server authentication radius dynamic-author server 192.0.2.1
```

```{cfgcmd} set service ipoe-server authentication radius dynamic-author port \<1-65535\>

**Configure the UDP port on which the DAE server accepts requests.**

The default is 1700.
```

Example:

```none
set service ipoe-server authentication radius dynamic-author port 3799
```

```{cfgcmd} set service ipoe-server authentication radius dynamic-author key \<secret\>

**Configure the shared secret for the DAE server.**
```

Example:

```none
set service ipoe-server authentication radius dynamic-author key 'coa-secret'
```

```{cfgcmd} set service ipoe-server authentication radius rate-limit enable

**Enable bandwidth shaping of client sessions based on rate
information received from the RADIUS server.**
```

Example:

```none
set service ipoe-server authentication radius rate-limit enable
```

```{cfgcmd} set service ipoe-server authentication radius rate-limit attribute \<attribute\>

**Configure which RADIUS attribute carries the rate information.**

The default is `Filter-Id`.
```

```{note}
A custom rate-limit attribute must be defined in the RADIUS
dictionaries of both the RADIUS server and VyOS.
```

Example:

```none
set service ipoe-server authentication radius rate-limit attribute Mikrotik-Rate-Limit
```

```{cfgcmd} set service ipoe-server authentication radius rate-limit vendor \<vendor\>

**Configure the RADIUS vendor whose vendor-specific attribute carries
the rate information.**

The vendor dictionary must be present in
`/usr/share/accel-ppp/radius`.
```

Example:

```none
set service ipoe-server authentication radius rate-limit vendor Mikrotik
```

```{cfgcmd} set service ipoe-server authentication radius rate-limit multiplier \<0.001-1000\>

**Configure a multiplier applied to the rate values received from the
RADIUS server.**

The default is 1.
```

Example:

```none
set service ipoe-server authentication radius rate-limit multiplier 0.001
```
<!--
Excluded: set service ipoe-server authentication radius preallocate-vif
This option only applies to PPP-based services and has no effect on the IPoE
server, so it is intentionally left undocumented.
-->

### RADIUS attributes

When included in a RADIUS reply, the attributes below determine the
client's IP address and prefix assignment, taking precedence over the
corresponding local settings. If an attribute is omitted, the local
configuration applies.

The following table outlines the allocation behaviors for different
RADIUS attributes:
% stop_vyoslinter

| RADIUS attribute | Allocation behavior with the RADIUS attribute | Allocation behavior without the RADIUS attribute |
|---|---|---|
| `Framed-IP-Address` | The IPv4 address carried in the attribute is assigned directly to the client. Example: `192.0.2.50` | IPv4 address assigned from the pool set as `default-pool`. Example: `192.0.2.15` from `IPOE-POOL` |
| `Framed-Pool` | IPv4 address assigned from a pool named by the attribute value and defined with `client-ip-pool`. Example: `198.51.100.20` from `PREMIUM-V4` | IPv4 address assigned from the pool set as `default-pool`. Example: `192.0.2.15` from `IPOE-POOL` |
| `Stateful-IPv6-Address-Pool` | IPv6 address assigned from the prefix ranges of a pool named by the attribute value and defined with `client-ipv6-pool`. Example: `2001:db8:aaaa::20` from the prefix `2001:db8:aaaa::/48` of `PREMIUM-V6` | IPv6 address assigned from the pool set as `default-ipv6-pool`. Example: `2001:db8:8002::5` from `IPV6-POOL` |
| `Delegated-IPv6-Prefix-Pool` | Delegated prefix assigned from the delegate ranges of a pool named by the attribute value and defined with `client-ipv6-pool`. Example: `2001:db8:bbbb:100::/56` from the delegate `2001:db8:bbbb::/48` of `PREMIUM-V6` | Delegated prefix assigned from the pool set as `default-ipv6-pool`. Example: `2001:db8:8003::/56` from `IPV6-POOL` |

```{note}
`Stateful-IPv6-Address-Pool` and `Delegated-IPv6-Prefix-Pool` are
defined in
[RFC 6911](https://datatracker.ietf.org/doc/html/rfc6911). If your
RADIUS server does not already define them, add them to its RADIUS
dictionary using the definitions from the
[accel-ppp RFC 6911 dictionary](https://github.com/accel-ppp/accel-ppp/blob/master/accel-pppd/radius/dict/dictionary.rfc6911).
```
% start_vyoslinter
```{note}
A session can be placed into a
{abbr}`VRF (Virtual Routing and Forwarding)` via the RADIUS
Access-Accept packet, or moved to another VRF via a CoA request, using
the `Accel-VRF-Name` attribute. It is a vendor-specific ACCEL-PPP
attribute. Define it on your RADIUS server.
```

### IPv4 address assignment

Use the following commands to configure the named IPv4 pools from which
the IPoE server assigns client addresses, as well as the server's local
address used for client sessions.

```{cfgcmd} set service ipoe-server client-ip-pool \<name\> range \<x.x.x.x/x | x.x.x.x-x.x.x.x\>

**Configure an IPv4 address range as part of the specified client
pool.**

Specify the range either as an IPv4 prefix or as an address range
whose endpoints lie within a common /24 network. Repeat the command
to add several ranges to the same pool.
```

Example:

```none
set service ipoe-server client-ip-pool IPOE-POOL range 192.0.2.10-192.0.2.99
set service ipoe-server client-ip-pool IPOE-POOL range 198.51.100.0/24
```

```{cfgcmd} set service ipoe-server client-ip-pool \<name\> next-pool \<name\>

**Configure the next pool, from which client addresses are allocated
once the specified client pool is exhausted.**

The following requirements are enforced when the configuration is
committed:

- The specified client pool must contain a `range`.
- The next pool must be defined.
- Circular references between pools are rejected.
```

Example:

```none
set service ipoe-server client-ip-pool IPOE-POOL next-pool IPOE-POOL2
```

```{cfgcmd} set service ipoe-server default-pool \<name\>

**Configure an IPv4 pool from which client addresses are allocated by
default.**

The pool must be defined at commit time. A `Framed-Pool` attribute
received from RADIUS overrides this selection.
```

Example:

```none
set service ipoe-server default-pool IPOE-POOL
```

```{cfgcmd} set service ipoe-server gateway-address \<x.x.x.x/x\>

**Configure the IPv4 gateway address with prefix length for IPoE
client sessions.**

The prefix length is provided to clients as the corresponding subnet
mask.

A distinct gateway can be defined for each client subnet. Each client
receives a gateway corresponding to its subnet.

If no gateway address is configured, the commit succeeds but generates
a warning.
```

Example:

```none
set service ipoe-server gateway-address 192.0.2.1/24
set service ipoe-server gateway-address 198.51.100.1/24
```

### IPv6 address assignment

Use the following commands to configure the named IPv6 pools from which
the IPoE server assigns client addresses and delegated prefixes.

```{cfgcmd} set service ipoe-server client-ipv6-pool \<name\> prefix \<h:h:h:h:h:h:h:h/h\> mask \<48-128\>

**Configure an IPv6 prefix with mask length as part of the specified
client pool.**

The system divides this prefix into smaller networks based on the
specified mask length. Clients using this pool receive an individual
network of the specified mask length.

The default mask is 64. Repeat the command to add several prefixes to
the same pool.
```

Example:

```none
set service ipoe-server client-ipv6-pool IPV6-POOL prefix 2001:db8:8002::/48 mask 64
```

```{cfgcmd} set service ipoe-server client-ipv6-pool \<name\> delegate \<h:h:h:h:h:h:h:h/h\> delegation-prefix \<32-64\>

**Configure an IPv6 prefix with delegation-prefix length as part of
the specified client pool.**

The system divides this prefix into smaller prefixes based on the
specified delegation-prefix length. Clients using this pool are
delegated an individual prefix of the specified length through DHCPv6
prefix delegation
([RFC 3633](https://datatracker.ietf.org/doc/html/rfc3633)).

Repeat the command to add several prefixes to the same pool.

A `prefix` must also be configured in the same pool. Otherwise, the
commit fails.
```

Example:

```none
set service ipoe-server client-ipv6-pool IPV6-POOL delegate 2001:db8:8003::/48 delegation-prefix 56
```

```{cfgcmd} set service ipoe-server default-ipv6-pool \<name\>

**Configure the IPv6 pool used by default for both client address
assignment and prefix delegation.**

The `Stateful-IPv6-Address-Pool` and `Delegated-IPv6-Prefix-Pool`
attributes received from RADIUS override this selection.
```

Example:

```none
set service ipoe-server default-ipv6-pool IPV6-POOL
```

### Name servers

```{cfgcmd} set service ipoe-server name-server \<address\>

**Configure a DNS server address advertised to IPoE clients.**

Repeat the command to configure up to two IPv4 and up to three IPv6
name servers.
```

Example:

```none
set service ipoe-server name-server 192.0.2.53
set service ipoe-server name-server 2001:db8::53
```

### Session and connection limits

```{cfgcmd} set service ipoe-server idle-timeout \<0-86400\>

**Configure the time, in seconds, after which sessions with no
packets from the client are disconnected.**

Typically used together with `mode l3`.
```

Example:

```none
set service ipoe-server idle-timeout 300
```

```{cfgcmd} set service ipoe-server max-concurrent-sessions \<0-65535\>

**Configure the maximum number of session start attempts the server
can process concurrently.**
```

Example:

```none
set service ipoe-server max-concurrent-sessions 64
```

```{cfgcmd} set service ipoe-server limits connection-limit \<rate\>

**Configure the acceptable rate of new connections from a single
source.**

Specify the rate as `<count>/min` or `<count>/sec`, where `<count>` is
an integer.
```

Example:

```none
set service ipoe-server limits connection-limit 10/min
```

```{cfgcmd} set service ipoe-server limits burst \<count\>

**Configure the number of connections from a single source accepted
without rate limiting.**

Further connections from that source are limited to the
`connection-limit` rate.

The count resets after the timeout period without connections.
```

Example:

```none
set service ipoe-server limits burst 3
```

```{cfgcmd} set service ipoe-server limits timeout \<seconds\>

**Configure the period without new connections, in seconds, after
which a source's burst allowance is restored.**
```

Example:

```none
set service ipoe-server limits timeout 60
```

### Traffic shaping

```{cfgcmd} set service ipoe-server shaper fwmark \<1-2147483647\>

**Exclude traffic marked with the specified firewall mark value from
bandwidth shaping.**
```

Example:

```none
set service ipoe-server shaper fwmark 223
```

### Session scripts

The IPoE server can run scripts at different stages of the session life
cycle.

```{cfgcmd} set service ipoe-server extended-scripts on-pre-up \<path\>

**Configure a script to run before the session interface comes up.**
```

Example:

```none
set service ipoe-server extended-scripts on-pre-up /config/scripts/ipoe-pre-up.sh
```

```{cfgcmd} set service ipoe-server extended-scripts on-up \<path\>

**Configure a script to run when the session interface is completely
configured and started.**
```

Example:

```none
set service ipoe-server extended-scripts on-up /config/scripts/ipoe-up.sh
```

```{cfgcmd} set service ipoe-server extended-scripts on-down \<path\>

**Configure a script to run when the session interface is about to
terminate.**
```

Example:

```none
set service ipoe-server extended-scripts on-down /config/scripts/ipoe-down.sh
```

```{cfgcmd} set service ipoe-server extended-scripts on-change \<path\>

**Configure a script to run when the session is changed by RADIUS CoA
handling.**
```

Example:

```none
set service ipoe-server extended-scripts on-change /config/scripts/ipoe-change.sh
```

### Miscellaneous

```{cfgcmd} set service ipoe-server description \<description\>

**Configure a description for the IPoE server configuration.**

The description can be up to 255 characters long.
```

Example:

```none
set service ipoe-server description 'IPoE access server'
```

```{cfgcmd} set service ipoe-server snmp master-agent

**Enable SNMP master agent mode for the IPoE server.**

The SNMP module then runs as a standalone SNMP master agent rather
than as an AgentX subagent, which is the default mode.
```

Example:

```none
set service ipoe-server snmp master-agent
```

```{cfgcmd} set service ipoe-server thread-count \<all | half | 1-512\>

**Configure the number of worker threads used by the IPoE server
process:**

- `all`: Use all available CPU cores.
- `half`: Use half of the available CPU cores.
- A number from 1 to 512: Use a fixed thread count.

The default is `all`.
```

Example:

```none
set service ipoe-server thread-count 4
```

```{cfgcmd} set service ipoe-server log level \<0-5\>

**Configure the logging severity level for the IPoE server process.**

Level 0 disables logging. Higher levels add warning, informational,
and debug messages.

The default is 3.
```

Example:

```none
set service ipoe-server log level 5
```

## Operation

### Show

```{opcmd} show ipoe-server sessions

**Show active IPoE server sessions.**
```

```{opcmd} show ipoe-server statistics

**Show IPoE server statistics.**
```

```{opcmd} show log ipoe-server

**Show the IPoE server log.**
```

### Reset

```{opcmd} reset ipoe-server session interface \<interface\>

**Terminate the IPoE session running on the specified interface.**
```

```{opcmd} reset ipoe-server session sid \<session-id\>

**Terminate the IPoE session with the specified session ID.**
```

```{opcmd} reset ipoe-server session username \<username\>

**Terminate the IPoE session with the specified username.**
```

### Restart

```{opcmd} restart ipoe-server

**Restart the IPoE server process.**

All active IPoE sessions are terminated.
```

## Example

The following configuration accepts IPoE clients on VLANs 100-200 of
`eth1`, with one VLAN per client. Two clients are authorized locally by
their VLAN and MAC address. They receive addresses from the `IPOE-POOL`
pool, with `192.0.2.1/24` as the gateway. DHCPv4 Discover messages from
clients that are not configured are ignored.

```none
set interfaces ethernet eth1 address '192.0.2.1/24'
set service ipoe-server authentication interface eth1.100 mac 00:00:5e:00:53:01
set service ipoe-server authentication interface eth1.101 mac 00:00:5e:00:53:02
set service ipoe-server authentication mode 'local'
set service ipoe-server client-ip-pool IPOE-POOL range '192.0.2.2-192.0.2.254'
set service ipoe-server default-pool 'IPOE-POOL'
set service ipoe-server gateway-address '192.0.2.1/24'
set service ipoe-server interface eth1 mode 'l2'
set service ipoe-server interface eth1 network 'vlan'
set service ipoe-server interface eth1 vlan '100-200'
```
