#######################
VPP IPFIX Configuration
#######################

VPP IPFIX in VyOS allows monitoring and exporting network traffic flows
for analytics, security, and accounting. IPFIX works with the VPP
(Vector Packet Processing) backend to provide high-performance flow tracking.

Overview
--------

VyOS integrates VPP for high-performance packet processing. IPFIX
configuration controls how flows are monitored, exported, and which
interfaces are included.  

Key IPFIX Concepts
------------------

- **Active timeout**: Maximum time a flow is kept active before export.
- **Inactive timeout**: Maximum time an idle flow is kept before export.
- **Collector**: The remote host and port to which flow records are sent.
- **Flow layers**: Determines which layer information is included
  (``l2``, ``l3``, ``l4``).
- **Interfaces**: Physical or virtual interfaces to monitor.
- **Direction**: Which traffic to monitor (`rx`, `tx`, `both`).
- **Flow variant**: Optional filter for IPv4 or IPv6 flows.

Configuration Options
---------------------

- **active-timeout**: Duration (in seconds) after which active flows
  are exported.
- **inactive-timeout**: Duration (in seconds) after which idle flows
  are exported.
- **collector `<ip>` port `<port>`**: IP and UDP port of the IPFIX collector.
- **collector `<ip>` source-address `<ip>`**: Source address for flow export.
- **flowprobe-record `<l2|l3|l4>`**: Layers to include in flow records.
- **interface** ``<interface>`` **[direction** ``<rx|tx|both>``\ **]**
  **[flow-variant** ``<ipv4|ipv6>``\ **]**: Interfaces to monitor,
  direction of traffic, and optional flow variant filter.

Example Configuration
---------------------

.. code-block:: none

    set vpp ipfix active-timeout '15'
    set vpp ipfix inactive-timeout '120'
    set vpp ipfix collector 192.0.2.2 port '4739'
    set vpp ipfix collector 192.0.2.2 source-address '192.0.2.1'
    set vpp ipfix flowprobe-record 'l2'
    set vpp ipfix flowprobe-record 'l3'
    set vpp ipfix flowprobe-record 'l4'
    set vpp ipfix interface eth0
    set vpp ipfix interface eth1 direction 'both'
    set vpp ipfix interface eth1 flow-variant 'ipv4'

