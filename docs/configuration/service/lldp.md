---
myst:
  html_meta:
    description: |
      LLDP is a vendor-neutral Layer 2 protocol that lets devices
      advertise their identity, capabilities, and management addresses
      to directly connected neighbors and learn the same from them.
    keywords: lldp, lldp-med, cdp, edp, fdp, sonmp, neighbor-discovery
---

(lldp)=

# LLDP

{abbr}`LLDP (Link Layer Discovery Protocol)` is a vendor-neutral Layer
2 protocol that enables devices to advertise their identity,
capabilities, and management addresses to directly connected neighbors
and to learn the same information from them. LLDP is specified in IEEE
802.1AB, Station and Media Access Control Connectivity Discovery.

Each device sends LLDP frames periodically on every interface where
LLDP transmission is enabled and records the received information in a
local neighbor database. This database can also be queried with
{abbr}`SNMP (Simple Network Management Protocol)` (see `set service
lldp snmp`), so the topology of an entire LLDP-enabled network can be
mapped by querying each device in turn. Advertised information may
include:

- System name and description
- Port name and description
- VLAN name
- Management IP address
- System capabilities (the device's role: router, bridge, telephone,
  and so on)
- Physical link settings, such as speed, duplex, and auto-negotiation
  (MAC/PHY)
- Power over Ethernet (MDI power)
- Link aggregation (bonding)

LLDP provides functionality similar to proprietary protocols such as
{abbr}`CDP (Cisco Discovery Protocol)`,
{abbr}`EDP (Extreme Discovery Protocol)`,
{abbr}`FDP (Foundry Discovery Protocol)`, and
{abbr}`SONMP (SynOptics Network Management Protocol)`. You can
configure VyOS to interoperate with devices running these protocols
via `set service lldp legacy-protocols`.

## Configuration

```{cfgcmd} set service lldp

**Enable the LLDP service.**

With no further configuration, the service sends and processes LLDP
frames on every available local interface.

Configure `service lldp interface` to restrict it to selected
interfaces.
```

Example:

```none
set service lldp
```

```{cfgcmd} set service lldp interface \<interface\>

**Enable LLDP on the specified interface.**

Repeat the command to enable LLDP on multiple interfaces. The special
value `all` enables LLDP on every available local interface.

Once LLDP is enabled with `set service lldp`, it runs on all available
local interfaces by default. Configuring one or more interfaces here
limits LLDP strictly to those configured, disabling LLDP on all
remaining interfaces.
```

Example:

```none
set service lldp interface eth1
set service lldp interface eth2
```

```{cfgcmd} set service lldp interface \<interface\> mode \<disable | rx-tx | tx | rx\>

**Configure the LLDP administrative status on the specified
interface:**

- `rx-tx`: Sends LLDP frames and processes received ones.
- `rx`: Processes only received frames, so the router learns about its
  neighbors without announcing itself.
- `tx`: Sends frames only.
- `disable`: Neither sends nor processes frames on the interface.

The default is `rx-tx`.
```

Example:

```none
set service lldp interface eth1 mode rx
```

```{cfgcmd} set service lldp interface \<interface\> location coordinate-based latitude \<latitude\>

**Configure the latitude of the coordinate-based LLDP-MED location
advertised on the specified interface.**

The value is a decimal number followed by N or S. Both latitude and
longitude must be configured.
```

Example:

```none
set service lldp interface eth1 location coordinate-based latitude 37.524449N
```

```{cfgcmd} set service lldp interface \<interface\> location coordinate-based longitude \<longitude\>

**Configure the longitude of the coordinate-based LLDP-MED location
advertised on the specified interface.**

The value is a decimal number followed by E or W. Both latitude and
longitude must be configured.
```

Example:

```none
set service lldp interface eth1 location coordinate-based longitude 122.267255W
```

```{cfgcmd} set service lldp interface \<interface\> location coordinate-based altitude \<altitude\>

**Configure the altitude, in meters, of the coordinate-based LLDP-MED
location advertised on the specified interface.**

The value is a positive or negative number of meters, where 0 means no
altitude. Altitude is part of the coordinate-based location, so
latitude and longitude must also be configured for it to be
advertised.

The default is 0.
```

Example:

```none
set service lldp interface eth1 location coordinate-based altitude 12
```

```{cfgcmd} set service lldp interface \<interface\> location coordinate-based datum \<WGS84 | NAD83 | MLLW\>

**Configure the geodetic datum of the coordinate-based LLDP-MED
location advertised on the specified interface:**

- `WGS84` and `NAD83` select the corresponding geodetic datum.
- `MLLW` selects NAD83 combined with the
  {abbr}`MLLW (Mean Lower Low Water)` tidal datum, used where altitude
  is referenced to tidal water level.

The default is `WGS84`.
```

Example:

```none
set service lldp interface eth1 location coordinate-based datum NAD83
```

```{cfgcmd} set service lldp interface \<interface\> location elin \<number\>

**Advertise an Emergency Call Service
{abbr}`ELIN (Emergency Location Identification Number)` on the
specified interface.**

The value is 10 to 25 digits.
```

Example:

```none
set service lldp interface eth1 location elin 1234567890
```

```{cfgcmd} set service lldp management-address \<address\>

**Advertise the specified IPv4 or IPv6 address to LLDP neighbors as a
management address.**

Repeat the command to advertise multiple addresses. VyOS generates a
warning upon commit if the address is a loopback address or is not
assigned to any interface.
```

Example:

```none
set service lldp management-address 192.0.2.1
set service lldp management-address 2001:db8::1
```

```{cfgcmd} set service lldp snmp

**Allow the LLDP database to be queried over SNMP.**

Requires a configured SNMP service (see {ref}`snmp`). Otherwise, the
commit fails.
```

Example:

```none
set service lldp snmp
```

```{cfgcmd} set service lldp legacy-protocols \<cdp | edp | fdp | sonmp\>

**Enable the LLDP service to process the specified vendor-proprietary
discovery protocol:**

- `cdp`: Cisco routers and switches.
- `edp`: Extreme routers and switches.
- `fdp`: Foundry routers and switches.
- `sonmp`: Nortel routers and switches.

After receiving a frame of an enabled protocol on an interface, VyOS
also transmits that protocol on the interface.

Repeat the command to enable processing of multiple protocols.
```

Example:

```none
set service lldp legacy-protocols cdp
```

## Operation

```{opcmd} show lldp neighbors

**Show all neighbors discovered via LLDP or enabled legacy
protocols.**
```

```{opcmd} show lldp neighbors detail

**Show detailed information about discovered neighbors.**
```

```{opcmd} show lldp neighbors interface \<interface\>

**Show neighbors discovered on the specified interface.**
```

```{opcmd} show lldp neighbors interface \<interface\> detail

**Show detailed information about neighbors discovered on the
specified interface.**
```

```{opcmd} show log lldp

**Show the log of the LLDP service since the last boot.**
```
