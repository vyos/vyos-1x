:lastproofread: 2026-02-16

.. _vpp_requirements:

.. include:: /_include/need_improvement.txt

##########################
VPP Dataplane Requirements
##########################

VPP Dataplane requires specific hardware. Ensure your system meets these
prerequisites before enabling VPP:

* **Deployment Platform**

  VPP Dataplane is available on both bare-metal, on-premise virtualized, and
  cloud deployment platforms.

* **CPU Requirements**

  Regardless of the platform, VPP Dataplane requires a CPU with:

  - SSE4.2 support (available on most modern Intel and AMD CPUs).
  - At least 4 physical CPU cores for a minimum configuration (more cores
    recommended for higher throughput).

  .. important:: **Physical Cores vs Logical Cores**

     VPP Dataplane requires 4 *physical* CPU cores, not logical cores.
     Systems with Simultaneous Multithreading (SMT) or Hyper-Threading (HT)
     present each physical core as 2 logical cores.

     Cloud providers often display logical cores as "cores" or "vCPUs".
     For example, a cloud instance showing "4 cores" may have only 2 physical
     cores with SMT/HT enabled. Always verify the actual physical core count
     in your cloud provider's documentation.

  For virtualized environments, ensure CPU features are passed through to the
  VM and that sufficient physical cores are allocated.

* **Memory Requirements**

  Memory significantly affects VPP stability. Insufficient RAM can cause
  initialization failures or prevent the dataplane from starting.

  - Minimum: 8 GB RAM. VyOS will not start the VPP Dataplane if less than 8 GB
    is available.
  - Recommended: 16 GB or more (especially for high throughput, many interfaces,
    or large routing tables).

* **Network Interface Cards (NICs)**

  .. warning::

     VyOS supports only specific NICs for the VPP dataplane. Using unsupported
     hardware may cause activation failures, initialization errors, crashes,
     or degraded performance.

  When enabling VPP, VyOS checks detected network interfaces against a list
  of validated NICs. Validation is based on the **PCI ID** of the device or
  the **kernel driver** used by the interface.

  Supported NICs:

  .. list-table::
     :widths: 15 18 40 35
     :header-rows: 1

     * - **Filter Type**
       - **Filter Value**
       - **NIC Name/Description**
       - **Platform Where NIC Can Be Found**
     * - PCI ID
       - 15b3:1019
       - Mellanox Technologies MT28800 Family
         [ConnectX-5 Ex]
       - Bare-metal
     * - PCI ID
       - 15b3:101d
       - Mellanox Technologies MT2892 Family
         [ConnectX-6 Dx]
       - Bare-metal
     * - PCI ID
       - 15b3:101e
       - Mellanox Technologies ConnectX Family
         mlx5Gen Virtual Function
       - Oracle Cloud
     * - PCI ID
       - 8086:1592
       - Intel Corporation Ethernet Controller
         E810-C for QSFP
       - Bare-metal
     * - PCI ID
       - 1ae0:0042
       - Google, Inc. Compute Engine Virtual
         Ethernet [gVNIC]
       - Google Cloud
     * - PCI ID
       - 1af4:1000
       - Red Hat, Inc. Virtio network device
       - KVM-based hypervisors, including with
         Open vSwitch; Google Cloud
     * - PCI ID
       - 1d0f:ec20
       - Amazon.com, Inc. Elastic Network
         Adapter (ENA)
       - AWS
     * - Kernel Driver
       - hv_netvsc
       - Microsoft Hyper-V network interface
         card
       - Microsoft Azure

  If no supported NIC is detected, VPP activation will be rejected.

  In testing or advanced deployments, unsupported hardware can be explicitly
  allowed in the configuration:

  .. cfgcmd:: set vpp settings allow-unsupported-nics

  .. note::

     This option bypass the hardware validation checks for the specified
     devices. Stability and performance are not guaranteed when using
     unsupported NICs or drivers.
