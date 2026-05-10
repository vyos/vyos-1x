:lastproofread: 2026-03-13

.. _vpp_config_interfaces_vxlan:

.. include:: /_include/need_improvement.txt

#######################
VPP VXLAN Configuration
#######################

VPP VXLAN interfaces provide virtual extensible local area network (VXLAN)
tunneling with high-performance packet processing. VXLAN extends Layer 2
domains across Layer 3 networks using UDP encapsulation, enabling scalable
multi-tenant networking while leveraging VPP's optimized data plane.

Basic Configuration
-------------------

Creating a VXLAN Interface
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. cfgcmd:: set interfaces vpp vxlan <vppvxlanN>

   Create a VXLAN interface where ``<vppvxlanN>`` follows the naming
   convention ``vppvxlan1``, ``vppvxlan2``, etc.

.. cfgcmd:: set interfaces vpp vxlan <vppvxlanN> vni <vni>

   Set the Virtual Network Identifier (VNI) for the VXLAN tunnel. Valid range
   is 0-16777214.

.. cfgcmd:: set interfaces vpp vxlan <vppvxlanN> remote <address>

   Set the tunnel remote endpoint address. Supports both IPv4 and IPv6
   addresses.

.. cfgcmd:: set interfaces vpp vxlan <vppvxlanN> source-address <address>

   Set the tunnel source address. Must match an address configured on the
   local system.

**Basic Example:**

.. code-block:: none

   set interfaces vpp vxlan vppvxlan1
   set interfaces vpp vxlan vppvxlan1 vni 100
   set interfaces vpp vxlan vppvxlan1 remote 203.0.113.2
   set interfaces vpp vxlan vppvxlan1 source-address 192.168.1.1

Interface Configuration
-----------------------

Description and Administrative Control
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. cfgcmd:: set interfaces vpp vxlan <vppvxlanN> description <description>

   Set a descriptive name for the VXLAN interface.

.. cfgcmd:: set interfaces vpp vxlan <vppvxlanN> disable

   Administratively disable the VXLAN interface.

Kernel Interface Integration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The kernel interface is bound to the VXLAN tunnel for management and
application compatibility.

IP Address Configuration
------------------------

.. cfgcmd:: set interfaces vpp vxlan <vppvxlanN> address <ip-address/prefix>

   Configure IPv4 or IPv6 addresses on the kernel interface. Multiple
   addresses can be assigned.

**Examples:**

.. code-block:: none

   set interfaces vpp vxlan vppvxlan1 address 192.168.1.10/24
   set interfaces vpp vxlan vppvxlan1 address 2001:db8::10/64

MTU Configuration
-----------------

.. cfgcmd:: set interfaces vpp vxlan <vppvxlanN> mtu <size>

   Set the Maximum Transmission Unit (MTU) for the kernel interface. The MTU
   must be compatible with the connected VPP interface.

Configuration Examples
----------------------

Basic VXLAN Tunnel
^^^^^^^^^^^^^^^^^^^

.. code-block:: none

   # IPv4 VXLAN tunnel
   set interfaces vpp vxlan vppvxlan1
   set interfaces vpp vxlan vppvxlan1 description "Tenant A network extension"
   set interfaces vpp vxlan vppvxlan1 vni 1000
   set interfaces vpp vxlan vppvxlan1 remote 203.0.113.10
   set interfaces vpp vxlan vppvxlan1 source-address 192.168.1.1

IPv6 VXLAN Tunnel
^^^^^^^^^^^^^^^^^

.. code-block:: none

   # IPv6 endpoints
   set interfaces vpp vxlan vppvxlan2
   set interfaces vpp vxlan vppvxlan2 vni 2000
   set interfaces vpp vxlan vppvxlan2 remote 2001:db8::2
   set interfaces vpp vxlan vppvxlan2 source-address 2001:db8::1

VXLAN with Kernel Interface
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

   # VXLAN tunnel with management interface
   set interfaces vpp vxlan vppvxlan3
   set interfaces vpp vxlan vppvxlan3 vni 3000
   set interfaces vpp vxlan vppvxlan3 remote 203.0.113.30
   set interfaces vpp vxlan vppvxlan3 source-address 192.168.1.1
   set interfaces vpp vxlan vppvxlan3 address 10.0.3.1/24

Bridge Integration
------------------

VXLAN interfaces are commonly used as members in VPP bridges for Layer 2
extension. See :doc:`bridge` for more information.

.. code-block:: none

   # Add VXLAN tunnel to bridge
   set interfaces vpp bridge vppbr1
   set interfaces vpp bridge vppbr1 member interface vppvxlan1
   set interfaces vpp bridge vppbr1 member interface eth1
   set interfaces vpp bridge vppbr1 member interface vpplo1 bvi

Multi-Tenant Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

   # Multiple VNIs for tenant separation
   set interfaces vpp vxlan vppvxlan10
   set interfaces vpp vxlan vppvxlan10 description "Tenant A - Production"
   set interfaces vpp vxlan vppvxlan10 vni 1001
   set interfaces vpp vxlan vppvxlan10 remote 203.0.113.20
   set interfaces vpp vxlan vppvxlan10 source-address 192.168.1.1
   
   set interfaces vpp vxlan vppvxlan11
   set interfaces vpp vxlan vppvxlan11 description "Tenant A - Development"
   set interfaces vpp vxlan vppvxlan11 vni 1002
   set interfaces vpp vxlan vppvxlan11 remote 203.0.113.21
   set interfaces vpp vxlan vppvxlan11 source-address 192.168.1.1
