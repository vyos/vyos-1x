:lastproofread: 2026-02-23

.. _vpp_config_dataplane_buffers:

.. include:: /_include/need_improvement.txt

###################################
VPP Dataplane Buffers Configuration
###################################

Buffers are essential for handling network packets efficiently. Proper
configuration enhances performance and reliability, and is mandatory for
VPP to work. Buffers temporarily store packets during processing. Therefore,
their configuration must be in sync with NIC configuration, CPU threads, and
overall system resources.

.. important::

   VPP buffers are allocated from the physical memory pool (``physmem``). The 
   total amount of memory available for buffer allocation is controlled by the
   ``physmem-max-size`` setting, while the buffer configuration parameters
   below control how that memory is used for buffer allocation.

   See :ref:`VPP Physical Memory Configuration <vpp_config_dataplane_physmem>`
   for details on configuring ``physmem``.

Buffer Configuration Parameters
===============================

The following parameters can be configured for VPP buffers:

buffers-per-numa
----------------

Number of buffers allocated per NUMA node. This setting optimizes
memory access patterns for multi-CPU systems.

Typically, you need to tune this value if:

- The system has many interfaces
- NICs have many queues
- NICs have large descriptor sizes

Set this value carefully to balance memory usage and performance.

.. cfgcmd:: set vpp settings resource-allocation buffers buffers-per-numa
  <value>

The common approach for the calculation is to use the formula:

.. code-block:: none

    buffers-per-numa = (num-rx-queues * num-rx-desc) + (num-tx-queues * num-tx-desc)

Calculate this formula for each NIC and sum the results. Multiply the
total by 2.5 to get the minimum recommended value for
``buffers-per-numa``.

Avoid setting this value too low to prevent packet drops.

data-size
---------

This value sets how much payload data can be stored in a single buffer
allocated by VPP. Larger values reduce buffer chains for large packets,
while smaller values conserve memory for environments handling mostly
small packets.

.. cfgcmd:: set vpp settings resource-allocation buffers data-size <value>

Optimal size depends on the typical packet size in your network. If
unsure, use the largest MTU in your network plus overhead (for example,
128 bytes).

page-size
---------

A memory pages type used for buffer allocation. Common values are 4K, 2M, or 1G.

Use page sizes configured in your system settings.

.. cfgcmd:: set vpp settings resource-allocation buffers page-size <value>

Potential Issues and Troubleshooting
====================================

Improper buffer configuration can lead to issues such as:

- Increased latency and packet loss
- Inefficient CPU utilization
- Interface initialization failures

Indicators of such issues are:

- Errors during interfaces initialization in VPP logs
- Packet drops observed in VPP statistics

To troubleshoot buffer-related issues, consider the following steps:

- Review VPP logs for errors related to buffer allocation. Look for
  error ``-5`` messages.
- Tune available buffers by adjusting the ``buffers-per-numa`` and
  ``data-size`` parameters.
