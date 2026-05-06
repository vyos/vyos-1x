:lastproofread: 2026-02-27

.. _vpp_config_system:

.. include:: /_include/need_improvement.txt

##########################
VyOS Configuration for VPP
##########################

.. _vpp_config_hugepages:

Hugepages
=========

VPP uses hugepages for efficient memory management. Hugepages are larger
memory pages that reduce the overhead of page management and improve
performance for applications that require large amounts of memory.

Hugepages can be configured in VyOS using the following commands:

.. warning::

   Changes to hugepage settings require a system reboot to take effect.

   Hugepages must be enabled before VPP configuration is applied.

To enable hugepages:

.. cfgcmd:: set system option kernel memory hugepage-size <size> hugepage-count
   '<count>'

Enables hugepages with the specified size and count. The size can be either
2MB or 1GB, and the count specifies the number of hugepages to allocate.

If your system has multiple NUMA nodes, the total amount of hugepages will be
divided equally among them.

Resources Limits
================

.. note::

   By default, system will calculate and set the recommended values for
   resource limits. Avoid tuning these values if you are not sure what you
   are doing.

During operations VPP utilizes a significant amount of system resources,
especially memory. There are two main settings that may need to be
adjusted to ensure VPP runs smoothly:

Maximum number of memory map areas a process may have:

.. cfgcmd:: set system option resource-limits max-map-count <value>

Maximum shared memory segment size:

.. cfgcmd:: set system option resource-limits shmmax <value>

Both settings are automatically calculated based on configured hugepages.

Kernel Tuning
=============

VPP performance greatly benefits from proper kernel tuning, especially
CPU isolation and disabling unnecessary kernel features. These
optimizations ensure dedicated CPU cores are available exclusively for
VPP dataplane processing without interference from the kernel scheduler
or other system processes.

.. warning::

   Kernel tuning changes require a system reboot to take effect.

   Improper CPU isolation can lead to system instability if essential system
   processes are starved of CPU resources.

CPU Isolation and Optimization
-------------------------------

CPU isolation is crucial for VPP performance as it dedicates specific
CPU cores exclusively to VPP dataplane processing. The isolated cores are
removed from the kernel scheduler and will not run regular system
processes.

**Disable NMI Watchdog**

The NMI (Non-Maskable Interrupt) watchdog can interfere with VPP
performance by generating interrupts on isolated cores and is not
compatible with nohz-full mode:

.. cfgcmd:: set system option kernel cpu disable-nmi-watchdog

   Disables the NMI watchdog for detecting hard CPU lockups. This
   prevents unnecessary interrupts on VPP worker cores.

**CPU Core Isolation**

.. cfgcmd:: set system option kernel cpu isolate-cpus <cpu-range>

   Isolates specified CPUs from the kernel scheduler. Isolated cores will
   not run regular system processes and are dedicated to applications like
   VPP.

   The ``<cpu-range>`` can be:
   
   * Single core: ``2``
   * Range: ``2-5``
   * Mixed: ``1,3-5,7``

   .. important:: 

      Always reserve at least 2 cores for the operating system to ensure
      system stability. For example, on a 4-core system, isolate cores
      2-3 for VPP and leave cores 0-1 for the OS.

      Assign the first isolated core as the VPP main core and the
      remaining isolated cores as VPP worker cores. Ensure that VPP CPU
      assignments match the isolated CPU range.

**Adaptive-Tick Mode**

.. cfgcmd:: set system option kernel cpu nohz-full <cpu-range>

   Enables adaptive-tick mode (NO_HZ_FULL) for specified CPUs. This
   causes the kernel to avoid sending scheduling-clock interrupts to CPUs
   that have only one runnable task, significantly reducing interrupt
   overhead for dedicated workloads like VPP.

   Use the same CPU range as configured for ``isolate-cpus``.

**RCU Callback Offloading**

.. cfgcmd:: set system option kernel cpu rcu-no-cbs <cpu-range>

   Offloads Read-Copy-Update (RCU) callback processing from specified
   CPUs. This ensures that RCU callbacks do not prevent the specified CPUs
   from entering dyntick-idle or adaptive-tick mode, which is essential
   for nohz-full functionality.

   Use the same CPU range as configured for ``isolate-cpus``.

System Optimization
--------------------

Additional kernel optimizations can further improve VPP performance by
disabling unnecessary features and reducing system overhead.

**Disable High Precision Event Timer**

.. cfgcmd:: set system option kernel disable-hpet

   Disables the High Precision Event Timer (HPET). HPET can cause
   additional interrupts and overhead that may impact VPP performance.

**Disable Machine Check Exceptions**

.. cfgcmd:: set system option kernel disable-mce

   Disables Machine Check Exception (MCE) reporting and handling. While
   MCE provides hardware error detection, it can introduce latency in
   high-performance scenarios.

**Disable CPU Power Saving**

.. cfgcmd:: set system option kernel disable-power-saving

   Disables CPU power saving mechanisms (C-states). This keeps CPU cores
   at maximum performance levels, eliminating latency from power state
   transitions.

**Disable Soft Lockup Detection**

.. cfgcmd:: set system option kernel disable-softlockup

   Disables the soft lockup detector for kernel threads. This prevents
   false positives when VPP worker threads are busy processing packets.

**Disable CPU Mitigations**

.. cfgcmd:: set system option kernel disable-mitigations

   Disables all optional CPU mitigations for security vulnerabilities
   (for example, Spectre, Meltdown). This may improve performance on some
   platforms.

Optimal Configuration Example
-----------------------------

For a system with 4 CPU cores (0-3) where cores 2-3 are dedicated to VPP:

.. code-block:: none

   # Kernel CPU optimizations
   set system option kernel cpu disable-nmi-watchdog
   set system option kernel cpu isolate-cpus '2-3'
   set system option kernel cpu nohz-full '2-3'
   set system option kernel cpu rcu-no-cbs '2-3'
   
   # System optimizations
   set system option kernel disable-hpet
   set system option kernel disable-mce
   set system option kernel disable-power-saving
   set system option kernel disable-softlockup
   
   # VPP CPU assignment
   set vpp settings resource-allocation cpu-cores '2'
