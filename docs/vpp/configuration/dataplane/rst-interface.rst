:lastproofread: 2026-02-23

.. _vpp_config_dataplane_interface:

.. include:: /_include/need_improvement.txt

######################################
VPP Dataplane Interfaces Configuration
######################################

Only Ethernet interfaces (physical or virtual) can be connected to the
VPP dataplane. Interfaces configured here act as a bridge between VPP
and the outside world, allowing VPP to send and receive network
packets.


Interface Configuration Parameters
==================================

Interfaces connected to the VPP dataplane use the DPDK driver by default,
providing high performance and low latency.

.. cfgcmd:: set vpp settings interface <interface-name>

Some network interface cards (NICs) may not be compatible with the DPDK driver.

DPDK interface options
----------------------

This section shows how to configures DPDK-specific settings for an interface.

.. cfgcmd:: set vpp settings interface <interface-name> num-rx-queues <value>

Specifies the number of receive queues for the interface. More queues
improve performance on multi-core systems by allowing parallel
processing of incoming packets. Each queue is assigned to a separate
CPU core.

.. cfgcmd:: set vpp settings interface <interface-name> num-tx-queues <value>

Specifies the number of transmit queues for the interface. Similar to
receive queues, more transmit queues improve performance by enabling
parallel processing of outgoing packets. By default, the VPP Dataplane
has one TX queue per enabled CPU worker, or a single queue if no
workers are configured.

.. seealso:: :doc:`cpu`

.. cfgcmd:: set vpp settings interface <interface-name> num-rx-desc <value>

Defines the size of each receive queue. Larger queue sizes accommodate
bursts of incoming traffic and reduce the likelihood of packet drops
during high traffic periods.

.. cfgcmd:: set vpp settings interface <interface-name> num-tx-desc <value>

Defines the size of each transmit queue. Larger sizes help manage
bursts of outgoing traffic more effectively.

Global Interface Parameters
===========================

.. _vpp_config_dataplane_interface_rx_mode:

interface-rx-mode
-----------------

The ``interface-rx-mode`` parameter defines how VPP handles incoming
packets on interfaces. There are several modes available, each with its
own advantages and use cases:

- ``interrupt``: In this mode, VPP relies on hardware interrupts to
  notify it of incoming packets. This mode suits low to moderate
  traffic loads and reduces CPU usage during idle periods. It is not
  recommended for low-latency processing. Some NICs may not support
  this mode.
- ``polling``: In polling mode, VPP continuously checks the interface
  for incoming packets. This mode is ideal for high-throughput
  scenarios where low latency is critical, as it minimizes packet
  waiting time. However, it can increase CPU usage, especially during
  low traffic periods, as the polling process is always active.
- ``adaptive``: Adaptive mode combines the benefits of interrupt and
  polling modes. VPP starts in interrupt mode and switches to polling
  mode when traffic load increases.

.. cfgcmd:: set vpp settings interface-rx-mode <mode>

Choose an rx-mode based on expected traffic patterns and performance
requirements of your network.

Potential Issues and Troubleshooting
====================================

Improper interface configuration can lead to issues such as:

- Failure to initialize the interface
- Poor performance due to suboptimal driver selection or settings

Indicators of such issues are:

- Failed commits after adding or modifying an interface settings
- Low throughput or high latency on the interface
