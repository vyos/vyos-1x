:lastproofread: 2026-03-13

.. _vpp_config_interfaces_loopback:

.. include:: /_include/need_improvement.txt

####################################
VPP Loopback Interface Configuration
####################################

VPP loopback interfaces provide virtual interfaces that remain
administratively up and are commonly used for stable addressing,
routing protocols, and as Bridge Virtual Interfaces (BVI). Loopback
interfaces in VPP offer high-performance virtual connectivity with optimized
packet processing.

Basic Configuration
-------------------

Creating a Loopback Interface
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. cfgcmd:: set interfaces vpp loopback <vpploN>

   Create a loopback interface where ``<vpploN>`` follows the naming
   convention ``vpplo1``, ``vpplo2``, etc.

**Basic Example:**

.. code-block:: none

   set interfaces vpp loopback vpplo1

Interface Configuration
-----------------------

Description and Administrative Control
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. cfgcmd:: set interfaces vpp loopback <vpploN> description <description>

   Set a descriptive name for the loopback interface.

.. cfgcmd:: set interfaces vpp loopback <vpploN> disable

   Administratively disable the loopback interface.

Kernel Interface Integration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Kernel interface is bounded to the VPP loopback interface for management
and application compatibility.

IP Address Configuration
------------------------

.. cfgcmd:: set interfaces vpp loopback <vpploN> address <ip-address/prefix>

   Configure IPv4 or IPv6 addresses on the kernel interface. Multiple
   addresses can be assigned.

**Examples:**

.. code-block:: none

   # IPv4 address
   set interfaces vpp loopback vpplo1 address 192.168.1.10/24

   # IPv6 address
   set interfaces vpp loopback vpplo1 address 2001:db8::10/64

MTU Configuration
-----------------

.. cfgcmd:: set interfaces vpp loopback <vpploN> mtu <size>

   Set the Maximum Transmission Unit (MTU) for the kernel interface.
   The MTU must be compatible with the connected VPP interface.

VLAN Configuration
------------------

VPP kernel interfaces support VLAN (Virtual LAN) sub-interfaces for network
segmentation.

Creating VLAN Sub-interfaces
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. cfgcmd:: set interfaces vpp loopback <vpploN> vif <vlan-id>

   Create a VLAN sub-interface with the specified VLAN ID (0-4094).

VLAN Sub-interface Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

VLAN sub-interfaces support the same configuration options as the parent
interface:

.. cfgcmd:: set interfaces vpp loopback <vpploN> vif <vlan-id> address
   <ip-address/prefix>

.. cfgcmd:: set interfaces vpp loopback <vpploN> vif <vlan-id> description
   <description>

.. cfgcmd:: set interfaces vpp loopback <vpploN> vif <vlan-id> disable

.. cfgcmd:: set interfaces vpp loopback <vpploN> vif <vlan-id> mtu <size>

**Examples:**

.. code-block:: none

   # Configure VLAN 100
   set interfaces vpp loopback vpplo1 vif 100 address 192.168.100.1/24
   set interfaces vpp loopback vpplo1 vif 100 description "Management VLAN"
   set interfaces vpp loopback vpplo1 vif 100 mtu 1500

   # Configure VLAN 200
   set interfaces vpp loopback vpplo1 vif 200 address 192.168.200.1/24
   set interfaces vpp loopback vpplo1 vif 200 description "Guest VLAN"

Configuration Examples
----------------------

Basic Loopback Interface
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

   # Create simple loopback
   set interfaces vpp loopback vpplo1
   set interfaces vpp loopback vpplo1 description "Router ID interface"

Loopback with Kernel Interface
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

   # Loopback with management access
   set interfaces vpp loopback vpplo2
   set interfaces vpp loopback vpplo2 description "Management loopback"
   set interfaces vpp loopback vpplo2 address 10.255.255.1/32

Bridge Virtual Interface (BVI)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: none

   # Loopback as BVI for bridge
   set interfaces vpp loopback vpplo3
   set interfaces vpp loopback vpplo3 description "Bridge gateway interface"
   set interfaces vpp bridge vppbr1
   set interfaces vpp bridge vppbr1 member interface vpplo3 bvi
   set interfaces vpp loopback vpplo3 address 192.168.100.1/24
