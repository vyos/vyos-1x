.. _routing-ospf:

####
OSPF
####

:abbr:`OSPF (Open Shortest Path First)` is a routing protocol for Internet
Protocol (IP) networks. It uses a link state routing (LSR) algorithm and falls
into the group of interior gateway protocols (IGPs), operating within a single
autonomous system (AS). It is defined as OSPF Version 2 in :rfc:`2328` (1998)
for IPv4. Updates for IPv6 are specified as OSPF Version 3 in :rfc:`5340`
(2008). OSPF supports the :abbr:`CIDR (Classless Inter-Domain Routing)`
addressing model.

OSPF is a widely used IGP in large enterprise networks.

*************
OSPFv2 (IPv4)
*************

Configuration
=============

General
-------

VyOS does not have a special command to start the OSPF process. The OSPF process
starts when the first ospf enabled interface is configured.

.. cfgcmd:: set protocols ospf area <number> network <A.B.C.D/M>

   This command specifies the OSPF enabled interface(s). If the interface has
   an address from defined range then the command enables OSPF on this
   interface so router can provide network information to the other ospf
   routers via this interface.

   This command is also used to enable the OSPF process. The area number can be
   specified in decimal notation in the range from 0 to 4294967295. Or it
   can be specified in dotted decimal notation similar to ip address.

   Prefix length in interface must be equal or bigger (i.e. smaller network)
   than prefix length in network statement. For example statement above doesn't
   enable ospf on interface with address 192.168.1.1/23, but it does on
   interface with address 192.168.1.129/25.

   In some cases it may be more convenient to enable OSPF on a per
   interface/subnet
   basis :cfgcmd:`set protocols ospf interface <interface> area <x.x.x.x | x>`

.. cfgcmd:: set protocols ospf auto-cost reference-bandwidth <number>

   This command sets the reference bandwidth for cost calculations, where
   bandwidth can be in range from 1 to 4294967, specified in Mbits/s. The
   default is 100Mbit/s (i.e. a link of bandwidth 100Mbit/s or higher will
   have a cost of 1. Cost of lower bandwidth links will be scaled with
   reference to this cost).

.. cfgcmd:: set protocols ospf parameters router-id <rid>

   This command sets the router-ID of the OSPF process. The router-ID may be an
   IP address of the router, but need not be – it can be any arbitrary 32bit
   number. However it MUST be unique within the entire OSPF domain to the OSPF
   speaker – bad things will happen if multiple OSPF speakers are configured
   with the same router-ID!


Optional
--------

.. cfgcmd:: set protocols ospf default-information originate [always]
   [metric <number>] [metric-type <1|2>] [route-map <name>]

   Originate an AS-External (type-5) LSA describing a default route into all
   external-routing capable areas, of the specified metric and metric type.
   If the :cfgcmd:`always` keyword is given then the default is always
   advertised, even when there is no default present in the routing table.
   The argument :cfgcmd:`route-map` specifies to advertise the default route
   if the route map is satisfied.

.. cfgcmd:: set protocols ospf distance global <distance>

   This command change distance value of OSPF globally.
   The distance range is 1 to 255.

.. cfgcmd:: set protocols ospf distance ospf <external|inter-area|intra-area>
   <distance>

   This command change distance value of OSPF. The arguments are the distance
   values for external routes, inter-area routes and intra-area routes
   respectively. The distance range is 1 to 255.

   .. note:: Routes with a distance of 255 are effectively disabled and not
      installed into the kernel.

.. cfgcmd:: set protocols ospf log-adjacency-changes [detail]

   This command allows to log changes in adjacency. With the optional
   :cfgcmd:`detail` argument, all changes in adjacency status are shown.
   Without :cfgcmd:`detail`, only changes to full or regressions are shown.

.. cfgcmd:: set protocols ospf max-metric router-lsa
   <administrative|on-shutdown <seconds>|on-startup <seconds>>

   This enables :rfc:`3137` support, where the OSPF process describes its
   transit links in its router-LSA as having infinite distance so that other
   routers will avoid calculating transit paths through the router while
   still being able to reach networks through the router.

   This support may be enabled administratively (and indefinitely) with the
   :cfgcmd:`administrative` command. It may also be enabled conditionally.
   Conditional enabling of max-metric router-lsas can be for a period of
   seconds after startup with the :cfgcmd:`on-startup <seconds>` command
   and/or for a period of seconds prior to shutdown with the
   :cfgcmd:`on-shutdown <seconds>` command. The time range is 5 to 86400.

.. cfgcmd:: set protocols ospf parameters abr-type
   <cisco|ibm|shortcut|standard>

   This command selects ABR model. OSPF router supports four ABR models:

   **cisco** – a router will be considered as ABR if it has several configured
   links to the networks in different areas one of which is a backbone area.
   Moreover, the link to the backbone area should be active (working).
   **ibm** – identical to "cisco" model but in this case a backbone area link
   may not be active.
   **standard** – router has several active links to different areas.
   **shortcut** – identical to "standard" but in this model a router is
   allowed to use a connected areas topology without involving a backbone
   area for inter-area connections.

   Detailed information about "cisco" and "ibm" models differences can be
   found in :rfc:`3509`. A "shortcut" model allows ABR to create routes
   between areas based on the topology of the areas connected to this router
   but not using a backbone area in case if non-backbone route will be
   cheaper. For more information about "shortcut" model,
   see :t:`ospf-shortcut-abr-02.txt`

.. cfgcmd:: set protocols ospf parameters rfc1583-compatibility

   :rfc:`2328`, the successor to :rfc:`1583`, suggests according to section
   G.2 (changes) in section 16.4.1 a change to the path preference algorithm
   that prevents possible routing loops that were possible in the old version
   of OSPFv2. More specifically it demands that inter-area paths and
   intra-area backbone path are now of equal preference but still both
   preferred to external paths.

   This command should NOT be set normally.

.. cfgcmd:: set protocols ospf interface <interface> passive [disable]

   This command specifies interface as passive. Passive interface advertises
   its address, but does not run the OSPF protocol (adjacencies are not formed
   and hello packets are not generated).

   The optional `disable` option allows to exclude interface from passive state.
   This command is used if the command :cfgcmd:`passive-interface default` was
   configured.

.. cfgcmd:: set protocols ospf passive-interface default

   This command specifies all interfaces as passive by default. Because this
   command changes the configuration logic to a default passive; therefore,
   interfaces where router adjacencies are expected need to be configured
   with the :cfgcmd:`passive-interface-exclude` command.

.. cfgcmd:: set protocols ospf maximum-paths <1-64>

   Use this command to control the maximum number of equal cost paths to reach
   a specific destination. The upper limit may differ if you change the value
   of MULTIPATH_NUM during compilation. The default is MULTIPATH_NUM (64).

.. cfgcmd:: set protocols ospf refresh timers <seconds>

   The router automatically updates link-state information with its neighbors.
   Only an obsolete information is updated which age has exceeded a specific
   threshold. This parameter changes a threshold value, which by default is
   1800 seconds (half an hour). The value is applied to the whole OSPF router.
   The timer range is 10 to 1800.

.. cfgcmd:: set protocols ospf timers throttle spf
   <delay|initial-holdtime|max-holdtime> <seconds>

   This command sets the initial delay, the initial-holdtime and the
   maximum-holdtime between when SPF is calculated and the event which
   triggered the calculation. The times are specified in milliseconds and must
   be in the range of 0 to 600000 milliseconds. :cfgcmd:`delay` sets the
   initial SPF schedule delay in milliseconds. The default value is 200 ms.
   :cfgcmd:`initial-holdtime` sets the minimum hold time between two
   consecutive SPF calculations. The default value is 1000 ms.
   :cfgcmd:`max-holdtime` sets the maximum wait time between two
   consecutive SPF calculations. The default value is 10000 ms.

.. cfgcmd:: set protocols ospf ldp-sync

  This command will enable IGP-LDP synchronization globally for OSPF. This
  requires for LDP to be functional. This is described in :rfc:`5443`. By
  default all interfaces operational in OSPF are enabled for synchronization.
  Loopbacks are exempt.

.. cfgcmd:: set protocols ospf ldp-sync holddown <seconds>

  This command will change the hold down value globally for IGP-LDP
  synchronization during convergence/interface flap events.

.. cfgcmd:: set protocols ospf capability opaque

   ospfd supports Opaque LSA :rfc:`2370` as partial support for MPLS Traffic
   Engineering LSAs. The opaque-lsa capability must be enabled in the
   configuration.

   An alternate command could be "mpls-te on" (Traffic Engineering)

   .. note:: FRR offers only partial support for some of the routing
      protocol extensions that are used with MPLS-TE; it does not
      support a complete RSVP-TE solution.

Area Configuration
------------------

.. cfgcmd:: set protocols ospf area <number> area-type stub

   This command specifies the area to be a Stub Area. That is, an area where
   no router originates routes external to OSPF and hence an area where all
   external routes are via the ABR(s). Hence, ABRs for such an area do not
   need to pass AS-External LSAs (type-5) or ASBR-Summary LSAs (type-4) into
   the area. They need only pass Network-Summary (type-3) LSAs into such an
   area, along with a default-route summary.

.. cfgcmd:: set protocols ospf area <number> area-type stub no-summary

   This command specifies the area to be a Totally Stub Area. In addition to
   stub area limitations this area type prevents an ABR from injecting
   Network-Summary (type-3) LSAs into the specified stub area. Only default
   summary route is allowed.

.. cfgcmd:: set protocols ospf area <number> area-type stub default-cost
   <number>

   This command sets the cost of default-summary LSAs announced to stubby
   areas. The cost range is 0 to 16777215.

.. cfgcmd:: set protocols ospf area <number> area-type nssa

   This command specifies the area to be a Not So Stubby Area. External
   routing information is imported into an NSSA in Type-7 LSAs. Type-7 LSAs
   are similar to Type-5 AS-external LSAs, except that they can only be
   flooded into the NSSA. In order to further propagate the NSSA external
   information, the Type-7 LSA must be translated to a Type-5 AS-external-LSA
   by the NSSA ABR.

.. cfgcmd:: set protocols ospf area <number> area-type nssa no-summary

   This command specifies the area to be a NSSA Totally Stub Area. ABRs for
   such an area do not need to pass Network-Summary (type-3) LSAs (except the
   default summary route), ASBR-Summary LSAs (type-4) and AS-External LSAs
   (type-5) into the area. But Type-7 LSAs that convert to Type-5 at the NSSA
   ABR are allowed.

.. cfgcmd:: set protocols ospf area <number> area-type nssa default-cost
   <number>

   This command sets the default cost of LSAs announced to NSSA areas.
   The cost range is 0 to 16777215.

.. cfgcmd:: set protocols ospf area <number> area-type nssa translate
   <always|candidate|never>

   Specifies whether this NSSA border router will unconditionally translate
   Type-7 LSAs into Type-5 LSAs. When role is Always, Type-7 LSAs are
   translated into Type-5 LSAs regardless of the translator state of other
   NSSA border routers. When role is Candidate, this router participates in
   the translator election to determine if it will perform the translations
   duties. When role is Never, this router will never translate Type-7 LSAs
   into Type-5 LSAs.

.. cfgcmd:: set protocols ospf area <number> authentication plaintext-password

   This command specifies that simple password authentication should be used
   for the given area. The password must also be configured on a per-interface
   basis.

.. cfgcmd:: set protocols ospf area <number> authentication md5

   This command specify that OSPF packets must be authenticated with MD5 HMACs
   within the given area. Keying material must also be configured on a
   per-interface basis.

.. cfgcmd:: set protocols ospf area <number> range <A.B.C.D/M> [cost <number>]

   This command summarizes intra area paths from specified area into one
   summary-LSA (Type-3) announced to other areas. This command can be used
   only in ABR and ONLY router-LSAs (Type-1) and network-LSAs (Type-2)
   (i.e. LSAs with scope area) can be summarized. AS-external-LSAs (Type-5)
   can’t be summarized - their scope is AS. The optional argument
   :cfgcmd:`cost` specifies the aggregated link metric. The metric range is 0
   to 16777215.

.. cfgcmd:: set protocols ospf area <number> range <A.B.C.D/M> not-advertise

   This command instead of summarizing intra area paths filter them - i.e.
   intra area paths from this range are not advertised into other areas.
   This command makes sense in ABR only.

.. cfgcmd:: set protocols ospf area <number> export-list <acl_number>

   Filter Type-3 summary-LSAs announced to other areas originated from
   intra- area paths from specified area.
   This command makes sense in ABR only.

.. cfgcmd:: set protocols ospf area <number> import-list <acl_number>

   Same as export-list, but it applies to paths announced into specified
   area as Type-3 summary-LSAs.
   This command makes sense in ABR only.

.. cfgcmd:: set protocols ospf area <number> range <A.B.C.D/M> substitute
   <E.F.G.H/M>

   One Type-3 summary-LSA with routing info <E.F.G.H/M> is announced into
   backbone area if defined area contains at least one intra-area network
   (i.e. described with router-LSA or network-LSA) from range <A.B.C.D/M>.
   This command makes sense in ABR only.

.. cfgcmd:: set protocols ospf area <number> shortcut <default|disable|enable>

   This parameter allows to "shortcut" routes (non-backbone) for inter-area
   routes. There are three modes available for routes shortcutting:

   **default** –  this area will be used for shortcutting only if ABR does not
   have a link to the backbone area or this link was lost.
   **enable** – the area will be used for shortcutting every time the route
   that goes through it is cheaper.
   **disable** – this area is never used by ABR for routes shortcutting.

.. cfgcmd:: set protocols ospf area <number> virtual-link <A.B.C.D>

   Provides a backbone area coherence by virtual link establishment.

   In general, OSPF protocol requires a backbone area (area 0) to be coherent
   and fully connected. I.e. any backbone area router must have a route to any
   other backbone area router. Moreover, every ABR must have a link to
   backbone area. However, it is not always possible to have a physical link
   to a backbone area. In this case between two ABR (one of them has a link to
   the backbone area) in the area (not stub area) a virtual link is organized.

   <number> – area identifier through which a virtual link goes.
   <A.B.C.D> – ABR router-id with which a virtual link is established. Virtual
   link must be configured on both routers.

   Formally, a virtual link looks like a point-to-point network connecting two
   ABR from one area one of which physically connected to a backbone area.
   This pseudo-network is considered to belong to a backbone area.


Interface Configuration
-----------------------

.. cfgcmd:: set protocols ospf interface <interface> area <x.x.x.x | x>

   Enable ospf on an interface and set associated area.

   If you have a lot of interfaces, and/or a lot of subnets, then enabling
   OSPF via this command may result in a slight performance improvement.

.. cfgcmd:: set protocols ospf interface <interface> authentication
   plaintext-password <text>

   This command sets OSPF authentication key to a simple password. After
   setting, all OSPF packets are authenticated. Key has length up to 8 chars.

   Simple text password authentication is insecure and deprecated in favour of
   MD5 HMAC authentication.

.. cfgcmd:: set protocols ospf interface <interface> authentication md5
   key-id <id> md5-key <text>

   This command specifys that MD5 HMAC authentication must be used on this
   interface. It sets OSPF authentication key to a cryptographic password.
   Key-id identifies secret key used to create the message digest. This ID
   is part of the protocol and must be consistent across routers on a link.
   The key can be long up to 16 chars (larger strings will be truncated),
   and is associated with the given key-id.

.. cfgcmd:: set protocols ospf interface <interface> bandwidth <number>

   This command sets the interface bandwidth for cost calculations, where
   bandwidth can be in range from 1 to 100000, specified in Mbits/s.

.. cfgcmd:: set protocols ospf interface <interface> cost <number>

   This command sets link cost for the specified interface. The cost value is
   set to router-LSA’s metric field and used for SPF calculation. The cost
   range is 1 to 65535.

.. cfgcmd:: set protocols ospf interface <interface> dead-interval <number>

   Set number of seconds for router Dead Interval timer value used for Wait
   Timer and Inactivity Timer. This value must be the same for all routers
   attached to a common network. The default value is 40 seconds. The
   interval range is 1 to 65535.

.. cfgcmd:: set protocols ospf interface <interface> hello-multiplier <number>

   The hello-multiplier specifies how many Hellos to send per second, from 1
   (every second) to 10 (every 100ms). Thus one can have 1s convergence time
   for OSPF. If this form is specified, then the hello-interval advertised in
   Hello packets is set to 0 and the hello-interval on received Hello packets
   is not checked, thus the hello-multiplier need NOT be the same across
   multiple routers on a common link.

.. cfgcmd:: set protocols ospf interface <interface> hello-interval <number>

   Set number of seconds for Hello Interval timer value. Setting this value,
   Hello packet will be sent every timer value seconds on the specified
   interface. This value must be the same for all routers attached to a
   common network. The default value is 10 seconds. The interval range is 1
   to 65535.

.. cfgcmd:: set protocols ospf interface <interface> bfd

   This command enables :abbr:`BFD (Bidirectional Forwarding Detection)` on
   this OSPF link interface.

.. cfgcmd:: set protocols ospf interface <interface> mtu-ignore

   This command disables check of the MTU value in the OSPF DBD packets. Thus,
   use of this command allows the OSPF adjacency to reach the FULL state even
   though there is an interface MTU mismatch between two OSPF routers.

.. cfgcmd:: set protocols ospf interface <interface> network <type>

   This command allows to specify the distribution type for the network
   connected to this interface:

   **broadcast** – broadcast IP addresses distribution.
   **non-broadcast** – address distribution in NBMA networks topology.
   **point-to-multipoint** – address distribution in point-to-multipoint
   networks.
   **point-to-point** – address distribution in point-to-point networks.

.. cfgcmd:: set protocols ospf interface <interface> priority <number>

   This command sets Router Priority integer value. The router with the
   highest priority will be more eligible to become Designated Router.
   Setting the value to 0, makes the router ineligible to become
   Designated Router. The default value is 1. The interval range is 0 to 255.

.. cfgcmd:: set protocols ospf interface <interface> retransmit-interval
   <number>

   This command sets number of seconds for RxmtInterval timer value. This
   value is used when retransmitting Database Description and Link State
   Request packets if acknowledge was not received. The default value is 5
   seconds. The interval range is 3 to 65535.

.. cfgcmd:: set protocols ospf interface <interface> transmit-delay <number>

   This command sets number of seconds for InfTransDelay value. It allows to
   set and adjust for each interface the delay interval before starting the
   synchronizing process of the router's database with all neighbors. The
   default value is 1 seconds. The interval range is 3 to 65535.

.. cfgcmd:: set protocols ospf interface <interface> ldp-sync disable

  This command disables IGP-LDP sync for this specific interface.

.. cfgcmd:: set protocols ospf interface <interface> ldp-sync holddown
   <seconds>

  This command will change the hold down value for IGP-LDP synchronization
  during convergence/interface flap events, but for this interface only.

External Route Summarisation
----------------------------

This feature summarises originated external LSAs (Type-5 and Type-7). Summary
Route will be originated on-behalf of all matched external LSAs.

.. cfgcmd:: set protocols ospf aggregation timer <seconds>

   Configure aggregation delay timer interval.

   Summarisation starts only after this delay timer expiry.

.. cfgcmd:: set protocols ospf summary-address x.x.x.x/y [tag (1-4294967295)]

   This command enable/disables summarisation for the configured address range.

   Tag is the optional parameter. If tag configured Summary route will be
   originated with the configured tag.

.. cfgcmd:: set protocols ospf summary-address x.x.x.x/y no-advertise

   This command to ensure not advertise the summary lsa for the matched
   external LSAs.

Graceful Restart
----------------

.. cfgcmd:: set protocols ospf graceful-restart [grace-period (1-1800)]

   Configure Graceful Restart :rfc:`3623` restarting support. When enabled,
   the default grace period is 120 seconds.

   To perform a graceful shutdown, the FRR ``graceful-restart prepare ip
   ospf`` EXEC-level command needs to be issued before restarting the
   ospfd daemon.

.. cfgcmd:: set protocols ospf graceful-restart helper enable [router-id A.B.C.D]

   Configure Graceful Restart :rfc:`3623` helper support. By default, helper support
   is disabled for all neighbours. This config enables/disables helper support
   on this router for all neighbours.

   To enable/disable helper support for a specific neighbour, the router-id
   (A.B.C.D) has to be specified.

.. cfgcmd:: set protocols ospf graceful-restart helper no-strict-lsa-checking

   By default `strict-lsa-checking` is configured then the helper will abort
   the Graceful Restart when a LSA change occurs which affects the restarting
   router.

   This command disables it.

.. cfgcmd:: set protocols ospf graceful-restart helper supported-grace-time

   Supports as HELPER for configured grace period.

.. cfgcmd:: set protocols ospf graceful-restart helper planned-only

   It helps to support as HELPER only for planned restarts.

   By default, it supports both planned and unplanned outages.

Manual Neighbor Configuration
-----------------------------

OSPF routing devices normally discover their neighbors dynamically by
listening to the broadcast or multicast hello packets on the network.
Because an NBMA network does not support broadcast (or multicast), the
device cannot discover its neighbors dynamically, so you must configure all
the neighbors statically.

.. cfgcmd:: set protocols ospf neighbor <A.B.C.D>

   This command specifies the IP address of the neighboring device.

.. cfgcmd:: set protocols ospf neighbor <A.B.C.D> poll-interval <seconds>

   This command specifies the length of time, in seconds, before the routing
   device sends hello packets out of the interface before it establishes
   adjacency with a neighbor. The range is 1 to 65535 seconds. The default
   value is 60 seconds.

.. cfgcmd:: set protocols ospf neighbor <A.B.C.D> priority <number>

   This command specifies the router priority value of the nonbroadcast
   neighbor associated with the IP address specified. The default is 0.
   This keyword does not apply to point-to-multipoint interfaces.


Redistribution Configuration
----------------------------

.. cfgcmd:: set protocols ospf redistribute <route source>

   This command redistributes routing information from the given route source
   to the OSPF process. There are five modes available for route source: bgp,
   connected, kernel, rip, static.

.. cfgcmd:: set protocols ospf default-metric <number>

   This command specifies the default metric value of redistributed routes.
   The metric range is 0 to 16777214.

.. cfgcmd:: set protocols ospf redistribute <route source> metric <number>

   This command specifies metric for redistributed routes from the given
   route source. There are five modes available for route source: bgp,
   connected, kernel, rip, static. The metric range is 1 to 16777214.

.. cfgcmd:: set protocols ospf redistribute <route source> metric-type <1|2>

   This command specifies metric type for redistributed routes. Difference
   between two metric types that metric type 1 is a metric which is
   "commensurable" with inner OSPF links. When calculating a metric to the
   external destination, the full path metric is calculated as a metric sum
   path of a router which had advertised this link plus the link metric.
   Thus, a route with the least summary metric will be selected. If external
   link is advertised with metric type 2 the path is selected which lies
   through the router which advertised this link with the least metric
   despite of the fact that internal path to this router is longer (with more
   cost). However, if two routers advertised an external link and with metric
   type 2 the preference is given to the path which lies through the router
   with a shorter internal path. If two different routers advertised two
   links to the same external destimation but with different metric type,
   metric type 1 is preferred. If type of a metric left undefined the router
   will consider these external links to have a default metric type 2.

.. cfgcmd:: set protocols ospf redistribute <route source> route-map <name>

   This command allows to use route map to filter redistributed routes from
   the given route source. There are five modes available for route source:
   bgp, connected, kernel, rip, static.


Operational Mode Commands
-------------------------

.. opcmd:: show ip ospf neighbor

   This command displays the neighbors status.

.. code-block:: none

   Neighbor ID     Pri State           Dead Time Address         Interface                        RXmtL RqstL DBsmL
   10.0.13.1         1 Full/DR           38.365s 10.0.13.1       eth0:10.0.13.3                       0     0     0
   10.0.23.2         1 Full/Backup       39.175s 10.0.23.2       eth1:10.0.23.3                       0     0     0

.. opcmd:: show ip ospf neighbor detail

   This command displays the neighbors information in a detailed form, not
   just a summary table.

.. code-block:: none

   Neighbor 10.0.13.1, interface address 10.0.13.1
      In the area 0.0.0.0 via interface eth0
      Neighbor priority is 1, State is Full, 5 state changes
      Most recent state change statistics:
        Progressive change 11m55s ago
      DR is 10.0.13.1, BDR is 10.0.13.3
      Options 2 *|-|-|-|-|-|E|-
      Dead timer due in 34.854s
      Database Summary List 0
      Link State Request List 0
      Link State Retransmission List 0
      Thread Inactivity Timer on
      Thread Database Description Retransmision off
      Thread Link State Request Retransmission on
      Thread Link State Update Retransmission on

  Neighbor 10.0.23.2, interface address 10.0.23.2
     In the area 0.0.0.1 via interface eth1
     Neighbor priority is 1, State is Full, 4 state changes
     Most recent state change statistics:
       Progressive change 41.193s ago
     DR is 10.0.23.3, BDR is 10.0.23.2
     Options 2 *|-|-|-|-|-|E|-
     Dead timer due in 35.661s
     Database Summary List 0
     Link State Request List 0
     Link State Retransmission List 0
     Thread Inactivity Timer on
     Thread Database Description Retransmision off
     Thread Link State Request Retransmission on
     Thread Link State Update Retransmission on

.. opcmd:: show ip ospf neighbor <A.B.C.D>

   This command displays the neighbors information in a detailed form for a
   neighbor whose IP address is specified.

.. opcmd:: show ip ospf neighbor <interface>

   This command displays the neighbors status for a neighbor on the specified
   interface.

.. opcmd:: show ip ospf interface [<interface>]

   This command displays state and configuration of OSPF the specified
   interface, or all interfaces if no interface is given.

.. code-block:: none

   eth0 is up
     ifindex 2, MTU 1500 bytes, BW 4294967295 Mbit <UP,BROADCAST,RUNNING,MULTICAST>
     Internet Address 10.0.13.3/24, Broadcast 10.0.13.255, Area 0.0.0.0
     MTU mismatch detection: enabled
     Router ID 10.0.23.3, Network Type BROADCAST, Cost: 1
     Transmit Delay is 1 sec, State Backup, Priority 1
     Backup Designated Router (ID) 10.0.23.3, Interface Address 10.0.13.3
     Multicast group memberships: OSPFAllRouters OSPFDesignatedRouters
     Timer intervals configured, Hello 10s, Dead 40s, Wait 40s, Retransmit 5
       Hello due in 4.470s
     Neighbor Count is 1, Adjacent neighbor count is 1
   eth1 is up
     ifindex 3, MTU 1500 bytes, BW 4294967295 Mbit <UP,BROADCAST,RUNNING,MULTICAST>
     Internet Address 10.0.23.3/24, Broadcast 10.0.23.255, Area 0.0.0.1
     MTU mismatch detection: enabled
     Router ID 10.0.23.3, Network Type BROADCAST, Cost: 1
     Transmit Delay is 1 sec, State DR, Priority 1
     Backup Designated Router (ID) 10.0.23.2, Interface Address 10.0.23.2
     Saved Network-LSA sequence number 0x80000002
     Multicast group memberships: OSPFAllRouters OSPFDesignatedRouters
     Timer intervals configured, Hello 10s, Dead 40s, Wait 40s, Retransmit 5
       Hello due in 4.563s
     Neighbor Count is 1, Adjacent neighbor count is 1

.. opcmd:: show ip ospf route [detail]

   This command displays the OSPF routing table, as determined by the most
   recent SPF calculation. With the optional :cfgcmd:`detail` argument,
   each route item's advertiser router and network attribute will be shown.

.. code-block:: none

   ============ OSPF network routing table ============
   N IA 10.0.12.0/24          [3] area: 0.0.0.0
                              via 10.0.13.3, eth0
   N    10.0.13.0/24          [1] area: 0.0.0.0
                              directly attached to eth0
   N IA 10.0.23.0/24          [2] area: 0.0.0.0
                              via 10.0.13.3, eth0
   N    10.0.34.0/24          [2] area: 0.0.0.0
                              via 10.0.13.3, eth0

   ============ OSPF router routing table =============
   R    10.0.23.3             [1] area: 0.0.0.0, ABR
                              via 10.0.13.3, eth0
   R    10.0.34.4             [2] area: 0.0.0.0, ASBR
                              via 10.0.13.3, eth0

   ============ OSPF external routing table ===========
   N E2 172.16.0.0/24         [2/20] tag: 0
                              via 10.0.13.3, eth0

The table consists of following data:

**OSPF network routing table** – includes a list of acquired routes for all
accessible networks (or aggregated area ranges) of OSPF system. "IA" flag
means that route destination is in the area to which the router is not
connected, i.e. it’s an inter-area path. In square brackets a summary metric
for all links through which a path lies to this network is specified. "via"
prefix defines a router-gateway, i.e. the first router on the way to the
destination (next hop).
**OSPF router routing table** – includes a list of acquired routes to all
accessible ABRs and ASBRs.
**OSPF external routing table** – includes a list of acquired routes that are
external to the OSPF process. "E" flag points to the external link metric type
(E1 – metric type 1, E2 – metric type 2). External link metric is printed in
the "<metric of the router which advertised the link>/<link metric>" format.

.. opcmd:: show ip ospf border-routers

   This command displays a table of paths to area boundary and autonomous
   system boundary routers.

.. opcmd:: show ip ospf database

   This command displays a summary table with a database contents (LSA).

.. code-block:: none

          OSPF Router with ID (10.0.13.1)

                   Router Link States (Area 0.0.0.0)

   Link ID         ADV Router      Age  Seq#       CkSum  Link count
   10.0.13.1       10.0.13.1        984 0x80000005 0xd915 1
   10.0.23.3       10.0.23.3       1186 0x80000008 0xfe62 2
   10.0.34.4       10.0.34.4       1063 0x80000004 0x4e3f 1

                   Net Link States (Area 0.0.0.0)

   Link ID         ADV Router      Age  Seq#       CkSum
   10.0.13.1       10.0.13.1        994 0x80000003 0x30bb
   10.0.34.4       10.0.34.4       1188 0x80000001 0x9411

                   Summary Link States (Area 0.0.0.0)

   Link ID         ADV Router      Age  Seq#       CkSum  Route
   10.0.12.0       10.0.23.3       1608 0x80000001 0x6ab6 10.0.12.0/24
   10.0.23.0       10.0.23.3        981 0x80000003 0xe232 10.0.23.0/24

                   AS External Link States

   Link ID         ADV Router      Age  Seq#       CkSum  Route
   172.16.0.0      10.0.34.4       1063 0x80000001 0xc40d E2 172.16.0.0/24 [0x0]

.. opcmd:: show ip ospf database <type> [A.B.C.D]
  [adv-router <A.B.C.D>|self-originate]

   This command displays a database contents for a specific link advertisement
   type.

   The type can be the following:
   asbr-summary, external, network, nssa-external, opaque-area, opaque-as,
   opaque-link, router, summary.

   [A.B.C.D] – link-state-id. With this specified the command displays portion
   of the network environment that is being described by the advertisement.
   The value entered depends on the advertisement’s LS type. It must be
   entered in the form of an IP address.

   :cfgcmd:`adv-router <A.B.C.D>` – router id, which link advertisements need
   to be reviewed.

   :cfgcmd:`self-originate` displays only self-originated LSAs from the local
   router.

.. code-block:: none

             OSPF Router with ID (10.0.13.1)

                   Router Link States (Area 0.0.0.0)

     LS age: 1213
     Options: 0x2  : *|-|-|-|-|-|E|-
     LS Flags: 0x3
     Flags: 0x0
     LS Type: router-LSA
     Link State ID: 10.0.13.1
     Advertising Router: 10.0.13.1
     LS Seq Number: 80000009
     Checksum: 0xd119
     Length: 36

      Number of Links: 1

       Link connected to: a Transit Network
        (Link ID) Designated Router address: 10.0.13.1
        (Link Data) Router Interface address: 10.0.13.1
        Number of TOS metrics: 0
          TOS 0 Metric: 1

.. opcmd:: show ip ospf database max-age

   This command displays LSAs in MaxAge list.


Examples
--------


Enable OSPF
^^^^^^^^^^^

**Node 1**

.. code-block:: none

  set interfaces loopback lo address 10.1.1.1/32
  set interfaces ethernet eth0 address 192.168.0.1/24
  set protocols ospf area 0 network 192.168.0.0/24
  set protocols ospf area 0 network 10.1.1.1/32
  set protocols ospf parameters router-id 10.1.1.1

**Node 2**

.. code-block:: none

  set interfaces loopback lo address 10.1.1.2/32
  set interfaces ethernet eth0 address 192.168.0.2/24
  set protocols ospf area 0 network 192.168.0.0/24
  set protocols ospf area 0 network 10.1.1.2/32
  set protocols ospf parameters router-id 10.1.1.2



Here's the neighbors up:

.. code-block:: none

  Node-1@vyos:~$ show ip ospf neighbor

  Neighbor ID     Pri State           Up Time         Dead Time Address         Interface                        RXmtL RqstL DBsmL
  10.1.1.2          1 Full/DR         3m43s             36.094s 192.168.0.2     eth0:192.168.0.1                     0     0     0



  Node-2@vyos:~$ show ip ospf neighbor

  Neighbor ID     Pri State           Up Time         Dead Time Address         Interface                        RXmtL RqstL DBsmL
  10.1.1.1          1 Full/Backup     3m47s             31.736s 192.168.0.1     eth0:192.168.0.2                     0     0     0

Here's the routes:

.. code-block:: none

  Node-1@vyos:~$ show ip route ospf
  Codes: K - kernel route, C - connected, S - static, R - RIP,
         O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
         T - Table, v - VNC, V - VNC-Direct, A - Babel, F - PBR,
         f - OpenFabric,
         > - selected route, * - FIB route, q - queued, r - rejected, b - backup
         t - trapped, o - offload failure

  O   10.1.1.1/32 [110/0] is directly connected, lo, weight 1, 00:00:14
  O>* 10.1.1.2/32 [110/1] via 192.168.0.2, eth0, weight 1, 00:00:07
  O   192.168.0.0/24 [110/1] is directly connected, eth0, weight 1, 00:03:32

  Node-2@vyos:~$ show ip route ospf
  Codes: K - kernel route, C - connected, S - static, R - RIP,
         O - OSPF, I - IS-IS, B - BGP, E - EIGRP, N - NHRP,
         T - Table, v - VNC, V - VNC-Direct, A - Babel, F - PBR,
         f - OpenFabric,
         > - selected route, * - FIB route, q - queued, r - rejected, b - backup
         t - trapped, o - offload failure

  O>* 10.1.1.1/32 [110/1] via 192.168.0.1, eth0, weight 1, 00:00:11
  O   10.1.1.2/32 [110/0] is directly connected, lo, weight 1, 00:00:04
  O   192.168.0.0/24 [110/1] is directly connected, eth0, weight 1, 00:03:18





Enable OSPF with route redistribution of the loopback and default originate:
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Node 1**

.. code-block:: none

  set interfaces loopback lo address 10.1.1.1/32
  set protocols ospf area 0 network 192.168.0.0/24
  set protocols ospf default-information originate always
  set protocols ospf default-information originate metric 10
  set protocols ospf default-information originate metric-type 2
  set protocols ospf log-adjacency-changes
  set protocols ospf parameters router-id 10.1.1.1
  set protocols ospf redistribute connected metric-type 2
  set protocols ospf redistribute connected route-map CONNECT

  set policy route-map CONNECT rule 10 action permit
  set policy route-map CONNECT rule 10 match interface lo

**Node 2**

.. code-block:: none

  set interfaces loopback lo address 10.2.2.2/32
  set protocols ospf area 0 network 192.168.0.0/24
  set protocols ospf log-adjacency-changes
  set protocols ospf parameters router-id 10.2.2.2
  set protocols ospf redistribute connected metric-type 2
  set protocols ospf redistribute connected route-map CONNECT

  set policy route-map CONNECT rule 10 action permit
  set policy route-map CONNECT rule 10 match interface lo


Enable OSPF and IGP-LDP synchronization:
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Node 1:**

.. code-block:: none

  set interfaces loopback lo address 10.1.1.1/32
  set interfaces ethernet eth0 address 192.168.0.1/24

  set protocols ospf area 0 network '192.168.0.0/24'
  set protocols ospf area 0 network '10.1.1.1/32'
  set protocols ospf parameters router-id '10.1.1.1'
  set protocols ospf ldp-sync

  set protocols mpls interface eth0
  set protocols mpls ldp discovery transport-ipv4-address 10.1.1.1
  set protocols mpls ldp interface lo
  set protocols mpls ldp interface eth0
  set protocols mpls ldp parameters transport-prefer-ipv4
  set protocols mpls ldp router-id 10.1.1.1


This gives us IGP-LDP synchronization for all non-loopback interfaces with
a holddown timer of zero seconds:


.. code-block:: none

  Node-1@vyos:~$ show ip ospf mpls ldp-sync
    eth0
    LDP-IGP Synchronization enabled: yes
    Holddown timer in seconds: 0
    State: Sync achieved



Enable OSPF with Segment Routing (Experimental):
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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




.. _routing-ospfv3:

*************
OSPFv3 (IPv6)
*************

.. _ospf:v3_configuration:

Configuration
=============

.. _ospf:v3_general:

General
-------

VyOS does not have a special command to start the OSPFv3 process. The OSPFv3
process starts when the first ospf enabled interface is configured.

.. cfgcmd:: set protocols ospfv3 interface <interface> area <number>

   This command specifies the OSPFv3 enabled interface. This command is also
   used to enable the OSPF process. The area number can be specified in
   decimal notation in the range from 0 to 4294967295. Or it can be specified
   in dotted decimal notation similar to ip address.

.. cfgcmd:: set protocols ospfv3 parameters router-id <rid>

   This command sets the router-ID of the OSPFv3 process. The router-ID may be
   an IP address of the router, but need not be – it can be any arbitrary
   32bit number. However it MUST be unique within the entire OSPFv3 domain to
   the OSPFv3 speaker – bad things will happen if multiple OSPFv3 speakers are
   configured with the same router-ID!


.. _ospf:v3_optional:

Optional
--------

.. cfgcmd:: set protocols ospfv3 distance global <distance>

   This command change distance value of OSPFv3 globally.
   The distance range is 1 to 255.

.. cfgcmd:: set protocols ospfv3 distance ospfv3
   <external|inter-area|intra-area> <distance>

   This command change distance value of OSPFv3. The arguments are the
   distance values for external routes, inter-area routes and intra-area
   routes respectively. The distance range is 1 to 255.

.. _ospf:v3_area_configuration:

Area Configuration
------------------

.. cfgcmd:: set protocols ospfv3 area <number> range <prefix>

   This command summarizes intra area paths from specified area into one
   Type-3 Inter-Area Prefix LSA announced to other areas. This command can be
   used only in ABR.

.. cfgcmd:: set protocols ospfv3 area <number> range <prefix> not-advertise

   This command instead of summarizing intra area paths filter them - i.e.
   intra area paths from this range are not advertised into other areas. This
   command makes sense in ABR only.

.. _ospf:v3_interface_config:

Interface Configuration
-----------------------

.. cfgcmd:: set protocols ospfv3 interface <interface> ipv6 cost <number>

   This command sets link cost for the specified interface. The cost value is
   set to router-LSA’s metric field and used for SPF calculation. The cost
   range is 1 to 65535.

.. cfgcmd:: set protocols ospfv3 interface <interface> dead-interval <number>

   Set number of seconds for router Dead Interval timer value used for Wait
   Timer and Inactivity Timer. This value must be the same for all routers
   attached to a common network. The default value is 40 seconds. The
   interval range is 1 to 65535.

.. cfgcmd:: set protocols ospfv3 interface <interface> hello-interval
   <number>

   Set number of seconds for Hello Interval timer value. Setting this value,
   Hello packet will be sent every timer value seconds on the specified
   interface. This value must be the same for all routers attached to a
   common network. The default value is 10 seconds. The interval range is 1
   to 65535.

.. cfgcmd:: set protocols ospfv3 interface <interface> mtu-ignore

   This command disables check of the MTU value in the OSPF DBD packets.
   Thus, use of this command allows the OSPF adjacency to reach the FULL
   state even though there is an interface MTU mismatch between two OSPF
   routers.

.. cfgcmd:: set protocols ospfv3 interface <interface> network <type>

   This command allows to specify the distribution type for the network
   connected to this interface:

   **broadcast** – broadcast IP addresses distribution.
   **point-to-point** – address distribution in point-to-point networks.

.. cfgcmd:: set protocols ospfv3 interface <interface> priority <number>

   This command sets Router Priority integer value. The router with the
   highest priority will be more eligible to become Designated Router.
   Setting the value to 0, makes the router ineligible to become Designated
   Router. The default value is 1. The interval range is 0 to 255.

.. cfgcmd:: set protocols ospfv3 interface <interface> passive

   This command specifies interface as passive. Passive interface advertises
   its address, but does not run the OSPF protocol (adjacencies are not formed
   and hello packets are not generated).

.. cfgcmd:: set protocols ospfv3 interface <interface> retransmit-interval
   <number>

   This command sets number of seconds for RxmtInterval timer value. This
   value is used when retransmitting Database Description and Link State
   Request packets if acknowledge was not received. The default value is 5
   seconds. The interval range is 3 to 65535.

.. cfgcmd:: set protocols ospfv3 interface <interface> transmit-delay
   <number>

   This command sets number of seconds for InfTransDelay value. It allows to
   set and adjust for each interface the delay interval before starting the
   synchronizing process of the router's database with all neighbors. The
   default value is 1 seconds. The interval range is 3 to 65535.

.. _ospf:v3_graceful_restart:

Graceful Restart
----------------

.. cfgcmd:: set protocols ospfv3 graceful-restart [grace-period (1-1800)]

   Configure Graceful Restart :rfc:`3623` restarting support. When enabled,
   the default grace period is 120 seconds.

   To perform a graceful shutdown, the FRR ``graceful-restart prepare ip
   ospf`` EXEC-level command needs to be issued before restarting the
   ospfd daemon.

.. cfgcmd:: set protocols ospfv3 graceful-restart helper enable [router-id A.B.C.D]

   Configure Graceful Restart :rfc:`3623` helper support. By default, helper support
   is disabled for all neighbours. This config enables/disables helper support
   on this router for all neighbours.

   To enable/disable helper support for a specific neighbour, the router-id
   (A.B.C.D) has to be specified.

.. cfgcmd:: set protocols ospfv3 graceful-restart helper lsa-check-disable

   By default `strict-lsa-checking` is configured then the helper will abort
   the Graceful Restart when a LSA change occurs which affects the restarting
   router.

   This command disables it.

.. cfgcmd:: set protocols ospfv3 graceful-restart helper supported-grace-time

   Supports as HELPER for configured grace period.

.. cfgcmd:: set protocols ospfv3 graceful-restart helper planned-only

   It helps to support as HELPER only for planned restarts.

   By default, it supports both planned and unplanned outages.

.. _ospf:v3_redistribution_config:

Redistribution Configuration
----------------------------

.. cfgcmd:: set protocols ospfv3 redistribute <route source>

   This command redistributes routing information from the given route source
   to the OSPFv3 process. There are five modes available for route source:
   bgp, connected, kernel, ripng, static.

.. cfgcmd:: set protocols ospf redistribute <route source> route-map <name>

   This command allows to use route map to filter redistributed routes from
   given route source. There are five modes available for route source: bgp,
   connected, kernel, ripng, static.

.. _ospf:v3_op_cmd:

Operational Mode Commands
-------------------------

.. opcmd:: show ipv6 ospfv3 neighbor

   This command displays the neighbors status.

.. opcmd:: show ipv6 ospfv3 neighbor detail

   This command displays the neighbors information in a detailed form, not
   just a summary table.

.. opcmd:: show ipv6 ospfv3 neighbor drchoice

   This command displays the neighbor DR choice information.

.. opcmd:: show ipv6 ospfv3 interface [prefix]|[<interface> [prefix]]

   This command displays state and configuration of OSPF the specified
   interface, or all interfaces if no interface is given. Whith the argument
   :cfgcmd:`prefix` this command shows connected prefixes to advertise.

.. opcmd:: show ipv6 ospfv3 route

   This command displays the OSPF routing table, as determined by the most
   recent SPF calculation.

.. opcmd:: show ipv6 ospfv3 border-routers

   This command displays a table of paths to area boundary and autonomous
   system boundary routers.

.. opcmd:: show ipv6 ospfv3 database

   This command displays a summary table with a database contents (LSA).

.. opcmd:: show ipv6 ospfv3 database <type> [A.B.C.D]
   [adv-router <A.B.C.D>|self-originate]

   This command displays a database contents for a specific link
   advertisement type.

.. opcmd:: show ipv6 ospfv3 redistribute

   This command displays external information redistributed into OSPFv3

.. _ospf:v3_config_example:

Configuration Example
---------------------

A typical configuration using 2 nodes.

**Node 1:**

.. code-block:: none

  set protocols ospfv3 interface eth1 area 0.0.0.0
  set protocols ospfv3 area 0.0.0.0 range 2001:db8:1::/64
  set protocols ospfv3 parameters router-id 192.168.1.1
  set protocols ospfv3 redistribute connected

**Node 2:**

.. code-block:: none

  set protocols ospfv3 interface eth1 area 0.0.0.0
  set protocols ospfv3 area 0.0.0.0 range 2001:db8:2::/64
  set protocols ospfv3 parameters router-id 192.168.2.1
  set protocols ospfv3 redistribute connected

**To see the redistributed routes:**

.. code-block:: none

  show ipv6 ospfv3 redistribute

Cost calculation wireguard interfaces is unreliable as ospfv3 uses the link speed to calculate the link cost.
You might therefore want to set the link cost to a fixed value on WireGuard tunnels.

Example configuration for WireGuard interfaces:

**Node 1**

.. code-block:: none

  set interfaces wireguard wg01 peer ospf02 allowed-ips '::/0'
  set interfaces wireguard wg01 peer ospf02 endpoint '10.1.1.101:12345'
  set interfaces wireguard wg01 peer ospf02 pubkey 'ie3...='
  set interfaces wireguard wg01 port '12345'
  set protocols ospfv3 parameters router-id 192.168.1.1
  set protocols ospfv3 interface 'wg01' area 0.0.0.0
  set protocols ospfv3 interface 'wg01' cost 10
  set protocols ospfv3 interface 'lo' area 0.0.0.0

**Node 2**

.. code-block:: none

  set interfaces wireguard wg01 peer ospf01 allowed-ips '::/0'
  set interfaces wireguard wg01 peer ospf01 endpoint '10.1.1.100:12345'
  set interfaces wireguard wg01 peer ospf01 pubkey 'NHI...='
  set interfaces wireguard wg01 port '12345'
  set protocols ospfv3 parameters router-id 192.168.1.2
  set protocols ospfv3 interface 'wg01' area 0.0.0.0
  set protocols ospfv3 interface 'wg01' cost 10
  set protocols ospfv3 interface 'lo' area 0.0.0.0

**Status**

.. code-block:: none

  vyos@ospf01:~$ sh ipv6 ospfv3 neighbor
  Neighbor ID     Pri    DeadTime    State/IfState         Duration I/F[State]
  192.168.0.2       1    00:00:37     Full/PointToPoint    00:18:03 wg01[PointToPoint]

  vyos@ospf02# run sh ipv6 ospfv3 neighbor
  Neighbor ID     Pri    DeadTime    State/IfState         Duration I/F[State]
  192.168.0.1       1    00:00:39     Full/PointToPoint    00:19:44 wg01[PointToPoint]

