:lastproofread: 2026-02-23

.. _vpp_config_dataplane_ipsec:

.. include:: /_include/need_improvement.txt

#######################
VPP IPsec Configuration
#######################

VPP supports IPsec (Internet Protocol Security) offloading from the
kernel, which speeds up cryptographic operations by leveraging VPP's
high-performance packet processing capabilities.

IPsec does not require any specific configuration on VPP side. If both
sources and destinations of the IPsec traffic are reachable via VPP
interfaces, VPP will automatically offload the IPsec processing from
the kernel. IPsec tunnels are configured in the VPN configuration
section, see :ref:`ipsec_general`.

IPsec Configuration Parameters
==============================

enable IPsec acceleration
^^^^^^^^^^^^^^^^^^^^^^^^^

When VPP is used for offloading IPsec, it creates a virtual interface to
connect to peers. The interface type is always 'ipsec', which is used for
IPsec tunnels.

.. cfgcmd:: set vpp settings ipsec-acceleration

Enabling this option allows VPP to handle IPsec traffic more efficiently by
offloading processing from the kernel.

netlink
^^^^^^^

VPP uses netlink to receive IPsec event messages from the kernel. Proper
settings of the following parameters are crucial for ensuring that VPP can
process all such messages:

.. cfgcmd:: set vpp settings lcp netlink batch-delay-ms <milliseconds>

This parameter specifies the delay in milliseconds between processing
batch netlink messages.

.. cfgcmd:: set vpp settings lcp netlink batch-size <number>

This parameter specifies the maximum number of netlink messages to
process in a single batch.

.. cfgcmd:: set vpp settings lcp netlink rx-buffer-size <number>

This parameter specifies the size of the receive buffer for netlink
socket. If you expect to offload many IPsec tunnels or get frequent and
intensive rekeying, you may need to increase this value.

.. note::

    IPsec uses the same netlink parameters as LCP, so tuning them
    affects both LCP and IPsec processing.

Potential Issues and Troubleshooting
====================================

Improper IPsec configuration can lead to various issues, including:

- Failure to offload IPsec tunnels to VPP
- Lost IPsec event messages due to insufficient netlink buffer size or
  batch settings
- IPsec states or SAs are not synchronized between kernel and VPP
