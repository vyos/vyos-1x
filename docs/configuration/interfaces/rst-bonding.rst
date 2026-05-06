:lastproofread: 2025-12-09

.. _bond-interface:

#######################
Bond / link aggregation
#######################

A **bonding interface** aggregates multiple network interfaces into a single 
logical interface (referred to as a bond, :abbr:`LAG (Link Aggregation Group)`, 
EtherChannel, or port-channel).

The behavior of a bonding interface depends on the selected mode. Modes provide 
either fault tolerance or a combination of load balancing and fault tolerance. 
Additionally, the bonding interface can be configured for link integrity 
monitoring.


*************
Configuration
*************

Common interface configuration
==============================

.. cmdinclude:: /_include/interface-common-with-dhcp.txt
   :var0: bonding
   :var1: bond0

Member interfaces
=================

.. cfgcmd:: set interfaces bonding <interface> member interface <member>

  **Add an interface to the bonding group.**

  **Example:**

  To configure eth0 and eth1 as members of the bonding interface bond0, execute 
  the following commands:

.. code-block:: none

   set interfaces bonding bond0 member interface eth0
   set interfaces bonding bond0 member interface eth1

Bond modes
============

.. cfgcmd:: set interfaces bonding <interface> mode <802.3ad | active-backup |
  broadcast | round-robin | transmit-load-balance | adaptive-load-balance |
  xor-hash>

   **Configure the bonding mode on the interface. The default mode is** 
   ``802.3ad``.

   The available modes are:

   * ``802.3ad`` 
  
   .. list-table::
      :widths: 20 80

      * - **Description:**
        - IEEE 802.3ad Dynamic Link Aggregation. Groups only member
          interfaces with the same speed (e.g., 1 Gbps) and duplex
          settings. Member interfaces with different speed and duplex
          settings are not included in the active bond.

          Provides load balancing and fault tolerance. Uses the
          :abbr:`LACP (Link Aggregation Control Protocol)` to
          negotiate the bond with the switch.
      * - **Traffic distribution:**
        - Traffic is distributed according to the **transmit hash
          policy** (default: XOR).

          The bonding driver applies an XOR operation to specific
          packet header fields, generating a hash value that maps to
          a particular member interface. This ensures the same network
          flow is consistently transmitted over the same member
          interface.
        
          The transmit hash policy is configured via the ``hash-policy`` option.
      * - **Failover:**
        - If a member interface fails, the hash is recalculated to distribute 
          traffic among the remaining active member interfaces.

   .. note:: Not all transmit hash policies comply with 802.3ad, particularly
      section 43.2.4. Using a non-compliant policy may result in out-of-order
      packet delivery.

   * ``active-backup`` 

   .. list-table::
      :widths: 20 80
 
      * - **Description:**
        - Provides fault tolerance. Only one member interface is active
          at a time. Other member interfaces remain in a standby mode.
      * - **Traffic distribution:**
        - All traffic (incoming and outgoing) is routed via one active
          member interface.
      * - **Failover:**
        - If the designated member interface fails, all traffic is
          routed to another member interface. The bonding driver sends
          a Gratuitous ARP to update the peer's MAC address table,
          linking the bond's MAC address to another physical port.

   * ``broadcast``

   .. list-table::
      :widths: 20 80
 
      * - **Description:**
        - Provides maximum fault tolerance by duplicating traffic.
      * - **Traffic distribution:**
        - Every packet is duplicated and transmitted on **all** member
          interfaces.
      * - **Failover:**
        - Traffic flow is not interrupted as long as at least one
          member interface remains active.

   * ``round-robin``   

   .. list-table::
      :widths: 20 80
 
      * - **Description:**
        - Provides load balancing and fault tolerance.
      * - **Traffic distribution:**
        - Packets are transmitted in sequential order across the member
          interfaces (e.g., packet 1 > interface A, packet 2 >
          interface B, etc.).
      * - **Failover:**
        - If a member interface fails, the sequence skips the failed
          interface and continues with the remaining active members.

   * ``transmit-load-balance``   

   .. list-table::
      :widths: 20 80
 
      * - **Description:**
        - Provides adaptive transmit load balancing and fault tolerance.
      * - **Traffic distribution:**
        - **Outgoing:** Distributed across all active member interfaces
          based on the current load.

          **Incoming:** Received by a designated member interface
          (active receiver).
      * - **Failover:**
        - If the active receiver fails, another member interface takes
          over as the new active receiver.

   * ``adaptive-load-balance``

   .. list-table::
      :widths: 20 80

      * - **Description:**
        - Provides adaptive transmit load balancing identical to
          ``transmit-load-balance``, receive load balancing for IPv4
          traffic, and fault tolerance for both incoming and outgoing
          traffic.
      * - **Traffic distribution:**
        - **Outgoing:** Identical to ``transmit-load-balance``.

          **Incoming:** Distributed based on ARP manipulation. For
          both local and remote connections, the bonding driver
          intercepts ARP traffic and changes the source MAC address
          to the MAC address of the least loaded member interface.

          All traffic from that peer is then routed to the chosen
          member interface.
      * - **Failover:**
        - If a member interface's state changes (fails, recovers, is
          added, or excluded), the traffic is redistributed among all
          active member interfaces.

   * ``xor-hash``: Provides load balancing and fault tolerance
     based on a hash formula. Distributes traffic and handles
     failover identically to ``802.3ad``, but operates without
     the :abbr:`LACP (Link Aggregation Control Protocol)`.

.. cfgcmd:: set interfaces bonding <interface> min-links <0-16>

   **Configure how many member interfaces must be active (in the
   link-up state) to mark the bonding interface UP (carrier
   asserted).**

   This command applies only when the bonding interface is configured
   in 802.3ad mode and functions like the Cisco EtherChannel min-links
   feature. It ensures that a bonding interface is marked UP (carrier
   asserted) only when a specified number of member interfaces are
   active (in the link-up state). This helps guarantee a minimum level
   of bandwidth for higher-level services (such as clustering) relying
   on the bonding interface.

   The default value is 0. This marks the bonding interface UP
   (carrier asserted) whenever an active LACP aggregator exists,
   regardless of the number of member interfaces in that aggregator.

   .. note:: In 802.3ad mode, a bond cannot be active without at
      least one active member interface. Therefore, setting min-links
      to 0 or 1 has the same result: the bonding interface is marked
      UP (carrier asserted).

.. cfgcmd:: set interfaces bonding <interface> lacp-rate <slow|fast>

   **Configure the rate at which the bonding interface requests its
   link partner to send**
   :abbr:`LACPDUs (Link Aggregation Control Protocol Data Units)`
   **in 802.3ad mode.**

   This command applies only when the bonding interface is configured
   in 802.3ad mode.

   The following options are available:

   * **slow (default):** Requests the link partner to transmit
     LACPDUs every 30 seconds.

   * **fast:** Requests the link partner to transmit LACPDUs every
     1 second.


.. cfgcmd:: set interfaces bonding <interface> system-mac <mac address>

   **Configure a specific MAC address for the bonding interface.**

   This sets the 802.3ad system MAC address, which is used for
   :abbr:`LACPDU (Link Aggregation Control Protocol Data Unit)`
   exchanges with the link partner. You can assign a fixed MAC address
   or generate a random one for these
   :abbr:`LACPDU (Link Aggregation Control Protocol Data Unit)`
   exchanges.


.. cfgcmd:: set interfaces bonding <interface> hash-policy <policy>

   **Configure which transmit hash policy to use for distributing
   traffic across member interfaces.**

   The following policies are available:

   * ``layer2``

     .. list-table::
        :widths: 20 80

        * - **Description:**
          - Routes all traffic destined for a specific network peer
            through the same member interface. The policy is
            802.3ad-compliant.
        * - **Hash inputs:**
          - Source MAC address, destination MAC address, and Ethernet
            packet type ID.
        * - **Formula:**
          - .. code-block:: none

               hash = source MAC address XOR destination MAC address XOR packet type ID
               member interface number = hash modulo member interface count

   * ``layer2+3``

     .. list-table::
        :widths: 20 80

        * - **Description:**
          - Similar to ``layer2``, routes all traffic destined for a
            specific network peer through the same member interface
            and is IEEE 802.3ad-compliant. Uses both Layer 2 and
            Layer 3 information to provide a more balanced traffic
            distribution.
        * - **Hash inputs:**
          - * Source MAC address, destination MAC address, and
              Ethernet packet type ID.
            * Source IP address, destination IP address. IPv6
              addresses are first hashed using ``IPv6_addr_hash``.
        * - **Formula:**
          - .. code-block:: none

               hash = source MAC address XOR destination MAC address XOR packet type ID
               hash = hash XOR source IP address XOR destination IP address
               hash = hash XOR (hash RSHIFT 16)
               hash = hash XOR (hash RSHIFT 8)
               member interface number = hash modulo member interface count
         
            For non-IP traffic, the formula is the same as for ``layer2``.

   * ``layer3+4``

     .. list-table::
        :widths: 20 80

        * - **Description:**
          - Routes different connections (flows) destined for a
            specific network peer through multiple member interfaces,
            but ensures each individual flow is routed through only
            one member interface.

            .. note:: This policy is not fully 802.3ad-compliant.
               When a single TCP or UDP flow contains both fragmented
               and unfragmented packets, the algorithm may distribute
               them across different member interfaces. This may
               result in out-of-order packet delivery, violating the
               802.3ad standard.
        * - **Hash inputs:**
          - * Source port, destination port (if available).
            * Source IP address, destination IP address. IPv6
              addresses are first hashed using ``IPv6_addr_hash``.
        * - **Formula:**
          - .. code-block:: none

               hash = source port, destination port (as in the header)
               hash = hash XOR source IP address XOR destination IP address
               hash = hash XOR (hash RSHIFT 16)
               hash = hash XOR (hash RSHIFT 8)
               member interface number = hash modulo member interface count

            For fragmented TCP or UDP packets and all other IPv4 and
            IPv6 traffic, the source and destination port information
            is omitted.

            For non-IP traffic, the formula is the same as for ``layer2``.
 
.. cfgcmd:: set interfaces bonding <interface> primary <interface>

   **Configure the primary member interface in the bond.**

   The primary member interface remains active as long as it is
   operational; alternative member interfaces are used only if it
   fails.

   Use this configuration when a specific member interface is
   preferred, such as one with higher throughput.

   This command applies only to ``active-backup``,
   ``transmit-load-balance``, and ``adaptive-load-balance`` modes.

.. cfgcmd:: set interfaces bonding <interface> arp-monitor interval <time>

   **Configure the ARP monitoring interval, in seconds, for the
   bonding interface.**

   ARP monitoring periodically assesses the health of each member
   interface by checking whether it has recently sent or received
   traffic (this criterion varies depending on the bonding mode and
   the member interface’s state). ARP probes are sent to the IP
   addresses specified with the arp-monitor target option.

   When ARP monitoring is used with EtherChannel-compatible modes
   (such as ``round-robin`` or ``xor-hash``), the switch should be
   configured to distribute traffic across all member interfaces. If
   the switch distributes traffic using an XOR-based policy, all ARP
   replies will be received on one member interface, causing other
   member interfaces to be incorrectly marked as failed.

   Setting this value to 0 disables ARP monitoring.

   The default value is 0.

.. cfgcmd:: set interfaces bonding <interface> arp-monitor target <address>

   **Configure the IP addresses for ARP monitoring requests.**

   The bonding driver sends ARP requests to these IP addresses to
   check the state of member interfaces.

   To enable ARP monitoring, configure at least one IP address (up to
   16 per bonding interface).

   By default, no IP addresses are configured.

:abbr:`VLAN (Virtual Local Area Network)`
=========================================

.. cmdinclude:: /_include/interface-vlan-8021q.txt
   :var0: bonding
   :var1: bond0

SPAN port mirroring
===================

.. cmdinclude:: ../../_include/interface-mirror.txt
   :var0: bonding
   :var1: bond1
   :var2: eth3

EVPN multihoming
----------------

EVPN multihoming (EVPN-MH) is a standards-based solution (RFC 7432, RFC 8365) 
that enables Customer Edge (CE) devices, such as servers, to connect to two 
or more Provider Edge (PE) devices for redundancy and load balancing. 

EVPN-MH is often used as a modern, standards-based alternative to 
:abbr:`MLAG (Multi-Chassis Link Aggregation)` and :abbr:`VTEPs (Virtual 
Tunnel Endpoints)`. 

**Ethernet Segment (ES) and Ethernet Segment Identifier (ESI)**

Physical links that connect a CE device to PE devices are bundled using link 
aggregation. This logical bundle is called an Ethernet Segment (ES) and is 
uniquely identified by an Ethernet Segment Identifier (ESI) within the 
EVPN domain.

To enable EVPN-MH, configure the same ESI on the bonding interfaces of all 
PE devices connected to a single CE device.

An ESI is configured by specifying either a system MAC address and a local 
discriminator, or an Ethernet Segment Identifier Name (ESINAME).

The following two commands generate a 10-byte Type-3 ESI by combining the 
system MAC and local discriminator: 

.. stop_vyoslinter

.. cfgcmd:: set interfaces bonding <interface> evpn es-id <1-16777215|10-byte ID>
.. cfgcmd:: set interfaces bonding <interface> evpn es-sys-mac <xx:xx:xx:xx:xx:xx>

  Alternatively, assign an ESINAME directly as a 10-byte Type-0 ESI
  using the following format: 00:AA:BB:CC:DD:EE:FF:GG:HH:II.

  **BGP-EVPN route usage**

  EVPN-MH uses BGP-EVPN route types 1 and 2 for ES discovery and
  MAC-IP synchronization:

  * **Type 1 (EAD-per-ES and EAD-per-EVI)** routes advertise the
    locally attached ESs and discover remote ESs in the network.
  * **Type 2 (MAC-IP advertisement)** routes are advertised with a
    destination ESI, enabling MAC-IP synchronization between ES peers.

.. stop_vyoslinter

.. cfgcmd:: set interfaces bonding <interface> evpn es-df-pref <1-65535>

  **Configure the** :abbr:`DF (Designated Forwarder)` **preference (1-65535) for
  the interface. A higher value indicates a higher preference to become the**
  :abbr:`DF (Designated Forwarder)`. **The** :abbr:`DF (Designated Forwarder)`
  **preference is configured per-ES.**

  The DF election process determines which interface in a specific ES forwards
  :abbr:`BUM (Broadcast, Unknown Unicast, and Multicast)` traffic from the EVPN
  overlay to the connected CE device. EVPN Type-4 (Ethernet Segment) routes are
  used to elect the DF, implementing the preference-based election method defined
  in RFC 9785.

  Interfaces not elected as the DF drop any BUM traffic from the EVPN overlay
  using non-DF filters. Similarly, traffic received from ES peers via the EVPN
  overlay is blocked from forwarding to the CE device to maintain split-horizon
  filtering with local bias.

.. start_vyoslinter

.. cmdinclude:: /_include/interface-evpn-uplink.txt
   :var0: bonding
   :var1: bond0

*******
Example
*******

The following configuration example applies to all listed third-party vendors. 
It creates a bonding interface with two member interfaces, defines VLANs 10 
and 100 on the bonding interface, and assigns an IPv4 address to each VLAN 
subinterface.

.. code-block:: none

  # Create the bonding interface bond0 with 802.3ad LACP
  set interfaces bonding bond0 hash-policy 'layer2'
  set interfaces bonding bond0 mode '802.3ad'

  # Add the required VLANs and IPv4 addresses on them
  set interfaces bonding bond0 vif 10 address 192.168.0.1/24
  set interfaces bonding bond0 vif 100 address 10.10.10.1/24

  # Add the member interfaces to the bonding interface
  set interfaces bonding bond0 member interface eth1
  set interfaces bonding bond0 member interface eth2

.. note:: If you are running this configuration in a virtual environment like
   EVE-NG, ensure the e1000 driver is chosen for your VyOS NIC. The default
   drivers, such as ``virtio-net-pci`` or ``vmxnet3``, are incompatible with
   this configuration. Specifically, ICMP messages will not be processed
   correctly.

   To check your NIC driver, use the following command:
   :opcmd:`show interfaces ethernet eth0 physical | grep -i driver`

Cisco Catalyst configuration
============================

Configure a Cisco Catalyst switch to integrate with a two-member VyOS bonding 
interface.

Assign member interfaces to PortChannel:

.. code-block:: none

  interface GigabitEthernet1/0/23
   description VyOS eth1
   channel-group 1 mode active
  !
  interface GigabitEthernet1/0/24
   description VyOS eth2
   channel-group 1 mode active
  !

A new interface, ``Port-channel1``, becomes available; all configuration, 
such as allowed VLAN interfaces and STP, is applied here.

.. code-block:: none

  interface Port-channel1
   description LACP Channel for VyOS
   switchport trunk encapsulation dot1q
   switchport trunk allowed vlan 10,100
   switchport mode trunk
   spanning-tree portfast trunk
  !


Juniper EX Switch configuration
===============================

Configure a Juniper EX Series switch to integrate with a two-member VyOS
bonding interface.

.. code-block:: none

  # Create aggregated ethernet device with 802.3ad LACP and port speeds of 10gbit/s
  set interfaces ae0 aggregated-ether-options link-speed 10g
  set interfaces ae0 aggregated-ether-options lacp active

  # Create layer 2 on the aggregated ethernet device with trunking for our VLANs
  set interfaces ae0 unit 0 family ethernet-switching port-mode trunk

  # Add the required vlans to the device
  set interfaces ae0 unit 0 family ethernet-switching vlan members 10
  set interfaces ae0 unit 0 family ethernet-switching vlan members 100

  # Add the two interfaces to the aggregated ethernet device, in this setup both
  # ports are on the same switch (switch 0, module 1, port 0 and 1)
  set interfaces xe-0/1/0 ether-options 802.3ad ae0
  set interfaces xe-0/1/1 ether-options 802.3ad ae0

  # But this can also be done with multiple switches in a stack, a virtual
  # chassis on Juniper (switch 0 and switch 1, module 1, port 0 on both switches)
  set interfaces xe-0/1/0 ether-options 802.3ad ae0
  set interfaces xe-1/1/0 ether-options 802.3ad ae0

Aruba/HP configuration
======================

Configure an Aruba/HP 2510G switch to integrate with a two-member VyOS bonding 
interface.

.. code-block:: none

  # Create trunk with 2 member interfaces (interface 1 and 2) and LACP
  trunk 1-2 Trk1 LACP

  # Add the required VLANs to the trunk
  vlan 10 tagged Trk1
  vlan 100 tagged Trk1

Arista EOS configuration
========================

When deploying VyOS in environments with Arista switches, use the following 
blueprint as an initial setup to configure an operational LACP port-channel 
between the two devices.

Let's assume the following topology:

.. figure:: /_static/images/vyos_arista_bond_lacp.*
   :alt: VyOS Arista EOS setup

**R1**

  .. code-block:: none

     interfaces {
         bonding bond10 {
             hash-policy layer3+4
             member {
                 interface eth1
                 interface eth2
             }
             mode 802.3ad
             vif 100 {
                 address 192.0.2.1/30
                 address 2001:db8::1/64
             }
         }

**R2**

  .. code-block:: none

     interfaces {
         bonding bond10 {
             hash-policy layer3+4
             member {
                 interface eth1
                 interface eth2
             }
             mode 802.3ad
             vif 100 {
                 address 192.0.2.2/30
                 address 2001:db8::2/64
             }
         }

**SW1**

  .. code-block:: none

     !
     vlan 100
        name FOO
     !
     interface Port-Channel10
        switchport trunk allowed vlan 100
        switchport mode trunk
        spanning-tree portfast
     !
     interface Port-Channel20
        switchport mode trunk
        no spanning-tree portfast auto
        spanning-tree portfast network
     !
     interface Ethernet1
        channel-group 10 mode active
     !
     interface Ethernet2
        channel-group 10 mode active
     !
     interface Ethernet3
        channel-group 20 mode active
     !
     interface Ethernet4
        channel-group 20 mode active
     !

**SW2**

  .. code-block:: none

     !
     vlan 100
        name FOO
     !
     interface Port-Channel10
        switchport trunk allowed vlan 100
        switchport mode trunk
        spanning-tree portfast
     !
     interface Port-Channel20
        switchport mode trunk
        no spanning-tree portfast auto
        spanning-tree portfast network
     !
     interface Ethernet1
        channel-group 10 mode active
     !
     interface Ethernet2
        channel-group 10 mode active
     !
     interface Ethernet3
        channel-group 20 mode active
     !
     interface Ethernet4
        channel-group 20 mode active
     !

.. note:: When testing this environment in EVE-NG, ensure the e1000 driver 
   is chosen for your VyOS network interfaces. If the default virtio driver 
   is used, VyOS will not transmit LACP PDUs, preventing the port-channel 
   from ever becoming active.

*********
Operation
*********

.. opcmd:: show interfaces bonding

   Show brief interface information.

   .. code-block:: none

     vyos@vyos:~$ show interfaces bonding
     Codes: S - State, L - Link, u - Up, D - Down, A - Admin Down
     Interface        IP Address                        S/L  Description
     ---------        ----------                        ---  -----------
     bond0            -                                 u/u  my-sw1 int 23 and 24
     bond0.10         192.168.0.1/24                    u/u  office-net
     bond0.100        10.10.10.1/24                     u/u  management-net


.. opcmd:: show interfaces bonding <interface>

   Show detailed interface information.

   .. code-block:: none

     vyos@vyos:~$ show interfaces bonding bond5
     bond5: <NO-CARRIER,BROADCAST,MULTICAST,MASTER,UP> mtu 1500 qdisc noqueue state DOWN group default qlen 1000
         link/ether 00:50:56:bf:ef:aa brd ff:ff:ff:ff:ff:ff
         inet6 fe80::e862:26ff:fe72:2dac/64 scope link tentative
            valid_lft forever preferred_lft forever

         RX:  bytes  packets  errors  dropped  overrun       mcast
                  0        0       0        0        0           0
         TX:  bytes  packets  errors  dropped  carrier  collisions
                  0        0       0        0        0           0

.. opcmd:: show interfaces bonding <interface> detail

   Show detailed information about the underlying physical links on the given 
   bonding interface.

   .. code-block:: none

     vyos@vyos:~$ show interfaces bonding bond5 detail
     Ethernet Channel Bonding Driver: v3.7.1 (April 27, 2011)

     Bonding Mode: IEEE 802.3ad Dynamic link aggregation
     Transmit Hash Policy: layer2 (0)
     MII Status: down
     MII Polling Interval (ms): 100
     Up Delay (ms): 0
     Down Delay (ms): 0

     802.3ad info
     LACP rate: slow
     Min links: 0
     Aggregator selection policy (ad_select): stable

     Slave Interface: eth1
     MII Status: down
     Speed: Unknown
     Duplex: Unknown
     Link Failure Count: 0
     Permanent HW addr: 00:50:56:bf:ef:aa
     Slave queue ID: 0
     Aggregator ID: 1
     Actor Churn State: churned
     Partner Churn State: churned
     Actor Churned Count: 1
     Partner Churned Count: 1

     Slave Interface: eth2
     MII Status: down
     Speed: Unknown
     Duplex: Unknown
     Link Failure Count: 0
     Permanent HW addr: 00:50:56:bf:19:26
     Slave queue ID: 0
     Aggregator ID: 2
     Actor Churn State: churned
     Partner Churn State: churned
     Actor Churned Count: 1
     Partner Churned Count: 1
