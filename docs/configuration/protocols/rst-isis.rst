.. include:: /_include/need_improvement.txt

.. _routing-isis:

#####
IS-IS
#####

:abbr:`IS-IS (Intermediate System to Intermediate System)` is a link-state
interior gateway protocol (IGP) which is described in ISO10589,
:rfc:`1195`, :rfc:`5308`. IS-IS runs the Dijkstra shortest-path first (SPF)
algorithm to create a database of the network’s topology, and
from that database to determine the best (that is, lowest cost) path to a
destination. The intermediate systems (the name for routers) exchange topology
information with their directly connected neighbors. IS-IS runs directly on
the data link layer (Layer 2). IS-IS addresses are called
:abbr:`NETs (Network Entity Titles)` and can be 8 to 20 bytes long, but are
generally 10 bytes long. The tree database that is created with IS-IS is
similar to the one that is created with OSPF in that the paths chosen should
be similar. Comparisons to OSPF are inevitable and often are reasonable ones
to make in regards to the way a network will respond with either IGP.

*******
General
*******

Configuration
=============

Mandatory Settings
------------------

For IS-IS top operate correctly, one must do the equivalent of a Router ID in
CLNS. This Router ID is called the :abbr:`NET (Network Entity Title)`. This
must be unique for each and every router that is operating in IS-IS. It also
must not be duplicated otherwise the same issues that occur within OSPF will
occur within IS-IS when it comes to said duplication.


.. cfgcmd:: set protocols isis net <network-entity-title>

  This command sets network entity title (NET) provided in ISO format.

  Here is an example :abbr:`NET (Network Entity Title)` value:

  .. code-block:: none

    49.0001.1921.6800.1002.00

  The CLNS address consists of the following parts:

  * :abbr:`AFI (Address family authority identifier)` - ``49`` The AFI value
    49 is what IS-IS uses for private addressing.

  * Area identifier: ``0001`` IS-IS area number (numerical area ``1``)

  * System identifier: ``1921.6800.1002`` - for system identifiers we recommend
    to use IP address or MAC address of the router itself. The way to construct
    this is to keep all of the zeroes of the router IP address, and then change
    the periods from being every three numbers to every four numbers. The
    address that is listed here is ``192.168.1.2``, which if expanded will turn
    into ``192.168.001.002``. Then all one has to do is move the dots to have
    four numbers instead of three. This gives us ``1921.6800.1002``.

  * :abbr:`NET (Network Entity Title)` selector: ``00`` Must always be 00. This
    setting indicates "this system" or "local system."

.. cfgcmd:: set protocols isis interface <interface>

  This command enables IS-IS on this interface, and allows for
  adjacency to occur. Note that the name of IS-IS instance must be
  the same as the one used to configure the IS-IS process.

IS-IS Global Configuration
--------------------------

.. cfgcmd:: set protocols isis dynamic-hostname

  This command enables support for dynamic hostname TLV. Dynamic hostname
  mapping determined as described in :rfc:`2763`, Dynamic Hostname
  Exchange Mechanism for IS-IS.

.. cfgcmd:: set protocols isis level <level-1|level-1-2|level-2>

  This command defines the IS-IS router behavior:

  * **level-1** - Act as a station (Level 1) router only.
  * **level-1-2** - Act as a station (Level 1) router and area (Level 2) router.
  * **level-2-only** - Act as an area (Level 2) router only.

.. cfgcmd:: set protocols isis lsp-mtu <size>

  This command configures the maximum size of generated
  :abbr:`LSPs (Link State PDUs)`, in bytes. The size range is 128 to 4352.

.. cfgcmd:: set protocols isis metric-style <narrow|transition|wide>

  This command sets old-style (ISO 10589) or new style packet formats:

  * **narrow** - Use old style of TLVs with narrow metric.
  * **transition** - Send and accept both styles of TLVs during transition.
  * **wide** - Use new style of TLVs to carry wider metric.

.. cfgcmd:: set protocols isis purge-originator

  This command enables :rfc:`6232` purge originator identification. Enable
  purge originator identification (POI) by adding the type, length and value
  (TLV) with the Intermediate System (IS) identification to the LSPs that do
  not contain POI information. If an IS generates a purge, VyOS adds this TLV
  with the system ID of the IS to the purge.

.. cfgcmd:: set protocols isis set-attached-bit

  This command sets ATT bit to 1 in Level1 LSPs. It is described in :rfc:`3787`.

.. cfgcmd:: set protocols isis set-overload-bit

  This command sets overload bit to avoid any transit traffic through this
  router. It is described in :rfc:`3787`.

.. cfgcmd:: set protocols isis default-information originate <ipv4|ipv6>
  level-1

  This command will generate a default-route in L1 database.

.. cfgcmd:: set protocols isis default-information originate <ipv4|ipv6>
  level-2

  This command will generate a default-route in L2 database.
  
  
.. cfgcmd:: set protocols isis ldp-sync

  This command will enable IGP-LDP synchronization globally for ISIS. This
  requires for LDP to be functional. This is described in :rfc:`5443`. By
  default all interfaces operational in IS-IS are enabled for synchronization.
  Loopbacks are exempt.
  
.. cfgcmd:: set protocols isis ldp-sync holddown <seconds>

  This command will change the hold down value globally for IGP-LDP
  synchronization during convergence/interface flap events. 


Interface Configuration
-----------------------

.. cfgcmd:: set protocols isis interface <interface> circuit-type
  <level-1|level-1-2|level-2-only>

  This command specifies circuit type for interface:

  * **level-1** - Level-1 only adjacencies are formed.
  * **level-1-2** - Level-1-2 adjacencies are formed
  * **level-2-only** - Level-2 only adjacencies are formed

.. cfgcmd:: set protocols isis interface <interface> hello-interval
  <seconds>

  This command sets hello interval in seconds on a given interface.
  The range is 1 to 600.

.. cfgcmd:: set protocols isis interface <interface> hello-multiplier
  <seconds>

  This command sets multiplier for hello holding time on a given
  interface. The range is 2 to 100.

.. cfgcmd:: set protocols isis interface <interface> hello-padding

  This command configures padding on hello packets to accommodate asymmetrical
  maximum transfer units (MTUs) from different hosts as described in
  :rfc:`3719`. This helps to prevent a premature adjacency Up state when one
  routing devices MTU does not meet the requirements to establish the adjacency.

.. cfgcmd:: set protocols isis interface <interface> metric <metric>

  This command set default metric for circuit.

  The metric range is 1 to 16777215 (Max value depend if metric support narrow
  or wide value).

.. cfgcmd:: set protocols isis interface <interface> network
  point-to-point

  This command specifies network type to Point-to-Point. The default
  network type is broadcast.

.. cfgcmd:: set protocols isis interface <interface> passive

  This command configures the passive mode for this interface.

.. cfgcmd:: set protocols isis interface <interface> password
  plaintext-password <text>

  This command configures the authentication password for the interface.

.. cfgcmd:: set protocols isis interface <interface> priority <number>

  This command sets priority for the interface for
  :abbr:`DIS (Designated Intermediate System)` election. The priority
  range is 0 to 127.

.. cfgcmd:: set protocols isis interface <interface> psnp-interval
  <number>

  This command sets PSNP interval in seconds. The interval range is 0
  to 127.

.. cfgcmd:: set protocols isis interface <interface>
  no-three-way-handshake

  This command disables Three-Way Handshake for P2P adjacencies which
  described in :rfc:`5303`. Three-Way Handshake is enabled by default.

.. cfgcmd:: set protocols isis interface <interface> ldp-sync disable

  This command disables IGP-LDP sync for this specific interface.

.. cfgcmd:: set protocols isis interface <interface> ldp-sync holddown
   <seconds>

  This command will change the hold down value for IGP-LDP synchronization
  during convergence/interface flap events, but for this interface only.

.. cfgcmd:: set protocols isis interface <interface> fast-reroute lfa [level-1 | level-2] enable
  
  This command enables per-prefix local LFA fast reroute link protection.

.. cfgcmd:: set protocols isis interface <interface> fast-reroute lfa [level-1 | level-2] exclude
  
  This command excludes an interface from the local LFA backup nexthop computation.

.. cfgcmd:: set protocols isis interface <interface> fast-reroute remote-lfa [level-1 | level-2] tunnel mpls-ldp
  
  This command enables per-prefix Remote LFA fast reroute link protection.
  Note that other routers in the network need to be configured to accept LDP
  targeted hello messages in order for RLFA to work.

.. cfgcmd:: set protocols isis interface <interface> fast-reroute remote-lfa [level-1 | level-2] maximum-metric <metric>
  
  This command limits Remote LFA PQ node selection within the specified metric. Metric value range (1-16777215).

.. cfgcmd:: set protocols isis interface <interface> fast-reroute ti-lfa [level-1|level-2] [node-protection [link-fallback]]
  
  This command enables per-prefix TI-LFA fast reroute link or node protection.
  When node protection is used, option link-fallback enables the computation 
  and use of link-protecting LFAs for destinations unprotected by node 
  protection.

Route Redistribution
--------------------

.. cfgcmd:: set protocols isis redistribute ipv4 <route source> level-1

  This command redistributes routing information from the given route source
  into the ISIS database as Level-1. There are six modes available for route
  source: bgp, connected, kernel, ospf, rip, static.

.. cfgcmd:: set protocols isis redistribute ipv4 <route source> level-2

  This command redistributes routing information from the given route source
  into the ISIS database as Level-2. There are six modes available for route
  source: bgp, connected, kernel, ospf, rip, static.

.. cfgcmd:: set protocols isis redistribute ipv4 <route source>
  <level-1|level-2> metric <number>

  This command specifies metric for redistributed routes from the given route
  source. There are six modes available for route source: bgp, connected,
  kernel, ospf, rip, static. The metric range is 1 to 16777215.

.. cfgcmd:: set protocols isis redistribute ipv4 <route source>
  <level-1|level-2> route-map <name>

  This command allows to use route map to filter redistributed routes from
  the given route source. There are six modes available for route source:
  bgp, connected, kernel, ospf, rip, static.


Timers
------

.. cfgcmd:: set protocols isis lsp-gen-interval <seconds>

  This command sets minimum interval in seconds between regenerating same
  LSP. The interval range is 1 to 120.

.. cfgcmd:: set protocols isis lsp-refresh-interval <seconds>

  This command sets LSP refresh interval in seconds. IS-IS generates LSPs
  when the state of a link changes. However, to ensure that routing
  databases on all routers remain converged, LSPs in stable networks are
  generated on a regular basis even though there has been no change to
  the state of the links. The interval range is 1 to 65235. The default
  value is 900 seconds.

.. cfgcmd:: set protocols isis max-lsp-lifetime <seconds>

  This command sets LSP maximum LSP lifetime in seconds. The interval range
  is 350 to 65535. LSPs remain in a database for 1200 seconds by default.
  If they are not refreshed by that time, they are deleted. You can change
  the LSP refresh interval or the LSP lifetime. The LSP refresh interval
  should be less than the LSP lifetime or else LSPs will time out before
  they are refreshed.

.. cfgcmd:: set protocols isis spf-interval <seconds>

  This command sets minimum interval between consecutive SPF calculations in
  seconds.The interval range is 1 to 120.

.. cfgcmd:: set protocols isis spf-delay-ietf holddown <milliseconds>

.. cfgcmd:: set protocols isis spf-delay-ietf init-delay
  <milliseconds>

.. cfgcmd:: set protocols isis spf-delay-ietf long-delay
  <milliseconds>

.. cfgcmd:: set protocols isis spf-delay-ietf short-delay
  <milliseconds>

.. cfgcmd:: set protocols isis spf-delay-ietf time-to-learn
  <milliseconds>

  This commands specifies the Finite State Machine (FSM) intended to
  control the timing of the execution of SPF calculations in response
  to IGP events. The process described in :rfc:`8405`.

Loop Free Alternate (LFA)
-------------------------

.. cfgcmd:: set protocols isis fast-reroute lfa remote prefix-list <name>
  <level-1|level-2>

  This command enables IP fast re-routing that is part of :rfc:`5286`.
  Specifically this is a prefix list which references a prefix in which
  will select eligible PQ nodes for remote LFA backups. 

.. cfgcmd:: set protocols isis fast-reroute lfa local load-sharing disable
  <level-1|level-2>

  This command disables the load sharing across multiple LFA backups.

.. cfgcmd:: set protocols isis fast-reroute lfa local tiebreaker
  <downstream|lowest-backup-metric|node-protecting> index <number>
  <level-1|level-2>

  This command will configure a tie-breaker for multiple local LFA backups.
  The lower index numbers will be processed first.
  
.. cfgcmd:: set protocols isis fast-reroute lfa local priority-limit
  <medium|high|critical> <level-1|level-2>
  
  This command will limit LFA backup computation up to the specified
  prefix priority. 

Segment Routing over IPv6 (SRv6)
-------------------------

.. cfgcmd:: set protocols isis segment-routing srv6 interface <interface>

  The :ref:`dummy interface<configuration/interfaces/dummy:dummy>` used
  to install SRv6 SIDs into the Linux data plane. The interface must exist and
  must be present when configuring IS-IS with
  SRv6.

.. cfgcmd:: set protocols isis segment-routing srv6 locator <locator>
  
  Specifies the SRv6 locator to use for IS-IS. IS-IS automatically allocates
  prefix and adjacency SIDs, creates local SID entries and advertises them
  into the IGP domain.

.. cfgcmd:: set protocols isis segment-routing srv6 node-msd max-end-d <0-255>

  The Maximum End D MSD Type specifies the maximum number of SIDs present in an
  SRH when performing decapsulation. As specified in :rfc:`8986`, the permitted
  SID types include, but are not limited to, End.DX6, End.DT4, End.DT46, End
  with USD, and End.X with USD.

  If the advertised value is zero or no value is advertised, then the router
  cannot apply any behavior that results in decapsulation and forwarding of the
  inner packet if the outer IPv6 header contains an SRH.

  Reference: :rfc:`9352`

.. cfgcmd:: set protocols isis segment-routing srv6 node-msd max-end-pop <0-255>

  The Maximum End Pop MSD Type signals the maximum number of SIDs in the SRH to
  which the router can apply "Penultimate Segment Pop (PSP) of the SRH" or
  "Ultimate Segment Pop (USP) of the SRH" behavior, as defined in "Flavors"
  (Section 4.16 of :rfc:`8986`).

  If the advertised value is zero or no value is advertised, then the router
  cannot apply PSP or USP flavors.

  Reference: :rfc:`9352`

.. cfgcmd:: set protocols isis segment-routing srv6 node-msd max-h-encaps <0-255>

  The Maximum H.Encaps MSD Type signals the maximum number of SIDs that can be
  added to the segment list of an SRH as part of the "H.Encaps" behavior, as
  defined in :rfc:`8986`.

  If the advertised value is zero or no value is advertised, then the headend
  can apply an SR Policy that only contains one segment without inserting any
  SRH header. A non-zero SRH Max H.encaps MSD indicates that the headend can
  insert an SRH up to the advertised number of SIDs.

  Reference: :rfc:`9352`

.. cfgcmd:: set protocols isis segment-routing srv6 node-msd max-segs-left <0-255>

  The Maximum Segments Left MSD Type signals the maximum value of the
  "Segments Left" field (:rfc:`8754`) in the SRH of a received packet before
  applying the Endpoint behavior associated with a SID.

  If no value is advertised, the supported value is 0.

  Reference: :rfc:`9352`

********
Examples
********

Enable IS-IS
============

**Node 1:**

.. code-block:: none

  set interfaces loopback lo address '192.168.255.255/32'
  set interfaces ethernet eth1 address '192.0.2.1/24'

  set protocols isis interface eth1
  set protocols isis interface lo
  set protocols isis net '49.0001.1921.6825.5255.00'

**Node 2:**

.. code-block:: none

  set interfaces ethernet eth1 address '192.0.2.2/24'

  set interfaces loopback lo address '192.168.255.254/32'
  set interfaces ethernet eth1 address '192.0.2.2/24'

  set protocols isis interface eth1
  set protocols isis interface lo
  set protocols isis net '49.0001.1921.6825.5254.00'



This gives us the following neighborships, Level 1 and Level 2:

.. code-block:: none

  Node-1@vyos:~$ show isis neighbor
  Area VyOS:
    System Id           Interface   L  State        Holdtime SNPA
   vyos                eth1        1  Up            28       0c87.6c09.0001
   vyos                eth1        2  Up            28       0c87.6c09.0001

  Node-2@vyos:~$ show isis neighbor
  Area VyOS:
    System Id           Interface   L  State        Holdtime SNPA
   vyos                eth1        1  Up            29       0c33.0280.0001
   vyos                eth1        2  Up            28       0c33.0280.0001



Here's the IP routes that are populated. Just the loopback:

.. code-block:: none

  Node-1@vyos:~$ show ip route isis
  Codes: K - kernel route, C - connected, S - static, R - RIP,
         O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
         T - Table, v - VNC, V - VNC-Direct, A - Babel, F - PBR,
         f - OpenFabric,
         > - selected route, * - FIB route, q - queued, r - rejected, b - backup
         t - trapped, o - offload failure

  I   192.0.2.0/24 [115/20] via 192.0.2.2, eth1 inactive, weight 1, 00:02:22
  I>* 192.168.255.254/32 [115/20] via 192.0.2.2, eth1, weight 1, 00:02:22

  Node-2@vyos:~$ show ip route isis
  Codes: K - kernel route, C - connected, S - static, R - RIP,
         O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
         T - Table, v - VNC, V - VNC-Direct, A - Babel, F - PBR,
         f - OpenFabric,
         > - selected route, * - FIB route, q - queued, r - rejected, b - backup
         t - trapped, o - offload failure

  I   192.0.2.0/24 [115/20] via 192.0.2.1, eth1 inactive, weight 1, 00:02:21
  I>* 192.168.255.255/32 [115/20] via 192.0.2.1, eth1, weight 1, 00:02:21



Enable IS-IS and redistribute routes not natively in IS-IS
==========================================================

**Node 1:**

.. code-block:: none

  set interfaces dummy dum0 address '203.0.113.1/24'
  set interfaces ethernet eth1 address '192.0.2.1/24'

  set policy prefix-list EXPORT-ISIS rule 10 action 'permit'
  set policy prefix-list EXPORT-ISIS rule 10 prefix '203.0.113.0/24'
  set policy route-map EXPORT-ISIS rule 10 action 'permit'
  set policy route-map EXPORT-ISIS rule 10 match ip address prefix-list 'EXPORT-ISIS'

  set protocols isis interface eth1
  set protocols isis net '49.0001.1921.6800.1002.00'
  set protocols isis redistribute ipv4 connected level-2 route-map 'EXPORT-ISIS'

**Node 2:**

.. code-block:: none

  set interfaces ethernet eth1 address '192.0.2.2/24'

  set protocols isis interface eth1
  set protocols isis net '49.0001.1921.6800.2002.00'

Routes on Node 2:

.. code-block:: none

  Node-2@r2:~$ show ip route isis
  Codes: K - kernel route, C - connected, S - static, R - RIP,
         O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
         T - Table, v - VNC, V - VNC-Direct, A - Babel, D - SHARP,
         F - PBR, f - OpenFabric,
         > - selected route, * - FIB route, q - queued route, r - rejected route

  I   203.0.113.0/24 [115/10] via 192.0.2.1, eth1, 00:03:42
  
Enable IS-IS and IGP-LDP synchronization
========================================

**Node 1:**

.. code-block:: none

  set interfaces loopback lo address 192.168.255.255/32
  set interfaces ethernet eth0 address 192.0.2.1/24

  set protocols isis interface eth0
  set protocols isis interface lo passive
  set protocols isis ldp-sync
  set protocols isis net 49.0001.1921.6825.5255.00

  set protocols mpls interface eth0
  set protocols mpls ldp discovery transport-ipv4-address 192.168.255.255
  set protocols mpls ldp interface lo
  set protocols mpls ldp interface eth0
  set protocols mpls ldp parameters transport-prefer-ipv4
  set protocols mpls ldp router-id 192.168.255.255


This gives us IGP-LDP synchronization for all non-loopback interfaces with
a holddown timer of zero seconds:


.. code-block:: none

  Node-1@vyos:~$  show isis mpls ldp-sync
  eth0
    LDP-IGP Synchronization enabled: yes
    holddown timer in seconds: 0
    State: Sync achieved




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

Enable IS-IS with Segment Routing over IPv6 (Experimental)
==========================================================

**Node 1:**

.. code-block:: none

  set interfaces dummy dum6 description "SRv6 IS-IS"
  set interfaces ethernet eth1 address '192.0.2.1/24'
  set interfaces loopback lo address '192.168.255.255/32'

  set protocols segment-routing srv6 locator MAIN prefix 2001:db8:1::/64
  set protocols segment-routing interface eth1

  set protocols isis interface eth1
  set protocols isis interface lo
  set protocols isis net '49.0001.1921.6825.5255.00'
  set protocols isis segment-routing srv6 locator MAIN
  set protocols isis segment-routing srv6 interface dum6

**Node 2:**

.. code-block:: none

  set interfaces dummy dum6 description "SRv6 IS-IS"
  set interfaces ethernet eth1 address '192.0.2.2/24'
  set interfaces loopback lo address '192.168.255.254/32'

  set protocols segment-routing srv6 locator MAIN prefix 2001:db8:2::/64
  set protocols segment-routing interface eth1

  set protocols isis interface eth1
  set protocols isis interface lo
  set protocols isis net '49.0001.1921.6825.5254.00'
  set protocols isis segment-routing srv6 locator MAIN
  set protocols isis segment-routing srv6 interface dum6

Enable IS-IS with Segment Routing over IPv6 (uSID) (Experimental)
=================================================================

**Node 1:**

.. code-block:: none

  set interfaces dummy dum6 description "SRv6 IS-IS"
  set interfaces ethernet eth1 address '192.0.2.1/24'
  set interfaces loopback lo address '192.168.255.255/32'

  set protocols segment-routing interface eth1
  set protocols segment-routing srv6 locator MAIN prefix 2001:db8:1::/48
  set protocols segment-routing srv6 locator MAIN behavior-usid
  set protocols segment-routing srv6 locator MAIN block-len 32
  set protocols segment-routing srv6 locator MAIN format usid-f3216
  set protocols segment-routing srv6 locator MAIN func-bits 16
  set protocols segment-routing srv6 locator MAIN node-len 16

  set protocols isis interface eth1
  set protocols isis interface lo
  set protocols isis net '49.0001.1921.6825.5255.00'
  set protocols isis segment-routing srv6 interface dum6
  set protocols isis segment-routing srv6 locator MAIN

**Node 2:**

.. code-block:: none

  set interfaces dummy dum6 description "SRv6 IS-IS"
  set interfaces ethernet eth1 address '192.0.2.2/24'
  set interfaces loopback lo address '192.168.255.254/32'

  set protocols segment-routing interface eth1
  set protocols segment-routing srv6 locator MAIN prefix 2001:db8:2::/48
  set protocols segment-routing srv6 locator MAIN behavior-usid
  set protocols segment-routing srv6 locator MAIN block-len 32
  set protocols segment-routing srv6 locator MAIN format usid-f3216
  set protocols segment-routing srv6 locator MAIN func-bits 16
  set protocols segment-routing srv6 locator MAIN node-len 16

  set protocols isis interface eth1
  set protocols isis interface lo
  set protocols isis net '49.0001.1921.6825.5254.00'
  set protocols isis segment-routing srv6 interface dum6
  set protocols isis segment-routing srv6 locator MAIN
