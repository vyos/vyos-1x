---
myst:
  html_meta:
    description: |
      Dynamic DNS is a VyOS service that keeps a DNS record updated
      with the current IP address of an interface. It supports direct
      DNS updates via RFC 2136 and hosted updates via third-party
      dynamic DNS providers such as Cloudflare, DuckDNS, deSEC, and
      DynDNS.
    keywords: dynamic dns, ddns, rfc 2136, nsupdate, cloudflare, dyndns
---

(dynamic-dns)=

# Dynamic DNS

The dynamic DNS service updates the DNS record (an A record for IPv4 or
an AAAA record for IPv6) that maps your hostname to your device whenever
your IP address changes, so you can always reach your device by
hostname.

Two update mechanisms are available:

- Direct DNS update ([RFC 2136](https://datatracker.ietf.org/doc/html/rfc2136)):
  Updates the record by sending an RFC 2136 DNS UPDATE message to an
  authoritative DNS server. Use this option when you run your own DNS
  server.
- Hosted DNS update: Updates the record by sending an HTTP(S) update
  request to a third-party dynamic DNS provider (such as Cloudflare,
  DuckDNS, deSEC, or DynDNS). Use this option when relying on an
  external provider.

## Configuration

### Common commands

The following commands apply to both direct and hosted DNS updates.

```{cfgcmd} set service dns dynamic name \<service-name\> address interface \<interface\>

**Configure the interface whose IP address the dynamic DNS record
points to.**
```

```{note}
Mutually exclusive with `address web` within the same dynamic DNS
`<service-name>` configuration.
```

Example:

```none
set service dns dynamic name VyOS-DNS address interface eth0
```

```{cfgcmd} set service dns dynamic name \<service-name\> description \<text\>

**Configure a description for the dynamic DNS service configuration.**

Limited to 255 characters.
```

Example:

```none
set service dns dynamic name VyOS-DNS description 'RFC 2136 dynamic DNS service'
```

```{cfgcmd} set service dns dynamic name \<service-name\> host-name \<hostname\>

**Configure a hostname whose DNS record is kept updated with the current
IP address.**

Accepts a standard hostname, `@` for the zone apex, or `*` for a
wildcard record. Repeat the command to add several hostnames to the
same dynamic DNS `<service-name>` configuration.
```

Example:

```none
set service dns dynamic name VyOS-DNS host-name host.example.com
```

```{cfgcmd} set service dns dynamic name \<service-name\> protocol \<protocol\>

**Configure the protocol used to send updates.**

Use `nsupdate` for direct DNS updates, or a provider-specific protocol
such as `cloudflare`, `dyndns2`, or `duckdns` for hosted DNS updates.
Use CLI tab-completion to list the available protocols.
```

Example:

```none
set service dns dynamic name VyOS-DNS protocol nsupdate
```

```{cfgcmd} set service dns dynamic name \<service-name\> server \<server\>

**Configure the IP address or {abbr}`FQDN (Fully Qualified Domain Name)`
of the authoritative DNS server (direct DNS updates), or the provider's
endpoint (hosted DNS updates).**

Required for `nsupdate` and optional for HTTP(S)-based protocols.
```

Example:

```none
set service dns dynamic name VyOS-DNS server ns1.example.com
```

```{cfgcmd} set service dns dynamic name \<service-name\> zone \<zone\>

**Configure the DNS zone that contains the configured hostnames.**

The value must be an FQDN. Required for protocols `cloudflare`,
`digitalocean`, `godaddy`, `hetzner`, `gandi`, `nfsn`, and `nsupdate`.
Also accepted for `dnsexit2` and `zoneedit1`. Not supported for any
other protocol.
```

Example:

```none
set service dns dynamic name VyOS-DNS zone example.com
```

```{cfgcmd} set service dns dynamic name \<service-name\> ttl \<0-2147483647\>

**Configure the {abbr}`TTL (Time-To-Live)`, in seconds, of the updated
DNS records.**

The TTL sets how long DNS resolvers may cache the record before it must
be re-fetched. Supported only for protocols `cloudflare`, `dnsexit2`,
`gandi`, `godaddy`, `hetzner`, `nfsn`, and `nsupdate`. When unset, no
TTL is included in the update.
```

Example:

```none
set service dns dynamic name VyOS-DNS ttl 300
```

```{cfgcmd} set service dns dynamic name \<service-name\> ip-version \<ipv4 | ipv6 | both\>

**Configure which DNS record types are updated:**

- `ipv4`: Updates the A record only.
- `ipv6`: Updates the AAAA record only.
- `both`: Updates both the A and AAAA records.

The default is `ipv4`.

`both` is supported only for protocols `cloudflare`, `digitalocean`,
`dnsexit2`, `duckdns`, `dyndns2`, `easydns`, `freedns`, `hetzner`,
`infomaniak`, and `njalla`.
```

Example:

```none
set service dns dynamic name VyOS-DNS ip-version ipv6
```

```{cfgcmd} set service dns dynamic interval \<60-3600\>

**Configure the interval, in seconds, between updates of the configured
DNS records.**

The default is 300.
```

Example:

```none
set service dns dynamic interval 300
```

### Running behind NAT

By default, the IP address configured under `address interface` is what
gets registered. When VyOS is behind NAT, this is the internal address
that cannot be reached from the public Internet. Configure `address web`
instead so the DNS record points to the public IP address.

```{cfgcmd} set service dns dynamic name \<service-name\> address web url \<url\>

**Configure an HTTP(S) URL from which dynamic DNS obtains the IP address
for the DNS record.**
```

```{note}
Mutually exclusive with `address interface` within the same dynamic DNS
`<service-name>` configuration.
```

Example:

```none
set service dns dynamic name VyOS-DNS address web url https://ipv4.icanhazip.com
```

```{cfgcmd} set service dns dynamic name \<service-name\> address web skip \<pattern\>

**Configure dynamic DNS to ignore URL response text before the
specified pattern when extracting the public IP address.**
```

```{note}
Requires `address web url` to be set within the same dynamic DNS
`<service-name>` configuration.
```

Example:

```none
set service dns dynamic name VyOS-DNS address web skip 'Current IP Address:'
```

### Direct DNS update (RFC 2136)

```{cfgcmd} set service dns dynamic name \<service-name\> key \<filename\>

**Configure the file containing the {abbr}`TSIG (Transaction Signature)`
key used to authenticate direct DNS update messages.**

The file must be within the `/config/auth` directory. Required when
`protocol` is `nsupdate`; other protocols use `password` instead.
```

Example:

```none
set service dns dynamic name VyOS-DNS key /config/auth/my.key
```

### Hosted (provider-based) DNS update

```{cfgcmd} set service dns dynamic name \<service-name\> username \<username\>

**Configure the username presented in HTTP(S) update requests to the
dynamic DNS provider.**

Required for most protocols. Not required for `1984`, `cloudflare`,
`cloudns`, `digitalocean`, `dnsexit2`, `duckdns`, `freemyip`, `hetzner`,
`keysystems`, `njalla`, `nsupdate`, and `regfishde`.
```

Example:

```none
set service dns dynamic name dedyn username myusername
```

```{cfgcmd} set service dns dynamic name \<service-name\> password \<password\>

**Configure the password, or provider API token, presented in HTTP(S)
update requests to the dynamic DNS provider.**

Required for every protocol except `nsupdate`, which uses `key` instead.
```

Example:

```none
set service dns dynamic name dedyn password mypassword
```

## Examples

### Direct DNS update ([RFC 2136](https://datatracker.ietf.org/doc/html/rfc2136))

The following example registers the DNS record `example.vyos.io` on the
DNS server `ns1.vyos.io`, keeps it updated with the current IP address
of `eth0`, authenticates updates with the TSIG key at
`/config/auth/my.key`, and sets a TTL of 300 seconds.

```none
set service dns dynamic name VyOS-DNS address interface 'eth0'
set service dns dynamic name VyOS-DNS description 'RFC 2136 dynamic DNS service'
set service dns dynamic name VyOS-DNS key '/config/auth/my.key'
set service dns dynamic name VyOS-DNS server 'ns1.vyos.io'
set service dns dynamic name VyOS-DNS zone 'vyos.io'
set service dns dynamic name VyOS-DNS host-name 'example.vyos.io'
set service dns dynamic name VyOS-DNS protocol 'nsupdate'
set service dns dynamic name VyOS-DNS ttl '300'
```

Resulting configuration:

```none
vyos@vyos# show service dns dynamic
 name VyOS-DNS {
     address {
         interface eth0
     }
     description "RFC 2136 dynamic DNS service"
     host-name example.vyos.io
     key /config/auth/my.key
     protocol nsupdate
     server ns1.vyos.io
     ttl 300
     zone vyos.io
 }
```

```{note}
You can define multiple dynamic DNS `<service-name>` configurations,
each registering its own set of DNS records.
```

### Hosted (provider-based) DNS update

The following example registers the DNS record `myhostname.dedyn.io`
with deSEC via the `dyndns2` protocol, keeps it updated with the current
IP address of `eth0`, and authenticates updates with the configured
username and password.

```none
set service dns dynamic name dedyn description 'deSEC dynamic DNS service'
set service dns dynamic name dedyn username 'myusername'
set service dns dynamic name dedyn password 'mypassword'
set service dns dynamic name dedyn host-name 'myhostname.dedyn.io'
set service dns dynamic name dedyn protocol 'dyndns2'
set service dns dynamic name dedyn server 'update.dedyn.io'
set service dns dynamic name dedyn address interface 'eth0'
```

```{note}
You can define multiple dynamic DNS `<service-name>` configurations,
each registering its own set of DNS records.
```

The following example is the same as above, but restricted to IPv6: the
AAAA record for `myhostname.dedyn.io` is updated with the current IPv6
address of `eth0`, using deSEC's IPv6 update endpoint
`update6.dedyn.io`.

```none
set service dns dynamic name dedyn description 'deSEC IPv6 dynamic DNS service'
set service dns dynamic name dedyn username 'myusername'
set service dns dynamic name dedyn password 'mypassword'
set service dns dynamic name dedyn host-name 'myhostname.dedyn.io'
set service dns dynamic name dedyn protocol 'dyndns2'
set service dns dynamic name dedyn ip-version 'ipv6'
set service dns dynamic name dedyn server 'update6.dedyn.io'
set service dns dynamic name dedyn address interface 'eth0'
```
