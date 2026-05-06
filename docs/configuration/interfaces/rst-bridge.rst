:lastproofread: 2025-12-22

.. _bridge-interface:

######
Bridge
######

VyOS bridges connect Ethernet segments by grouping multiple interfaces into a 
single bridge interface, which acts as a virtual software switch. Unlike 
routers, which forward traffic based on Layer 3 IP addresses, bridges operate 
at Layer 2 and forward traffic based on MAC addresses. Operating at Layer 2, 
bridges are protocol-agnostic and transparently forward all Ethernet-
encapsulated traffic, whether it is IPv4, IPv6, or specialized industrial 
protocols. 

This implementation utilizes the Linux bridge subsystem to support a subset of 
the ANSI/IEEE 802.1d standard for transparent bridging and MAC address learning. 

.. note:: :abbr:`STP (Spanning Tree Protocol)` is disabled by default in VyOS 
   and must be explicitly enabled if required. See :ref:`stp` for details.

*************
Configuration
*************

Common interface configuration
==============================

.. cmdinclude:: /_include/interface-common-with-dhcp.txt
   :var0: bridge
   :var1: br0

Member interfaces
=================

.. cfgcmd:: set interfaces bridge <interface> member interface <member>

   **Configure an interface as a bridge member.**

   Valid interface types are: :ref:`ethernet-interface`, :ref:`bond-interface`, 
   :ref:`l2tpv3-interface`, :ref:`openvpn`, :ref:`vxlan-interface`, 
   :ref:`wireless-interface`, :ref:`tunnel-interface`, and 
   :ref:`geneve-interface`.

   Use tab completion to list interfaces that can be bridged.

.. cfgcmd:: set interfaces bridge <interface> member interface <member>
   priority <priority>

   **Configure the** :abbr:`STP (Spanning Tree Protocol)` **port priority 
   for a specific member interface within a bridge.** 

   Within the :abbr:`STP (Spanning Tree Protocol)` topology, each member interface 
   in a bridge operates as a port with an assigned **priority** and **path cost**. 
   :abbr:`STP (Spanning Tree Protocol)` uses these values to determine the 
   **lowest-cost path** to the root bridge, maintaining a loop-free topology. 
   Traffic flows through the path with the lowest path cost, while alternate 
   paths remain in standby. 

   A **lower** priority value means **higher** precedence in path selection.

   :abbr:`STP (Spanning Tree Protocol)` considers the port priority only if 
   multiple member interfaces have the same path costs.


.. cfgcmd:: set interfaces bridge <interface> member interface <member>
   cost <cost>

   **Configure the** :abbr:`STP (Spanning Tree Protocol)` **path cost for a 
   specific member interface within the bridge.**

   Path cost is the primary metric :abbr:`STP (Spanning Tree Protocol)` uses to 
   determine the path to the root bridge. This value is based on interface 
   bandwidth; faster interfaces receive lower costs. 

   By assigning a lower cost, you give the interface higher precedence during 
   path selection.

.. cfgcmd:: set interfaces bridge <interface> member interface <member>
   disable-learning

   **Disable MAC address learning for a specific member interface
   within a bridge.**

   When learning is disabled, the bridge will not add source MAC addresses
   observed on this port to its forwarding database (FDB). Frames destined
   to MACs not present in the FDB are then flooded to all bridge ports
   rather than unicast-forwarded.

Bridge options
==============

Configure how bridge interfaces maintain their :abbr:`FDB (Forwarding Database)`
, react to topology changes, and optimize multicast data streams. 

.. cfgcmd:: set interfaces bridge <interface> aging <time>

   **Configure the MAC address aging time for the bridge.**

   The duration in seconds that a MAC address remains in the bridge’s :abbr:`FDB 
   (Forwarding Database)` before removal if no traffic is received from that 
   address.

   The default value is 300 seconds.

.. cfgcmd:: set interfaces bridge <interface> max-age <time>

   **Configure the** :abbr:`STP (Spanning Tree Protocol)` **max age timer for 
   the bridge.**

   The duration in seconds that the bridge waits for a :abbr:`BPDU (Bridge 
   Protocol Data Unit)` from the root bridge.

   If the bridge does not receive a :abbr:`BPDU (Bridge Protocol Data Unit)` 
   within this period, it recalculates the path to the root bridge or initiates 
   a new root bridge election.

.. cfgcmd:: set interfaces bridge <interface> igmp querier

   **Configure the bridge interface to act as the** :abbr:`IGMP (Internet Group 
   Management Protocol)`/:abbr:`MLD (Multicast Listener Discovery)` **Querier.**

   **When configured:** The bridge interface sends :abbr:`IGMP (Internet Group 
   Management Protocol)` (IPv4) and :abbr:`MLD (Multicast Listener Discovery)`
   (IPv6) general queries to all connected hosts to identify active multicast 
   listeners.

.. cfgcmd:: set interfaces bridge <interface> igmp snooping

   **Configure the bridge interface to perform** :abbr:`IGMP (Internet Group 
   Management Protocol)`/:abbr:`MLD (Multicast Listener Discovery)`
   **snooping.** 

   **When configured:** The bridge interface monitors :abbr:`IGMP (Internet Group 
   Management Protocol)` (IPv4) and :abbr:`MLD (Multicast Listener Discovery)`
   (IPv6) join requests and restricts multicast traffic forwarding to only active 
   listeners. This prevents network flooding.

.. _stp:

STP configuration
-----------------

:abbr:`STP (Spanning Tree Protocol)` is a Layer 2 protocol that prevents loops 
in Ethernet networks by ensuring only one logical path exists between any two 
bridges. This creates a loop-free topology and prevents broadcast storms that 
can crash the network.

By default, :abbr:`STP (Spanning Tree Protocol)` is disabled on bridge interfaces. 
To activate loop prevention, you must explicitly enable the protocol and 
configure its parameters. 

.. cfgcmd:: set interfaces bridge <interface> stp

   Enable :abbr:`STP (Spanning Tree Protocol)` on the bridge interface.

.. cfgcmd:: set interfaces bridge <interface> forwarding-delay <delay>

   **Configure the** :abbr:`STP (Spanning Tree Protocol)` **delay, in seconds, 
   for the bridge interface.**

   This parameter defines how long the bridge interface remains in the listening 
   and learning states before forwarding traffic. The delay ensures that the 
   bridge has sufficient time to detect loops (in the listening state) and learn 
   the MAC addresses of connected devices (in the learning state).

   The default value is 15 seconds. The total time before forwarding begins is 
   twice this value.

.. cfgcmd:: set interfaces bridge <interface> hello-time <interval>

   **Configure the** :abbr:`STP (Spanning Tree Protocol)` **Hello advertisement 
   interval, in seconds.**

   This parameter sets the frequency at which the bridge interface transmits 
   Hello packets (:abbr:`BPDUs (Bridge Protocol Data Units)`). These packets 
   originate from the root bridge and are propagated by designated bridges. If 
   neighbors stop receiving Hello packets, they assume a connection failure and 
   trigger a topology recalculation.

   The default value is 2 seconds.

VLAN
====

VLAN-aware bridges
------------------

.. cfgcmd:: set interfaces bridge <interface> enable-vlan

   **Enable VLAN filtering (also known as VLAN awareness) on the bridge interface.**

   When enabled, the bridge strictly segregates traffic among VLANs configured
   on its member interfaces.

   .. note::
      Do not configure **vif 1** on a VLAN-aware bridge. The main bridge
      interface acts as VLAN 1 (the default native VLAN) and automatically
      handles all untagged traffic.

.. cfgcmd:: set interfaces bridge <interface> protocol <802.1ad | 802.1q>

   **Configure the VLAN protocol (EtherType) for the bridge interface.**

   The following options are available:  

   * ``802.1q`` (default): Sets the EtherType to ``0x8100``. Used for standard 
     enterprise VLANs. 
   * ``802.1ad``: Sets the EtherType to ``0x88a8``. Used for QinQ (provider bridging).   

VLAN configuration
------------------

.. cmdinclude:: /_include/interface-vlan-8021q.txt
   :var0: bridge
   :var1: br0

.. cfgcmd:: set interfaces bridge <interface> member interface <member>
   native-vlan <vlan-id>

   **Configure the native VLAN ID for a specific member interface within a 
   VLAN-aware bridge.**

   This assigns the specified ``<vlan-id>`` to untagged traffic entering the member 
   interface. The bridge strips the VLAN tag from outgoing traffic matching this 
   ID.

   **Example:** 

   Set the native VLAN ID to 2 for the member interface ``eth0``:

   .. code-block:: none

     set interfaces bridge br1 member interface eth0 native-vlan 2

.. cfgcmd:: set interfaces bridge <interface> member interface <member>
   allowed-vlan <vlan-id>

   **Configure allowed VLAN IDs for a specific member interface within a 
   VLAN-aware bridge.**

   Enter a single VLAN ID or a range of VLAN IDs separated by a hyphen.

   **Example:** 

   To allow VLAN ID 4 on member interface ``eth0``:

   .. code-block:: none

     set interfaces bridge br1 member interface eth0 allowed-vlan 4

   **Example:** 

   To allow VLAN IDs 6 through 8 on member interface ``eth0``:

   .. code-block:: none

     set interfaces bridge br1 member interface eth0 allowed-vlan 6-8

SPAN port mirroring
===================
.. cmdinclude:: ../../_include/interface-mirror.txt
   :var0: bridge
   :var1: br1
   :var2: eth3

********
Examples
********

Configure a standard bridge
===========================

The following example creates a bridge named br100 with :abbr:`STP (Spanning 
Tree Protocol)` enabled.

Configuration requirements:

* **Bridge name:** ``br100``
* **Member interfaces:** Physical interface ``eth1`` and VLAN interface ``eth2.10``.
* **STP:** Enabled.
* **Bridge IP addresses:** ``192.0.2.1/24`` (IPv4) and ``2001:db8::ffff/64`` (IPv6).

.. code-block:: none

  set interfaces bridge br100 address 192.0.2.1/24
  set interfaces bridge br100 address 2001:db8::ffff/64
  set interfaces bridge br100 member interface eth1
  set interfaces bridge br100 member interface eth2.10
  set interfaces bridge br100 stp

Verify the configuration:

.. code-block:: none

   vyos@vyos# show interfaces bridge br100
    address 192.0.2.1/24
    address 2001:db8::ffff/64
    member {
        interface eth1 {
        }
        interface eth2.10 {
        }
    }
    stp


Configure a VLAN-aware bridge
=============================

The following example creates a VLAN-aware bridge named br100. In this setup, 
one member interface is configured as a trunk port, and the other as an access 
port. The VLAN interface is configured with IP addresses.

**Configuration requirements:**

* **Bridge name:** ``br100``.
* **Trunk port** (``eth1``): Handles **tagged** traffic for VLAN 10.
* **Access port** (``eth2``): Handles **untagged** traffic (assigned to native 
  VLAN 10).
* **STP:** Enabled.
* **VLAN IP addresses** (``vif 10``): ``192.0.2.1/24`` (IPv4) and 
  ``2001:db8::ffff/64`` (IPv6).

.. code-block:: none

  set interfaces bridge br100 enable-vlan
  set interfaces bridge br100 member interface eth1 allowed-vlan 10
  set interfaces bridge br100 member interface eth2 native-vlan 10
  set interfaces bridge br100 vif 10 address 192.0.2.1/24
  set interfaces bridge br100 vif 10 address 2001:db8::ffff/64
  set interfaces bridge br100 stp

Verify the configuration:

.. code-block:: none

   vyos@vyos# show interfaces bridge br100
    enable-vlan
    member {
        interface eth1 {
            allowed-vlan 10
        }
        interface eth2 {
            native-vlan 10
        }
    }
    stp
    vif 10 {
        address 192.0.2.1/24
        address 2001:db8::ffff/64
    }


Operation
=========

.. opcmd:: show bridge

   Show the status of member interfaces for all configured bridges.

   .. code-block:: none

     vyos@vyos:~$ show bridge
     3: eth1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 master br0 state forwarding
     priority 32 cost 100
     4: eth2: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 master br0 state forwarding
     priority 32 cost 100

.. opcmd:: show bridge <name> fdb

   Show the :abbr:`FDB (Forwarding Database)` for the specified bridge.

   .. code-block:: none

     vyos@vyos:~$ show bridge br0 fdb
     50:00:00:08:00:01 dev eth1 vlan 20 master br0 permanent
     50:00:00:08:00:01 dev eth1 vlan 10 master br0 permanent
     50:00:00:08:00:01 dev eth1 master br0 permanent
     33:33:00:00:00:01 dev eth1 self permanent
     33:33:00:00:00:02 dev eth1 self permanent
     01:00:5e:00:00:01 dev eth1 self permanent
     50:00:00:08:00:02 dev eth2 vlan 20 master br0 permanent
     50:00:00:08:00:02 dev eth2 vlan 10 master br0 permanent
     50:00:00:08:00:02 dev eth2 master br0 permanent
     33:33:00:00:00:01 dev eth2 self permanent
     33:33:00:00:00:02 dev eth2 self permanent
     01:00:5e:00:00:01 dev eth2 self permanent
     33:33:00:00:00:01 dev br0 self permanent
     33:33:00:00:00:02 dev br0 self permanent
     33:33:ff:08:00:01 dev br0 self permanent
     01:00:5e:00:00:6a dev br0 self permanent
     33:33:00:00:00:6a dev br0 self permanent
     01:00:5e:00:00:01 dev br0 self permanent
     33:33:ff:00:00:00 dev br0 self permanent

.. opcmd:: show bridge <name> mdb

   Show the :abbr:`MDB (Multicast group Database)` for the specified bridge.

   The :abbr:`MDB (Multicast group Database)` is populated by :abbr:`IGMP 
   (Internet Group Management Protocol)`/:abbr:`MLD (Multicast Listener 
   Discovery)` snooping and lists the multicast groups currently active on the 
   bridge. 

   .. code-block:: none

     vyos@vyos:~$ show bridge br0 mdb
     dev br0 port br0 grp ff02::1:ff00:0 temp vid 1
     dev br0 port br0 grp ff02::2 temp vid 1
     dev br0 port br0 grp ff02::1:ff08:1 temp vid 1
     dev br0 port br0 grp ff02::6a temp vid 1

.. opcmd:: show bridge <name> macs

   Show the learned :abbr:`MAC (Media Access Control)` address table for the 
   specified bridge.

   .. code-block:: none

     vyos@vyos:~$ show bridge br100 macs
     port no mac addr                is local?       ageing timer
       1     00:53:29:44:3b:19       yes                0.00
