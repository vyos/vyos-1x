---
myst:
  html_meta:
    description: |
      DNS forwarding is a VyOS service that resolves DNS queries for
      connected clients by forwarding to configurable upstream servers
      or by operating as a full recursive resolver.
    keywords: dns, dns forwarding, recursive dns, authoritative dns, dnssec
---

(dns-forwarding)=

# DNS forwarding

VyOS provides DNS infrastructure for small networks, designed to be
lightweight and suitable for resource-constrained routers and
firewalls.

Connected clients are served through the DNS forwarding service,
configured under `service dns forwarding`. It can either forward
queries to configurable upstream DNS servers or operate as a full
recursive DNS server without requiring upstream DNS servers. Operating
without upstream servers avoids exposing client queries to an upstream
DNS operator.

## Configuration

```{note}
A DNS forwarding configuration is committable only when both
`listen-address` and `allow-from` are set. Otherwise, the commit
fails.
```

### Listener

```{cfgcmd} set service dns forwarding listen-address \<address\>

**Configure a local IPv4 or IPv6 address on which DNS forwarding
listens for incoming queries.**

The address must already be assigned to a local interface. Repeat the
command to configure multiple listen addresses. At least one
listen-address is required for a successful commit.
```

Example:

```none
set service dns forwarding listen-address 192.0.2.1
set service dns forwarding listen-address 2001:db8::1
```

```{cfgcmd} set service dns forwarding port \<1-65535\>

**Configure the port on which DNS forwarding listens for incoming
queries.**

The default is 53.
```

Example:

```none
set service dns forwarding port 5353
```

```{cfgcmd} set service dns forwarding allow-from \<prefix\>

**Restrict incoming queries to clients whose source IP is within the
specified IPv4 or IPv6 prefix.**

Repeat the command to allow multiple prefixes. At least one prefix is
required for a successful commit.
```

```{note}
Restrict `allow-from` to trusted networks. Do not use `0.0.0.0/0` or
`::/0` if the service is reachable from the public Internet.
```

Example:

```none
set service dns forwarding allow-from 192.0.2.0/24
set service dns forwarding allow-from 2001:db8::/32
```

```{cfgcmd} set service dns forwarding exclude-throttle-address \<address\>

**Prevent throttling of authoritative servers matching the specified
IPv4 or IPv6 address or prefix.**

DNS forwarding throttles authoritative servers that do not answer a
query or return responses DNS forwarding rejects. This command exempts
the specified addresses from throttling. Repeat the command to add
multiple addresses.
```

Example:

```none
set service dns forwarding exclude-throttle-address 192.0.2.53
set service dns forwarding exclude-throttle-address 2001:db8::53
```

### Upstream forwarding

```{cfgcmd} set service dns forwarding name-server \<address\>

**Forward queries to the specified IPv4 or IPv6 upstream DNS server.**

The upstream servers are configured directly under DNS forwarding.
Repeat the command to configure multiple upstream servers.
```

Example:

```none
set service dns forwarding name-server 192.0.2.53
set service dns forwarding name-server 2001:db8::53
```

```{cfgcmd} set service dns forwarding name-server \<address\> port \<1-65535\>

**Configure the destination port used when forwarding queries to the
specified upstream DNS server.**

The default is 53.
```

Example:

```none
set service dns forwarding name-server 192.0.2.53 port 853
```

```{cfgcmd} set service dns forwarding system

**Forward queries to the upstream DNS servers configured under `system
name-server`.**

The upstream servers are inherited from `system name-server`.
```

Example:

```none
set service dns forwarding system
```

```{cfgcmd} set service dns forwarding dhcp \<interface\>

**Forward queries to the DNS servers learned via the DHCPv4 or DHCPv6
client on the specified interface.**

Repeat the command to forward queries to DHCP-learned servers from
multiple interfaces.
```

Example:

```none
set service dns forwarding dhcp eth0
```

```{cfgcmd} set service dns forwarding source-address \<address\>

**Configure the local IPv4 or IPv6 address used as the source when DNS
forwarding initiates outbound queries.**

The default is `0.0.0.0` and `::`, which means that the source address
is selected per outgoing query. Repeat the command to configure
multiple source addresses.
```

Example:

```none
set service dns forwarding source-address 192.0.2.1
set service dns forwarding source-address 2001:db8::1
```

```{cfgcmd} set service dns forwarding no-serve-rfc1918

**Disable authoritative answering of queries for `10.in-addr.arpa`,
`168.192.in-addr.arpa`, and `16-31.172.in-addr.arpa` zones.**

These are the reverse-lookup zones for the RFC 1918 private address
ranges. Queries for these zones are then forwarded to the configured
upstream servers.
```

Example:

```none
set service dns forwarding no-serve-rfc1918
```

```{cfgcmd} set service dns forwarding ignore-hosts-file

**Do not use the local `/etc/hosts` file in name resolution.**

By default, DNS forwarding answers queries using `/etc/hosts` before
performing recursion or forwarding.
```

Example:

```none
set service dns forwarding ignore-hosts-file
```

### Cache and timers

```{cfgcmd} set service dns forwarding cache-size \<0-2147483647\>

**Configure the maximum number of DNS cache entries.**

The default is 10000. A value of 0 disables the cache.
```

Example:

```none
set service dns forwarding cache-size 1000000
```

```{cfgcmd} set service dns forwarding negative-ttl \<0-7200\>

**Configure the maximum time, in seconds, that negative answers
(NXDOMAIN and NODATA) are cached.**

The default is 3600.
```

Example:

```none
set service dns forwarding negative-ttl 60
```

```{cfgcmd} set service dns forwarding minimum-ttl-override \<0-2147483647\>

**Configure the minimum {abbr}`TTL (Time-to-Live)`, in seconds,
applied to cached records regardless of the TTL received from the
authoritative server.**

Records with a TTL below this value are cached with this minimum
TTL. The default is `1`.
```

```{note}
Change this only if you have a specific reason to raise short TTLs,
as higher values extend caching beyond the authoritative TTL. If the
record changes upstream, clients receive the outdated cached value
until the override expires.
```

Example:

```none
set service dns forwarding minimum-ttl-override 30
```

```{cfgcmd} set service dns forwarding timeout \<10-60000\>

**Configure the time, in milliseconds, to wait for a remote
authoritative server to respond to an outgoing query.**

The default is 1500.
```

Example:

```none
set service dns forwarding timeout 2000
```

```{cfgcmd} set service dns forwarding ttl-percent \<0-100\>

**Refresh cached records in the background when the remaining TTL
falls below this percentage of the original TTL.**

Clients continue to receive the existing cached answer during refresh.
The default is 0, which disables background refresh.
```

Example:

```none
set service dns forwarding ttl-percent 10
```

```{cfgcmd} set service dns forwarding serve-stale-extension \<0-65535\>

**Configure how many times an expired record's TTL can be extended by
30 seconds when the record cannot be refreshed.**

The default is 0, which disables serving stale records.
```

Example:

```none
set service dns forwarding serve-stale-extension 30
```

### DNSSEC and NXDOMAIN behavior

```{cfgcmd} set service dns forwarding dnssec \<off | process-no-validate | process | log-fail | validate\>

**Configure the DNSSEC processing mode for outgoing queries and
responses:**

- `off`: No DNSSEC processing. DO bits in client queries are ignored,
  and no DNSSEC records are requested from authoritative servers.
- `process-no-validate`: Returns DNSSEC records (RRSIG, NSEC) to
  clients that request them, but does not validate.
- `process`: Validates responses only when the client requests it (DO
  or AD bit set). Returns `SERVFAIL` on bogus data.
- `log-fail`: Validates all responses regardless of client request,
  logs bogus responses, but returns the same answers as `process`
  mode.
- `validate`: Validates all responses and returns `SERVFAIL` on bogus
  data regardless of client request.

The default is `process-no-validate`.
```

Example:

```none
set service dns forwarding dnssec validate
```

```{cfgcmd} set service dns forwarding nothing-below-nxdomain \<no | dnssec | yes\>

**Configure how DNS forwarding handles the NXDOMAIN cut.**

When DNS forwarding has a cached NXDOMAIN, it can also return NXDOMAIN
for any name beneath the denied name, without asking upstream. This
setting controls when that behavior applies:

- `no`: Never apply the NXDOMAIN cut.
- `dnssec`: Apply the NXDOMAIN cut only for DNSSEC-validated NXDOMAIN
  entries.
- `yes`: Apply the NXDOMAIN cut for any cached NXDOMAIN that is not
  bogus.

The default is `dnssec`.
```

Example:

```none
set service dns forwarding nothing-below-nxdomain yes
```

### DNS64

```{cfgcmd} set service dns forwarding dns64-prefix \<prefix\>

**Synthesize AAAA records from A records for names that have no AAAA
records, using the specified NAT64 IPv6 prefix.**

The prefix length must be exactly `/96`.
```

Example:

```none
set service dns forwarding dns64-prefix 2001:db8:64::/96
```

### EDNS Client Subnet

```{cfgcmd} set service dns forwarding options ecs-add-for \<prefix\>

**Configure which client source address is sent as the
{abbr}`ECS (EDNS Client Subnet)` value in outgoing queries.**

For clients whose source address matches the specified prefix, the
client's real address is sent. For non-matching clients, a
placeholder address is sent instead so no client-specific subnet is
exposed.

ECS is only sent for queries matching `edns-subnet-allow-list`. This
option controls only the value, not whether ECS is sent.

Prepend `!` to exclude a prefix. Repeat the command for multiple
entries.
```

Example:

```none
set service dns forwarding options ecs-add-for 192.0.2.0/24
set service dns forwarding options ecs-add-for !192.0.2.128/25
```

```{cfgcmd} set service dns forwarding options ecs-ipv4-bits \<0-32\>

**Configure the number of bits of the client's IPv4 address included
in the ECS option sent to authoritative servers.**

Applies only to queries where ECS is sent (those matching
`edns-subnet-allow-list`).
```

Example:

```none
set service dns forwarding options ecs-ipv4-bits 24
```

```{cfgcmd} set service dns forwarding options edns-subnet-allow-list \<value\>

**Enable ECS in outgoing queries when the destination server's address
is within the specified netmask, or when the query name is under the
specified domain.**

Repeat the command to add multiple entries.
```

Example:

```none
set service dns forwarding options edns-subnet-allow-list example.com
set service dns forwarding options edns-subnet-allow-list 192.0.2.0/24
```

### Per-domain forwarding

```{cfgcmd} set service dns forwarding domain \<domain-name\> name-server \<address\>

**Forward queries for the specified domain to the given IPv4 or IPv6
upstream DNS server.**

Repeat the command to configure multiple nameservers for the same
domain. Use this option to implement split-horizon DNS. The domain may
also be a reverse-lookup zone such as `2.0.192.in-addr.arpa`.
```

Example:

```none
set service dns forwarding domain example.com name-server 192.0.2.53
set service dns forwarding domain example.com name-server 2001:db8::53
```

```{cfgcmd} set service dns forwarding domain \<domain-name\> name-server \<address\> port \<1-65535\>

**Configure the port on the given upstream DNS server to which queries
for the specified domain are forwarded.**

The default is 53.
```

Example:

```none
set service dns forwarding domain example.com name-server 192.0.2.53 port 853
```

```{cfgcmd} set service dns forwarding domain \<domain-name\> addnta

**Configure the specified domain as an {abbr}`NTA (Negative Trust
Anchor)`, disabling DNSSEC validation for it.**

Configure this when queries for a DNSSEC-broken domain return
`SERVFAIL`, so the domain becomes reachable again.
```

Example:

```none
set service dns forwarding domain example.com addnta
```

```{cfgcmd} set service dns forwarding domain \<domain-name\> recursion-desired

**Set the {abbr}`RD (Recursion Desired)` bit in queries sent to the
upstream DNS server for this domain.**
```

Example:

```none
set service dns forwarding domain example.com recursion-desired
```

### Authoritative zones

DNS forwarding can host authoritative records for a domain, answering
directly rather than forwarding or recursing queries.

```{cfgcmd} set service dns forwarding authoritative-domain \<domain-name\> disable

**Prevent DNS forwarding from serving the specified authoritative
zone, without removing it from configuration.**

Queries for names in the zone are forwarded or recursed instead.
```

Example:

```none
set service dns forwarding authoritative-domain example.com disable
```

```{cfgcmd} set service dns forwarding authoritative-domain \<domain-name\> records \<type\> \<name\> disable

**Prevent DNS forwarding from serving a specific record within the
authoritative zone, without removing it from configuration.**

Queries matching the record are forwarded or recursed instead.
```

Example:

```none
set service dns forwarding authoritative-domain example.com records a www disable
```

```{cfgcmd} set service dns forwarding authoritative-domain \<domain-name\> records \<type\> \<name\> ttl \<0-2147483647\>

**Configure the TTL, in seconds, for the specified record.**

The default is 300.
```

Example:

```none
set service dns forwarding authoritative-domain example.com records a www ttl 600
```

#### Record types

The record-type commands in this section accept the following
record-name keywords:

- `@`: Represents a zone apex, e.g., `example.com`. Accepted by every
  record type.
- `any`: Represents a wildcard record, e.g., `*.example.com`, that
  matches every subdomain under the apex. Accepted by `a` and `aaaa`
  records only.

```{cfgcmd} set service dns forwarding authoritative-domain \<domain-name\> records a \<name\> address \<ipv4-address\>

**Configure an {abbr}`A (IPv4 address)` record in the specified
authoritative zone.**

Supports `@` and `any` as `<name>`. Repeat the command to add multiple
IPv4 addresses to the same record.
```

Example:

```none
set service dns forwarding authoritative-domain example.com records a www address 192.0.2.10
```

```{cfgcmd} set service dns forwarding authoritative-domain \<domain-name\> records aaaa \<name\> address \<ipv6-address\>

**Configure an {abbr}`AAAA (IPv6 address)` record in the specified
authoritative zone.**

Supports `@` and `any` as `<name>`. Repeat the command to add multiple
IPv6 addresses to the same record.
```

Example:

```none
set service dns forwarding authoritative-domain example.com records aaaa www address 2001:db8::10
```

```{cfgcmd} set service dns forwarding authoritative-domain \<domain-name\> records cname \<name\> target \<target-domain-name\>

**Configure a {abbr}`CNAME (Canonical Name)` record in the specified
authoritative zone.**

Supports `@` as `<name>`.
```

Example:

```none
set service dns forwarding authoritative-domain example.com records cname www target host.example.com
```

```{cfgcmd} set service dns forwarding authoritative-domain \<domain-name\> records mx \<name\> server \<server\>

**Configure an {abbr}`MX (Mail Exchanger)` record in the specified
authoritative zone.**

Supports `@` as `<name>`. Repeat the command to add multiple mail
servers to the same record.
```

Example:

```none
set service dns forwarding authoritative-domain example.com records mx @ server mail.example.com
```

```{cfgcmd} set service dns forwarding authoritative-domain \<domain-name\> records mx \<name\> server \<server\> priority \<1-999\>

**Configure the priority of the specified MX record.**

Lower values are preferred. The default is 10.
```

Example:

```none
set service dns forwarding authoritative-domain example.com records mx @ server mail.example.com priority 20
```

```{cfgcmd} set service dns forwarding authoritative-domain \<domain-name\> records ns \<name\> target \<target-name\>

**Configure an {abbr}`NS (Name Server)` record in the specified
authoritative zone.**

Supports `@` as `<name>`. Repeat the command to add multiple
nameservers to the same record.
```

Example:

```none
set service dns forwarding authoritative-domain example.com records ns @ target ns1.example.com
```

```{cfgcmd} set service dns forwarding authoritative-domain \<domain-name\> records ptr \<name\> target \<target-name\>

**Configure a {abbr}`PTR (Pointer)` record in the specified
authoritative zone.**

Supports `@` as `<name>`.
```

Example:

```none
set service dns forwarding authoritative-domain 2.0.192.in-addr.arpa records ptr 10 target host.example.com
```

```{cfgcmd} set service dns forwarding authoritative-domain \<domain-name\> records txt \<name\> value \<value\>

**Configure a {abbr}`TXT (Text)` record in the specified authoritative
zone.**

Supports `@` as `<name>`. Repeat the command to add multiple TXT
strings to the same record.
```

Example:

```none
set service dns forwarding authoritative-domain example.com records txt @ value 'v=spf1 -all'
```

```{cfgcmd} set service dns forwarding authoritative-domain \<domain-name\> records spf \<name\> value \<value\>

**Configure an {abbr}`SPF (Sender Policy Framework)` record in the
specified authoritative zone.**

Supports `@` as `<name>`.
```

```{note}
SPF records are deprecated in favor of TXT records. Prefer TXT records
for new deployments.
```

Example:

```none
set service dns forwarding authoritative-domain example.com records spf @ value 'v=spf1 -all'
```

```{cfgcmd} set service dns forwarding authoritative-domain \<domain-name\> records srv \<name\> entry \<0-65535\> hostname \<name\>

**Configure the target hostname of an {abbr}`SRV (Service Locator)`
record entry in the specified authoritative zone.**

Supports `@` as `<name>`.
```

Example:

```none
set service dns forwarding authoritative-domain example.com records srv _sip._tcp entry 0 hostname sip.example.com
```

```{cfgcmd} set service dns forwarding authoritative-domain \<domain-name\> records srv \<name\> entry \<0-65535\> port \<0-65535\>

**Configure the port of an SRV record entry in the specified
authoritative zone.**
```

Example:

```none
set service dns forwarding authoritative-domain example.com records srv _sip._tcp entry 0 port 5060
```

```{cfgcmd} set service dns forwarding authoritative-domain \<domain-name\> records srv \<name\> entry \<0-65535\> priority \<0-65535\>

**Configure the priority of an SRV record entry in the specified
authoritative zone.**

Lower values are preferred. The default is 10.
```

Example:

```none
set service dns forwarding authoritative-domain example.com records srv _sip._tcp entry 0 priority 20
```

```{cfgcmd} set service dns forwarding authoritative-domain \<domain-name\> records srv \<name\> entry \<0-65535\> weight \<0-65535\>

**Configure the weight of an SRV record entry in the specified
authoritative zone.**

Weight is used to distribute load among entries with equal priority.
The default is 0.
```

Example:

```none
set service dns forwarding authoritative-domain example.com records srv _sip._tcp entry 0 weight 50
```

```{cfgcmd} set service dns forwarding authoritative-domain \<domain-name\> records naptr \<name\> rule \<0-65535\> order \<0-65535\>

**Configure the order field of a {abbr}`NAPTR (Naming Authority
Pointer)` rule in the specified authoritative zone.**

Supports `@` as `<name>`. Rules with lower order are evaluated first.
```

Example:

```none
set service dns forwarding authoritative-domain example.com records naptr @ rule 100 order 10
```

```{cfgcmd} set service dns forwarding authoritative-domain \<domain-name\> records naptr \<name\> rule \<0-65535\> preference \<0-65535\>

**Configure the preference field of a NAPTR rule in the specified
authoritative zone.**

Supports `@` as `<name>`. The default is 0.
```

Example:

```none
set service dns forwarding authoritative-domain example.com records naptr @ rule 100 preference 50
```

```{cfgcmd} set service dns forwarding authoritative-domain \<domain-name\> records naptr \<name\> rule \<0-65535\> lookup-a

**Set the A flag on a NAPTR rule in the specified authoritative
zone.**

When set, DNS forwarding treats the rule's output as a domain name and
looks up its A or AAAA record. No further NAPTR lookups follow.
```

```{note}
Set at most one of `lookup-a`, `lookup-srv`, `resolve-uri`, and
`protocol-specific` on the same NAPTR rule. These flags define
mutually exclusive next actions in the DNS resolution.
```

Example:

```none
set service dns forwarding authoritative-domain example.com records naptr @ rule 100 lookup-a
```

```{cfgcmd} set service dns forwarding authoritative-domain \<domain-name\> records naptr \<name\> rule \<0-65535\> lookup-srv

**Set the S flag on a NAPTR rule in the specified authoritative
zone.**

When set, DNS forwarding treats the rule's output as a domain name and
looks up its SRV record. No further NAPTR lookups follow.
```

Example:

```none
set service dns forwarding authoritative-domain example.com records naptr @ rule 100 lookup-srv
```

```{cfgcmd} set service dns forwarding authoritative-domain \<domain-name\> records naptr \<name\> rule \<0-65535\> resolve-uri

**Set the U flag on a NAPTR rule in the specified authoritative
zone.**

When set, DNS forwarding treats the rule's output as a URI and uses it
directly. No further DNS lookups follow.
```

Example:

```none
set service dns forwarding authoritative-domain example.com records naptr @ rule 100 resolve-uri
```

```{cfgcmd} set service dns forwarding authoritative-domain \<domain-name\> records naptr \<name\> rule \<0-65535\> protocol-specific

**Set the P flag on a NAPTR rule in the specified authoritative
zone.**

When set, DNS forwarding treats the rule's output according to the
associated application protocol. No further DNS lookups follow.
```

Example:

```none
set service dns forwarding authoritative-domain example.com records naptr @ rule 100 protocol-specific
```

```{cfgcmd} set service dns forwarding authoritative-domain \<domain-name\> records naptr \<name\> rule \<0-65535\> service \<service\>

**Configure the Service field of a NAPTR rule in the specified
authoritative zone.**

Defines the protocol and resolution service this rule offers in
`Protocol+ResolutionService` format (for example, SIP over TCP →
`SIP+D2T`).
```

Example:

```none
set service dns forwarding authoritative-domain example.com records naptr @ rule 100 service SIP+D2T
```

```{cfgcmd} set service dns forwarding authoritative-domain \<domain-name\> records naptr \<name\> rule \<0-65535\> regexp \<expression\>

**Configure the Regexp field of a NAPTR rule in the specified
authoritative zone.**

A substitution expression in `!ere!replacement!` format, applied to
the query name to produce the next-lookup target or URI.
```

```{note}
A rule uses either `regexp` or `replacement`, not both. Setting both
produces a malformed NAPTR record.
```

Example:

```none
set service dns forwarding authoritative-domain example.com records naptr @ rule 100 regexp !^.*$!sip:helpdesk@example.com!
```

```{cfgcmd} set service dns forwarding authoritative-domain \<domain-name\> records naptr \<name\> rule \<0-65535\> replacement \<target-name\>

**Configure the Replacement field of a NAPTR rule in the specified
authoritative zone.**

An absolute DNS name used as the target of the next lookup, whose type
depends on the rule's flag.
```

Example:

```none
set service dns forwarding authoritative-domain example.com records naptr @ rule 100 replacement sip.example.com
```

### Zone caching

DNS forwarding can load a zone directly into its cache via
AXFR or from a zone file at a URL.
Zone caching is configured under
`service dns forwarding zone-cache <domain-name>`.

```{cfgcmd} set service dns forwarding zone-cache \<domain-name\> source axfr \<address\>

**Configure DNS forwarding to load the specified zone via AXFR from
the given IPv4 or IPv6 DNS server.**
```

Example:

```none
set service dns forwarding zone-cache example.com source axfr 192.0.2.53
```

```{cfgcmd} set service dns forwarding zone-cache \<domain-name\> source url \<url\>

**Configure DNS forwarding to load the specified zone from the given
HTTP(S) URL pointing to a zone file.**
```

Example:

```none
set service dns forwarding zone-cache example.com source url https://zones.example.com/example.com.zone
```

```{cfgcmd} set service dns forwarding zone-cache \<domain-name\> options timeout \<1-3600\>

**Configure how long, in seconds, DNS forwarding waits for the zone to
be retrieved before aborting the attempt.**

The default is 20.
```

Example:

```none
set service dns forwarding zone-cache example.com options timeout 60
```

```{cfgcmd} set service dns forwarding zone-cache \<domain-name\> options refresh interval \<0-31536000\>

**Configure the interval, in seconds, between periodic retrievals of
the zone into the cache.**

The default is 86400. A value of 0 disables periodic refresh.
```

Example:

```none
set service dns forwarding zone-cache example.com options refresh interval 3600
```

```{cfgcmd} set service dns forwarding zone-cache \<domain-name\> options refresh on-reload

**Retrieve the zone into the cache only at startup and when the
service is reloaded.**
```

Example:

```none
set service dns forwarding zone-cache example.com options refresh on-reload
```

```{cfgcmd} set service dns forwarding zone-cache \<domain-name\> options retry-interval \<1-86400\>

**Configure the interval, in seconds, before retrying zone retrieval
after an error.**

The default is 60.
```

Example:

```none
set service dns forwarding zone-cache example.com options retry-interval 300
```

```{cfgcmd} set service dns forwarding zone-cache \<domain-name\> options max-zone-size \<0-1024\>

**Configure the maximum size, in megabytes, of a zone loaded into the
cache.**

The default is 0, which imposes no limit.
```

Example:

```none
set service dns forwarding zone-cache example.com options max-zone-size 100
```

```{cfgcmd} set service dns forwarding zone-cache \<domain-name\> options zonemd \<ignore | validate | require\>

**Configure how DNS forwarding treats the ZONEMD digest of a retrieved
zone:**

- `ignore`: Does not check the ZONEMD digest.
- `validate`: Validates the ZONEMD digest if present.
- `require`: Rejects the zone unless a valid ZONEMD digest is present.

The default is `validate`.
```

Example:

```none
set service dns forwarding zone-cache example.com options zonemd require
```

```{cfgcmd} set service dns forwarding zone-cache \<domain-name\> options dnssec \<ignore | validate | require\>

**Configure the DNSSEC validation policy for a retrieved zone:**

- `ignore`: No DNSSEC validation.
- `validate`: Rejects zones with incorrect signatures but accepts
  unsigned zones.
- `require`: Rejects the zone unless it is DNSSEC-signed and passes
  signature validation.

The default is `validate`.
```

Example:

```none
set service dns forwarding zone-cache example.com options dnssec require
```

## Operation

### Show

```{opcmd} show dns forwarding statistics

**Show operational statistics collected by DNS forwarding.**
```

```{opcmd} show log dns forwarding

**Show log entries for DNS forwarding since the last boot.**
```

```{opcmd} monitor log dns forwarding

**Follow the DNS forwarding service log in real time.**
```

### Reset and restart

```{opcmd} reset dns forwarding all

**Clear the entire DNS forwarding cache.**
```

```{opcmd} reset dns forwarding domain \<domain-name\>

**Clear the DNS forwarding cache entries for the specified domain
only.**
```

```{opcmd} restart dns forwarding

**Restart the DNS forwarding service.**

Restarting the service also clears its cache.
```

## Example

The following configuration implements split-horizon DNS for
`example.com` on a VyOS router with two interfaces (`eth0` WAN, `eth1`
LAN):

- DNS queries for `example.com` are forwarded to `192.0.2.254` and
  `2001:db8:cafe::1`.
- All other DNS queries are forwarded to a set of upstream servers,
  two of which use non-standard ports.
- DNS forwarding listens only on LAN interface addresses.
- DNS forwarding accepts DNS queries only from LAN clients.
- Reverse lookups for RFC 1918 zones are forwarded upstream rather
  than answered locally.

```none
set service dns forwarding domain example.com name-server 192.0.2.254
set service dns forwarding domain example.com name-server 2001:db8:cafe::1
set service dns forwarding name-server 192.0.2.1
set service dns forwarding name-server 192.0.2.2
set service dns forwarding name-server 192.0.2.3 port 853
set service dns forwarding name-server 2001:db8::1:ffff
set service dns forwarding name-server 2001:db8::2:ffff
set service dns forwarding name-server 2001:db8::3:ffff port 8053
set service dns forwarding listen-address 192.168.1.254
set service dns forwarding listen-address 2001:db8::ffff
set service dns forwarding allow-from 192.168.1.0/24
set service dns forwarding allow-from 2001:db8::/64
set service dns forwarding no-serve-rfc1918
```
