:lastproofread: 2026-03-13

.. _vpp_config_interfaces_ipip:

.. include:: /_include/need_improvement.txt

######################
VPP IPIP Configuration
######################

VPP IPIP interfaces provide IP-in-IP tunneling with high-performance
packet processing. IPIP tunnels encapsulate IP packets within IP
packets, creating point-to-point connections across Layer 3 networks.

Basic Configuration
-------------------

Creating an IPIP Interface
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. cfgcmd:: set interfaces vpp ipip <vppipipN>

   Create an IPIP interface where ``<vppipipN>`` follows the naming
   convention ``vppipip1``, ``vppipip2``, etc.

.. cfgcmd:: set interfaces vpp ipip <vppipipN> remote <address>

   Set the tunnel remote endpoint address. Supports both IPv4 and IPv6
   addresses.

.. cfgcmd:: set interfaces vpp ipip <vppipipN> source-address <address>

   Set the tunnel source address. The source address must match an address
   configured on the local system.

**Basic Example:**

.. code-block:: none

   set interfaces vpp ipip vppipip1
   set interfaces vpp ipip vppipip1 remote 203.0.113.2
   set interfaces vpp ipip vppipip1 source-address 192.168.1.1

Interface Configuration
-----------------------

Description and Administrative Control
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. cfgcmd:: set interfaces vpp ipip <vppipipN> description <description>

   Set a descriptive name for the IPIP interface.

.. cfgcmd:: set interfaces vpp ipip <vppipipN> disable

   Administratively disable the IPIP interface.

Kernel Interface Integration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Kernel interface is bound to the VPP IPIP interface for management and
application compatibility.

IP Address Configuration
------------------------

.. cfgcmd:: set interfaces vpp ipip <vppipipN> address <ip-address/prefix>

   Configure IPv4 or IPv6 addresses on the kernel interface. Multiple
   addresses can be assigned.

**Examples:**

.. code-block:: none

   # IPv4 address
   set interfaces vpp ipip vppipip0 address 192.168.1.10/24

   # IPv6 address
   set interfaces vpp ipip vppipip0 address 2001:db8::10/64

MTU Configuration
-----------------

.. cfgcmd:: set interfaces vpp ipip <vppipipN> mtu <size>

   Set the Maximum Transmission Unit (MTU) for the kernel interface.
   The MTU must be compatible with the connected VPP interface.

Configuration Examples
----------------------

IPv4 IPIP Tunnel
^^^^^^^^^^^^^^^^

.. code-block:: none

   # Basic IPv4 IPIP tunnel
   set interfaces vpp ipip vppipip1
   set interfaces vpp ipip vppipip1 description "Site-to-site IPIP tunnel"
   set interfaces vpp ipip vppipip1 remote 203.0.113.10
   set interfaces vpp ipip vppipip1 source-address 192.168.1.1

IPv6 IPIP Tunnel
^^^^^^^^^^^^^^^^

.. code-block:: none

   # IPv6 endpoints
   set interfaces vpp ipip vppipip2
   set interfaces vpp ipip vppipip2 remote 2001:db8::2
   set interfaces vpp ipip vppipip2 source-address 2001:db8::1

IPIP with Kernel Interface
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

   # IPIP tunnel with management interface
   set interfaces vpp ipip vppipip3
   set interfaces vpp ipip vppipip3 remote 203.0.113.30
   set interfaces vpp ipip vppipip3 source-address 192.168.1.1
   set interfaces vpp ipip vppipip3 address 10.0.2.1/30
