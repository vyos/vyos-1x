:lastproofread: 2026-02-17

.. _vpp_limitations:

.. include:: /_include/need_improvement.txt

#########################
VPP Dataplane Limitations
#########################


VPP Dataplane provides significant performance advantages, but has some
limitations you should consider.

* **Feature Parity**

  VPP does not support all features available in the Linux kernel dataplane.
  Some networking features, specific protocols, or services may not be
  available.

  While VPP supports various interface types similar to the kernel, their
  capabilities may differ.

* **NIC and Driver Compatibility**

  VyOS currently supports only DPDK drivers for network interfaces.
  Not all network interface cards are compatible with DPDK drivers.

* **Data Path Limitations**

  If a feature exists only in the kernel dataplane, traffic that uses that
  feature cannot traverse VPP interfaces. Examples include:

  - Firewall
  - QoS

  When traffic uses the pure VPP path, it does not reach the kernel, where
  such features are implemented. Plan how traffic flows through your VyOS
  instance to ensure it reaches the necessary features.

  VPP provides native alternatives for some features. For example, VPP
  native ACLs provide basic firewall functionality.
