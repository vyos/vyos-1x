:lastproofread: 2026-03-09

.. _vpp_config_interfaces_bonding:

.. include:: /_include/need_improvement.txt

#########################
VPP Bonding Configuration
#########################

VPP bonding interfaces provide link aggregation capabilities by combining
multiple physical interfaces into a single logical interface for increased
bandwidth and redundancy. VPP bonding offers high-performance packet
processing compared to traditional Linux bonding.

Basic Configuration
-------------------

Creating a Bonding Interface
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To create a VPP bonding interface:

.. cfgcmd:: set interfaces vpp bonding <vppbondN>

   Create a bonding interface where ``<vppbondN>`` follows the naming
   convention ``vppbond0``, ``vppbond1``, and so on. A kernel pair interface is
   automatically created for the VPP bonding interface. This allows
   standard Linux networking tools and services to interact with the VPP
   bond.

**Example:**

.. code-block:: none

   set interfaces vpp bonding vppbond0

Interface Description
^^^^^^^^^^^^^^^^^^^^^

.. cfgcmd:: set interfaces vpp bonding <vppbondN> description <description>

   Set a descriptive name for the bonding interface.

**Example:**

.. code-block:: none

   set interfaces vpp bonding vppbond0 description "Primary uplink bond"

Administrative Control
^^^^^^^^^^^^^^^^^^^^^^

.. cfgcmd:: set interfaces vpp bonding <vppbondN> disable

   Administratively disable the bonding interface. By default, interfaces
   are enabled.

Member Interface Configuration
------------------------------

Adding Member Interfaces
^^^^^^^^^^^^^^^^^^^^^^^^

.. cfgcmd:: set interfaces vpp bonding <vppbondN> member interface
   <interface-name>

   Add physical interfaces as members of the bond. You can add multiple
   interfaces to the same bond.

**Example:**

.. code-block:: none

   set interfaces vpp bonding vppbond0 member interface eth0
   set interfaces vpp bonding vppbond0 member interface eth1

.. note::

   Member interfaces must have the same speed and duplex for optimal
   performance. They must already be attached to VPP.

Bonding Modes
-------------

.. cfgcmd:: set interfaces vpp bonding <vppbondN> mode <mode>

   Configure the bonding mode. Available modes:

   * **802.3ad**: IEEE 802.3ad Dynamic Link Aggregation (LACP) - Default
   * **active-backup**: Fault tolerant, only one slave interface active
   * **broadcast**: Transmits everything on all slave interfaces
   * **round-robin**: Load balance by transmitting packets in sequential order
   * **xor-hash**: Distribute based on hash policy

**Examples:**

.. code-block:: none

   # Use LACP (recommended for switch environments)
   set interfaces vpp bonding vppbond0 mode 802.3ad
   
   # Use active-backup for simple failover
   set interfaces vpp bonding vppbond0 mode active-backup

Hash Policies
-------------

For load balancing modes, configure how the system distributes traffic
across member interfaces:

.. cfgcmd:: set interfaces vpp bonding <vppbondN> hash-policy <policy>

   Set the transmit hash policy:

   * **layer2**: Use MAC addresses to generate hash (default)
   * **layer2+3**: Combine MAC addresses and IP addresses
   * **layer3+4**: Combine IP addresses and port numbers

**Examples:**

.. code-block:: none

   # Layer 2 hashing (default)
   set interfaces vpp bonding vppbond0 hash-policy layer2
   
   # Layer 3+4 for better distribution with multiple flows
   set interfaces vpp bonding vppbond0 hash-policy layer3+4

MAC Address Configuration
-------------------------

.. cfgcmd:: set interfaces vpp bonding <vppbondN> mac <mac-address>

   Set a specific MAC address for the bonding interface.

**Example:**

.. code-block:: none

   set interfaces vpp bonding vppbond0 mac 00:11:22:33:44:55

IP Address Configuration
------------------------

.. cfgcmd:: set interfaces vpp bonding <vppbondN> address <ip-address/prefix>

   Configure IPv4 or IPv6 addresses on the kernel interface. You can
   assign multiple addresses.

**Examples:**

.. code-block:: none

   # IPv4 address
   set interfaces vpp bonding vppbond0 address 192.168.1.10/24

   # IPv6 address
   set interfaces vpp bonding vppbond0 address 2001:db8::10/64

   # Multiple addresses
   set interfaces vpp bonding vppbond0 address 192.168.1.10/24
   set interfaces vpp bonding vppbond0 address 10.0.0.10/8

MTU Configuration
-----------------

.. cfgcmd:: set interfaces vpp bonding <vppbondN> mtu <size>

   Set the Maximum Transmission Unit (MTU) for the kernel interface. The
   MTU must be compatible with the connected VPP interface.

**Example:**

.. code-block:: none

   set interfaces vpp bonding vppbond0 mtu 9000

.. note::

   The MTU setting must match or be smaller than the MTU supported by the
   associated VPP interface.

VLAN Configuration
------------------

VPP kernel interfaces support VLAN (Virtual LAN) sub-interfaces for
network segmentation.

Creating VLAN Sub-interfaces
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. cfgcmd:: set interfaces vpp bonding <vppbondN> vif <vlan-id>

   Create a VLAN sub-interface with the specified VLAN ID (0-4094).

**Example:**

.. code-block:: none

   set interfaces vpp bonding vppbond0 vif 100

VLAN Sub-interface Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

VLAN sub-interfaces support the same configuration options as the parent
interface:

.. cfgcmd:: set interfaces vpp bonding <vppbondN> vif <vlan-id> address
   <ip-address/prefix>

.. cfgcmd:: set interfaces vpp bonding <vppbondN> vif <vlan-id> description
   <description>

.. cfgcmd:: set interfaces vpp bonding <vppbondN> vif <vlan-id> disable

.. cfgcmd:: set interfaces vpp bonding <vppbondN> vif <vlan-id> mtu <size>

**Examples:**

.. code-block:: none

   # Configure VLAN 100
   set interfaces vpp bonding vppbond0 vif 100 address 192.168.100.1/24
   set interfaces vpp bonding vppbond0 vif 100 description "Management VLAN"
   set interfaces vpp bonding vppbond0 vif 100 mtu 1500

   # Configure VLAN 200
   set interfaces vpp bonding vppbond0 vif 200 address 192.168.200.1/24
   set interfaces vpp bonding vppbond0 vif 200 description "Guest VLAN"


Complete Configuration Example
------------------------------

Here's a complete example configuring a bonding interface with LACP:

.. code-block:: none

   # Create bonding interface
   set interfaces vpp bonding vppbond0
   set interfaces vpp bonding vppbond0 description "Server uplink bond"
   
   # Configure bonding parameters
   set interfaces vpp bonding vppbond0 mode 802.3ad
   set interfaces vpp bonding vppbond0 hash-policy layer3+4
   
   # Add member interfaces
   set interfaces vpp bonding vppbond0 member interface eth0
   set interfaces vpp bonding vppbond0 member interface eth1

   # Configure IP on kernel interface
   set interfaces vpp bonding vppbond0 address 192.168.1.10/24

Best Practices
--------------

* Use **802.3ad mode** with LACP-capable switches for best performance
  and standards compliance.
* Configure **layer3+4 hash policy** for environments with multiple
  traffic flows.
* Ensure member interfaces have identical settings (speed, duplex,
  MTU).
