:lastproofread: 2026-03-13

.. _vpp_config_interfaces_gre:

.. include:: /_include/need_improvement.txt

#####################
VPP GRE Configuration
#####################

VPP GRE interfaces provide Generic Routing Encapsulation tunneling with
high-performance packet processing. GRE tunnels encapsulate various
protocols within IP packets, enabling connectivity across Layer 3
networks while maintaining the performance benefits of VPP's optimized
data plane.

Basic Configuration
-------------------

Creating a GRE Interface
^^^^^^^^^^^^^^^^^^^^^^^^^

.. cfgcmd:: set interfaces vpp gre <vppgreN>

   Create a GRE interface where ``<vppgreN>`` follows the naming convention
   ``vppgre1``, ``vppgre2``, etc.

.. cfgcmd:: set interfaces vpp gre <vppgreN> remote <address>

   Set the tunnel remote endpoint address. Supports both IPv4 and IPv6
   addresses.

.. cfgcmd:: set interfaces vpp gre <vppgreN> source-address <address>

   Set the tunnel source address. Must match an address configured on
   the local system.

**Basic Example:**

.. code-block:: none

   set interfaces vpp gre vppgre1
   set interfaces vpp gre vppgre1 remote 203.0.113.2
   set interfaces vpp gre vppgre1 source-address 192.168.1.1

Interface Configuration
-----------------------

Description and Administrative Control
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. cfgcmd:: set interfaces vpp gre <vppgreN> description <description>

   Set a descriptive name for the GRE interface.

.. cfgcmd:: set interfaces vpp gre <vppgreN> disable

   Administratively disable the GRE interface.

Tunnel Type
^^^^^^^^^^^

.. cfgcmd:: set interfaces vpp gre <vppgreN> tunnel-type <type>

   Set the GRE tunnel encapsulation type:

   * ``l3`` - Generic Routing Encapsulation for network layer traffic (default).
   * ``teb`` - Transparent Ethernet Bridge for Layer 2 frame transport.
   * ``erspan`` - Encapsulated Remote Switched Port Analyzer for traffic
     mirroring.

Kernel Interface Integration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

LCP kernel pair interface bound to the VPP GRE interface is created
automatically. This allows standard Linux networking tools and
services to interact with the VPP GRE.

IP Address Configuration
------------------------

.. cfgcmd:: set interfaces vpp gre <vppgreN> address <ip-address/prefix>

   Configure IPv4 or IPv6 addresses on the kernel interface. Multiple
   addresses can be assigned.

**Examples:**

.. code-block:: none

   # IPv4 address
   set interfaces vpp gre vppgre0 address 192.168.1.10/24

   # IPv6 address
   set interfaces vpp gre vppgre0 address 2001:db8::10/64

MTU Configuration
-----------------

.. cfgcmd:: set interfaces vpp gre <vppgreN> mtu <size>

   Set the Maximum Transmission Unit (MTU) for the kernel interface.
   The MTU must be compatible with the connected VPP interface.

**Example:**

.. code-block:: none

   set interfaces vpp gre vppgre0 mtu 9000

.. note::

   The MTU size must not exceed the MTU size
   supported by the associated VPP interface.


Configuration Examples
----------------------

Layer 3 GRE Tunnel
^^^^^^^^^^^^^^^^^^

.. code-block:: none

   # IPv4 GRE tunnel
   set interfaces vpp gre vppgre1
   set interfaces vpp gre vppgre1 description "Site-to-site tunnel"
   set interfaces vpp gre vppgre1 remote 203.0.113.10
   set interfaces vpp gre vppgre1 source-address 192.168.1.1
   set interfaces vpp gre vppgre1 tunnel-type l3

Layer 2 GRE Tunnel (TEB)
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

   # Transparent Ethernet Bridge
   set interfaces vpp gre vppgre2
   set interfaces vpp gre vppgre2 description "L2 extension tunnel"
   set interfaces vpp gre vppgre2 remote 203.0.113.20
   set interfaces vpp gre vppgre2 source-address 192.168.1.1
   set interfaces vpp gre vppgre2 tunnel-type teb

IPv6 GRE Tunnel
^^^^^^^^^^^^^^^

.. code-block:: none

   # IPv6 endpoints
   set interfaces vpp gre vppgre3
   set interfaces vpp gre vppgre3 remote 2001:db8::2
   set interfaces vpp gre vppgre3 source-address 2001:db8::1

GRE with Kernel Interface
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

   # GRE tunnel with management interface
   set interfaces vpp gre vppgre4
   set interfaces vpp gre vppgre4 remote 203.0.113.30
   set interfaces vpp gre vppgre4 source-address 192.168.1.1
   set interfaces vpp gre vppgre4 address 10.0.1.1/30

Bridge Integration
------------------

GRE interfaces can be added as members to VPP bridges for Layer 2
switching. See :doc:`bridge` for detailed bridge configuration.

.. code-block:: none

   # Add TEB GRE tunnel to bridge
   set interfaces vpp bridge vppbr1
   set interfaces vpp bridge vppbr1 member interface vppgre2
   set interfaces vpp bridge vppbr1 member interface eth1
