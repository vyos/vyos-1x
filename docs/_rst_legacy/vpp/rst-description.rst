:lastproofread: 2026-02-16

.. _vpp_description:

.. include:: /_include/need_improvement.txt

#########################
VPP Dataplane Description
#########################

What is VPP in VyOS?
====================

VyOS supports two packet forwarding dataplanes:

- **Linux kernel dataplane** (traditional)
- **Vector Packet Processor (VPP) dataplane** (optional)

VPP is a high-performance user space packet processor that improves
throughput for demanding network workloads.

Key Benefits
============

**Performance Improvement**

VPP uses vector-based packet processing instead of one-by-one handling,
delivering:

- **Higher throughput** compared to kernel forwarding.
- **Lower and more consistent latency** for time-sensitive applications.
- **Linear scaling** with additional CPU cores.

**VyOS Hybrid Integration**

VyOS supports both dataplanes simultaneously, providing:

- **Cross-dataplane forwarding**: Traffic can flow between the VPP dataplane
  and kernel interfaces seamlessly.
- **Transparent configuration**: Same CLI commands and most services work
  regardless of dataplane.
- **Gradual migration**: Enable VPP on high-traffic interfaces while keeping
  others on kernel.

When to Use VPP
===============

**Consider VPP if you have:**

- High-throughput requirements
- Latency-sensitive applications requiring consistent performance

**Stay with kernel dataplane if you have:**

- Low to moderate traffic volumes
- No latency-sensitive workloads
- Applications requiring specific features not supported by VPP Dataplane

Packet Processing Integration
=============================

VPP Dataplane integration minimizes configuration changes. Features in the
kernel dataplane continue to operate there. VPP Dataplane only handles packet
forwarding for interfaces explicitly assigned to it.

Traffic flow examples between VPP and kernel dataplane interfaces:

.. image:: /_static/images/vpp/vyos_vpp_integration.svg
   :align: center

Green path
""""""""""

Traffic between two VPP interfaces stays within VPP for maximum performance
and can use only VPP dataplane features.

Blue path
"""""""""

Traffic between a VPP interface and a kernel interface is processed by both
dataplanes and can use features from both.

**Note:** This path has slower performance than pure VPP or pure kernel
forwarding because packets traverse both dataplanes.

Red path
""""""""

Traffic between two kernel interfaces stays within the kernel dataplane without
VPP acceleration. This is the traditional VyOS dataplane operation.


CLI Integration
===============

VyOS CLI commands work with both dataplanes. Use the same commands to
configure interfaces, routing, and other features regardless of the dataplane.
