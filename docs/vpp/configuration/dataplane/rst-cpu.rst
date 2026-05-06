:lastproofread: 2026-02-23

.. _vpp_config_dataplane_cpu:

.. include:: /_include/need_improvement.txt

###############################
VPP Dataplane CPU Configuration
###############################

VPP can utilize multiple CPU cores for better packet processing
performance. Proper CPU configuration is essential for optimal
throughput and low latency.

VPP CPU assignment is handled automatically. You specify how many CPU
cores VPP may use, and the system distributes them between the main
thread and worker threads.

.. important::

   Review the system configuration settings page before changing CPU
   settings: :doc:`system`.

If you don't configure CPU settings, VPP uses a single core for the
main thread and doesn't create worker threads.

CPU Configuration Parameters
============================

``cpu-cores``
^^^^^^^^^^^^^

This parameter defines the total number of CPU cores allocated to VPP.

.. cfgcmd:: set vpp settings resource-allocation cpu-cores <core-number>

The system automatically assigns cores using the following rules:

   * The first two CPU cores are always reserved for the operating system and
     other services.

   * The main VPP thread is assigned to the first available core after the
     reserved ones.

   * The remaining allocated cores are used for worker threads.

For example:

   * If cpu-cores is set to 1, VPP runs only a main thread.

   * If cpu-cores is set to 4, VPP uses:

       * 1 core for the main thread

       * 3 cores for worker threads

Choose a value based on available hardware resources and expected
traffic load. Too few cores may limit performance, while too many can
negatively impact other system services.

Potential Issues and Troubleshooting
====================================

Improper CPU configuration can lead to issues such as:

- VPP underperformance when not enough cores are assigned, or kernel
  underperformance when too many cores are assigned to VPP.
- Resource conflicts with other processes and services.

Indicators of such issues are:

- VPP or kernel forwarding performance is lower than expected
- Degraded performance of system components or services, such as DNS,
  DHCP, and dynamic routing
