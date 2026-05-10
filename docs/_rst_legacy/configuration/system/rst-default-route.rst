.. _default_gateway:

#####################
Default Gateway/Route
#####################

In the past (VyOS 1.1) used a gateway-address configured under the system tree
(:cfgcmd:`set system gateway-address <address>`), this is no longer supported
and existing configurations are migrated to the new CLI command.

Configuration
=============

.. cfgcmd:: set protocols static route 0.0.0.0/0 next-hop <address>

   Specify static route into the routing table sending all non local traffic
   to the nexthop address `<address>`.


.. cfgcmd:: delete protocols static route 0.0.0.0/0

   Delete default route from the system.

Operation
=========

.. opcmd:: show ip route 0.0.0.0

   Show routing table entry for the default route.

   .. code-block:: none

      vyos@vyos:~$ show ip route 0.0.0.0
      Routing entry for 0.0.0.0/0
        Known via "static", distance 10, metric 0, best
        Last update 09:46:30 ago
        * 172.18.201.254, via eth0.201

.. seealso:: Configuration of :ref:`routing-static`

