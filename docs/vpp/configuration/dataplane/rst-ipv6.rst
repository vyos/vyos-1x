:lastproofread: 2026-02-26

.. _vpp_config_dataplane_ipv6:

.. include:: /_include/need_improvement.txt

######################
VPP IPv6 Configuration
######################

VPP lets you configure resources allocated for IPv6 traffic processing
independently from IPv4. This helps ensure that in networks without IPv6
traffic, resources are not wasted. If IPv6 traffic is present, especially
with large routing tables, you must allocate additional resources for IPv6
processing to keep the dataplane stable.

You can configure two main resources for IPv6 traffic processing:

.. cfgcmd:: set vpp settings resource-allocation ipv6 hash-buckets <value>

This parameter configures the number of hash buckets used for IPv6
routing. If you have a large IPv6 routing table, you may need to increase
this value to ensure efficient routing table performance and fast lookups.

.. cfgcmd:: set vpp settings resource-allocation ipv6 heap-size <value>

This parameter configures the heap size used for IPv6 forwarding. If you
have a large IPv6 routing table, you may need to increase this value to
ensure the routing table can accommodate all routes.

Potential Issues and Troubleshooting
====================================

Improper IPv6 configuration can lead to various issues, including:

- Inefficient, slow routing table lookups and traffic processing due to
  insufficient hash buckets
- Dataplane crashes or instability due to insufficient heap size when
  handling a large number of IPv6 routes
- Overall dataplane instability when handling IPv6 traffic

Consider increasing configuration values if you experience issues with
IPv6 traffic processing or if you have a large IPv6 routing table.
