:lastproofread: 2021-10-04

.. _rip:

###
RIP
###

:abbr:`RIP (Routing Information Protocol)` is a widely deployed interior gateway
protocol. RIP was developed in the 1970s at Xerox Labs as part of the XNS
routing protocol. RIP is a distance-vector protocol and is based on the
Bellman-Ford algorithms. As a distance-vector protocol, RIP router send updates
to its neighbors periodically, thus allowing the convergence to a known
topology. In each update, the distance to any given network will be broadcast
to its neighboring router.

Supported versions of RIP are:

 - RIPv1 as described in :rfc:`1058`
 - RIPv2 as described in :rfc:`2453`

General Configuration
---------------------

.. cfgcmd:: set protocols rip network <A.B.C.D/M>

  This command enables RIP and sets the RIP enable interface by NETWORK.
  The interfaces which have addresses matching with NETWORK are enabled.
  
.. cfgcmd:: set protocols rip interface <interface>

  This command specifies a RIP enabled interface by interface name. Both
  the sending and receiving of RIP packets will be enabled on the port
  specified in this command.
  
.. cfgcmd:: set protocols rip neighbor <A.B.C.D>

  This command specifies a RIP neighbor. When a neighbor doesn’t understand
  multicast, this command is used to specify neighbors. In some cases, not
  all routers will be able to understand multicasting, where packets are
  sent to a network or a group of addresses. In a situation where a neighbor
  cannot process multicast packets, it is necessary to establish a direct
  link between routers.

.. cfgcmd:: set protocols rip passive-interface interface <interface>

  This command sets the specified interface to passive mode. On passive mode
  interface, all receiving packets are processed as normal and VyOS does not
  send either multicast or unicast RIP packets except to RIP neighbors
  specified with neighbor command.
  
.. cfgcmd:: set protocols rip passive-interface interface default

  This command specifies all interfaces to passive mode.


Optional Configuration
----------------------

.. cfgcmd:: set protocols rip default-distance <distance>

  This command change the distance value of RIP. The distance range is 1 to 255.
   
   .. note:: Routes with a distance of 255 are effectively disabled and not
      installed into the kernel.

.. cfgcmd:: set protocols rip network-distance <A.B.C.D/M> distance <distance>

  This command sets default RIP distance to a specified value when the routes
  source IP address matches the specified prefix.
  
.. cfgcmd:: set protocols rip network-distance <A.B.C.D/M> access-list <name>

  This command can be used with previous command to sets default RIP distance
  to specified value when the route source IP address matches the specified
  prefix and the specified access-list.

.. cfgcmd:: set protocols rip default-information originate

  This command generate a default route into the RIP.

.. cfgcmd:: set protocols rip distribute-list access-list <in|out> <number>

  This command can be used to filter the RIP path using access lists.
  :cfgcmd:`in` and :cfgcmd:`out` this is the direction in which the access
  lists are applied.
  
.. cfgcmd:: set protocols rip distribute-list interface <interface> access-list <in|out> <number>

  This command allows you apply access lists to a chosen interface to
  filter the RIP path.
  
.. cfgcmd:: set protocols rip distribute-list prefix-list <in|out> <name>

  This command can be used to filter the RIP path using prefix lists.
  :cfgcmd:`in` and :cfgcmd:`out` this is the direction in which the prefix
  lists are applied.

.. cfgcmd:: set protocols rip distribute-list interface <interface> prefix-list <in|out> <name>

  This command allows you apply prefix lists to a chosen interface to
  filter the RIP path.

.. cfgcmd:: set protocols rip route <A.B.C.D/M>

  This command is specific to FRR and VyOS. The route command makes a static
  route only inside RIP. This command should be used only by advanced users
  who are particularly knowledgeable about the RIP protocol. In most cases,
  we recommend creating a static route in VyOS and redistributing it in RIP
  using :cfgcmd:`redistribute static`.
  
.. cfgcmd:: set protocols rip timers update <seconds>

  This command specifies the update timer. Every update timer seconds, the
  RIP process is awakened to send an unsolicited response message containing
  the complete routing table to all neighboring RIP routers. The time range
  is 5 to 2147483647. The default value is 30 seconds.

.. cfgcmd:: set protocols rip timers timeout <seconds>

  This command specifies the timeout timer. Upon expiration of the timeout,
  the route is no longer valid; however, it is retained in the routing table
  for a short time so that neighbors can be notified that the route has been
  dropped. The time range is 5 to 2147483647. The default value is 180
  seconds.

.. cfgcmd:: set protocols rip timers garbage-collection <seconds>

  This command specifies the garbage-collection timer. Upon expiration of
  the garbage-collection timer, the route is finally removed from the
  routing table. The time range is 5 to 2147483647. The default value is 120
  seconds.


Redistribution Configuration
----------------------------

.. cfgcmd:: set protocols rip redistribute <route source>

  This command redistributes routing information from the given route source
  into the RIP tables. There are five modes available for route source: bgp,
  connected, kernel, ospf, static.

.. cfgcmd:: set protocols rip redistribute <route source> metric <metric>

  This command specifies metric for redistributed routes from the given route
  source. There are five modes available for route source: bgp, connected,
  kernel, ospf, static. The metric range is 1 to 16. 
  
.. cfgcmd:: set protocols rip redistribute <route source> route-map <name>

  This command allows to use route map to filter redistributed routes from
  the given route source. There are five modes available for route source:
  bgp, connected, kernel, ospf, static.

.. cfgcmd:: set protocols rip default-metric <metric>

  This command modifies the default metric (hop count) value for redistributed
  routes. The metric range is 1 to 16. The default value is 1. This command
  does not affect connected route even if it is redistributed by
  :cfgcmd:`redistribute connected`. To modify connected routes metric
  value, please use :cfgcmd:`redistribute connected metric`.


Interfaces Configuration
------------------------

.. cfgcmd:: set interfaces <inttype> <intname> ip rip authentication plaintext-password <text>

  This command sets the interface with RIP simple password authentication.
  This command also sets authentication string. The string must be shorter
  than 16 characters.

.. cfgcmd:: set interfaces <inttype> <intname> ip rip authentication md5 <id> password <text>

  This command sets the interface with RIP MD5 authentication. This command
  also sets MD5 Key. The key must be shorter than 16 characters.

.. cfgcmd:: set interfaces <inttype> <intname> ip rip split-horizon disable

  This command disables split-horizon on the interface. By default, VyOS does
  not advertise RIP routes out the interface over which they were learned
  (split horizon).3
  
.. cfgcmd:: set interfaces <inttype> <intname> ip rip split-horizon poison-reverse

  This command enables poison-reverse on the interface. If both poison reverse
  and split horizon are enabled, then VyOS advertises the learned routes
  as unreachable over the interface on which the route was learned.


Operational Mode Commands
-------------------------

.. opcmd:: show ip rip

  This command displays RIP routes.

.. code-block:: none

  Codes: R - RIP, C - connected, S - Static, O - OSPF, B - BGP
  Sub-codes:
        (n) - normal, (s) - static, (d) - default, (r) - redistribute,
        (i) - interface
  
       Network            Next Hop         Metric From            Tag Time
  C(i) 10.0.12.0/24       0.0.0.0               1 self              0
  C(i) 10.0.13.0/24       0.0.0.0               1 self              0
  R(n) 10.0.23.0/24       10.0.12.2             2 10.0.12.2         0 02:53

.. opcmd:: show ip rip status

  The command displays current RIP status. It includes RIP timer, filtering,
  version, RIP enabled interface and RIP peer information.

.. code-block:: none

  Routing Protocol is "rip"
    Sending updates every 30 seconds with +/-50%, next due in 11 seconds
    Timeout after 180 seconds, garbage collect after 120 seconds
    Outgoing update filter list for all interface is not set
    Incoming update filter list for all interface is not set
    Default redistribution metric is 1
    Redistributing:
    Default version control: send version 2, receive any version
      Interface        Send  Recv   Key-chain
      eth0             2     1 2
      eth2             2     1 2
    Routing for Networks:
      10.0.12.0/24
      eth0
    Routing Information Sources:
      Gateway          BadPackets BadRoutes  Distance Last Update
      10.0.12.2                0         0       120   00:00:11
    Distance: (default is 120)
  

Configuration Example
---------------------

Simple RIP configuration using 2 nodes and redistributing connected interfaces.

**Node 1:**

.. code-block:: none

  set interfaces loopback address 10.1.1.1/32
  set protocols rip network 192.168.0.0/24
  set protocols rip redistribute connected

**Node 2:**

.. code-block:: none

  set interfaces loopback address 10.2.2.2/32
  set protocols rip network 192.168.0.0/24
  set protocols rip redistribute connected
