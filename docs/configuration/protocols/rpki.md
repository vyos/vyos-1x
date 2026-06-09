---
myst:
  html_meta:
    description: |
      Resource Public Key Infrastructure (RPKI) is an architecture designed
      to secure the internet routing infrastructure by cryptographically
      associating IP address prefixes with their originating ASNs.
    keywords: rpki, roa, bgp, routing security, rtr, validator, asn
---

(rpki)=

# RPKI

{abbr}`RPKI (Resource Public Key Infrastructure)` is an architecture designed
to secure the internet routing infrastructure. It cryptographically associates
IP address prefixes with the correct originating
{abbr}`ASNs (Autonomous System Numbers)`. BGP routers can use this data to
check the origin of each route against the corresponding
{abbr}`ROA (Route Origin Authorization)` for validity. RPKI is described in
[RFC 6480](https://datatracker.ietf.org/doc/html/rfc6480).

BGP routers can retrieve ROA information from RPKI Relying Party software,
also known as an RPKI server or validator, using the RTR protocol. Open-source
implementations include NLnet Labs'
[Routinator](https://www.nlnetlabs.nl/projects/routing/routinator/) (Rust),
OpenBSD's [rpki-client](https://www.rpki-client.org/) (C), and
[StayRTR](https://github.com/bgp/stayrtr) (Go). The RTR protocol is described
in [RFC 8210](https://datatracker.ietf.org/doc/html/rfc8210).

```{tip}
If you are new to routing security, the
[RPKI Documentation](https://rpki.readthedocs.io/) maintained by NLnet Labs
will quickly get you up to speed. It covers everything from fundamental
concepts to production deployment.
```

## Getting started

First, you need to deploy an RPKI validator for your routers. The
[RPKI Documentation](https://rpki.readthedocs.io/) maintained by NLnet Labs
provides a comprehensive list of open-source software packages you can compare
and choose from. Once your chosen server is running, your routers can start
validating announcements.

After validation, imported routes may have one of the following states:

- `valid`: The prefix and originating ASN match a signed ROA. These route
  announcements are considered trustworthy.
- `invalid`: The prefix, prefix length, or originating ASN does not match
  any existing ROA. This may indicate a prefix hijack or misconfiguration
  and should be treated as untrustworthy.
- `notfound`: No ROA covers the prefix. As of early 2024, this applies to
  approximately 40% to 50% of prefixes announced to the
  {abbr}`DFZ (Default-Free Zone)`.

```{note}
If you manage global IP addresses for your network, ensure their prefixes
have associated ROAs to prevent them from being marked as `notfound` by
RPKI.
```

For most network operators, this involves publishing ROAs through their
respective {abbr}`RIR (Regional Internet Registry)`, such as ARIN, RIPE NCC,
APNIC, LACNIC, or AFRINIC. It is highly recommended to create ROAs for any IP
prefixes you plan to announce into the DFZ.

Particularly large networks may choose to run their own RPKI certificate
authority and publication server instead of publishing ROAs via their RIR.
This subject is beyond the scope of VyOS documentation. For more information,
consider reviewing resources about
[Krill](https://www.nlnetlabs.nl/projects/routing/krill/).

## Current implementation

The current implementation includes the following features:

- The BGP router connects to one or more RPKI cache servers to receive
  validated prefix-to-origin AS mappings. Advanced failover can be
  implemented by configuring multiple cache servers with different
  preference values.
- If no connection to an RPKI cache server is established after a predefined
  timeout, the router processes routes without prefix origin validation. It
  will continue attempting to connect to an RPKI cache server in the
  background.
- By default, enabling RPKI does not affect best path selection. Invalid
  prefixes are still considered during best path selection, but you can
  configure the router to ignore them.
- You can configure route maps to match a specific RPKI validation state.
  This enables the creation of local policies that handle BGP routes based
  on Prefix Origin Validation results.
- Updates from RPKI cache servers are applied directly, and path selection
  is updated accordingly. Note: BGP soft reconfiguration must be enabled
  for this feature to work.

## Configuration

```{cfgcmd} set protocols rpki polling-period \<1-86400\>

**Configure the interval, in seconds, at which the router polls the RPKI
cache server for updates.**

The default value is 300 seconds.
```

Example:

```none
set protocols rpki polling-period 600
```

```{cfgcmd} set protocols rpki expire-interval \<600-172800\>

**Configure the interval, in seconds, after which the router expires its
cached RPKI data.**

The default value is 7200 seconds.
```

Example:

```none
set protocols rpki expire-interval 14400
```

```{cfgcmd} set protocols rpki retry-interval \<1-7200\>

**Configure the interval, in seconds, before the router retries a failed
connection to the RPKI cache server.**

The default value is 600 seconds.
```

Example:

```none
set protocols rpki retry-interval 60
```

```{cfgcmd} set protocols rpki cache \<address\> port \<1-65535\>

**Configure the address and port of an RPKI cache server.**

The address can be specified as an IPv4 or IPv6 address, or as a
{abbr}`FQDN (Fully Qualified Domain Name)`.
```

```{note}
You need to configure both `port` and `preference` for each cache server
IP address.
```

Example:

```none
set protocols rpki cache 192.0.2.1 port 3323
```

```{cfgcmd} set protocols rpki cache \<address\> preference \<1-255\>

**Configure the preference value for an RPKI cache server.**

When multiple cache servers are configured, the router prioritizes
connecting to the server with the lowest preference value.
```

```{note}
You need to configure both `port` and `preference` for each cache server
IP address.
```

```{note}
`preference` values must be unique across cache servers.
```

Example:

```none
set protocols rpki cache 192.0.2.1 preference 1
```

### SSH

You can connect to the RPKI cache server using the RTR protocol over plain
TCP or over SSH. SSH provides transport integrity and confidentiality. Use
SSH if your validation software supports this option.

To use SSH authentication, complete the following steps:

   **Step 1.** Generate an SSH client keypair:

```{opcmd} generate ssh client-key /config/auth/id_rsa_rpki
```

   **Step 2.** Extract the base64 portion from both keys, plus the public
   key's algorithm identifier:

```bash
   grep -v "PRIVATE KEY" /config/auth/id_rsa_rpki | tr -d '\n'
   awk '{print $2}' /config/auth/id_rsa_rpki.pub
   awk '{print $1}' /config/auth/id_rsa_rpki.pub
```

```{note}
   The PKI subsystem accepts only the base64 portion of each key, without
   any PEM/OpenSSH headers, footer, or line breaks. If you paste the file
   contents directly, the commit fails.
```

   **Step 3.** Import the keypair into the PKI subsystem:

```none
   set pki openssh <name> private key <base64-encoded-private-key>
   set pki openssh <name> public key <base64-encoded-public-key>
   set pki openssh <name> public type <type>
```

Once the keypair is imported, set up the SSH connection using the commands
below.

```{cfgcmd} set protocols rpki cache \<address\> ssh username \<user\>

**Configure the SSH username for authenticating to the RPKI cache server.**
```

Example:

```none
set protocols rpki cache 192.0.2.1 ssh username rpki-user
```

```{cfgcmd} set protocols rpki cache \<address\> ssh key \<name\>

**Configure the name of the OpenSSH keypair used to authenticate to the RPKI
cache server.**

The `<name>` must match a keypair name previously defined under the
`set pki openssh` commands.
```

Example:

```none
set protocols rpki cache 192.0.2.1 ssh key rpki
```

## Example

The following example demonstrates how to connect to an RPKI cache server
(such as Routinator) and build an import route-map to filter prefixes based
on their validation state.

First, configure the connection to the RPKI cache server at `192.0.2.1`:

```none
set protocols rpki cache 192.0.2.1 port '3323'
set protocols rpki cache 192.0.2.1 preference '1'
```

Next, create a route-map to apply to your incoming BGP updates. This policy
dictates the following behavior:

- Permits `valid` prefixes and assigns a high local-preference (300).
- Permits `notfound` prefixes but assigns a lower local-preference (125).
- Rejects prefixes with an `invalid` state.

```none
set policy route-map ROUTES-IN rule 10 action 'permit'
set policy route-map ROUTES-IN rule 10 match rpki 'valid'
set policy route-map ROUTES-IN rule 10 set local-preference '300'

set policy route-map ROUTES-IN rule 20 action 'permit'
set policy route-map ROUTES-IN rule 20 match rpki 'notfound'
set policy route-map ROUTES-IN rule 20 set local-preference '125'

set policy route-map ROUTES-IN rule 30 action 'deny'
set policy route-map ROUTES-IN rule 30 match rpki 'invalid'
```

After configuring your routers to reject RPKI-invalid prefixes, verify the
setup using [Cloudflare's test website](https://isbgpsafe.com/).

```{note}
Ensure there are no default routes or other paths that would direct traffic
to RPKI-invalid destinations. Otherwise, the test may report the router as
unsafe.
```
