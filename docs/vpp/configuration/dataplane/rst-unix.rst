:lastproofread: 2026-02-27

.. _vpp_config_dataplane_unix:

.. include:: /_include/need_improvement.txt

################################
VPP Unix Dataplane Configuration
################################

The UNIX configuration section is used to control VPP's interaction
with the underlying operating system, including operations scheduling.

VPP relies on the polling mechanism to efficiently manage I/O operations
and system events. By default VPP continuously polls for events, which
leads to permanent 100% CPU usage by all cores assigned to VPP dataplane.
This is optimal for performance, but may not be desirable in all
environments, especially where power consumption is a concern or where VPP
is running inside a hypervisor, especially if the VM has burstable
thresholds and CPU usage limits.

To mitigate this, VPP provides a configurable polling delay that allows
reducing CPU usage by introducing a delay between polling cycles. This
introduces a trade-off between CPU usage and latency, as longer delays
can lead to increased latency in processing events.

You can configure the polling delay using the following command in the
VyOS CLI:

.. cfgcmd:: set vpp settings poll-sleep-usec <delay>

Sets the polling delay in microseconds. A value of 0 means no delay
(default), while higher values introduce a delay between polling cycles.

Troubleshooting
===============

Setting the polling delay too high can lead to increased latency and
reduced performance, as VPP may not respond to events as quickly.
Conversely, setting it too low may result in high CPU usage, which can be
problematic in resource-constrained environments.

Symptoms of improper configuration may include:

- Increased latency in packet processing
- Higher CPU usage than expected
- Packets lost due to buffer overruns

If you do not need to reduce CPU usage, it is recommended to leave the
polling delay at its default value of 0 for optimal performance.

If you need to reduce CPU usage, you may also consider using ``interrupt`` or
``adaptive`` :ref:`DPDK driver modes <vpp_config_dataplane_interface_rx_mode>`,
which can provide a balance between performance and resource utilization
without affecting polling behavior.
