:lastproofread: 2026-02-26

.. _vpp_config_dataplane_lcp:

.. include:: /_include/need_improvement.txt

#####################
VPP LCP Configuration
#####################

Linux Control Plane (LCP) is a core component of VPP that lets you
offload various control plane functions to the Linux kernel. LCP provides
seamless integration with other VyOS components, letting you use system
components like DHCP clients and routing daemons together with the VPP
dataplane.

VPP integration in VyOS relies heavily on LCP. Almost all control plane
functions are handled by other daemons and services, while VPP handles
high-performance packet forwarding exclusively. This approach also reduces
VPP management processing load, improving overall dataplane performance and
stability.

VyOS integrates the kernel and VPP routing tables uniquely. By default,
all routes, even those not directly connected to VPP interfaces, are
imported from the kernel routing table to the VPP routing table, pointing
to the kernel. This lets you forward traffic to any destination known to
the kernel, even if VPP doesn't have a route to that destination.

However, in some scenarios this behavior may not be desired. For example,
if you have many routes in the kernel routing table not directly connected
to VPP interfaces, and you don't need forwarding between those
destinations and destinations reachable via VPP, you can disable this
behavior using the following command:

.. _vpp_config_dataplane_lcp_ignore-kernel-routes:

.. cfgcmd:: set vpp settings ignore-kernel-routes

Pay attention that disabling this option leads to loss of connectivity to
destinations if there are no direct routes in VPP routing table.

Potential Issues and Troubleshooting
====================================

Disabling kernel route import can result in:

- Loss of connectivity to certain destinations if kernel routes are ignored
- Incomplete route synchronization between the kernel and VPP
