##
IP
##

System configuration commands
-----------------------------

.. cfgcmd:: set system ip disable-forwarding

   Use this command to disable IPv4 forwarding on all interfaces.

.. cfgcmd:: set system ip disable-directed-broadcast

   Use this command to disable IPv4 directed broadcast forwarding on all
   interfaces.

   If set, IPv4 directed broadcast forwarding will be completely disabled
   regardless of whether per-interface directed broadcast forwarding is
   enabled or not.

.. cfgcmd:: set system ip arp table-size <number>

   Use this command to define the maximum number of entries to keep in
   the ARP cache (1024, 2048, 4096, 8192, 16384, 32768).

.. cfgcmd:: set system ip multipath layer4-hashing

   Use this command to use Layer 4 information for IPv4 ECMP hashing.

.. cfgcmd:: set system ip import-table <table-id>

   Use this command to immport the table, by given table id, into the main RIB.

.. cfgcmd:: set system ip import-table <table-id> distance <distance>

   Use this command to override the default distance when importing routers
   from the alternate table.

.. cfgcmd:: set system ip import-table <table-id> route-map <route-map>

   Use this command to filter routes that are imported into the main table
   from alternate table using route-map.

Zebra/Kernel route filtering
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Zebra supports prefix-lists and Route Maps to match routes received from
other FRR components. The permit/deny facilities provided by these commands
can be used to filter which routes zebra will install in the kernel.

.. cfgcmd:: set system ip protocol <protocol> route-map <route-map>

   Apply a route-map filter to routes for the specified protocol. The following
   protocols can be used: any, babel, bgp, eigrp, isis, ospf, rip, static

   .. note:: If you choose any as the option that will cause all protocols that
      are sending routes to zebra.

Nexthop Tracking
^^^^^^^^^^^^^^^^

Nexthop tracking resolve nexthops via the default route by default. This is enabled
by default for a traditional profile of FRR which we use. It and can be disabled if
you do not want to e.g. allow BGP to peer across the default route.

.. cfgcmd:: set system ip nht no-resolve-via-default

   Do not allow IPv4 nexthop tracking to resolve via the default route. This
   parameter is configured per-VRF, so the command is also available in the VRF
   subnode.

Operational commands
--------------------

show commands
^^^^^^^^^^^^^

See below the different parameters available for the IPv4 **show** command:

.. code-block:: none

   vyos@vyos:~$ show ip
   Possible completions:
     access-list   Show all IP access-lists
     as-path-access-list
                   Show all as-path-access-lists
     bgp           Show Border Gateway Protocol (BGP) information
     community-list
                   Show IP community-lists
     extcommunity-list
                   Show extended IP community-lists
     forwarding    Show IP forwarding status
     groups        Show IP multicast group membership
     igmp          Show IGMP (Internet Group Management Protocol) information
     large-community-list
                   Show IP large-community-lists
     multicast     Show IP multicast
     ospf          Show IPv4 Open Shortest Path First (OSPF) routing information
     pim           Show PIM (Protocol Independent Multicast) information
     ports         Show IP ports in use by various system services
     prefix-list   Show all IP prefix-lists
     protocol      Show IP route-maps per protocol
     rip           Show Routing Information Protocol (RIP) information
     route         Show IP routes


reset commands
^^^^^^^^^^^^^^

And the different IPv4 **reset** commands available:

.. code-block:: none

   vyos@vyos:~$ reset ip
   Possible completions:
     arp           Reset Address Resolution Protocol (ARP) cache
     bgp           Clear Border Gateway Protocol (BGP) statistics or status
     igmp          IGMP clear commands
     multicast     IP multicast routing table
     route         Reset IP route
