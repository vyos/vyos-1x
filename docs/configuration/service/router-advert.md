---
myst:
  html_meta:
    description: |
      Router Advertisements are network messages sent by IPv6 routers
      to announce their presence and provide configuration parameters
      for Stateless Address Autoconfiguration and related settings.
    keywords: router-advert, ra, ipv6, slaac, dhcpv6-pd, rdnss, nat64
---

(router-advert)=

# Router Advertisements
 
Router Advertisements ({abbr}`RAs (Router Advertisements)`) are network
messages sent by IPv6 routers to hosts.
 
Each RA announces the router's presence and provides configuration
parameters for
{abbr}`SLAAC (Stateless Address Autoconfiguration)` and related
settings. Routers send RAs periodically and in response to Router
Solicitations from hosts.
 
RAs can be enabled on any IPv6-capable interface.
 
RAs are defined in
[RFC 4861, §4.2](https://datatracker.ietf.org/doc/html/rfc4861#section-4.2).

## Configuration

### Interface parameters

```{cfgcmd} set service router-advert interface \<interface\> hop-limit \<0-255\>

**Configure the Cur Hop Limit advertised in RAs on the specified
interface.**

Hosts receiving the RA use this value as the default Hop Limit for
packets they send. A value of 0 means unspecified by the router,
leaving hosts to use their own default.

The default is 64, matching the IANA-recommended value.
```

Example:

```none
set service router-advert interface eth0 hop-limit 64
```

```{cfgcmd} set service router-advert interface \<interface\> default-lifetime \<0 | 4-9000\>

**Configure the Router Lifetime, in seconds, advertised in RAs on the
specified interface.**

This value controls how long hosts keep this router in their default
router list.

A value of 0 indicates that the router is not to be used as a default
router by receiving hosts. A non-zero value must be greater than or
equal to the maximum unsolicited RA interval (`interval max`, default
600). Otherwise, RAs will not be sent on the interface.

If unset, the value is set as three times the maximum unsolicited RA
interval.
```

Example:

```none
set service router-advert interface eth0 default-lifetime 1800
```

```{cfgcmd} set service router-advert interface \<interface\> default-preference \<low | medium | high\>

**Configure the Default Router Preference advertised in the RA on the
specified interface.**

Hosts use this preference to choose among multiple default routers if
available. Higher preference wins.

The default is `medium`.
```

Example:

```none
set service router-advert interface eth0 default-preference high
```

```{cfgcmd} set service router-advert interface \<interface\> managed-flag

**Set the Managed Address Configuration (M) flag in RAs on the
specified interface.**

When set, the flag indicates to hosts that IPv6 addresses are
available via DHCPv6, in addition to any addresses configured via
SLAAC (which is driven independently by the A flag on advertised
prefixes).
```

Example:

```none
set service router-advert interface eth0 managed-flag
```

```{cfgcmd} set service router-advert interface \<interface\> other-config-flag

**Set the Other Configuration (O) flag in RAs on the specified
interface.**

When set, the flag indicates to hosts that non-address configuration
information, such as DNS servers or other network parameters, is
available via DHCPv6.

If `managed-flag` is also set, the O flag is redundant, as DHCPv6
provides all available configuration information regardless.
```

Example:

```none
set service router-advert interface eth0 other-config-flag
```

```{cfgcmd} set service router-advert interface \<interface\> link-mtu \<1280-9000\>

**Configure the {abbr}`MTU (Maximum Transmission Unit)` value
advertised in RAs on the specified interface.**

Hosts receiving the RA set their interface's IPv6 MTU to the
advertised value so they don't send packets the router drops.

If unset, the MTU option is omitted from the RA.
```

Example:

```none
set service router-advert interface eth0 link-mtu 1500
```

```{cfgcmd} set service router-advert interface \<interface\> reachable-time \<0-3600000\>

**Configure the Reachable Time, in milliseconds, advertised in RAs on
the specified interface.**

This is the time a host assumes a neighbor (any other IPv6 device it
can reach directly) is still reachable after a positive reachability
confirmation.

A value of 0 means unspecified by the router, so hosts fall back to
their own default.

The default is 0.
```

Example:

```none
set service router-advert interface eth0 reachable-time 30000
```

```{cfgcmd} set service router-advert interface \<interface\> retrans-timer \<0-4294967295\>

**Configure the Retrans Timer, in milliseconds, advertised in RAs on
the specified interface
([RFC 4861, §4.2](https://datatracker.ietf.org/doc/html/rfc4861#section-4.2)).**

This is the time hosts must wait before resending unanswered Neighbor
Solicitation messages.

A value of 0 means unspecified by this router, so hosts fall back to
their own default.

The default is 0.
```

Example:

```none
set service router-advert interface eth0 retrans-timer 1000
```

```{cfgcmd} set service router-advert interface \<interface\> source-address \<ipv6-address\>

**Configure the IPv6 source address used when sending RAs on the
specified interface.**

The address must be a link-local address (`fe80::/10`) configured on
the interface. Hosts drop RAs sourced from any non-link-local address.

Repeat the command to configure multiple source addresses.
```

Example:

```none
set service router-advert interface eth0 source-address fe80::1
```

```{cfgcmd} set service router-advert interface \<interface\> captive-portal \<url\>

**Advertise the captive-portal API URL in RAs on the specified
interface.**

The URL must point to a Captive Portal API endpoint.
```

Example:

```none
set service router-advert interface eth0 captive-portal https://captive.example.com/capport-api
```

### Advertisement interval

```{cfgcmd} set service router-advert interface \<interface\> interval max \<4-1800\>

**Configure the maximum interval, in seconds, between unsolicited
multicast RAs on the specified interface.**

Each successive unsolicited RA is sent after a random delay between
`interval min` and `interval max`.

The default is 600.
```

Example:

```none
set service router-advert interface eth0 interval max 800
```

```{cfgcmd} set service router-advert interface \<interface\> interval min \<3-1350\>

**Configure the minimum interval, in seconds, between unsolicited
multicast RAs on the specified interface.**

Each successive unsolicited RA is sent after a random delay between
`interval min` and `interval max`.

Must be at most 0.75 × `interval max`. Otherwise, RAs will not be
sent on the interface.
```

Example:

```none
set service router-advert interface eth0 interval min 200
```

### DNS options

```{cfgcmd} set service router-advert interface \<interface\> name-server \<ipv6-address\>

**Advertise the address of an IPv6 recursive DNS server in RAs on the
specified interface.**

Repeat the command to advertise multiple servers, up to a maximum of
three.
```

Example:

```none
set service router-advert interface eth0 name-server 2001:db8::1
```

```{cfgcmd} set service router-advert interface \<interface\> name-server-lifetime \<0 | 1-7200\>

**Advertise the {abbr}`RDNSS (Recursive DNS Server)` Lifetime, in
seconds, in RAs on the specified interface.**

If non-zero, the value must be at least `interval max`. Otherwise, the commit
fails.
```

Example:

```none
set service router-advert interface eth0 name-server-lifetime 1200
```

```{cfgcmd} set service router-advert interface \<interface\> dnssl \<domain\>

**Advertise a {abbr}`DNSSL (DNS Search List)` domain in RAs on the
specified interface.**

Repeat the command to advertise multiple domains.
```

Example:

```none
set service router-advert interface eth0 dnssl example.com
```

### Advertising a prefix

```{cfgcmd} set service router-advert interface \<interface\> prefix \<ipv6net\>

**Configure an IPv6 prefix advertised in RAs on the specified
interface.**

Hosts use this prefix for SLAAC and treat destinations within it as
directly reachable. The prefix length must be `/64` for SLAAC.

Repeat the command to advertise multiple prefixes.
```

```{note}
The special value `::/64` is a wildcard used when the prefix is not
known in advance (for example, when learned dynamically from
{abbr}`DHCPv6-PD (DHCPv6 Prefix Delegation)`). RAs then advertise
whatever prefixes are configured on this interface, or on another
interface if `base-interface` is set.
```

Example:

```none
set service router-advert interface eth0 prefix 2001:db8:100::/64
```

```{cfgcmd} set service router-advert interface \<interface\> prefix \<ipv6net\> valid-lifetime \<1-4294967295 | infinity\>

**Configure the Valid Lifetime, in seconds, advertised in RAs for the
specified prefix.**

Hosts treat addresses configured from this prefix via SLAAC as valid
for this duration. After it expires, the addresses are removed. The
`infinity` value disables expiry.

Must be greater than or equal to `preferred-lifetime`. Otherwise, the
commit fails.

The default is 2592000 (30 days).
```

Example:

```none
set service router-advert interface eth0 prefix 2001:db8:100::/64 valid-lifetime 2592000
```

```{cfgcmd} set service router-advert interface \<interface\> prefix \<ipv6net\> preferred-lifetime \<0-4294967295 | infinity\>

**Configure the Preferred Lifetime, in seconds, advertised in RAs for
the specified prefix.**

Hosts treat addresses configured from this prefix via SLAAC as
preferred for this duration (used for new and existing connections).
After it expires, the addresses are deprecated (still used for
existing connections, but not chosen for new ones). The `infinity`
value disables the transition to deprecated.

Must be less than or equal to `valid-lifetime`. Otherwise, the commit
fails.

The default is 14400 (4 hours).
```

Example:

```none
set service router-advert interface eth0 prefix 2001:db8:100::/64 preferred-lifetime 14400
```

```{cfgcmd} set service router-advert interface \<interface\> prefix \<ipv6net\> no-autonomous-flag

**Clear the Autonomous Address Configuration (A) flag in RAs for the
specified prefix.**

Hosts do not use this prefix for SLAAC.
```

Example:

```none
set service router-advert interface eth0 prefix 2001:db8:100::/64 no-autonomous-flag
```

```{cfgcmd} set service router-advert interface \<interface\> prefix \<ipv6net\> no-on-link-flag

**Clear the On-Link (L) flag in RAs for the specified prefix.**

Hosts do not treat destinations within this prefix as directly
reachable and route them through the default router instead.
```

Example:

```none
set service router-advert interface eth0 prefix 2001:db8:100::/64 no-on-link-flag
```

```{cfgcmd} set service router-advert interface \<interface\> prefix \<ipv6net\> decrement-lifetime

**Advertise the specified prefix with `valid-lifetime` and
`preferred-lifetime` counting down in real time.**

Each RA carries the time remaining until the prefix expires rather
than the fixed configured value (computed as the configured lifetime
minus the time already elapsed).

Intended for use with DHCPv6-PD prefixes, so the advertised lifetimes
stay in sync with the delegated lease.
```

Example:

```none
set service router-advert interface eth0 prefix 2001:db8:100::/64 decrement-lifetime
```

```{cfgcmd} set service router-advert interface \<interface\> prefix \<ipv6net\> deprecate-prefix

**On service shutdown, advertise the specified prefix with a Preferred
Lifetime of 0.**

Receiving hosts deprecate any addresses configured from this prefix.
```

Example:

```none
set service router-advert interface eth0 prefix 2001:db8:100::/64 deprecate-prefix
```

```{cfgcmd} set service router-advert interface \<interface\> prefix ::/64 base-interface \<interface\>

**Configure a base interface to take the prefix from when the
advertised prefix is defined with the `::/64` wildcard.**

If not defined, the prefix is taken from the interface on which RAs
are sent.
```

Example:

```none
set service router-advert interface eth0 prefix ::/64 base-interface pppoe0
```

```{cfgcmd} set service router-advert interface \<interface\> auto-ignore \<ipv6net\>

**Exclude the specified IPv6 prefix from RAs when the advertised
prefix is defined with the `::/64` wildcard.**

Repeat the command to exclude multiple prefixes.
```

Example:

```none
set service router-advert interface eth0 auto-ignore 2001:db8:200::/64
```

### Advertising more-specific routes

```{cfgcmd} set service router-advert interface \<interface\> route \<ipv6net\>

**Configure an IPv6 route advertised in RAs on the specified
interface.**

Hosts add the route to their routing table with the advertising
router as the next hop.

Repeat the command to advertise multiple routes.
```

Example:

```none
set service router-advert interface eth0 route 2001:db8:200::/48
```

```{cfgcmd} set service router-advert interface \<interface\> route \<ipv6net\> valid-lifetime \<1-4294967295 | infinity\>

**Configure the Valid Lifetime, in seconds, advertised in RAs for the
specified route.**

Hosts keep the route in their routing table for this duration. After
it expires, the route is removed. The `infinity` value disables
expiry.

The default is 1800 (30 minutes).
```

Example:

```none
set service router-advert interface eth0 route 2001:db8:200::/48 valid-lifetime 1800
```

```{cfgcmd} set service router-advert interface \<interface\> route \<ipv6net\> route-preference \<low | medium | high\>

**Configure the preference advertised in RAs for the specified
route.**

Hosts use this preference to choose among multiple routes to the same
destination if available. Higher preference wins.

The default is `medium`.
```

Example:

```none
set service router-advert interface eth0 route 2001:db8:200::/48 route-preference high
```

```{cfgcmd} set service router-advert interface \<interface\> route \<ipv6net\> no-remove-route

**On service shutdown, do not advertise the specified route with a
Valid Lifetime of 0.**

By default, the route is advertised with a zero Valid Lifetime on
shutdown so that receiving hosts remove it from their routing tables.
```

Example:

```none
set service router-advert interface eth0 route 2001:db8:200::/48 no-remove-route
```

### Advertising a NAT64 prefix

```{cfgcmd} set service router-advert interface \<interface\> nat64prefix \<ipv6net\>

**Configure a NAT64 prefix advertised in RAs on the specified
interface.**

Hosts use the prefix to reach IPv4 destinations over an IPv6-only
network via NAT64.

The prefix length must be one of `/32`, `/40`, `/48`, `/56`, `/64`,
or `/96`. Otherwise, the commit fails.

Repeat the command to advertise multiple NAT64 prefixes.
```

Example:

```none
set service router-advert interface eth0 nat64prefix 64:ff9b::/96
```

```{cfgcmd} set service router-advert interface \<interface\> nat64prefix \<ipv6net\> valid-lifetime \<4-65528\>

**Configure the Valid Lifetime, in seconds, advertised in RAs for the
specified NAT64 prefix.**

Hosts use the prefix to reach IPv4 destinations for this duration.
After it expires, the prefix is no longer used.

Must be greater than or equal to `interval max`. Otherwise, the
commit fails.

The default is 65528.
```

Example:

```none
set service router-advert interface eth0 nat64prefix 64:ff9b::/96 valid-lifetime 65528
```

### Disabling advertisements

```{cfgcmd} set service router-advert interface \<interface\> no-send-advert

**Suppress RAs (both unsolicited transmissions and responses to Router
Solicitations) on the specified interface.**
```

Example:

```none
set service router-advert interface eth0 no-send-advert
```

```{cfgcmd} set service router-advert interface \<interface\> no-send-interval

**Exclude the Advertisement Interval option from RAs on the specified
interface.**

The option is included by default and is only relevant to Mobile
IPv6 hosts.
```

Example:

```none
set service router-advert interface eth0 no-send-interval
```

## Example

The LAN attached to `eth0` uses the prefix `2001:db8:100::/64`, with
the router at `2001:db8:100::1`. The following configuration enables
RAs on the interface with a basic set of options for host
autoconfiguration.

```none
set interfaces ethernet eth0 address '2001:db8:100::1/64'

set service router-advert interface eth0 prefix '2001:db8:100::/64'
set service router-advert interface eth0 default-preference 'high'
set service router-advert interface eth0 name-server '2001:db8::1'
set service router-advert interface eth0 name-server '2001:db8::2'
set service router-advert interface eth0 other-config-flag
```
