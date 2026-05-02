---
lastproofread: '2023-03-26'
---

(examples-nmp)=

# NMP example

Consider how to quickly set up NMP and VyOS for monitoring.
NMP is multi-vendor network monitoring from 'SolarWinds' built to
scale and expand with the needs of your network.

## Configuration 'VyOS'

First prepare our VyOS router for connection to NMP. We have to set
up the SNMP protocol and connectivity between the router and NMP.

% stop_vyoslinter

```none
set interfaces ethernet eth0 address 'dhcp'
set system name-server '8.8.8.8'
set service snmp community router authorization 'test'
set service snmp community router network '0.0.0.0/0'
```

% start_vyoslinter


## Configuration 'NMP'

Next, you just should follow the pictures:

```{image} /_static/images/nmp1.webp
:align: center
:alt: Network Topology Diagram
:width: 80%
```

```{image} /_static/images/nmp2.webp
:align: center
:alt: Network Topology Diagram
:width: 80%
```

```{image} /_static/images/nmp3.webp
:align: center
:alt: Network Topology Diagram
:width: 80%
```

```{image} /_static/images/nmp4.webp
:align: center
:alt: Network Topology Diagram
:width: 80%
```

```{image} /_static/images/nmp5.webp
:align: center
:alt: Network Topology Diagram
:width: 80%
```

```{image} /_static/images/nmp6.webp
:align: center
:alt: Network Topology Diagram
:width: 80%
```

```{image} /_static/images/nmp7.webp
:align: center
:alt: Network Topology Diagram
:width: 80%
```

In the end, you'll get a powerful instrument for monitoring the VyOS systems.
