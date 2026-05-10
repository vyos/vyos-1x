:lastproofread: 2025-09-04

.. _vpp_dconfig_index:

.. include:: /_include/need_improvement.txt

#################
VPP Configuration
#################

VPP settings consist of several main sections.

Main Dataplane settings and internal VPP interfaces:

.. toctree::
   :maxdepth: 1
   :includehidden:

   dataplane/index
   interfaces/index

Features that can be enabled on VPP Dataplane:

.. toctree::
   :maxdepth: 1
   :includehidden:

   acl
   ipfix
   ipsec
   nat/index
   sflow

VPP Initialization
==================

When VPP Dataplane is configured and the configuration is committed, VyOS will attempt to start VPP and initialize all interfaces assigned to it. During this process the following steps occur:

1. VyOS checks that the system meets all requirements for VPP operation. If any requirement is not met, VPP will not start and an error message will be displayed.

2. VPP is started and its initial configuration is applied.

3. All interfaces assigned to VPP are initialized and brought up.

4. A special virtual interfaces are reinstalled to the kernel with the same names as interfaces that were attached to VPP to maintain compatibility with the configuration.

5. VyOS configuration initializes those virtual interfaces, so that features that exist only in kernel dataplane continue to operate.
