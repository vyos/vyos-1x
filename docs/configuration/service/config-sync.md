---
myst:
  html_meta:
    description: |
      Config sync is a VyOS service that replicates selected sections of
      one router's configuration to another by pushing changes from a
      primary to a secondary over the HTTPS API.
    keywords: config-sync, configuration synchronization, primary, secondary, https api
---

(config-sync)=

# Config sync

Configuration synchronization (config-sync) is a VyOS service that
replicates selected sections of one router's configuration to another
router. It eliminates the need to manually mirror configuration changes
from a primary router to a secondary.

Synchronization is performed by a post-commit hook on the primary
router. The hook watches the sections selected for synchronization. When
any of them is modified by a commit, the hook calls the HTTPS API on the
secondary router and sends the current state of all selected sections in
one of the following modes:

- `load`: Replaces the selected sections on the secondary with the
  primary's version. Anything that exists only on the secondary inside
  those sections is removed.
- `set`: Merges the primary's version of the selected sections into the
  secondary. Conflicting values are overwritten by the primary. Entries
  that exist only on the secondary are kept.

Synchronization is strictly unidirectional from primary to secondary;
changes made on the secondary are not sent back.

Both routers must be online during a commit on the primary that modifies
a configured section. If the secondary is unreachable, the primary's
commit still succeeds, but the configuration is not synchronized, and
the failure is recorded in the system log.

## Configuration

### Secondary router parameters

```{cfgcmd} set service config-sync secondary address \<address\>

**Configure the address of the secondary router.**

The primary router pushes the synchronized configuration to this address
over the secondary's HTTPS API. The value can be an IPv4 address, an
IPv6 address, or an {abbr}`FQDN (Fully Qualified Domain Name)`. This
value is mandatory.
```

```{note}
The address must be set whenever `service config-sync` is configured.
Otherwise, the commit is rejected.
```

Example:

```none
set service config-sync secondary address 192.0.2.112
```

```{cfgcmd} set service config-sync secondary port \<1-65535\>

**Configure the TCP port on which the secondary router's HTTPS API
listens.**

The value must match the port configured under `service https port` on
the secondary router. If they diverge, the primary's commit succeeds,
but the post-commit sync fails. The secondary is not updated, and the
primary logs the error to the system log.

The default is 443, matching the default of `service https port`.
```

Example:

```none
set service config-sync secondary port 8443
```

```{cfgcmd} set service config-sync secondary key \<key\>

**Configure the HTTPS API key the primary router uses to authenticate
to the secondary router's HTTPS API.**

The value must match a key configured under `service https api keys id
<ID> key` on the secondary. If no matching key exists on the secondary,
the primary's commit still succeeds, but the post-commit sync fails.
The secondary is not updated, and the primary logs the error to the
system log.
```

```{note}
This value must be set whenever `service config-sync` is configured.
Otherwise, the commit is rejected.
```

Example:

```none
set service config-sync secondary key 'foo'
```

```{cfgcmd} set service config-sync secondary timeout \<1-3600\>

**Configure how long, in seconds, the primary router waits for an HTTPS
response from the secondary after pushing configuration.**

The default is 60 seconds.
```

Example:

```none
set service config-sync secondary timeout 120
```

### Synchronization mode

```{cfgcmd} set service config-sync mode \<load | set\>

**Configure how the secondary router applies the configuration pushed
by the primary:**

- `load`: Replaces the selected sections on the secondary with the
  primary's version. Anything that exists only on the secondary inside
  those sections is removed.
- `set`: Merges the primary's version of the selected sections into the
  secondary. Conflicting values are overwritten by the primary. Entries
  that exist only on the secondary are kept.
```

```{note}
This value must be set whenever `service config-sync` is configured.
Otherwise, the commit is rejected.
```

Example:

```none
set service config-sync mode load
```

### Sections to synchronize

```{cfgcmd} set service config-sync section \<section\>

**Configure one or more configuration sections to be synchronized from
the primary to the secondary router.**

Repeat the command to add additional sections. If any configured
section was modified by a commit on the primary, the hook pushes the
current state of all configured sections to the secondary. If none of
the configured sections were modified, the hook does nothing.

Supported sections:

- `firewall`
- `interfaces <bonding | bridge | dummy | ethernet | geneve | input |
  l2tpv3 | loopback | macsec | openvpn | pppoe | pseudo-ethernet |
  sstpc | tunnel | virtual-ethernet | vti | vxlan | wireguard |
  wireless | wwan>`
- `nat`
- `nat66`
- `pki`
- `policy`
- `protocols <babel | bfd | bgp | failover | igmp-proxy | isis | mpls |
  nhrp | ospf | ospfv3 | pim | pim6 | rip | ripng | rpki |
  segment-routing | static>`
- `qos <interface | policy>`
- `service <console-server | dhcp-relay | dhcp-server | dhcpv6-relay |
  dhcpv6-server | dns | lldp | mdns | monitoring | ndp-proxy | ntp |
  snmp | tftp-server | webproxy>`
- `system <conntrack | flow-accounting | login | option | sflow |
  static-host-mapping | sysctl | time-zone>`
- `vpn`
- `vrf`
```

```{note}
At least one section must be set whenever `service config-sync` is
configured. Otherwise, the commit is rejected.
```

Example:

```none
set service config-sync section protocols ospf
set service config-sync section system time-zone
```

## Operation

```{opcmd} show configuration secondary sync [commands] [running | candidate | saved [\<config-node-path\>]]

**Show the difference between the local configuration on the primary
and the running configuration on the secondary.**

The command fetches the secondary's running configuration live over the
HTTPS API, so the secondary must be reachable.

The local configuration defaults to `running` and can be set to
`candidate` (uncommitted changes) or `saved` (last saved configuration).
The remote side is always the secondary's running configuration.

By default, the difference is shown in the curly-brace configuration
format with `-` prefixing lines that exist only on the secondary and
`+` prefixing lines that exist only on the primary. The optional
`commands` keyword renders the same difference as a sequence of `set`
and `delete` configuration commands, where `set` lists paths present
only on the primary, and `delete` lists paths present only on the
secondary.

The optional `<config-node-path>` argument limits the difference to a
single section and must be one of the sections already configured under
`set service config-sync section`. If omitted, the difference covers
all configured sections.
```

Examples:

```none
# Compare the full running configuration against the secondary
show configuration secondary sync

# Compare only the OSPF protocol configuration against the secondary
show configuration secondary sync running protocols ospf

# Compare the candidate configuration against the secondary,
# rendered as commands
show configuration secondary sync commands candidate
```

## Example

The following example synchronizes the `system time-zone` and
`protocols ospf` sections from Router A (primary, `192.0.2.1`) to
Router B (secondary, `192.0.2.112`). Router B's HTTPS API listens on
TCP port 8443.

Enable and configure the HTTPS API service on Router B:

```none
set service https listen-address '192.0.2.112'
set service https port '8443'
set service https api keys id primary key 'foo'
set service https api rest
```

Configure the config-sync service on Router A:

```none
set service config-sync mode 'load'
set service config-sync secondary address '192.0.2.112'
set service config-sync secondary port '8443'
set service config-sync secondary key 'foo'
set service config-sync section protocols 'ospf'
set service config-sync section system 'time-zone'
```

Make changes on Router A that fall under one of the synchronized
sections. The post-commit hook fires automatically on commit:

```none
vyos@vyos-A# set system time-zone 'America/Los_Angeles'
vyos@vyos-A# commit
INFO:vyos_config_sync:Config synchronization: Mode=load, Secondary=192.0.2.112
vyos@vyos-A# save

vyos@vyos-A# set protocols ospf area 0 network '198.51.100.0/30'
vyos@vyos-A# commit
INFO:vyos_config_sync:Config synchronization: Mode=load, Secondary=192.0.2.112
vyos@vyos-A# save
```

Each commit on Router A modifies one section, but because the hook
pushes all configured sections whenever any of them is modified, both
commits replace the full state of `system` and `protocols ospf` on
Router B.

Verify that the changes have been applied on Router B:

```none
vyos@vyos-B:~$ show configuration commands | match time-zone
set system time-zone 'America/Los_Angeles'

vyos@vyos-B:~$ show configuration commands | match ospf
set protocols ospf area 0 network '198.51.100.0/30'
```
