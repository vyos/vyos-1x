:lastproofread: 2026-03-10

.. _vpp_config_interfaces_bridge:

.. include:: /_include/need_improvement.txt

########################
VPP Bridge Configuration
########################

VPP bridge interfaces provide Layer 2 switching functionality, allowing
multiple interfaces to be connected at the data link layer.

VPP bridges operate as learning bridges, automatically discovering MAC
addresses and building forwarding tables to efficiently switch traffic
between member interfaces. This provides transparent connectivity between
different network segments while maintaining the performance benefits of
VPP's optimized data plane.

**Supported Member Interface Types:**

VPP bridges support various interface types as members:

* Physical Ethernet interfaces (managed through linux-cp)
* :doc:`bonding` - VPP bonding interfaces  
* :doc:`gre` - GRE tunnel interfaces
* :doc:`loopback` - Loopback interfaces (required for BVI)
* :doc:`vxlan` - VXLAN tunnel interfaces

This flexibility allows you to create complex Layer 2 topologies
combining different networking technologies.

Basic Configuration
-------------------

Creating a Bridge Interface
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. cfgcmd:: set interfaces vpp bridge <vppbrN>

   Create a bridge interface where ``<vppbrN>`` follows the naming
   convention ``vppbr1``, ``vppbr2``, etc.

.. note::

   Bridge domain ``vppbr0`` is reserved by VPP and cannot be
   configured through VyOS. Start with ``vppbr1`` for your bridge
   configurations.

**Example:**

.. code-block:: none

   set interfaces vpp bridge vppbr1


Interface Description
^^^^^^^^^^^^^^^^^^^^^

.. cfgcmd:: set interfaces vpp bridge <vppbrN> description <description>

   Set a descriptive name for the bridge interface.

**Example:**

.. code-block:: none

   set interfaces vpp bridge vppbr1 description "Main campus bridge"

Member Interface Configuration
------------------------------

Adding Member Interfaces
^^^^^^^^^^^^^^^^^^^^^^^^

.. cfgcmd:: set interfaces vpp bridge <vppbrN> member interface
            <interface-name>

   Add an interface as a member of the bridge.

**Examples:**

.. code-block:: none

   # Add physical interfaces
   set interfaces vpp bridge vppbr1 member interface eth0
   set interfaces vpp bridge vppbr1 member interface eth1
   
   # Add other VPP interfaces
   set interfaces vpp bridge vppbr1 member interface vppbond0
   set interfaces vpp bridge vppbr1 member interface vppgre1

.. important::

   Bridge members can include various interface types such as:
   
   * Physical Ethernet interfaces (eth0, eth1, etc.)
   * :doc:`bonding` - VPP bonding interfaces (vppbond0, vppbond1, etc.)
   * :doc:`gre` - GRE tunnel interfaces
   * :doc:`loopback` - Loopback interfaces
   * :doc:`vxlan` - VXLAN tunnel interfaces

Bridge Virtual Interface (BVI)
------------------------------

A Bridge Virtual Interface (BVI) provides Layer 3 connectivity to a
bridge domain, allowing the bridge to have an IP address and participate
in routing.

Configuring BVI
^^^^^^^^^^^^^^^

.. cfgcmd:: set interfaces vpp bridge <vppbrN> member interface
            <loopback-interface> bvi

   Designate a loopback interface as the Bridge Virtual Interface for
   the bridge domain.

**Example:**

.. code-block:: none

   # Create a loopback interface first
   set interfaces vpp loopback vpplo1
   
   # Add it to the bridge as BVI
   set interfaces vpp bridge vppbr1 member interface vpplo1 bvi

.. important::

   **BVI Restrictions:**
   
   * Only loopback interfaces can be configured as BVI
   * Each bridge domain can have only one BVI interface

Configuration Examples
----------------------

Basic Bridge Setup
^^^^^^^^^^^^^^^^^^

.. code-block:: none

   # Create bridge interface
   set interfaces vpp bridge vppbr1
   set interfaces vpp bridge vppbr1 description "Office network bridge"
   
   # Add member interfaces
   set interfaces vpp bridge vppbr1 member interface eth0
   set interfaces vpp bridge vppbr1 member interface eth1
   set interfaces vpp bridge vppbr1 member interface eth2

Bridge with BVI
^^^^^^^^^^^^^^^

.. code-block:: none

   # Create bridge and loopback for BVI
   set interfaces vpp bridge vppbr2
   set interfaces vpp bridge vppbr2 description "Server segment with gateway"
   set interfaces vpp loopback vpplo1
   
   # Configure bridge members
   set interfaces vpp bridge vppbr2 member interface eth3
   set interfaces vpp bridge vppbr2 member interface eth4
   set interfaces vpp bridge vppbr2 member interface vpplo1 bvi

Multi-Technology Bridge
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

   # Create bridge combining different interface types
   set interfaces vpp bridge vppbr3
   set interfaces vpp bridge vppbr3 description "Hybrid network bridge"
   
   # Add various interface types
   set interfaces vpp bridge vppbr3 member interface vppbond1
   set interfaces vpp bridge vppbr3 member interface vppgre1
   set interfaces vpp bridge vppbr3 member interface vppvxlan1
   set interfaces vpp bridge vppbr3 member interface vpplo2 bvi

Integration with Kernel Interfaces
----------------------------------

Bridge interfaces can be integrated with kernel interfaces for
management and compatibility with standard Linux networking services.
This is accomplished by binding a kernel interface to the Bridge
Virtual Interface (BVI).

**Example Integration:**

.. code-block:: none

   # Create VPP bridge with member interfaces
   set interfaces vpp bridge vppbr1
   set interfaces vpp bridge vppbr1 member interface eth1
   set interfaces vpp bridge vppbr1 member interface eth2
   
   # Create loopback interface and configure as BVI
   set interfaces vpp loopback vpplo1
   set interfaces vpp bridge vppbr1 member interface vpplo1 bvi
   
   # Bind LCP kernel interface to the BVI loopback
   set interfaces vpp loopback vpplo1 address '192.0.2.1/24'

This configuration creates a kernel interface bound to the BVI,
allowing standard Linux applications and routing daemons to interact
with the VPP bridge. The kernel interface provides Layer 3 access to
the bridge domain.
