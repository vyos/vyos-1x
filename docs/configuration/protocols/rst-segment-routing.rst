.. _segment-routing:

###############
Segment Routing
###############

Segment Routing (SR) is a network architecture that is similar to source-routing
. In this architecture, the ingress router adds a list of segments, known as 
SIDs, to the packet as it enters the network. These segments represent different 
portions of the network path that the packet will take.

The SR segments are portions of the network path taken by the packet, and are 
called SIDs. At each node, the first SID of the list is read, executed as a 
forwarding function, and may be popped to let the next node read the next SID of 
the list. The SID list completely determines the path where the packet is 
forwarded.

Segment Routing can be applied to an existing MPLS-based data plane and defines
a control plane network architecture. In MPLS networks, segments are encoded as
MPLS labels and are added at the ingress router. These MPLS labels are then 
exchanged and populated by Interior Gateway Protocols (IGPs) like IS-IS or OSPF 
which are running on most ISPs.


.. note:: Segment routing defines a control plane network architecture and
  can be applied to an existing MPLS based dataplane. In the MPLS networks,
  segments are encoded as MPLS labels and are imposed at the ingress router.
  MPLS labels are exchanged and populated by IGPs like IS-IS.Segment Routing
  as per RFC8667 for MPLS dataplane. It supports IPv4, IPv6 and ECMP and has
  been tested against Cisco & Juniper routers.however,this deployment is still
  EXPERIMENTAL for FRR.
 

IS-IS SR Configuration
----------------------

Segment routing (SR) is used by the IGP protocols to interconnect network
devices, below configuration shows how to enable SR on IS-IS:


.. note:: ``Known limitations:`` 

  No support for level redistribution (L1 to L2 or L2 to L1)

  No support for binding SID

  No support for SRLB

  Only one SRGB and default SPF Algorithm is supported



.. cfgcmd::  set protocols isis segment-routing global-block high-label-value 
  <label-value>

  Set the Segment Routing Global Block i.e. the label range used by MPLS to 
  store label in the MPLS FIB for Prefix SID. Note that the block size may 
  not exceed 65535.

.. cfgcmd:: set protocols isis segment-routing global-block low-label-value 
  <label-value>

  Set the Segment Routing Global Block i.e. the low label range used by MPLS to 
  store label in the MPLS FIB for Prefix SID. Note that the block size may 
  not exceed 65535.
 
.. cfgcmd:: set protocols isis segment-routing local-block high-label-value 
  <label-value>

  Set the Segment Routing Local Block i.e. the label range used by MPLS to 
  store label in the MPLS FIB for Prefix SID. Note that the block size may 
  not exceed 65535.Segment Routing Local Block, The negative command always 
  unsets both.

.. cfgcmd:: set protocols isis segment-routing local-block <low-label-value 
  <label-value>

  Set the Segment Routing Local Block i.e. the low label range used by MPLS to 
  store label in the MPLS FIB for Prefix SID. Note that the block size may 
  not exceed 65535.Segment Routing Local Block, The negative command always 
  unsets both.

.. cfgcmd:: set protocols isis segment-routing maximum-label-depth <1-16>

  Set the Maximum Stack Depth supported by the router. The value depend of
  the MPLS dataplane.

.. cfgcmd:: set protocols isis segment-routing prefix <address> index value 
  <0-65535>
   
  A segment ID that contains an IP address prefix calculated by an IGP in the
  service provider core network. Prefix SIDs are globally unique, this value
  indentify it 

.. cfgcmd:: set protocols isis segment-routing prefix <address> index
   <no-php-flag | explicit-null| n-flag-clear>

   this option allows to configure prefix-sid on SR. The ‘no-php-flag’ means NO 
   Penultimate Hop Popping that allows SR node to request to its neighbor to 
   not pop the label. The ‘explicit-null’ flag allows SR node to request to its 
   neighbor to send IP packet with the EXPLICIT-NULL label. The ‘n-flag-clear’ 
   option can be used to explicitly clear the Node flag that is set by default 
   for Prefix-SIDs associated to loopback addresses. This option is necessary 
   to configure Anycast-SIDs.


.. opcmd:: show isis segment-routing node
 
   Show detailed information about all learned Segment Routing Nodes

.. opcmd:: show isis route prefix-sid

   Show detailed information about prefix-sid and label learned

.. note:: more information related IGP  - :ref:`routing-isis`

   

OSPF SR  Configuration
----------------------

Segment routing (SR) is used by the IGP protocols to interconnect network
devices, below configuration shows how to enable SR on OSPF:

.. cfgcmd:: set protocols ospf parameters opaque-lsa

  Enable the Opaque-LSA capability (rfc2370), necessary to transport label 
  on IGP


.. cfgcmd:: set protocols ospf segment-routing global-block high-label-value 
  <label-value>

  Set the Segment Routing Global Block i.e. the label range used by MPLS to 
  store label in the MPLS FIB for Prefix SID. Note that the block size may 
  not exceed 65535.

.. cfgcmd:: set protocols ospf segment-routing global-block low-label-value 
  <label-value>

  Set the Segment Routing Global Block i.e. the low label range used by MPLS to 
  store label in the MPLS FIB for Prefix SID. Note that the block size may 
  not exceed 65535.

.. cfgcmd:: set protocols ospf segment-routing local-block high-label-value 
  <label-value>

  Set the Segment Routing Local Block i.e. the label range used by MPLS to 
  store label in the MPLS FIB for Prefix SID. Note that the block size may 
  not exceed 65535.Segment Routing Local Block, The negative command always 
  unsets both.

.. cfgcmd:: set protocols ospf segment-routing local-block <low-label-value 
  <label-value>

  Set the Segment Routing Local Block i.e. the low label range used by MPLS to 
  store label in the MPLS FIB for Prefix SID. Note that the block size may 
  not exceed 65535.Segment Routing Local Block, The negative command always 
  unsets both.

.. cfgcmd:: set protocols ospf segment-routing maximum-label-depth <1-16>

  Set the Maximum Stack Depth supported by the router. The value depend of
  the MPLS dataplane.

.. cfgcmd:: set protocols ospf segment-routing prefix <address> index value 
  <0-65535>
   
  A segment ID that contains an IP address prefix calculated by an IGP in the
  service provider core network. Prefix SIDs are globally unique, this value
  indentify it 

.. cfgcmd:: set protocols ospf segment-routing prefix <address> index
   <no-php-flag | explicit-null| n-flag-clear>

   this option allows to configure prefix-sid on SR. The ‘no-php-flag’ means NO 
   Penultimate Hop Popping that allows SR node to request to its neighbor to 
   not pop the label. The ‘explicit-null’ flag allows SR node to request to its 
   neighbor to send IP packet with the EXPLICIT-NULL label. The ‘n-flag-clear’ 
   option can be used to explicitly clear the Node flag that is set by default 
   for Prefix-SIDs associated to loopback addresses. This option is necessary 
   to configure Anycast-SIDs.

.. note:: more information related IGP  - :ref:`routing-ospf`

Configuration Example
---------------------

we described the configuration SR ISIS / SR OSPF using 2 connected with them to
share label information.

Enable IS-IS with Segment Routing (Experimental)
================================================

**Node 1:**

.. code-block:: none

  set interfaces loopback lo address '192.168.255.255/32'
  set interfaces ethernet eth1 address '192.0.2.1/24'

  set protocols isis interface eth1
  set protocols isis interface lo
  set protocols isis net '49.0001.1921.6825.5255.00'
  set protocols isis segment-routing global-block high-label-value '599'
  set protocols isis segment-routing global-block low-label-value '550'
  set protocols isis segment-routing prefix 192.168.255.255/32 index value '1'
  set protocols isis segment-routing prefix 192.168.255.255/32 index explicit-null
  set protocols mpls interface 'eth1'
  
**Node 2:**

.. code-block:: none

  set interfaces loopback lo address '192.168.255.254/32'
  set interfaces ethernet eth1 address '192.0.2.2/24'

  set protocols isis interface eth1
  set protocols isis interface lo
  set protocols isis net '49.0001.1921.6825.5254.00'
  set protocols isis segment-routing global-block high-label-value '599'
  set protocols isis segment-routing global-block low-label-value '550'
  set protocols isis segment-routing prefix 192.168.255.254/32 index value '2'
  set protocols isis segment-routing prefix 192.168.255.254/32 index explicit-null
  set protocols mpls interface 'eth1'
  
  
  
This gives us MPLS segment routing enabled and labels for far end loopbacks:

.. code-block:: none

  Node-1@vyos:~$ show mpls table
   Inbound Label  Type        Nexthop                Outbound Label
   ----------------------------------------------------------------------
   552            SR (IS-IS)  192.0.2.2              IPv4 Explicit Null <-- Node-2 loopback learned on Node-1
   15000          SR (IS-IS)  192.0.2.2              implicit-null
   15001          SR (IS-IS)  fe80::e87:6cff:fe09:1  implicit-null
   15002          SR (IS-IS)  192.0.2.2              implicit-null
   15003          SR (IS-IS)  fe80::e87:6cff:fe09:1  implicit-null

  Node-2@vyos:~$ show mpls table
   Inbound Label  Type        Nexthop               Outbound Label
   ---------------------------------------------------------------------
   551            SR (IS-IS)  192.0.2.1             IPv4 Explicit Null <-- Node-1 loopback learned on Node-2
   15000          SR (IS-IS)  192.0.2.1             implicit-null
   15001          SR (IS-IS)  fe80::e33:2ff:fe80:1  implicit-null
   15002          SR (IS-IS)  192.0.2.1             implicit-null
   15003          SR (IS-IS)  fe80::e33:2ff:fe80:1  implicit-null

Here is the routing tables showing the MPLS segment routing label operations:

.. code-block:: none

  Node-1@vyos:~$ show ip route isis
  Codes: K - kernel route, C - connected, S - static, R - RIP,
         O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
         T - Table, v - VNC, V - VNC-Direct, A - Babel, F - PBR,
         f - OpenFabric,
         > - selected route, * - FIB route, q - queued, r - rejected, b - backup
         t - trapped, o - offload failure

  I   192.0.2.0/24 [115/20] via 192.0.2.2, eth1 inactive, weight 1, 00:07:48
  I>* 192.168.255.254/32 [115/20] via 192.0.2.2, eth1, label IPv4 Explicit Null, weight 1, 00:03:39

  Node-2@vyos:~$ show ip route isis
  Codes: K - kernel route, C - connected, S - static, R - RIP,
         O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
         T - Table, v - VNC, V - VNC-Direct, A - Babel, F - PBR,
         f - OpenFabric,
         > - selected route, * - FIB route, q - queued, r - rejected, b - backup
         t - trapped, o - offload failure

  I   192.0.2.0/24 [115/20] via 192.0.2.1, eth1 inactive, weight 1, 00:07:46
  I>* 192.168.255.255/32 [115/20] via 192.0.2.1, eth1, label IPv4 Explicit Null, weight 1, 00:03:43


Enable OSPF with Segment Routing (Experimental):
================================================

**Node 1**

.. code-block:: none

  set interfaces loopback lo address 10.1.1.1/32
  set interfaces ethernet eth0 address 192.168.0.1/24
  set protocols ospf area 0 network '192.168.0.0/24'
  set protocols ospf area 0 network '10.1.1.1/32'
  set protocols ospf parameters opaque-lsa
  set protocols ospf parameters router-id '10.1.1.1'
  set protocols ospf segment-routing global-block high-label-value '1100'
  set protocols ospf segment-routing global-block low-label-value '1000'
  set protocols ospf segment-routing prefix 10.1.1.1/32 index explicit-null
  set protocols ospf segment-routing prefix 10.1.1.1/32 index value '1'

**Node 2**

.. code-block:: none

  set interfaces loopback lo address 10.1.1.2/32
  set interfaces ethernet eth0 address 192.168.0.2/24
  set protocols ospf area 0 network '192.168.0.0/24'
  set protocols ospf area 0 network '10.1.1.2/32'
  set protocols ospf parameters opaque-lsa
  set protocols ospf parameters router-id '10.1.1.2'
  set protocols ospf segment-routing global-block high-label-value '1100'
  set protocols ospf segment-routing global-block low-label-value '1000'
  set protocols ospf segment-routing prefix 10.1.1.2/32 index explicit-null
  set protocols ospf segment-routing prefix 10.1.1.2/32 index value '2'


This gives us MPLS segment routing enabled and labels for far end loopbacks:

.. code-block:: none

  Node-1@vyos:~$ show mpls table
   Inbound Label  Type       Nexthop      Outbound Label
   -----------------------------------------------------------
   1002           SR (OSPF)  192.168.0.2  IPv4 Explicit Null  <-- Node-2 loopback learned on Node-1
   15000          SR (OSPF)  192.168.0.2  implicit-null
   15001          SR (OSPF)  192.168.0.2  implicit-null

  Node-2@vyos:~$ show mpls table
   Inbound Label  Type       Nexthop      Outbound Label
   -----------------------------------------------------------
   1001           SR (OSPF)  192.168.0.1  IPv4 Explicit Null  <-- Node-1 loopback learned on Node-2
   15000          SR (OSPF)  192.168.0.1  implicit-null
   15001          SR (OSPF)  192.168.0.1  implicit-null

Here is the routing tables showing the MPLS segment routing label operations:

.. code-block:: none

  Node-1@vyos:~$ show ip route ospf
  Codes: K - kernel route, C - connected, S - static, R - RIP,
         O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
         T - Table, v - VNC, V - VNC-Direct, A - Babel, F - PBR,
         f - OpenFabric,
         > - selected route, * - FIB route, q - queued, r - rejected, b - backup
         t - trapped, o - offload failure

  O   10.1.1.1/32 [110/0] is directly connected, lo, weight 1, 00:03:43
  O>* 10.1.1.2/32 [110/1] via 192.168.0.2, eth0, label IPv4 Explicit Null, weight 1, 00:03:32
  O   192.168.0.0/24 [110/1] is directly connected, eth0, weight 1, 00:03:43

  Node-2@vyos:~$ show ip route ospf
  Codes: K - kernel route, C - connected, S - static, R - RIP,
         O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
         T - Table, v - VNC, V - VNC-Direct, A - Babel, F - PBR,
         f - OpenFabric,
         > - selected route, * - FIB route, q - queued, r - rejected, b - backup
         t - trapped, o - offload failure

  O>* 10.1.1.1/32 [110/1] via 192.168.0.1, eth0, label IPv4 Explicit Null, weight 1, 00:03:36
  O   10.1.1.2/32 [110/0] is directly connected, lo, weight 1, 00:03:51
  O   192.168.0.0/24 [110/1] is directly connected, eth0, weight 1, 00:03:51

