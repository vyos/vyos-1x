:lastproofread: 2026-03-16

.. _vxlan-interface:

#####
VXLAN
#####

:abbr:`VXLAN (Virtual Extensible LAN)` is a network virtualization technology 
that addresses scalability challenges in large cloud computing environments. 
It encapsulates Ethernet frames (Layer 2) within UDP datagrams (Layer 4), which 
are then transmitted via UDP port 4789, as assigned by IANA. VXLAN endpoints, 
called :abbr:`VTEPs (VXLAN tunnel endpoints)`, terminate VXLAN tunnels and can 
be either virtual or physical switch ports.

VXLAN supports up to 16 million logical networks and enables Layer 2 adjacency 
across Layer 3 IP networks. It uses multicast or unicast with head-end 
replication (HER) to flood broadcast, unknown unicast, and multicast (BUM) 
traffic.

The VXLAN specification was initially developed by VMware, Arista Networks, and 
Cisco. Other supporters include Huawei, Broadcom, Citrix, Pica8, Big Switch 
Networks, Cumulus Networks, Dell EMC, Ericsson, Mellanox, FreeBSD, OpenBSD, Red 
Hat, Joyent, and Juniper Networks.

VXLAN is officially documented by the IETF in :rfc:`7348`.

When configuring VXLAN in a VyOS virtual machine, ensure that MAC spoofing 
(Hyper-V) or Forged Transmits (ESX) are permitted. Otherwise, the hypervisor 
may block forwarded frames.

.. note:: Although the IANA-assigned VXLAN port is **4789**, VyOS uses the 
   Linux default UDP port **8472** for VXLAN interfaces. To ensure compatibility 
   with other vendors, set the port to the IANA standard **4789**.

Configuration
=============

Common interface configuration
------------------------------

.. cmdinclude:: /_include/interface-common-without-dhcp.txt
  :var0: vxlan
  :var1: vxlan0

VXLAN-specific options
-----------------------

.. cfgcmd:: set interfaces vxlan <interface> vni <number>

  **Configure a** :abbr:`VNI (VXLAN Network Identifier)` **for the VXLAN 
  interface.**

  Each VXLAN segment is identified by this 24-bit VNI, allowing up to 16 million 
  segments to coexist within the same administrative domain.

.. cfgcmd:: set interfaces vxlan <interface> port <port>

  Configure the UDP port of the remote VXLAN endpoint.

  .. note:: Although the IANA-assigned VXLAN port is **4789**, VyOS uses the 
     Linux default UDP port **8472** for VXLAN interfaces.

.. cfgcmd:: set interfaces vxlan <interface> source-address <address>

  Configure the source IP address for the VXLAN underlay. 

  .. warning:: This setting is mandatory when deploying VXLAN via L2VPN/EVPN.

.. cfgcmd:: set interfaces vxlan <interface> gpe

   **Enable the** :abbr:`GPE (Generic Protocol Extension)` **for the VXLAN 
   interface.**

   To use this feature, you must configure the interface with the ``external`` 
   parameter.

.. cfgcmd:: set interfaces vxlan <interface> parameters external

   **Configure the VXLAN interface to use an external control plane, such as BGP 
   L2VPN/EVPN, for remote endpoint discovery.**

   If not configured, the internal :abbr:`FDB (Forwarding Database)` is used.

.. cfgcmd:: set interfaces vxlan <interface> parameters neighbor-suppress

   **Enable ARP and ND suppression on the VXLAN interface.**

   This reduces ARP and ND message flooding across the VXLAN network. As defined 
   in :rfc:`7432#section-10`, participating VTEPs use known MAC-to-IP bindings 
   to reply to local requests on behalf of remote hosts.  

.. cfgcmd:: set interfaces vxlan <interface> parameters nolearning

   Disable :abbr:`SLLA (Source Link-Layer Address)` and IP address learning on 
   the VXLAN interface. 

.. cfgcmd:: set interfaces vxlan <interface> parameters vni-filter

   **Enable** :abbr:`VNI (VXLAN Network Identifier)` **filtering on the VXLAN 
   interface.** 

   When enabled, the interface only receives packets with VNIs configured in its 
   VNI filtering table.

   .. note:: VNI filtering works only if the interface is configured with the 
      ``external`` parameter.

Unicast
^^^^^^^

.. cfgcmd:: set interfaces vxlan <interface> remote <address>

   **Configure the IPv4 or IPv6 address of the remote VTEP.**

   Unlike multicast setups, this command allows you to directly configure the 
   remote IPv4 or IPv6 address.

Multicast
^^^^^^^^^

.. cfgcmd:: set interfaces vxlan <interface> source-interface <interface>

  **Configure the source interface for the VXLAN underlay.**

  All VXLAN traffic is sent and received through the specified interface. 

  This setting is mandatory when deploying VXLAN over a multicast network.
  
.. cfgcmd:: set interfaces vxlan <interface> group <address>

  **Configure the IPv4 or IPv6 multicast group address for the VXLAN interface.**

  VXLAN tunnels can be built using either multicast group or unicast IP addresses.

Multicast VXLAN
===============

Topology: PC4 - Leaf2 - Spine1 - Leaf3 - PC5

PC4 uses the IP address ``10.0.0.4/24``, and PC5 uses the IP address 
``10.0.0.5/24``. Both devices assume they reside within the same broadcast 
domain.

Assume PC4 on Leaf2 pings PC5 on Leaf3. Rather than manually specifying Leaf3 
as the remote endpoint, Leaf2 encapsulates the packet into a UDP datagram and 
sends it to the designated multicast address via Spine1. Spine1 forwards the 
packet to all leaves in the same multicast group, including Leaf3. Upon 
receiving the datagram, Leaf3 forwards it to PC5 and learns that PC4 is 
reachable through Leaf2 by inspecting the source IP in the encapsulated 
datagram.

PC5 receives the ping and responds with an echo reply. Leaf3, now aware of 
PC4's location, forwards the reply directly to Leaf2's unicast address. Upon 
receiving the echo reply, Leaf2 learns that PC5 is reachable through Leaf3.

After this discovery, subsequent traffic between PC4 and PC5 will not use the 
multicast address between the leaves, as both leaves have learned the PCs' 
locations. This reduces multicast traffic and network load, improving 
scalability as more leaves are added.

Single VXLAN device (SVD)
=========================

In VyOS, you can configure multiple **VLAN-to-VNI mappings** for EVPN-VXLAN on 
a single container interface, known as a single VXLAN device (SVD). This 
enables significant VNI scaling because a separate VXLAN interface is not 
required for each VNI.

.. cfgcmd:: set interfaces vxlan <interface> vlan-to-vni <vlan> vni <vni>

   **Map a VLAN ID to a VNI on the specified VXLAN interface.**

   The VXLAN interface can be added to a bridge.

   The following example shows an SVD configuration with multiple VLAN-to-VNI 
   mappings.

   .. code-block:: none

    set interfaces bridge br0 member interface vxlan0
    set interfaces vxlan vxlan0 parameters external
    set interfaces vxlan vxlan0 source-interface 'dum0'
    set interfaces vxlan vxlan0 vlan-to-vni 10 vni '10010'
    set interfaces vxlan vxlan0 vlan-to-vni 11 vni '10011'
    set interfaces vxlan vxlan0 vlan-to-vni 30 vni '10030'
    set interfaces vxlan vxlan0 vlan-to-vni 31 vni '10031'

Example
-------

The following example demonstrates a multicast VXLAN deployment.

The setup includes three routers: Spine1, a Cisco IOS router, and Leaf2 and 
Leaf3, which are VyOS routers.

**Topology:**  Leaf2 - Spine1 - Leaf3.

The topology is built using GNS3.

.. code-block:: none

  Spine1:
  fa0/2 towards Leaf2, IP-address: 10.1.2.1/24
  fa0/3 towards Leaf3, IP-address: 10.1.3.1/24

  Leaf2:
  Eth0 towards Spine1, IP-address: 10.1.2.2/24
  Eth1 towards a VLAN-aware switch

  Leaf3:
  Eth0 towards Spine1, IP-address 10.1.3.3/24
  Eth1 towards a VLAN-aware switch

**Spine1 configuration:**

.. code-block:: none

  conf t
  ip multicast-routing
  !
  interface fastethernet0/2
   ip address 10.1.2.1 255.255.255.0
   ip pim sparse-dense-mode
  !
  interface fastethernet0/3
   ip address 10.1.3.1 255.255.255.0
   ip pim sparse-dense-mode
  !
  router ospf 1
   network 10.0.0.0 0.255.255.255 area 0

Multicast routing is required for scalable traffic forwarding between leaves. 
:abbr:`PIM (Protocol Independent Multicast)` must be enabled towards the leaves 
so the spine can learn from which multicast groups each leaf expects traffic.

**Leaf2 configuration:**

.. code-block:: none

  set interfaces ethernet eth0 address '10.1.2.2/24'
  set protocols ospf area 0 network '10.0.0.0/8'

  ! First VXLAN interface
  set interfaces bridge br241 address '172.16.241.1/24'
  set interfaces bridge br241 member interface 'eth1.241'
  set interfaces bridge br241 member interface 'vxlan241'

  set interfaces vxlan vxlan241 group '239.0.0.241'
  set interfaces vxlan vxlan241 source-interface 'eth0'
  set interfaces vxlan vxlan241 vni '241'

  ! Second VXLAN interface
  set interfaces bridge br242 address '172.16.242.1/24'
  set interfaces bridge br242 member interface 'eth1.242'
  set interfaces bridge br242 member interface 'vxlan242'

  set interfaces vxlan vxlan242 group '239.0.0.242'
  set interfaces vxlan vxlan242 source-interface 'eth0'
  set interfaces vxlan vxlan242 vni '242'

**Leaf3 configuration:**

.. code-block:: none

  set interfaces ethernet eth0 address '10.1.3.3/24'
  set protocols ospf area 0 network '10.0.0.0/8'

  ! First VXLAN interface
  set interfaces bridge br241 address '172.16.241.1/24'
  set interfaces bridge br241 member interface 'eth1.241'
  set interfaces bridge br241 member interface 'vxlan241'

  set interfaces vxlan vxlan241 group '239.0.0.241'
  set interfaces vxlan vxlan241 source-interface 'eth0'
  set interfaces vxlan vxlan241 vni '241'

  ! Second VXLAN interface
  set interfaces bridge br242 address '172.16.242.1/24'
  set interfaces bridge br242 member interface 'eth1.242'
  set interfaces bridge br242 member interface 'vxlan242'

  set interfaces vxlan vxlan242 group '239.0.0.242'
  set interfaces vxlan vxlan242 source-interface 'eth0'
  set interfaces vxlan vxlan242 vni '242'

The configurations for Leaf2 and Leaf3 are nearly identical. Detailed 
explanations for each command are provided below.

.. code-block:: none

  set interfaces bridge br241 address '172.16.241.1/24'

This command creates a bridge to bind traffic on ``eth1`` VLAN 241 with the 
``vxlan241`` interface. The IP address is optional. If configured, it can serve 
as the default gateway for each leaf, allowing devices on the VLAN to reach 
other subnets. Subnets must be redistributed by :abbr:`OSPF (Open Shortest Path 
First)` so the spine can learn how to reach them. To advertise ``172.16/12`` 
networks, change the :abbr:`OSPF (Open Shortest Path First)` network from 
``10.0.0.0/8`` to ``0.0.0.0/0``.

.. code-block:: none

  set interfaces bridge br241 member interface 'eth1.241'
  set interfaces bridge br241 member interface 'vxlan241'

These commands bind ``eth1.241`` and ``vxlan241`` as member interfaces of the 
same bridge.

.. code-block:: none

  set interfaces vxlan vxlan241 group '239.0.0.241'

This command configures the multicast group used by all leaves for this VLAN 
extension. It must be the same on all leaves that have this interface.

.. code-block:: none

  set interfaces vxlan vxlan241 source-interface 'eth0'

This command configures the interface that listens for multicast packets. It 
can also be a loopback interface.

.. code-block:: none

  set interfaces vxlan vxlan241 vni '241'

This command configures the unique ID for the VXLAN interface. 

.. code-block:: none

  set interfaces vxlan vxlan241 port 12345

VyOS uses the Linux default UDP port **8472** for VXLAN interfaces. This 
command allows you to configure a different UDP port.

Unicast VXLAN
=============

As an alternative to multicast, you can configure the VXLAN tunnel by 
specifying the remote IPv4 address directly. The following updates the previous 
multicast example:

.. code-block:: none

  # leaf2 and leaf3
  delete interfaces vxlan vxlan241 group '239.0.0.241'
  delete interfaces vxlan vxlan241 source-interface 'eth0'

  # leaf2
  set interfaces vxlan vxlan241 remote 10.1.3.3

  # leaf3
  set interfaces vxlan vxlan241 remote 10.1.2.2

The default UDP port is 8472. To configure a different port, use ``set 
interfaces vxlan <vxlanN> port <port>``.

