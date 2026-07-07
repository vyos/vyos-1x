---
myst:
  html_meta:
    description: |
      Suricata is an open-source network threat detection engine
      integrated in VyOS as a managed service. It performs intrusion
      detection, inline intrusion prevention, and network security
      monitoring by matching live traffic against rules.
    keywords: suricata, ids, ips, nsm, intrusion detection, intrusion
      prevention, network security monitoring, eve, address group, port group
---

(suricata)=

# Suricata

[Suricata](https://suricata.io/) is an open-source network threat
detection engine that performs intrusion detection
({abbr}`IDS (Intrusion Detection System)`), inline intrusion
prevention ({abbr}`IPS (Intrusion Prevention System)`), and network
security monitoring ({abbr}`NSM (Network Security Monitoring)`) by
matching live traffic against a set of rules, also called signatures.
Each event is recorded in the {abbr}`EVE (Extensible Event Format)`
event log in {abbr}`JSON (JavaScript Object Notation)` format.

VyOS integrates Suricata as a managed service, configurable under
`service suricata`. When the configuration is committed, VyOS generates
Suricata configuration from these settings and starts the service.

Under `service suricata`, you can configure the following:

- **Monitored interfaces**: One or more interfaces on which Suricata
  captures traffic.
- **Address groups**: Named lists of IPv4/IPv6 addresses or prefixes,
  used in place of literal IP addresses in Suricata rules. 
- **Port groups**: Named lists of ports or port ranges, used in place
  of literal ports in Suricata rules. 
- **EVE log**: Destination (regular file or syslog), file name or
  path, and the event types to log.

Rules are fetched separately by running `update suricata` from
operational mode. Until this command is run, the service has no rules
to match against.

```{note}
A Suricata configuration is committable only when at least one
interface, one address group, and one port group are defined.
Otherwise, the commit fails.
```

## Configuration

### Monitored interfaces

Use the following command to configure the interfaces Suricata
monitors.

```{cfgcmd} set service suricata interface \<interface\>

**Configure an interface on which Suricata captures and inspects
traffic.**

Repeat the command to monitor several interfaces. At least one
interface must be configured for a successful commit.
```

Example:

```none
set service suricata interface eth1
```

### Address groups

Use the following commands to configure address groups.

```{note}
Group names must be lowercase letters, digits, or hyphens. 
```

```{note}
Suricata rules reference a conventional set of group names, such as
`home-net`, `external-net`, `http-servers`, and others. Defining a
group with a non-standard name is allowed, but no shipped rules will
reference it. Typical address groups include:

- `home-net`: the networks Suricata should treat as internal (for
  example, `192.0.2.0/24` and `2001:db8::/32`).
- `external-net`: everything not in `home-net`.
- `http-servers`, `sql-servers`, `dns-servers`: hosts running the
  corresponding services.
```

```{cfgcmd} set service suricata address-group \<name\> address \<address\>

**Configure an IPv4 or IPv6 address or prefix as a member of the
specified address group.**

`<address>` accepts an IPv4 or IPv6 address, an IPv4 or IPv6 prefix,
or any of these prefixed with `!` to exclude it from matches.

Repeat the command to add more addresses or prefixes to the same
group.
```

Example:

```none
set service suricata address-group home-net address 192.0.2.0/24
set service suricata address-group home-net address 2001:db8::/32
set service suricata address-group home-net address !192.0.2.5
```

```{cfgcmd} set service suricata address-group \<name\> group \<name\>

**Configure another address group as a member of the specified
address group.**

Prefix the referenced name with `!` to exclude that group's members.
The referenced group must be defined at commit time, and cyclic
references between groups are rejected.

Repeat the command to add more groups to the same parent group.
```

Example:

```none
set service suricata address-group home-net address 192.0.2.0/24
set service suricata address-group external-net group !home-net
```

### Port groups

Use the following commands to configure port groups.

```{note}
Group names must be lowercase letters, digits, or hyphens. 
```

```{note}
Suricata rules reference a conventional set of port-group names, such
as `http-ports`, `ssh-ports`, `oracle-ports`, `shellcode-ports`, and
others. Defining a port group with a non-standard name is allowed,
but no shipped rules will reference it. Typical port groups include:

- `http-ports`: ports where HTTP services run.
- `ssh-ports`: ports where SSH services listen.
- `oracle-ports`: ports used by Oracle database services.
- `shellcode-ports`: ports inspected by shellcode-detection rules.
```

```{cfgcmd} set service suricata port-group \<name\> port \<port\>

**Configure a port or port range as a member of the specified port
group.**

`<port>` accepts a single port (1–65535), a numeric range in
`start-end` form (e.g., `1001-1005`), or either form prefixed with
`!` to exclude it from matches.

Repeat the command to add more ports or port ranges to the same
group.
```

Example:

```none
set service suricata port-group http-ports port 80
set service suricata port-group http-ports port 443
set service suricata port-group http-ports port 8000-8999
set service suricata port-group http-ports port !8080
```

```{cfgcmd} set service suricata port-group \<name\> group \<name\>

**Configure another port group as a member of the specified port
group.**

Prefix the referenced name with `!` to exclude that group's members
from matches. The referenced group must be defined at commit time,
and cyclic references between groups are rejected.

Repeat the command to add multiple groups to the same parent group.
```

Example:

```none
set service suricata port-group http-ports port 80
set service suricata port-group shellcode-ports group !http-ports
```

### EVE log

Use the following commands to configure the EVE log.

```{cfgcmd} set service suricata log eve filename \<filename\>

**Configure the filename or path for the Suricata EVE log.**

A bare filename (e.g., `eve.json`) places the log in Suricata's
default log directory, `/var/log/suricata/`. An absolute path is used
as-is.

The default is `eve.json`.
```

Example:

```none
set service suricata log eve filename eve.json
set service suricata log eve filename /var/log/custom/suricata-eve.json
```

```{cfgcmd} set service suricata log eve filetype \<regular | syslog\>

**Configure the destination for the Suricata EVE log:**

- `regular`: Writes the EVE log to the file specified by
  `set service suricata log eve filename`.
- `syslog`: Sends the EVE log to syslog.

The default is `regular`.
```

Example:

```none
set service suricata log eve filetype syslog
```

```{cfgcmd} set service suricata log eve type \<type\>

**Configure which EVE event types are logged.**

Accepted values:

- General event types: `alert`, `anomaly`, `drop`, `files`, `flow`,
  `netflow`.
- Per-protocol event types: `http`, `http2`, `dns`, `tls`, `smtp`,
  `ftp`, `smb`, `ssh`, `dhcp`, `tftp`, `nfs`, `rdp`, `sip`, `snmp`,
  `ikev2`, `krb5`, `dcerpc`, `dnp3`, `rfb`, `mqtt`.

Repeat the command to log multiple event types.
```

Example:

```none
set service suricata log eve type alert
set service suricata log eve type flow
set service suricata log eve type http
```

## Operation

```{opcmd} update suricata

**Fetch the current rule set with `suricata-update` and restart the
Suricata service to load it.**

If `service suricata` is not configured, the command outputs an error
message and exits.
```

Example:

```none
update suricata
```

```{opcmd} restart suricata

**Restart the Suricata service.**

If the service is not configured (no `service suricata` configuration
exists), or a configuration commit is in progress, the command prints
an error message and exits.
```

Example:

```none
restart suricata
```
