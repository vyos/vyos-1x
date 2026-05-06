####
IPv6
####

System configuration commands
-----------------------------

.. cfgcmd:: set system ipv6 disable-forwarding

   Use this command to disable IPv6 forwarding on all interfaces.

.. cfgcmd:: set system ipv6 neighbor table-size <number>

   Use this command to define the maximum number of entries to keep in
   the Neighbor cache (1024, 2048, 4096, 8192, 16384, 32768).

.. cfgcmd:: set system ipv6 strict-dad

   Use this command to disable IPv6 operation on interface when
   Duplicate Address Detection fails on Link-Local address.

.. cfgcmd:: set system ipv6 multipath layer4-hashing

   Use this command to user Layer 4 information for ECMP hashing.

Zebra/Kernel route filtering
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Zebra supports prefix-lists and Route Maps to match routes received from
other FRR components. The permit/deny facilities provided by these commands
can be used to filter which routes zebra will install in the kernel.

.. cfgcmd:: set system ipv6 protocol <protocol> route-map <route-map>

   Apply a route-map filter to routes for the specified protocol. The following
   protocols can be used: any, babel, bgp, isis, ospfv3, ripng, static

   .. note:: If you choose any as the option that will cause all protocols that
      are sending routes to zebra.

Nexthop Tracking
^^^^^^^^^^^^^^^^

Nexthop tracking resolve nexthops via the default route by default. This is enabled
by default for a traditional profile of FRR which we use. It and can be disabled if
you do not want to e.g. allow BGP to peer across the default route.

.. cfgcmd:: set system ipv6 nht no-resolve-via-default

   Do not allow IPv6 nexthop tracking to resolve via the default route. This
   parameter is configured per-VRF, so the command is also available in the VRF
   subnode.

Operational commands
--------------------

Show commands
^^^^^^^^^^^^^

.. opcmd:: show ipv6 neighbors

   Use this command to show IPv6 Neighbor Discovery Protocol information.

.. opcmd:: show ipv6 groups

   Use this command to show IPv6 multicast group membership.

.. opcmd:: show ipv6 forwarding

   Use this command to show IPv6 forwarding status.

.. opcmd:: show ipv6 route

   Use this command to show IPv6 routes.

   Check the many parameters available for the `show ipv6 route` command:

   .. code-block:: none

      vyos@vyos:~$ show ipv6 route
      Possible completions:
        <Enter>       Execute the current command
        <X:X::X:X>    Show IPv6 routes of given address or prefix
        <X:X::X:X/M>
        bgp           Show IPv6 BGP routes
        cache         Show kernel IPv6 route cache
        connected     Show IPv6 connected routes
        forward       Show kernel IPv6 route table
        isis          Show IPv6 ISIS routes
        kernel        Show IPv6 kernel routes
        ospfv3        Show IPv6 OSPF6 routes
        ripng         Show IPv6 RIPNG routes
        static        Show IPv6 static routes
        summary       Show IPv6 routes summary
        table         Show IP routes in policy table
        tag           Show only routes with tag
        vrf           Show IPv6 routes in VRF


.. opcmd:: show ipv6 prefix-list

   Use this command to show all IPv6 prefix lists

   There are different parameters for getting prefix-list information:

   .. code-block:: none

      vyos@vyos:~$ show ipv6 prefix-list
      Possible completions:
        <Enter>       Execute the current command
        <WORD>        Show specified IPv6 prefix-list
        detail        Show detail of IPv6 prefix-lists
        summary       Show summary of IPv6 prefix-lists

.. opcmd:: show ipv6 access-list

   Use this command to show all IPv6 access lists

   You can also specify which IPv6 access-list should be shown:

   .. code-block:: none

      vyos@vyos:~$ show ipv6 access-list
      Possible completions:
        <Enter>       Execute the current command
        <text>        Show specified IPv6 access-list



.. opcmd:: show ipv6 ospfv3

   Use this command to get information about OSPFv3.

   You can get more specific OSPFv3 information by using the parameters
   shown below:

   .. code-block:: none

      vyos@vyos:~$ show ipv6 ospfv3
      Possible completions:
        <Enter>       Execute the current command
        area          Show OSPFv3 spf-tree information
        border-routers
                      Show OSPFv3 border-router (ABR and ASBR) information
        database      Show OSPFv3 Link state database information
        interface     Show OSPFv3 interface information
        linkstate     Show OSPFv3 linkstate routing information
        neighbor      Show OSPFv3 neighbor information
        redistribute  Show OSPFv3 redistribute External information
        route         Show OSPFv3 routing table information

.. opcmd:: show ipv6 ripng

   Use this command to get information about the RIPNG protocol

.. opcmd:: show ipv6 ripng status

   Use this command to show the status of the RIPNG protocol


Reset commands
^^^^^^^^^^^^^^

.. opcmd:: reset bgp ipv6 <address>

   Use this command to clear Border Gateway Protocol statistics or
   status.


.. opcmd:: reset ipv6 neighbors <address | interface>

   Use this command to reset IPv6 Neighbor Discovery Protocol cache for
   an address or interface.

.. opcmd:: reset ipv6 route cache

   Use this command to flush the kernel IPv6 route cache.
   An address can be added to flush it only for that route.
