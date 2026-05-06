:lastproofread: 2026-02-26

.. _vpp_config_dataplane_l2learn:

.. include:: /_include/need_improvement.txt

#########################
VPP L2LEARN Configuration
#########################

When VPP dataplane connects to an L2 domain, it learns MAC addresses of
devices in the domain. By default, the number of MAC addresses it can
learn is limited.

You can configure the limit using the following command:

.. cfgcmd:: set vpp settings resource-allocation mac-limit <value>

This parameter sets the maximum number of MAC addresses that can be
learned in the L2 domain. If you have many devices, you may need to
increase this limit to ensure VPP learns all MAC addresses.

Potential Issues and Troubleshooting
====================================

Improper L2LEARN configuration can lead to various issues, including:

- MAC address learning failure in the L2 domain if the limit is set too
  low
- Increased packet loss or latency for devices that aren't learned
- Overall dataplane instability when handling L2 traffic

Consider increasing the L2LEARN limit if you experience issues with MAC
address learning or if you have many devices in the L2 domain.
