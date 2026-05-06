:lastproofread: 2026-02-27

.. _vpp_config_dataplane_memory:

.. include:: /_include/need_improvement.txt

########################
VPP Memory Configuration
########################

VPP heavily relies on hugepages for its memory management. Hugepages
are larger memory pages that reduce the overhead of page management and
improve performance for applications that require large amounts of
memory, such as VPP.

VPP supports both 2MB and 1GB hugepages, but the default and most
commonly used size is 2MB. The choice of hugepage size can impact
performance, with larger pages generally providing better performance
for memory-intensive applications.

Before configuring memory in VPP dataplane settings, you need to
ensure that hugepages are enabled and properly configured on your
system.

.. seealso:: :ref:`Hugepages in VyOS Configuration for VPP
   <vpp_config_hugepages>`

To configure memory settings for VPP, you can use the following
commands in the VPP CLI:

VPP uses a main heap as a central memory pool for FIB data structures
entry allocations.

Efficient memory management is crucial for VPP's performance, and the
main heap plays a significant role in this.

It can be configured using the following command:

.. cfgcmd:: set vpp settings resource-allocation memory main-heap-page-size
   <size>

Sets the main heap page size for VPP. 

.. cfgcmd:: set vpp settings resource-allocation memory main-heap-size <size>

Sets the main heap size for VPP.

.. _vpp_config_dataplane_physmem:

Physical Memory Configuration
=============================

VPP uses physical memory for packet buffers and interface operations.
The ``physmem`` setting controls how much memory VPP can allocate for
these operations.

.. cfgcmd:: set vpp settings resource-allocation memory physmem-max-size <size>

Sets the maximum amount of physical memory VPP can use for packet
processing and interface buffers.

**Default**: 16GB (usually sufficient for most deployments)

You may need to modify the value for high-throughput environments with
many interfaces, large packet buffers, very high packet rates, or
memory-constrained systems where you need to limit VPP's memory usage.

**Physmem independent of main heap size** — physmem is for packet
buffers, main heap is for routing tables.

.. seealso::

   - :ref:`Hugepages in VyOS Configuration for VPP <vpp_config_hugepages>`
   - :ref:`VPP Buffer Configuration <vpp_config_dataplane_buffers>` - for
     controlling buffer allocation within physmem

Common configurations
---------------------

.. code-block:: none

   # Reduce for memory-constrained systems
   set vpp settings physmem max-size 4G

   # Increase for high-throughput environments
   set vpp settings physmem max-size 32G

Stats Memory Configuration
==========================

VPP uses a dedicated statistics memory segment to store runtime
counters and telemetry data. This segment is used by the VPP CLI and
monitoring tools to access performance and status information.

The statistics segment is allocated from hugepage memory and can be
configured independently from the main heap and physmem settings.

You can configure statistics memory using the following commands:

.. cfgcmd:: set vpp settings resource-allocation memory stats page-size <size>

Sets the hugepage page size used for the statistics memory segment.

.. cfgcmd:: set vpp settings resource-allocation memory stats size <size>

Sets the total size of the statistics memory segment.

Increasing this value may be required in large deployments with many
interfaces or enabled features that generate a high number of counters.

Statistics memory is used only for telemetry and monitoring. It does
not affect packet buffer allocation or routing table memory.

Troubleshooting
===============

Improper configuration of main heap size can lead to performance
degradation or even system instability. If VPP runs out of memory in the
main heap, it may crash or exhibit erratic behavior. Symptoms you may
observe include:

- Increased latency or packet loss
- Crashes or restarts of VPP processes, especially during routing table
  population (for example, BGP session establishment)
- Error messages related to memory allocation failures

You need to tune the main heap size based on expected FIB entries. Pay
attention: the same amount of routes with a single next-hop and with
multiple next-hops will consume different amounts of memory.

For physmem, insufficient allocation can lead to packet drops, interface
initialization failures, and overall degraded performance. Symptoms
include:

- Packet drops or failures to allocate buffers
- Increased latency or jitter in packet processing
- Crashes or restarts of VPP processes under heavy load

You need to tune the physmem settings based on expected traffic patterns
and interface usage. Monitor memory usage closely and adjust the
configuration as needed to ensure optimal performance.
